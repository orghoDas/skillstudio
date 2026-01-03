from django.urls import path
from .views import (
    MyCertificatesListView,
    MyCertificateDetailView,
    DownloadCertificateView,
    VerifyCertificateView,
    regenerate_certificate
)

urlpatterns = [
    # User certificate endpoints
    path('my/', MyCertificatesListView.as_view(), name='my-certificates'),
    path('my/<int:course_id>/', MyCertificateDetailView.as_view(), name='my-certificate-detail'),
    path('download/<int:course_id>/', DownloadCertificateView.as_view(), name='download-certificate'),
    
    # Public verification
    path('verify/<str:code>/', VerifyCertificateView.as_view(), name='verify-certificate'),
    
    # Admin operations
    path('regenerate/<int:course_id>/', regenerate_certificate, name='regenerate-certificate'),
]

