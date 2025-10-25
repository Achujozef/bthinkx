from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = [
        ('manager', 'Operations Manager'),
        ('coordinator', 'Coordinator'),
        ('student', 'Student'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)

    # Fix reverse accessor clash
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',  # <- change to avoid clash
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set_permissions',  # <- change to avoid clash
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    career_background = models.TextField(blank=True, null=True)
    blood_group = models.CharField(max_length=5, blank=True, null=True)
    guardian_name = models.CharField(max_length=150)
    guardian_phone = models.CharField(max_length=15)
    date_of_birth = models.DateField()
    phone = models.CharField(max_length=15)
    address = models.TextField()
    admission_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name()



class CoordinatorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'role': 'coordinator'})
    designation = models.CharField(max_length=100, blank=True, null=True)  # Example: Academic Coordinator
    phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.user.get_full_name()


class Course(models.Model):
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    duration_weeks = models.PositiveIntegerField()
    coordinators = models.ManyToManyField(User, limit_choices_to={'role': 'coordinator'}, blank=True)

    def __str__(self):
        return self.title


class WeeklyTopic(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='weeks')
    week_number = models.PositiveIntegerField()
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('course', 'week_number')

    def __str__(self):
        return f"{self.course.title} - Week {self.week_number}"


class Session(models.Model):
    SESSION_TYPES = [
        ('review', 'Review Session'),
        ('lecture', 'Lecture'),
        ('lab', 'Lab/Practical'),
        ('discussion', 'Discussion'),
        ('other', 'Other'),
    ]
    week = models.ForeignKey(WeeklyTopic, on_delete=models.CASCADE, related_name='sessions')
    name = models.CharField(max_length=150)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default='Scheduled')  # Scheduled, Completed, Pending

    def __str__(self):
        return f"{self.week} - {self.name}"


class Enrollment(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_on = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student} in {self.course}"


class ReviewPerformance(models.Model):
    STATUS_CHOICES = [
        ('failed', 'Failed'),
        ('critical', 'Critical'),
        ('improve', 'Need Improvement'),
        ('good', 'Good'),
        ('excellent', 'Excellent'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='reviews')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, limit_choices_to={'session_type': 'review'})
    theory_marks = models.PositiveIntegerField(default=0)
    practical_marks = models.PositiveIntegerField(default=0)
    total_marks = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('student', 'session')

    def save(self, *args, **kwargs):
        self.total_marks = self.theory_marks + self.practical_marks
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.session} ({self.status})"
