"""
chat/admin.py
Django admin interface for chat management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    ChatRoom, ChatRoomMembership, Message, MessageMeta,
    Attachment, TypingIndicator
)


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'room_type', 'member_count', 'message_count', 'is_active', 'created_at']
    list_filter = ['room_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'channel_group_name']
    filter_horizontal = ['admins']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'room_type', 'description', 'avatar')
        }),
        ('Group Settings', {
            'fields': ('created_by', 'admins'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
        ('Technical', {
            'fields': ('channel_group_name',),
            'classes': ('collapse',)
        }),
    )
    
    def member_count(self, obj):
        count = obj.memberships.count()
        url = reverse('admin:chat_chatroommembership_changelist') + f'?room__id__exact={obj.id}'
        return format_html('<a href="{}">{} members</a>', url, count)
    member_count.short_description = 'Members'
    
    def message_count(self, obj):
        count = obj.messages.filter(is_deleted=False).count()
        url = reverse('admin:chat_message_changelist') + f'?room__id__exact={obj.id}'
        return format_html('<a href="{}">{} messages</a>', url, count)
    message_count.short_description = 'Messages'


@admin.register(ChatRoomMembership)
class ChatRoomMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'joined_at', 'last_read_at', 'is_muted', 'is_pinned']
    list_filter = ['is_muted', 'is_pinned', 'notifications_enabled', 'joined_at']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'room__name']
    readonly_fields = ['id', 'joined_at']
    raw_id_fields = ['user', 'room']
    
    fieldsets = (
        ('Membership', {
            'fields': ('id', 'room', 'user', 'joined_at')
        }),
        ('Settings', {
            'fields': ('is_muted', 'is_pinned', 'notifications_enabled', 'last_read_at')
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['truncated_content', 'sender', 'room', 'message_type', 'created_at', 'is_edited', 'is_deleted']
    list_filter = ['message_type', 'is_edited', 'is_deleted', 'created_at']
    search_fields = ['content', 'subject', 'sender__first_name', 'sender__last_name']
    readonly_fields = ['id', 'created_at', 'edited_at', 'read_receipts']
    raw_id_fields = ['room', 'sender', 'reply_to']
    filter_horizontal = ['to_users', 'cc_users']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Message Details', {
            'fields': ('id', 'room', 'sender', 'message_type', 'content')
        }),
        ('Formal Email Fields', {
            'fields': ('subject', 'to_users', 'cc_users'),
            'classes': ('collapse',)
        }),
        ('Thread', {
            'fields': ('reply_to',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_edited', 'is_deleted', 'created_at', 'edited_at')
        }),
        ('Read Receipts', {
            'fields': ('read_receipts',),
            'classes': ('collapse',)
        }),
    )
    
    def truncated_content(self, obj):
        if obj.message_type == 'formal':
            return f"📧 {obj.subject[:50]}..."
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
    truncated_content.short_description = 'Content'
    
    def read_receipts(self, obj):
        receipts = obj.meta.filter(read_at__isnull=False).select_related('user')
        if not receipts:
            return "No reads yet"
        
        html = "<ul>"
        for receipt in receipts:
            html += f"<li>{receipt.user.get_full_name()} - {receipt.read_at}</li>"
        html += "</ul>"
        return mark_safe(html)
    read_receipts.short_description = 'Read By'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('sender', 'room').prefetch_related('attachments')


@admin.register(MessageMeta)
class MessageMetaAdmin(admin.ModelAdmin):
    list_display = ['user', 'message_preview', 'delivered_at', 'read_at']
    list_filter = ['delivered_at', 'read_at']
    search_fields = ['user__first_name', 'user__last_name', 'message__content']
    readonly_fields = ['id', 'message', 'user', 'delivered_at', 'read_at']
    raw_id_fields = ['message', 'user']
    
    def message_preview(self, obj):
        return obj.message.content[:50] + ('...' if len(obj.message.content) > 50 else '')
    message_preview.short_description = 'Message'
    
    def has_add_permission(self, request):
        return False


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'file_type', 'file_size_display', 'message_preview', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['file_name', 'message__content']
    readonly_fields = ['id', 'file_name', 'file_size', 'mime_type', 'uploaded_at', 'preview']
    raw_id_fields = ['message']
    
    fieldsets = (
        ('File Information', {
            'fields': ('id', 'file_name', 'file', 'file_type', 'mime_type', 'file_size')
        }),
        ('Message', {
            'fields': ('message',)
        }),
        ('Media Details', {
            'fields': ('thumbnail', 'width', 'height'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('uploaded_at', 'preview')
        }),
    )
    
    def file_size_display(self, obj):
        size = obj.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = 'Size'
    
    def message_preview(self, obj):
        return obj.message.content[:30] + '...'
    message_preview.short_description = 'Message'
    
    def preview(self, obj):
        if obj.file_type == 'image':
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;" />',
                obj.file.url
            )
        elif obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;" />',
                obj.thumbnail.url
            )
        return "No preview available"
    preview.short_description = 'Preview'


@admin.register(TypingIndicator)
class TypingIndicatorAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'started_at', 'is_stale']
    list_filter = ['started_at']
    search_fields = ['user__first_name', 'user__last_name', 'room__name']
    readonly_fields = ['id', 'user', 'room', 'started_at']
    
    def is_stale(self, obj):
        from django.utils import timezone
        threshold = timezone.now() - timezone.timedelta(seconds=10)
        is_old = obj.started_at < threshold
        color = 'red' if is_old else 'green'
        text = 'Stale' if is_old else 'Active'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    is_stale.short_description = 'Status'
    
    def has_add_permission(self, request):
        return False


# Custom admin actions
def mark_rooms_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)
mark_rooms_inactive.short_description = "Mark selected rooms as inactive"

def mark_messages_deleted(modeladmin, request, queryset):
    from django.utils import timezone
    queryset.update(is_deleted=True)
mark_messages_deleted.short_description = "Mark selected messages as deleted"

# Add actions to admins
ChatRoomAdmin.actions = [mark_rooms_inactive]
MessageAdmin.actions = [mark_messages_deleted]


"""
chat/management/commands/cleanup_typing_indicators.py
Management command to clean up stale typing indicators
"""
from django.core.management.base import BaseCommand
from chat.models import TypingIndicator

class Command(BaseCommand):
    help = 'Clean up stale typing indicators'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seconds',
            type=int,
            default=10,
            help='Remove indicators older than this many seconds',
        )

    def handle(self, *args, **options):
        seconds = options['seconds']
        TypingIndicator.cleanup_old(seconds=seconds)
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cleaned up typing indicators older than {seconds} seconds'
            )
        )


"""
chat/management/commands/create_test_data.py
Create test chat data for development
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from chat.models import ChatRoom, ChatRoomMembership, Message

