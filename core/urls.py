from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # Authentication pages
    path('auth/login/', views.login_page, name='login_page'),
    path('auth/register/', views.register_page, name='register_page'),
    path('auth/password-reset/', views.password_reset_page, name='password_reset_page'),
    path('auth/password-reset/confirm/', views.password_reset_confirm_page, name='password_reset_confirm_page'),
    
    # Dashboard pages
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    
    # Course pages
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    
    # Profile pages
    path('profile/', views.profile_page, name='profile_page'),
    path('settings/', views.settings_page, name='settings_page'),
    path('social/circles/', views.circles_list, name='circles_list'),
    path('social/circles/<int:circle_id>/', views.circle_detail, name='circle_detail'),
    path('events/', views.events_list, name='events_list'),
    path('events/<int:event_id>/', views.event_detail, name='event_detail'),
    path('assessments/', views.assessments_list, name='assessments_list'),
    path('assessments/<int:assessment_id>/attempt/', views.assessment_attempt, name='assessment_attempt'),
    path('assessments/<int:assessment_id>/attempt/<int:attempt_id>/', views.assessment_attempt, name='assessment_attempt_resume'),
    path('assessments/<int:assessment_id>/results/<int:attempt_id>/', views.assessment_results, name='assessment_results'),
    path('instructor/courses/', views.instructor_courses_list, name='instructor_courses_list'),
    path('instructor/courses/create/', views.instructor_course_create, name='instructor_course_create'),
    path('instructor/courses/<slug:slug>/content/', views.instructor_course_content, name='instructor_course_content'),
    path('my-courses/', views.my_courses, name='my_courses'),
    path('learn/<slug:slug>/', views.learn_course, name='learn_course'),
    
    # Payments & Certificates
    path('checkout/', views.checkout, name='checkout'),
    path('certificates/', views.certificates_list, name='certificates_list'),
    path('payments/history/', views.payment_history, name='payment_history'),
    
    # Live Sessions
    path('live/', views.live_schedule, name='live_schedule'),
    path('live/room/<int:session_id>/', views.live_room, name='live_room'),
    
    # Admin Panel
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/moderation/', views.admin_moderation, name='admin_moderation'),
    
    # Search & Discovery
    path('search/', views.search_results, name='search_results'),
    path('browse/', views.browse_courses, name='browse_courses'),
    path('analytics/instructor/', views.analytics_instructor, name='analytics_instructor'),
    path('analytics/student/', views.analytics_student, name='analytics_student'),
    path('recommendations/', views.ai_recommendations, name='ai_recommendations'),
    path('courses/<int:course_id>/resources/', views.course_resources, name='course_resources'),
    path('instructor/resources/', views.instructor_resources, name='instructor_resources'),
    path('courses/<int:course_id>/discussions/', views.discussions_list, name='discussions_list'),
    path('courses/<int:course_id>/discussions/<int:thread_id>/', views.discussion_thread, name='discussion_thread'),
]
