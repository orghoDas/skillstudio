from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ExamAttemptSnapshotMigrationTests(TransactionTestCase):
    previous = [('exams', '0003_mcq_tf_only')]
    target = [('exams', '0004_attempt_snapshots')]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_backfill_repairs_legacy_threshold_and_preserves_completed_grades(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        apps = executor.loader.project_state(self.previous).apps
        users = apps.get_model('accounts', 'User').objects
        instructor = users.create(email='legacy-exam-instructor@example.test', role='instructor')
        student = users.create(email='legacy-exam-student@example.test')
        course = apps.get_model('courses', 'Course').objects.create(
            title='Legacy course', slug='legacy-course', instructor=instructor, is_free=True,
        )
        exam = apps.get_model('exams', 'Exam').objects.create(
            course=course, title='Legacy exam', duration_minutes=5, total_marks=100, passing_marks=50,
            custom_questions=[{
                'id': 'old-1', 'marks': 10, 'question_text': 'Question',
                'options': [{'text': 'Yes', 'is_correct': True}, {'text': 'No', 'is_correct': False}],
            }],
        )
        attempts = apps.get_model('exams', 'ExamAttempt').objects
        graded = attempts.create(
            exam=exam, user=student, attempt_number=1, status='completed', score=10, percentage=100, passed=False,
        )
        active = attempts.create(exam=exam, user=student, attempt_number=2, answers={'old-1': 0})
        executor = MigrationExecutor(connection)
        executor.migrate(self.target)
        migrated = executor.loader.project_state(self.target).apps
        Exam = migrated.get_model('exams', 'Exam')
        ExamAttempt = migrated.get_model('exams', 'ExamAttempt')

        updated = Exam.objects.get(pk=exam.pk)
        self.assertEqual((updated.total_marks, updated.passing_marks), (Decimal('10.00'), Decimal('5.00')))
        updated_active = ExamAttempt.objects.get(pk=active.pk)
        self.assertEqual(updated_active.answers, {'old-1': 0})
        self.assertEqual(updated_active.snapshot['passing_marks'], '5.00')
        self.assertEqual(updated_active.snapshot['questions'][0]['id'], 'old-1')
        updated_graded = ExamAttempt.objects.get(pk=graded.pk)
        self.assertIsNone(updated_graded.snapshot)
        self.assertEqual((updated_graded.score, updated_graded.percentage, updated_graded.passed), (10, 100, False))
