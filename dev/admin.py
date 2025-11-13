from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    User,
    Company,
    Department,
    Designation,
    Employee,
    Attendance,
    LeaveRequest,
    Holiday,
    Task,
    Project,
    DailyReport,
    Notification,
    CalendarEvent,
    Client,
    ProjectMembership,
    TaskTimeLog,
    Invoice,
    Payment,
    Expense,
    Course,
    Enrollment,
    Review,
    Ticket,
    TicketComment,
    ActionLog,
    Announcement,
    PolicyDocument,
    GroupPermission,
    LeaveType,
    Lead,
    Quotation,
    Campaign,

)

# --------------------------------------------------------------------
#  Generic Admin Configurations
# --------------------------------------------------------------------
class BaseAdmin(admin.ModelAdmin):
    """Common admin base for most models"""
    list_per_page = 25
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    search_fields = ("id",)
    list_filter = ("is_deleted",)
    ordering = ("-created_at",)

    def get_queryset(self, request):
        # include soft-deleted objects for superusers only
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(is_deleted=False)

    def soft_delete(self, request, queryset):
        for obj in queryset:
            obj.delete()
        self.message_user(request, f"{queryset.count()} record(s) soft deleted.")
    soft_delete.short_description = "Soft delete selected records"

    actions = ["soft_delete"]

# --------------------------------------------------------------------
#  User & Company
# --------------------------------------------------------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin, BaseAdmin):
    list_display = ("username", "email", "role", "is_active", "is_verified", "created_at")
    list_filter = ("role", "is_active", "is_verified")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "phone", "avatar")}),
        ("Permissions", {"fields": ("role", "is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Meta", {"fields": ("is_verified", "preferences", "created_at", "updated_at")}),
    )

@admin.register(Company)
class CompanyAdmin(BaseAdmin):
    list_display = ("name", "email", "phone", "website", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")

# --------------------------------------------------------------------
#  Employees & Departments
# --------------------------------------------------------------------
@admin.register(Department)
class DepartmentAdmin(BaseAdmin):
    list_display = ("name", "company", "lead")
    search_fields = ("name", "company__name", "lead__username")

@admin.register(Designation)
class DesignationAdmin(BaseAdmin):
    list_display = ("title", "company", "level")
    search_fields = ("title",)

@admin.register(Employee)
class EmployeeAdmin(BaseAdmin):
    list_display = ("user", "company", "department", "designation", "manager", "is_active_employee")
    list_filter = ("company", "department", "designation", "is_active_employee")
    search_fields = ("user__username", "user__email", "employee_code")

# --------------------------------------------------------------------
#  Attendance, Leave & Holidays
# --------------------------------------------------------------------
@admin.register(Attendance)
class AttendanceAdmin(BaseAdmin):
    list_display = ("employee", "date", "login_time", "logout_time", "total_work_seconds")
    search_fields = ("employee__user__username",)
    list_filter = ("date", "employee__company")

@admin.register(LeaveRequest)
class LeaveRequestAdmin(BaseAdmin):
    list_display = ("employee", "leave_type", "status", "start_date", "end_date", "days")
    list_filter = ("status", "leave_type__name", "employee__company")
    search_fields = ("employee__user__username", "reason")

@admin.register(Holiday)
class HolidayAdmin(BaseAdmin):
    list_display = ("title", "company", "date")
    list_filter = ("company", "date")
    search_fields = ("title",)

# --------------------------------------------------------------------
#  Project & Task Management
# --------------------------------------------------------------------
@admin.register(Client)
class ClientAdmin(BaseAdmin):
    list_display = ("name", "company", "email", "phone")
    search_fields = ("name", "email", "phone")

class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 1

@admin.register(Project)
class ProjectAdmin(BaseAdmin):
    list_display = ("name", "company", "client", "status", "progress_percent")
    list_filter = ("company", "status")
    search_fields = ("name", "code", "client__name")
    inlines = [ProjectMembershipInline]

@admin.register(Task)
class TaskAdmin(BaseAdmin):
    list_display = ("title", "project", "priority", "status", "assignee", "due_date")
    list_filter = ("priority", "status", "project")
    search_fields = ("title", "description", "assignee__username")

@admin.register(TaskTimeLog)
class TaskTimeLogAdmin(BaseAdmin):
    list_display = ("task", "user", "start_time", "end_time", "duration_seconds")
    list_filter = ("user", "task__project")

# --------------------------------------------------------------------
#  Finance
# --------------------------------------------------------------------
@admin.register(Invoice)
class InvoiceAdmin(BaseAdmin):
    list_display = ("invoice_number", "client", "total", "status", "issue_date", "due_date")
    list_filter = ("status", "issue_date")
    search_fields = ("invoice_number", "client__name")

@admin.register(Payment)
class PaymentAdmin(BaseAdmin):
    list_display = ("invoice", "amount", "method", "paid_on")
    search_fields = ("invoice__invoice_number", "transaction_ref")

@admin.register(Expense)
class ExpenseAdmin(BaseAdmin):
    list_display = ("title", "company", "amount", "date", "category")
    list_filter = ("company", "category")
    search_fields = ("title", "notes")

# --------------------------------------------------------------------
#  Training & Courses
# --------------------------------------------------------------------
@admin.register(Course)
class CourseAdmin(BaseAdmin):
    list_display = ("title", "company", "duration_hours")
    search_fields = ("title", "description")

@admin.register(Enrollment)
class EnrollmentAdmin(BaseAdmin):
    list_display = ("course", "user", "status", "progress_percent")
    list_filter = ("status",)

# --------------------------------------------------------------------
#  Reviews & Performance
# --------------------------------------------------------------------
@admin.register(Review)
class ReviewAdmin(BaseAdmin):
    list_display = ("employee", "period", "reviewer", "score")
    list_filter = ("period",)
    search_fields = ("employee__user__username", "reviewer__username")

# --------------------------------------------------------------------
#  Tickets & Support
# --------------------------------------------------------------------
@admin.register(Ticket)
class TicketAdmin(BaseAdmin):
    list_display = ("title", "company", "priority", "status", "reporter", "assignee")
    list_filter = ("status", "priority", "company")
    search_fields = ("title", "description")

@admin.register(TicketComment)
class TicketCommentAdmin(BaseAdmin):
    list_display = ("ticket", "user", "created_at")
    search_fields = ("ticket__title", "user__username")

# --------------------------------------------------------------------
#  Miscellaneous
# --------------------------------------------------------------------
@admin.register(Notification)
class NotificationAdmin(BaseAdmin):
    list_display = ("title", "notif_type", "recipient", "is_read", "send_at")
    list_filter = ("notif_type", "is_read")
    search_fields = ("title", "body")

@admin.register(CalendarEvent)
class CalendarEventAdmin(BaseAdmin):
    list_display = ("title", "organizer", "start", "end", "location")
    list_filter = ("organizer", "start")

@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("actor", "action", "timestamp", "content_type")
    list_filter = ("action", "timestamp")
    search_fields = ("actor__username", "object_id", "action")

# --------------------------------------------------------------------
#  Optional Lightweight Admins for less-used models
# --------------------------------------------------------------------
admin.site.register(Announcement, BaseAdmin)
admin.site.register(PolicyDocument, BaseAdmin)
@admin.register(GroupPermission)
class GroupPermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "codename", "description")
    search_fields = ("name", "codename")

admin.site.register(LeaveType, BaseAdmin)
admin.site.register(DailyReport, BaseAdmin)
admin.site.register(Lead, BaseAdmin)
admin.site.register(Quotation, BaseAdmin)
admin.site.register(Campaign, BaseAdmin)
