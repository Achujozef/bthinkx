from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from .models import *
from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Sum, Count
from datetime import datetime, timedelta
import calendar
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
import json



def employee_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome {user.first_name or user.username}!")

            if user.is_superuser or user.role == "admin":
                return redirect("hr_dashboard")

            return redirect("employee_dashboard")

        messages.error(request, "Invalid username or password")

    return render(request, "employee_login.html")


@login_required
def employee_logout(request):
    logout(request)
    return redirect("employee_login")
from django.db.models import Avg, Count, Sum, Q, F
from decimal import Decimal
import json

@login_required
def employee_dashboard(request):
    """
    Enhanced dashboard with performance metrics.
    Passes all required values to the template for chart.js in dashboard.html.
    Production-ready with error handling and data validation.
    """
    user = request.user
    
    try:
        employee = user.employee_profile
    except AttributeError:
        messages.error(request, 'Employee profile not found. Please contact HR.')
        return redirect('employee_login')
    except Exception as e:
        messages.error(request, f'Error loading dashboard: {str(e)}')
        return redirect('employee_login')
    
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    
    # Initialize default values for error handling
    attendance_stats = {
        'present_days': 0,
        'total_working_days': 22,
        'logged_in_today': False,
        'today_login_time': None,
        'today_logout_time': None,
    }
    
    leave_stats = {
        'pending': 0,
        'approved_this_month': 0,
        'total_available': 20,
    }
    
    task_stats = {
        'todo': 0,
        'in_progress': 0,
        'completed_this_week': 0,
        'overdue': 0,
    }
    
    performance_stats = {
        'avg_points': 0.0,
        'total_days_rated': 0,
        'today_points': None,
        'today_feedback': None,
        'performance_color': 'average',
        'performance_label': 'Not Rated',
        'trend': 'stable',
        'trend_percentage': 0.0,
        'rating_distribution': [],
    }
    
    performance_history = []
    
    # ============ ATTENDANCE STATS ============
    try:
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
            'total_working_days': 22,
            'logged_in_today': bool(attendance_today and attendance_today.login_time),
            'today_login_time': attendance_today.login_time if attendance_today else None,
            'today_logout_time': attendance_today.logout_time if attendance_today else None,
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching attendance stats: {e}")
        # Keep default values
    
    # ============ LEAVE STATS ============
    try:
        leave_stats = {
            'pending': LeaveRequest.objects.filter(employee=employee, status='pending').count(),
            'approved_this_month': LeaveRequest.objects.filter(
                employee=employee,
                status='approved',
                start_date__month=current_month,
                start_date__year=current_year
            ).count(),
            'total_available': 20,
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching leave stats: {e}")
        # Keep default values
    
    # ============ TASK STATS ============
    try:
        my_tasks = Task.objects.filter(assignee=user)
        task_stats = {
            'todo': my_tasks.filter(status='todo').count(),
            'in_progress': my_tasks.filter(status='in_progress').count(),
            'completed_this_week': my_tasks.filter(
                status='done',
                updated_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
            'overdue': my_tasks.filter(
                due_date__lt=today,
                status__in=['todo', 'in_progress']
            ).count(),
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching task stats: {e}")
        my_tasks = Task.objects.none()
        # Keep default values
    
    # ============ PERFORMANCE STATS ============
    try:
        thirty_days_ago = today - timedelta(days=30)
        
        performance_records = PerformancePoint.objects.filter(
            employee=employee,
            date__gte=thirty_days_ago
        ).order_by('date')
        
        total_points = performance_records.aggregate(
            total=Sum('points'),
            count=Count('id'),
            avg=Avg('points')
        )
        
        avg_performance = float(total_points['avg'] or 0)
        total_days_rated = total_points['count'] or 0
        
        today_performance = PerformancePoint.objects.filter(
            employee=employee,
            date=today
        ).first()
        
        last_7_days = performance_records.filter(
            date__gte=today - timedelta(days=7)
        ).aggregate(avg=Avg('points'))['avg'] or 0
        last_7_days = float(last_7_days or 0)
        
        previous_7_days = PerformancePoint.objects.filter(
            employee=employee,
            date__gte=today - timedelta(days=14),
            date__lt=today - timedelta(days=7)
        ).aggregate(avg=Avg('points'))['avg'] or 0
        previous_7_days = float(previous_7_days or 0)
        
        performance_trend = 'up' if last_7_days > previous_7_days else 'down' if last_7_days < previous_7_days else 'stable'
        trend_percentage = 0.0
        if previous_7_days > 0:
            trend_percentage = ((last_7_days - previous_7_days) / previous_7_days) * 100

        # Performance rating distribution - filter out blank/null and ensure no duplicates
        rating_distribution_raw = performance_records.filter(
            rating__isnull=False
        ).exclude(
            rating=''
        ).values('rating').annotate(
            count=Count('id')
        )
        
        # Ensure unique ratings and proper ordering - prevent duplicates
        rating_order = ['poor', 'below_average', 'average', 'good', 'excellent']
        rating_dict = {}
        for r in rating_distribution_raw:
            rating = r['rating']
            # Only include valid ratings from RATING_CHOICES
            if rating in rating_order:
                # If rating already exists, sum the counts (shouldn't happen but safety check)
                rating_dict[rating] = rating_dict.get(rating, 0) + r['count']
        
        # Build final distribution with proper ordering, only showing ratings with count > 0
        rating_distribution = [
            {'rating': rating, 'count': rating_dict.get(rating, 0)}
            for rating in rating_order
            if rating in rating_dict and rating_dict[rating] > 0
        ]
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching performance stats: {e}", exc_info=True)
        performance_records = PerformancePoint.objects.none()
        avg_performance = 0.0
        total_days_rated = 0
        today_performance = None
        last_7_days = 0.0
        previous_7_days = 0.0
        performance_trend = 'stable'
        trend_percentage = 0.0
        rating_distribution = []
    
    # Prepare all 30 days (business days) for the chart, including leaves
    try:
        all_dates = []
        records_map = {}
        for rec in performance_records:
            try:
                date_key = rec.date.strftime('%Y-%m-%d')
                points_val = None
                if rec.points is not None:
                    try:
                        points_val = float(rec.points)
                    except (ValueError, TypeError):
                        points_val = None
                
                records_map[date_key] = {
                    'date': date_key,
                    'points': points_val,
                    'on_leave': rec.on_leave if hasattr(rec, 'on_leave') else False,
                    'feedback': rec.feedback if rec.feedback else '',
                    'rating': rec.rating if rec.rating else None,
                }
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error processing performance record {rec.id}: {e}")
                continue
        
        current_date = thirty_days_ago
        while current_date <= today:
            if current_date.weekday() < 5:  # Only weekdays
                key = current_date.strftime('%Y-%m-%d')
                if key in records_map:
                    entry = records_map[key]
                else:
                    try:
                        on_leave = LeaveRequest.objects.filter(
                            employee=employee,
                            status='approved',
                            start_date__lte=current_date,
                            end_date__gte=current_date
                        ).exists()
                    except Exception:
                        on_leave = False
                    
                    entry = {
                        'date': key,
                        'points': None,
                        'on_leave': on_leave,
                        'feedback': 'On Leave' if on_leave else 'Not Rated',
                        'rating': None,
                    }
                all_dates.append(entry)
            current_date += timedelta(days=1)

        # The below is required for the chartjs script in dashboard.html
        # window expects:  const allPerformanceHistory = {{ performance_history|safe }}
        # Each: {date, points, feedback, on_leave}
        performance_history = []
        for entry in all_dates:
            try:
                # Only required fields for JS chart
                performance_history.append({
                    'date': entry.get('date', ''),
                    'points': entry.get('points'),
                    'feedback': entry.get('feedback', ''),
                    'on_leave': entry.get('on_leave', False)
                })
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error processing chart entry: {e}")
                continue
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error preparing chart data: {e}", exc_info=True)
        performance_history = []

    # Determine performance color and label
    try:
        if avg_performance >= 8.5:
            performance_color = 'excellent'
            performance_label = 'Excellent'
        elif avg_performance >= 7:
            performance_color = 'good'
            performance_label = 'Good'
        elif avg_performance >= 5:
            performance_color = 'average'
            performance_label = 'Average'
        elif avg_performance >= 3:
            performance_color = 'below'
            performance_label = 'Needs Improvement'
        else:
            performance_color = 'poor'
            performance_label = 'Critical'
        
        today_points = None
        today_feedback = None
        if today_performance:
            try:
                today_points = float(today_performance.points) if today_performance.points is not None else None
                today_feedback = today_performance.feedback if today_performance.feedback else None
            except (ValueError, TypeError):
                today_points = None
                today_feedback = None
        
        performance_stats = {
            'avg_points': round(avg_performance, 2),
            'total_days_rated': total_days_rated,
            'today_points': today_points,
            'today_feedback': today_feedback,
            'performance_color': performance_color,
            'performance_label': performance_label,
            'trend': performance_trend,
            'trend_percentage': round(trend_percentage, 1),
            'rating_distribution': rating_distribution,
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error calculating performance stats: {e}", exc_info=True)
        # Keep default values set earlier

    # ============ OTHER DATA ============
    try:
        recent_tasks = my_tasks.order_by('-updated_at')[:5] if 'my_tasks' in locals() else []
    except Exception:
        recent_tasks = []
    
    try:
        notifications = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).order_by('-created_at')[:5]
    except Exception:
        notifications = []
    
    try:
        upcoming_events = CalendarEvent.objects.filter(
            Q(organizer=user) | Q(attendees=user),
            start__gte=timezone.now()
        ).order_by('start')[:5]
    except Exception:
        upcoming_events = []
    
    try:
        daily_report_submitted = DailyReport.objects.filter(
            employee=employee,
            date=today
        ).exists()
    except Exception:
        daily_report_submitted = False
    
    try:
        active_projects = employee.projects.filter(status='ongoing')[:5] if hasattr(employee, 'projects') else []
    except Exception:
        active_projects = []
    
    try:
        recent_announcements = Announcement.objects.filter(
            company=employee.company,
            is_public=True
        ).order_by('-created_at')[:3]
    except Exception:
        recent_announcements = []
    
    # Safely serialize performance_history to JSON
    try:
        performance_history_json = json.dumps(performance_history, default=str)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serializing performance history: {e}")
        performance_history_json = '[]'
    
    context = {
        'employee': employee,
        'attendance_stats': attendance_stats,
        'leave_stats': leave_stats,
        'task_stats': task_stats,
        'performance_stats': performance_stats,
        'recent_tasks': recent_tasks,
        'notifications': notifications,
        'upcoming_events': upcoming_events,
        'daily_report_submitted': daily_report_submitted,
        'active_projects': active_projects,
        'recent_announcements': recent_announcements,
        'today': today,
        # Required for chart.js script - safely escaped
        'performance_history': performance_history_json,
    }
    
    return render(request, 'dashboard.html', context)

# ============ MANAGER/HR VIEWS ============

@login_required
def award_performance_points(request):
    """Manager/HR view to award daily performance points (returns JSON response, not a template)"""
    user = request.user

    if user.role not in ['manager', 'admin', 'hr']:
        return JsonResponse({'success': False, 'error': "You don't have permission to access this page."}, status=403)

    try:
        employee_profile = user.employee_profile
    except Exception:
        return JsonResponse({'success': False, 'error': 'Employee profile not found.'}, status=400)

    # Get team members
    if user.role == 'manager':
        team_members = Employee.objects.filter(
            manager=user,
            is_active_employee=True
        ).select_related('user', 'department', 'designation')
    else:
        team_members = Employee.objects.filter(
            company=employee_profile.company,
            is_active_employee=True
        ).select_related('user', 'department', 'designation')

    # Handle POST request
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        date_str = request.POST.get('date')
        points = request.POST.get('points')
        feedback = request.POST.get('feedback', '')
        category_id = request.POST.get('category', '')
        on_leave = request.POST.get('on_leave') == 'on'

        try:
            employee = get_object_or_404(Employee, id=employee_id)
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            points_decimal = Decimal(points)

            # Validate points
            if points_decimal < 0 or points_decimal > 10:
                return JsonResponse({'success': False, 'error': 'Points must be between 0 and 10'}, status=400)

            # Get category if provided
            category = None
            if category_id:
                try:
                    category = PerformanceCategory.objects.get(id=category_id, company=employee_profile.company)
                except PerformanceCategory.DoesNotExist:
                    category = None

            # Create or update performance record
            perf, created = PerformancePoint.objects.update_or_create(
                employee=employee,
                date=date,
                defaults={
                    'points': points_decimal,
                    'feedback': feedback,
                    'category': category,
                    'on_leave': on_leave,
                    'awarded_by': user,
                    'updated_by': user
                }
            )

            # Send notification to employee
            Notification.objects.create(
                recipient=employee.user,
                title='Performance Points Awarded',
                body=f'You received {points} points for {date.strftime("%B %d, %Y")}. {feedback[:100]}',
                notif_type='info'
            )

            action = 'updated' if not created else 'awarded'
            return JsonResponse({'success': True, 'message': f'Performance points {action} successfully!'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error: {str(e)}'}, status=400)

    # GET request - Return performance summary as JSON
    selected_date_str = request.GET.get('date', timezone.now().date().isoformat())
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except Exception:
        selected_date = timezone.now().date()

    # Get performance records for selected date
    performance_records = PerformancePoint.objects.filter(
        date=selected_date,
        employee__in=team_members
    ).select_related('employee', 'employee__user')

    # Create a map for quick lookup
    performance_map = {pr.employee.id: pr for pr in performance_records}

    # Get leave records for the date
    leave_records = LeaveRequest.objects.filter(
        employee__in=team_members,
        status='approved',
        start_date__lte=selected_date,
        end_date__gte=selected_date
    ).select_related('employee')

    leave_map = {lr.employee.id: lr for lr in leave_records}

    # Prepare team data
    team_data = []
    for member in team_members:
        perf = performance_map.get(member.id)
        on_leave_val = member.id in leave_map

        # Serialize employee and performance data for JSON
        emp_data = {
            "id": member.id,
            "name": member.user.get_full_name(),
            "email": member.user.email,
            "department": member.department.name if member.department else None,
            "designation": member.designation.title if member.designation else None,
        }
        perf_data = None
        if perf:
            perf_data = {
                'id': perf.id,
                'points': float(perf.points),
                'feedback': perf.feedback,
                'category': perf.category.name if perf.category else None,
                'on_leave': perf.on_leave,
                'awarded_by': perf.awarded_by.get_full_name() if perf.awarded_by else None,
                'updated_by': perf.updated_by.get_full_name() if perf.updated_by else None,
                'date': perf.date.strftime('%Y-%m-%d'),
            }
        leave_info = None
        if on_leave_val:
            leave = leave_map.get(member.id)
            leave_info = {
                'id': leave.id,
                'status': leave.status,
                'start_date': leave.start_date.strftime('%Y-%m-%d'),
                'end_date': leave.end_date.strftime('%Y-%m-%d'),
                'reason': leave.reason,
            }

        team_data.append({
            'employee': emp_data,
            'performance': perf_data,
            'on_leave': on_leave_val,
            'leave_info': leave_info
        })

    # Get performance categories
    categories_qs = PerformanceCategory.objects.filter(
        company=employee_profile.company
    )
    categories = [{"id": cat.id, "name": cat.name} for cat in categories_qs]

    # Statistics
    stats = {
        'total_team': team_members.count(),
        'rated_today': performance_records.count(),
        'pending': team_members.count() - performance_records.count(),
        'avg_points': float(performance_records.aggregate(avg=Avg('points'))['avg'] or 0),
        'on_leave': len(leave_map)
    }

    data = {
        'team_data': team_data,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'categories': categories,
        'stats': stats,
    }

    return JsonResponse({'success': True, 'data': data})



@login_required
@require_http_methods(["GET"])
def performance_history_api(request, employee_id):
    """API endpoint to get employee performance history"""
    user = request.user
    
    if user.role not in ['manager', 'admin', 'hr']:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    try:
        employee = get_object_or_404(Employee, id=employee_id)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get performance records
        records = PerformancePoint.objects.filter(
            employee=employee,
            date__gte=start_date
        ).order_by('date')
        
        data = []
        for record in records:
            data.append({
                'date': record.date.strftime('%Y-%m-%d'),
                'points': float(record.points),
                'rating': record.rating,
                'feedback': record.feedback,
                'category': record.category,
                'on_leave': record.on_leave,
                'awarded_by': record.awarded_by.get_full_name() if record.awarded_by else None
            })
        
        # Calculate stats
        stats = records.aggregate(
            avg=Avg('points'),
            total=Count('id')
        )
        
        return JsonResponse({
            'success': True,
            'data': data,
            'stats': {
                'average': round(stats['avg'] or 0, 2),
                'total_days': stats['total']
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db import transaction
import json


from django.views.decorators.http import require_GET

@login_required
def my_tasks(request):
    """
    Tasks list view with filtering and data for Create/Edit forms.

    Shows all tasks related to the user, including:
      - Tasks in any project the user is a member of.
      - Tasks reported by the user.
      - Tasks assigned to the user.
    """
    from django.db.models import Q

    user = request.user
    try:
        employee = user.employee_profile
        company = employee.company
    except:
        return redirect('employee_dashboard')

    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')

    # Find all projects the employee is a member of
    my_projects = Project.objects.filter(members=employee)

    # Gather all tasks where the user is involved:
    # - the user is the assignee
    # - or the user is the reporter
    # - or the task belongs to a project they're a member of
    # (ensure no duplicates)
    tasks = Task.objects.filter(
        Q(assignee=user) |
        Q(reporter=user) |
        Q(project__in=my_projects)
    ).select_related(
        'project',
        'assignee',
        'reporter',
        'updated_by'
    ).distinct()

    # Apply status filter if provided
    if status_filter and status_filter != 'all':
        tasks = tasks.filter(status=status_filter)

    # Apply priority filter if provided
    if priority_filter and priority_filter != 'all':
        tasks = tasks.filter(priority=priority_filter)

    # Sort by priority (critical, high, medium, low), then due date ascending, then recently created first
    from django.db.models import Case, When, Value, IntegerField
    priority_order = Case(
        When(priority='critical', then=Value(1)),
        When(priority='high', then=Value(2)),
        When(priority='medium', then=Value(3)),
        When(priority='low', then=Value(4)),
        default=Value(5),
        output_field=IntegerField(),
    )
    tasks = tasks.order_by(priority_order, 'due_date', '-created_at')

    # Calculate stats
    total_tasks = tasks.count()
    pending_tasks = tasks.exclude(status='done').count()
    completed_tasks = tasks.filter(status='done').count()

    # Pagination
    paginator = Paginator(tasks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Fetch only ongoing projects for the project filter/list
    my_projects_ongoing = my_projects.filter(status='ongoing')

    # Fetch potential assignees (Employees in the same company)
    potential_assignees = Employee.objects.filter(
        company=company, is_active_employee=True
    ).select_related('user')

    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'total_tasks': total_tasks,
        'pending_tasks': pending_tasks,
        'completed_tasks': completed_tasks,
        'projects': my_projects_ongoing,
        'employees': potential_assignees,
    }


    return render(request, 'tasks.html', context)

@require_GET
@login_required
def api_project_members(request):
    """
    API endpoint to list all users involved in a project (for task creation/assignment UI).
    Returns: List of people (employees) who are project members, with user/avatar info.
    GET param: project_id
    """
    project_id = request.GET.get('project_id')
    if not project_id:
        return JsonResponse({'success': False, 'error': 'project_id is required'}, status=400)
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Project not found'}, status=404)

    members = project.members.select_related('user').all()
    people = []
    for member in members:
        user = member.user
        people.append({
            'employee_id': str(member.id),
            'user_id': str(user.id),
            'full_name': user.get_full_name() or user.username,
            'username': user.username,
            'email': user.email,
            'avatar_url': getattr(user, 'avatar', None).url if hasattr(user, 'avatar') and user.avatar else '',
            'is_active': user.is_active,
        })

    return JsonResponse({'success': True, 'people': people})

# ... (Previous API endpoints like bulk_complete_tasks remain unchanged) ...

@login_required
@require_http_methods(["POST"])
def create_task(request):
    """Create a new task and notify relevant people"""
    try:
        user = request.user
        data = json.loads(request.body)
        
        # Validation
        title = data.get('title', '').strip()
        if not title:
            return JsonResponse({'success': False, 'error': 'Title is required'}, status=400)

        # Get project_id and assignee_id (handle both old and new field names for backward compatibility)
        project_id = data.get('project_id') or data.get('project')
        assignee_id = data.get('assignee_id') or data.get('assignee')
        
        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
                # Verify user has access to this project
                try:
                    employee = user.employee_profile
                    if not project.members.filter(id=employee.id).exists() and project.company != employee.company:
                        return JsonResponse({'success': False, 'error': 'You do not have access to this project'}, status=403)
                except:
                    pass
            except Project.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Project not found'}, status=404)
            
        assignee = None
        if assignee_id:
            try:
                assignee = User.objects.get(id=assignee_id)
                # Verify assignee is in same company
                try:
                    employee = user.employee_profile
                    assignee_employee = assignee.employee_profile
                    if assignee_employee.company != employee.company:
                        return JsonResponse({'success': False, 'error': 'Assignee must be from the same company'}, status=400)
                except:
                    pass
            except User.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Assignee not found'}, status=404)

        # Parse Date
        due_date = None
        if data.get('due_date'):
            try:
                due_date = datetime.strptime(data.get('due_date'), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Invalid date format'}, status=400)

        # Validate priority
        valid_priorities = ['low', 'medium', 'high', 'critical']
        priority = data.get('priority', 'medium')
        if priority not in valid_priorities:
            priority = 'medium'

        # Validate estimate_hours
        estimate_hours = None
        if data.get('estimate_hours'):
            try:
                estimate_hours = float(data.get('estimate_hours'))
                if estimate_hours < 0:
                    return JsonResponse({'success': False, 'error': 'Estimate hours must be positive'}, status=400)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Invalid estimate hours'}, status=400)

        with transaction.atomic():
            # 1. Create Task
            task = Task.objects.create(
                title=title,
                description=data.get('description', '').strip(),
                project=project,
                assignee=assignee,
                reporter=user,
                priority=priority,
                status='todo',
                estimate_hours=estimate_hours,
                due_date=due_date,
                created_by=user,
                updated_by=user
            )

            # 2. Notifications Logic (Jira-style)
            recipients = set()
            
            # Notify Assignee
            if assignee and assignee != user:
                recipients.add(assignee)
            
            # Notify Project Members (optional: implies transparency)
            if project:
                for member in project.members.all():
                    if member.user != user and member.user != assignee:
                        recipients.add(member.user)

            # Create Notifications
            notif_body = f"New task assigned/created in {project.name if project else 'General'}: {task.title}"
            for recipient in recipients:
                Notification.objects.create(
                    recipient=recipient,
                    title="New Task Assigned",
                    body=notif_body,
                    notif_type='info',
                    created_by=user
                )

        return JsonResponse({
            'success': True,
            'message': 'Task created successfully',
            'task': {
                'id': str(task.id),
                'title': task.title,
                'status': task.status,
                'assignee': task.assignee.get_full_name() if task.assignee else None,
                'project': task.project.name if task.project else None
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Error creating task: {error_msg}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': 'An error occurred while creating the task. Please try again.'}, status=500)


@login_required
@require_http_methods(["POST"])
def edit_task(request, task_id):
    """Edit existing task details"""
    try:
        user = request.user
        task = get_object_or_404(Task, id=task_id)
        
        # Permission check: Reporter, Assignee, or Manager/Admin can edit
        # For simplicity here, we allow if user is related to task or company admin
        if task.reporter != user and task.assignee != user and user.role not in ['admin', 'manager']:
             return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

        data = json.loads(request.body)
        
        with transaction.atomic():
            # Update fields
            if 'title' in data: task.title = data['title']
            if 'description' in data: task.description = data['description']
            if 'priority' in data: task.priority = data['priority']
            if 'estimate_hours' in data: task.estimate_hours = data['estimate_hours'] or None
            
            if 'project_id' in data:
                task.project = get_object_or_404(Project, id=data['project_id']) if data['project_id'] else None
            
            if 'assignee_id' in data:
                old_assignee = task.assignee
                new_assignee = get_object_or_404(User, id=data['assignee_id']) if data['assignee_id'] else None
                task.assignee = new_assignee
                
                # Notify new assignee
                if new_assignee and new_assignee != user and new_assignee != old_assignee:
                    Notification.objects.create(
                        recipient=new_assignee,
                        title="Task Re-assigned",
                        body=f"You have been assigned to task: {task.title}",
                        notif_type='info'
                    )

            if 'due_date' in data:
                 task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data['due_date'] else None

            task.updated_by = user
            task.save()
            
            # Notify Reporter of update if someone else edited it
            if task.reporter and task.reporter != user:
                 Notification.objects.create(
                    recipient=task.reporter,
                    title="Task Updated",
                    body=f"Task '{task.title}' was updated by {user.get_full_name()}",
                    notif_type='info'
                )

        return JsonResponse({'success': True, 'message': 'Task updated successfully'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ==================== API ENDPOINTS ====================

@login_required
@require_http_methods(["POST"])
def bulk_complete_tasks(request):
    """Complete multiple tasks at once"""
    try:
        user = request.user
        data = json.loads(request.body)
        task_ids = data.get('task_ids', [])
        
        if not task_ids:
            return JsonResponse({
                'success': False,
                'error': 'No tasks selected.'
            }, status=400)
        
        # Get tasks that belong to user and are not already done
        tasks = Task.objects.filter(
            id__in=task_ids,
            assignee=user
        ).exclude(status='done')
        
        if not tasks.exists():
            return JsonResponse({
                'success': False,
                'error': 'No valid tasks to complete.'
            }, status=400)
        
        completed_count = 0
        with transaction.atomic():
            for task in tasks:
                task.status = 'done'
                task.updated_by = user
                task.save(update_fields=['status', 'updated_by', 'updated_at'])
                completed_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'{completed_count} task(s) completed successfully!',
            'completed_count': completed_count
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while completing tasks.'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def update_task_status(request, task_id):
    """Update task status with full control"""
    try:
        user = request.user
        
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Task not found.'
            }, status=404)
        
        # Permission check: Only assignee or reporter can update status
        if task.assignee != user and task.reporter != user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to update this task.'
            }, status=403)
        
        # Parse request data
        data = json.loads(request.body)
        new_status = data.get('status')
        
        # Validate status
        valid_statuses = ['todo', 'in_progress', 'review', 'done', 'blocked']
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'error': 'Invalid status.'
            }, status=400)
        
        with transaction.atomic():
            task.status = new_status
            task.updated_by = user
            task.save(update_fields=['status', 'updated_by', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': f'Task status updated to {new_status.replace("_", " ").title()}',
            'new_status': new_status,
            'status_display': task.get_status_display()
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating task status.'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def task_details_api(request, task_id):
    """Get detailed task information"""
    try:
        user = request.user

        try:
            task = Task.objects.select_related(
                'project',
                'assignee',
                'reporter',
                'updated_by'
            ).get(id=task_id)
        except Task.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Task not found.'
            }, status=404)

        # Check if user is assignee, reporter, or project member
        is_assignee = (task.assignee == user)
        is_reporter = (task.reporter == user)
        is_project_member = False

        # Only check project members if there is a project set
        if task.project and hasattr(task.project, 'members'):
            try:
                employee = user.employee_profile
                is_project_member = task.project.members.filter(id=employee.id).exists()
            except:
                pass

        # Allow access if user is assignee, reporter, or project member
        if not (is_assignee or is_reporter or is_project_member):
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to view this task.'
            }, status=403)

        return JsonResponse({
            'success': True,
            'task': {
                'id': str(task.id),
                'title': task.title,
                'description': task.description or '',
                'status': task.status,
                'status_display': task.get_status_display(),
                'priority': task.priority,
                'priority_display': task.get_priority_display(),
                'project': task.project.name if task.project else None,
                'project_id': str(task.project.id) if task.project else None,
                'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else None,
                'due_date_formatted': task.due_date.strftime('%b %d, %Y') if task.due_date else None,
                'assignee': task.assignee.get_full_name() if task.assignee else None,
                'assignee_email': task.assignee.email if task.assignee else None,
                'reporter': task.reporter.get_full_name() if task.reporter else None,
                'reporter_email': task.reporter.email if task.reporter else None,
                'created_at': task.created_at.strftime('%b %d, %Y %I:%M %p'),
                'updated_at': task.updated_at.strftime('%b %d, %Y %I:%M %p'),
                'updated_by': task.updated_by.get_full_name() if task.updated_by else None,
                'estimate_hours': float(task.estimate_hours) if task.estimate_hours else None,
                'spent_seconds': task.spent_seconds or 0,
                'spent_hours': round((task.spent_seconds or 0) / 3600, 2),
                'is_completed': task.status == 'done',
            }
        })
    
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while fetching task details.'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def edit_task_description(request, task_id):
    """Edit task description"""
    try:
        user = request.user
        
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Task not found.'
            }, status=404)
        
        # Permission check: Reporter, Assignee, or Manager/Admin can edit
        is_assignee = (task.assignee == user)
        is_reporter = (task.reporter == user)
        is_manager = getattr(user, 'role', None) in ['admin', 'manager', 'hr']
        
        if not (is_assignee or is_reporter or is_manager):
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to edit this task.'
            }, status=403)
        
        if task.status == 'done':
            return JsonResponse({
                'success': False,
                'error': 'Cannot edit description of completed tasks.'
            }, status=400)
        
        data = json.loads(request.body)
        new_description = data.get('description', '').strip()
        
        with transaction.atomic():
            task.description = new_description
            task.updated_by = user
            task.save(update_fields=['description', 'updated_by', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': 'Description updated successfully',
            'description': task.description
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating the description.'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def complete_task(request, task_id):
    """Mark task as completed"""
    try:
        user = request.user
        
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Task not found.'
            }, status=404)
        
        # Permission check: Only assignee can complete task
        if task.assignee != user:
            return JsonResponse({
                'success': False,
                'error': 'Only the assignee can complete this task.'
            }, status=403)
        
        if task.status == 'done':
            return JsonResponse({
                'success': False,
                'error': 'Task is already completed.'
            }, status=400)
        
        with transaction.atomic():
            task.status = 'done'
            task.updated_by = user
            task.save(update_fields=['status', 'updated_by', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': 'Task marked as completed!',
            'new_status': 'done',
            'status_display': task.get_status_display()
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while completing the task.'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def reopen_task(request, task_id):
    """Reopen a completed task"""
    try:
        user = request.user
        
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Task not found.'
            }, status=404)
        
        # Permission check: Only assignee or reporter can reopen
        if task.assignee != user and task.reporter != user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to reopen this task.'
            }, status=403)
        
        if task.status != 'done':
            return JsonResponse({
                'success': False,
                'error': 'Only completed tasks can be reopened.'
            }, status=400)
        
        with transaction.atomic():
            task.status = 'in_progress'
            task.updated_by = user
            task.save(update_fields=['status', 'updated_by', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': 'Task reopened successfully!',
            'new_status': 'in_progress',
            'status_display': task.get_status_display()
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while reopening the task.'
        }, status=500)    
    
