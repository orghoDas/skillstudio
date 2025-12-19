from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# PostgreSQL Equivalent:
# CREATE TABLE payments_payment (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     course_id INTEGER REFERENCES courses_course(id) ON DELETE SET NULL,
#     event_id INTEGER REFERENCES live_event(id) ON DELETE SET NULL,
#     amount DECIMAL(12, 2) NOT NULL,
#     currency VARCHAR(10) NOT NULL DEFAULT 'USD',
#     provider VARCHAR(100),
#     provider_id VARCHAR(255),
#     status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
#     metadata JSONB DEFAULT '{}',
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX payments_payment_user_id_idx ON payments_payment(user_id);
# CREATE INDEX payments_payment_status_idx ON payments_payment(status);
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


# PostgreSQL Equivalent:
# CREATE TABLE payments_refund (
#     id SERIAL PRIMARY KEY,
#     payment_id INTEGER NOT NULL REFERENCES payments_payment(id) ON DELETE CASCADE,
#     amount DECIMAL(12, 2) NOT NULL,
#     reason TEXT,
#     status VARCHAR(20) NOT NULL DEFAULT 'requested',
#     processed_at TIMESTAMP WITH TIME ZONE
# );
# CREATE INDEX payments_refund_payment_id_idx ON payments_refund(payment_id);
# CREATE INDEX payments_refund_status_idx ON payments_refund(status);
class Refund(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default="requested")
    processed_at = models.DateTimeField(null=True, blank=True)


# PostgreSQL Equivalent:
# CREATE TABLE payments_coupon (
#     id SERIAL PRIMARY KEY,
#     code VARCHAR(64) UNIQUE NOT NULL,
#     discount_type VARCHAR(20) NOT NULL CHECK (discount_type IN ('percent', 'fixed')),
#     discount_value DECIMAL(10, 2) NOT NULL,
#     expires_at TIMESTAMP WITH TIME ZONE,
#     usage_limit INTEGER,
#     min_order_amount DECIMAL(12, 2),
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX payments_coupon_code_idx ON payments_coupon(code);
# CREATE INDEX payments_coupon_expires_at_idx ON payments_coupon(expires_at);
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


# PostgreSQL Equivalent:
# CREATE TABLE payments_couponredemption (
#     id SERIAL PRIMARY KEY,
#     coupon_id INTEGER NOT NULL REFERENCES payments_coupon(id) ON DELETE CASCADE,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     redeemed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     UNIQUE (coupon_id, user_id)
# );
# CREATE INDEX payments_couponredemption_coupon_id_idx ON payments_couponredemption(coupon_id);
# CREATE INDEX payments_couponredemption_user_id_idx ON payments_couponredemption(user_id);
class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    redeemed_at = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ("coupon","user")


# PostgreSQL Equivalent:
# CREATE TABLE payments_payout (
#     id SERIAL PRIMARY KEY,
#     instructor_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     amount DECIMAL(12, 2) NOT NULL,
#     currency VARCHAR(10) NOT NULL DEFAULT 'USD',
#     status VARCHAR(20) NOT NULL DEFAULT 'pending',
#     provider_details JSONB DEFAULT '{}',
#     processed_at TIMESTAMP WITH TIME ZONE,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX payments_payout_instructor_id_idx ON payments_payout(instructor_id);
# CREATE INDEX payments_payout_status_idx ON payments_payout(status);
class Payout(models.Model):
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=20, default="pending")
    provider_details = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
