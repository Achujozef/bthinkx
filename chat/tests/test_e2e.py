"""
End-to-end browser tests using Playwright
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestChatE2E:
    """E2E tests for chat functionality"""
    
    def test_chat_room_loads(self, page: Page, live_server):
        """Test that chat room page loads correctly"""
        page.goto(f"{live_server.url}/chat/")
        expect(page).to_have_title(containing="Chat")
    
    def test_send_message(self, page: Page, live_server, authenticated_user):
        """Test sending a message"""
        page.goto(f"{live_server.url}/chat/")
        
        # Wait for input
        input_field = page.locator('#messageInput')
        input_field.fill('Test message')
        
        # Click send
        send_button = page.locator('#sendBtn')
        send_button.click()
        
        # Verify message appears
        expect(page.locator('.message-bubble')).to_contain_text('Test message')
    
    def test_mobile_layout(self, page: Page, live_server):
        """Test mobile responsive layout"""
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        
        page.goto(f"{live_server.url}/chat/")
        
        # Verify send button is visible
        send_button = page.locator('#sendBtn')
        expect(send_button).to_be_visible()
        
        # Verify input area is accessible
        input_area = page.locator('.chat-input-area')
        expect(input_area).to_be_visible()

