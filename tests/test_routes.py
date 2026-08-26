def test_index_route_with_token(client, mock_mapbox_token):
    """Test the index route when Mapbox token is configured"""
    response = client.get('/')
    assert response.status_code == 200
    # Check if the token is in the response
    assert str(mock_mapbox_token) in response.get_data(as_text=True)

def test_index_route_without_token(client):
    """Test the index route when Mapbox token is not configured"""
    response = client.get('/')
    assert response.status_code == 500
    assert b'Error: Required API key not configured!' in response.data

def test_debug_info_route_with_token(client, mock_mapbox_token):
    """Test the debug info route with token configured"""
    response = client.get('/debug')
    assert response.status_code == 200
    data = response.get_json()
    assert data['mapbox_token_present'] is True
    assert data['environment'] == 'development'
    assert data['debug_mode'] is True

def test_debug_info_route_without_token(client):
    """Test the debug info route without token configured"""
    response = client.get('/debug')
    assert response.status_code == 200
    data = response.get_json()
    assert data['mapbox_token_present'] is False

def test_favicon_route(client):
    """Test the favicon route"""
    response = client.get('/favicon.ico')
    assert response.status_code == 200
    assert response.mimetype == 'image/vnd.microsoft.icon'


def test_healthcheck_reports_missing_required_configuration(client):
    response = client.get('/healthz')

    assert response.status_code == 503
    assert response.get_json()['status'] == 'not ready'


def test_healthcheck_is_ready_with_mapbox_token(client, mock_mapbox_token):
    response = client.get('/healthz')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}
