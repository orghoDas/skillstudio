"""OPS-01 / OPS-02 / TEST-01: static & media storage, certificate PDF files."""

import importlib
from pathlib import Path
from decimal import Decimal

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.urls import Resolver404, resolve
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from certificates.models import Certificate
from certificates.services import certificate_has_pdf, issue_certificate, render_certificate_pdf
from courses.models import Category, Course, Lesson, Module
from enrollments.models import Enrollment
from enrollments.services import evaluate_and_complete_enrollment, mark_lesson_completed
from exams.models import Exam
from exams.services import start_exam_attempt, submit_exam_attempt


class StorageSettingsTests(SimpleTestCase):
    def test_project_uses_storages_with_hashed_static_files(self):
        """OPS-01: STATICFILES_STORAGE is ignored on Django 5.1+; STORAGES is used."""
        project_settings = importlib.import_module("skillstudio.settings")
        self.assertFalse(hasattr(project_settings, "STATICFILES_STORAGE"))
        self.assertEqual(
            project_settings.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    def test_tests_use_temporary_media_root(self):
        """TEST-01: tests never write into the project's real media/ folder."""
        real_media = Path(settings.BASE_DIR) / "media"
        self.assertNotEqual(Path(settings.MEDIA_ROOT).resolve(), real_media.resolve())
        self.assertIn("skillstudio-test-media-", str(settings.MEDIA_ROOT))

    def test_media_files_are_not_served_publicly(self):
        """OPS-02: certificate PDFs are only reachable via the authenticated download view."""
        with self.assertRaises(Resolver404):
            resolve("/media/certificates/2026/01/certificate_x.pdf")


class CertificateDownloadTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(email="s@student.com", password="pw")
        instructor = User.objects.create_user(email="t@instructor.com", password="pw", role="instructor")
        category = Category.objects.create(name="Tech", slug="tech")
        self.course = Course.objects.create(title="Course", instructor=instructor, category=category,
                                            status="published")
        enrollment = Enrollment.objects.create(user=self.student, course=self.course, status="completed",
                                               is_completed=True)
        self.certificate = Certificate.objects.create(user=self.student, course=self.course,
                                                      enrollment=enrollment)
        self.client.force_authenticate(self.student)

    def download(self):
        return self.client.get(f"/api/certificates/download/{self.course.id}/")

    def test_missing_pdf_is_rendered_on_download(self):
        self.assertFalse(certificate_has_pdf(self.certificate))
        response = self.download()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.certificate.refresh_from_db()
        self.assertTrue(certificate_has_pdf(self.certificate))

    def test_deleted_pdf_file_is_regenerated_not_a_500(self):
        render_certificate_pdf(self.certificate.id)
        self.certificate.refresh_from_db()
        storage, name = self.certificate.pdf.storage, self.certificate.pdf.name
        storage.delete(name)  # file gone, name still recorded
        self.assertFalse(certificate_has_pdf(self.certificate))

        response = self.download()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.certificate.refresh_from_db()
        self.assertTrue(certificate_has_pdf(self.certificate))

    def test_pdf_is_regenerated_when_the_public_learner_name_changes(self):
        from accounts.models import Profile

        render_certificate_pdf(self.certificate.pk)
        self.certificate.refresh_from_db()
        self.assertEqual(self.certificate.pdf_learner_name, 'SkillStudio learner')
        Profile.objects.update_or_create(user=self.student, defaults={'full_name': 'Updated Learner'})
        self.assertEqual(self.download().status_code, 200)
        self.certificate.refresh_from_db()
        self.assertEqual(self.certificate.pdf_learner_name, 'Updated Learner')
        response = self.client.get(f'/api/certificates/verify/{self.certificate.verification_code}/')
        self.assertEqual(response.data['user_name'], 'Updated Learner')

    def test_other_users_cannot_download(self):
        self.client.force_authenticate(User.objects.create_user(email="o@student.com", password="pw"))
        self.assertEqual(self.download().status_code, status.HTTP_404_NOT_FOUND)

    def test_public_verification_and_cancellation(self):
        from django.urls import reverse

        code = self.certificate.verification_code
        public_page = reverse('certificate-verification-page', kwargs={'code': code})
        public_api = f'/api/certificates/verify/{code}/'
        public = self.client_class()
        response = public.get(public_api)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], str(self.certificate.pk))
        self.assertNotIn('certificate_id', response.data)
        self.assertNotIn(self.student.email, response.content.decode())
        self.assertContains(public.get(public_page), 'Verified certificate')
        self.assertTrue(self.certificate.verification_url.endswith(public_page))

        enrollment = self.certificate.enrollment
        canceled = self.client.patch(f'/api/enrollments/enrollments/{enrollment.pk}/cancel/')
        self.assertEqual(canceled.status_code, 200, canceled.data)
        self.certificate.refresh_from_db()
        self.assertIsNotNone(self.certificate.revoked_at)
        self.assertContains(public.get(public_page), 'This certificate was revoked.', status_code=410)
        self.assertEqual(public.get(public_api).status_code, 410)
        self.assertEqual(self.download().status_code, 410)

        enrollment.status = 'completed'
        enrollment.save(update_fields=['status'])
        reissued = issue_certificate(self.student, self.course)
        self.assertEqual(reissued.pk, self.certificate.pk)
        self.assertNotEqual(reissued.verification_code, code)
        self.assertIsNone(reissued.revoked_at)
        self.assertEqual(public.get(public_api).status_code, 404)

    def test_download_count_uses_current_database_value(self):
        stale = Certificate.objects.get(pk=self.certificate.pk)
        self.certificate.increment_download_count()
        stale.increment_download_count()
        self.assertEqual(stale.download_count, 2)

    def test_passing_published_exam_completes_course_and_contributes_grade(self):
        self.certificate.delete()
        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        enrollment.status = 'active'
        enrollment.is_completed = False
        enrollment.save(update_fields=['status', 'is_completed'])
        module = Module.objects.create(course=self.course, title='Module')
        lesson = Lesson.objects.create(module=module, title='Required lesson')
        mark_lesson_completed(enrollment, lesson)
        exam = Exam.objects.create(
            course=self.course, title='Final', duration_minutes=10, passing_marks=3,
            max_attempts=2, status='published', show_results_immediately=False,
            custom_questions=[
                {
                    'id': key, 'marks': marks,
                    'options': [{'text': 'A', 'is_correct': True}, {'text': 'B', 'is_correct': False}],
                }
                for key, marks in (('q1', 3), ('q2', 1))
            ],
        )
        self.assertFalse(evaluate_and_complete_enrollment(enrollment.pk))
        failed = submit_exam_attempt(start_exam_attempt(exam, self.student), {'q1': 1})
        self.assertFalse(failed.passed)
        self.assertFalse(Certificate.objects.filter(enrollment=enrollment).exists())

        passed = submit_exam_attempt(start_exam_attempt(exam, self.student), {'q1': 0})
        self.assertTrue(passed.passed)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, 'completed')
        certificate = Certificate.objects.get(enrollment=enrollment)
        self.assertEqual(certificate.grade, Decimal('75.00'))
        self.assertFalse(certificate.pdf)
        verification = f'/api/certificates/verify/{certificate.verification_code}/'
        self.assertIsNone(self.client.get(verification).data['grade'])
        response = self.download()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))
        certificate.refresh_from_db()
        self.assertIsNone(certificate.pdf_grade)

        exam.show_results_immediately = True
        exam.save(update_fields=['show_results_immediately'])
        self.assertEqual(self.client.get(verification).data['grade'], '75.00')
        response = self.download()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))
        certificate.refresh_from_db()
        self.assertEqual(certificate.pdf_grade, Decimal('75.00'))


class CertificateRevocationMigrationTests(TransactionTestCase):
    def test_migration_revokes_legacy_certificates_with_canceled_enrollments(self):
        executor = MigrationExecutor(connection)
        old = [('certificates', '0001_initial')]
        executor.migrate(old)
        apps = executor.loader.project_state(old).apps
        try:
            user = apps.get_model('accounts', 'User').objects.create(email='legacy-certificate@example.test')
            course = apps.get_model('courses', 'Course').objects.create(
                title='Legacy', slug='legacy-certificate', instructor=user, is_free=True,
            )
            apps.get_model('enrollments', 'Enrollment').objects.create(user=user, course=course, status='canceled')
            certificate = apps.get_model('certificates', 'Certificate').objects.create(
                user=user, course=course, verification_code='legacy-cert-code',
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
        self.assertIsNotNone(Certificate.objects.get(pk=certificate.pk).revoked_at)
