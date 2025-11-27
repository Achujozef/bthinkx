"""
chat/serializers.py
Unified message serializer - single source of truth for all message serialization
"""
from django.contrib.auth import get_user_model
from .models import Message, Attachment

User = get_user_model()


def serialize_message(message, include_meta=False):
    """
    Unified message serializer used by:
    - WebSocket consumers
    - HTTP views
    - Message.to_json() method
    - All message broadcasts
    
    Args:
        message: Message instance
        include_meta: Whether to include read/delivery metadata
    
    Returns:
        dict: Complete message data structure
    """
    # Serialize sender
    sender_data = None
    if message.sender:
        sender_data = {
            'id': str(message.sender.id),
            'name': message.sender.get_full_name() or message.sender.username,
            'avatar': None
        }
        if hasattr(message.sender, 'avatar') and message.sender.avatar:
            try:
                sender_data['avatar'] = message.sender.avatar.url
            except:
                pass
    else:
        sender_data = {
            'id': None,
            'name': 'System',
            'avatar': None
        }
    
    # Serialize reply_to
    reply_to_data = None
    if message.reply_to:
        reply_to_data = {
            'id': str(message.reply_to.id),
            'sender': {
                'id': str(message.reply_to.sender.id) if message.reply_to.sender else None,
                'name': message.reply_to.sender.get_full_name() if message.reply_to.sender else 'System',
                'avatar': None
            },
            'content': (message.reply_to.content or '')[:100],
            'message_type': message.reply_to.message_type,
        }
        if message.reply_to.sender and hasattr(message.reply_to.sender, 'avatar') and message.reply_to.sender.avatar:
            try:
                reply_to_data['sender']['avatar'] = message.reply_to.sender.avatar.url
            except:
                pass
    
    # Serialize attachments
    attachments_data = []
    for att in message.attachments.all():
        att_data = {
            'id': str(att.id),
            'file_name': att.file_name,
            'file_size': att.file_size,
            'file_type': att.file_type,
            'mime_type': att.mime_type,
            'file_url': None,
            'thumbnail_url': None,
        }
        if att.file:
            try:
                att_data['file_url'] = att.file.url
            except:
                pass
        if att.thumbnail:
            try:
                att_data['thumbnail_url'] = att.thumbnail.url
            except:
                pass
        attachments_data.append(att_data)
    
    # Serialize formal message recipients
    to_users_data = []
    cc_users_data = []
    if message.message_type == 'formal':
        to_users_data = [
            {
                'id': str(u.id),
                'name': u.get_full_name() or u.username,
                'email': u.email
            }
            for u in message.to_users.all()
        ]
        cc_users_data = [
            {
                'id': str(u.id),
                'name': u.get_full_name() or u.username,
                'email': u.email
            }
            for u in message.cc_users.all()
        ]
    
    # Build base message data
    message_data = {
        'id': str(message.id),
        'room_id': str(message.room.id),
        'sender': sender_data,
        'content': message.content or '',
        'message_type': message.message_type,
        'subject': message.subject or '',
        'to_users': to_users_data,
        'cc_users': cc_users_data,
        'reply_to': reply_to_data,
        'attachments': attachments_data,
        'is_edited': message.is_edited,
        'is_deleted': message.is_deleted,
        'created_at': message.created_at.isoformat(),
        'edited_at': message.edited_at.isoformat() if message.edited_at else None,
    }
    
    # Add metadata if requested
    if include_meta:
        read_by = []
        delivered_to = []
        for meta in message.meta.all():
            user_info = {
                'user_id': str(meta.user.id),
                'user_name': meta.user.get_full_name() or meta.user.username,
            }
            if meta.delivered_at:
                delivered_to.append({
                    **user_info,
                    'timestamp': meta.delivered_at.isoformat()
                })
            if meta.read_at:
                read_by.append({
                    **user_info,
                    'timestamp': meta.read_at.isoformat()
                })
        message_data['meta'] = {
            'read_by': read_by,
            'delivered_to': delivered_to
        }
    
    return message_data


def sanitize_filename(filename):
    """Sanitize file name for safe storage"""
    import os
    import re
    # Remove path components
    filename = os.path.basename(filename)
    # Remove dangerous characters
    filename = re.sub(r'[^\w\s.-]', '', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    return filename or 'file'

