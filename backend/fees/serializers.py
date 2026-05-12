from rest_framework import serializers
from .models import FeeCategory, FeeSchedule, FeePayment


class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = FeeCategory
        fields = ['id', 'name', 'description', 'is_compulsory']


class FeeScheduleSerializer(serializers.ModelSerializer):
    fee_category_name  = serializers.CharField(source='fee_category.name', read_only=True)
    class_level_name   = serializers.CharField(source='class_level.name', read_only=True)
    term_name          = serializers.SerializerMethodField()

    class Meta:
        model  = FeeSchedule
        fields = [
            'id', 'term', 'term_name', 'class_level', 'class_level_name',
            'fee_category', 'fee_category_name', 'amount', 'due_date',
        ]

    def get_term_name(self, obj):
        return f"{obj.term.get_name_display()} {obj.term.session.name}"


class FeePaymentSerializer(serializers.ModelSerializer):
    student_name     = serializers.SerializerMethodField()
    fee_category_name = serializers.CharField(source='fee_schedule.fee_category.name', read_only=True)

    class Meta:
        model  = FeePayment
        fields = [
            'id', 'student', 'student_name', 'fee_schedule', 'fee_category_name',
            'amount_paid', 'payment_date', 'method', 'paystack_reference',
            'paystack_status', 'receipt_number', 'created_at',
        ]
        read_only_fields = ['receipt_number', 'created_at']

    def get_student_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.admission_number
