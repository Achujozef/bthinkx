from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('edtech/', views.edtech, name='edtech'),
    path('dev/', views.dev, name='dev'),    
    path('career/', views.career, name='career'),
    path('dev-team-login/', views.dev_team_login, name='dev_team_login'),
    path('submit-contact-form/', views.submit_contact_form, name='submit_contact_form'),
    path('roadmap/', views.roadmap_view, name='roadmap'),


]
