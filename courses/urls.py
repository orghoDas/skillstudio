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
    path('api/courses/', CourseListView.as_view(), name='course-list'),
    path('api/courses/<int:id>/', CourseDetailView.as_view(), name='course-detail'),
    path('api/courses/create/', CourseCreateView.as_view(), name='course-create'),
    path('api/courses/<int:id>/update/', CourseUpdateView.as_view(), name='course-update'),
    path('api/courses/<int:id>/delete/', CourseDeleteView.as_view(), name='course-delete'),
    path('api/instructor/courses/', InstructorCoursesView.as_view(), name='instructor-courses'),
    
    # Course Submission & Publishing
    path('api/courses/<int:course_id>/submit/', SubmitCourseForReviewView.as_view(), name='submit-course'),
    path('api/courses/<int:course_id>/publish/', PublishCourseView.as_view(), name='publish-course'),
    path('api/courses/<int:course_id>/reject/', RejectCourseView.as_view(), name='reject-course'),
    
    # Course Curriculum & Learning
    path('api/courses/<int:course_id>/curriculum/', CourseCurriculumView.as_view(), name='course-curriculum'),
    path('api/courses/<int:course_id>/resume/', ResumeLearningView.as_view(), name='resume-learning'),
    
    # ===== MODULE ENDPOINTS =====
    path('api/courses/<int:course_id>/modules/', ModuleListView.as_view(), name='module-list'),
    path('api/modules/create/', ModuleCreateView.as_view(), name='module-create'),
    path('api/modules/<int:id>/update/', ModuleUpdateView.as_view(), name='module-update'),
    path('api/modules/<int:id>/delete/', ModuleDeleteView.as_view(), name='module-delete'),
    
    # ===== LESSON ENDPOINTS =====
    path('api/modules/<int:module_id>/lessons/', LessonListView.as_view(), name='lesson-list'),
    path('api/lessons/<int:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('api/lessons/create/', LessonCreateView.as_view(), name='lesson-create'),
    path('api/lessons/<int:id>/update/', LessonUpdateView.as_view(), name='lesson-update'),
    path('api/lessons/<int:id>/delete/', LessonDeleteView.as_view(), name='lesson-delete'),
    
    # ===== CATEGORY & TAG ENDPOINTS =====
    path('api/categories/', CategoryListView.as_view(), name='category-list'),
    path('api/categories/create/', CategoryCreateView.as_view(), name='category-create'),
    path('api/tags/', TagListCreateView.as_view(), name='tag-list-create'),
    
    # ===== REVIEW & RATING ENDPOINTS =====
    path('api/courses/<int:course_id>/reviews/', CourseReviewListView.as_view(), name='course-reviews'),
    path('api/courses/<int:course_id>/reviews/create/', CourseReviewCreateView.as_view(), name='create-review'),
    path('api/reviews/<int:id>/update/', ReviewUpdateView.as_view(), name='update-review'),
    path('api/reviews/<int:id>/delete/', ReviewDeleteView.as_view(), name='delete-review'),
    path('api/courses/<int:course_id>/rating-stats/', CourseRatingStatsView.as_view(), name='course-rating-stats'),
    
    # ===== ANALYTICS ENDPOINTS =====
    path('api/courses/<int:course_id>/analytics/', CourseAnalyticsView.as_view(), name='course-analytics'),
    path('api/instructor/dashboard/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
    path('api/admin/course-stats/', AdminCourseStatsView.as_view(), name='admin-course-stats'),
]