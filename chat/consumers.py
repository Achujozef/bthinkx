"""
chat/consumers.py
WebSocket consumer for real-time chat with typing indicators, read receipts, etc.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from .models import ChatRoom, Message, MessageMeta, TypingIndicator, ChatRoomMembership, Attachment
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for chat functionality
    Handles: messages, typing indicators, read receipts, room joining/leaving
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        
        # Authenticate user
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Verify user has access to this room
        has_access = await self.verify_room_access()
        if not has_access:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Notify others user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': str(self.user.id),
                'user_name': self.user.get_full_name(),
            }
        )
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'room_group_name'):
            # Remove typing indicator if exists
            await self.remove_typing_indicator()
            
            # Notify others user left
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user_id': str(self.user.id),
                    'user_name': self.user.get_full_name(),
                }
            )
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing_start':
                await self.handle_typing_start()
            elif message_type == 'typing_stop':
                await self.handle_typing_stop()
            elif message_type == 'message_read':
                await self.handle_message_read(data)
            elif message_type == 'message_delivered':
                await self.handle_message_delivered(data)
            elif message_type == 'load_history':
                await self.handle_load_history(data)
            else:
                await self.send(text_data=json.dumps({
                    'error': f'Unknown message type: {message_type}'
                }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e)
            }))
    
    async def handle_chat_message(self, data):
        """Handle new chat message"""
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        reply_to_id = data.get('reply_to')
        
        # Formal email specific
        subject = data.get('subject', '')
        to_user_ids = data.get('to_users', [])
        cc_user_ids = data.get('cc_users', [])
        
        if not content:
            return
        
        # Save message to database
        message = await self.save_message(
            content=content,
            message_type=message_type,
            subject=subject,
            to_user_ids=to_user_ids,
            cc_user_ids=cc_user_ids,
            reply_to_id=reply_to_id
        )
        
        # Get message data for broadcasting
        message_data = await self.get_message_data(message)
        
        # Broadcast to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )
    
    async def handle_typing_start(self):
        """Handle typing indicator start"""
        await self.save_typing_indicator()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': str(self.user.id),
                'user_name': self.user.get_full_name(),
                'is_typing': True
            }
        )
    
    async def handle_typing_stop(self):
        """Handle typing indicator stop"""
        await self.remove_typing_indicator()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': str(self.user.id),
                'user_name': self.user.get_full_name(),
                'is_typing': False
            }
        )
    
    async def handle_message_read(self, data):
        """Handle message read receipt"""
        message_id = data.get('message_id')
        if message_id:
            await self.mark_message_read(message_id)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_read_receipt',
                    'message_id': message_id,
                    'user_id': str(self.user.id),
                    'user_name': self.user.get_full_name()
                }
            )
    
    async def handle_message_delivered(self, data):
        """Handle message delivered receipt"""
        message_id = data.get('message_id')
        if message_id:
            await self.mark_message_delivered(message_id)
    
    async def handle_load_history(self, data):
        """Handle loading message history"""
        before_id = data.get('before_id')
        limit = data.get('limit', 50)
        
        messages = await self.load_message_history(before_id, limit)
        
        await self.send(text_data=json.dumps({
            'type': 'message_history',
            'messages': messages
        }, cls=DjangoJSONEncoder))
    
    # Broadcast handlers (called by channel layer)
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message']
        }, cls=DjangoJSONEncoder))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        # Don't send own typing indicator back
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))
    
    async def user_joined(self, event):
        """Send user joined notification"""
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'user_joined',
                'user_id': event['user_id'],
                'user_name': event['user_name']
            }))
    
    async def user_left(self, event):
        """Send user left notification"""
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'user_left',
                'user_id': event['user_id'],
                'user_name': event['user_name']
            }))
    
    async def message_read_receipt(self, event):
        """Send read receipt to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_read_receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'user_name': event['user_name']
        }))
    
    # Database operations
    @database_sync_to_async
    def verify_room_access(self):
        """Verify user has access to the room"""
        try:
            room = ChatRoom.objects.get(id=self.room_id, is_active=True)
            return ChatRoomMembership.objects.filter(
                room=room,
                user=self.user
            ).exists()
        except ChatRoom.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_message(self, content, message_type, subject, to_user_ids, cc_user_ids, reply_to_id):
        """Save message to database"""
        room = ChatRoom.objects.get(id=self.room_id)
        
        message = Message.objects.create(
            room=room,
            sender=self.user,
            content=content,
            message_type=message_type,
            subject=subject if message_type == 'formal' else '',
            reply_to_id=reply_to_id if reply_to_id else None
        )
        
        # Add to/cc users for formal messages
        if message_type == 'formal' and to_user_ids:
            to_users = User.objects.filter(id__in=to_user_ids)
            message.to_users.set(to_users)
        
        if message_type == 'formal' and cc_user_ids:
            cc_users = User.objects.filter(id__in=cc_user_ids)
            message.cc_users.set(cc_users)
        
        # Update room timestamp
        room.updated_at = timezone.now()
        room.save(update_fields=['updated_at'])
        
        return message
    
    @database_sync_to_async
    def get_message_data(self, message):
        """Get serialized message data"""
        data = {
            'id': str(message.id),
            'room_id': str(message.room.id),
            'sender': {
                'id': str(message.sender.id),
                'name': message.sender.get_full_name(),
                'avatar': message.sender.avatar.url if message.sender.avatar else None
            },
            'content': message.content,
            'message_type': message.message_type,
            'subject': message.subject,
            'is_edited': message.is_edited,
            'created_at': message.created_at.isoformat(),
            'reply_to': str(message.reply_to.id) if message.reply_to else None,
        }
        
        # Add formal message fields
        if message.message_type == 'formal':
            data['to_users'] = [
                {'id': str(u.id), 'name': u.get_full_name()}
                for u in message.to_users.all()
            ]
            data['cc_users'] = [
                {'id': str(u.id), 'name': u.get_full_name()}
                for u in message.cc_users.all()
            ]
        
        # Add attachments
        data['attachments'] = [
            {
                'id': str(a.id),
                'file_name': a.file_name,
                'file_url': a.file.url,
                'file_type': a.file_type,
                'file_size': a.file_size
            }
            for a in message.attachments.all()
        ]
        
        return data
    
    @database_sync_to_async
    def save_typing_indicator(self):
        """Save typing indicator"""
        room = ChatRoom.objects.get(id=self.room_id)
        TypingIndicator.objects.update_or_create(
            room=room,
            user=self.user,
            defaults={'started_at': timezone.now()}
        )
    
    @database_sync_to_async
    def remove_typing_indicator(self):
        """Remove typing indicator"""
        TypingIndicator.objects.filter(
            room_id=self.room_id,
            user=self.user
        ).delete()
    
    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark message as read"""
        try:
            message = Message.objects.get(id=message_id)
            message.mark_as_read_by(self.user)
            
            # Update membership last_read_at
            ChatRoomMembership.objects.filter(
                room=message.room,
                user=self.user
            ).update(last_read_at=timezone.now())
        except Message.DoesNotExist:
            pass
    
    @database_sync_to_async
    def mark_message_delivered(self, message_id):
        """Mark message as delivered"""
        try:
            message = Message.objects.get(id=message_id)
            message.mark_as_delivered_to(self.user)
        except Message.DoesNotExist:
            pass
    
    @database_sync_to_async
    def load_message_history(self, before_id, limit):
        """Load message history"""
        queryset = Message.objects.filter(
            room_id=self.room_id,
            is_deleted=False
        ).select_related('sender').prefetch_related(
            'attachments',
            'to_users',
            'cc_users'
        ).order_by('-created_at')
        
        if before_id:
            try:
                before_msg = Message.objects.get(id=before_id)
                queryset = queryset.filter(created_at__lt=before_msg.created_at)
            except Message.DoesNotExist:
                pass
        
        messages = list(queryset[:limit])
        messages.reverse()  # Return in chronological order
        
        return [
            {
                'id': str(msg.id),
                'sender': {
                    'id': str(msg.sender.id),
                    'name': msg.sender.get_full_name(),
                    'avatar': msg.sender.avatar.url if msg.sender.avatar else None
                },
                'content': msg.content,
                'message_type': msg.message_type,
                'subject': msg.subject,
                'is_edited': msg.is_edited,
                'created_at': msg.created_at.isoformat(),
                'to_users': [
                    {'id': str(u.id), 'name': u.get_full_name()}
                    for u in msg.to_users.all()
                ] if msg.message_type == 'formal' else [],
                'cc_users': [
                    {'id': str(u.id), 'name': u.get_full_name()}
                    for u in msg.cc_users.all()
                ] if msg.message_type == 'formal' else [],
                'attachments': [
                    {
                        'id': str(a.id),
                        'file_name': a.file_name,
                        'file_url': a.file.url,
                        'file_type': a.file_type
                    }
                    for a in msg.attachments.all()
                ]
            }
            for msg in messages
        ]