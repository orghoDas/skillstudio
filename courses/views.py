from django.utils import timezone
from django.forms import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import F, Q, Avg, Count, Prefetch
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly

from accounts.permissions import IsAdmin, IsInstructor
from courses.permissions import CanEditCourse
from courses.services import validate_course_for_submission
from enrollments.services import get_next_lesson, require_active_enrollment

from .models import Course, Lesson, Module, Category, Tag, LessonResource
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateUpdateSerializer,
    ModuleSerializer, ModuleCreateUpdateSerializer, LessonSerializer,
    LessonCreateUpdateSerializer, CategorySerializer, TagSerializer,
    CourseCurriculumSerializer, LessonDataSerializer, LessonResourceSerializer
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

class CourseListView(generics.ListAPIView):
    """List all published courses with search and filtering"""
    serializer_class = CourseListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
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
        
        # Filter by instructor
        instructor = self.request.query_params.get('instructor')
        if instructor:
            queryset = queryset.filter(instructor__id=instructor)
        
        # Sorting
        sort_by = self.request.query_params.get('sort_by', '-published_at')
        if sort_by == 'popular':
            queryset = queryset.annotate(
                enrollment_count=Count('enrollments', filter=Q(enrollments__status='active'))
            ).order_by('-enrollment_count')
        elif sort_by == 'rating':
            queryset = queryset.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
        else:
            queryset = queryset.order_by(sort_by)
        
        return queryset


class CourseDetailView(generics.RetrieveAPIView):
    """Get course details"""
    queryset = Course.objects.select_related('instructor', 'instructor__profile', 'category').prefetch_related('tags', 'modules__lessons')
    serializer_class = CourseDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only show published courses to public, or drafts to owner/admin
        if instance.status != 'published':
            if not request.user.is_authenticated:
                return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
            if instance.instructor != request.user and request.user.role != 'admin':
                return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(instance, context={'request': request})
        return Response(serializer.data)


class CourseCreateView(generics.CreateAPIView):
    """Create new course (instructor/admin only)"""
    serializer_class = CourseCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        user = self.request.user
        
        # Only instructors and admins can create courses
        if user.role not in ['instructor', 'admin']:
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
        
        # Only drafts can be edited
        if course.status not in ['draft', 'under_review']:
            raise ValidationError("Only draft or under review courses can be edited.")
        
        return course


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
        return Course.objects.filter(instructor=self.request.user).select_related(
            'category', 'instructor__profile'
        ).order_by('-created_at')


# ===== MODULE VIEWS =====

class ModuleListView(generics.ListAPIView):
    """List modules for a course"""
    serializer_class = ModuleSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        course_id = self.kwargs['course_id']
        return Module.objects.filter(course_id=course_id).prefetch_related('lessons').order_by('position')


class ModuleCreateView(generics.CreateAPIView):
    """Create module (instructor only)"""
    serializer_class = ModuleCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        
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

class LessonListView(generics.ListAPIView):
    """List lessons for a module"""
    serializer_class = LessonSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        module_id = self.kwargs['module_id']
        return Lesson.objects.filter(module_id=module_id).prefetch_related('resources').order_by('position')


class LessonCreateView(generics.CreateAPIView):
    """Create lesson"""
    serializer_class = LessonCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        module = serializer.validated_data['module']
        
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
    """Get detailed lesson content (with enrollment check)"""

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson.objects.select_related('module__course').prefetch_related('resources'), id=lesson_id)
        course = lesson.module.course
        user = request.user

        # Increment view count
        Lesson.objects.filter(id=lesson.id).update(view_count=F('view_count') + 1)

        # Free lesson → public access
        if lesson.is_free:
            return Response(LessonDataSerializer(lesson).data)

        # Protected lesson requires authentication
        if not user.is_authenticated:
            return Response({'error': 'Login required'}, status=status.HTTP_403_FORBIDDEN)

        # Check enrollment
        enrollment = require_active_enrollment(user, course)

        # Check if lesson is unlocked (progression system)
        previous_lessons = Lesson.objects.filter(
            module__course=course,
            module__position__lt=lesson.module.position
        ) | Lesson.objects.filter(
            module=lesson.module,
            position__lt=lesson.position
        )

        total_previous = previous_lessons.count()
        if total_previous > 0:
            completed_previous = LessonProgress.objects.filter(
                enrollment=enrollment,
                lesson__in=previous_lessons,
                is_completed=True
            ).count()
            is_unlocked = completed_previous == total_previous
        else:
            is_unlocked = True

        if not is_unlocked and not lesson.is_free:
            return Response({'error': 'Lesson is locked. Complete previous lessons first.'}, status=status.HTTP_403_FORBIDDEN)

        return Response(LessonDataSerializer(lesson).data)


class CourseCurriculumView(APIView):
    """Get course curriculum with progression tracking"""
    permission_classes = [AllowAny]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(
            Course.objects.prefetch_related('modules__lessons'),
            id=course_id
        )

        enrollment = None

        # Check access for non-free courses
        if not course.is_free:
            if not user.is_authenticated:
                return Response({'error': 'Login required'}, status=status.HTTP_403_FORBIDDEN)

            enrollment = Enrollment.objects.filter(
                user=user,
                course=course,
                status='active'
            ).first()

            if not enrollment and course.instructor != user and not user.is_staff:
                return Response({'error': 'Active enrollment required'}, status=status.HTTP_403_FORBIDDEN)

        # Get all lessons
        lessons = Lesson.objects.filter(
            module__course=course
        ).order_by('module__position', 'position')

        lesson_ids = list(lessons.values_list('id', flat=True))

        # Get completed lessons
        completed_ids = set()
        if enrollment:
            completed_ids = set(
                LessonProgress.objects.filter(
                    enrollment=enrollment,
                    is_completed=True
                ).values_list('lesson_id', flat=True)
            )

        # Calculate locked lessons
        locked_ids = set()
        unlock_next = True

        for lesson in lessons:
            if lesson.is_free:
                continue

            if unlock_next:
                unlock_next = lesson.id in completed_ids
            else:
                locked_ids.add(lesson.id)

        # Return curriculum with context
        serializer = CourseCurriculumSerializer(
            course,
            context={
                'completed_ids': completed_ids,
                'locked_ids': locked_ids,
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
        enrollment = require_active_enrollment(user, course_id)
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