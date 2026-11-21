from datetime import UTC, date, datetime, timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from students.models import LearningActivity


class LearningActivityMigrationTests(TransactionTestCase):
    previous = [('students', '0002_wallet_wallettransaction'), ('enrollments', '0001_initial')]
    target = [('students', '0003_learning_activity_and_live_totals')]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_migration_recovers_distinct_days_without_guessing_watch_seconds(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        apps = executor.loader.project_state(self.previous).apps
        user = apps.get_model('accounts', 'User').objects.create(email='legacy-student@example.test')
        course = apps.get_model('courses', 'Course').objects.create(
            title='Legacy activity course', slug='legacy-activity-course', instructor=user, is_free=True,
        )
        module = apps.get_model('courses', 'Module').objects.create(course=course, title='Lessons', position=1)
        lesson_model = apps.get_model('courses', 'Lesson')
        lesson = lesson_model.objects.create(module=module, title='Studied lesson', position=1)
        enrollment = apps.get_model('enrollments', 'Enrollment').objects.create(course=course, user=user)
        progress = apps.get_model('enrollments', 'LessonProgress').objects
        row = progress.create(enrollment=enrollment, user=user, lesson=lesson, watch_time=100, is_completed=True)
        day = datetime(2026, 11, 8, 10, tzinfo=UTC)
        progress.filter(pk=row.pk).update(started_at=day, updated_at=day + timedelta(days=1), completed_at=day)
        empty_lesson = lesson_model.objects.create(module=module, title='Empty progress', position=2)
        empty = progress.create(enrollment=enrollment, user=user, lesson=empty_lesson)
        progress.filter(pk=empty.pk).update(started_at=day + timedelta(days=2), updated_at=day + timedelta(days=2))

        MigrationExecutor(connection).migrate(self.target)

        activity = LearningActivity.objects.filter(user_id=user.pk).order_by('date')
        self.assertEqual(list(activity.values_list('date', 'watch_seconds')), [
            (date(2026, 11, 8), 0),
            (date(2026, 11, 9), 0),
        ])
