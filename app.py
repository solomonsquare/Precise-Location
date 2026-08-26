import json
import logging
import math
import os
import re
import threading

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024

MAPBOX_ACCESS_TOKEN = os.getenv('MAPBOX_ACCESS_TOKEN')
OVERPASS_API_URL = os.getenv(
    'OVERPASS_API_URL',
    'https://overpass-api.de/api/interpreter'
)
OVERPASS_QUERY_TIMEOUT_SECONDS = 12
OVERPASS_HTTP_TIMEOUT = (3.05, 18)
OVERPASS_MAX_RESULTS = 2_000
OVERPASS_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_SEARCH_TERM_LENGTH = 80
MAX_BOUNDING_BOX_SPAN_DEGREES = 5
OVERPASS_MAX_CONCURRENT_REQUESTS = 2
OVERPASS_CONCURRENCY_GATE = threading.BoundedSemaphore(
    OVERPASS_MAX_CONCURRENT_REQUESTS
)

if not MAPBOX_ACCESS_TOKEN:
    logger.error('Mapbox access token not found in environment variables')


class UpstreamResponseTooLarge(Exception):
    pass


def get_osm_filters(search_term):
    """Translate a user-facing place type into safe OSM tag selectors."""
    term = search_term.lower()

    if 'train station' in term or term == 'train_station':
        return ['["railway"="station"]']
    if 'bus station' in term or term == 'bus_station':
        return ['["amenity"="bus_station"]']
    if any(value in term for value in ('bbq', 'barbecue', 'barbeque')):
        return ['["amenity"="bbq"]']
    if 'garden' in term:
        return ['["garden:type"="botanical"]']
    if 'marketplace' in term or term == 'market':
        return ['["amenity"="marketplace"]']
    if 'skate' in term or term == 'skateboard_pitch':
        return ['["leisure"="pitch"]["sport"="skateboard"]']
    if 'playground' in term:
        return ['["leisure"="playground"]']
    if 'sports' in term or term == 'sports_centre':
        return ['["leisure"="sports_centre"]']
    if 'shopping mall' in term or 'mall' in term:
        return ['["shop"~"^(mall|department_store)$"]']
    if 'supermarket' in term:
        return ['["shop"="supermarket"]']
    if 'restaurant' in term:
        return ['["amenity"="restaurant"]']
    if 'cafe' in term:
        return ['["amenity"="cafe"]']
    if 'bar' in term or 'pub' in term:
        return ['["amenity"~"^(bar|pub)$"]']
    if 'hotel' in term:
        return ['["tourism"="hotel"]']
    if any(value in term for value in ('night', 'club', 'nightclub')):
        return ['["amenity"="nightclub"]']
    if 'school' in term:
        return ['["amenity"="school"]']
    if 'university' in term:
        return ['["amenity"="university"]']
    if 'hospital' in term:
        return ['["amenity"="hospital"]']
    if 'pharmacy' in term:
        return ['["amenity"="pharmacy"]']
    if 'bank' in term:
        return ['["amenity"="bank"]']
    if 'post office' in term:
        return ['["amenity"="post_office"]']
    if 'police' in term:
        return ['["amenity"="police"]']
    if 'library' in term:
        return ['["amenity"="library"]']
    if 'park' in term:
        return ['["leisure"="park"]']
    if 'gym' in term:
        return ['["leisure"="fitness_centre"]']
    if 'cinema' in term or 'movie' in term:
        return ['["amenity"="cinema"]']
    if any(value in term for value in ('gas', 'petrol', 'fuel')):
        return ['["amenity"~"^(fuel|charging_station)$"]']
    if 'parking' in term:
        return ['["amenity"="parking"]']
    if 'airport' in term:
        return ['["aeroway"="aerodrome"]']
    if 'beach' in term:
        return ['["natural"="beach"]']
    if 'picnic' in term or term == 'picnic_site':
        return ['["tourism"="picnic_site"]']
    if 'square' in term:
        return ['["place"="square"]']
    if 'college' in term:
        return ['["amenity"="college"]']

    clean_term = re.sub(
        r'[^a-z0-9_-]',
        '',
        re.sub(r'\s+', '_', re.sub(r's\b', '', term))
    )
    if not clean_term:
        raise ValueError('Please enter a valid place type.')

    return [
        f'["amenity"="{clean_term}"]',
        f'["shop"="{clean_term}"]',
        f'["tourism"="{clean_term}"]',
        f'["leisure"="{clean_term}"]'
    ]


def parse_bounding_box(value):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(point, list) and len(point) == 2 for point in value)
    ):
        raise ValueError('A valid map boundary is required.')

    try:
        longitude_1, latitude_1 = map(float, value[0])
        longitude_2, latitude_2 = map(float, value[1])
    except (TypeError, ValueError):
        raise ValueError('A valid map boundary is required.') from None

    coordinates = (longitude_1, latitude_1, longitude_2, latitude_2)
    if not all(math.isfinite(coordinate) for coordinate in coordinates):
        raise ValueError('A valid map boundary is required.')
    if not all(-180 <= longitude <= 180 for longitude in (longitude_1, longitude_2)):
        raise ValueError('The map boundary longitude is out of range.')
    if not all(-90 <= latitude <= 90 for latitude in (latitude_1, latitude_2)):
        raise ValueError('The map boundary latitude is out of range.')

    south, north = sorted((latitude_1, latitude_2))
    west, east = sorted((longitude_1, longitude_2))
    if south == north or west == east:
        raise ValueError('The map boundary must cover an area.')
    if (
        north - south > MAX_BOUNDING_BOX_SPAN_DEGREES
        or east - west > MAX_BOUNDING_BOX_SPAN_DEGREES
    ):
        raise ValueError('This area is too large. Please choose a more precise location.')

    return south, west, north, east


