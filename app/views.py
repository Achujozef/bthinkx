from django.shortcuts import render
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import User, Course


def home(request):
    return render(request, 'index.html')


def edtech(request):
    return render(request, 'bthinkxedtech.html')


def dev(request):
    return render(request, 'bthinkxdev.html')

@csrf_exempt
def submit_contact_form(request):
    if request.method == 'POST':
        data = {
            "Name": request.POST.get('name'),
            "Email": request.POST.get('email'),
            "Phone": request.POST.get('phone'),
            "Education": request.POST.get('education'),
            "Experience": request.POST.get('experience'),
            "Place": request.POST.get('place'),
            "Reason": request.POST.get('reason'),
        }

        # Connect to Google Sheets
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('bthinkx-d17e6d002985.json', scope)
        client = gspread.authorize(creds)

        # Open sheet and append data
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1TbW3WBVmlhARWYdf6LN7_wpSq0ir1YYZ4oOQFV9-xsg/edit")
        worksheet = sheet.sheet1
        worksheet.append_row(list(data.values()))

        return redirect('/')  # Or success page
    
def roadmap_view(request):
    return render(request, 'roadmap.html')



def user_login(request):
    if request.user.is_authenticated:
        return redirect('student_dashboard')  # Redirect if already logged in

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # Redirect based on role
            if user.role == 'student':
                return redirect('student_dashboard')
            elif user.role == 'coordinator':
                return redirect('coordinator_dashboard')
            elif user.role == 'manager':
                return redirect('manager_dashboard')
            else:
                messages.error(request, 'User role not assigned.')
                logout(request)
                return redirect('login')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')


@login_required
def student_dashboard(request):
    # Get courses and reviews dynamically
    enrollments = request.user.studentprofile.enrollments.select_related('course').all()
    reviews = request.user.studentprofile.reviews.all()
    
    context = {
        'enrollments': enrollments,
        'reviews': reviews
    }
    return render(request, 'student_dashboard.html', context)

@login_required
def coordinator_dashboard(request):
    # Courses assigned
    courses = Course.objects.filter(coordinators=request.user)
    
    context = {
        'courses': courses,
    }
    return render(request, 'coordinator_dashboard.html', context)

@login_required
def manager_dashboard(request):
    students_count = User.objects.filter(role='student').count()
    coordinators_count = User.objects.filter(role='coordinator').count()
    courses_count = Course.objects.count()
    
    context = {
        'students_count': students_count,
        'coordinators_count': coordinators_count,
        'courses_count': courses_count
    }
    return render(request, 'manager_dashboard.html', context)



def user_logout(request):
    logout(request)
    return redirect('login')