import json

import pytest
import requests

import app as app_module


class FakeOverpassResponse:
    def __init__(self, status_code=200, payload=None, body=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False
        if body is None:
            body = json.dumps(payload if payload is not None else {}).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.body = body

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start:start + chunk_size]

    def close(self):
        self.closed = True


def post_place_search(client, **overrides):
    payload = {
        'type': 'places',
        'searchTerm': 'shopping mall',
        'boundingBox': [[-1.63, 54.97], [-1.60, 54.99]]
    }
    payload.update(overrides)
    return client.post('/api/overpass', json=payload)


def test_json_body_is_required(client):
    response = client.post('/api/overpass')

    assert response.status_code == 400
    assert response.get_json()['error'] == 'A JSON request body is required.'


def test_arbitrary_overpass_queries_are_rejected(client):
    response = client.post(
        '/api/overpass',
        json={'query': '[out:json];node(1);out;'}
    )

    assert response.status_code == 400
    assert 'request type' in response.get_json()['error']


def test_concurrency_limit_rejects_excess_requests(client, mocker):
    gate = mocker.patch('app.OVERPASS_CONCURRENCY_GATE')
    gate.acquire.return_value = False
    post = mocker.patch('app.requests.post')

    response = post_place_search(client)

    assert response.status_code == 503
    assert response.headers['Retry-After'] == '2'
    assert 'capacity is busy' in response.get_json()['error']
    post.assert_not_called()
    gate.release.assert_not_called()


def test_place_search_builds_a_bounded_query(client, mocker):
    upstream = FakeOverpassResponse(
        payload={'elements': [{'type': 'node', 'id': 1}]}
    )
    post = mocker.patch('app.requests.post', return_value=upstream)

    response = post_place_search(client)

    assert response.status_code == 200
    assert response.get_json()['elements'][0]['id'] == 1
    query = post.call_args.kwargs['data']['data']
    assert '[timeout:12]' in query
    assert 'node["shop"~"^(mall|department_store)$"]' in query
    assert 'way["shop"~"^(mall|department_store)$"]' in query
    assert '(54.97,-1.63,54.99,-1.6)' in query
    assert 'out body center qt 2000;' in query
    assert post.call_args.kwargs['timeout'] == (3.05, 18)
    assert post.call_args.kwargs['stream'] is True
    assert upstream.closed is True


def test_concurrency_slot_is_released_after_upstream_failure(client, mocker):
    gate = mocker.patch('app.OVERPASS_CONCURRENCY_GATE')
    gate.acquire.return_value = True
    mocker.patch('app.requests.post', side_effect=requests.Timeout)

    response = post_place_search(client)

    assert response.status_code == 504
    gate.release.assert_called_once_with()


@pytest.mark.parametrize(
    ('search_term', 'expected_filter'),
    [
        ('garden', '["garden:type"="botanical"]'),
        ('skateboard_pitch', '["leisure"="pitch"]["sport"="skateboard"]'),
        ('picnic_site', '["tourism"="picnic_site"]'),
        ('square', '["place"="square"]'),
        ('college', '["amenity"="college"]')
    ]
)
def test_live_branch_categories_are_preserved(search_term, expected_filter):
    query = app_module.build_overpass_query({
        'type': 'places',
        'searchTerm': search_term,
        'boundingBox': [[-1.63, 54.97], [-1.60, 54.99]]
    })

    assert expected_filter in query


@pytest.mark.parametrize(
    'bounding_box',
    [
        None,
        [['bad', 54.97], [-1.60, 54.99]],
        [[-181, 54.97], [-1.60, 54.99]],
        [[-1.63, 91], [-1.60, 54.99]],
        [[-1.63, 54.97], [-1.63, 54.99]]
    ]
)
def test_invalid_boundaries_are_rejected(client, bounding_box):
    response = post_place_search(client, boundingBox=bounding_box)

    assert response.status_code == 400


