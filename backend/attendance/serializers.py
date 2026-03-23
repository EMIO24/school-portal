"""
backend/attendance/serializers.py

Serializers for AttendanceSession and AttendanceRecord.

Key design decisions:
  - AttendanceSessionSerializer.create() auto-creates blank records for
    every enrolled student so the teacher gets a pre-populated list.
  - BulkRecordSerializer handles the PATCH submit/ payload:
    [{student_id, status, remark?}, ...] in one round-trip.
  - ReportSerializer returns the computed summary dict from the manager.
"""

from django.utils import timezone
from rest_framework import serializers

from .models import AttendanceSession, AttendanceRecord


# ─────────────────────────────────────────────────────────────────────────────
# AttendanceRecord — used inside the session detail
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name      = serializers.SerializerMethodField()
    student_admission = serializers.CharField(
        source='student.profile.admission_number', read_only=True, default=''
    )

    class Meta:
        model  = AttendanceRecord
        fields = [
            'id', 'student', 'student_name', 'student_admission',
            'status', 'remark',
        ]
        read_only_fields = ['id', 'student_name', 'student_admission']

    def get_student_name(self, obj):
        u = obj.student
        return f"{u.last_name} {u.first_name}".strip() or u.username


# ─────────────────────────────────────────────────────────────────────────────
# AttendanceSession
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceSessionSerializer(serializers.ModelSerializer):
    records      = AttendanceRecordSerializer(many=True, read_only=True)
    teacher_name = serializers.SerializerMethodField()
    class_name   = serializers.CharField(source='class_arm.name', read_only=True)

    class Meta:
        model  = AttendanceSession
        fields = [
            'id', 'class_arm', 'class_name', 'teacher', 'teacher_name',
            'term', 'date', 'period', 'mode', 'is_finalized',
            'created_at', 'updated_at', 'records',
        ]
        read_only_fields = ['id', 'teacher', 'is_finalized', 'created_at', 'updated_at']

    def get_teacher_name(self, obj):
        if obj.teacher:
            return obj.teacher.get_full_name() or obj.teacher.username
        return None


class AttendanceSessionCreateSerializer(serializers.ModelSerializer):
    """
    Used for POST start/ .
    school and teacher injected from request context — not accepted from client.
    """
    class Meta:
        model  = AttendanceSession
        fields = ['class_arm', 'term', 'date', 'period', 'mode']

    def validate(self, attrs):
        school    = self.context['request'].tenant
        class_arm = attrs['class_arm']
        term      = attrs['term']
        date      = attrs['date']
        mode      = attrs.get('mode', AttendanceSession.Mode.DAILY)
        period    = attrs.get('period')

        # Reject if a session already exists for this slot
        qs = AttendanceSession.objects.filter(
            school=school, class_arm=class_arm, term=term, date=date, mode=mode
        )
        if mode == AttendanceSession.Mode.PER_PERIOD:
            qs = qs.filter(period=period)
        else:
            qs = qs.filter(period__isnull=True)

        if qs.exists():
            raise serializers.ValidationError(
                'An attendance session already exists for this class on this date.'
            )
        return attrs

    def create(self, validated_data):
        """
        Create the session, then bulk-create an AttendanceRecord (default=present)
        for every enrolled student in the class arm. This pre-populates the
        teacher's list so they only need to flip absent/late students.
        """
        request   = self.context['request']
        school    = request.tenant

        session = AttendanceSession.objects.create(
            school  = school,
            teacher = request.user,
            **validated_data,
        )

        # Fetch enrolled students for this class arm (scoped to tenant)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        students = User.objects.filter(
            school=school,
            role='student',
            profile__class_arm=session.class_arm,
        )

        AttendanceRecord.objects.bulk_create([
            AttendanceRecord(
                attendance_session=session,
                student=student,
                status=AttendanceRecord.Status.PRESENT,
            )
            for student in students
        ])

        return session


# ─────────────────────────────────────────────────────────────────────────────
# Bulk submit payload
# ─────────────────────────────────────────────────────────────────────────────

class BulkRecordItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    status     = serializers.ChoiceField(choices=AttendanceRecord.Status.choices)
    remark     = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class BulkSubmitSerializer(serializers.Serializer):
    records = BulkRecordItemSerializer(many=True)

    def validate_records(self, value):
        if not value:
            raise serializers.ValidationError('At least one record is required.')
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Report serializers
# ─────────────────────────────────────────────────────────────────────────────

class StudentAttendanceSummarySerializer(serializers.Serializer):
    """Used by GET report/?student=&term= and in low-attendance panel."""
    student_id    = serializers.IntegerField()
    student_name  = serializers.CharField()
    admission_no  = serializers.CharField()
    class_arm     = serializers.CharField()
    total         = serializers.IntegerField()
    present       = serializers.IntegerField()
    absent        = serializers.IntegerField()
    late          = serializers.IntegerField()
    excused       = serializers.IntegerField()
    percentage    = serializers.FloatField()


class DailyClassRecordSerializer(serializers.Serializer):
    """
    One row in the class attendance report, per session date.
    Used for the admin heatmap calendar.
    """
    date           = serializers.DateField()
    period_name    = serializers.CharField(allow_null=True)
    total_students = serializers.IntegerField()
    present_count  = serializers.IntegerField()
    absent_count   = serializers.IntegerField()
    late_count     = serializers.IntegerField()
    is_finalized   = serializers.BooleanField()
    session_id     = serializers.IntegerField()
    # Ratio for heatmap colouring: 0.0 – 1.0
    present_ratio  = serializers.FloatField()