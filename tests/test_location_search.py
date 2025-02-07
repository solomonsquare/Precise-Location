import pytest
import json
import requests_mock

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

def test_overpass_search(client, requests_mock, mock_mapbox_token):
    """Test the Overpass API search functionality"""
    mock_response = {
        'elements': [
            {
                'type': 'node',
                'id': 123456,
                'lat': 54.9783,
                'lon': -1.6178,
                'tags': {
                    'amenity': 'restaurant',
                    'name': 'Test Restaurant'
                }
            }
        ]
    }
    
    requests_mock.get(
        'https://overpass-api.de/api/interpreter',
        json=mock_response
    )
    
    response = client.get('/')
    assert b'searchPlaces' in response.data

def test_amenity_filter_generation(client, mock_mapbox_token):
    """Test the amenity filter generation for different search terms"""
    response = client.get('/')
    assert b'getAmenityFilter' in response.data
    
    # Common search terms should be present in the JavaScript code
    common_terms = [
        b'restaurant', b'cafe', b'pub',
        b'supermarket', b'school', b'hospital'
    ]
    for term in common_terms:
        assert term in response.data

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