def test_large_boundary_is_rejected_before_upstream_call(client, mocker):
    post = mocker.patch('app.requests.post')

    response = post_place_search(
        client,
        boundingBox=[[-10, 45], [10, 60]]
    )

    assert response.status_code == 400
    assert 'too large' in response.get_json()['error']
    post.assert_not_called()


def test_long_search_term_is_rejected(client):
    response = post_place_search(client, searchTerm='x' * 81)

    assert response.status_code == 400
    assert 'too long' in response.get_json()['error']


def test_geometry_lookup_accepts_only_an_osm_type_and_id(client, mocker):
    upstream = FakeOverpassResponse(payload={'elements': []})
    post = mocker.patch('app.requests.post', return_value=upstream)

    response = client.post('/api/overpass', json={
        'type': 'geometry',
        'osmType': 'way',
        'osmId': '123'
    })

    assert response.status_code == 200
    query = post.call_args.kwargs['data']['data']
    assert 'way(123);' in query
    assert 'relation(123);' not in query


def test_timeout_returns_a_friendly_gateway_error(client, mocker):
    mocker.patch('app.requests.post', side_effect=requests.Timeout)

    response = client.post('/api/overpass', json={
        'type': 'geometry',
        'osmType': 'node',
        'osmId': 1
    })

    assert response.status_code == 504
    assert 'took too long' in response.get_json()['error']


def test_connection_failure_is_temporary(client, mocker):
    mocker.patch('app.requests.post', side_effect=requests.ConnectionError)

    response = client.post('/api/overpass', json={
        'type': 'geometry',
        'osmType': 'node',
        'osmId': 1
    })

    assert response.status_code == 503
    assert 'temporarily unavailable' in response.get_json()['error']


def test_rate_limit_preserves_retry_after(client, mocker):
    upstream = FakeOverpassResponse(
        status_code=429,
        headers={'Retry-After': '10'}
    )
    mocker.patch('app.requests.post', return_value=upstream)

    response = client.post('/api/overpass', json={
        'type': 'geometry',
        'osmType': 'node',
        'osmId': 1
    })

    assert response.status_code == 503
    assert response.headers['Retry-After'] == '10'
    assert 'busy' in response.get_json()['error']
    assert upstream.closed is True


@pytest.mark.parametrize(
    ('upstream_status', 'expected_status'),
    [(400, 400), (500, 502)]
)
def test_upstream_errors_are_normalized(
    client,
    mocker,
    upstream_status,
    expected_status
):
    upstream = FakeOverpassResponse(status_code=upstream_status)
    mocker.patch('app.requests.post', return_value=upstream)

    response = client.post('/api/overpass', json={
        'type': 'geometry',
        'osmType': 'node',
        'osmId': 1
    })

    assert response.status_code == expected_status
    assert upstream.closed is True


def test_invalid_json_from_upstream_is_rejected(client, mocker):
    upstream = FakeOverpassResponse(body='not json')
    mocker.patch('app.requests.post', return_value=upstream)

    response = client.post('/api/overpass', json={
        'type': 'geometry',
        'osmType': 'node',
        'osmId': 1
    })

    assert response.status_code == 502
    assert 'invalid response' in response.get_json()['error']


def test_oversized_upstream_response_is_rejected(client, mocker):
    upstream = FakeOverpassResponse(
        headers={'Content-Length': str(app_module.OVERPASS_MAX_RESPONSE_BYTES + 1)}
    )
    mocker.patch('app.requests.post', return_value=upstream)

    response = client.post('/api/overpass', json={
        'type': 'geometry',
        'osmType': 'node',
        'osmId': 1
    })

    assert response.status_code == 502
    assert 'too many results' in response.get_json()['error']


def test_request_body_limit_returns_json(client):
    response = client.post(
        '/api/overpass',
        data=b'{' + (b' ' * (17 * 1024)) + b'}',
        content_type='application/json'
    )

    assert response.status_code == 413
    assert response.get_json()['error'] == 'The request body is too large.'
