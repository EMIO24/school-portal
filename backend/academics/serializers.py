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
        if attrs.get("start_date") and attrs.get("end_date"):
            if attrs["start_date"] > attrs["end_date"]:
                raise serializers.ValidationError(
                    {"end_date": "End date cannot be before start date."}
                )
        return attrs


class TermSerializer(serializers.ModelSerializer):
    holidays           = HolidaySerializer(many=True, read_only=True)
    name_display       = serializers.CharField(source="get_name_display", read_only=True)
    name_display_short = serializers.CharField(
        source="get_name_display_short", read_only=True
    )
    duration_weeks     = serializers.SerializerMethodField()

    class Meta:
        model  = Term
        fields = [
            "id", "session", "name", "name_display", "name_display_short",
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
        if attrs.get("start_date") and attrs.get("end_date"):
            if attrs["start_date"] >= attrs["end_date"]:
                raise serializers.ValidationError(
                    {"end_date": "End date must be after start date."}
                )
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
        if attrs.get("start_date") and attrs.get("end_date"):
            if attrs["start_date"] >= attrs["end_date"]:
                raise serializers.ValidationError(
                    {"end_date": "End date must be after start date."}
                )
        return attrs


class CurrentCalendarSerializer(serializers.Serializer):
    """
    Read-only snapshot of the current session + current term.
    Returned by GET /api/calendar/current/
    """
    session = AcademicSessionSerializer(read_only=True)
    term    = TermSerializer(read_only=True)