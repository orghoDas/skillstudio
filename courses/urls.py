"""Course API routes, mounted at /api/courses/.

API-02: everything lives in this one file (the old ``urls_extras.py`` was
included *after* this one on the same prefix, so the ``<slug:slug>/``
catch-all below shadowed routes such as ``tags/``). Order matters: all fixed
paths first, the slug catch-alls last. Course slugs can never be purely
numeric or one of the reserved words in ``courses.models.RESERVED_COURSE_SLUGS``,
so they can't collide with these routes either.
"""

from django.urls import path

from instructors.views import InstructorDashboardView

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
    LessonRetrieveUpdateView,
    # Categories & Tags
    CategoryListView, CategoryCreateView, TagListCreateView,
)
from .views_analytics import AdminCourseStatsView

urlpatterns = [
    # ===== CATEGORIES & TAGS =====
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/create/', CategoryCreateView.as_view(), name='category-create'),
    path('tags/', TagListCreateView.as_view(), name='tag-list-create'),

    # ===== COURSES =====
    path('', CourseListView.as_view(), name='course-list'),
    path('create/', CourseCreateView.as_view(), name='course-create'),
    path('instructor/courses/', InstructorCoursesView.as_view(), name='instructor-courses'),
    path('instructor/dashboard/', InstructorDashboardView.as_view(), name='courses-instructor-dashboard'),
    path('admin/course-stats/', AdminCourseStatsView.as_view(), name='admin-course-stats'),

    path('<int:id>/', CourseDetailView.as_view(), name='course-detail'),
    path('<int:id>/update/', CourseUpdateView.as_view(), name='course-update'),
    path('<int:id>/delete/', CourseDeleteView.as_view(), name='course-delete'),
    path('<int:course_id>/submit/', SubmitCourseForReviewView.as_view(), name='submit-course'),
    path('<int:course_id>/publish/', PublishCourseView.as_view(), name='publish-course'),
    path('<int:course_id>/reject/', RejectCourseView.as_view(), name='reject-course'),
    path('<int:course_id>/curriculum/', CourseCurriculumView.as_view(), name='course-curriculum'),
    path('<int:course_id>/resume/', ResumeLearningView.as_view(), name='resume-learning'),

    # ===== MODULES ("sections" in the UI) =====
    path('<int:course_id>/modules/', ModuleListView.as_view(), name='module-list'),
    path('<int:course_id>/sections/', ModuleListView.as_view(), name='course-sections'),
    path('modules/create/', ModuleCreateView.as_view(), name='module-create'),
    path('modules/<int:id>/update/', ModuleUpdateView.as_view(), name='module-update'),
    path('modules/<int:id>/delete/', ModuleDeleteView.as_view(), name='module-delete'),
    path('modules/<int:module_id>/lessons/', LessonListView.as_view(), name='lesson-list'),
    # GET/PATCH/PUT/DELETE one module (API-03: DELETE used to be a 405).
    path('sections/<int:id>/', ModuleUpdateView.as_view(), name='section-detail'),
    path('sections/<int:id>/lessons/', LessonListView.as_view(), name='section-lessons'),

    # ===== LESSONS =====
    path('lessons/create/', LessonCreateView.as_view(), name='lesson-create'),
    # Instructor editor: GET/PATCH/PUT/DELETE one lesson (API-03: DELETE used to be a 405).
    path('lessons/<int:id>/', LessonRetrieveUpdateView.as_view(), name='lesson-retrieve-update'),
    path('lessons/<int:id>/update/', LessonUpdateView.as_view(), name='lesson-update'),
    path('lessons/<int:id>/delete/', LessonDeleteView.as_view(), name='lesson-delete'),
    # Student-facing lesson content (learn page, LRN-01).
    path('lessons/<int:lesson_id>/content/', LessonDetailView.as_view(), name='lesson-content'),

    # ===== SLUG-BASED COURSE ROUTES (MUST BE LAST) =====
    path('<slug:slug>/sections/', ModuleListView.as_view(), name='course-sections-slug'),
    path('<slug:slug>/', CourseDetailView.as_view(), name='course-detail-slug'),
]
