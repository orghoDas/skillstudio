"""CRS-01: the course access policy, checked as a full matrix.

viewer (anonymous, owner, other instructor, admin, student with an active /
completed / canceled / no enrollment) x course status (draft, under_review,
published, archived) x free/paid, for: catalog visibility, content access,
management, and lesson access (paid lesson and free-preview lesson).
"""

import itertools
from decimal import Decimal

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from accounts.models import User
from courses.models import Category, Course, Lesson, Module
from courses.policies import (
    can_access_course_content, can_access_lesson, can_manage_course, can_view_course_catalog,
)
from enrollments.models import Enrollment

STATUSES = ("draft", "under_review", "published", "archived")
VIEWERS = ("anonymous", "owner", "other_instructor", "admin",
           "student_active", "student_completed", "student_canceled", "student_none")


def expected(viewer, status, free):
    manager = viewer in ("owner", "admin")
    owns = viewer in ("student_active", "student_completed")
    visible = status == "published" or manager or (status == "archived" and owns)
    content = visible and (free or manager or owns)
    return {
        "catalog": visible,
        "content": content,
        "manage": manager,
        "paid_lesson": content,
        "preview_lesson": visible,  # free-preview lessons: anyone who can see the course
    }


class CourseAccessPolicyMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(email="owner@instructor.com", password="pw", role="instructor")
        cls.users = {
            "anonymous": AnonymousUser(),
            "owner": cls.owner,
            "other_instructor": User.objects.create_user(email="other@instructor.com", password="pw",
                                                         role="instructor"),
            "admin": User.objects.create_superuser(email="root@example.com", password="pw"),
        }
        for state in ("active", "completed", "canceled", "none"):
            cls.users[f"student_{state}"] = User.objects.create_user(email=f"{state}@student.com", password="pw")

        category = Category.objects.create(name="Tech", slug="tech")
        cls.cases = []
        for status, free in itertools.product(STATUSES, (False, True)):
            course = Course.objects.create(
                title=f"{status} {'free' if free else 'paid'}", instructor=cls.owner, category=category,
                status=status, is_free=free, price=Decimal("0") if free else Decimal("10"),
            )
            module = Module.objects.create(course=course, title="M", position=1)
            paid_lesson = Lesson.objects.create(module=module, title="Paid", position=1, is_free=False)
            preview = Lesson.objects.create(module=module, title="Preview", position=2, is_free=True)
            for state in ("active", "completed", "canceled"):
                Enrollment.objects.create(user=cls.users[f"student_{state}"], course=course, status=state)
            cls.cases.append((status, free, course, paid_lesson, preview))

    def test_matrix(self):
        checked = 0
        for (status, free, course, paid_lesson, preview), viewer in itertools.product(self.cases, VIEWERS):
            user = self.users[viewer]
            actual = {
                "catalog": can_view_course_catalog(user, course),
                "content": can_access_course_content(user, course),
                "manage": bool(can_manage_course(user, course)),
                "paid_lesson": can_access_lesson(user, paid_lesson),
                "preview_lesson": can_access_lesson(user, preview),
            }
            with self.subTest(viewer=viewer, status=status, free=free):
                self.assertEqual(actual, expected(viewer, status, free))
            checked += 1
        self.assertEqual(checked, len(STATUSES) * 2 * len(VIEWERS))

    def test_draft_free_course_is_not_open_to_the_public(self):
        """Regression: content access used to skip the visibility check for free courses."""
        draft_free = next(c for s, f, c, _, _ in self.cases if s == "draft" and f)
        self.assertFalse(can_access_course_content(AnonymousUser(), draft_free))
        self.assertFalse(can_access_course_content(self.users["student_none"], draft_free))
