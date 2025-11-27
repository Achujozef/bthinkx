"""
chat/views.py
Production-ready chat views with full functionality
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Max, Count, Prefetch
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from .models import (
    ChatRoom, ChatRoomMembership, Message, MessageMeta,
    Attachment, TypingIndicator, BlockedUser
)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
import json
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


# ============ HELPER FUNCTIONS ============

def get_csrf_token(request):
    """Get CSRF token from request"""
    from django.middleware.csrf import get_token
    return get_token(request)


def broadcast_to_room(room_id, event_type, data):
    """
    Broadcast message to WebSocket room
    Uses normalized event names with dot notation for Channels routing
    """
    channel_layer = get_channel_layer()
    # Normalize event type to use dot notation
    normalized_type = event_type.replace('_', '.')
    async_to_sync(channel_layer.group_send)(
        f'chat_{room_id}',
        {'type': normalized_type, **data}
    )

def message_to_json(message):
    """Convert message to JSON-serializable dict - uses unified serializer"""
    from .serializers import serialize_message
    return serialize_message(message)


def check_user_blocked(user1, user2):
    """Check if either user has blocked the other"""
    return BlockedUser.objects.filter(
        Q(blocker=user1, blocked=user2) | Q(blocker=user2, blocked=user1)
    ).exists()


def get_room_context_data(user, rooms):
    """Build context data for room list"""
    room_data = []
    for room in rooms:
        membership = room.memberships.filter(user=user).first()
        if not membership:
            continue
            
        last_message = room.messages.filter(is_deleted=False).order_by('-created_at').first()
        
        # Calculate unread count
        if membership:
            unread_count = room.messages.filter(
                created_at__gt=membership.last_read_at,
                is_deleted=False
            ).exclude(sender=user).count()
        else:
            unread_count = 0
        
        # Get other user for personal chats
        other_user = None
        if room.room_type == 'personal':
            other_membership = room.memberships.exclude(user=user).first()
            if other_membership:
                other_user = other_membership.user
        
        room_data.append({
            'room': room,
            'membership': membership,
            'last_message': last_message,
            'unread_count': unread_count,
            'other_user': other_user
        })
    
    return room_data

# ============ MAIN VIEWS ============

@login_required
def chat_list(request):
    """List all chat rooms for user"""
    user = request.user
    rooms = ChatRoom.objects.get_user_rooms(user).annotate(
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_time')
    
    room_data = get_room_context_data(user, rooms)
    return render(request, 'chat_list.html', {'room_data': room_data})



@login_required
def chat_room(request, room_id):
    """Display chat room with messages"""
    user = request.user
    room = get_object_or_404(ChatRoom, id=room_id, is_active=True)
    
    # Check membership
    membership = ChatRoomMembership.objects.filter(room=room, user=user).first()
    if not membership:
        return HttpResponseForbidden("You don't have access to this chat room.")
    
    # Check blocking for personal chats
    other_user = None
    is_blocked = False
    blocked_by_other = False
    
    if room.room_type == 'personal':
        other_user = room.get_other_user(user)
        if other_user:
            is_blocked = BlockedUser.objects.filter(blocker=user, blocked=other_user).exists()
            blocked_by_other = BlockedUser.objects.filter(blocker=other_user, blocked=user).exists()
    
    # Get messages with related data
    messages = Message.objects.filter(
        room=room,
        is_deleted=False
    ).select_related(
        'sender', 'reply_to', 'reply_to__sender'
    ).prefetch_related(
        'attachments', 'to_users', 'cc_users', 'meta'
    ).order_by('-created_at')[:50]
    
    messages = list(reversed(messages))
    membership.mark_as_read()
    
    # Get members
    members = room.memberships.select_related('user').all()
    
    # Build sidebar data
    user_rooms = ChatRoom.objects.get_user_rooms(user).annotate(
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_time')
    room_data = get_room_context_data(user, user_rooms)
    
    context = {
        'room': room,
        'room_data': room_data,
        'messages': messages,
        'membership': membership,
        'members': members,
        'other_user': other_user,
        'user': user,
        'is_blocked': is_blocked,
        'blocked_by_other': blocked_by_other,
        'is_admin': room.admins.filter(id=user.id).exists(),
    }
    return render(request, 'chat_room.html', context)


# ============ CHAT CREATION ============
@login_required
@require_http_methods(["POST"])
def create_group_chat(request):
    """Create a new group chat"""
    user = request.user
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '')
    member_ids = request.POST.getlist('members[]')
    
    if not name:
        return JsonResponse({'error': 'Group name is required'}, status=400)
    
    room = ChatRoom.objects.create(
        name=name,
        description=description,
        room_type='group',
        created_by=user
    )
    room.admins.add(user)
    ChatRoomMembership.objects.create(room=room, user=user)
    
    if member_ids:
        members = User.objects.filter(id__in=member_ids)
        for member in members:
            ChatRoomMembership.objects.create(room=room, user=member)
    
    return JsonResponse({
        'success': True,
        'room_id': str(room.id),
        'redirect_url': f'/chat/room/{room.id}/'
    })

@login_required
def start_personal_chat(request, user_id):
    """Start or continue personal chat"""
    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        return redirect('chat_list')
    
    # Check blocking
    if BlockedUser.objects.filter(blocker=request.user, blocked=other_user).exists():
        return HttpResponseForbidden("You have blocked this user.")
    if BlockedUser.objects.filter(blocker=other_user, blocked=request.user).exists():
        return HttpResponseForbidden("This user has blocked you.")
        
    room = ChatRoom.objects.get_or_create_personal_room(request.user, other_user)
    return redirect('chat_room', room_id=room.id)

# ============ MESSAGE OPERATIONS ============

@login_required
@require_http_methods(["POST"])
def send_message(request, room_id):
    """Send a new message via HTTP (fallback for WebSocket)"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if not ChatRoomMembership.objects.filter(room=room, user=request.user).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Check blocking for personal chats
    if room.room_type == 'personal':
        other_user = room.get_other_user(request.user)
        if other_user and check_user_blocked(request.user, other_user):
            return JsonResponse({'error': 'Cannot send message - user blocked'}, status=403)
    
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        reply_to_id = data.get('reply_to')
        subject = data.get('subject', '')
        
        if not content:
            return JsonResponse({'error': 'Message content required'}, status=400)
        
        # Get reply_to message
        reply_to = None
        if reply_to_id:
            reply_to = Message.objects.filter(id=reply_to_id, room=room).first()
        
        # Create message
        message = Message.objects.create(
            room=room,
            sender=request.user,
            content=content,
            message_type=message_type,
            subject=subject,
            reply_to=reply_to
        )
        
        # Handle formal message recipients
        if message_type == 'formal':
            to_users = data.get('to_users', [])
            cc_users = data.get('cc_users', [])
            if to_users:
                message.to_users.set(User.objects.filter(id__in=to_users))
            if cc_users:
                message.cc_users.set(User.objects.filter(id__in=cc_users))
        
        # Update room timestamp
        room.updated_at = timezone.now()
        room.save(update_fields=['updated_at'])
        
        # Broadcast via WebSocket with normalized event name
        msg_json = message_to_json(message)
        broadcast_to_room(room.id, 'chat.message', {'message': msg_json})
        
        # Mark as delivered to all room members except sender
        from django.db import transaction
        with transaction.atomic():
            for membership in room.memberships.exclude(user=request.user):
                message.mark_as_delivered_to(membership.user)
        
        return JsonResponse({'success': True, 'message': msg_json})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return JsonResponse({'error': 'Failed to send message'}, status=500)

