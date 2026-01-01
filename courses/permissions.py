from rest_framework.permissions import BasePermission
from enrollments.models import Enrollment

class CanAccessLesson(BasePermission):
    def has_object_permission(self, request, view, lesson):
        user = request.user

        if not user.is_authenticated:
            return False
        
        course = lesson.module.course

        if user.role == 'admin':
            return True
        
        if user.role == 'instructor' and course.instructor == user:
            return True
        
        return Enrollment.objects.filter(user=user, course=course).exists()
    

class CanEditCourse(BasePermission):
    message = "This course is locked and cannot be modified."

    def has_object_permission(self, request, view, course):
        # Must be owner
        if course.instructor != request.user:
            return False

        # Course must be editable
        return course.status == 'draft'
