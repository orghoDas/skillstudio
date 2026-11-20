from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import F, Q, Count, Prefetch
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.permissions import IsAdmin, IsInstructor
from accounts.utils import is_platform_admin
from courses.policies import can_view_course_catalog
from courses.permissions import CanEditCourse
from courses.services import validate_course_for_submission
from courses.progression import get_next_lesson
from enrollments.constants import ACCESS_STATUSES
from enrollments.services import require_active_enrollment

from .models import Course, Lesson, Module, Category, Tag, LessonResource
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateUpdateSerializer,
    ModuleSerializer, ModuleCreateUpdateSerializer, LessonSerializer,
    LessonCreateUpdateSerializer, CategorySerializer, TagSerializer,
    CourseCurriculumSerializer, CatalogModuleSerializer, CatalogLessonSummarySerializer,
    LessonDataSerializer, LessonResourceSerializer
)
from enrollments.models import Enrollment, LessonProgress


# ===== CATEGORY & TAG VIEWS =====

class CategoryListView(generics.ListAPIView):
    """List all categories with course counts"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class CategoryCreateView(generics.CreateAPIView):
    """Create category (admin only)"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdmin]


class TagListCreateView(generics.ListCreateAPIView):
    """List and create tags"""
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [AllowAny()]


# ===== COURSE VIEWS =====

COURSE_ORDERING_FIELDS = {'created_at', 'published_at', 'price', 'title', 'level'}


class CourseListView(generics.ListAPIView):
    """List all published courses with search and filtering"""
    serializer_class = CourseListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # Filter by instructor first (including "me" for current user)
        instructor = self.request.query_params.get('instructor')
        if instructor == 'me' and self.request.user.is_authenticated:
            # Show all courses (including drafts) for the logged-in instructor
            queryset = Course.objects.filter(instructor=self.request.user).select_related(
                'instructor', 'category'
            ).prefetch_related('modules', 'enrollments')
        elif instructor:
            # Show only published courses for other instructors
            queryset = Course.objects.filter(
                instructor__id=instructor,
                status='published'
            ).select_related('instructor', 'instructor__profile', 'category').prefetch_related('modules', 'enrollments')
        else:
            # Show only published courses for public
            queryset = Course.objects.filter(status='published').select_related(
                'instructor', 'instructor__profile', 'category'
            ).prefetch_related('modules', 'enrollments')
        
        # Search by title or description
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
        
        # Filter by level
        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)
        
        # Filter by price
        is_free = self.request.query_params.get('is_free')
        if is_free == 'true':
            queryset = queryset.filter(is_free=True)
        elif is_free == 'false':
            queryset = queryset.filter(is_free=False)
        
        # Filter by status (only for instructor=me)
        if instructor == 'me' and self.request.user.is_authenticated:
            status_filter = self.request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
        
        # Sorting. Only allow-listed fields (SEC-04): passing the raw value to
        # order_by() let anyone sort by e.g. instructor__password (a hash
        # side-channel) or crash the endpoint with an unknown field.
        sort_by = self.request.query_params.get('ordering', '-created_at')
        if sort_by == 'popular':
            queryset = queryset.annotate(
                enrollment_count=Count('enrollments', filter=Q(enrollments__status__in=ACCESS_STATUSES))
            ).order_by('-enrollment_count', '-id')
        else:
            if sort_by.lstrip('-') not in COURSE_ORDERING_FIELDS:
                sort_by = '-created_at'  # includes the old, never-implemented "rating"
            queryset = queryset.order_by(sort_by, '-id')

        return queryset


