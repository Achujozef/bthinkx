from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    StudentProfile,
    CoordinatorProfile,
    Course,
    WeeklyTopic,
    Session,
    Enrollment,
    ReviewPerformance
)
admin.site.register(User)
# ----------------------------
# Custom User Admin
# ----------------------------
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2', 'is_active', 'is_staff')}
        ),
    )

# ----------------------------
# Student Profile Admin
# ----------------------------
@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'guardian_name', 'guardian_phone', 'date_of_birth', 'blood_group', 'admission_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'guardian_name', 'phone')
    list_filter = ('blood_group',)
    ordering = ('user__username',)

# ----------------------------
# Coordinator Profile Admin
# ----------------------------
@admin.register(CoordinatorProfile)
class CoordinatorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'designation', 'phone')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'designation', 'phone')
    ordering = ('user__username',)

# ----------------------------
# Course Admin
# ----------------------------
class WeeklyTopicInline(admin.TabularInline):
    model = WeeklyTopic
    extra = 1

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'duration_weeks')
    search_fields = ('title', 'description')
    filter_horizontal = ('coordinators',)
    inlines = [WeeklyTopicInline]

# ----------------------------
# Weekly Topic Admin
# ----------------------------
class SessionInline(admin.TabularInline):
    model = Session
    extra = 1

@admin.register(WeeklyTopic)
class WeeklyTopicAdmin(admin.ModelAdmin):
    list_display = ('course', 'week_number', 'title')
    search_fields = ('title', 'course__title')
    inlines = [SessionInline]

# ----------------------------
# Session Admin
# ----------------------------
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'week', 'session_type', 'status')
    list_filter = ('session_type', 'status')
    search_fields = ('name', 'week__course__title')

# ----------------------------
# Enrollment Admin
# ----------------------------
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_on', 'is_active')
    list_filter = ('is_active', 'course')
    search_fields = ('student__user__username', 'course__title')

# ----------------------------
# Review Performance Admin
# ----------------------------
@admin.register(ReviewPerformance)
class ReviewPerformanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'theory_marks', 'practical_marks', 'total_marks', 'status')
    list_filter = ('status', 'session__week__course')
    search_fields = ('student__user__username', 'session__name')
