"""
Integration tests for chat views
"""
import pytest
import json
from django.contrib.auth import get_user_model
from django.urls import reverse
from chat.models import ChatRoom, Message, ChatRoomMembership, BlockedUser

User = get_user_model()


@pytest.mark.django_db
class TestChatViews:
    """Test chat HTTP views"""
    
    @pytest.fixture
    def user1(self):
        return User.objects.create_user(
            username='user1',
            email='user1@example.com',
            first_name='User',
            last_name='One'
        )
    
    @pytest.fixture
    def user2(self):
        return User.objects.create_user(
            username='user2',
            email='user2@example.com',
            first_name='User',
            last_name='Two'
        )
    
    @pytest.fixture
    def room(self, user1, user2):
        room = ChatRoom.objects.create(name='Test Room', room_type='personal')
        ChatRoomMembership.objects.create(room=room, user=user1)
        ChatRoomMembership.objects.create(room=room, user=user2)
        return room
    
    def test_send_message(self, client, user1, room):
        """Test sending a message via HTTP"""
        client.force_login(user1)
        
        response = client.post(
            reverse('send_message', args=[room.id]),
            data=json.dumps({
                'content': 'Test message',
                'message_type': 'text'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['message']['content'] == 'Test message'
        assert Message.objects.filter(room=room, content='Test message').exists()
    
    def test_send_formal_message(self, client, user1, room, user2):
        """Test sending formal message with recipients"""
        client.force_login(user1)
        
        response = client.post(
            reverse('send_message', args=[room.id]),
            data=json.dumps({
                'content': 'Formal message',
                'message_type': 'formal',
                'subject': 'Test Subject',
                'to_users': [str(user2.id)],
                'cc_users': []
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['message']['subject'] == 'Test Subject'
        assert len(data['message']['to_users']) == 1
        assert data['message']['to_users'][0]['id'] == str(user2.id)
    
    def test_edit_message(self, client, user1, room):
        """Test editing a message"""
        message = Message.objects.create(
            room=room,
            sender=user1,
            content='Original',
            message_type='text'
        )
        
        client.force_login(user1)
        
        response = client.post(
            reverse('edit_message', args=[message.id]),
            data=json.dumps({'content': 'Edited'}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        message.refresh_from_db()
        assert message.content == 'Edited'
        assert message.is_edited is True
    
    def test_delete_message(self, client, user1, room):
        """Test deleting a message"""
        message = Message.objects.create(
            room=room,
            sender=user1,
            content='To delete',
            message_type='text'
        )
        
        client.force_login(user1)
        
        response = client.post(reverse('delete_message', args=[message.id]))
        
        assert response.status_code == 200
        message.refresh_from_db()
        assert message.is_deleted is True
    
    def test_block_user(self, client, user1, user2):
        """Test blocking a user"""
        client.force_login(user1)
        
        response = client.post(reverse('block_user', args=[user2.id]))
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['is_blocked'] is True
        assert BlockedUser.objects.filter(blocker=user1, blocked=user2).exists()

