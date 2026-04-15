"""
backend/results/urls.py

Endpoint reference:
  POST /api/results/positions/compute/?class_arm=&term=
  GET  /api/results/class-results/?class_arm=&term=
  GET  /api/results/remarks/{student_id}/?term=
  PATCH /api/results/remarks/{student_id}/?term=
  GET  /api/results/slip-data/{student_id}/?term=
  GET  /api/results/slip/{student_id}/?term=          → PDF
  GET  /api/results/broadsheet/{class_arm_id}/?term=  → PDF
  GET  /api/results/all-slips/{class_arm_id}/?term=   → ZIP
  POST /api/results/check/                            → PUBLIC (no auth)

  POST /api/scratch-cards/generate/
  GET  /api/scratch-cards/
  GET  /api/scratch-cards/batch-stats/
  GET  /api/scratch-cards/unused-csv/?batch=
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
    PublicResultCheckView,
    ScratchCardGenerateView,
    ScratchCardListView,
    ScratchCardBatchStatsView,
    ScratchCardUnusedCSVView,
)

results_urlpatterns = [
    path('positions/compute/',             ComputePositionsView.as_view(),    name='compute-positions'),
    path('class-results/',                 ClassResultsView.as_view(),        name='class-results'),
    path('remarks/<int:student_id>/',      ResultRemarkView.as_view(),        name='result-remark'),
    path('slip-data/<int:student_id>/',    SlipDataView.as_view(),            name='slip-data'),
    path('slip/<int:student_id>/',         ResultSlipPDFView.as_view(),       name='result-slip-pdf'),
    path('broadsheet/<int:class_arm_id>/', BroadsheetPDFView.as_view(),       name='broadsheet-pdf'),
    path('all-slips/<int:class_arm_id>/',  AllSlipsZipView.as_view(),         name='all-slips-zip'),
    path('check/',                         PublicResultCheckView.as_view(),   name='public-result-check'),
]

scratch_card_urlpatterns = [
    path('generate/',    ScratchCardGenerateView.as_view(),  name='scratch-card-generate'),
    path('',             ScratchCardListView.as_view(),      name='scratch-card-list'),
    path('batch-stats/', ScratchCardBatchStatsView.as_view(),name='scratch-card-batch-stats'),
    path('unused-csv/',  ScratchCardUnusedCSVView.as_view(), name='scratch-card-unused-csv'),
]
