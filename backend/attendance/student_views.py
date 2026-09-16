from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAuthenticatedTenantUser
from .models import AttendanceRecord


class MyAttendanceRecordsView(APIView):
    """Return only the logged-in student's attendance records for a term."""

    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request):
        if request.user.role != 'student':
            return Response(
                {'detail': 'Only students can access this endpoint.'},
                status=403,
            )

        term_id = request.query_params.get('term')
        if not term_id:
            return Response({'detail': 'term parameter is required.'}, status=400)

        records = (
            AttendanceRecord.objects
            .filter(
                school=request.tenant,
                student=request.user,
                attendance_session__term_id=term_id,
            )
            .select_related('attendance_session')
            .order_by('attendance_session__date', 'attendance_session__period__order_index')
        )

        return Response([
            {
                'date': record.attendance_session.date,
                'status': record.status,
                'remark': record.remark,
                'session_id': record.attendance_session_id,
            }
            for record in records
        ])
