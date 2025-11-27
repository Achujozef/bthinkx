"""
Pytest configuration for chat tests
"""
import pytest
from django.contrib.auth import get_user_model
from channels.testing import ChannelsLiveServerTestCase

User = get_user_model()


@pytest.fixture
def authenticated_user(client):
    """Create and authenticate a test user"""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    client.force_login(user)
    return user


@pytest.fixture
def live_server():
    """Provide live server for E2E tests"""
    # This would be configured based on your test setup
    return ChannelsLiveServerTestCase