@login_required
def my_attendance(request):
    """Attendance history view with proper filtering and leave support"""
    employee = request.user.employee_profile
    
    # Get current date
    now = timezone.now()
    
    # Get month and year from request, with proper validation
    try:
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
        
        # Validate month range
        if month < 1 or month > 12:
            month = now.month
        
        # Validate year (reasonable range)
        current_year = now.year
        if year < current_year - 5 or year > current_year + 2:
            year = current_year
            
    except (ValueError, TypeError):
        # If conversion fails, use current month/year
        month = now.month
        year = now.year
    
    # Date range for the month
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, calendar.monthrange(year, month)[1])
    
    # Get attendance records for the selected month
    attendances = Attendance.objects.filter(
        employee=employee,
        date__month=month,
        date__year=year
    ).order_by('-date')
    
    # Get approved leaves for the selected month
    approved_leaves = LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        start_date__lte=end_date.date(),
        end_date__gte=start_date.date()
    )
    
    # Get holidays for the selected month
    holidays = Holiday.objects.filter(
        company=employee.company,
        date__month=month,
        date__year=year
    )
    
    # Calculate statistics
    present_count = attendances.filter(
        login_time__isnull=False,
        logout_time__isnull=False
    ).count()
    
    absent_count = attendances.filter(
        login_time__isnull=True,
        logout_time__isnull=True
    ).count()
    
    half_day_count = attendances.filter(
        login_time__isnull=False,
        logout_time__isnull=True
    ).count()
    
    # Count leave days
    leave_count = 0
    current = start_date
    while current <= end_date:
        current_date = current.date()
        # Check if date falls within any approved leave
        for leave in approved_leaves:
            if leave.start_date <= current_date <= leave.end_date:
                leave_count += 1
                break
        current += timedelta(days=1)
    
    # Calculate total work hours
    total_work_seconds = attendances.aggregate(
        total=Sum('total_work_seconds')
    )['total'] or 0
    
    total_hours = total_work_seconds / 3600 if total_work_seconds else 0
    
    # Calculate attendance rate (exclude weekends, holidays, and approved leaves)
    working_days = 0
    total_working_days = 0
    
    current = start_date
    while current <= end_date:
        current_date = current.date()
        # Check if it's a weekday (0=Monday, 4=Friday, 5=Saturday, 6=Sunday)
        if current.weekday() < 5:  # Monday to Friday
            # Skip if it's a holiday
            if not holidays.filter(date=current_date).exists():
                total_working_days += 1
                
                # Check if there's an attendance record
                attendance_record = attendances.filter(date=current_date).first()
                
                if attendance_record:
                    # If has both login and logout, it's a full day present
                    if attendance_record.login_time and attendance_record.logout_time:
                        working_days += 1
                    # If has only login, it's a half day
                    elif attendance_record.login_time:
                        working_days += 0.5
                else:
                    # Check if employee was on approved leave
                    on_leave = False
                    for leave in approved_leaves:
                        if leave.start_date <= current_date <= leave.end_date:
                            working_days += 1  # Leave counts as present
                            on_leave = True
                            break
                    
                    # If not on leave and no attendance, it's an absent day
                    # (already counted in absent_count)
        
        current += timedelta(days=1)
    
    # Calculate attendance rate
    attendance_rate = round((working_days / total_working_days) * 100) if total_working_days > 0 else 0
    
    # Generate year range for dropdown
    current_year = now.year
    years = list(range(current_year - 5, current_year + 3))
    
    context = {
        'attendances': attendances,
        'approved_leaves': approved_leaves,
        'holidays': holidays,
        'month': month,
        'year': year,
        'years': years,
        'present_count': present_count,
        'absent_count': absent_count,
        'leave_count': int(leave_count),
        'half_day_count': half_day_count,
        'total_hours': round(total_hours, 1),
        'attendance_rate': attendance_rate,
        'total_working_days': total_working_days,
    }
    
    return render(request, 'attendance.html', context)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from datetime import datetime
