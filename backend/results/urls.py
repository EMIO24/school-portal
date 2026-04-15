"""
backend/results/urls.py
"""
from django.urls import path
from .views import (
    ComputePositionsView,
    ResultRemarkView,
    ClassResultsView,
    SlipDataView,
    ResultSlipPDFView,
    BroadsheetPDFView,
    AllSlipsZipView,
)

urlpatterns = [
    # Position computation
    path('positions/compute/',                    ComputePositionsView.as_view(),  name='compute-positions'),

    # Class results list (admin table)
    path('class-results/',                        ClassResultsView.as_view(),      name='class-results'),

    # Remarks CRUD
    path('remarks/<int:student_id>/',             ResultRemarkView.as_view(),      name='result-remark'),

    # JSON preview (browser result card)
    path('slip-data/<int:student_id>/',           SlipDataView.as_view(),          name='slip-data'),

    # PDF outputs
    path('slip/<int:student_id>/',                ResultSlipPDFView.as_view(),     name='result-slip-pdf'),
    path('broadsheet/<int:class_arm_id>/',        BroadsheetPDFView.as_view(),     name='broadsheet-pdf'),
    path('all-slips/<int:class_arm_id>/',         AllSlipsZipView.as_view(),       name='all-slips-zip'),
]

# ─── Endpoint reference ───────────────────────────────────────────────────────
# POST /api/results/positions/compute/?class_arm=&term=
# GET  /api/results/class-results/?class_arm=&term=
# GET  /api/results/remarks/{student_id}/?term=
# PATCH /api/results/remarks/{student_id}/?term=
# GET  /api/results/slip-data/{student_id}/?term=
# GET  /api/results/slip/{student_id}/?term=          → PDF
# GET  /api/results/broadsheet/{class_arm_id}/?term=  → PDF
# GET  /api/results/all-slips/{class_arm_id}/?term=   → ZIP