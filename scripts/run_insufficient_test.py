import os, sys, django, traceback
from decimal import Decimal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','skillstudio.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Profile
from students.models import Wallet
from courses.models import Course
from payments.models import Payment
from enrollments.serializers import EnrollmentCreateSerializer
from rest_framework.test import APIRequestFactory
from rest_framework import serializers

User = get_user_model()

try:
    student_email = 'insufficient_test_student@example.com'
    instructor_email = 'insufficient_test_instructor@example.com'

    student, _ = User.objects.get_or_create(email=student_email, defaults={'role':'student'})
    instructor, _ = User.objects.get_or_create(email=instructor_email, defaults={'role':'instructor'})

    # ensure profile and wallet exist
    student_profile, _ = Profile.objects.get_or_create(user=student)
    Wallet.objects.filter(user=student).delete()
    student_wallet_obj, _ = Wallet.objects.get_or_create(user=student)

    # set wallet balance to 0 (insufficient)
    student_profile.wallet = Decimal('0.00')
    student_profile.save(update_fields=['wallet'])
    student_wallet_obj.balance = Decimal('0.00')
    student_wallet_obj.save(update_fields=['balance'])

    course, _ = Course.objects.get_or_create(slug='insufficient-test-course', defaults={
        'title':'Insufficient Test Course', 'price': Decimal('20.00'), 'is_free': False, 'status':'published', 'instructor': instructor
    })

    factory = APIRequestFactory()
    request = factory.post('/api/enroll/')
    request.user = student
    serializer = EnrollmentCreateSerializer(data={'course_id': course.id}, context={'request': request})
    try:
        if serializer.is_valid(raise_exception=True):
            serializer.save()
    except Exception as e:
        if isinstance(e, serializers.ValidationError):
            print('ValidationError raised as expected:')
            print(e.detail)
        else:
            print('Other exception:')
            traceback.print_exc()

except Exception:
    traceback.print_exc()
    raise
