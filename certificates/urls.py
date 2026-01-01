from django.urls import path
from .views import DownloadCertificateView, VerifyCertificateView

urlpatterns = [
    path('verify/<str:code>/', VerifyCertificateView.as_view()),
    path('download/<int:course_id>/', DownloadCertificateView.as_view()),
]
