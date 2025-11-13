# models_all.py
# Put each app's models in its own app/models.py in production; this single file is illustrative.
import uuid
from django.conf import settings
from django.db.models import JSONField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

# -----------------------
# Managers
# -----------------------
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class AllObjectsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


# -----------------------
# Abstract Meta Classes
# -----------------------
class TimeStampedModel(models.Model):
    """created_at, updated_at"""
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True

class SoftDeleteModel(TimeStampedModel):
    """soft delete support"""
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def hard_delete(self):
        super().delete()

    class Meta:
        abstract = True

class AuditModel(SoftDeleteModel):
    """Tracks who created/modified records (optional)"""
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
        on_delete=models.SET_NULL,
    )

    class Meta:
        abstract = True

# -----------------------
# Action / Audit Log
# -----------------------
class ActionLog(models.Model):
    """
    Generic action log for auditing and system events.
    Use signals to create entries on save/delete or call manually.
    """
    ACTION_CHOICES = (
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("approve", "Approve"),
        ("reject", "Reject"),
        ("other", "Other"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    # Generic relation to any object
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    # snapshot of changes
    changes = JSONField(null=True, blank=True)  # {'field_name': ['old', 'new'], ...}
    meta = JSONField(null=True, blank=True)  # other contextual data (IP, user agent, etc.)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["actor", "action", "timestamp"]),
        ]

# -----------------------
# CORE (company) app
# -----------------------
class Company(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    legal_name = models.CharField(max_length=512, blank=True)
    tagline = models.CharField(max_length=255, blank=True)
    logo = models.ImageField(upload_to="company/logos/", null=True, blank=True)
    cover_image = models.ImageField(upload_to="company/covers/", null=True, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    metadata = JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"

class Announcement(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_public = models.BooleanField(default=True)
    pinned_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

class PolicyDocument(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="policies")
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    file = models.FileField(upload_to="company/policies/")
    version = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("company", "slug", "version")

# -----------------------
# Accounts & Roles app
# -----------------------
from django.contrib.auth.models import AbstractUser

class User(AbstractUser, AuditModel):
    """Extend as needed. Keep username/email settings consistent in project settings."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ImageField(upload_to="users/avatars/", null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_verified = models.BooleanField(default=False)
    # roles: allow multiple roles via M2M OR keep single role field for simplicity
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("employee", "Employee"),
        ("manager", "Manager"),
        ("hr", "HR"),
        ("sales", "Sales"),
        ("client", "Client"),
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="employee", db_index=True)
    # extra meta
    preferences = JSONField(null=True, blank=True)

    class Meta:
        swappable = "AUTH_USER_MODEL"
        indexes = [models.Index(fields=["email"]), models.Index(fields=["role"])]

class GroupPermission(models.Model):
    """
    Optional extra permissions mapping (complements Django's permissions).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    codename = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

# -----------------------
# Employees app
# -----------------------
class Department(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=32, blank=True)
    lead = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="department_leads")

    class Meta:
        unique_together = ("company", "name")

class Designation(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="designations")
    title = models.CharField(max_length=200)
    level = models.IntegerField(default=0)

    class Meta:
        unique_together = ("company", "title")

def employee_doc_upload(instance, filename):
    return f"employees/{instance.id}/docs/{filename}"


class Employee(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee_profile")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")
    designation = models.ForeignKey(Designation, null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")
    employee_code = models.CharField(max_length=64, db_index=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    date_of_leaving = models.DateField(null=True, blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reportees")
    emergency_contact = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    documents = models.FileField(upload_to=employee_doc_upload, null=True, blank=True)
    is_active_employee = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["company", "employee_code"]), models.Index(fields=["manager"])]

# -----------------------
# Attendance & Breaks app
# -----------------------
class Attendance(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField(db_index=True)
    login_time = models.DateTimeField(null=True, blank=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    total_work_seconds = models.BigIntegerField(default=0)  # compute and store for fast aggregation
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("employee", "date")
        indexes = [models.Index(fields=["employee", "date"])]

    def compute_total(self):
        # implement logic to compute total_work_seconds minus breaks
        pass

class Break(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name="breaks")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-start_time"]

# -----------------------
# Leave & Holiday Management
# -----------------------
class LeaveType(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="leave_types")
    name = models.CharField(max_length=100)
    default_days_per_year = models.IntegerField(default=0)

    class Meta:
        unique_together = ("company", "name")

class LeaveRequest(AuditModel):
    STATUS_CHOICES = (("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leaves")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(max_digits=6, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending", db_index=True)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_leaves")

    class Meta:
        indexes = [models.Index(fields=["employee", "status"])]

class Holiday(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="holidays")
    title = models.CharField(max_length=255)
    date = models.DateField(db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("company", "date")

# -----------------------
# Daily Reports / Work Logs
# -----------------------
class DailyReport(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="daily_reports")
    date = models.DateField(db_index=True)
    tasks_done = models.TextField()
    blockers = models.TextField(blank=True)
    time_spent_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    mood = models.CharField(max_length=32, blank=True)
    linked_project = models.ForeignKey("Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="daily_reports")
    manager_comments = models.TextField(blank=True)
    productivity_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ("employee", "date")
        indexes = [models.Index(fields=["employee", "date"])]

# -----------------------
# Project & Task Management
# -----------------------
class Client(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    metadata = JSONField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["company", "name"])]

class Project(AuditModel):
    STATUS_CHOICES = (("planning", "Planning"), ("ongoing", "Ongoing"), ("on_hold", "On Hold"), ("completed", "Completed"), ("cancelled", "Cancelled"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="projects")
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, blank=True, db_index=True)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="planning", db_index=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    members = models.ManyToManyField(Employee, through="ProjectMembership", related_name="projects")

    class Meta:
        indexes = [models.Index(fields=["company", "code"])]

class ProjectMembership(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    role = models.CharField(max_length=128, blank=True)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("project", "employee")

class Task(AuditModel):
    PRIORITY = (("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical"))
    STATUS = (("todo", "To Do"), ("in_progress", "In Progress"), ("review", "In Review"), ("done", "Done"), ("blocked", "Blocked"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reported_tasks")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tasks")
    priority = models.CharField(max_length=32, choices=PRIORITY, default="medium", db_index=True)
    status = models.CharField(max_length=32, choices=STATUS, default="todo", db_index=True)
    estimate_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    spent_seconds = models.BigIntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["project", "assignee", "status", "priority"])]

class TaskTimeLog(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="time_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.BigIntegerField(default=0)

# -----------------------
# Leads & Enquiries
# -----------------------
class Lead(AuditModel):
    SOURCE_CHOICES = (("web", "Website"), ("email", "Email"), ("phone", "Phone"), ("referral", "Referral"), ("campaign", "Campaign"))
    STATUS_CHOICES = (("new", "New"), ("contacted", "Contacted"), ("qualified", "Qualified"), ("converted", "Converted"), ("lost", "Lost"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="leads")
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    message = models.TextField(blank=True)
    source = models.CharField(max_length=64, choices=SOURCE_CHOICES, default="web")
    status = models.CharField(max_length=64, choices=STATUS_CHOICES, default="new", db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_leads")
    metadata = JSONField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["company", "status", "source"])]

# -----------------------
# Finance & Billing
# -----------------------
class Quotation(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="quotations")
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL)
    reference = models.CharField(max_length=128, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, default="draft")

class Invoice(AuditModel):
    STATUS = (("draft", "Draft"), ("sent", "Sent"), ("paid", "Paid"), ("overdue", "Overdue"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL)
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL)
    invoice_number = models.CharField(max_length=128, db_index=True)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=32, choices=STATUS, default="draft", db_index=True)
    metadata = JSONField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["invoice_number", "status"])]

class Payment(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_on = models.DateTimeField(default=timezone.now)
    method = models.CharField(max_length=64, blank=True)
    transaction_ref = models.CharField(max_length=255, blank=True)

class Expense(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="expenses")
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField(default=timezone.now)
    category = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)

# -----------------------
# Sales & Marketing
# -----------------------
class Campaign(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="campaigns")
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=128, blank=True)  # e.g., google, facebook, email
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    metadata = JSONField(null=True, blank=True)

# -----------------------
# Training & Skill Development
# -----------------------
class Course(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="courses")
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    duration_hours = models.IntegerField(default=0)

class Enrollment(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=64, default="enrolled")
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

# -----------------------
# Performance & Reviews
# -----------------------
class Review(AuditModel):
    PERIOD_CHOICES = (("monthly", "Monthly"), ("quarterly", "Quarterly"), ("yearly", "Yearly"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="reviews")
    period = models.CharField(max_length=32, choices=PERIOD_CHOICES)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)

# -----------------------
# Communication & Notifications
# -----------------------
class Notification(AuditModel):
    TYPE_CHOICES = (("info","Info"), ("warning","Warning"), ("alert","Alert"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    notif_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default="info")
    is_read = models.BooleanField(default=False)
    send_at = models.DateTimeField(null=True, blank=True)

# -----------------------
# Scheduling & Calendar
# -----------------------
class CalendarEvent(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="events", blank=True)
    location = models.CharField(max_length=255, blank=True)

# -----------------------
# Support / Ticket System
# -----------------------
class Ticket(AuditModel):
    PRIORITY = (("low","Low"), ("medium","Medium"), ("high","High"), ("urgent","Urgent"))
    STATUS = (("open","Open"), ("in_progress","In Progress"), ("resolved","Resolved"), ("closed","Closed"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tickets")
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reported_tickets")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tickets")
    priority = models.CharField(max_length=32, choices=PRIORITY, default="medium")
    status = models.CharField(max_length=32, choices=STATUS, default="open", db_index=True)

class TicketComment(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    message = models.TextField()

# -----------------------
# Documents & Knowledgebase
# -----------------------
class Document(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/")
    tags = JSONField(null=True, blank=True)

class KBArticle(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="kb_articles")
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    body = models.TextField()
    is_public = models.BooleanField(default=False)
