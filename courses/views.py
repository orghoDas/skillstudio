from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F, Q, Count, Sum
from django.db.models.functions import Coalesce
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.permissions import IsAdmin, IsInstructor
from core.query_params import optional_id
from courses.policies import can_access_course_content, can_manage_course, can_view_course_catalog
from courses.services import course_learner_count, lock_course_for_edit, lock_draft_for_deletion, start_new_version, transition
from enrollments.services import (
    get_access_enrollment, get_resume_lesson, lesson_lock_state, ordered_course_lessons, require_active_enrollment,
)

from .models import Course, Lesson, Module, Category, Tag
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateUpdateSerializer,
    ModuleSerializer, ModuleCreateUpdateSerializer, LessonSerializer,
    LessonCreateUpdateSerializer, CategorySerializer, TagSerializer,
    CourseCurriculumSerializer, CatalogModuleSerializer, CatalogLessonSummarySerializer,
    LessonDataSerializer
)


# ===== CATEGORY & TAG VIEWS =====

class CategoryListView(generics.ListAPIView):
    """List all categories with course counts"""
    queryset = Category.objects.annotate(
        course_count=Count('courses', filter=Q(courses__status='published')),
    ).order_by('name', 'pk')
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class CategoryCreateView(generics.CreateAPIView):
    """Create category (admin only)"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdmin]


class TagListCreateView(generics.ListCreateAPIView):
    """List and create tags"""
    queryset = Tag.objects.order_by('name', 'pk')
    serializer_class = TagSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [AllowAny()]


# ===== COURSE VIEWS =====

COURSE_ORDERING_FIELDS = {'created_at', 'published_at', 'price', 'title', 'level'}
# Course-length filter buckets in hours: (min inclusive, max exclusive or None).
DURATION_BUCKETS = {'0-2': (0, 2), '2-5': (2, 5), '5-10': (5, 10), '10+': (10, None)}


def _csv_param(value):
    """Split a comma-separated query value into a clean list."""
    return [part.strip() for part in (value or '').split(',') if part.strip()]


class CoursePagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 100


def _with_course_counts(queryset):
    return queryset.select_related('instructor__profile', 'category').annotate(
        enrollments_count=course_learner_count(),
        module_count=Count('modules', distinct=True),
        lesson_count=Count('modules__lessons', distinct=True),
    )


class CourseListView(generics.ListAPIView):
    """List all published courses with search and filtering"""
    serializer_class = CourseListSerializer
    permission_classes = [AllowAny]
    pagination_class = CoursePagination

    def get_queryset(self):
        # Filter by instructor first (including "me" for current user)
        instructor = self.request.query_params.get('instructor')
        if instructor == 'me' and self.request.user.is_authenticated:
            # Show all courses (including drafts) for the logged-in instructor
            queryset = Course.objects.filter(instructor=self.request.user)
        elif instructor and instructor.isascii() and instructor.isdecimal():
            # Show only published courses for other instructors
            queryset = Course.objects.filter(
                instructor_id=optional_id(self.request.query_params, 'instructor'),
                status='published'
            )
        else:
            # Show only published courses for public
            queryset = Course.objects.filter(status='published')
        
        # Search by title or description
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        
        # Filter by category / level: one value or a comma-separated list.
        categories = _csv_param(self.request.query_params.get('category'))
        if categories:
            queryset = queryset.filter(category__slug__in=categories)

        levels = _csv_param(self.request.query_params.get('level'))
        if levels:
            queryset = queryset.filter(level__in=levels)

        # Filter by total video/lesson length in hours: comma-separated
        # buckets "0-2", "2-5", "5-10", "10+" (used by the search page).
        durations = [b for b in _csv_param(self.request.query_params.get('duration')) if b in DURATION_BUCKETS]
        if durations:
            queryset = queryset.annotate(
                total_seconds=Coalesce(Sum('modules__lessons__duration_seconds'), 0)
            )
            duration_q = Q()
            for bucket in durations:
                low, high = DURATION_BUCKETS[bucket]
                cond = Q(total_seconds__gte=low * 3600)
                if high is not None:
                    cond &= Q(total_seconds__lt=high * 3600)
                duration_q |= cond
            queryset = queryset.filter(duration_q)
        
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
        if sort_by in ('rating', '-rating'):
            raise ValidationError({'ordering': 'Course rating order is unavailable.'})
        queryset = _with_course_counts(queryset)
        if sort_by == 'popular':
            return queryset.order_by('-enrollments_count', '-id')
        if sort_by.removeprefix('-') not in COURSE_ORDERING_FIELDS:
            sort_by = '-created_at'
        return queryset.order_by(sort_by, '-id')


class CourseDetailView(generics.RetrieveAPIView):
    """Get single course details (by id or slug)"""
    queryset = Course.objects.select_related(
        'instructor', 'instructor__profile', 'category', 'current_version',
    ).prefetch_related('tags', 'modules__lessons').annotate(
        enrollments_count=course_learner_count(),
    )
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
        enrollment = get_access_enrollment(request.user, instance)
        is_enrolled = enrollment is not None
        
        if not can_view_course_catalog(request.user, instance, is_enrolled=is_enrolled):
            if not request.user.is_authenticated:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        lessons = [lesson for module in instance.modules.all() for lesson in module.lessons.all()]
        if not can_access_course_content(request.user, instance, is_enrolled=is_enrolled):
            locks = {lesson.pk: not lesson.is_free for lesson in lessons}
        else:
            learner_enrollment = None if can_manage_course(request.user, instance) else enrollment
            locks = lesson_lock_state(learner_enrollment, lessons)
        context = self.get_serializer_context()
        context.update(is_enrolled=is_enrolled, lesson_locks_by_course={instance.pk: locks})
        serializer = self.get_serializer(instance, context=context)
        return Response(serializer.data)


def require_course_manager(user, course):
    if not can_manage_course(user, course):
        raise PermissionDenied("You do not have permission to manage this course.")


def prepare_course_edit(course, user):
    try:
        return lock_course_for_edit(course, user)
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages[0]) from exc


class CourseOwnedObjectMixin:
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lock_for_mutation = staticmethod(prepare_course_edit)

    def get_object(self):
        obj = super().get_object()
        course = self.get_object_course(obj)
        require_course_manager(self.request.user, course)
        if self.request.method in SAFE_METHODS:
            return obj

        locked_course = self.lock_for_mutation(course, self.request.user)
        if obj is course:
            return locked_course
        # A previous request can remove the child while this request waits for
        # the course lock. Read it again before allowing DRF to save or delete.
        return super().get_object()

    def get_object_course(self, obj):
        return obj

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class CourseCreateView(generics.CreateAPIView):
    """Create new course (instructor/admin only)."""
    serializer_class = CourseCreateUpdateSerializer
    permission_classes = [IsAuthenticated, IsInstructor]

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user, status='draft')


class CourseUpdateView(CourseOwnedObjectMixin, generics.UpdateAPIView):
    """Update details, returning an edited review to draft."""
    queryset = Course.objects.all()
    serializer_class = CourseCreateUpdateSerializer


class CourseDeleteView(CourseOwnedObjectMixin, generics.DestroyAPIView):
    """Delete a draft course as its instructor or a platform admin."""
    queryset = Course.objects.all()

    @staticmethod
    def lock_for_mutation(course, user):
        try:
            return lock_draft_for_deletion(course, user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages[0]) from exc


class InstructorCoursesView(generics.ListAPIView):
    """List all courses by logged-in instructor"""
    serializer_class = CourseListSerializer
    permission_classes = [IsAuthenticated, IsInstructor]
    pagination_class = CoursePagination
    
    def get_queryset(self):
        # BUG-02: the old try/except wrappers referenced an un-imported
        # `logging` (NameError) and turned every error into a vague 500.
        # DRF's exception handler already logs and reports real errors.
        return _with_course_counts(Course.objects.filter(instructor=self.request.user)).order_by('-created_at', '-id')


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
        return Module.objects.filter(course=course).prefetch_related('lessons')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ModuleCreateUpdateSerializer
        return CatalogModuleSerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        course = prepare_course_edit(self.get_course(), self.request.user)
        serializer.save(course=course)


class ModuleCreateView(generics.CreateAPIView):
    """Create a module in a manageable course."""
    serializer_class = ModuleCreateUpdateSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):
        course = serializer.validated_data.get('course')
        if course is None:
            raise ValidationError({'course': 'This field is required.'})
        course = prepare_course_edit(course, self.request.user)
        serializer.save(course=course)


class ModuleOwnedObjectMixin(CourseOwnedObjectMixin):
    queryset = Module.objects.select_related('course')

    def get_object_course(self, obj):
        return obj.course


class ModuleUpdateView(ModuleOwnedObjectMixin, generics.RetrieveUpdateDestroyAPIView):
    """Read, update or delete a module through the section editor."""
    serializer_class = ModuleCreateUpdateSerializer


class ModuleDeleteView(ModuleOwnedObjectMixin, generics.DestroyAPIView):
    """Delete a module."""


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
        return Lesson.objects.filter(module=module).select_related('module__course')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LessonCreateUpdateSerializer
        return CatalogLessonSummarySerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        module = self.get_module()
        course = prepare_course_edit(module.course, self.request.user)
        serializer.save(module=get_object_or_404(Module, pk=module.pk, course=course))


class LessonCreateView(generics.CreateAPIView):
    """Create a lesson."""
    serializer_class = LessonCreateUpdateSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):
        module = serializer.validated_data.get('module')
        if module is None:
            raise ValidationError({'module': 'This field is required.'})
        course = prepare_course_edit(module.course, self.request.user)
        serializer.save(module=get_object_or_404(Module, pk=module.pk, course=course))


class LessonOwnedObjectMixin(CourseOwnedObjectMixin):
    queryset = Lesson.objects.select_related('module__course')

    def get_object_course(self, obj):
        return obj.module.course


class LessonUpdateView(LessonOwnedObjectMixin, generics.UpdateAPIView):
    """Update a lesson."""
    serializer_class = LessonCreateUpdateSerializer


class LessonRetrieveUpdateView(LessonOwnedObjectMixin, generics.RetrieveUpdateDestroyAPIView):
    """Read, update or delete a lesson through the course editor."""
    serializer_class = LessonCreateUpdateSerializer


class LessonDeleteView(LessonOwnedObjectMixin, generics.DestroyAPIView):
    """Delete a lesson."""


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
    serializer_class = LessonDataSerializer

    def get(self, request, lesson_id):
        from courses.policies import can_access_lesson
        from enrollments.services import get_access_enrollment, require_unlocked_lesson

        lesson = get_object_or_404(
            Lesson.objects.select_related('module__course').prefetch_related('resources'), id=lesson_id
        )
        course = lesson.module.course
        user = request.user

        if not can_view_course_catalog(user, course):
            return Response({'error': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not can_access_lesson(user, lesson):
            if not user.is_authenticated:
                return Response({'error': 'Login required.', 'code': 'login_required'},
                                status=status.HTTP_403_FORBIDDEN)
            return Response({'error': 'Enroll in this course to access this lesson.', 'code': 'not_enrolled'},
                            status=status.HTTP_403_FORBIDDEN)

        # Progression applies to enrolled students (free or paid course alike),
        # exactly as the curriculum shows it; owners/admins are never locked.
        if not can_manage_course(user, course):
            enrollment = get_access_enrollment(user, course)
            require_unlocked_lesson(enrollment, lesson)

        # Count only views that actually got the content.
        Lesson.objects.filter(id=lesson.id).update(view_count=F('view_count') + 1)
        return Response(LessonDataSerializer(lesson).data)


class CourseCurriculumView(APIView):
    """Course outline with per-lesson ``is_completed`` / ``is_locked``.

    Uses the same progression rule as LessonDetailView, so what the learn
    page shows as unlocked is exactly what the content endpoint serves.
    """
    permission_classes = [AllowAny]
    serializer_class = CourseCurriculumSerializer

    def get(self, request, course_id):
        from courses.policies import can_access_course_content
        from enrollments.services import (
            completed_lesson_ids, get_access_enrollment, lesson_lock_state, ordered_course_lessons,
        )

        user = request.user
        course = get_object_or_404(Course.objects.prefetch_related('modules__lessons'), id=course_id)
        if not can_view_course_catalog(user, course):
            return Response({'error': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not can_access_course_content(user, course):
            if not user.is_authenticated:
                return Response({'error': 'Login required'}, status=status.HTTP_403_FORBIDDEN)
            return Response({'error': 'Active enrollment required'}, status=status.HTTP_403_FORBIDDEN)

        # Owners/admins see nothing locked; students see their own progression.
        enrollment = None if can_manage_course(user, course) else get_access_enrollment(user, course)

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
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        user = request.user

        course = get_object_or_404(Course, id=course_id)
        require_course_manager(user, course)

        try:
            course = transition(course, 'under_review', user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages[0]) from exc

        return Response({
            "message": "Course submitted for review.",
            "status": course.status
        })


class PublishCourseView(APIView):
    """Publish course (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        try:
            transition(course, 'published', request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages[0]) from exc

        return Response({
            "message": "Course published successfully."
        })


class RejectCourseView(APIView):
    """Reject course (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        raw_reason = request.data.get('reason')
        reason = raw_reason.strip() if isinstance(raw_reason, str) else ''

        try:
            transition(course, 'draft', request.user, reason=reason)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages[0]) from exc

        return Response({
            "message": "Course rejected and returned to draft.",
            "reason": reason
        })


class ArchiveCourseView(APIView):
    """Remove a published course from the catalog, retaining learner access."""
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        try:
            course = transition(course, 'archived', request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages[0]) from exc
        return Response({'status': course.status, 'message': 'Course archived.'})


class NewCourseVersionView(APIView):
    """Create or resume a private revision of a published course."""
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        source = get_object_or_404(Course, id=course_id)
        try:
            draft, created = start_new_version(source, request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages[0]) from exc
        return Response(
            {'id': draft.pk, 'slug': draft.slug, 'status': draft.status, 'revision_of': source.pk},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ResumeLearningView(APIView):
    """Get next lesson for user to continue learning"""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)
        if not can_view_course_catalog(user, course):
            return Response({'error': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)
        enrollment = require_active_enrollment(user, course)
        lesson = get_resume_lesson(enrollment, lessons=ordered_course_lessons(course))

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
