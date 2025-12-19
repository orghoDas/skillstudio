from django.db import models
from django.conf import settings
# Create your models here.


# PostgreSQL Equivalent:
# CREATE TABLE analytics_courseanalyticssnapshot (
#     id SERIAL PRIMARY KEY,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
#     total_enrollments INTEGER NOT NULL DEFAULT 0 CHECK (total_enrollments >= 0),
#     total_completions INTEGER NOT NULL DEFAULT 0 CHECK (total_completions >= 0),
#     total_watch_minutes INTEGER NOT NULL DEFAULT 0 CHECK (total_watch_minutes >= 0),
#     unique_viewers INTEGER NOT NULL DEFAULT 0 CHECK (unique_viewers >= 0),
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     UNIQUE (course_id, snapshot_date)
# );
# CREATE INDEX analytics_courseanalyticssnapshot_course_id_idx ON analytics_courseanalyticssnapshot(course_id);
class CourseAnalyticsSnapshot(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="analytics")
    snapshot_date = models.DateField(auto_now_add=True)
    total_enrollments = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    total_watch_minutes = models.PositiveIntegerField(default=0)
    unique_viewers = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("course", "snapshot_date")


# PostgreSQL Equivalent:
# CREATE TABLE analytics_userinteraction (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     course_id INTEGER REFERENCES courses_course(id) ON DELETE SET NULL,
#     event_type_id INTEGER REFERENCES live_event(id) ON DELETE SET NULL,
#     action VARCHAR(100) NOT NULL,
#     metadata JSONB DEFAULT '{}',
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX analytics_userinteraction_user_id_idx ON analytics_userinteraction(user_id);
# CREATE INDEX analytics_userinteraction_course_id_idx ON analytics_userinteraction(course_id);
class UserInteraction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    course = models.ForeignKey("courses.Course", on_delete=models.SET_NULL, null=True)
    event_type = models.ForeignKey("live.Event", on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)