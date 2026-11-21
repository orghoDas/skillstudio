from django.db import migrations, models

from exams.grading import MAX_EXAM_MARKS, build_questions, exam_snapshot, legacy_passing_marks, total_question_marks


def backfill_exam_settings_and_open_attempts(apps, schema_editor):
    Exam = apps.get_model('exams', 'Exam')
    ExamAttempt = apps.get_model('exams', 'ExamAttempt')
    alias = schema_editor.connection.alias
    attempts = ExamAttempt.objects.using(alias)
    for exam in Exam.objects.using(alias).prefetch_related('questions').iterator(chunk_size=200):
        questions = build_questions(exam.questions.all(), exam.custom_questions)
        total = total_question_marks(questions)
        passing_marks = legacy_passing_marks(exam.passing_marks, exam.total_marks, total)
        attempts.filter(exam_id=exam.pk, status='in_progress').update(
            snapshot=exam_snapshot(exam, questions, passing_marks),
        )
        # Oversized historical exams require correction before another attempt.
        if total <= MAX_EXAM_MARKS:
            Exam.objects.using(alias).filter(pk=exam.pk).update(total_marks=total, passing_marks=passing_marks)


class Migration(migrations.Migration):
    dependencies = [('exams', '0003_mcq_tf_only')]
    operations = [
        migrations.AlterField(
            model_name='exam',
            name='total_marks',
            field=models.DecimalField(max_digits=6, decimal_places=2, default=0),
        ),
        migrations.AddField(
            model_name='examattempt',
            name='snapshot',
            field=models.JSONField(null=True, editable=False),
        ),
        migrations.AlterField(
            model_name='examattempt',
            name='score',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.RunPython(backfill_exam_settings_and_open_attempts, migrations.RunPython.noop),
    ]
