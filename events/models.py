from django.db import models
from accounts.models import User

# Create your models here.

class Event(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()

    scheduled_for = models.DateTimeField()
    max_seats = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)

class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    registered_on = models.DateTimeField(auto_now_add=True)