User = get_user_model()

class Command(BaseCommand):
    help = 'Create test chat data'

    def handle(self, *args, **options):
        # Get or create test users
        user1, _ = User.objects.get_or_create(
            username='alice',
            defaults={
                'first_name': 'Alice',
                'last_name': 'Smith',
                'email': 'alice@example.com'
            }
        )
        user1.set_password('password123')
        user1.save()
        
        user2, _ = User.objects.get_or_create(
            username='bob',
            defaults={
                'first_name': 'Bob',
                'last_name': 'Johnson',
                'email': 'bob@example.com'
            }
        )
        user2.set_password('password123')
        user2.save()
        
        # Create personal chat
        personal_room = ChatRoom.objects.get_or_create_personal_room(user1, user2)
        
        # Create some messages
        Message.objects.create(
            room=personal_room,
            sender=user1,
            content="Hey Bob, how's it going?",
            message_type='casual'
        )
        
        Message.objects.create(
            room=personal_room,
            sender=user2,
            content="Hi Alice! Doing great, thanks!",
            message_type='casual'
        )
        
        # Create group chat
        group_room = ChatRoom.objects.create(
            name='Project Team',
            room_type='group',
            description='Team collaboration chat',
            created_by=user1
        )
        group_room.admins.add(user1)
        
        ChatRoomMembership.objects.create(room=group_room, user=user1)
        ChatRoomMembership.objects.create(room=group_room, user=user2)
        
        # Create formal message
        formal_msg = Message.objects.create(
            room=group_room,
            sender=user1,
            content="Please review the attached proposal and provide your feedback by EOD.",
            message_type='formal',
            subject='Proposal Review Request'
        )
        formal_msg.to_users.add(user2)
        
        self.stdout.write(self.style.SUCCESS('Successfully created test data'))
        self.stdout.write(f'Personal chat: {personal_room.id}')
        self.stdout.write(f'Group chat: {group_room.id}')