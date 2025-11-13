from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import *
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages
from datetime import datetime, timedelta
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.core.paginator import Paginator

def employee_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome {user.first_name or user.username}!")
            return redirect("employee_dashboard")
        else:
            messages.error(request, "Invalid username or password")
    return render(request, "employee_login.html")

@login_required
def employee_logout(request):
    logout(request)
    return redirect("employee_login")


# views.py - Employee Dashboard Views


@login_required
def employee_dashboard(request):
    """Main dashboard view for employees"""
    user = request.user
    
    try:
        employee = user.employee_profile
    except:
        return redirect('employee_login')
    
    # Get current date info
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    
    # Attendance stats
    attendance_today = Attendance.objects.filter(
        employee=employee,
        date=today
    ).first()
    
    monthly_attendance = Attendance.objects.filter(
        employee=employee,
        date__month=current_month,
        date__year=current_year
    )
    
    attendance_stats = {
        'present_days': monthly_attendance.filter(login_time__isnull=False).count(),
        'total_working_days': 22,  # Can be dynamic
        'logged_in_today': attendance_today and attendance_today.login_time,
        'today_login_time': attendance_today.login_time if attendance_today else None,
        'today_logout_time': attendance_today.logout_time if attendance_today else None,
    }
    
    # Leave stats
    leave_stats = {
        'pending': LeaveRequest.objects.filter(employee=employee, status='pending').count(),
        'approved_this_month': LeaveRequest.objects.filter(
            employee=employee,
            status='approved',
            start_date__month=current_month
        ).count(),
        'total_available': 20,  # Calculate from LeaveType
    }
    
    # Task stats
    my_tasks = Task.objects.filter(assignee=user)
    task_stats = {
        'todo': my_tasks.filter(status='todo').count(),
        'in_progress': my_tasks.filter(status='in_progress').count(),
        'completed_this_week': my_tasks.filter(
            status='done',
            updated_at__gte=today - timedelta(days=7)
        ).count(),
        'overdue': my_tasks.filter(
            due_date__lt=today,
            status__in=['todo', 'in_progress']
        ).count(),
    }
    
    # Recent tasks
    recent_tasks = my_tasks.order_by('-updated_at')[:5]
    
    # Recent notifications
    notifications = Notification.objects.filter(
        recipient=user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # Upcoming events
    upcoming_events = CalendarEvent.objects.filter(
        Q(organizer=user) | Q(attendees=user),
        start__gte=timezone.now()
    ).order_by('start')[:5]
    
    # Daily report check
    daily_report_submitted = DailyReport.objects.filter(
        employee=employee,
        date=today
    ).exists()
    
    # Projects
    active_projects = employee.projects.filter(status='ongoing')[:5]
    
    # Announcements
    recent_announcements = Announcement.objects.filter(
        company=employee.company,
        is_public=True
    ).order_by('-created_at')[:3]
    
    context = {
        'employee': employee,
        'attendance_stats': attendance_stats,
        'leave_stats': leave_stats,
        'task_stats': task_stats,
        'recent_tasks': recent_tasks,
        'notifications': notifications,
        'upcoming_events': upcoming_events,
        'daily_report_submitted': daily_report_submitted,
        'active_projects': active_projects,
        'recent_announcements': recent_announcements,
        'today': today,
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def my_tasks(request):
    """Tasks list view"""
    user = request.user
    
    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    
    tasks = Task.objects.filter(assignee=user)
    
    if status_filter != 'all':
        tasks = tasks.filter(status=status_filter)
    
    if priority_filter != 'all':
        tasks = tasks.filter(priority=priority_filter)
    
    tasks = tasks.order_by('-priority', 'due_date')
    
    paginator = Paginator(tasks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
    }
    
    return render(request, 'tasks.html', context)


@login_required
def my_attendance(request):
    """Attendance history view"""
    employee = request.user.employee_profile
    
    month = request.GET.get('month', timezone.now().month)
    year = request.GET.get('year', timezone.now().year)
    
    attendances = Attendance.objects.filter(
        employee=employee,
        date__month=month,
        date__year=year
    ).order_by('-date')
    
    context = {
        'attendances': attendances,
        'month': month,
        'year': year,
    }
    
    return render(request, 'attendance.html', context)


@login_required
def my_leaves(request):
    """Leave management view"""
    employee = request.user.employee_profile
    
    leaves = LeaveRequest.objects.filter(
        employee=employee
    ).order_by('-created_at')
    
    leave_types = LeaveType.objects.filter(company=employee.company)
    
    context = {
        'leaves': leaves,
        'leave_types': leave_types,
    }
    
    return render(request, 'leaves.html', context)


@login_required
def my_projects(request):
    """Projects view"""
    employee = request.user.employee_profile
    
    projects = employee.projects.all().order_by('-created_at')
    
    context = {
        'projects': projects,
    }
    
    return render(request, 'projects.html', context)


@login_required
def submit_daily_report(request):
    """Daily report submission"""
    if request.method == 'POST':
        employee = request.user.employee_profile
        today = timezone.now().date()
        
        report, created = DailyReport.objects.update_or_create(
            employee=employee,
            date=today,
            defaults={
                'tasks_done': request.POST.get('tasks_done'),
                'blockers': request.POST.get('blockers', ''),
                'time_spent_hours': request.POST.get('time_spent_hours', 0),
                'mood': request.POST.get('mood', ''),
            }
        )
        
        return JsonResponse({'success': True, 'message': 'Report submitted successfully'})
    
    return render(request, 'daily_report.html')


# Manager-specific views
@login_required
def manager_dashboard(request):
    """Dashboard for managers"""
    user = request.user
    
    if user.role not in ['manager', 'admin', 'hr']:
        return redirect('employee_dashboard')
    
    # Get team members
    team_members = Employee.objects.filter(manager=user)
    
    # Team attendance today
    today = timezone.now().date()
    team_attendance = Attendance.objects.filter(
        employee__in=team_members,
        date=today
    )
    
    # Pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        employee__in=team_members,
        status='pending'
    )
    
    # Team tasks
    team_tasks = Task.objects.filter(assignee__in=[tm.user for tm in team_members])
    
    context = {
        'team_members': team_members,
        'team_attendance': team_attendance,
        'pending_leaves': pending_leaves,
        'team_tasks': team_tasks,
    }
    
    return render(request, 'manager_dashboard.html', context)


# HR-specific views
@login_required
def hr_dashboard(request):
    """Dashboard for HR"""
    user = request.user
    
    if user.role not in ['hr', 'admin']:
        return redirect('employee_dashboard')
    
    company = user.employee_profile.company
    
    # All employees stats
    total_employees = Employee.objects.filter(company=company, is_active_employee=True).count()
    
    # Recent hires
    recent_hires = Employee.objects.filter(
        company=company,
        date_of_joining__gte=timezone.now().date() - timedelta(days=30)
    )
    
    # Leave requests
    all_leave_requests = LeaveRequest.objects.filter(
        employee__company=company
    ).order_by('-created_at')[:10]
    
    context = {
        'total_employees': total_employees,
        'recent_hires': recent_hires,
        'all_leave_requests': all_leave_requests,
    }
    
    return render(request, 'hr_dashboard.html', context)


@login_required
def all_employees(request):
    """Complete employee directory with filters and search"""
    user = request.user
    
    # Check if user has HR/Admin access
    if user.role not in ['hr', 'admin']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    try:
        company = user.employee_profile.company
    except:
        return redirect('employee_dashboard')
    
    # Get all employees
    employees = Employee.objects.filter(
        company=company,
        is_deleted=False
    ).select_related('user', 'department', 'designation', 'manager')
    
    # Filters
    department_filter = request.GET.get('department', '')
    status_filter = request.GET.get('status', 'active')
    search_query = request.GET.get('search', '')
    
    if department_filter:
        employees = employees.filter(department_id=department_filter)
    
    if status_filter == 'active':
        employees = employees.filter(is_active_employee=True)
    elif status_filter == 'inactive':
        employees = employees.filter(is_active_employee=False)
    
    if search_query:
        employees = employees.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(employee_code__icontains=search_query)
        )
    
    # Order by
    employees = employees.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(employees, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get departments for filter
    departments = Department.objects.filter(company=company)
    
    # Statistics
    stats = {
        'total_employees': Employee.objects.filter(company=company, is_active_employee=True).count(),
        'new_this_month': Employee.objects.filter(
            company=company,
            date_of_joining__month=timezone.now().month,
            date_of_joining__year=timezone.now().year
        ).count(),
        'on_leave_today': LeaveRequest.objects.filter(
            employee__company=company,
            status='approved',
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        ).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'departments': departments,
        'department_filter': department_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'stats': stats,
    }
    
    return render(request, 'all_employees.html', context)


# ============================================
# 👤 Profile & Settings
# ============================================

@login_required
def profile(request):
    """User profile view and edit"""
    user = request.user
    
    try:
        employee = user.employee_profile
    except:
        return redirect('employee_dashboard')
    
    if request.method == 'POST':
        # Update profile
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.phone = request.POST.get('phone', user.phone)
        
        # Handle avatar upload
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']
        
        user.save()
        
        # Update employee info
        employee.emergency_contact = request.POST.get('emergency_contact', employee.emergency_contact)
        employee.address = request.POST.get('address', employee.address)
        employee.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    # Get user's recent activity
    recent_tasks = Task.objects.filter(assignee=user).order_by('-updated_at')[:5]
    recent_leaves = LeaveRequest.objects.filter(employee=employee).order_by('-created_at')[:5]
    
    # Performance stats
    performance_stats = {
        'total_tasks_completed': Task.objects.filter(assignee=user, status='done').count(),
        'projects_involved': employee.projects.count(),
        'attendance_rate': calculate_attendance_rate(employee),
        'avg_task_completion_time': calculate_avg_task_time(user),
    }
    
    context = {
        'user': user,
        'employee': employee,
        'recent_tasks': recent_tasks,
        'recent_leaves': recent_leaves,
        'performance_stats': performance_stats,
    }
    
    return render(request, 'profile.html', context)


@login_required
def settings(request):
    """User settings and preferences"""
    user = request.user
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_account':
            user.email = request.POST.get('email', user.email)
            user.save()
            messages.success(request, 'Account settings updated!')
            
        elif action == 'change_password':
            old_password = request.POST.get('old_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if user.check_password(old_password):
                if new_password == confirm_password:
                    user.set_password(new_password)
                    user.save()
                    messages.success(request, 'Password changed successfully!')
                else:
                    messages.error(request, 'New passwords do not match!')
            else:
                messages.error(request, 'Incorrect old password!')
                
        elif action == 'update_preferences':
            preferences = {
                'email_notifications': request.POST.get('email_notifications') == 'on',
                'push_notifications': request.POST.get('push_notifications') == 'on',
                'theme': request.POST.get('theme', 'dark'),
                'language': request.POST.get('language', 'en'),
            }
            user.preferences = preferences
            user.save()
            messages.success(request, 'Preferences updated!')
        
        return redirect('settings')
    
    context = {
        'user': user,
        'preferences': user.preferences or {},
    }
    
    return render(request, 'settings.html', context)


# ============================================
# 📚 Resources
# ============================================

@login_required
def documents(request):
    """Company documents and employee documents"""
    user = request.user
    
    try:
        employee = user.employee_profile
        company = employee.company
    except:
        return redirect('employee_dashboard')
    
    # Get documents
    company_documents = Document.objects.filter(
        company=company,
        is_deleted=False
    ).order_by('-created_at')
    
    # Filter by tags
    tag_filter = request.GET.get('tag', '')
    if tag_filter:
        company_documents = company_documents.filter(tags__contains=[tag_filter])
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        company_documents = company_documents.filter(
            Q(title__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(company_documents, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all unique tags
    all_tags = []
    for doc in Document.objects.filter(company=company):
        if doc.tags:
            all_tags.extend(doc.tags)
    unique_tags = list(set(all_tags))
    
    context = {
        'page_obj': page_obj,
        'unique_tags': unique_tags,
        'tag_filter': tag_filter,
        'search_query': search_query,
    }
    
    return render(request, 'employees/documents.html', context)


@login_required
def knowledgebase(request):
    """Knowledge base articles"""
    user = request.user
    
    try:
        employee = user.employee_profile
        company = employee.company
    except:
        return redirect('employee_dashboard')
    
    # Get KB articles
    articles = KBArticle.objects.filter(
        company=company,
        is_deleted=False
    )
    
    # Filter by public/private
    if user.role not in ['admin', 'hr']:
        articles = articles.filter(is_public=True)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        articles = articles.filter(
            Q(title__icontains=search_query) |
            Q(body__icontains=search_query)
        )
    
    articles = articles.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(articles, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Popular articles (based on views - you'd need to track this)
    popular_articles = articles[:5]
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'popular_articles': popular_articles,
    }
    
    return render(request, 'employees/knowledgebase.html', context)


@login_required
def training(request):
    """Training courses and enrollments"""
    user = request.user
    
    try:
        employee = user.employee_profile
        company = employee.company
    except:
        return redirect('employee_dashboard')
    
    # Get all courses
    all_courses = Course.objects.filter(
        company=company,
        is_deleted=False
    )
    
    # Get user's enrollments
    my_enrollments = Enrollment.objects.filter(
        user=user,
        is_deleted=False
    ).select_related('course')
    
    # Available courses (not enrolled)
    enrolled_course_ids = my_enrollments.values_list('course_id', flat=True)
    available_courses = all_courses.exclude(id__in=enrolled_course_ids)
    
    # Statistics
    stats = {
        'total_courses': all_courses.count(),
        'enrolled': my_enrollments.count(),
        'completed': my_enrollments.filter(status='completed').count(),
        'in_progress': my_enrollments.filter(status='enrolled').count(),
    }
    
    context = {
        'my_enrollments': my_enrollments,
        'available_courses': available_courses,
        'stats': stats,
    }
    
    return render(request, 'employees/training.html', context)


# ============================================
# 🧾 Support
# ============================================

@login_required
def tickets(request):
    """Support tickets system"""
    user = request.user
    
    try:
        employee = user.employee_profile
        company = employee.company
    except:
        return redirect('employee_dashboard')
    
    # Create new ticket
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        priority = request.POST.get('priority', 'medium')
        
        ticket = Ticket.objects.create(
            company=company,
            title=title,
            description=description,
            reporter=user,
            priority=priority,
            status='open',
            created_by=user
        )
        
        messages.success(request, f'Ticket #{ticket.id} created successfully!')
        return redirect('tickets')
    
    # Get tickets
    status_filter = request.GET.get('status', 'all')
    
    if user.role in ['admin', 'hr']:
        # Admin/HR can see all tickets
        tickets_list = Ticket.objects.filter(company=company)
    else:
        # Regular users see their own tickets
        tickets_list = Ticket.objects.filter(
            Q(reporter=user) | Q(assignee=user)
        )
    
    if status_filter != 'all':
        tickets_list = tickets_list.filter(status=status_filter)
    
    tickets_list = tickets_list.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(tickets_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'open': Ticket.objects.filter(reporter=user, status='open').count(),
        'in_progress': Ticket.objects.filter(reporter=user, status='in_progress').count(),
        'resolved': Ticket.objects.filter(reporter=user, status='resolved').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'stats': stats,
    }
    
    return render(request, 'employees/tickets.html', context)


@login_required
def help_center(request):
    """Help center with FAQs and guides"""
    user = request.user
    
    # FAQs organized by category
    faqs = {
        'Getting Started': [
            {'q': 'How do I reset my password?', 'a': 'Go to Settings > Security > Change Password and follow the instructions.'},
            {'q': 'How do I update my profile?', 'a': 'Navigate to Profile page and click Edit Profile button.'},
            {'q': 'How do I log attendance?', 'a': 'Click the Login/Logout button on your dashboard attendance card.'},
        ],
        'Leave Management': [
            {'q': 'How do I apply for leave?', 'a': 'Go to Leave Requests page, click "Apply for Leave" and fill in the required details.'},
            {'q': 'Who approves my leave?', 'a': 'Your direct manager or HR department approves leave requests.'},
            {'q': 'How many leave days do I have?', 'a': 'Check your Leave Requests page for your available leave balance.'},
        ],
        'Tasks & Projects': [
            {'q': 'How do I view my assigned tasks?', 'a': 'Visit the My Tasks page from the sidebar menu.'},
            {'q': 'Can I create my own tasks?', 'a': 'Depending on your role, you may be able to create tasks in Projects page.'},
            {'q': 'How do I update task status?', 'a': 'Click on the task and change its status from the dropdown menu.'},
        ],
        'Support': [
            {'q': 'How do I contact IT support?', 'a': 'Create a support ticket from the Support Tickets page.'},
            {'q': 'Where can I find company policies?', 'a': 'Check the Documents page under Resources section.'},
            {'q': 'How do I access training materials?', 'a': 'Navigate to Training page under Resources.'},
        ],
    }
    
    # Quick links
    quick_links = [
        {'title': 'Employee Handbook', 'url': '/documents/', 'icon': 'book'},
        {'title': 'IT Support', 'url': '/tickets/', 'icon': 'life-preserver'},
        {'title': 'HR Policies', 'url': '/documents/', 'icon': 'file-text'},
        {'title': 'Training Portal', 'url': '/training/', 'icon': 'trophy'},
    ]
    
    context = {
        'faqs': faqs,
        'quick_links': quick_links,
    }
    
    return render(request, 'employees/help_center.html', context)


# ============================================
# 🔔 Notifications
# ============================================

@login_required
def all_notifications(request):
    """All notifications page"""
    user = request.user
    
    # Mark as read action
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_all_read':
            Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)
            messages.success(request, 'All notifications marked as read!')
            return redirect('all_notifications')
        elif action == 'mark_read':
            notif_id = request.POST.get('notification_id')
            Notification.objects.filter(id=notif_id, recipient=user).update(is_read=True)
            return JsonResponse({'success': True})
    
    # Get notifications
    filter_type = request.GET.get('type', 'all')
    
    notifications = Notification.objects.filter(recipient=user)
    
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_type != 'all':
        notifications = notifications.filter(notif_type=filter_type)
    
    notifications = notifications.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Stats
    stats = {
        'total': Notification.objects.filter(recipient=user).count(),
        'unread': Notification.objects.filter(recipient=user, is_read=False).count(),
        'info': Notification.objects.filter(recipient=user, notif_type='info').count(),
        'alert': Notification.objects.filter(recipient=user, notif_type='alert').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'filter_type': filter_type,
        'stats': stats,
    }
    
    return render(request, 'notifications.html', context)


# ============================================
# 🕒 API Endpoints (Attendance)
# ============================================

@login_required
def attendance_login(request):
    """API endpoint for attendance login"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    user = request.user
    
    try:
        employee = user.employee_profile
    except:
        return JsonResponse({'success': False, 'error': 'Employee profile not found'})
    
    today = timezone.now().date()
    
    # Check if already logged in
    attendance = Attendance.objects.filter(employee=employee, date=today).first()
    
    if attendance and attendance.login_time:
        return JsonResponse({
            'success': False,
            'error': 'Already logged in today',
            'login_time': attendance.login_time.strftime('%I:%M %p')
        })
    
    # Create or update attendance
    if not attendance:
        attendance = Attendance.objects.create(
            employee=employee,
            date=today,
            login_time=timezone.now(),
            created_by=user
        )
    else:
        attendance.login_time = timezone.now()
        attendance.save()
    
    # Create notification
    Notification.objects.create(
        recipient=user,
        title='Attendance Logged',
        body=f'You have successfully logged in at {timezone.now().strftime("%I:%M %p")}',
        notif_type='info'
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Login recorded successfully',
        'login_time': attendance.login_time.strftime('%I:%M %p')
    })


@login_required
def attendance_logout(request):
    """API endpoint for attendance logout"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    user = request.user
    
    try:
        employee = user.employee_profile
    except:
        return JsonResponse({'success': False, 'error': 'Employee profile not found'})
    
    today = timezone.now().date()
    
    # Get today's attendance
    attendance = Attendance.objects.filter(employee=employee, date=today).first()
    
    if not attendance or not attendance.login_time:
        return JsonResponse({
            'success': False,
            'error': 'You must login first'
        })
    
    if attendance.logout_time:
        return JsonResponse({
            'success': False,
            'error': 'Already logged out today',
            'logout_time': attendance.logout_time.strftime('%I:%M %p')
        })
    
    # Update logout time
    attendance.logout_time = timezone.now()
    
    # Calculate total work time
    time_diff = attendance.logout_time - attendance.login_time
    attendance.total_work_seconds = int(time_diff.total_seconds())
    attendance.save()
    
    # Create notification
    work_hours = attendance.total_work_seconds / 3600
    Notification.objects.create(
        recipient=user,
        title='Attendance Logged Out',
        body=f'You have logged out at {timezone.now().strftime("%I:%M %p")}. Total work time: {work_hours:.2f} hours',
        notif_type='info'
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Logout recorded successfully',
        'logout_time': attendance.logout_time.strftime('%I:%M %p'),
        'total_hours': f'{work_hours:.2f}'
    })


# ============================================
# 👥 Manager Actions
# ============================================

@login_required
def team_attendance(request):
    """Manager view for team attendance"""
    user = request.user
    
    if user.role not in ['manager', 'admin', 'hr']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    try:
        employee = user.employee_profile
    except:
        return redirect('employee_dashboard')
    
    # Get team members
    if user.role == 'manager':
        team_members = Employee.objects.filter(manager=user, is_active_employee=True)
    else:
        # Admin/HR can see all
        team_members = Employee.objects.filter(company=employee.company, is_active_employee=True)
    
    # Date filter
    date_str = request.GET.get('date', timezone.now().date().isoformat())
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        selected_date = timezone.now().date()
    
    # Get attendance for selected date
    attendance_records = Attendance.objects.filter(
        employee__in=team_members,
        date=selected_date
    ).select_related('employee', 'employee__user')
    
    # Create a map of employee to attendance
    attendance_map = {att.employee.id: att for att in attendance_records}
    
    # Prepare team data
    team_data = []
    for member in team_members:
        att = attendance_map.get(member.id)
        team_data.append({
            'employee': member,
            'attendance': att,
            'status': 'present' if (att and att.login_time) else 'absent',
            'hours_worked': (att.total_work_seconds / 3600) if (att and att.total_work_seconds) else 0,
        })
    
    # Statistics
    stats = {
        'total_team': team_members.count(),
        'present': sum(1 for d in team_data if d['status'] == 'present'),
        'absent': sum(1 for d in team_data if d['status'] == 'absent'),
        'avg_hours': sum(d['hours_worked'] for d in team_data) / len(team_data) if team_data else 0,
    }
    
    context = {
        'team_data': team_data,
        'selected_date': selected_date,
        'stats': stats,
    }
    
    return render(request, 'employees/team_attendance.html', context)


@login_required
def approve_leaves(request):
    """Manager view to approve/reject leave requests"""
    user = request.user
    
    if user.role not in ['manager', 'admin', 'hr']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    try:
        employee = user.employee_profile
    except:
        return redirect('employee_dashboard')
    
    # Handle approval/rejection
    if request.method == 'POST':
        leave_id = request.POST.get('leave_id')
        action = request.POST.get('action')  # 'approve' or 'reject'
        
        leave_request = get_object_or_404(LeaveRequest, id=leave_id)
        
        if action == 'approve':
            leave_request.status = 'approved'
            leave_request.approver = user
            leave_request.save()
            
            # Notify employee
            Notification.objects.create(
                recipient=leave_request.employee.user,
                title='Leave Request Approved',
                body=f'Your leave request from {leave_request.start_date} to {leave_request.end_date} has been approved.',
                notif_type='info'
            )
            
            messages.success(request, 'Leave request approved!')
            
        elif action == 'reject':
            leave_request.status = 'rejected'
            leave_request.approver = user
            leave_request.save()
            
            # Notify employee
            Notification.objects.create(
                recipient=leave_request.employee.user,
                title='Leave Request Rejected',
                body=f'Your leave request from {leave_request.start_date} to {leave_request.end_date} has been rejected.',
                notif_type='warning'
            )
            
            messages.success(request, 'Leave request rejected!')
        
        return redirect('approve_leaves')
    
    # Get team members
    if user.role == 'manager':
        team_members = Employee.objects.filter(manager=user, is_active_employee=True)
    else:
        team_members = Employee.objects.filter(company=employee.company, is_active_employee=True)
    
    # Get pending leave requests
    status_filter = request.GET.get('status', 'pending')
    
    leave_requests = LeaveRequest.objects.filter(
        employee__in=team_members
    ).select_related('employee', 'employee__user', 'leave_type', 'approver')
    
    if status_filter != 'all':
        leave_requests = leave_requests.filter(status=status_filter)
    
    leave_requests = leave_requests.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(leave_requests, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'pending': LeaveRequest.objects.filter(employee__in=team_members, status='pending').count(),
        'approved': LeaveRequest.objects.filter(employee__in=team_members, status='approved').count(),
        'rejected': LeaveRequest.objects.filter(employee__in=team_members, status='rejected').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'stats': stats,
    }
    
    return render(request, 'employees/approve_leaves.html', context)


# ============================================
# Helper Functions
# ============================================

def calculate_attendance_rate(employee):
    """Calculate attendance percentage"""
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    total_working_days = 22  # You can make this dynamic
    present_days = Attendance.objects.filter(
        employee=employee,
        date__month=current_month,
        date__year=current_year,
        login_time__isnull=False
    ).count()
    
    return (present_days / total_working_days * 100) if total_working_days > 0 else 0


def calculate_avg_task_time(user):
    """Calculate average task completion time"""
    completed_tasks = Task.objects.filter(
        assignee=user,
        status='done'
    )
    
    if not completed_tasks.exists():
        return 0
    
    total_hours = 0
    for task in completed_tasks:
        if task.spent_seconds:
            total_hours += task.spent_seconds / 3600
    
    return total_hours / completed_tasks.count() if completed_tasks.count() > 0 else 0