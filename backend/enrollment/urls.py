"""
enrollment/urls.py — full URL config including subject assignments.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ClassArmViewSet, ClassLevelViewSet, StudentViewSet, SubjectViewSet
from .staff_views import StaffViewSet
from .parent_links import StudentParents
from .assignment_views import SubjectAssignmentViewSet, AssignSubjectsMixin, SubjectByClassMixin
from .migration_import import (MigrationCentre, MigrationConflictList, MigrationJobList,
                               MigrationJobReport, MigrationMappingProfiles)
from .operations import (AdmissionDecision, AdmissionDocumentCreate, AdmissionListCreate, StudentRecordHistory,
                         WelfareListCreate, WelfareUpdateView)

# Patch mixins onto existing ViewSets (avoids inheritance conflicts)
StaffViewSet.__bases__  = (AssignSubjectsMixin,) + StaffViewSet.__bases__
SubjectViewSet.__bases__ = (SubjectByClassMixin,) + SubjectViewSet.__bases__

router = DefaultRouter()
router.register(r"class-levels",        ClassLevelViewSet,        basename="class-level")
router.register(r"class-arms",          ClassArmViewSet,          basename="class-arm")
router.register(r"subjects",            SubjectViewSet,           basename="subject")
router.register(r"students",            StudentViewSet,           basename="student")
router.register(r"staff",               StaffViewSet,             basename="staff")
router.register(r"subject-assignments", SubjectAssignmentViewSet, basename="subject-assignment")

urlpatterns = [
    path('operations/admissions/', AdmissionListCreate.as_view()),
    path('operations/admissions/<int:pk>/decision/', AdmissionDecision.as_view()),
    path('operations/admissions/<int:pk>/documents/', AdmissionDocumentCreate.as_view()),
    path('operations/student-records/<int:student_id>/', StudentRecordHistory.as_view()),
    path('operations/welfare/', WelfareListCreate.as_view()),
    path('operations/welfare/<int:pk>/updates/', WelfareUpdateView.as_view()),
    path('migration/', MigrationCentre.as_view()),
    path('migration/jobs/', MigrationJobList.as_view()),
    path('migration/jobs/<int:pk>/report/', MigrationJobReport.as_view()),
    path('migration/mappings/', MigrationMappingProfiles.as_view()),
    path('migration/conflicts/', MigrationConflictList.as_view()),
    path('migration/templates/<str:domain>/', MigrationCentre.as_view()),
    path('migration/<str:domain>/<str:operation>/', MigrationCentre.as_view()),
    path('students/<int:pk>/parents/', StudentParents.as_view()),
    path("", include(router.urls)),
]

# Routes:
#   /api/class-levels/
#   /api/class-arms/
#   /api/subjects/
#   /api/subjects/by-class/{arm_id}/
#   /api/students/
#   /api/students/bulk-import/
#   /api/students/{id}/assign-class/
#   /api/students/by-class/{arm_id}/
#   /api/staff/
#   /api/staff/bulk-import/
#   /api/staff/{id}/assign-subjects/       ← NEW
#   /api/subject-assignments/
#   /api/subject-assignments/grid/         ← NEW
