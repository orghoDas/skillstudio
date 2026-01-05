import os
import sys
import django
from decimal import Decimal
import traceback

# Ensure project root is on PYTHONPATH so Django settings package is importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Profile
from courses.models import Course
from payments.models import Payment
from enrollments.serializers import EnrollmentCreateSerializer
from rest_framework.test import APIRequestFactory
from students.models import Wallet

User = get_user_model()

try:
    # Prepare users
    student_email = 'test_student_wallet@example.com'
    instructor_email = 'test_instructor_wallet@example.com'

    student, created = User.objects.get_or_create(email=student_email, defaults={'role': 'student'})
    if created:
        student.set_password('testpass')
        student.save()

    instructor, icreated = User.objects.get_or_create(email=instructor_email, defaults={'role': 'instructor'})
    if icreated:
        instructor.set_password('testpass')
        instructor.save()

    # Ensure profiles exist and have wallets
    student_profile, _ = Profile.objects.get_or_create(user=student)
    instructor_profile, _ = Profile.objects.get_or_create(user=instructor)

    # Ensure student Wallet model exists and seed it (frontend reads this)
    student_wallet_obj, _ = Wallet.objects.get_or_create(user=student)

    # Seed wallets (both Profile.wallet and students.Wallet to simulate existing state)
    student_profile.wallet = Decimal('100.00')
    student_profile.save(update_fields=['wallet'])
    student_wallet_obj.balance = Decimal('100.00')
    student_wallet_obj.save(update_fields=['balance'])
    instructor_profile.wallet = Decimal('0.00')
    instructor_profile.save(update_fields=['wallet'])

    # Prepare a paid course
    course_title = 'Test Paid Course for Wallet'
    course, ccreated = Course.objects.get_or_create(
        slug='test-paid-course-wallet',
        defaults={
            'title': course_title,
            'description': 'Auto-created test course',
            'price': Decimal('30.00'),
            'is_free': False,
            'status': 'published',
            'instructor': instructor,
        }
    )
    if not ccreated:
        course.price = Decimal('30.00')
        course.is_free = False
        course.status = 'published'
        course.instructor = instructor
        course.save()

    # Ensure we read the latest saved values from DB
    student_profile.refresh_from_db()
    instructor_profile.refresh_from_db()
    print('Before enrollment:')
    print(' student Profile.wallet =', student_profile.wallet)
    # show students.Wallet balance if present
    try:
        student_wallet_obj.refresh_from_db()
        print(' student Wallet.balance =', student_wallet_obj.balance)
    except Exception:
        print(' student Wallet.balance = (none)')
    print(' instructor wallet =', instructor_profile.wallet)
    before_payments = Payment.objects.filter(user=student, course=course).count()
    print(' existing payments for this course:', before_payments)

    # Run enrollment serializer
    factory = APIRequestFactory()
    request = factory.post('/api/enroll/')
    request.user = student
    serializer = EnrollmentCreateSerializer(data={'course_id': course.id}, context={'request': request})
    if serializer.is_valid(raise_exception=True):
        enrollment = serializer.save()
        print('Enrollment created:', enrollment.id)

    print('\nAfter enrollment:')
    student_profile.refresh_from_db()
    instructor_profile.refresh_from_db()
    print(' student Profile.wallet =', student_profile.wallet)
    try:
        student_wallet_obj.refresh_from_db()
        print(' student Wallet.balance =', student_wallet_obj.balance)
    except Exception:
        print(' student Wallet.balance = (none)')
    print(' instructor wallet =', instructor_profile.wallet)
    after_payments = Payment.objects.filter(user=student, course=course).count()
    print(' payments created for this course:', after_payments)

except Exception as e:
    print('Test failed with exception:')
    traceback.print_exc()
    raise