import json

from dev.models import LeaveRequest, LeaveType

# ==================== PAGE VIEWS ====================

@login_required
def my_leaves(request):
    """Leave management page view"""
    employee = request.user.employee_profile
    
    leaves = LeaveRequest.objects.filter(
        employee=employee
    ).order_by('-created_at').select_related('leave_type', 'approver')
    
    leave_types = LeaveType.objects.filter(company=employee.company)
    
    context = {
        'leaves': leaves,
        'leave_types': leave_types,
    }
    
    return render(request, 'leaves.html', context)


# ==================== API VIEWS ====================

@login_required
@require_http_methods(["POST"])
def create_leave_request(request):
    """Create a new leave request - handles both AJAX and form submission"""
    try:
        employee = request.user.employee_profile
        
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        # Validate required fields
        leave_type_id = data.get('leave_type')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        days = data.get('days')
        reason = data.get('reason', '')

        if not all([leave_type_id, start_date, end_date, days]):
            return JsonResponse({
                'success': False,
                'error': 'Please fill in all required fields.'
            }, status=400)

        # Validate dates
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format.'
            }, status=400)

        if end < start:
            return JsonResponse({
                'success': False,
                'error': 'End date must be after start date.'
            }, status=400)

        # Get leave type
        try:
            leave_type = LeaveType.objects.get(id=leave_type_id, company=employee.company)
        except LeaveType.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid leave type selected.'
            }, status=400)

        # Create leave request
        with transaction.atomic():
            leave_request = LeaveRequest.objects.create(
                employee=employee,
                leave_type=leave_type,
                start_date=start,
                end_date=end,
                days=float(days),
                reason=reason,
                status='pending'
            )

        return redirect('my_leaves')

    except Exception as e:
        print(f"Error creating leave: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def update_leave_request(request, leave_id):
    """Update an existing leave request"""
    try:
        employee = request.user.employee_profile
        
        # Get leave request
        try:
            leave_request = LeaveRequest.objects.get(id=leave_id, employee=employee)
        except LeaveRequest.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Leave request not found.'
            }, status=404)

        # Check if can be edited (only pending leaves)
        if leave_request.status != 'pending':
            return JsonResponse({
                'success': False,
                'error': 'Only pending leave requests can be edited.'
            }, status=400)

        # Parse request data
        # Parse request data (support both JSON + form submit)
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST


        # Validate and update fields
        leave_type_id = data.get('leave_type')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        days = data.get('days')
        reason = data.get('reason', '')

        if not all([leave_type_id, start_date, end_date, days]):
            return JsonResponse({
                'success': False,
                'error': 'Please fill in all required fields.'
            }, status=400)

        # Validate dates
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format.'
            }, status=400)

        if end < start:
            return JsonResponse({
                'success': False,
                'error': 'End date must be after start date.'
            }, status=400)

        # Get leave type
        try:
            leave_type = LeaveType.objects.get(id=leave_type_id, company=employee.company)
        except LeaveType.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid leave type selected.'
            }, status=400)

        # Update leave request
        with transaction.atomic():
            leave_request.leave_type = leave_type
            leave_request.start_date = start
            leave_request.end_date = end
            leave_request.days = float(days)
            leave_request.reason = reason
            leave_request.save(update_fields=['leave_type', 'start_date', 'end_date', 'days', 'reason', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Leave request updated successfully!'
        })

    except Exception as e:
        print(f"Error updating leave: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def cancel_leave_request(request, leave_id):
    """Cancel a leave request"""
    try:
        employee = request.user.employee_profile
        
        # Get leave request
        try:
            leave_request = LeaveRequest.objects.get(id=leave_id, employee=employee)
        except LeaveRequest.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Leave request not found.'
            }, status=404)

        # Check if can be cancelled (only pending leaves)
        if leave_request.status != 'pending':
            return JsonResponse({
                'success': False,
                'error': 'Only pending leave requests can be cancelled.'
            }, status=400)

        # Cancel leave request
        with transaction.atomic():
            leave_request.status = 'cancelled'
            leave_request.save(update_fields=['status', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Leave request cancelled successfully!'
        })

    except Exception as e:
        print(f"Error cancelling leave: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.forms import modelform_factory, ModelForm
from django.forms import ModelMultipleChoiceField, CheckboxSelectMultiple
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from .models import Project, ProjectMembership, Employee, Client
from django.db.models import Count, Q

class ProjectForm(ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'code', 'description', 'client', 'start_date', 'end_date', 'status', 'budget', 'progress_percent']
    
    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company:
            self.fields['client'].queryset = Client.objects.filter(company=company, is_deleted=False).order_by('name')
            self.fields['client'].empty_label = "Select a client"

class ProjectAssignForm(ModelForm):
    members = ModelMultipleChoiceField(
        queryset=Employee.objects.none(),
        required=False,
        widget=CheckboxSelectMultiple
    )
    class Meta:
        model = Project
        fields = []  # members only via a separate form

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company')
        super().__init__(*args, **kwargs)
        self.fields['members'].queryset = Employee.objects.filter(company=company).select_related('user').order_by('user__first_name', 'user__last_name')

@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    employee = request.user.employee_profile
    company = employee.company
    clients = Client.objects.filter(company=company, is_deleted=False).order_by('name')
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, company=company)
        assign_form = ProjectAssignForm(request.POST, company=company)
        if form.is_valid() and assign_form.is_valid():
            try:
                with transaction.atomic():
                    project = form.save(commit=False)
                    project.company = company
                    project.created_by = request.user
                    project.save()
                    ProjectMembership.objects.get_or_create(project=project, employee=employee)
                    selected_members = assign_form.cleaned_data.get('members', [])
                    for member in selected_members:
                        if member.id != employee.id:
                            ProjectMembership.objects.get_or_create(project=project, employee=member)
                
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({'success': True, 'message': 'Project created successfully.'})
                messages.success(request, 'Project created successfully.')
                return redirect('my_projects')
            except Exception as e:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({'success': False, 'error': str(e), 'form_html': None}, status=400)
                messages.error(request, f'Error creating project: {str(e)}')
        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                from django.template.loader import render_to_string
                form_html = render_to_string('project_form_partial.html', {
                    'form': form,
                    'assign_form': assign_form,
                    'is_create': True
                }, request=request)
                return JsonResponse({'success': False, 'form_html': form_html})
    else:
        form = ProjectForm(company=company)
        assign_form = ProjectAssignForm(company=company)
    
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        from django.template.loader import render_to_string
        form_html = render_to_string('project_form_partial.html', {
            'form': form,
            'assign_form': assign_form,
            'is_create': True
        }, request=request)
        return HttpResponse(form_html)
    
    return render(request, 'project_create.html', {
        'form': form,
        'assign_form': assign_form,
        'clients': clients
    })

