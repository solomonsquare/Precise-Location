from app import get_osm_filters

def test_nominatim_search(client, requests_mock, mock_mapbox_token):
    """Test the Nominatim search functionality"""
    mock_response = [{
        'place_id': 12345,
        'lat': '54.9783',
        'lon': '-1.6178',
        'display_name': 'Newcastle upon Tyne, England',
        'geojson': {
            'type': 'Polygon',
            'coordinates': [[[-1.6178, 54.9783], [-1.6179, 54.9784], [-1.6177, 54.9784], [-1.6178, 54.9783]]]
        }
    }]
    
    requests_mock.get(
        'https://nominatim.openstreetmap.org/search',
        json=mock_response
    )
    
    response = client.get('/')
    assert b'getLocation' in response.data

def test_overpass_search_uses_same_origin_proxy(client, mock_mapbox_token):
    """The browser must not call Overpass directly because that fails CORS."""
    response = client.get('/')
    page = response.get_data(as_text=True)

    assert "fetch('/api/overpass'" in page
    assert 'overpass-api.de/api/interpreter' not in page

def test_amenity_filter_generation():
    """Category filters are generated and sanitized on the server."""
    assert get_osm_filters('restaurant') == ['["amenity"="restaurant"]']
    assert get_osm_filters('pub') == ['["amenity"~"^(bar|pub)$"]']
    assert get_osm_filters('college') == ['["amenity"="college"]']
    assert get_osm_filters('square') == ['["place"="square"]']

def test_map_marker_functionality(client, mock_mapbox_token):
    """Test the map marker related functions"""
    response = client.get('/')
    assert b'addMarker' in response.data
    assert b'clearMarkers' in response.data
    assert b'updateMap' in response.data

def test_search_result_handling(client, mock_mapbox_token):
    """Test the search result handling functions"""
    response = client.get('/')
    assert b'handleSearchResults' in response.data
    assert b'displaySearchResults' in response.data

def test_error_handling(client, mock_mapbox_token):
    """Test error handling in search functionality"""
    response = client.get('/')
    assert b'catch' in response.data
    assert b'error-message' in response.data
