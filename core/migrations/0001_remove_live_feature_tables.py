from django.db import migrations


LIVE_TABLES = [
    "live_livequestionupvote",
    "live_recordingview",
    "live_sessionattendance",
    "live_pollvote",
    "live_polloption",
    "live_livechatmessage",
    "live_livequestion",
    "live_livepoll",
    "live_sessionrecording",
    "live_sessionparticipant",
    "live_livesession",
]


def remove_live_contenttypes(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="live").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[f"DROP TABLE IF EXISTS {table};" for table in LIVE_TABLES]
            + ["DELETE FROM django_migrations WHERE app = 'live';"],
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(remove_live_contenttypes, migrations.RunPython.noop),
    ]