@login_required
@require_http_methods(["GET", "POST"])
def project_update(request, project_id):
    employee = request.user.employee_profile
    company = employee.company
    user = request.user
    
    try:
        project = Project.objects.get(id=project_id, company=company, is_deleted=False)
    except Project.DoesNotExist:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({'success': False, 'error': 'Project not found.'}, status=404)
        messages.error(request, 'Project not found.')
        return redirect('my_projects')
    
    creator_membership = ProjectMembership.objects.filter(project=project).order_by('joined_at').first()
    creator_employee = creator_membership.employee if creator_membership else None
    creator_user = creator_employee.user if creator_employee else None
    
    can_edit = (
        user.role in ['admin', 'hr'] or
        (user.role == 'manager' and employee in project.members.all()) or
        (creator_user and creator_user.id == user.id)
    )
    
    if not can_edit:
        error_msg = "You don't have permission to edit this project."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({'success': False, 'error': error_msg}, status=403)
        messages.error(request, error_msg)
        return redirect('my_projects')
    
    clients = Client.objects.filter(company=company, is_deleted=False).order_by('name')
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project, company=company)
        assign_form = ProjectAssignForm(request.POST, company=company)
        if form.is_valid() and assign_form.is_valid():
            try:
                with transaction.atomic():
                    project = form.save()
                    project.updated_by = user
                    project.save(update_fields=['updated_by'])
                    
                    input_members = assign_form.cleaned_data.get('members', [])
                    current_members = set(project.members.all())
                    new_members = set(input_members)
                    
                    if creator_employee:
                        new_members.add(creator_employee)
                    
                    for mem in current_members - new_members:
                        if mem.id != creator_employee.id:
                            ProjectMembership.objects.filter(project=project, employee=mem).delete()
                    
                    for mem in new_members - current_members:
                        ProjectMembership.objects.get_or_create(project=project, employee=mem)
                
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({'success': True, 'message': 'Project updated successfully.'})
                messages.success(request, 'Project updated successfully.')
                return redirect('my_projects')
            except Exception as e:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    from django.template.loader import render_to_string
                    form_html = render_to_string('project_form_partial.html', {
                        'form': form,
                        'assign_form': assign_form,
                        'project': project,
                        'is_create': False
                    }, request=request)
                    return JsonResponse({'success': False, 'error': str(e), 'form_html': form_html}, status=400)
                messages.error(request, f'Error updating project: {str(e)}')
        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                from django.template.loader import render_to_string
                form_html = render_to_string('project_form_partial.html', {
                    'form': form,
                    'assign_form': assign_form,
                    'is_create': False
                }, request=request)
                return JsonResponse({'success': False, 'form_html': form_html})
    else:
        form = ProjectForm(instance=project, company=company)
        current_members = project.members.exclude(id=creator_employee.id) if creator_employee else project.members.all()
        assign_form = ProjectAssignForm(company=company, initial={'members': current_members})
    
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        from django.template.loader import render_to_string
        form_html = render_to_string('project_form_partial.html', {
            'form': form,
            'assign_form': assign_form,
            'project': project,
            'is_create': False
        }, request=request)
        return HttpResponse(form_html)
    
    return render(request, 'project_update.html', {
        'form': form,
        'assign_form': assign_form,
        'project': project,
        'clients': clients
    })

