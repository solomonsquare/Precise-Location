import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_search_input_exists(client, mock_mapbox_token):
    """Test that the search input field exists and is properly configured"""
    response = client.get('/')
    assert b'search-input' in response.data
    assert b'placeholder="Search for places' in response.data

def test_map_initialization(client, mock_mapbox_token):
    """Test that the map is properly initialized with Mapbox token"""
    response = client.get('/')
    assert b'mapboxgl.accessToken' in response.data
    assert b'initMap' in response.data
    assert b'streets-v12' in response.data

def test_quick_search_categories(client, mock_mapbox_token):
    """Test that quick search categories are properly rendered"""
    response = client.get('/')
    assert b'searchCategory' in response.data
    # Test for presence of common categories
    categories = [b'mall', b'supermarket', b'pub', b'night_club']
    for category in categories:
        assert category in response.data

def test_error_message_container(client, mock_mapbox_token):
    """Test that error message container exists"""
    response = client.get('/')
    assert b'error-message' in response.data

def test_suggestions_container(client, mock_mapbox_token):
    """Test that suggestions container exists"""
    response = client.get('/')
    assert b'suggestions' in response.data
    assert b'suggestions-container' in response.data

def test_mobile_responsive_elements(client, mock_mapbox_token):
    """Test that mobile responsive elements are present"""
    response = client.get('/')
    assert b'mobile-toggle' in response.data
    assert b'sidebar' in response.data
    assert b'map' in response.data 