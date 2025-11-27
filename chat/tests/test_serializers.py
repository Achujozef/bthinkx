"""
Unit tests for chat serializers
"""
import pytest
from django.contrib.auth import get_user_model
from chat.models import ChatRoom, Message, ChatRoomMembership
from chat.serializers import serialize_message, sanitize_filename

User = get_user_model()


@pytest.mark.django_db
class TestSerializers:
    """Test unified message serializer"""
    
    def test_serialize_basic_message(self):
        """Test serialization of basic text message"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        room = ChatRoom.objects.create(name='Test Room', room_type='group')
        ChatRoomMembership.objects.create(room=room, user=user)
        
        message = Message.objects.create(
            room=room,
            sender=user,
            content='Test message',
            message_type='text'
        )
        
        data = serialize_message(message)
        
        assert data['id'] == str(message.id)
        assert data['content'] == 'Test message'
        assert data['message_type'] == 'text'
        assert data['sender']['id'] == str(user.id)
        assert data['sender']['name'] == 'Test User'
        assert data['attachments'] == []
        assert data['to_users'] == []
        assert data['cc_users'] == []
        assert data['reply_to'] is None
    
    def test_serialize_formal_message(self):
        """Test serialization of formal message with recipients"""
        sender = User.objects.create_user(
            username='sender',
            email='sender@example.com',
            first_name='Sender',
            last_name='User'
        )
        recipient = User.objects.create_user(
            username='recipient',
            email='recipient@example.com',
            first_name='Recipient',
            last_name='User'
        )
        room = ChatRoom.objects.create(name='Test Room', room_type='personal')
        ChatRoomMembership.objects.create(room=room, user=sender)
        ChatRoomMembership.objects.create(room=room, user=recipient)
        
        message = Message.objects.create(
            room=room,
            sender=sender,
            content='Formal message',
            message_type='formal',
            subject='Test Subject'
        )
        message.to_users.add(recipient)
        
        data = serialize_message(message)
        
        assert data['message_type'] == 'formal'
        assert data['subject'] == 'Test Subject'
        assert len(data['to_users']) == 1
        assert data['to_users'][0]['id'] == str(recipient.id)
        assert data['to_users'][0]['name'] == 'Recipient User'
    
    def test_serialize_message_with_reply(self):
        """Test serialization of message with reply_to"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        room = ChatRoom.objects.create(name='Test Room', room_type='group')
        ChatRoomMembership.objects.create(room=room, user=user)
        
        original = Message.objects.create(
            room=room,
            sender=user,
            content='Original message',
            message_type='text'
        )
        
        reply = Message.objects.create(
            room=room,
            sender=user,
            content='Reply message',
            message_type='text',
            reply_to=original
        )
        
        data = serialize_message(reply)
        
        assert data['reply_to'] is not None
        assert data['reply_to']['id'] == str(original.id)
        assert data['reply_to']['content'] == 'Original message'
        assert data['reply_to']['sender']['id'] == str(user.id)
    
    def test_serialize_message_without_sender(self):
        """Test serialization of system message without sender"""
        room = ChatRoom.objects.create(name='Test Room', room_type='group')
        
        message = Message.objects.create(
            room=room,
            sender=None,
            content='System message',
            message_type='system'
        )
        
        data = serialize_message(message)
        
        assert data['sender']['id'] is None
        assert data['sender']['name'] == 'System'
    
    def test_sanitize_filename(self):
        """Test filename sanitization"""
        assert sanitize_filename('test.txt') == 'test.txt'
        assert sanitize_filename('../../etc/passwd') == 'etcpasswd'
        assert sanitize_filename('file with spaces.txt') == 'file with spaces.txt'
        assert len(sanitize_filename('a' * 300 + '.txt')) <= 255

