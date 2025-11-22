
"""
chat/urls.py
URL patterns for chat views
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_list, name='chat_list'),
    path('room/<uuid:room_id>/', views.chat_room, name='chat_room'),
    path('create-group/', views.create_group_chat, name='create_group_chat'),
    path('start/<uuid:user_id>/', views.start_personal_chat, name='start_personal_chat'),
    path('room/<uuid:room_id>/upload/', views.upload_attachment, name='upload_attachment'),
    path('room/<uuid:room_id>/add-member/', views.add_member_to_group, name='add_member_to_group'),
    path('room/<uuid:room_id>/leave/', views.leave_group, name='leave_group'),
    path('search-users/', views.search_users, name='search_users'),
]