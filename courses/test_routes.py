"""API-02 (route shadowing) and API-03 (DELETE on section/lesson routes)."""

import importlib

from django.apps import apps as django_apps
from django.urls import resolve
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from courses.models import Category, Course, Lesson, Module, Tag


class RouteShadowingTests(APITestCase):
    """API-02."""

    def setUp(self):
        self.instructor = User.objects.create_user(email="t@instructor.com", password="pw", role="instructor")
        self.category = Category.objects.create(name="Tech", slug="tech")

    def make(self, title):
        return Course.objects.create(title=title, instructor=self.instructor, category=self.category,
                                     status="published")

    def test_tags_endpoint_is_reachable(self):
        Tag.objects.create(name="python")
        self.assertEqual(resolve("/api/courses/tags/").func.view_class.__name__, "TagListCreateView")
        response = self.client.get("/api/courses/tags/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_fixed_routes_win_over_slug_catch_all(self):
        expected = {
            "/api/courses/categories/": "CategoryListView",
            "/api/courses/categories/create/": "CategoryCreateView",
            "/api/courses/create/": "CourseCreateView",
            "/api/courses/instructor/courses/": "InstructorCoursesView",
            "/api/courses/modules/create/": "ModuleCreateView",
            "/api/courses/lessons/create/": "LessonCreateView",
        }
        for url, view in expected.items():
            with self.subTest(url=url):
                self.assertEqual(resolve(url).func.view_class.__name__, view)

    def test_reserved_and_numeric_titles_get_safe_slugs(self):
        for title, slug in [("Tags", "tags-course"), ("2024", "2024-course"), ("Create", "create-course"),
                            ("!!!", "course")]:
            with self.subTest(title=title):
                course = self.make(title)
                self.assertEqual(course.slug, slug)
                response = self.client.get(f"/api/courses/{course.slug}/")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["id"], course.id)

    def test_migration_reslugs_existing_colliding_courses(self):
        tags = self.make("Real Course")
        numeric = self.make("Another")
        Course.objects.filter(pk=tags.pk).update(slug="tags")
        Course.objects.filter(pk=numeric.pk).update(slug="2024")
        Course.objects.create(  # occupy the first candidate slug
            title="x", slug="tags-course", instructor=self.instructor, category=self.category)

        migration = importlib.import_module("courses.migrations.0003_reslug_route_colliding_courses")
        migration.reslug_colliding_courses(django_apps, None)

        tags.refresh_from_db()
        numeric.refresh_from_db()
        self.assertEqual((tags.slug, numeric.slug), ("tags-course-1", "2024-course"))


class SectionAndLessonDeleteTests(APITestCase):
    """API-03: the course-content page's DELETE calls work."""

    def setUp(self):
        self.owner = User.objects.create_user(email="o@instructor.com", password="pw", role="instructor")
        self.other = User.objects.create_user(email="x@instructor.com", password="pw", role="instructor")
        category = Category.objects.create(name="Tech", slug="tech")
        self.course = Course.objects.create(title="Draft", instructor=self.owner, category=category, status="draft")
        self.module = Module.objects.create(course=self.course, title="M", position=1)
        self.lesson = Lesson.objects.create(module=self.module, title="L", position=1)
        self.client.force_authenticate(self.owner)

    def test_owner_deletes_lesson_and_section_in_draft(self):
        response = self.client.delete(f"/api/courses/lessons/{self.lesson.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Lesson.objects.filter(pk=self.lesson.pk).exists())

        response = self.client.delete(f"/api/courses/sections/{self.module.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Module.objects.filter(pk=self.module.pk).exists())

    def test_delete_refused_outside_draft(self):
        self.course.status = "under_review"
        self.course.save()
        for url in (f"/api/courses/lessons/{self.lesson.id}/", f"/api/courses/sections/{self.module.id}/"):
            with self.subTest(url=url):
                response = self.client.delete(url)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Lesson.objects.filter(pk=self.lesson.pk).exists())
        self.assertTrue(Module.objects.filter(pk=self.module.pk).exists())

    def test_non_owner_cannot_delete(self):
        self.client.force_authenticate(self.other)
        self.assertNotEqual(self.client.delete(f"/api/courses/lessons/{self.lesson.id}/").status_code, 204)
        self.assertNotEqual(self.client.delete(f"/api/courses/sections/{self.module.id}/").status_code, 204)
        self.assertTrue(Lesson.objects.filter(pk=self.lesson.pk).exists())
        self.assertTrue(Module.objects.filter(pk=self.module.pk).exists())

    def test_owner_can_read_section(self):
        response = self.client.get(f"/api/courses/sections/{self.module.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