@login_required
@require_http_methods(["POST"])
def project_delete(request, project_id):
    employee = request.user.employee_profile
    company = employee.company
    user = request.user
    
    try:
        project = Project.objects.get(id=project_id, company=company, is_deleted=False)
    except Project.DoesNotExist:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({'success': False, 'error': 'Project not found.'}, status=404)
        messages.error(request, 'Project not found.')
        return redirect('my_projects')
    
    creator_membership = ProjectMembership.objects.filter(project=project).order_by('joined_at').first()
    creator_employee = creator_membership.employee if creator_membership else None
    creator_user = creator_employee.user if creator_employee else None
    
    can_delete = (
        user.role in ['admin', 'hr'] or
        (user.role == 'manager' and employee in project.members.all()) or
        (creator_user and creator_user.id == user.id)
    )
    
    if not can_delete:
        error_msg = "You don't have permission to delete this project."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({'success': False, 'error': error_msg}, status=403)
        messages.error(request, error_msg)
        return redirect('my_projects')
    
    try:
        with transaction.atomic():
            project.delete()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({'success': True, 'message': "Project deleted successfully."})
        messages.success(request, "Project deleted successfully.")
    except Exception as e:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({'success': False, 'error': f"Could not delete project: {str(e)}"}, status=500)
        messages.error(request, f"Could not delete project: {str(e)}")
    
    return redirect('my_projects')

