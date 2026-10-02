from django.conf import settings
from django.db import models


class AdmissionApplication(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        OFFERED = "offered", "Offered"
        ADMITTED = "admitted", "Admitted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    school = models.ForeignKey("tenants.School", on_delete=models.CASCADE, related_name="admission_applications")
    application_number = models.CharField(max_length=40)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    guardian_name = models.CharField(max_length=150)
    guardian_phone = models.CharField(max_length=30)
    guardian_email = models.EmailField(blank=True)
    applying_class_level = models.ForeignKey("enrollment.ClassLevel", on_delete=models.PROTECT, related_name="admission_applications")
    preferred_campus = models.ForeignKey("tenants.Campus", on_delete=models.PROTECT, null=True, blank=True, related_name="admission_applications")
    previous_school = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_admission_applications")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admitted_student = models.OneToOneField("enrollment.StudentProfile", null=True, blank=True, on_delete=models.PROTECT, related_name="admission_application")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_admission_applications")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["school", "application_number"], name="unique_admission_application_number_per_school"),
        ]
        indexes = [models.Index(fields=["school", "status"], name="admission_school_status_idx")]


class AdmissionDocument(models.Model):
    application = models.ForeignKey(AdmissionApplication, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=30, choices=[
        ("birth_certificate", "Birth certificate"),
        ("previous_result", "Previous result"),
        ("passport_photo", "Passport photo"),
        ("medical", "Medical document"),
        ("other", "Other"),
    ])
    title = models.CharField(max_length=180)
    file_url = models.URLField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "id"]


class StudentRecordEntry(models.Model):
    class Kind(models.TextChoices):
        IDENTITY = "identity", "Identity"
        GUARDIAN = "guardian", "Guardian"
        ENROLLMENT = "enrollment", "Enrollment"
        DOCUMENT = "document", "Document"
        NOTE = "note", "Official note"

    school = models.ForeignKey("tenants.School", on_delete=models.PROTECT, related_name="student_record_entries")
    student = models.ForeignKey("enrollment.StudentProfile", on_delete=models.PROTECT, related_name="official_record_entries")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=180)
    details = models.TextField(blank=True)
    document_url = models.URLField(blank=True)
    effective_date = models.DateField()
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="corrections")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="student_records_recorded")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "-id"]
        indexes = [models.Index(fields=["school", "student", "kind"], name="student_record_scope_idx")]


class WelfareCase(models.Model):
    class Category(models.TextChoices):
        ATTENDANCE = "attendance", "Attendance"
        BEHAVIOUR = "behaviour", "Behaviour"
        ACADEMIC = "academic", "Academic support"
        HEALTH = "health", "Health"
        SAFEGUARDING = "safeguarding", "Safeguarding"
        OTHER = "other", "Other"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        MONITORING = "monitoring", "Monitoring"
        RESOLVED = "resolved", "Resolved"

    school = models.ForeignKey("tenants.School", on_delete=models.PROTECT, related_name="welfare_cases")
    student = models.ForeignKey("enrollment.StudentProfile", on_delete=models.PROTECT, related_name="welfare_cases")
    category = models.CharField(max_length=20, choices=Category.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.LOW)
    title = models.CharField(max_length=180)
    details = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    class_arm_snapshot = models.ForeignKey("enrollment.ClassArm", null=True, blank=True, on_delete=models.PROTECT, related_name="welfare_cases")
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="opened_welfare_cases")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_welfare_cases")
    resolved_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-opened_at", "-id"]
        indexes = [
            models.Index(fields=["school", "status", "severity"], name="welfare_school_status_idx"),
            models.Index(fields=["school", "student"], name="welfare_student_idx"),
        ]


class WelfareCaseUpdate(models.Model):
    case = models.ForeignKey(WelfareCase, on_delete=models.PROTECT, related_name="updates")
    note = models.TextField()
    status_after = models.CharField(max_length=12, choices=WelfareCase.Status.choices)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
