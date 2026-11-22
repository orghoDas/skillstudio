from django.urls import path
from certificates.views import certificate_verification_page
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # Authentication pages
    path('auth/login/', views.login_page, name='login_page'),
    path('auth/register/', views.register_page, name='register_page'),
    
    # Dashboard pages
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    
    # Course pages
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    
    # Profile pages
    path('profile/', views.profile_page, name='profile_page'),
    path('instructor/profile/', views.instructor_profile_page, name='instructor_profile_page'),
    path('settings/', views.settings_page, name='settings_page'),
    path('settings/api-keys/', views.api_keys_page, name='api_keys_page'),
    path('settings/profile/', views.profile_page, name='settings_profile_page'),  # Alias for profile
    path('instructor/courses/', views.instructor_courses_list, name='instructor_courses_list'),
    path('instructor/courses/create/', views.instructor_course_create, name='instructor_course_create'),
    path('instructor/courses/<slug:slug>/edit/', views.instructor_course_edit, name='instructor_course_edit'),
    path('instructor/courses/<slug:slug>/content/', views.instructor_course_content, name='instructor_course_content'),
    path('instructor/courses/<slug:slug>/preview/', views.instructor_course_preview, name='instructor_course_preview'),
    path('instructor/lessons/<int:id>/edit/', views.instructor_lesson_edit, name='instructor_lesson_edit'),
    path('instructor/students/', views.instructor_students, name='instructor_students'),
    path('library/', views.learning_library, name='learning_library'),
    path('my-courses/', views.my_courses, name='my_courses'),
    path('enrollments/', views.enrollments_list, name='enrollments_list'),
    path('learn/<slug:slug>/', views.learn_course, name='learn_course'),
    
    # Payments & Certificates
    path('certificates/', views.certificates_list, name='certificates_list'),
    path('certificates/verify/<str:code>/', certificate_verification_page, name='certificate-verification-page'),
    path('payments/refunds/', views.refunds_page, name='refunds_page'),
    path('payments/payouts/', views.payouts_page, name='payouts_page'),
    path('payments/receipts/<int:payment_id>/', views.payment_receipt, name='payment_receipt'),
    path('payments/history/', views.payment_history, name='payment_history'),
    path('wallet/', views.wallet_page, name='wallet_page'),
    
    # Exams
    path('exams/', views.exams_list, name='exams_list'),
    path("exams/create/", views.exam_create, name="exam_create"),
    path('exams/take/<int:exam_id>/', views.exam_take, name='exam_take'),
    path('exams/results/<int:exam_id>/', views.exam_results, name='exam_results'),
    
    # Search & Discovery
    path('search/', views.search_results, name='search_results'),
    path('browse/', views.browse_courses, name='browse_courses'),
]