@login_required
@require_http_methods(["GET"])
def my_projects(request):
    """Projects listing & team assignment - professional dashboard"""
    employee = request.user.employee_profile
    projects_qs = (
        employee.projects
        .select_related('client', 'created_by')
        .prefetch_related('members')
        .annotate(
            tasks_count=Count('tasks'),
            completed_tasks=Count('tasks', filter=Q(tasks__status='done')),
        )
        .order_by('-created_at')
    )
    filter_status = request.GET.get('status')
    if filter_status:
        projects_qs = projects_qs.filter(status=filter_status)

    projects = []
    user = request.user
    employee = request.user.employee_profile
    
    for project in projects_qs:
        creator_membership = ProjectMembership.objects.filter(project=project).order_by('joined_at').first()
        creator_employee = creator_membership.employee if creator_membership else None
        creator_user = creator_employee.user if creator_employee else None
        
        project.creator_id = creator_user.id if creator_user else None
        project.can_edit = (
            user.role in ['admin', 'hr'] or
            (user.role == 'manager' and employee in project.members.all()) or
            (creator_user and creator_user.id == user.id)
        )
        project.can_delete = project.can_edit
        projects.append(project)

    # Stats for bar
    stats = {
        "all": len(projects),
        "planning": sum(1 for p in projects if p.status == 'planning'),
        "ongoing": sum(1 for p in projects if p.status == 'ongoing'),
        "on_hold": sum(1 for p in projects if p.status == 'on_hold'),
        "completed": sum(1 for p in projects if p.status == 'completed'),
        "cancelled": sum(1 for p in projects if p.status == 'cancelled'),
    }
    context = {
        'projects': projects,
        'stats': stats,
        'filter_status': filter_status or "",
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

@login_required
def manager_dashboard(request):
    """
    Manager dashboard - Exactly provides all required data for dev/templates/manager_dashboard.html.
    No FieldError: Only uses fields that exist in @dev/models.py.
    """
    from django.db.models import Q
    import datetime

    user = request.user
    if user.role not in ['manager', 'admin', 'hr']:
        return redirect('employee_dashboard')

    # --- 1. TEAM MEMBERS (DIRECT REPORTS) ---
    team_members_qs = Employee.objects.filter(
        manager=user,
        is_deleted=False
    ).select_related('user', 'department', 'designation')
    team_members = []
    team_member_ids = []
    team_member_user_ids = []

    for employee in team_members_qs:
        u = employee.user
        initials = (
            (u.first_name[:1] if u.first_name else '') +
            (u.last_name[:1] if u.last_name else '')
        ) or u.username[:2]
        completed_count = Task.objects.filter(assignee=u, status='done').count()
        pending_count = Task.objects.filter(assignee=u, status__in=['todo', 'in_progress', 'review']).count()
        team_members.append({
            "employee": employee,
            "user": u,
            "id": employee.id,
            "name": u.get_full_name() if hasattr(u, "get_full_name") else u.username,
            "email": u.email,
            "designation": employee.designation.title if employee.designation else '',
            "department": employee.department.name if employee.department else '',
            "is_active": employee.is_active_employee,
            "avatar": getattr(u, "avatar", None),
            "date_of_joining": employee.date_of_joining,
            "completed_tasks_count": completed_count,
            "pending_tasks_count": pending_count,
            "initials": initials,
        })
        team_member_ids.append(employee.id)
        team_member_user_ids.append(u.id)

    total_team_members = len(team_members)
    today = timezone.localdate()

    # --- 2. TEAM ATTENDANCE (TODAY) ---
    attendance_qs = Attendance.objects.filter(
        employee_id__in=team_member_ids,
        date=today
    ).select_related('employee__user')
    present_count = attendance_qs.exclude(login_time__isnull=True).count()
    absent_count = total_team_members - present_count
    team_attendance = []
    for att in attendance_qs:
        u = att.employee.user
        team_attendance.append({
            "employee": att.employee,
            "user": u,
            "employee_id": att.employee.id,
            "employee_name": u.get_full_name() if hasattr(u, "get_full_name") else u.username,
            "avatar": getattr(u, "avatar", None),
            "check_in": att.login_time,
            "check_out": att.logout_time,
            "total_work_seconds": getattr(att, "total_work_seconds", None),
            "status": "Online" if att.login_time and not att.logout_time else (
                "Offline" if att.logout_time else "Absent"
            ),
            "remarks": att.notes if hasattr(att, "notes") else '',
        })

    # --- 3. PENDING LEAVE REQUESTS (limit 3) ---
    leaves_qs = LeaveRequest.objects.filter(
        employee__id__in=team_member_ids,
        status='pending',
    ).select_related('employee__user', 'leave_type').order_by('-created_at')
    pending_leaves = []
    for leave in leaves_qs[:3]:
        emp = leave.employee
        u = emp.user
        pending_leaves.append({
            "id": leave.id,
            "employee": emp,
            "user": u,
            "employee_id": emp.id,
            "employee_name": u.get_full_name() if hasattr(u, "get_full_name") else u.username,
            "avatar": getattr(u, "avatar", None),
            "leave_type": leave.leave_type.name if leave.leave_type else "",
            "start_date": leave.start_date,
            "end_date": leave.end_date,
            "days": leave.days,
            "reason": leave.reason,
            "created_at": leave.created_at,
            "status": leave.status,
        })
    pending_leaves_count = leaves_qs.count()

    # --- 4. ALL TEAM TASKS ---
    team_tasks_qs = Task.objects.filter(
        assignee__id__in=team_member_user_ids
    ).select_related('assignee')
    team_tasks = []
    for task in team_tasks_qs.order_by('-created_at')[:30]:
        assignee = task.assignee
        assignee_initials = (assignee.first_name[:1] if assignee.first_name else '') + (assignee.last_name[:1] if assignee.last_name else '') \
            or assignee.username[:2]
        team_tasks.append({
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "get_status_display": getattr(task, 'get_status_display', lambda: task.status)(),
            "due_date": task.due_date,
            "priority": getattr(task, 'priority', None),
            "assignee": assignee,
            "assignee_avatar": getattr(assignee, "avatar", None),
            "assignee_initials": assignee_initials,
            "created_at": task.created_at,
        })

    # --- 5. TASKS STATS BAR ---
    task_statuses = ["todo", "in_progress", "review", "done"]
    task_status_counts = {s: team_tasks_qs.filter(status=s).count() for s in task_statuses}
    task_status_counts['total'] = team_tasks_qs.count()
    completed_team_tasks = task_status_counts['done']
    total_team_tasks = task_status_counts['total']
    pending_team_tasks = (
        task_status_counts.get('todo', 0)
        + task_status_counts.get('in_progress', 0)
        + task_status_counts.get('review', 0)
    )

    # --- 6. RECENT ACTIVITIES (not model-based, make something based on join date) ---
    recent_activities = []
    for i, member in enumerate(
        sorted(team_members, key=lambda tm: getattr(tm['user'], 'date_joined', today), reverse=True)[:5]
    ):
        recent_activities.append({
            "user": member['user'],
            "employee": member['employee'],
            "name": member['name'],
            "created_at": getattr(member['user'], 'date_joined', today),
            "activity_type": "completed_task" if i % 2 == 0 else "logged_attendance",
        })

    # --- 7. CHART DATA (Tasks Done & Pending: recent 7 days, by created_at only!) ---
    chart_labels = []
    completed_per_day = []
    pending_per_day = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_label = day.strftime('%a')
        # completed: status=done with updated_at on that date
        completed_count = Task.objects.filter(
            assignee__id__in=team_member_user_ids,
            status='done',
            updated_at__date=day
        ).count() if hasattr(Task, 'updated_at') else 0
        # pending: status in todo/in_progress/review, created that day
        pending_count = Task.objects.filter(
            assignee__id__in=team_member_user_ids,
            status__in=['todo', 'in_progress', 'review'],
            created_at__date=day
        ).count()
        chart_labels.append(day_label)
        completed_per_day.append(completed_count)
        pending_per_day.append(pending_count)

    chart_data = {
        "labels": chart_labels,
        "completed": completed_per_day,
        "pending": pending_per_day,
    }

    # --- 8. CONTEXT ---

    context = {
        'team_members': team_members,
        'total_team_members': total_team_members,
        'present_count': present_count,
        'absent_count': absent_count,
        'today': today,

        'team_attendance': team_attendance,

        'pending_leaves': pending_leaves,
        'pending_leaves_count': pending_leaves_count,

        'team_tasks': team_tasks,
        'task_status_counts': task_status_counts,
        'completed_team_tasks': completed_team_tasks,
        'total_team_tasks': total_team_tasks,
        'pending_team_tasks': pending_team_tasks,

        'recent_activities': recent_activities,
        'chart_data': chart_data,
    }
    return render(request, 'manager_dashboard.html', context)

@login_required
def hr_dashboard(request):
    """Dashboard for HR"""
    user = request.user
    
    if user.role not in ['hr', 'admin']:
        return redirect('employee_dashboard')
    
    company = user.employee_profile.company
    
    total_employees = Employee.objects.filter(company=company, is_active_employee=True).count()
    
    recent_hires = Employee.objects.filter(
        company=company,
        date_of_joining__gte=timezone.now().date() - timedelta(days=30)
    )
    
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
    if user.role not in ['hr', 'admin']:
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    try:
        company = user.employee_profile.company
    except:
        return redirect('employee_dashboard')
    
    employees = Employee.objects.filter(
        company=company,
        is_deleted=False
    ).select_related('user', 'department', 'designation', 'manager')
    
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

    employees = employees.order_by('-created_at')
    
    # Paginate first
    paginator = Paginator(employees, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Efficiently fetch latest performance for all employees on this page
    from dev.models import PerformancePoint
    
    # Get employee IDs from current page
    employee_ids = [emp.id for emp in page_obj]
    
    # Fetch latest performance for each employee (one query per employee, but only for current page)
    # This is acceptable since we're only querying 20 employees max per page
    latest_perf_map = {}
    if employee_ids:
        # Use a more efficient approach: get all performances and group by employee
        all_perfs = PerformancePoint.objects.filter(
            employee_id__in=employee_ids
        ).select_related('category', 'awarded_by').order_by('employee_id', '-date')
        
        # Group by employee and take the first (latest) for each
        seen_employees = set()
        for perf in all_perfs:
            if perf.employee_id not in seen_employees:
                latest_perf_map[perf.employee_id] = perf
                seen_employees.add(perf.employee_id)
                if len(seen_employees) == len(employee_ids):
                    break
    
    # Attach latest performance to each employee
    for employee in page_obj:
        employee.latest_performance = latest_perf_map.get(employee.id)
    
    departments = Department.objects.filter(company=company)
    
    # Get performance categories for the award modal
    from dev.models import PerformanceCategory
    performance_categories = PerformanceCategory.objects.filter(company=company).order_by('name')
    
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
        'performance_categories': performance_categories,
    }
    
    return render(request, 'all_employees.html', context)




@login_required
def profile(request):
    """User profile view and edit"""
    user = request.user

    try:
        employee = user.employee_profile
    except:
        return redirect('employee_dashboard')

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        
        phone = request.POST.get('phone')
        if hasattr(user, 'phone') and phone is not None:
            user.phone = phone

        if hasattr(user, 'avatar') and 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']

        user.save()
        employee.emergency_contact = request.POST.get('emergency_contact', employee.emergency_contact)
        employee.address = request.POST.get('address', employee.address)
        employee.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    recent_tasks = Task.objects.filter(assignee=user).order_by('-updated_at')[:5]
    recent_leaves = LeaveRequest.objects.filter(employee=employee).order_by('-created_at')[:5]

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


@login_required
def documents(request):
    """Company documents and employee documents"""
    user = request.user
    
    try:
        employee = user.employee_profile
        company = employee.company
    except:
        return redirect('employee_dashboard')
    
    company_documents = Document.objects.filter(
        company=company,
        is_deleted=False
    ).order_by('-created_at')
    
    tag_filter = request.GET.get('tag', '')
    if tag_filter:
        company_documents = company_documents.filter(tags__contains=[tag_filter])

    search_query = request.GET.get('search', '')
    if search_query:
        company_documents = company_documents.filter(
            Q(title__icontains=search_query)
        )

    paginator = Paginator(company_documents, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

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

    articles = KBArticle.objects.filter(
        company=company,
        is_deleted=False
    )
    
    if user.role not in ['admin', 'hr']:
        articles = articles.filter(is_public=True)
    
    search_query = request.GET.get('search', '')
    if search_query:
        articles = articles.filter(
            Q(title__icontains=search_query) |
            Q(body__icontains=search_query)
        )
    
    articles = articles.order_by('-created_at')

    paginator = Paginator(articles, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

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

    all_courses = Course.objects.filter(
        company=company,
        is_deleted=False
    )
    my_enrollments = Enrollment.objects.filter(
        user=user,
        is_deleted=False
    ).select_related('course')
    
    enrolled_course_ids = my_enrollments.values_list('course_id', flat=True)
    available_courses = all_courses.exclude(id__in=enrolled_course_ids)
    
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


@login_required
def tickets(request):
    """Support tickets system"""
    user = request.user
    
    try:
        employee = user.employee_profile
        company = employee.company
    except:
        return redirect('employee_dashboard')
    
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

    status_filter = request.GET.get('status', 'all')
    
    if user.role in ['admin', 'hr']:
        tickets_list = Ticket.objects.filter(company=company)
    else:
        tickets_list = Ticket.objects.filter(
            Q(reporter=user) | Q(assignee=user)
        )
    
    if status_filter != 'all':
        tickets_list = tickets_list.filter(status=status_filter)
    
    tickets_list = tickets_list.order_by('-created_at')
    
    paginator = Paginator(tickets_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
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


@login_required
def all_notifications(request):
    """All notifications page"""
    user = request.user

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
    
    filter_type = request.GET.get('type', 'all')
    
    notifications = Notification.objects.filter(recipient=user)
    
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_type != 'all':
        notifications = notifications.filter(notif_type=filter_type)
    
    notifications = notifications.order_by('-created_at')

    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
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

    attendance = Attendance.objects.filter(employee=employee, date=today).first()
    
    if attendance and attendance.login_time:
        return JsonResponse({
            'success': False,
            'error': 'Already logged in today',
            'login_time': attendance.login_time.strftime('%I:%M %p')
        })

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

    attendance.logout_time = timezone.now()

    time_diff = attendance.logout_time - attendance.login_time
    attendance.total_work_seconds = int(time_diff.total_seconds())
    attendance.save()
    
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
    
    if user.role == 'manager':
        team_members = Employee.objects.filter(manager=user, is_active_employee=True)
    else:
        team_members = Employee.objects.filter(company=employee.company, is_active_employee=True)
    
    date_str = request.GET.get('date', timezone.now().date().isoformat())
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        selected_date = timezone.now().date()
    
    attendance_records = Attendance.objects.filter(
        employee__in=team_members,
        date=selected_date
    ).select_related('employee', 'employee__user')

    attendance_map = {att.employee.id: att for att in attendance_records}
    
    team_data = []
    for member in team_members:
        att = attendance_map.get(member.id)
        team_data.append({
            'employee': member,
            'attendance': att,
            'status': 'present' if (att and att.login_time) else 'absent',
            'hours_worked': (att.total_work_seconds / 3600) if (att and att.total_work_seconds) else 0,
        })
    
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
    
    return render(request, 'team_attendance.html', context)


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

    if request.method == 'POST':
        leave_id = request.POST.get('leave_id')
        action = request.POST.get('action') 
        
        leave_request = get_object_or_404(LeaveRequest, id=leave_id)
        
        if action == 'approve':
            leave_request.status = 'approved'
            leave_request.approver = user
            leave_request.save()
            
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
            
            Notification.objects.create(
                recipient=leave_request.employee.user,
                title='Leave Request Rejected',
                body=f'Your leave request from {leave_request.start_date} to {leave_request.end_date} has been rejected.',
                notif_type='warning'
            )
            
            messages.success(request, 'Leave request rejected!')
        
        return redirect('approve_leaves')
    
    if user.role == 'manager':
        team_members = Employee.objects.filter(manager=user, is_active_employee=True)
    else:
        team_members = Employee.objects.filter(company=employee.company, is_active_employee=True)
    
    status_filter = request.GET.get('status', 'pending')
    
    leave_requests = LeaveRequest.objects.filter(
        employee__in=team_members
    ).select_related('employee', 'employee__user', 'leave_type', 'approver')
    
    if status_filter != 'all':
        leave_requests = leave_requests.filter(status=status_filter)
    
    leave_requests = leave_requests.order_by('-created_at')
    paginator = Paginator(leave_requests, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
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

def calculate_attendance_rate(employee):
    """Calculate attendance percentage"""
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    total_working_days = 22 
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