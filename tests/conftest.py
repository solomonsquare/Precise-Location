import pytest
import os
from app import app as flask_app

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "DEBUG": True
    })
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def mock_mapbox_token(monkeypatch):
    """Set a mock Mapbox token for testing"""
    test_token = "test_mapbox_token"
    monkeypatch.setenv('MAPBOX_ACCESS_TOKEN', test_token)
    # Also update the app's token
    import app
    app.MAPBOX_ACCESS_TOKEN = test_token
    return test_token

@pytest.fixture(autouse=True)
def clear_mapbox_token(monkeypatch):
    """Clear the Mapbox token before each test unless explicitly set"""
    monkeypatch.delenv('MAPBOX_ACCESS_TOKEN', raising=False)
    import app
    app.MAPBOX_ACCESS_TOKEN = None