def build_overpass_query(payload):
    request_type = payload.get('type')

    if request_type == 'places':
        search_term = payload.get('searchTerm')
        if not isinstance(search_term, str) or not search_term.strip():
            raise ValueError('A place type is required.')
        if len(search_term) > MAX_SEARCH_TERM_LENGTH:
            raise ValueError('The place type is too long.')

        south, west, north, east = parse_bounding_box(payload.get('boundingBox'))
        selectors = []
        for osm_filter in get_osm_filters(search_term.strip()):
            for element_type in ('node', 'way'):
                selectors.append(
                    f'{element_type}{osm_filter}({south},{west},{north},{east});'
                )
        selectors_text = '\n'.join(selectors)

        return (
            f'[out:json][timeout:{OVERPASS_QUERY_TIMEOUT_SECONDS}];\n'
            '(\n'
            f'{selectors_text}\n'
            ');\n'
            f'out body center qt {OVERPASS_MAX_RESULTS};'
        )

    if request_type == 'geometry':
        osm_type = payload.get('osmType')
        osm_id = payload.get('osmId')
        if osm_type not in {'node', 'way', 'relation'}:
            raise ValueError('A valid OSM object type is required.')
        try:
            osm_id = int(osm_id)
        except (TypeError, ValueError):
            raise ValueError('A valid OSM object ID is required.') from None
        if osm_id <= 0:
            raise ValueError('A valid OSM object ID is required.')

        return (
            f'[out:json][timeout:{OVERPASS_QUERY_TIMEOUT_SECONDS}];\n'
            f'{osm_type}({osm_id});\n'
            'out geom;'
        )

    raise ValueError('A valid OSM request type is required.')


def read_upstream_json(response):
    content_length = response.headers.get('Content-Length')
    if content_length:
        try:
            if int(content_length) > OVERPASS_MAX_RESPONSE_BYTES:
                raise UpstreamResponseTooLarge
        except ValueError:
            logger.warning('Overpass returned an invalid Content-Length header')

    body = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        body.extend(chunk)
        if len(body) > OVERPASS_MAX_RESPONSE_BYTES:
            raise UpstreamResponseTooLarge

    return json.loads(body)


@app.route('/')
def index():
    if not MAPBOX_ACCESS_TOKEN:
        return 'Error: Required API key not configured!', 500

    return render_template('index.html', mapbox_token=MAPBOX_ACCESS_TOKEN)


@app.route('/debug')
def debug_info():
    return {
        'mapbox_token_present': bool(MAPBOX_ACCESS_TOKEN),
        'environment': 'development' if app.debug else 'production',
        'debug_mode': app.debug
    }


@app.route('/healthz')
def healthcheck():
    if not MAPBOX_ACCESS_TOKEN:
        return {
            'status': 'not ready',
            'reason': 'MAPBOX_ACCESS_TOKEN is not configured'
        }, 503

    return {'status': 'ok'}


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(error='The request body is too large.'), 413


@app.post('/api/overpass')
def overpass_proxy():
    """Run bounded OSM queries server-side so browsers are not blocked by CORS."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='A JSON request body is required.'), 400

    try:
        query = build_overpass_query(payload)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    if not OVERPASS_CONCURRENCY_GATE.acquire(blocking=False):
        flask_response = jsonify(
            error='OSM search capacity is busy. Please try again in a moment.'
        )
        flask_response.status_code = 503
        flask_response.headers['Retry-After'] = '2'
        return flask_response

    response = None
    try:
        response = requests.post(
            OVERPASS_API_URL,
            data={'data': query},
            headers={
                'Accept': 'application/json',
                'User-Agent': 'PreciseLocation/1.0 (https://precise-location.onrender.com/)'
            },
            timeout=OVERPASS_HTTP_TIMEOUT,
            stream=True
        )

        if response.status_code == 429:
            flask_response = jsonify(
                error='OSM is busy right now. Please wait a moment and try again.'
            )
            flask_response.status_code = 503
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                flask_response.headers['Retry-After'] = retry_after
            return flask_response

        if not response.ok:
            logger.warning('Overpass returned HTTP %s', response.status_code)
            status_code = 400 if response.status_code == 400 else 502
            message = (
                'OSM could not understand this search.'
                if status_code == 400
                else 'OSM search is temporarily unavailable. Please try again.'
            )
            return jsonify(error=message), status_code

        return jsonify(read_upstream_json(response))
    except requests.Timeout:
        logger.warning('Overpass request timed out')
        return jsonify(
            error='The OSM search took too long. Please try again in a moment.'
        ), 504
    except requests.RequestException as error:
        logger.warning('Could not reach Overpass: %s', error)
        return jsonify(
            error='OSM search is temporarily unavailable. Please try again.'
        ), 503
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning('Overpass returned a non-JSON response')
        return jsonify(
            error='OSM returned an invalid response. Please try again.'
        ), 502
    except (UpstreamResponseTooLarge, ValueError):
        logger.warning('Overpass returned an oversized response')
        return jsonify(
            error='OSM returned too many results. Please choose a smaller area.'
        ), 502
    finally:
        if response is not None:
            response.close()
        OVERPASS_CONCURRENCY_GATE.release()


if __name__ == '__main__':
    app.run(debug=True, port=5002)
