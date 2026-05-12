from django.urls import path
from .views import PromotionCriteriaView, PromotionEvaluateView, PromotionExecuteView

urlpatterns = [
    path('criteria/',  PromotionCriteriaView.as_view()),
    path('evaluate/',  PromotionEvaluateView.as_view()),
    path('execute/',   PromotionExecuteView.as_view()),
]
