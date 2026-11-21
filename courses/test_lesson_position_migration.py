from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from courses.models import Lesson


class LessonPositionMigrationTests(TransactionTestCase):
    previous = [('courses', '0007_supported_lesson_types')]
    target = [('courses', '0008_unique_lesson_positions')]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_duplicate_positions_are_repaired_without_changing_lesson_order_or_ids(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        apps = executor.loader.project_state(self.previous).apps
        user = apps.get_model('accounts', 'User').objects.create(email='lesson-positions@example.test')
        course = apps.get_model('courses', 'Course').objects.create(
            title='Legacy course', slug='legacy-positions', instructor=user, is_free=True,
        )
        modules = apps.get_model('courses', 'Module').objects
        module = modules.create(course=course, title='Duplicate positions')
        other_module = modules.create(course=course, title='Unique positions')
        lessons = apps.get_model('courses', 'Lesson').objects
        first = lessons.create(module=module, title='First', position=3)
        last = lessons.create(module=module, title='Last', position=10)
        second = lessons.create(module=module, title='Second', position=3)
        separate = lessons.create(module=other_module, title='Separate', position=3)
        resource = apps.get_model('courses', 'LessonResource').objects.create(
            lesson=second, file_url='https://example.test/notes.pdf',
        )

        MigrationExecutor(connection).migrate(self.target)

        self.assertEqual(
            list(Lesson.objects.filter(module_id=module.pk).values_list('pk', 'position')),
            [(first.pk, 3), (second.pk, 4), (last.pk, 10)],
        )
        self.assertEqual(Lesson.objects.get(pk=separate.pk).position, 3)
        self.assertTrue(Lesson.objects.get(pk=second.pk).resources.filter(pk=resource.pk).exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Lesson.objects.create(module_id=module.pk, title='Duplicate', position=3)