@login_required
@require_http_methods(["POST"])
def upload_attachment(request, room_id):
    """Handle file upload with optional text content"""
    from django.db import transaction
    from .serializers import sanitize_filename
    import os
    
    room = get_object_or_404(ChatRoom, id=room_id)
    if not ChatRoomMembership.objects.filter(room=room, user=request.user).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)

    content = request.POST.get('content', '').strip()
    reply_to_id = request.POST.get('reply_to')
    
    files = request.FILES.getlist('file')
    if not files and not content:
        return JsonResponse({'error': 'No content or file provided'}, status=400)

    # Resolve Reply
    reply_to = None
    if reply_to_id:
        try:
            reply_to = Message.objects.get(id=reply_to_id, room=room, is_deleted=False)
        except Message.DoesNotExist:
            pass

    # Transactional message and attachment creation
    with transaction.atomic():
        # Create Message
        message = Message.objects.create(
            room=room,
            sender=request.user,
            content=content if content else 'Sent a file',
            message_type='text',
            reply_to=reply_to
        )

        for file in files:
            # Size check
            if file.size > 50 * 1024 * 1024:  # 50MB limit
                continue
            
            # Sanitize filename
            safe_filename = sanitize_filename(file.name)
            
            mime_type = file.content_type or 'application/octet-stream'
            file_type = 'other'
            if mime_type.startswith('image/'): 
                file_type = 'image'
            elif mime_type.startswith('video/'): 
                file_type = 'video'
            elif mime_type.startswith('audio/'): 
                file_type = 'audio'
            elif mime_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']: 
                file_type = 'document'
            
            attachment = Attachment.objects.create(
                message=message,
                file=file,
                file_name=safe_filename,
                file_size=file.size,
                file_type=file_type,
                mime_type=mime_type
            )
            
            # Generate thumbnail for images (async/background task recommended for production)
            if file_type == 'image':
                try:
                    from PIL import Image
                    img = Image.open(attachment.file.path)
                    img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    thumb_name = f'thumb_{os.path.basename(attachment.file.name)}'
                    thumb_path = os.path.join(os.path.dirname(attachment.file.path), thumb_name)
                    img.save(thumb_path)
                    attachment.thumbnail.name = os.path.join(os.path.dirname(attachment.file.name), thumb_name)
                    attachment.width = img.width
                    attachment.height = img.height
                    attachment.save()
                except Exception as e:
                    logger.warning(f"Could not generate thumbnail: {e}")
        
        # Update room timestamp
        room.updated_at = timezone.now()
        room.save(update_fields=['updated_at'])
        
        # Mark as delivered to all room members except sender
        for membership in room.memberships.exclude(user=request.user):
            message.mark_as_delivered_to(membership.user)

    # Broadcast to WebSocket using unified serializer
    msg_json = message_to_json(message)
    broadcast_to_room(room.id, 'chat.message', {'message': msg_json})

    return JsonResponse({'success': True, 'message': msg_json})

