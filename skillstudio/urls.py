"""
URL configuration for skillstudio project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('core.urls')),
    path('admin/', admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/courses/", include("courses.urls")),
    path("api/courses/", include("courses.urls_extras")),  # Additional course-related endpoints
    path("api/enrollments/", include("enrollments.urls")),
    path("api/assessments/", include("assessments.urls")),
    path("api/exams/", include("exams.urls")),
    path("api/analytics/", include("analytics.urls")),
    path("api/students/", include("students.urls")),
    path("api/certificates/", include("certificates.urls")),
    path('api/instructors/', include('instructors.urls')),
    path('api/events/', include('events.urls')),
    path('api/social/', include('social.urls')),
    path('api/adminpanel/', include('adminpanel.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/ai-recommender/', include('ai_recommender.urls')),
    path('api/live/', include('live.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
