from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('login/', views.employee_login, name='employee_login'),
    path('logout/', views.employee_logout, name='logout'),

    # Dashboard
    path('dashboard/', views.employee_dashboard, name='employee_dashboard'),
    
    # Tasks
    path('tasks/', views.my_tasks, name='my_tasks'),
    path('api/tasks/create/', views.create_task, name='create_task'),
    path('api/tasks/<str:task_id>/toggle/', views.update_task_status, name='toggle_task_status'),
    path('api/tasks/<str:task_id>/update-status/', views.update_task_status, name='update_task_status'),
    path('api/tasks/<str:task_id>/details/', views.task_details_api, name='task_details_api'),
    path('api/tasks/<str:task_id>/edit-description/', views.edit_task_description, name='edit_task_description'),
    path('api/tasks/<str:task_id>/complete/', views.complete_task, name='complete_task'),
    path('api/tasks/<str:task_id>/reopen/', views.reopen_task, name='reopen_task'),
    path('api/project-members/', views.api_project_members, name='api_project_members'),
    # Attendance
    path('attendance/', views.my_attendance, name='my_attendance'),
    path('api/attendance/login/', views.attendance_login, name='attendance_login'),
    path('api/attendance/logout/', views.attendance_logout, name='attendance_logout'),
    
    # Leaves
    path('leaves/', views.my_leaves, name='my_leaves'),
    path('api/leaves/create/', views.create_leave_request, name='create_leave_request'),
    path('api/leaves/<str:leave_id>/update/', views.update_leave_request, name='update_leave_request'),
    path('api/leaves/<str:leave_id>/cancel/', views.cancel_leave_request, name='cancel_leave_request'),
    
    # Projects
    path('projects/', views.my_projects, name='my_projects'),
    path('api/projects/create/', views.project_create, name='project_create'),
    path('api/projects/<str:project_id>/update/', views.project_update, name='project_update'),
    path('api/projects/<str:project_id>/delete/', views.project_delete, name='project_delete'),
    # Daily Report
    path('daily-report/', views.submit_daily_report, name='submit_daily_report'),
    
    # Performance
    path('api/performance/<int:employee_id>/history/', views.performance_history_api, name='performance_history_api'),

    # Manager URLs
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/team-attendance/', views.team_attendance, name='team_attendance'),
    path('manager/approve-leaves/', views.approve_leaves, name='approve_leaves'),
    path('manager/award-performance/', views.award_performance_points, name='award_performance_points'),
    
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
]