@login_required
@require_http_methods(["POST"])
def edit_message(request, message_id):
    """Edit message"""
    try:
        data = json.loads(request.body)
        new_content = data.get('content', '').strip()
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
    if not new_content:
        return JsonResponse({'error': 'Empty content'}, status=400)
        
    message = get_object_or_404(Message, id=message_id)
    if message.sender != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
        
    if (timezone.now() - message.created_at).total_seconds() > 86400:
        return JsonResponse({'error': 'Edit period expired'}, status=403)
        
    message.content = new_content
    message.is_edited = True
    message.edited_at = timezone.now()
    message.save(update_fields=['content', 'is_edited', 'edited_at'])
    
    # Broadcast edit with full message data
    msg_json = message_to_json(message)
    broadcast_to_room(message.room.id, 'message.edited', {'message': msg_json})
    
    return JsonResponse({'success': True, 'message': msg_data})


@login_required
@require_http_methods(["POST"])
def delete_message(request, message_id):
    """Delete message"""
    message = get_object_or_404(Message, id=message_id)
    
    is_sender = message.sender == request.user
    is_admin = message.room.admins.filter(id=request.user.id).exists()
    
    if not (is_sender or is_admin):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    message.is_deleted = True
    message.save(update_fields=['is_deleted'])
    
    # Broadcast deletion with normalized event name
    broadcast_to_room(message.room.id, 'message.deleted', {'message_id': str(message.id)})
    
    return JsonResponse({'success': True})




