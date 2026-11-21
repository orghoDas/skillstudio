"""API-01: discovery endpoints the browse/search/course-list pages rely on."""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile, User
from courses.models import Category, Course, Lesson, Module
from enrollments.models import Enrollment


class DiscoveryFixture:
    def setUp(self):
        super().setUp()
        self.ann = User.objects.create_user(email="ann@instructor.com", password="pw", role="instructor")
        Profile.objects.filter(user=self.ann).update(full_name="Ann Teacher")
        self.ben = User.objects.create_user(email="ben@instructor.com", password="pw", role="instructor")
        self.idle = User.objects.create_user(email="idle@instructor.com", password="pw", role="instructor")
        self.prog = Category.objects.create(name="Programming", slug="programming")
        self.design = Category.objects.create(name="Design", slug="design")

        self.short = self.course("Short Python", self.ann, self.prog, "beginner", hours=1)
        self.medium = self.course("Medium Design", self.ann, self.design, "intermediate", hours=3)
        self.long = self.course("Long Data", self.ben, self.prog, "advanced", hours=12, free=True)
        Course.objects.create(title="Draft", instructor=self.idle, category=self.prog, status="draft")

        for i in range(3):
            student = User.objects.create_user(email=f"s{i}@student.com", password="pw")
            Enrollment.objects.create(user=student, course=self.short)
        Enrollment.objects.create(user=User.objects.create_user(email="x@student.com", password="pw"),
                                  course=self.long)

    def course(self, title, instructor, category, level, hours, free=False):
        course = Course.objects.create(title=title, instructor=instructor, category=category, level=level,
                                       status="published", is_free=free,
                                       price=Decimal("0") if free else Decimal("20"))
        module = Module.objects.create(course=course, title="M", position=1)
        Lesson.objects.create(module=module, title="L", position=1, duration_seconds=hours * 3600)
        return course

    def titles(self, **params):
        response = self.client.get("/api/courses/", params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return sorted(c["title"] for c in response.data["results"])


class CourseListFilterTests(DiscoveryFixture, APITestCase):
    def test_comma_separated_category_and_level(self):
        self.assertEqual(self.titles(category="programming,design"), ["Long Data", "Medium Design", "Short Python"])
        self.assertEqual(self.titles(level="beginner,advanced"), ["Long Data", "Short Python"])

    def test_duration_buckets(self):
        self.assertEqual(self.titles(duration="0-2"), ["Short Python"])
        self.assertEqual(self.titles(duration="2-5,10+"), ["Long Data", "Medium Design"])
        self.assertEqual(len(self.titles(duration="bogus")), 3)  # unknown buckets are ignored

    def test_search_free_and_instructor_filters(self):
        self.assertEqual(self.titles(search="python"), ["Short Python"])
        self.assertEqual(self.titles(is_free="true"), ["Long Data"])
        self.assertEqual(self.titles(instructor=str(self.ann.id)), ["Medium Design", "Short Python"])

    def test_non_numeric_instructor_is_ignored_not_a_500(self):
        self.assertEqual(len(self.titles(instructor="abc")), 3)

    def test_popular_ordering(self):
        response = self.client.get("/api/courses/", {"ordering": "popular"})
        self.assertEqual(response.data["results"][0]["title"], "Short Python")


class FeaturedInstructorsTests(DiscoveryFixture, APITestCase):
    def test_public_list_ordered_by_students_without_emails(self):
        response = self.client.get("/api/instructors/featured/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([i["id"] for i in response.data['results']], [self.ann.id, self.ben.id])  # idle has no published course
        ann = response.data['results'][0]
        self.assertEqual((ann["name"], ann["courses_count"], ann["students_count"]), ("Ann Teacher", 2, 3))
        for entry in response.data['results']:
            self.assertNotIn("email", entry)
            self.assertNotIn("@", entry["name"])
