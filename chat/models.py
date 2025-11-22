"""
chat/models.py
Production-ready chat system models with support for personal and group chats
"""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.postgres.indexes import GinIndex


class ChatRoomManager(models.Manager):
    def get_or_create_personal_room(self, user1, user2):
        """Get or create a personal chat room between two users"""
        # Ensure consistent ordering to prevent duplicates
        users = sorted([user1.id, user2.id], key=lambda x: str(x))
        
        room = self.filter(
            room_type='personal',
            memberships__user_id=users[0]
        ).filter(
            memberships__user_id=users[1]
        ).first()
        
        if not room:
            room = self.create(
                name=f"Chat: {user1.get_full_name()} & {user2.get_full_name()}",
                room_type='personal'
            )
            ChatRoomMembership.objects.create(room=room, user=user1)
            ChatRoomMembership.objects.create(room=room, user=user2)
        
        return room
    
    def get_user_rooms(self, user):
        """Get all rooms a user is a member of"""
        return self.filter(
            memberships__user=user,
            is_active=True
        ).prefetch_related('memberships__user').distinct()


class ChatRoom(models.Model):
    """Chat room - can be personal (1:1) or group"""
    ROOM_TYPE_CHOICES = (
        ('personal', 'Personal'),
        ('group', 'Group'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES, default='group', db_index=True)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='chat/rooms/', null=True, blank=True)
    
    # Group chat specific
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_rooms'
    )
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='admin_rooms',
        blank=True
    )
    
    # Metadata
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = ChatRoomManager()
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['room_type', 'is_active', '-updated_at']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def channel_group_name(self):
        """WebSocket channel group name"""
        return f'chat_{self.id}'
    
    def get_other_user(self, current_user):
        """For personal chats, get the other user"""
        if self.room_type == 'personal':
            membership = self.memberships.exclude(user=current_user).first()
            return membership.user if membership else None
        return None
    
    def get_last_message(self):
        """Get the most recent message"""
        return self.messages.filter(is_deleted=False).order_by('-created_at').first()
    
    def get_unread_count(self, user):
        """Get unread message count for a user"""
        membership = self.memberships.filter(user=user).first()
        if not membership:
            return 0
        
        return self.messages.filter(
            created_at__gt=membership.last_read_at,
            is_deleted=False
        ).exclude(sender=user).count()


class ChatRoomMembership(models.Model):
    """Membership of users in chat rooms"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_memberships')
    
    # Membership settings
    joined_at = models.DateTimeField(default=timezone.now)
    last_read_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_muted = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    
    # Notification preferences
    notifications_enabled = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('room', 'user')
        indexes = [
            models.Index(fields=['user', '-last_read_at']),
            models.Index(fields=['room', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} in {self.room.name}"
    
    def mark_as_read(self):
        """Mark all messages as read up to now"""
        self.last_read_at = timezone.now()
        self.save(update_fields=['last_read_at'])


class Message(models.Model):
    """Chat message"""
    MESSAGE_TYPE_CHOICES = (
        ('text', 'Text'),
        ('formal', 'Formal Email'),
        ('casual', 'Casual'),
        ('system', 'System'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages', db_index=True)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages'
    )
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text', db_index=True)
    content = models.TextField()
    
    # Formal email specific fields
    subject = models.CharField(max_length=500, blank=True)
    to_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='formal_messages_to',
        blank=True
    )
    cc_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='formal_messages_cc',
        blank=True
    )
    
    # Reply/thread support
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    # Metadata
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room', '-created_at']),
            models.Index(fields=['room', 'is_deleted', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.sender.get_full_name() if self.sender else 'System'}: {self.content[:50]}"
    
    def mark_as_read_by(self, user):
        """Mark message as read by a user"""
        meta, created = MessageMeta.objects.get_or_create(
            message=self,
            user=user,
            defaults={'read_at': timezone.now()}
        )
        if not created and not meta.read_at:
            meta.read_at = timezone.now()
            meta.save(update_fields=['read_at'])
    
    def mark_as_delivered_to(self, user):
        """Mark message as delivered to a user"""
        meta, created = MessageMeta.objects.get_or_create(
            message=self,
            user=user,
            defaults={'delivered_at': timezone.now()}
        )
        if not created and not meta.delivered_at:
            meta.delivered_at = timezone.now()
            meta.save(update_fields=['delivered_at'])
    
    def get_read_by_users(self):
        """Get list of users who have read this message"""
        return [
            meta.user for meta in self.meta.filter(read_at__isnull=False)
        ]


class MessageMeta(models.Model):
    """Message delivery and read receipts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='meta')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Receipt timestamps
    delivered_at = models.DateTimeField(null=True, blank=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    class Meta:
        unique_together = ('message', 'user')
        indexes = [
            models.Index(fields=['message', 'user']),
            models.Index(fields=['user', '-read_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.message.id}"


class Attachment(models.Model):
    """File attachments for messages"""
    ATTACHMENT_TYPE_CHOICES = (
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat/attachments/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # in bytes
    file_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES, default='other')
    mime_type = models.CharField(max_length=100)
    
    # Image/video specific
    thumbnail = models.ImageField(upload_to='chat/thumbnails/%Y/%m/%d/', null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return self.file_name


class TypingIndicator(models.Model):
    """Temporary model to track who is typing in which room"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='typing_indicators')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        unique_together = ('room', 'user')
        indexes = [
            models.Index(fields=['room', '-started_at']),
        ]
    
    @classmethod
    def cleanup_old(cls, seconds=10):
        """Remove typing indicators older than specified seconds"""
        threshold = timezone.now() - timezone.timedelta(seconds=seconds)
        cls.objects.filter(started_at__lt=threshold).delete()