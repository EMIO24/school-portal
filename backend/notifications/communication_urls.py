from django.urls import path
from .communications import AudiencePreview, RecipientOptions, NoticeSend, NoticeHistory, NoticeHistoryDetail, NoticeInbox, NoticeRead

urlpatterns = [
    path('preview/', AudiencePreview.as_view()),
    path('recipients/', RecipientOptions.as_view()),
    path('send/', NoticeSend.as_view()),
    path('history/', NoticeHistory.as_view()),
    path('history/<int:pk>/', NoticeHistoryDetail.as_view()),
    path('inbox/', NoticeInbox.as_view()),
    path('inbox/<int:pk>/read/', NoticeRead.as_view()),
]
