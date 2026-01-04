from django.urls import path
from .views import (
    # Curriculum & Learning
    CourseCurriculumView, LessonDetailView, ResumeLearningView,
    # Course CRUD
    CourseListView, CourseDetailView, CourseCreateView,
    CourseUpdateView, CourseDeleteView, InstructorCoursesView,
    # Course Submission & Publishing
    SubmitCourseForReviewView, PublishCourseView, RejectCourseView,
    # Module CRUD
    ModuleListView, ModuleCreateView, ModuleUpdateView, ModuleDeleteView,
    # Lesson CRUD
    LessonListView, LessonCreateView, LessonUpdateView, LessonDeleteView,
    # Categories & Tags
    CategoryListView, CategoryCreateView, TagListCreateView,
)
from .views_reviews import (
    CourseReviewListView, CourseReviewCreateView, ReviewUpdateView,
    ReviewDeleteView, CourseRatingStatsView
)
from .views_analytics import AdminCourseStatsView
from instructors.views import InstructorDashboardView
from analytics.views import InstructorCourseAnalyticsView as CourseAnalyticsView

urlpatterns = [
    # ===== COURSE ENDPOINTS =====
    path('', CourseListView.as_view(), name='course-list'),
    path('<int:id>/', CourseDetailView.as_view(), name='course-detail'),
    path('create/', CourseCreateView.as_view(), name='course-create'),
    path('<int:id>/update/', CourseUpdateView.as_view(), name='course-update'),
    path('<int:id>/delete/', CourseDeleteView.as_view(), name='course-delete'),
    
    # Course Submission & Publishing
    path('<int:course_id>/submit/', SubmitCourseForReviewView.as_view(), name='submit-course'),
    path('<int:course_id>/publish/', PublishCourseView.as_view(), name='publish-course'),
    path('<int:course_id>/reject/', RejectCourseView.as_view(), name='reject-course'),
    
    # Course Curriculum & Learning
    path('<int:course_id>/curriculum/', CourseCurriculumView.as_view(), name='course-curriculum'),
    path('<int:course_id>/resume/', ResumeLearningView.as_view(), name='resume-learning'),
    
    # ===== MODULE ENDPOINTS =====
    path('<int:course_id>/modules/', ModuleListView.as_view(), name='module-list'),
    
    # ===== REVIEW & RATING ENDPOINTS =====
    path('<int:course_id>/reviews/', CourseReviewListView.as_view(), name='course-reviews'),
    path('<int:course_id>/reviews/create/', CourseReviewCreateView.as_view(), name='create-review'),
    path('<int:course_id>/rating-stats/', CourseRatingStatsView.as_view(), name='course-rating-stats'),
    
    # ===== ANALYTICS ENDPOINTS =====
    path('<int:course_id>/analytics/', CourseAnalyticsView.as_view(), name='course-analytics'),
]