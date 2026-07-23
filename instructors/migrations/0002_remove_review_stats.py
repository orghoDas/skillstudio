from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("instructors", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="instructorprofile",
            name="instructor__average_5aaa7a_idx",
        ),
        migrations.RemoveField(
            model_name="instructorprofile",
            name="average_rating",
        ),
        migrations.RemoveField(
            model_name="instructorprofile",
            name="total_reviews",
        ),
    ]
