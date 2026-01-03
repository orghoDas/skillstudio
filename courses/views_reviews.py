from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import serializers

from .models import Course
from social.models import Review
from enrollments.models import Enrollment


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.profile.full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'course', 'user', 'user_name', 'user_email', 'rating', 'title', 'comment', 'created_at']
        read_only_fields = ['user', 'created_at']


class ReviewCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


# ===== REVIEW VIEWS =====

class CourseReviewListView(generics.ListAPIView):
    """List all reviews for a course"""
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        course_id = self.kwargs['course_id']
        return Review.objects.filter(course_id=course_id).select_related(
            'user', 'user__profile'
        ).order_by('-created_at')


class CourseReviewCreateView(APIView):
    """Create or update review for a course (requires enrollment)"""
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id, status='published')

        # Check if user is enrolled
        enrollment = Enrollment.objects.filter(
            user=user,
            course=course,
            status='active'
        ).first()

        if not enrollment:
            return Response({
                'error': 'You must be enrolled in this course to leave a review.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Create or update review
        review, created = Review.objects.get_or_create(
            course=course,
            user=user,
            defaults={
                'rating': request.data.get('rating'),
                'comment': request.data.get('comment', '')
            }
        )

        if not created:
            # Update existing review
            serializer = ReviewCreateUpdateSerializer(review, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            message = "Review updated successfully."
        else:
            message = "Review created successfully."

        return Response({
            'message': message,
            'review': ReviewSerializer(review).data
        }, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)


class ReviewUpdateView(generics.UpdateAPIView):
    """Update your own review"""
    serializer_class = ReviewCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)


class ReviewDeleteView(generics.DestroyAPIView):
    """Delete your own review"""
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)


class CourseRatingStatsView(APIView):
    """Get rating statistics for a course"""
    permission_classes = [AllowAny]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        
        stats = Review.objects.filter(course=course).aggregate(
            average_rating=Avg('rating'),
            total_reviews=Count('id'),
            five_star=Count('id', filter=Q(rating=5)),
            four_star=Count('id', filter=Q(rating=4)),
            three_star=Count('id', filter=Q(rating=3)),
            two_star=Count('id', filter=Q(rating=2)),
            one_star=Count('id', filter=Q(rating=1)),
        )

        return Response({
            'course_id': course.id,
            'course_title': course.title,
            'average_rating': round(stats['average_rating'] or 0, 2),
            'total_reviews': stats['total_reviews'],
            'rating_distribution': {
                '5': stats['five_star'],
                '4': stats['four_star'],
                '3': stats['three_star'],
                '2': stats['two_star'],
                '1': stats['one_star'],
            }
        })
