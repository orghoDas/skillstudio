from decimal import Decimal

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from accounts.models import APIKey
from certificates.models import Certificate
from courses.models import Category, Course, Lesson, Module
from enrollments.models import Enrollment, LessonProgress
from payments import services
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

    def test_populated_wishlist_and_webhook_changelists_render(self):
        from enrollments.models import Wishlist
        from payments.models import PaymentWebhookLog

        Wishlist.objects.create(user=self.student, course=self.course)
        PaymentWebhookLog.objects.create(
            gateway='stripe', event_type='other', event_id='audit-fixture', payload={}, processed=True,
        )
        self.assertContains(self.client.get(reverse('admin:enrollments_wishlist_changelist'), {'q': 'student'}), '$0.00')
        self.assertContains(self.client.get(reverse('admin:payments_paymentwebhooklog_changelist')), 'Processed')

    def test_enrollment_admin_counts_only_required_lessons(self):
        lesson = self.progress.lesson
        self.progress.is_completed = True
        self.progress.save(update_fields=['is_completed'])
        preview = Lesson.objects.create(module=lesson.module, title='Preview', position=2, is_free=True)
        LessonProgress.objects.create(enrollment=self.enrollment, user=self.student, lesson=preview, is_completed=True)
        response = self.client.get(reverse('admin:enrollments_enrollment_changelist'))
        self.assertContains(response, '100.0%')
        self.assertNotContains(response, '200.0%')

    def test_payment_history_prevents_account_deletion(self):
        from django.db.models import ProtectedError

        Payment.objects.create(user=self.student, instructor=self.instructor, course=self.course, amount=10, original_amount=10)
        with self.assertRaises(ProtectedError):
            self.student.delete()
        with self.assertRaises(ProtectedError):
            self.instructor.delete()

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

    def test_overview_and_workflow_follow_staff_permissions(self):
        review = Course.objects.create(
            title='Awaiting a review', instructor=self.instructor, category=self.category, status='under_review',
        )
        index = reverse('admin:index')
        decision = reverse('admin:courses_course_decision', args=[review.pk])
        self.assertContains(self.client.get(index), 'Learning enrollments')
        self.assertContains(self.client.get(index), decision)
        self.client.force_login(self.student)
        self.assertRedirects(self.client.get(index), f'{reverse("admin:login")}?next={index}')

        staff = get_user_model().objects.create_user(email='reviewer@example.com', role='admin', admin_console_only=True)
        reviewers = Group.objects.create(name='Course reviewers')
        reviewers.permissions.add(Permission.objects.get(content_type__app_label='courses', codename='view_course'))
        staff.groups.add(reviewers)
        self.client.force_login(staff)
        overview = self.client.get(index)
        self.assertContains(overview, review.title)
        self.assertNotContains(overview, 'Net course sales')
        self.assertNotContains(overview, 'New enrollments')
        self.assertNotContains(overview, decision)
        self.assertEqual(self.client.post(decision, {'action': 'draft', 'note': 'Feedback'}).status_code, 403)

        reviewers.permissions.add(Permission.objects.get(content_type__app_label='courses', codename='change_course'))
        self.assertContains(self.client.get(index), decision)
        self.assertContains(self.client.post(decision, {'action': 'draft'}), 'Rejection reason is required.')
        self.assertEqual(self.client.post(decision, {'action': 'draft', 'note': 'Add a worked example.'}).status_code, 302)
        review.refresh_from_db()
        self.assertEqual((review.status, review.reviewed_by, review.rejection_reason), ('draft', staff, 'Add a worked example.'))
        self.assertContains(self.client.get(index), 'Course status changed to draft.')
        self.assertTrue(LogEntry.objects.filter(user=staff, object_id=review.pk, content_type__model='course').exists())

    def test_finance_decisions_use_wallet_ledger_and_require_csrf(self):
        buyer_wallet, _ = Wallet.objects.get_or_create(user=self.student)
        buyer_wallet.add_money('40.00')
        course = Course.objects.create(
            title='Paid course', instructor=self.instructor, category=self.category,
            status='published', is_free=False, price=Decimal('30.00'),
        )
        payment = services.purchase_course(self.student, course.pk).payment
        refund = services.request_refund(self.student, payment.pk, 'Partial refund request', Decimal('5.00'))
        url = reverse('admin:payments_refund_decision', args=[refund.pk])
        self.assertContains(self.client.get(url), 'Partial refund request')
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post(url, {'action': 'approve'}).status_code, 403)
        self.assertEqual(self.client.post(url, {'action': 'approve', 'note': 'Verified purchase'}).status_code, 302)
        self.assertEqual(self.client.post(url, {'action': 'approve'}).status_code, 403)
        refund.refresh_from_db()
        buyer_wallet.refresh_from_db()
        self.assertEqual(refund.status, 'processed')
        self.assertEqual(buyer_wallet.balance, Decimal('15.00'))
        self.assertContains(self.client.get(reverse('admin:index')), 'USD 25.00')

        payout = services.create_payout(self.instructor, Decimal('10.00'), payout_method='bank_transfer')
        url = reverse('admin:payments_payout_decision', args=[payout.pk])
        self.assertEqual(self.client.post(url, {'action': 'approve'}).status_code, 302)
        self.assertContains(self.client.post(url, {'action': 'complete'}), 'Enter the reference')
        self.assertEqual(self.client.post(url, {'action': 'complete', 'transaction_id': 'fixture-transfer'}).status_code, 302)
        payout.refresh_from_db()
        self.assertEqual((payout.status, payout.transaction_id), ('paid', 'fixture-transfer'))
        self.assertTrue(payout.wallet_debited)
        self.assertEqual(LogEntry.objects.filter(user=self.admin, content_type__model='payout', object_id=payout.pk).count(), 2)

    def test_console_only_accounts_cannot_use_website_credentials(self):
        password = 'A-testing-password!12'
        add_url = reverse('admin:accounts_user_add')
        response = self.client.post(add_url, {
            'email': 'operator@example.com', 'role': 'admin', 'is_active': 'on',
            'password1': password, 'password2': password, '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        staff = get_user_model().objects.get(email='operator@example.com')
        self.assertTrue(staff.admin_console_only)
        client = Client()
        self.assertTrue(client.login(email=staff.email, password=password))
        self.assertContains(client.get(reverse('admin:index')), 'Operations overview')

        _, secret = APIKey.create_for_user(staff, 'Existing key')
        existing_token = RefreshToken.for_user(staff)
        stored = OutstandingToken.objects.get(jti=existing_token['jti'])
        self.assertNotContains(
            self.client.get(reverse('admin:token_blacklist_outstandingtoken_change', args=[stored.pk])),
            str(existing_token),
        )
        api = Client()
        self.assertEqual(api.post('/api/accounts/token/', {
            'email': staff.email, 'password': password, 'token_in_body': True,
        }).status_code, 401)
        self.assertEqual(api.post('/api/accounts/token/refresh/', {'refresh': str(existing_token)}).status_code, 401)
        self.assertEqual(api.get('/api/accounts/users/', HTTP_AUTHORIZATION=f'Bearer {existing_token.access_token}').status_code, 401)
        self.assertEqual(api.get('/api/accounts/users/', HTTP_X_API_KEY=secret).status_code, 401)
        api.cookies[settings.JWT_AUTH_COOKIE] = str(existing_token.access_token)
        self.assertRedirects(
            api.get('/instructor/courses/'), '/auth/login/?next=%2Finstructor%2Fcourses%2F',
            fetch_redirect_response=False,
        )

    def test_delegated_account_manager_can_deactivate_users_without_granting_permissions(self):
        operator = get_user_model().objects.create_user(email='accounts-operator@example.com', role='admin', admin_console_only=True)
        operator.user_permissions.add(
            Permission.objects.get(content_type__app_label='accounts', codename='change_user'),
            Permission.objects.get(content_type__app_label='accounts', codename='view_user'),
            Permission.objects.get(content_type__app_label='auth', codename='change_group'),
        )
        group = Group.objects.create(name='Account operators')
        self.client.force_login(operator)
        response = self.client.post(reverse('admin:accounts_user_change', args=[self.student.pk]), {
            'email': 'changed@example.com', 'role': 'admin', 'is_superuser': 'on',
            'groups': [group.pk], '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual((self.student.is_active, self.student.is_superuser, self.student.role, self.student.email),
                         (False, False, 'student', 'student@example.com'))
        self.assertFalse(self.student.groups.exists())
        self.assertEqual(self.client.post(reverse('admin:accounts_user_change', args=[self.admin.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:auth_group_change', args=[group.pk])).status_code, 403)
