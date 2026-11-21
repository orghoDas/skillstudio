from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from certificates.models import Certificate
from courses.models import Category, Course, Lesson, Module
from enrollments.models import Enrollment, LessonProgress
from payments.models import Payment
from students.models import Wallet


class AdminDomainActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_superuser(email='admin@example.com', password='test-password')
        cls.instructor = users.create_user(email='instructor@example.com', role='instructor')
        cls.student = users.create_user(email='student@example.com')
        cls.category = Category.objects.create(name='Admin tests', slug='admin-tests')
        cls.course = Course.objects.create(
            title='Published course', instructor=cls.instructor, category=cls.category,
            status='published',
        )
        cls.enrollment = Enrollment.objects.create(user=cls.student, course=cls.course)
        module = Module.objects.create(course=cls.course, title='Module', position=1)
        lesson = Lesson.objects.create(module=module, title='Lesson', position=1)
        cls.progress = LessonProgress.objects.create(
            enrollment=cls.enrollment, user=cls.student, lesson=lesson,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def run_action(self, model, action, *ids):
        response = self.client.post(reverse(f'admin:{model}_changelist'), {
            'action': action, '_selected_action': ids, 'index': 0,
        }, secure=True)
        self.assertEqual(response.status_code, 302)

    def test_course_actions_enforce_source_status_and_keep_review_metadata(self):
        draft = Course.objects.create(
            title='Draft course', instructor=self.instructor, category=self.category,
        )
        review = Course.objects.create(
            title='Course in review', instructor=self.instructor, category=self.category,
            status='under_review', rejection_reason='Previous review',
        )
        review_module = Module.objects.create(course=review, title='Ready for review')
        Lesson.objects.create(module=review_module, title='Review lesson')
        self.run_action('courses_course', 'archive_courses', draft.pk, self.course.pk, review.pk)
        draft.refresh_from_db()
        self.course.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(draft.status, 'draft')
        self.assertEqual(review.status, 'under_review')
        self.assertEqual(self.course.status, 'archived')
        self.assertIsNotNone(self.course.archived_at)

        self.run_action('courses_course', 'publish_courses', draft.pk, review.pk)
        review.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'draft')
        self.assertEqual(review.status, 'published')
        self.assertEqual(review.reviewed_by, self.admin)
        self.assertEqual(review.rejection_reason, '')

    def test_completion_actions_check_requirements_and_issue_certificate_once(self):
        self.run_action('enrollments_enrollment', 'mark_as_completed', self.enrollment.pk)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'active')
        self.assertFalse(Certificate.objects.filter(enrollment=self.enrollment).exists())

        self.run_action('enrollments_lessonprogress', 'mark_as_completed', self.progress.pk)
        self.progress.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertTrue(self.progress.is_completed)
        self.assertEqual(self.enrollment.status, 'completed')
        self.assertTrue(self.enrollment.is_completed)

        self.run_action('enrollments_enrollment', 'mark_as_completed', self.enrollment.pk)
        self.assertEqual(Certificate.objects.filter(enrollment=self.enrollment).count(), 1)

    def test_lesson_action_cannot_restore_access_to_canceled_enrollment(self):
        self.run_action('enrollments_enrollment', 'mark_as_canceled', self.enrollment.pk)
        self.run_action('enrollments_lessonprogress', 'mark_as_completed', self.progress.pk)
        self.enrollment.refresh_from_db()
        self.progress.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'canceled')
        self.assertFalse(self.progress.is_completed)

    def test_completion_action_repairs_a_missing_certificate_for_legacy_completion(self):
        completed_at = timezone.now()
        LessonProgress.objects.filter(pk=self.progress.pk).update(
            is_completed=True, completed_at=completed_at,
        )
        Enrollment.objects.filter(pk=self.enrollment.pk).update(
            status='completed', is_completed=True, completed_at=completed_at,
        )
        self.run_action('enrollments_enrollment', 'mark_as_completed', self.enrollment.pk)
        certificate = Certificate.objects.get(enrollment=self.enrollment)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.completed_at, completed_at)
        self.assertEqual(certificate.completion_date, completed_at)

    def test_view_permission_alone_cannot_run_completion_action(self):
        staff = get_user_model().objects.create_user(email='staff@example.com', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(
            content_type__app_label='enrollments', codename='view_lessonprogress',
        ))
        self.client.force_login(staff)
        response = self.client.post(reverse('admin:enrollments_lessonprogress_changelist'), {
            'action': 'mark_as_completed', '_selected_action': [self.progress.pk], 'index': 0,
        }, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('admin:login')))
        self.progress.refresh_from_db()
        self.assertFalse(self.progress.is_completed)

    def test_admin_money_records_allow_inspection_but_reject_direct_writes(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.student)
        entry = wallet.add_money('20.00')
        payment = Payment.objects.create(
            user=self.student, purpose=Payment.PURPOSE_WALLET_TOPUP,
            amount='10.00', original_amount='10.00',
        )
        for model, obj, data in [
            ('students_wallet', wallet, {'balance': '500.00'}),
            ('students_wallettransaction', entry, {'amount': '500.00'}),
            ('payments_payment', payment, {'amount': '500.00', 'status': 'completed'}),
        ]:
            with self.subTest(model=model):
                change_url = reverse(f'admin:{model}_change', args=[obj.pk])
                self.assertEqual(self.client.get(change_url, secure=True).status_code, 200)
                self.assertEqual(self.client.post(change_url, data, secure=True).status_code, 403)
                add_url = reverse(f'admin:{model}_add')
                self.assertEqual(self.client.post(add_url, data, secure=True).status_code, 403)
                delete_url = reverse(f'admin:{model}_delete', args=[obj.pk])
                self.assertEqual(self.client.post(delete_url, {'post': 'yes'}, secure=True).status_code, 403)

        wallet.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(str(wallet.balance), '20.00')
        self.assertEqual(str(payment.amount), '10.00')
        self.assertEqual(payment.status, 'pending')
