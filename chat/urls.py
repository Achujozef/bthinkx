"""
chat/urls.py
URL configuration for chat app - synced with views.py
"""
from django.urls import path
from . import views

urlpatterns = [
    # Main views
    path('', views.chat_list, name='chat_list'),
    path('room/<uuid:room_id>/', views.chat_room, name='chat_room'),
    
    # Chat creation
    path('create-group/', views.create_group_chat, name='create_group_chat'),
    path('start/<uuid:user_id>/', views.start_personal_chat, name='start_personal_chat'),
    
    # Message operations
    path('room/<uuid:room_id>/send/', views.send_message, name='send_message'),
    path('room/<uuid:room_id>/upload/', views.upload_attachment, name='upload_attachment'),
    path('message/<uuid:message_id>/edit/', views.edit_message, name='edit_message'),
    path('message/<uuid:message_id>/delete/', views.delete_message, name='delete_message'),
    path('message/<uuid:message_id>/status/', views.get_message_status, name='message_status'),
    
    # Search
    path('search-users/', views.search_users, name='search_users'),
    path('room/<uuid:room_id>/search/', views.search_messages, name='search_messages'),
    
    # Group management
    path('room/<uuid:room_id>/add-member/', views.add_member_to_group, name='add_member'),
    path('room/<uuid:room_id>/remove-member/', views.remove_member_from_group, name='remove_member'),
    path('room/<uuid:room_id>/leave/', views.leave_group, name='leave_group'),
    path('room/<uuid:room_id>/info/', views.get_room_info, name='room_info'),
    path('room/<uuid:room_id>/update/', views.update_group_info, name='update_group'),
    
    # Chat settings
    path('room/<uuid:room_id>/mute/', views.mute_chat, name='mute_chat'),
    path('room/<uuid:room_id>/pin/', views.pin_chat, name='pin_chat'),
    path('room/<uuid:room_id>/clear/', views.clear_chat, name='clear_chat'),
    path('room/<uuid:room_id>/mark-read/', views.mark_messages_read, name='mark_read'),
    path('room/<uuid:room_id>/typing/', views.update_typing_status, name='typing_status'),
    path('room/<uuid:room_id>/messages/', views.load_more_messages, name='load_messages'),
    
    # Blocking
    path('block/<uuid:user_id>/', views.block_user, name='block_user'),
    path('blocked-users/', views.get_blocked_users, name='blocked_users'),
]