from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending","Pending"),
        ("completed","Completed"),
        ("failed","Failed"),
        ("refunded","Refunded")
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    course = models.ForeignKey("courses.Course", on_delete=models.SET_NULL, null=True, blank=True)
    event = models.ForeignKey("live.Event", on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    provider = models.CharField(max_length=100, blank=True, null=True)
    provider_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class Refund(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default="requested")
    processed_at = models.DateTimeField(null=True, blank=True)

class Coupon(models.Model):
    PERCENT = "percent"
    FIXED = "fixed"
    TYPE_CHOICES = [(PERCENT,"Percent"),(FIXED,"Fixed")]

    code = models.CharField(max_length=64, unique=True)
    discount_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    expires_at = models.DateTimeField(null=True, blank=True)
    usage_limit = models.IntegerField(null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    redeemed_at = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ("coupon","user")

class Payout(models.Model):
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=20, default="pending")
    provider_details = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
