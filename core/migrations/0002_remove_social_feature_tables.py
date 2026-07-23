from django.db import migrations


SOCIAL_TABLES = [
    "social_circleresource",
    "social_circleevent",
    "social_circlegoal",
    "social_circlemessage",
    "social_circlemembership",
    "social_learningcircle",
    "social_postvote",
    "social_post",
    "social_thread",
    "social_forum",
    "social_reviewhelpful",
    "social_review",
]


def remove_social_contenttypes(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="social").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_remove_live_feature_tables"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[f"DROP TABLE IF EXISTS {table};" for table in SOCIAL_TABLES]
            + ["DELETE FROM django_migrations WHERE app = 'social';"],
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(remove_social_contenttypes, migrations.RunPython.noop),
    ]