class CourseDetailView(generics.RetrieveAPIView):
    """Get single course details (by id or slug)"""
    queryset = Course.objects.select_related('instructor', 'instructor__profile', 'category').prefetch_related('tags', 'modules__lessons', 'enrollments')
    serializer_class = CourseDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'
    
    def get_object(self):
        """Support both id and slug lookups"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Try to get by slug first (if present in kwargs)
        if 'slug' in self.kwargs:
            filter_kwargs = {'slug': self.kwargs['slug']}
        else:
            # Otherwise use id
            filter_kwargs = {'id': self.kwargs['id']}
        
        obj = generics.get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only show published courses to public, or drafts to owner/admin
        if instance.status != 'published':
            if not request.user.is_authenticated:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
            # Check if user is the instructor or admin
            if is_platform_admin(request.user):
                pass  # Admins can see all courses
            elif instance.instructor.id != request.user.id:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance, context={'request': request})
        return Response(serializer.data)


class CourseCreateView(generics.CreateAPIView):
    """Create new course (instructor/admin only)"""
    serializer_class = CourseCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        user = self.request.user
        
        # Only instructors and admins can create courses
        if user.role != 'instructor' and not is_platform_admin(user):
            raise ValidationError("Only instructors can create courses.")
        
        serializer.save(instructor=user, status='draft')


class CourseUpdateView(generics.UpdateAPIView):
    """Update course (only owner can edit draft courses)"""
    queryset = Course.objects.all()
    serializer_class = CourseCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        course = super().get_object()
        
        # Only course owner can update
        if course.instructor != self.request.user:
            raise ValidationError("You don't have permission to edit this course.")

        if course.status not in ['draft', 'under_review']:
            raise ValidationError("Cannot edit published or archived courses.")
        
        return course

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_update(serializer)
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        # Ensure instructor is set to current user
        serializer.save(instructor=self.request.user)


class CourseDeleteView(generics.DestroyAPIView):
    """Delete course (only owner can delete draft courses)"""
    queryset = Course.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        course = super().get_object()
        
        if course.instructor != self.request.user:
            raise ValidationError("You don't have permission to delete this course.")
        
        if course.status != 'draft':
            raise ValidationError("Only draft courses can be deleted.")
        
        return course


class InstructorCoursesView(generics.ListAPIView):
    """List all courses by logged-in instructor"""
    serializer_class = CourseListSerializer
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def get_queryset(self):
        # BUG-02: the old try/except wrappers referenced an un-imported
        # `logging` (NameError) and turned every error into a vague 500.
        # DRF's exception handler already logs and reports real errors.
        return Course.objects.filter(instructor=self.request.user).select_related(
            'category', 'instructor__profile'
        ).order_by('-created_at', '-id')


# ===== MODULE VIEWS =====

class ModuleListView(generics.ListCreateAPIView):
    """List and create modules for a course (supports both course_id and slug)"""
    serializer_class = ModuleSerializer
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_course(self):
        if 'slug' in self.kwargs:
            course = get_object_or_404(Course, slug=self.kwargs['slug'])
        else:
            course = get_object_or_404(Course, id=self.kwargs['course_id'])

        if self.request.method in SAFE_METHODS and not can_view_course_catalog(self.request.user, course):
            raise PermissionDenied("You don't have permission to view this course curriculum.")

        return course

    def get_queryset(self):
        course = self.get_course()
        return Module.objects.filter(course=course).prefetch_related('lessons').order_by('position')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ModuleCreateUpdateSerializer
        return CatalogModuleSerializer
    
    def perform_create(self, serializer):
        course = self.get_course()
        
        # Check permissions
        if course.instructor != self.request.user:
            raise ValidationError("You don't have permission to add modules to this course.")
        
        if course.status not in ['draft', 'under_review']:
            raise ValidationError("Cannot add modules to published courses.")
        
        serializer.save(course=course)


class ModuleCreateView(generics.CreateAPIView):
    """Create module (instructor only)"""
    serializer_class = ModuleCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        course = serializer.validated_data.get('course')
        if course is None:  # SEC-05: used to be a KeyError -> 500
            raise ValidationError({'course': 'This field is required.'})
        
        if course.instructor != self.request.user:
            raise ValidationError("You don't have permission to add modules to this course.")
        
        if course.status not in ['draft', 'under_review']:
            raise ValidationError("Cannot add modules to published courses.")
        
        serializer.save()


class ModuleUpdateView(generics.UpdateAPIView):
    """Update module"""
    queryset = Module.objects.all()
    serializer_class = ModuleCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        module = super().get_object()
        
        if module.course.instructor != self.request.user:
            raise ValidationError("You don't have permission to edit this module.")
        
        if module.course.status not in ['draft', 'under_review']:
            raise ValidationError("Cannot edit modules in published courses.")
        
        return module


class ModuleDeleteView(generics.DestroyAPIView):
    """Delete module"""
    queryset = Module.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        module = super().get_object()
        
        if module.course.instructor != self.request.user:
            raise ValidationError("You don't have permission to delete this module.")
        
        if module.course.status != 'draft':
            raise ValidationError("Cannot delete modules in non-draft courses.")
        
        return module


# ===== LESSON VIEWS =====

class LessonListView(generics.ListCreateAPIView):
    """List and create lessons for a module/section"""
    serializer_class = LessonSerializer
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_module(self):
        module_id = self.kwargs.get('module_id') or self.kwargs.get('id')
        module = get_object_or_404(Module.objects.select_related('course'), id=module_id)

        if self.request.method in SAFE_METHODS and not can_view_course_catalog(self.request.user, module.course):
            raise PermissionDenied("You don't have permission to view this course curriculum.")

        return module
    
    def get_queryset(self):
        module = self.get_module()
        return Lesson.objects.filter(module=module).select_related('module__course').order_by('position')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LessonCreateUpdateSerializer
        return CatalogLessonSummarySerializer
    
    def perform_create(self, serializer):
        module = self.get_module()
        
        # Check permissions
        if module.course.instructor != self.request.user:
            raise ValidationError("You don't have permission to add lessons to this module.")
        
        if module.course.status not in ['draft', 'under_review']:
            raise ValidationError("Cannot add lessons to published courses.")
        
        serializer.save(module=module)


class LessonCreateView(generics.CreateAPIView):
    """Create lesson"""
    serializer_class = LessonCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        module = serializer.validated_data.get('module')
        if module is None:  # SEC-05: used to be a KeyError -> 500
            raise ValidationError({'module': 'This field is required.'})
        
        if module.course.instructor != self.request.user:
            raise ValidationError("You don't have permission to add lessons.")

        if module.course.status not in ['draft', 'under_review']:
            raise ValidationError("Cannot add lessons to published courses.")
        
        serializer.save()


class LessonUpdateView(generics.UpdateAPIView):
    """Update lesson"""
    queryset = Lesson.objects.all()
    serializer_class = LessonCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        lesson = super().get_object()
        
        if lesson.module.course.instructor != self.request.user:
            raise ValidationError("You don't have permission to edit this lesson.")
        
        if lesson.module.course.status not in ['draft', 'under_review']:
            raise ValidationError("Cannot edit lessons in published courses.")
        
        return lesson


class LessonRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve and update lesson for instructor editor"""
    queryset = Lesson.objects.all()
    serializer_class = LessonCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        lesson = super().get_object()
        
        if lesson.module.course.instructor != self.request.user:
            raise ValidationError("You don't have permission to edit this lesson.")

        if lesson.module.course.status not in ['draft', 'under_review']:
            raise ValidationError("Cannot edit lessons in published courses.")
        
        return lesson