# ============ SEARCH ============
@login_required
def search_users(request):
    """Search users for chat"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        users = User.objects.exclude(id=request.user.id).filter(is_active=True)[:20]
    else:
        users = User.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        ).exclude(id=request.user.id)[:10]
    
    return JsonResponse({
        'users': [
            {
                'id': str(u.id),
                'name': u.get_full_name(),
                'email': u.email,
                'avatar': u.avatar.url if u.avatar else None
            }
            for u in users
        ]
    })
@login_required
def search_messages(request, room_id):
    """Search messages in room"""
    room = get_object_or_404(ChatRoom, id=room_id)
    if not ChatRoomMembership.objects.filter(room=room, user=request.user).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    query = request.GET.get('q', '').strip()
    if len(query) < 2: 
        return JsonResponse({'results': []})
    
    messages = Message.objects.filter(
        room=room, 
        content__icontains=query, 
        is_deleted=False
    ).select_related('sender').order_by('-created_at')[:20]
    
    return JsonResponse({
        'results': [
            {
                'id': str(m.id), 
                'sender_name': m.sender.get_full_name() if m.sender else 'System', 
                'content': m.content[:100], 
                'created_at': m.created_at.isoformat()
            } 
            for m in messages
        ]
    })


# ============ GROUP MANAGEMENT ============

@login_required
@require_http_methods(["POST"])
def add_member_to_group(request, room_id):
    """Add member to group chat"""
    room = get_object_or_404(ChatRoom, id=room_id, room_type='group')
    
    if not room.admins.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Only admins can add members'}, status=403)
    
    user_id = request.POST.get('user_id') or json.loads(request.body).get('user_id')
    new_member = get_object_or_404(User, id=user_id)
    
    membership, created = ChatRoomMembership.objects.get_or_create(
        room=room,
        user=new_member
    )
    
    if created:
        Message.objects.create(
            room=room,
            sender=None,
            content=f'{new_member.get_full_name()} was added by {request.user.get_full_name()}',
            message_type='system'
        )
    
    return JsonResponse({
        'success': True,
        'created': created,
        'message': f'{new_member.get_full_name()} {"added to" if created else "already in"} group'
    })


@login_required
@require_http_methods(["POST"])
def remove_member_from_group(request, room_id):
    """Remove member from group chat"""
    room = get_object_or_404(ChatRoom, id=room_id, room_type='group')
    
    if not room.admins.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Only admins can remove members'}, status=403)
    
    user_id = request.POST.get('user_id') or json.loads(request.body).get('user_id')
    member_to_remove = get_object_or_404(User, id=user_id)
    
    # Can't remove self if only admin
    if member_to_remove == request.user:
        admin_count = room.admins.count()
        if admin_count <= 1:
            return JsonResponse({'error': 'Cannot remove yourself as the only admin'}, status=400)
    
    ChatRoomMembership.objects.filter(room=room, user=member_to_remove).delete()
    room.admins.remove(member_to_remove)
    
    Message.objects.create(
        room=room,
        sender=None,
        content=f'{member_to_remove.get_full_name()} was removed by {request.user.get_full_name()}',
        message_type='system'
    )
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def leave_group(request, room_id):
    """Leave group"""
    room = get_object_or_404(ChatRoom, id=room_id, room_type='group')
    ChatRoomMembership.objects.filter(room=room, user=request.user).delete()
    
    # Send system message
    Message.objects.create(
        room=room,
        sender=None,
        content=f'{request.user.get_full_name()} left the group',
        message_type='system'
    )
    
    return JsonResponse({'success': True})


# ============ CHAT SETTINGS ============

@login_required
@require_http_methods(["POST"])
def mute_chat(request, room_id):
    """Mute/unmute chat"""
    room = get_object_or_404(ChatRoom, id=room_id)
    m = ChatRoomMembership.objects.get(room=room, user=request.user)
    m.is_muted = not m.is_muted
    m.save(update_fields=['is_muted'])
    
    # Broadcast mute status change
    broadcast_to_room(room.id, 'chat.muted', {
        'room_id': str(room.id),
        'user_id': str(request.user.id),
        'is_muted': m.is_muted
    })
    
    return JsonResponse({'success': True, 'is_muted': m.is_muted})

@login_required
@require_http_methods(["POST"])
def pin_chat(request, room_id):
    """Toggle pin status for chat"""
    room = get_object_or_404(ChatRoom, id=room_id)
    membership = get_object_or_404(ChatRoomMembership, room=room, user=request.user)
    
    membership.is_pinned = not membership.is_pinned
    membership.save(update_fields=['is_pinned'])
    
    # Broadcast pin status change
    broadcast_to_room(room.id, 'chat.pinned', {
        'room_id': str(room.id),
        'user_id': str(request.user.id),
        'is_pinned': membership.is_pinned
    })
    
    return JsonResponse({
        'success': True,
        'is_pinned': membership.is_pinned,
        'message': 'Chat pinned' if membership.is_pinned else 'Chat unpinned'
    })


@login_required
@require_http_methods(["POST"])
def clear_chat(request, room_id):
    """Clear chat history for user (marks as read)"""
    room = get_object_or_404(ChatRoom, id=room_id)
    membership = get_object_or_404(ChatRoomMembership, room=room, user=request.user)
    
    membership.last_read_at = timezone.now()
    membership.save(update_fields=['last_read_at'])
    
    return JsonResponse({'success': True})


# ============ BLOCKING ============
@login_required
@require_http_methods(["POST"])
def block_user(request, user_id):
    """Block/unblock user"""
    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        return JsonResponse({'error': 'Cannot block self'}, status=400)
        
    blocked_obj, created = BlockedUser.objects.get_or_create(
        blocker=request.user,
        blocked=other_user
    )
    
    if not created:
        blocked_obj.delete()
        is_blocked = False
        msg = 'User unblocked'
    else:
        is_blocked = True
        msg = 'User blocked'
    
    # Broadcast block status change to all shared rooms
    shared_rooms = ChatRoom.objects.filter(
        room_type='personal',
        memberships__user=request.user
    ).filter(memberships__user=other_user).distinct()
    
    for room in shared_rooms:
        broadcast_to_room(room.id, 'user.blocked', {
            'user_id': str(other_user.id),
            'blocked_by': str(request.user.id),
            'is_blocked': is_blocked
        })
        
    return JsonResponse({'success': True, 'is_blocked': is_blocked, 'message': msg})

@login_required
def get_blocked_users(request):
    """Get list of blocked users"""
    blocked = BlockedUser.objects.filter(blocker=request.user).select_related('blocked')
    
    return JsonResponse({
        'blocked_users': [
            {
                'id': str(b.blocked.id),
                'name': b.blocked.get_full_name(),
                'blocked_at': b.created_at.isoformat()
            }
            for b in blocked
        ]
    })


# ============ MESSAGE STATUS ============

@login_required
def get_message_status(request, message_id):
    """Get read/delivery status of a message"""
    message = get_object_or_404(Message, id=message_id)
    
    if message.sender != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    meta = message.meta.select_related('user').all()
    
    delivered_to = []
    read_by = []
    
    for m in meta:
        user_info = {
            'user_id': str(m.user.id),
            'user_name': m.user.get_full_name(),
        }
        if m.delivered_at:
            delivered_to.append({**user_info, 'timestamp': m.delivered_at.isoformat()})
        if m.read_at:
            read_by.append({**user_info, 'timestamp': m.read_at.isoformat()})
    
    return JsonResponse({
        'delivered_to': delivered_to,
        'read_by': read_by,
        'total_recipients': message.room.memberships.exclude(user=message.sender).count()
    })


@login_required
@require_http_methods(["POST"])
def mark_messages_read(request, room_id):
    """Mark all messages in room as read"""
    room = get_object_or_404(ChatRoom, id=room_id)
    membership = get_object_or_404(ChatRoomMembership, room=room, user=request.user)
    
    membership.mark_as_read()
    
    return JsonResponse({'success': True})


# ============ TYPING INDICATOR ============

@login_required
@require_http_methods(["POST"])
def update_typing_status(request, room_id):
    """Update typing status (HTTP fallback)"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if not ChatRoomMembership.objects.filter(room=room, user=request.user).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        is_typing = data.get('is_typing', False)
    except:
        is_typing = request.POST.get('is_typing') == 'true'
    
    if is_typing:
        TypingIndicator.objects.update_or_create(
            room=room,
            user=request.user,
            defaults={'started_at': timezone.now()}
        )
    else:
        TypingIndicator.objects.filter(room=room, user=request.user).delete()
    
    # Broadcast typing status with normalized event name
    broadcast_to_room(room.id, 'typing.indicator', {
        'user_id': str(request.user.id),
        'user_name': request.user.get_full_name(),
        'is_typing': is_typing
    })
    
    return JsonResponse({'success': True})


