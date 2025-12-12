from django.db import models
from accounts.models import User

# Create your models here.

class Transaction(models.Model):
    PAYMENT_TYPES = [
        ('course', 'Course Enrollment'),
        ('event', 'Event Registration'),
        ('payout', 'Instructor Payout')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    status = models.CharField(max_length=20, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)

