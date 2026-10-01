"""
academics/serializers.py
"""

from rest_framework import serializers
from .models import AcademicSession, Holiday, Term


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Holiday
        fields = [
            "id", "term", "name",
            "start_date", "end_date", "holiday_type",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        from rest_framework.exceptions import PermissionDenied
        term = attrs.get('term', getattr(self.instance, 'term', None))
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        request = self.context.get('request')
        if term and request and term.session.school_id != request.tenant.pk:
            raise PermissionDenied('Term does not belong to this school.')
        if start and end and start > end:
            raise serializers.ValidationError({'end_date': 'End date cannot be before start date.'})
        if term and start and end and (start < term.start_date or end > term.end_date):
            raise serializers.ValidationError({'start_date': 'Holiday dates must stay within the selected term.'})
        return attrs


class TermSerializer(serializers.ModelSerializer):
    session_name = serializers.CharField(source='session.name', read_only=True)
    holidays           = HolidaySerializer(many=True, read_only=True)
    name_display       = serializers.CharField(source="get_name_display", read_only=True)
    name_display_short = serializers.CharField(
        source="get_name_display_short", read_only=True
    )
    duration_weeks     = serializers.SerializerMethodField()

    class Meta:
        model  = Term
        fields = [
            "id", "session", "session_name", "name", "name_display", "name_display_short",
            "start_date", "end_date", "is_current",
            "next_term_begins", "duration_weeks", "holidays",
        ]
        read_only_fields = ["id", "is_current", "name_display",
                            "name_display_short", "duration_weeks", "holidays"]

    def get_duration_weeks(self, obj) -> int | None:
        if obj.start_date and obj.end_date:
            delta = obj.end_date - obj.start_date
            return round(delta.days / 7)
        return None

    def validate(self, attrs):
        session = attrs.get("session", getattr(self.instance, "session", None))
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        next_term = attrs.get("next_term_begins", getattr(self.instance, "next_term_begins", None))
        request = self.context.get("request")
        if session and request and session.school_id != request.tenant.pk:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Session does not belong to this school.")
        if start and end and start >= end:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        if session and start and end and (start < session.start_date or end > session.end_date):
            raise serializers.ValidationError({"start_date": "Term dates must stay within the selected session."})
        if next_term and end and next_term <= end:
            raise serializers.ValidationError({"next_term_begins": "Next term must begin after this term ends."})
        return attrs


class AcademicSessionSerializer(serializers.ModelSerializer):
    terms          = TermSerializer(many=True, read_only=True)
    duration_weeks = serializers.SerializerMethodField()

    class Meta:
        model  = AcademicSession
        fields = [
            "id", "school", "name",
            "start_date", "end_date",
            "is_current", "duration_weeks", "terms",
        ]
        read_only_fields = ["id", "school", "is_current",
                            "duration_weeks", "terms"]

    def get_duration_weeks(self, obj) -> int | None:
        if obj.start_date and obj.end_date:
            return round((obj.end_date - obj.start_date).days / 7)
        return None

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and start >= end:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})

        request = self.context.get("request")
        school = getattr(request, "tenant", None) if request else getattr(self.instance, "school", None)
        if school and start and end:
            overlaps = AcademicSession.objects.filter(
                school=school,
                start_date__lte=end,
                end_date__gte=start,
            )
            if self.instance:
                overlaps = overlaps.exclude(pk=self.instance.pk)
            if overlaps.exists():
                raise serializers.ValidationError(
                    {"start_date": "Academic sessions for a school cannot overlap."}
                )
        return attrs


class CurrentCalendarSerializer(serializers.Serializer):
    """
    Read-only snapshot of the current session + current term.
    Returned by GET /api/calendar/current/
    """
    session = AcademicSessionSerializer(read_only=True)
    term    = TermSerializer(read_only=True)
