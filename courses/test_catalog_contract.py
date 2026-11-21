from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from accounts.models import User
from courses.models import Course, Lesson, Module
from enrollments.models import Enrollment


class CatalogContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(email='catalog-contract@example.test', role='instructor')
        cls.course = Course.objects.create(title='First course', instructor=cls.owner, status='published')
        cls.module = Module.objects.create(course=cls.course, title='Published module')
        draft = Course.objects.create(title='Draft course', instructor=cls.owner)
        cls.draft_module = Module.objects.create(course=draft, title='Draft module')
        cls.lesson = Lesson.objects.create(module=cls.draft_module, title='Text lesson', content_type='text')

    def test_course_lists_use_bounded_pagination_and_preserve_the_default(self):
        Course.objects.bulk_create([
            Course(
                title=f'Published course {number}', slug=f'published-course-{number}',
                instructor=self.owner, status='published', is_free=True,
            )
            for number in range(104)
        ])
        url = '/api/courses/'
        self.assertEqual(len(self.client.get(url).data['results']), 20)
        first = self.client.get(url, {'page_size': 3}).data
        second = self.client.get(url, {'page_size': 3, 'page': 2}).data
        self.assertEqual((first['count'], len(first['results']), len(second['results'])), (105, 3, 3))
        self.assertTrue({item['id'] for item in first['results']}.isdisjoint(item['id'] for item in second['results']))
        self.assertEqual(len(self.client.get(url, {'page_size': 500}).data['results']), 100)

        self.client.force_authenticate(self.owner)
        self.assertEqual(len(self.client.get('/api/courses/instructor/courses/', {'page_size': 3}).data['results']), 3)
        self.assertEqual(len(self.client.get(url, {'instructor': 'me', 'page_size': 3}).data['results']), 3)

    def test_popular_order_is_real_and_rating_order_is_rejected(self):
        student = User.objects.create_user(email='catalog-student@example.test')
        Enrollment.objects.create(user=student, course=self.course)
        Course.objects.create(title='Newer course', instructor=self.owner, status='published')
        response = self.client.get('/api/courses/', {'ordering': 'popular', 'page_size': 1})
        self.assertEqual([item['id'] for item in response.data['results']], [self.course.pk])
        for ordering in ('rating', '-rating'):
            with self.subTest(ordering=ordering):
                response = self.client.get('/api/courses/', {'ordering': ordering})
                self.assertEqual(response.status_code, 400)
                self.assertIn('ordering', response.data)

    def test_course_detail_excludes_the_unsaved_learning_outcomes_field(self):
        response = self.client.get(f'/api/courses/{self.course.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('learning_outcomes', response.data)

    def test_retired_lesson_types_are_rejected_on_create_and_update(self):
        self.client.force_authenticate(self.owner)
        for type_name in ('assignment', 'resource'):
            with self.subTest(type_name=type_name):
                created = self.client.post(
                    f'/api/courses/sections/{self.draft_module.pk}/lessons/',
                    {'title': 'Unsupported type', 'content_type': type_name}, format='json',
                )
                edited = self.client.patch(
                    f'/api/courses/lessons/{self.lesson.pk}/', {'content_type': type_name}, format='json',
                )
                for response in (created, edited):
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn('content_type', response.data)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.content_type, 'text')
        self.assertFalse(Lesson.objects.filter(title='Unsupported type').exists())


class LessonTypeMigrationTests(TransactionTestCase):
    previous = [('courses', '0006_course_pricing_rules')]
    target = [('courses', '0007_supported_lesson_types')]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_retired_lessons_keep_their_ids_text_metadata_and_attachments(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        apps = executor.loader.project_state(self.previous).apps
        user = apps.get_model('accounts', 'User').objects.create(email='legacy-lesson@example.test')
        course = apps.get_model('courses', 'Course').objects.create(
            title='Legacy lessons', slug='legacy-lessons', instructor=user, is_free=True,
        )
        module = apps.get_model('courses', 'Module').objects.create(course=course, title='Legacy module')
        lessons = apps.get_model('courses', 'Lesson').objects
        assignment = lessons.create(
            module=module, title='Assignment', content_type='assignment', content_text='Write your notes.',
            metadata={'instructions': 'Keep the existing metadata'},
        )
        resource = lessons.create(module=module, title='Handout', content_type='resource')
        video = lessons.create(module=module, title='Video', content_type='video')
        attachment = apps.get_model('courses', 'LessonResource').objects.create(
            lesson=resource, file_url='https://example.test/handout.pdf',
        )
        MigrationExecutor(connection).migrate(self.target)

        converted = Lesson.objects.get(pk=assignment.pk)
        self.assertEqual(converted.content_type, 'text')
        self.assertEqual(converted.content_text, 'Write your notes.')
        self.assertEqual(converted.metadata, {'instructions': 'Keep the existing metadata'})
        converted_resource = Lesson.objects.get(pk=resource.pk)
        self.assertEqual(converted_resource.content_type, 'text')
        self.assertTrue(converted_resource.resources.filter(pk=attachment.pk, file_url=attachment.file_url).exists())
        self.assertEqual(Lesson.objects.get(pk=video.pk).content_type, 'video')