class LessonDeleteView(generics.DestroyAPIView):
    """Delete lesson"""
    queryset = Lesson.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        lesson = super().get_object()
        
        if lesson.module.course.instructor != self.request.user:
            raise ValidationError("You don't have permission to delete this lesson.")
        
        if lesson.module.course.status != 'draft':
            raise ValidationError("Cannot delete lessons in non-draft courses.")
        
        return lesson


class LessonDetailView(APIView):
    """Full lesson content for studying it (the learn page).

    Mounted at /api/courses/lessons/<id>/content/ (LRN-01). Access:
    * the course must be visible (published, or you own/administer it);
    * free lessons and free courses: anyone who can see the course;
    * otherwise: the owner, an admin, or a student who owns the course
      (active or completed enrollment) and has unlocked the lesson
      (enrollments.services.lesson_lock_state).
    """
    permission_classes = [AllowAny]

    def get(self, request, lesson_id):
        from courses.policies import can_manage_course
        from enrollments.services import get_access_enrollment, lesson_lock_state

        lesson = get_object_or_404(
            Lesson.objects.select_related('module__course').prefetch_related('resources'), id=lesson_id
        )
        course = lesson.module.course
        user = request.user

        if not can_view_course_catalog(user, course):
            return Response({'error': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not (lesson.is_free or course.is_free or can_manage_course(user, course)):
            if not user.is_authenticated:
                return Response({'error': 'Login required.', 'code': 'login_required'},
                                status=status.HTTP_403_FORBIDDEN)
            enrollment = get_access_enrollment(user, course)
            if enrollment is None:
                return Response({'error': 'Enroll in this course to access this lesson.', 'code': 'not_enrolled'},
                                status=status.HTTP_403_FORBIDDEN)
            if lesson_lock_state(enrollment).get(lesson.id):
                return Response({'error': 'Lesson is locked. Complete the previous lessons first.',
                                 'code': 'lesson_locked'}, status=status.HTTP_403_FORBIDDEN)

        # Count only views that actually got the content.
        Lesson.objects.filter(id=lesson.id).update(view_count=F('view_count') + 1)
        return Response(LessonDataSerializer(lesson).data)


class CourseCurriculumView(APIView):
    """Course outline with per-lesson ``is_completed`` / ``is_locked``.

    Uses the same progression rule as LessonDetailView, so what the learn
    page shows as unlocked is exactly what the content endpoint serves.
    """
    permission_classes = [AllowAny]

    def get(self, request, course_id):
        from courses.policies import can_manage_course
        from enrollments.services import (
            completed_lesson_ids, get_access_enrollment, lesson_lock_state, ordered_course_lessons,
        )

        user = request.user
        course = get_object_or_404(Course.objects.prefetch_related('modules__lessons'), id=course_id)
        if not can_view_course_catalog(user, course):
            return Response({'error': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)

        enrollment = get_access_enrollment(user, course)
        if not (course.is_free or enrollment or can_manage_course(user, course)):
            if not user.is_authenticated:
                return Response({'error': 'Login required'}, status=status.HTTP_403_FORBIDDEN)
            return Response({'error': 'Active enrollment required'}, status=status.HTTP_403_FORBIDDEN)

        lessons = ordered_course_lessons(course)
        completed_ids = completed_lesson_ids(enrollment)
        locked = lesson_lock_state(enrollment, lessons, completed_ids)

        serializer = CourseCurriculumSerializer(
            course,
            context={
                'completed_ids': completed_ids,
                'locked_ids': {lesson_id for lesson_id, is_locked in locked.items() if is_locked},
            }
        )
        return Response(serializer.data)


# ===== COURSE SUBMISSION & REVIEW =====

class SubmitCourseForReviewView(APIView):
    """Submit course for admin review"""
    permission_classes = [IsAuthenticated, CanEditCourse]

    def post(self, request, course_id):
        user = request.user

        course = Course.objects.filter(
            id=course_id,
            instructor=user
        ).first()

        if not course:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)

        if course.status != 'draft':
            raise ValidationError("Only draft courses can be submitted.")

        validate_course_for_submission(course)

        course.status = 'under_review'
        course.submitted_for_review_at = timezone.now()
        course.save(update_fields=['status', 'submitted_for_review_at'])

        return Response({
            "message": "Course submitted for review.",
            "status": course.status
        })


class PublishCourseView(APIView):
    """Publish course (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        if course.status != 'under_review':
            raise ValidationError("Course is not under review.")

        course.status = 'published'
        course.published_at = timezone.now()
        course.reviewed_at = timezone.now()
        course.reviewed_by = request.user
        course.rejection_reason = ""

        course.save(update_fields=[
            'status',
            'published_at',
            'reviewed_at',
            'reviewed_by',
            'rejection_reason'
        ])

        return Response({
            "message": "Course published successfully."
        })


class RejectCourseView(APIView):
    """Reject course (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        reason = request.data.get('reason', '').strip()

        if course.status != 'under_review':
            raise ValidationError("Course is not under review.")

        if not reason:
            raise ValidationError("Rejection reason is required.")

        course.status = 'draft'
        course.rejection_reason = reason
        course.reviewed_at = timezone.now()
        course.reviewed_by = request.user

        course.save(update_fields=[
            'status',
            'rejection_reason',
            'reviewed_at',
            'reviewed_by'
        ])

        return Response({
            "message": "Course rejected and returned to draft.",
            "reason": reason
        })


class ResumeLearningView(APIView):
    """Get next lesson for user to continue learning"""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)
        enrollment = require_active_enrollment(user, course)
        lesson = get_next_lesson(enrollment)

        if not lesson:
            return Response({
                'completed': True,
                'message': "You have completed all lessons in this course."
            })
        
        return Response({
            'lesson_id': lesson.id,
            'lesson_title': lesson.title,
            'module_title': lesson.module.title,
        })
