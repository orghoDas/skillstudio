import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')
django.setup()

from live.models import LiveSession
from accounts.models import User

session = LiveSession.objects.first()
users = User.objects.all()

print(f"Session: {session.title}")
print(f"  Requires Enrollment: {session.requires_enrollment}")
print(f"  Course: {session.course.title}")
print(f"  Instructor: {session.instructor.email}")
print(f"\nUsers:")
for user in users:
    print(f"  - {user.email} ({user.role})")
    
# Check enrollments
from enrollments.models import Enrollment
enrollments = Enrollment.objects.filter(course=session.course)
print(f"\nEnrollments in {session.course.title}:")
for enroll in enrollments:
    print(f"  - {enroll.user.email}: {enroll.status}")
