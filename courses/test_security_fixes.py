"""
Regression tests for SEC-04, SEC-05, BUG-01 and BUG-02 (AUDIT_REPORT.md).
"""

import csv
import io
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from courses.models import Category, Course, Lesson, Module
from enrollments.models import Enrollment, LessonProgress


class Fixture:
    def setUp(self):
        super().setUp()
        self.alice = User.objects.create_user(email="alice@test.com", password="pw", role="instructor")
        self.bob = User.objects.create_user(email="bob@test.com", password="pw", role="instructor")
        self.student = User.objects.create_user(email="student@test.com", password="pw", role="student")
        self.category = Category.objects.create(name="Tech", slug="tech")
        self.alice_course = Course.objects.create(title="Alice Course", instructor=self.alice,
                                                  category=self.category, status="draft")
        self.bob_course = Course.objects.create(title="Bob Course", instructor=self.bob,
                                                category=self.category, status="published")
        self.alice_module = Module.objects.create(course=self.alice_course, title="A1", position=1)
        self.alice_module2 = Module.objects.create(course=self.alice_course, title="A2", position=2)
        self.bob_module = Module.objects.create(course=self.bob_course, title="B1", position=1)
        self.alice_lesson = Lesson.objects.create(module=self.alice_module, title="Alice lesson", position=1)


class CourseOrderingTests(Fixture, APITestCase):
    """SEC-04: ?ordering= is allow-listed."""

    def setUp(self):
        super().setUp()
        Course.objects.create(title="Zeta", instructor=self.bob, category=self.category,
                              status="published", price=Decimal("5.00"))
        Course.objects.create(title="Alpha", instructor=self.alice, category=self.category,
                              status="published", price=Decimal("50.00"))

    def titles(self, ordering):
        response = self.client.get("/api/courses/", {"ordering": ordering})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [c["title"] for c in response.data["results"]]

    def test_sensitive_and_unknown_fields_fall_back_to_default(self):
        default = self.titles("-created_at")
        for ordering in ("instructor__password", "-instructor__password", "instructor__email",
                         "nonexistent_field", "rating", "id;DROP TABLE"):
            with self.subTest(ordering=ordering):
                self.assertEqual(self.titles(ordering), default)

    def test_allowed_fields_still_sort(self):
        self.assertEqual(self.titles("title")[:2], ["Alpha", "Bob Course"])
        self.assertEqual(self.titles("-price")[0], "Alpha")


class NoCrossCourseInjectionTests(Fixture, APITestCase):
    """SEC-05: modules/lessons can't be moved into someone else's course."""

    def test_module_cannot_be_moved_to_another_course(self):
        self.client.force_authenticate(self.alice)
        response = self.client.patch(f"/api/courses/sections/{self.alice_module.id}/",
                                     {"course": self.bob_course.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.alice_module.refresh_from_db()
        self.assertEqual(self.alice_module.course, self.alice_course)

    def test_lesson_cannot_be_moved_into_another_course(self):
        self.client.force_authenticate(self.alice)
        for url in (f"/api/courses/lessons/{self.alice_lesson.id}/",
                    f"/api/courses/lessons/{self.alice_lesson.id}/update/"):
            with self.subTest(url=url):
                response = self.client.patch(url, {"module": self.bob_module.id}, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.alice_lesson.refresh_from_db()
        self.assertEqual(self.alice_lesson.module, self.alice_module)
        self.assertEqual(self.bob_module.lessons.count(), 0)

    def test_lesson_can_move_within_its_own_course(self):
        self.client.force_authenticate(self.alice)
        response = self.client.patch(f"/api/courses/lessons/{self.alice_lesson.id}/",
                                     {"module": self.alice_module2.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.alice_lesson.refresh_from_db()
        self.assertEqual(self.alice_lesson.module, self.alice_module2)

    def test_create_without_parent_is_a_400_not_a_500(self):
        self.client.force_authenticate(self.alice)
        module = self.client.post("/api/courses/modules/create/", {"title": "Orphan"}, format="json")
        lesson = self.client.post("/api/courses/lessons/create/", {"title": "Orphan"}, format="json")
        self.assertEqual((module.status_code, lesson.status_code), (400, 400))

    def test_cannot_create_into_someone_elses_course(self):
        self.client.force_authenticate(self.alice)
        module = self.client.post("/api/courses/modules/create/",
                                  {"course": self.bob_course.id, "title": "Injected"}, format="json")
        lesson = self.client.post("/api/courses/lessons/create/",
                                  {"module": self.bob_module.id, "title": "Injected"}, format="json")
        self.assertEqual((module.status_code, lesson.status_code), (400, 400))
        self.assertFalse(Module.objects.filter(title="Injected").exists())
        self.assertFalse(Lesson.objects.filter(title="Injected").exists())


class LessonAnalyticsCsvTests(Fixture, APITestCase):
    """BUG-01: the CSV export works, handles unstarted lessons and escapes formulas."""

    def test_csv_export(self):
        evil = Lesson.objects.create(module=self.bob_module, title='=HYPERLINK("http://evil","x")', position=1)
        untouched = Lesson.objects.create(module=self.bob_module, title="Never started", position=2)
        enrollment = Enrollment.objects.create(user=self.student, course=self.bob_course)
        LessonProgress.objects.create(enrollment=enrollment, user=self.student, lesson=evil, is_completed=False)

        self.client.force_authenticate(self.bob)
        response = self.client.get(f"/api/enrollments/instructor/courses/{self.bob_course.id}/lesson-analytics-csv/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        by_id = {int(r[0]): r for r in rows[1:]}
        self.assertEqual(by_id[evil.id][1], "'=HYPERLINK(\"http://evil\",\"x\")")
        self.assertEqual(by_id[evil.id][2:], ["1", "0", "1", "100.0"])
        self.assertEqual(by_id[untouched.id][2:], ["0", "0", "0", "0.0"])

    def test_other_instructors_cannot_export(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(f"/api/enrollments/instructor/courses/{self.bob_course.id}/lesson-analytics-csv/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class InstructorCoursesListTests(Fixture, APITestCase):
    """BUG-02: the list works and no longer swallows errors into a NameError."""

    def test_lists_only_own_courses(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get("/api/courses/instructor/courses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c["title"] for c in response.data["results"]], ["Alice Course"])
