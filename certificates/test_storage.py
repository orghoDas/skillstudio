"""OPS-01 / OPS-02 / TEST-01: static & media storage, certificate PDF files."""

import importlib
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import Resolver404, resolve
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from certificates.models import Certificate
from certificates.services import certificate_has_pdf, render_certificate_pdf
from courses.models import Category, Course
from enrollments.models import Enrollment


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

    def test_other_users_cannot_download(self):
        self.client.force_authenticate(User.objects.create_user(email="o@student.com", password="pw"))
        self.assertEqual(self.download().status_code, status.HTTP_404_NOT_FOUND)
