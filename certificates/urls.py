from django.urls import path
from .views import DownloadCertificateView, MyCertificateView, VerifyCertificateView

urlpatterns = [
    path('my/<int:course_id>/', MyCertificateView.as_view()),
    path('verify/<uuid:code>/', VerifyCertificateView.as_view()),
    path('download/<int:course_id>/', DownloadCertificateView.as_view()),
]
