from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from courses.models import Category, Course, Lesson, Module
from enrollments.models import Enrollment, LessonProgress
from students.services import get_student_dashboard_data


class ProgressQueryBudgetTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.instructor = users.create_user(email='budget-instructor@example.test', role='instructor')
        cls.student = users.create_user(email='budget-student@example.test')
        other = users.create_user(email='budget-other@example.test')
        category = Category.objects.create(name='Performance')
        for index in range(5):
            course = Course.objects.create(
                instructor=cls.instructor, title=f'Course {index}', category=category, status='published',
            )
            module = Module.objects.create(course=course, title='Module')
            first = Lesson.objects.create(module=module, title='First lesson', position=1, duration_seconds=4500)
            Lesson.objects.create(module=module, title='Second lesson', position=2, duration_seconds=4500)
            preview = Lesson.objects.create(module=module, title='Preview', position=0, is_free=True)
            enrollment = Enrollment.objects.create(course=course, user=cls.student)
            Enrollment.objects.create(course=course, user=other, status='completed')
            for lesson in (first, preview):
                LessonProgress.objects.create(
                    enrollment=enrollment, user=cls.student, lesson=lesson, is_completed=True, watch_time=120,
                )
            cls.last_course = course

    def test_course_list_budget_with_popularity_and_duration_filters(self):
        with self.assertNumQueries(2):
            response = self.client.get('/api/courses/?ordering=popular&duration=2-5')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 5)
        self.assertTrue(all(
            (item['enrollments_count'], item['module_count'], item['lesson_count']) == (2, 1, 3)
            for item in response.data['results']
        ))

    def test_course_detail_budget_includes_viewer_progress(self):
        self.client.force_authenticate(self.student)
        with self.assertNumQueries(7):
            response = self.client.get(f'/api/courses/{self.last_course.pk}/')
        self.assertTrue(response.data['is_enrolled'])
        self.assertEqual(response.data['enrollment_count'], response.data['enrollments_count'])
        self.assertEqual(response.data['enrollments_count'], 2)

    def test_enrollment_list_budget_and_required_progress(self):
        self.client.force_authenticate(self.student)
        with self.assertNumQueries(3):
            response = self.client.get('/api/enrollments/')
        self.assertEqual(response.data['count'], 5)
        for item in response.data['results']:
            self.assertEqual(
                (item['total_lessons_count'], item['completed_lessons_count'], item['progress_percentage']),
                (2, 1, 50),
            )
            self.assertEqual(len(item['completed_lessons']), 1)

    def test_enrollment_dashboard_query_budgets(self):
        self.client.force_authenticate(self.student)
        with self.assertNumQueries(3):
            stats = self.client.get('/api/enrollments/stats/')
        self.assertEqual(stats.data['average_progress'], 50)
        with self.assertNumQueries(2):
            dashboard = self.client.get('/api/enrollments/learning-dashboard/')
        self.assertEqual(dashboard.data['count'], 5)
        for course in dashboard.data['results']:
            self.assertEqual(
                (course['progress_percentage'], course['total_duration_seconds'], course['watched_time_seconds']),
                (50, 9000, 240),
            )

    def test_student_dashboard_course_cards_have_fixed_query_budget(self):
        with self.assertNumQueries(3):
            cards = get_student_dashboard_data(self.student)
        self.assertEqual(len(cards), 5)
        self.assertTrue(all(
            item['resume_context']['lesson_title'] == 'Second lesson' and item['progress_percentage'] == 50
            for item in cards
        ))

    def test_instructor_roster_uses_constant_queries_and_required_progress(self):
        self.client.force_authenticate(self.instructor)
        with self.assertNumQueries(3):
            response = self.client.get('/api/instructors/students/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 10)
        self.assertEqual(response.data['summary'], {'active_count': 5, 'average_progress': 25.0})
        self.assertEqual({item['progress'] for item in response.data['results']}, {0, 50})
