from django.urls import path
from . import views

app_name = 'exams'

urlpatterns = [
    # Question Bank
    path('questions/', views.QuestionBankListView.as_view(), name='question-list'),
    path('questions/<int:pk>/', views.QuestionBankDetailView.as_view(), name='question-detail'),
    
    # Exam Management
    path('', views.ExamListCreateView.as_view(), name='exam-list'),
    path('<int:pk>/', views.ExamDetailView.as_view(), name='exam-detail'),
    
    # Student Exam Taking
    path('course/<int:course_id>/', views.get_exam_for_course, name='course-exams'),
    path('<int:exam_id>/start/', views.start_exam, name='start-exam'),
    path('<int:exam_id>/submit/', views.submit_exam, name='submit-exam'),
    path('<int:exam_id>/attempts/', views.exam_attempts_history, name='exam-attempts'),
    path('attempt/<int:attempt_id>/result/', views.exam_result_detail, name='exam-result'),
    
    # Instructor Views
    path('<int:exam_id>/analytics/', views.exam_analytics, name='exam-analytics'),
    path('<int:exam_id>/all-attempts/', views.exam_attempts_list, name='all-attempts'),
    path('attempt/<int:attempt_id>/grade/', views.grade_manual_exam, name='grade-exam'),
    path('<int:exam_id>/publish/', views.publish_exam, name='publish-exam'),
    path('<int:exam_id>/archive/', views.archive_exam, name='archive-exam'),
]
