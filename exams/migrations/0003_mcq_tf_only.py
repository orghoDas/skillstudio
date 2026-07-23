from django.db import migrations, models


ALLOWED_TYPES = {"mcq", "tf"}
PRIVATE_ANSWER_KEYS = {
    "correct_answer",
    "correct_option",
    "correct_options",
    "answer",
    "answers",
    "model_answer",
}


def remove_text_answer_questions(apps, schema_editor):
    QuestionBank = apps.get_model("exams", "QuestionBank")
    Exam = apps.get_model("exams", "Exam")

    QuestionBank.objects.exclude(question_type__in=ALLOWED_TYPES).delete()

    for exam in Exam.objects.all():
        kept_questions = []
        for question in exam.custom_questions or []:
            if not isinstance(question, dict):
                continue

            question_type = question.get("question_type", question.get("type", "mcq"))
            if question_type not in ALLOWED_TYPES:
                continue

            options = question.get("options", [])
            if not isinstance(options, list) or len(options) < 2:
                continue
            if question_type == "tf" and len(options) != 2:
                continue

            correct_count = sum(
                1
                for option in options
                if isinstance(option, dict) and option.get("is_correct")
            )
            if correct_count != 1:
                continue

            cleaned = {
                key: value
                for key, value in question.items()
                if key not in PRIVATE_ANSWER_KEYS
            }
            cleaned["question_type"] = question_type
            kept_questions.append(cleaned)

        if kept_questions != exam.custom_questions:
            exam.custom_questions = kept_questions
            exam.save(update_fields=["custom_questions"])


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0002_attempt_number_constraints"),
    ]

    operations = [
        migrations.RunPython(remove_text_answer_questions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="questionbank",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("mcq", "Multiple Choice"),
                    ("tf", "True/False"),
                ],
                default="mcq",
                max_length=10,
            ),
        ),
        migrations.RemoveField(
            model_name="questionbank",
            name="correct_answer",
        ),
        migrations.RemoveField(
            model_name="examattempt",
            name="graded_by",
        ),
        migrations.RemoveField(
            model_name="examattempt",
            name="manually_graded_at",
        ),
    ]
