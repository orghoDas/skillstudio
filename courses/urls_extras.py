from django.urls import path
from .views import (
    ModuleCreateView, ModuleUpdateView, ModuleDeleteView,
    LessonDetailView, LessonCreateView, LessonUpdateView, LessonDeleteView, LessonListView,
    CategoryListView, CategoryCreateView, TagListCreateView,
    InstructorCoursesView,
)
from .views_reviews import ReviewUpdateView, ReviewDeleteView
from instructors.views import InstructorDashboardView
from .views_analytics import AdminCourseStatsView

urlpatterns = [
    # Module management (not course-specific)
    path('modules/create/', ModuleCreateView.as_view(), name='module-create'),
    path('modules/<int:id>/update/', ModuleUpdateView.as_view(), name='module-update'),
    path('modules/<int:id>/delete/', ModuleDeleteView.as_view(), name='module-delete'),
    
    # Lesson management
    path('modules/<int:module_id>/lessons/', LessonListView.as_view(), name='lesson-list'),
    path('lessons/<int:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('lessons/create/', LessonCreateView.as_view(), name='lesson-create'),
    path('lessons/<int:id>/update/', LessonUpdateView.as_view(), name='lesson-update'),
    path('lessons/<int:id>/delete/', LessonDeleteView.as_view(), name='lesson-delete'),
    
    # Categories & Tags
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/create/', CategoryCreateView.as_view(), name='category-create'),
    path('tags/', TagListCreateView.as_view(), name='tag-list-create'),
    
    # Reviews (not course-specific)
    path('reviews/<int:id>/update/', ReviewUpdateView.as_view(), name='update-review'),
    path('reviews/<int:id>/delete/', ReviewDeleteView.as_view(), name='delete-review'),
    
    # Instructor routes
    path('instructor/courses/', InstructorCoursesView.as_view(), name='instructor-courses'),
    path('instructor/dashboard/', InstructorDashboardView.as_view(), name='instructor-dashboard-api'),
    
    # Admin
    path('admin/course-stats/', AdminCourseStatsView.as_view(), name='admin-course-stats'),
]
