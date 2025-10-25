from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('submit-contact-form/', views.submit_contact_form, name='submit_contact_form'),
    path('roadmap/', views.roadmap_view, name='roadmap'),

    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('dashboard/coordinator/', views.coordinator_dashboard, name='coordinator_dashboard'),
    path('dashboard/manager/', views.manager_dashboard, name='manager_dashboard'),
]
