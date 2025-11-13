from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.employee_login, name='employee_login'),
    path('logout/', views.employee_logout, name='logout'),

    path('dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('tasks/', views.my_tasks, name='my_tasks'),
    path('attendance/', views.my_attendance, name='my_attendance'),
    path('leaves/', views.my_leaves, name='my_leaves'),
    path('projects/', views.my_projects, name='my_projects'),
    path('daily-report/', views.submit_daily_report, name='submit_daily_report'),
    
    # Manager URLs
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/team-attendance/', views.team_attendance, name='team_attendance'),
    path('manager/approve-leaves/', views.approve_leaves, name='approve_leaves'),
    
    # HR URLs
    path('hr/dashboard/', views.hr_dashboard, name='hr_dashboard'),
    path('hr/employees/', views.all_employees, name='all_employees'),
    
    # Profile & Settings
    path('profile/', views.profile, name='profile'),
    path('settings/', views.settings, name='settings'),
    
    # Resources
    path('documents/', views.documents, name='documents'),
    path('knowledgebase/', views.knowledgebase, name='knowledgebase'),
    path('training/', views.training, name='training'),
    
    # Support
    path('tickets/', views.tickets, name='tickets'),
    path('help/', views.help_center, name='help'),
    
    # Notifications
    path('notifications/', views.all_notifications, name='all_notifications'),
    
    # API Endpoints
    path('api/attendance/login/', views.attendance_login, name='attendance_login'),
    path('api/attendance/logout/', views.attendance_logout, name='attendance_logout'),
]
