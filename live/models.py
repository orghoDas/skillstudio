from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

User = settings.AUTH_USER_MODEL


# PostgreSQL Equivalent:
# CREATE TABLE live_event (
#     id SERIAL PRIMARY KEY,
#     organizer_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     title VARCHAR(255) NOT NULL,
#     description TEXT DEFAULT '',
#     starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
#     ends_at TIMESTAMP WITH TIME ZONE,
#     location VARCHAR(255) DEFAULT '',
#     seats INTEGER CHECK (seats >= 0),
#     price DECIMAL(8, 2) NOT NULL DEFAULT 0.00,
#     creted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX live_event_organizer_id_idx ON live_event(organizer_id);
# CREATE INDEX live_event_starts_at_idx ON live_event(starts_at);
class Event(models.Model):
    organizer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="organized_events")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    seats = models.PositiveIntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    creted_at = models.DateTimeField(default=timezone.now)


# PostgreSQL Equivalent:
# CREATE TABLE live_eventregistration (
#     id SERIAL PRIMARY KEY,
#     event_id INTEGER NOT NULL REFERENCES live_event(id) ON DELETE CASCADE,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     registered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     UNIQUE (event_id, user_id)
# );
# CREATE INDEX live_eventregistration_event_id_idx ON live_eventregistration(event_id);
# CREATE INDEX live_eventregistration_user_id_idx ON live_eventregistration(user_id);
class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_registrations")
    registered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("event","user")


# PostgreSQL Equivalent:
# CREATE TABLE live_liveclass (
#     id SERIAL PRIMARY KEY,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     host_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
#     meeting_link VARCHAR(200) NOT NULL,
#     creaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX live_liveclass_course_id_idx ON live_liveclass(course_id);
# CREATE INDEX live_liveclass_host_id_idx ON live_liveclass(host_id);
# CREATE INDEX live_liveclass_scheduled_at_idx ON live_liveclass(scheduled_at);
class LiveClass(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="live_classes")
    host = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="hosted_live_classes")
    scheduled_at = models.DateTimeField()
    meeting_link = models.URLField()
    creaded_at = models.DateTimeField(default=timezone.now)


# PostgreSQL Equivalent:
# CREATE TABLE live_livemessage (
#     id SERIAL PRIMARY KEY,
#     live_class_id INTEGER NOT NULL REFERENCES live_liveclass(id) ON DELETE CASCADE,
#     user_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     content TEXT NOT NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX live_livemessage_live_class_id_idx ON live_livemessage(live_class_id);
# CREATE INDEX live_livemessage_user_id_idx ON live_livemessage(user_id);
class LiveMessage(models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