# ============ LOAD MORE MESSAGES ============

@login_required
def load_more_messages(request, room_id):
    """Load older messages for pagination"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if not ChatRoomMembership.objects.filter(room=room, user=request.user).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    before_id = request.GET.get('before')
    limit = min(int(request.GET.get('limit', 50)), 100)
    
    messages = Message.objects.filter(
        room=room,
        is_deleted=False
    ).select_related('sender', 'reply_to', 'reply_to__sender').prefetch_related('attachments')
    
    if before_id:
        try:
            before_msg = Message.objects.get(id=before_id)
            messages = messages.filter(created_at__lt=before_msg.created_at)
        except Message.DoesNotExist:
            pass
    
    messages = messages.order_by('-created_at')[:limit]
    messages = list(reversed(messages))
    
    return JsonResponse({
        'messages': [message_to_json(m) for m in messages],
        'has_more': len(messages) == limit
    })


# ============ UTILITY VIEWS ============

@login_required
def get_room_info(request, room_id):
    """Get room information"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if not ChatRoomMembership.objects.filter(room=room, user=request.user).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    members = room.memberships.select_related('user').all()
    admins = room.admins.all()
    
    return JsonResponse({
        'room': {
            'id': str(room.id),
            'name': room.name,
            'room_type': room.room_type,
            'description': room.description,
            'created_at': room.created_at.isoformat(),
            'member_count': members.count(),
        },
        'members': [
            {
                'id': str(m.user.id),
                'name': m.user.get_full_name(),
                'email': m.user.email,
                'is_admin': m.user in admins,
                'joined_at': m.joined_at.isoformat(),
            }
            for m in members
        ],
        'is_admin': request.user in admins,
    })


@login_required
@require_http_methods(["POST"])
def update_group_info(request, room_id):
    """Update group chat info (name, description)"""
    room = get_object_or_404(ChatRoom, id=room_id, room_type='group')
    
    if not room.admins.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Only admins can update group info'}, status=403)
    
    try:
        data = json.loads(request.body)
    except:
        data = request.POST
    
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if name:
        room.name = name
    if description is not None:
        room.description = description
    
    room.save(update_fields=['name', 'description', 'updated_at'])
    
    return JsonResponse({
        'success': True,
        'room': {
            'id': str(room.id),
            'name': room.name,
            'description': room.description,
        }
    })