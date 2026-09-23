from django.urls import path
from .views import (
    FeeCategoryListView, FeeCategoryDetailView,
    FeeScheduleView, StudentFeesView,
    PaystackInitiateView, PaystackVerifyView,
    ManualPaymentView, FeeReceiptView, OutstandingFeesView,
)

urlpatterns = [
    path('categories/',          FeeCategoryListView.as_view()),
    path('categories/<int:pk>/', FeeCategoryDetailView.as_view()),
    path('schedule/',            FeeScheduleView.as_view()),
    path('student/<int:pk>/',    StudentFeesView.as_view()),
    path('pay/initiate/',        PaystackInitiateView.as_view()),
    path('pay/verify/',          PaystackVerifyView.as_view()),
    path('pay/manual/',          ManualPaymentView.as_view()),
    path('receipts/<int:pk>/',   FeeReceiptView.as_view()),
    path('outstanding/',         OutstandingFeesView.as_view()),
]

from .payments import SchoolSubscription
urlpatterns += [path('subscription/', SchoolSubscription.as_view())]

from .exceptions import SchoolPaymentExceptions
urlpatterns += [path('exceptions/', SchoolPaymentExceptions.as_view()),
                path('exceptions/<int:pk>/', SchoolPaymentExceptions.as_view())]
