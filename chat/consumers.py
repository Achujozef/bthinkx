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
                'type': 'user.joined',
                'user_id': str(self.user.id),
                'user_name': self.user.get_full_name(),
            }
        )
        
        # Deliver pending messages on reconnect
        await self.deliver_pending_messages()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'room_group_name'):
            # Remove typing indicator if exists
            await self.remove_typing_indicator()
            
            # Notify others user left
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user.left',
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
        
        # Update room timestamp
        await self.update_room_timestamp()
        
        # Mark as delivered to all room members except sender
        await self.mark_delivered_to_all(message)
        
        # Broadcast to room group with normalized event name
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat.message',
                'message': message_data
            }
        )
    
    async def handle_typing_start(self):
        """Handle typing indicator start"""
        await self.save_typing_indicator()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing.indicator',
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
                'type': 'typing.indicator',
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
                    'type': 'message.read.receipt',
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
    
    # Broadcast handlers (called by channel layer) - normalized event names
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat.message',
            'message': event['message']
        }, cls=DjangoJSONEncoder))

    async def message_edited(self, event):
        """Send edited message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message.edited',
            'message': event['message']
        }, cls=DjangoJSONEncoder))

    async def message_deleted(self, event):
        """Send deleted message notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message.deleted',
            'message_id': event['message_id']
        }))

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        # Don't send own typing indicator back
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing.indicator',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))

    async def user_joined(self, event):
        """Send user joined notification"""
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'user.joined',
                'user_id': event['user_id'],
                'user_name': event['user_name']
            }))

    async def user_left(self, event):
        """Send user left notification"""
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'user.left',
                'user_id': event['user_id'],
                'user_name': event['user_name']
            }))

    async def message_read_receipt(self, event):
        """Send read receipt to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message.read.receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'user_name': event['user_name']
        }))
    
    async def chat_pinned(self, event):
        """Send chat pinned notification"""
        await self.send(text_data=json.dumps({
            'type': 'chat.pinned',
            'room_id': event.get('room_id'),
            'is_pinned': event.get('is_pinned')
        }))
    
    async def chat_muted(self, event):
        """Send chat muted notification"""
        await self.send(text_data=json.dumps({
            'type': 'chat.muted',
            'room_id': event.get('room_id'),
            'is_muted': event.get('is_muted')
        }))
    
    async def user_blocked(self, event):
        """Send user blocked notification"""
        await self.send(text_data=json.dumps({
            'type': 'user.blocked',
            'user_id': event.get('user_id'),
            'is_blocked': event.get('is_blocked')
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
        """Save message to database with transaction"""
        from django.db import transaction
        
        with transaction.atomic():
            room = ChatRoom.objects.get(id=self.room_id)
            
            # Get reply_to message
            reply_to = None
            if reply_to_id:
                try:
                    reply_to = Message.objects.get(id=reply_to_id, room=room, is_deleted=False)
                except Message.DoesNotExist:
                    pass
            
            message = Message.objects.create(
                room=room,
                sender=self.user,
                content=content,
                message_type=message_type,
                subject=subject if message_type == 'formal' else '',
                reply_to=reply_to
            )
            
            # Add to/cc users for formal messages
            if message_type == 'formal':
                if to_user_ids:
                    to_users = User.objects.filter(id__in=to_user_ids)
                    message.to_users.set(to_users)
                if cc_user_ids:
                    cc_users = User.objects.filter(id__in=cc_user_ids)
                    message.cc_users.set(cc_users)
            
            # Update room timestamp
            room.updated_at = timezone.now()
            room.save(update_fields=['updated_at'])
            
            # Mark as delivered to all room members except sender
            for membership in room.memberships.exclude(user=self.user):
                message.mark_as_delivered_to(membership.user)
        
        return message
    
    @database_sync_to_async
    def update_room_timestamp(self):
        """Update room updated_at timestamp"""
        ChatRoom.objects.filter(id=self.room_id).update(updated_at=timezone.now())
    
    @database_sync_to_async
    def mark_delivered_to_all(self, message):
        """Mark message as delivered to all room members except sender"""
        for membership in message.room.memberships.exclude(user=message.sender):
            message.mark_as_delivered_to(membership.user)
    
    @database_sync_to_async
    def deliver_pending_messages(self):
        """Deliver messages that were sent while user was offline"""
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            membership = ChatRoomMembership.objects.get(room=room, user=self.user)
            
            # Get messages after last_read_at that haven't been delivered
            pending_messages = Message.objects.filter(
                room=room,
                created_at__gt=membership.last_read_at,
                is_deleted=False
            ).exclude(sender=self.user).select_related('sender', 'reply_to').prefetch_related(
                'attachments', 'to_users', 'cc_users'
            ).order_by('created_at')
            
            # Mark as delivered and send to user
            from .serializers import serialize_message
            for msg in pending_messages:
                msg.mark_as_delivered_to(self.user)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error delivering pending messages: {e}")
    
    @database_sync_to_async
    def get_message_data(self, message):
        """Get serialized message data using unified serializer"""
        from .serializers import serialize_message
        return serialize_message(message)
    
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
        
        # Use unified serializer
        from .serializers import serialize_message
        return [serialize_message(msg) for msg in messages]