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
                         "nonexistent_field", "--title", "id;DROP TABLE"):
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
        self.assertEqual((module.status_code, lesson.status_code), (403, 403))
        self.assertFalse(Module.objects.filter(title="Injected").exists())
        self.assertFalse(Lesson.objects.filter(title="Injected").exists())


class CourseModerationTests(Fixture, APITestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(email="moderator@test.com", role="admin")
        self.base = "/api/courses/"
        self.course = self.alice_course
        self.module = self.alice_module
        self.lesson = self.alice_lesson

    def test_nonowners_get_403_for_course_and_content_management(self):
        for actor in (self.bob, self.student):
            self.client.force_authenticate(actor)
            cases = [
                ("PATCH", f"{self.course.pk}/update/"),
                ("DELETE", f"{self.course.pk}/delete/"),
                ("POST", f"{self.course.pk}/submit/"),
                ("POST", f"{self.course.slug}/sections/"),
                ("POST", f"modules/{self.module.pk}/lessons/"),
                ("GET", f"sections/{self.module.pk}/"),
                ("PATCH", f"modules/{self.module.pk}/update/"),
                ("DELETE", f"modules/{self.module.pk}/delete/"),
                ("GET", f"lessons/{self.lesson.pk}/"),
                ("PATCH", f"lessons/{self.lesson.pk}/update/"),
                ("DELETE", f"lessons/{self.lesson.pk}/delete/"),
            ]
            for method, route in cases:
                with self.subTest(actor=actor.role, method=method, route=route):
                    request = getattr(self.client, method.lower())
                    payload = {"title": "Unauthorized", "content_type": "text"} if method in ("POST", "PATCH") else {}
                    response = request(self.base + route, payload, format="json")
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "Alice Course")
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(f"{self.base}create/").status_code, 403)

    def test_admin_can_edit_and_delete_without_taking_ownership(self):
        self.client.force_authenticate(self.admin)
        updated = self.client.patch(
            f"{self.base}{self.course.pk}/update/",
            {"title": "Moderated course", "instructor": self.admin.pk}, format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.course.refresh_from_db()
        self.assertEqual((self.course.title, self.course.instructor_id), ("Moderated course", self.alice.pk))

        for route in (f"lessons/{self.lesson.pk}/", f"sections/{self.module.pk}/"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(self.base + route).status_code, 200)
                self.assertEqual(self.client.patch(self.base + route, {"title": "Moderated"}, format="json").status_code, 200)
                self.assertEqual(self.client.delete(self.base + route).status_code, 204)
        self.assertFalse(Module.objects.filter(pk=self.module.pk).exists())
        self.assertFalse(Lesson.objects.filter(pk=self.lesson.pk).exists())
        self.assertEqual(self.client.delete(f"{self.base}{self.course.pk}/delete/").status_code, 204)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())

    def test_admin_can_create_content_through_both_parent_routes(self):
        self.client.force_authenticate(self.admin)
        parents = (
            (f"{self.course.pk}/modules/", {}),
            ("modules/create/", {"course": self.course.pk}),
        )
        for route, fields in parents:
            created = self.client.post(self.base + route, {"title": "Admin module", **fields}, format="json")
            self.assertEqual(created.status_code, 201, created.data)
            self.assertEqual(created.data["course"], self.course.pk)

        parents = (
            (f"sections/{self.module.pk}/lessons/", {}),
            ("lessons/create/", {"module": self.module.pk}),
        )
        for route, fields in parents:
            created = self.client.post(
                self.base + route, {"title": "Admin lesson", "content_type": "text", **fields}, format="json",
            )
            self.assertEqual(created.status_code, 201, created.data)
            self.assertEqual(created.data["module"], self.module.pk)

    def test_admin_moderation_still_checks_course_state_and_parent_assignments(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(
            f"{self.base}sections/{self.module.pk}/", {"course": self.bob_course.pk}, format="json",
        ).status_code, 400)
        self.assertEqual(self.client.patch(
            f"{self.base}lessons/{self.lesson.pk}/", {"module": self.bob_module.pk}, format="json",
        ).status_code, 400)

        Lesson.objects.create(module=self.alice_module2, title="Second draft lesson")
        response = self.client.post(f"{self.base}{self.course.pk}/submit/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "under_review")
        self.assertEqual(self.client.delete(f"{self.base}{self.course.pk}/delete/").status_code, 400)
        self.assertEqual(self.client.post(f"{self.base}{self.course.pk}/publish/").status_code, 200)
        self.assertEqual(self.client.delete(f"{self.base}sections/{self.module.pk}/").status_code, 400)
        self.assertEqual(self.client.delete(f"{self.base}lessons/{self.lesson.pk}/").status_code, 400)
        self.assertEqual(self.client.patch(
            f"{self.base}{self.course.pk}/update/", {"title": "Past the edit window"}, format="json",
        ).status_code, 400)


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
