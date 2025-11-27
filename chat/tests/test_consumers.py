"""
Async tests for WebSocket consumers
"""
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from chat.models import ChatRoom, Message, ChatRoomMembership
from chat.consumers import ChatConsumer
from chat.routing import websocket_urlpatterns

User = get_user_model()


@pytest.mark.asyncio
@pytest.mark.django_db
class TestChatConsumer:
    """Test WebSocket consumer"""
    
    @pytest.fixture
    async def user1(self):
        return await database_sync_to_async(User.objects.create_user)(
            username='user1',
            email='user1@example.com',
            first_name='User',
            last_name='One'
        )
    
    @pytest.fixture
    async def user2(self):
        return await database_sync_to_async(User.objects.create_user)(
            username='user2',
            email='user2@example.com',
            first_name='User',
            last_name='Two'
        )
    
    @pytest.fixture
    async def room(self, user1, user2):
        room = await database_sync_to_async(ChatRoom.objects.create)(
            name='Test Room',
            room_type='personal'
        )
        await database_sync_to_async(ChatRoomMembership.objects.create)(
            room=room, user=user1
        )
        await database_sync_to_async(ChatRoomMembership.objects.create)(
            room=room, user=user2
        )
        return room
    
    async def test_connect(self, user1, room):
        """Test WebSocket connection"""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f'/ws/chat/{room.id}/'
        )
        communicator.scope['user'] = user1
        
        connected, subprotocol = await communicator.connect()
        assert connected
        
        await communicator.disconnect()
    
    async def test_send_message(self, user1, room):
        """Test sending message via WebSocket"""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f'/ws/chat/{room.id}/'
        )
        communicator.scope['user'] = user1
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Send message
        await communicator.send_json_to({
            'type': 'chat_message',
            'content': 'Test message',
            'message_type': 'text'
        })
        
        # Receive response
        response = await communicator.receive_json_from()
        assert response['type'] == 'chat.message'
        assert response['message']['content'] == 'Test message'
        
        await communicator.disconnect()
    
    async def test_typing_indicator(self, user1, room):
        """Test typing indicator"""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f'/ws/chat/{room.id}/'
        )
        communicator.scope['user'] = user1
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Start typing
        await communicator.send_json_to({
            'type': 'typing_start'
        })
        
        # Stop typing
        await communicator.send_json_to({
            'type': 'typing_stop'
        })
        
        await communicator.disconnect()

