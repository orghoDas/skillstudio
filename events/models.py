from django.db import models
from accounts.models import User

# Create your models here.

# PostgreSQL Equivalent:
# CREATE TABLE events_event (
#     id SERIAL PRIMARY KEY,
#     host_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     title VARCHAR(255) NOT NULL,
#     description TEXT NOT NULL,
#     scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL,
#     max_seats INTEGER,
#     price DECIMAL(8, 2) NOT NULL DEFAULT 0.00,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX events_event_host_id_idx ON events_event(host_id);
# CREATE INDEX events_event_scheduled_for_idx ON events_event(scheduled_for);
class Event(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()

    scheduled_for = models.DateTimeField()
    max_seats = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)

# PostgreSQL Equivalent:
# CREATE TABLE events_eventregistration (
#     id SERIAL PRIMARY KEY,
#     event_id INTEGER NOT NULL REFERENCES events_event(id) ON DELETE CASCADE,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     registered_on TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX events_eventregistration_event_id_idx ON events_eventregistration(event_id);
# CREATE INDEX events_eventregistration_user_id_idx ON events_eventregistration(user_id);
class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    registered_on = models.DateTimeField(auto_now_add=True)