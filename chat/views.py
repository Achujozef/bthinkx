"""
chat/views.py
Views for chat interface
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Max, Count, Prefetch
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message, ChatRoomMembership, Attachment
from django.core.paginator import Paginator
import json

User = get_user_model()


@login_required
def chat_list(request):
    """Display list of chat rooms"""
    user = request.user
    
    # Get all rooms user is a member of
    rooms = ChatRoom.objects.get_user_rooms(user).annotate(
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_time')
    
    # Prepare room data with unread counts
    room_data = []
    for room in rooms:
        membership = room.memberships.get(user=user)
        last_message = room.get_last_message()
        unread_count = room.get_unread_count(user)
        
        # For personal chats, get the other user
        other_user = None
        if room.room_type == 'personal':
            other_user = room.get_other_user(user)
        
        room_data.append({
            'room': room,
            'membership': membership,
            'last_message': last_message,
            'unread_count': unread_count,
            'other_user': other_user
        })
    
    context = {
        'room_data': room_data,
        'active_users': get_active_users(user),
    }
    
    return render(request, 'chat_list.html', context)


@login_required
def chat_room(request, room_id):
    """Display chat room conversation"""
    user = request.user
    room = get_object_or_404(ChatRoom, id=room_id, is_active=True)
    
    # Verify user has access
    membership = ChatRoomMembership.objects.filter(room=room, user=user).first()
    if not membership:
        return HttpResponseForbidden("You don't have access to this chat room.")
    
    # Get initial messages (last 50)
    messages = Message.objects.filter(
        room=room,
        is_deleted=False
    ).select_related('sender').prefetch_related(
        'attachments',
        'to_users',
        'cc_users',
        'meta'
    ).order_by('-created_at')[:50]
    
    messages = list(reversed(messages))
    
    # Mark messages as read
    membership.mark_as_read()
    
    # Get room members
    members = room.memberships.select_related('user').all()
    
    # For personal chats
    other_user = None
    if room.room_type == 'personal':
        other_user = room.get_other_user(user)
    
    context = {
        'room': room,
        'messages': messages,
        'membership': membership,
        'members': members,
        'other_user': other_user,
        'room_members_json': json.dumps([
            {
                'id': str(m.user.id),
                'name': m.user.get_full_name(),
                'avatar': m.user.avatar.url if m.user.avatar else None
            }
            for m in members
        ])
    }
    
    return render(request, 'chat_room.html', context)


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
    
    # Create room
    room = ChatRoom.objects.create(
        name=name,
        description=description,
        room_type='group',
        created_by=user
    )
    room.admins.add(user)
    
    # Add creator as member
    ChatRoomMembership.objects.create(room=room, user=user)
    
    # Add other members
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
    """Start or continue a personal chat with another user"""
    other_user = get_object_or_404(User, id=user_id)
    
    if other_user == request.user:
        return redirect('chat_list')
    
    # Get or create personal chat room
    room = ChatRoom.objects.get_or_create_personal_room(request.user, other_user)
    
    return redirect('chat_room', room_id=room.id)


@login_required
@require_http_methods(["POST"])
def upload_attachment(request, room_id):
    """Upload file attachment"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    # Verify access
    if not ChatRoomMembership.objects.filter(room=room, user=request.user).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    
    # Determine file type
    mime_type = file.content_type
    file_type = 'other'
    if mime_type.startswith('image/'):
        file_type = 'image'
    elif mime_type.startswith('video/'):
        file_type = 'video'
    elif mime_type.startswith('audio/'):
        file_type = 'audio'
    elif mime_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        file_type = 'document'
    
    # Create temporary message for attachment (will be linked properly in frontend)
    message = Message.objects.create(
        room=room,
        sender=request.user,
        content=f'Sent a file: {file.name}',
        message_type='text'
    )
    
    attachment = Attachment.objects.create(
        message=message,
        file=file,
        file_name=file.name,
        file_size=file.size,
        file_type=file_type,
        mime_type=mime_type
    )
    
    return JsonResponse({
        'success': True,
        'attachment': {
            'id': str(attachment.id),
            'message_id': str(message.id),
            'file_name': attachment.file_name,
            'file_url': attachment.file.url,
            'file_type': attachment.file_type,
            'file_size': attachment.file_size
        }
    })


@login_required
def search_users(request):
    """Search users for adding to chat"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
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
@require_http_methods(["POST"])
def add_member_to_group(request, room_id):
    """Add member to group chat"""
    room = get_object_or_404(ChatRoom, id=room_id, room_type='group')
    
    # Check if user is admin
    if not room.admins.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Only admins can add members'}, status=403)
    
    user_id = request.POST.get('user_id')
    new_member = get_object_or_404(User, id=user_id)
    
    # Add member if not already in group
    membership, created = ChatRoomMembership.objects.get_or_create(
        room=room,
        user=new_member
    )
    
    if created:
        # Send system message
        Message.objects.create(
            room=room,
            sender=None,
            content=f'{new_member.get_full_name()} was added to the group',
            message_type='system'
        )
    
    return JsonResponse({
        'success': True,
        'message': f'{new_member.get_full_name()} added to group'
    })


@login_required
@require_http_methods(["POST"])
def leave_group(request, room_id):
    """Leave a group chat"""
    room = get_object_or_404(ChatRoom, id=room_id, room_type='group')
    
    membership = ChatRoomMembership.objects.filter(
        room=room,
        user=request.user
    ).first()
    
    if membership:
        membership.delete()
        
        # Send system message
        Message.objects.create(
            room=room,
            sender=None,
            content=f'{request.user.get_full_name()} left the group',
            message_type='system'
        )
    
    return JsonResponse({'success': True})


def get_active_users(exclude_user):
    """Get list of recently active users"""
    # You can customize this based on your activity tracking
    return User.objects.exclude(id=exclude_user.id).filter(
        is_active=True
    ).order_by('first_name', 'last_name')[:20]