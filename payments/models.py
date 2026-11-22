from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from payments.payout_details import decrypt_payout_details

User = settings.AUTH_USER_MODEL


class Payment(models.Model):
    """A money movement: a wallet top-up or a course purchase paid from the wallet."""
    
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("partially_refunded", "Partially Refunded"),
        ("disputed", "Disputed"),
        ("cancelled", "Cancelled"),
    ]
    
    # Payments architecture (AUDIT_REPORT.md Decision D-01): money enters only
    # through a wallet top-up (Stripe, test mode) and courses are bought from
    # the wallet. Every Payment row is one of these two movements.
    PURPOSE_COURSE_PURCHASE = "course_purchase"
    PURPOSE_WALLET_TOPUP = "wallet_topup"
    PURPOSE_CHOICES = [
        (PURPOSE_COURSE_PURCHASE, "Course purchase (paid from wallet)"),
        (PURPOSE_WALLET_TOPUP, "Wallet top-up"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("bank_transfer", "Bank Transfer"),
        ("wallet", "Wallet"),
        ("manual", "Manual"),
    ]

    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default=PURPOSE_COURSE_PURCHASE,
        db_index=True,
    )

    # User and instructor
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="payments"
    )
    instructor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="instructor_payments",
    )

    # Related items
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    # Payment details
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    original_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Amount before discounts"
    )
    discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0
    )
    currency = models.CharField(max_length=10, default="USD")
    
    # Fee distribution
    platform_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    instructor_earnings = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    
    # Payment gateway
    payment_method = models.CharField(
        max_length=50, 
        choices=PAYMENT_METHOD_CHOICES,
        default="stripe"
    )
    provider = models.CharField(max_length=100, blank=True, null=True)
    provider_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Coupon
    coupon = models.ForeignKey(
        'Coupon',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )

    # Status and tracking
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="pending"
    )
    failure_reason = models.TextField(blank=True)
    
    # Billing info
    billing_email = models.EmailField(blank=True)
    billing_address = models.JSONField(default=dict, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["instructor"]),
            models.Index(fields=["user"]),
            models.Index(fields=["payment_method"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["provider_id"]),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        item = self.course or "Unknown"
        return f"Payment #{self.id} - {self.user.email} - {item} - {self.status}"


    
    @property
    def is_successful(self) -> bool:
        return self.status == 'completed'
    
    @property
    def can_be_refunded(self) -> bool:
        return self.status in ['completed', 'partially_refunded']


class Payout(models.Model):
    """Instructor payout model"""
    
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    
    METHOD_CHOICES = [
        ("stripe_connect", "Stripe Connect"),
        ("paypal", "PayPal"),
        ("bank_transfer", "Bank Transfer"),
        ("wire_transfer", "Wire Transfer"),
    ]

    instructor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="payouts"
    )

    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('10.00'))]
    )
    currency = models.CharField(max_length=10, default="USD")

    # DEPRECATED (PAY-07, 2026-11-21): payouts are no longer tied to individual
    # payments. Withdrawable money is the instructor's wallet balance; a payout
    # debits the wallet. Kept only for historical rows.
    payments = models.ManyToManyField(
        Payment, related_name="payouts", blank=True
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )

    # True once ``amount`` has been taken out of the instructor's wallet ledger.
    # New payouts are debited (reserved) at request time; if a payout is
    # rejected/failed/cancelled the amount is credited back and this flips to
    # False. Legacy rows created before the wallet ledger start as False.
    wallet_debited = models.BooleanField(default=False)

    payout_method = models.CharField(
        max_length=50,
        choices=METHOD_CHOICES,
        default="stripe_connect"
    )
    
    account_details_encrypted = models.TextField(default='', blank=True, editable=False)
    
    # Transaction tracking
    transaction_id = models.CharField(max_length=255, blank=True)
    provider_details = models.JSONField(default=dict, blank=True)
    
    failure_reason = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    # Timestamps
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['instructor', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Payout #{self.id} - {self.instructor.email} - ${self.amount} - {self.status}"

    def get_account_details(self):
        """Retrieve the destination for authorized offline payout processing."""
        return decrypt_payout_details(self.account_details_encrypted)


    
    @property
    def payment_count(self):
        return self.payments.count()


class Refund(models.Model):
    """Refund model for payment refunds"""
    
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("processing", "Processing"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    ]
    
    REFUND_TYPE_CHOICES = [
        ("full", "Full Refund"),
        ("partial", "Partial Refund"),
    ]

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="refunds"
    )
    
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="refund_requests"
    )
    
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_refunds"
    )

    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    refund_type = models.CharField(
        max_length=20,
        choices=REFUND_TYPE_CHOICES,
        default="full"
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="requested"
    )
    
    # Admin handling
    admin_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # How the refund was funded when it was processed (PAY-08): the student's
    # wallet is credited ``amount``; the instructor's wallet is debited their
    # pro-rata share; anything the instructor could not cover (only when an
    # admin explicitly chose to absorb it) is recorded as platform_absorbed.
    instructor_debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_absorbed = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Provider tracking
    provider_refund_id = models.CharField(max_length=255, blank=True)

    # Timestamps
    requested_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['payment']),
        ]
    
    def __str__(self):
        return f"Refund #{self.id} - Payment #{self.payment.id} - ${self.amount} - {self.status}"


class Coupon(models.Model):
    """Discount coupon model"""
    
    PERCENT = "percent"
    FIXED = "fixed"

    TYPE_CHOICES = [
        (PERCENT, "Percentage Discount"),
        (FIXED, "Fixed Amount Discount"),
    ]
    
    APPLIES_TO_CHOICES = [
        ("all", "All Courses"),
        ("courses", "Courses Only"),
        ("specific", "Specific Courses"),
    ]

    code = models.CharField(max_length=64, unique=True, db_index=True)
    discount_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    discount_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Restrictions
    applies_to = models.CharField(
        max_length=20,
        choices=APPLIES_TO_CHOICES,
        default="all"
    )
    specific_courses = models.ManyToManyField(
        'courses.Course',
        blank=True,
        related_name='coupons'
    )
    
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum discount amount for percentage coupons"
    )
    min_order_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Minimum purchase amount to use coupon"
    )
    
    # Usage limits
    usage_limit = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Total number of times coupon can be used"
    )
    usage_limit_per_user = models.IntegerField(
        null=True,
        blank=True,
        help_text="Times each user can use this coupon"
    )
    current_usage = models.IntegerField(default=0)

    # Status
    is_active = models.BooleanField(default=True)
    # Only public coupons are listed to students; private codes are shared
    # out-of-band and can still be redeemed by anyone who knows them.
    is_public = models.BooleanField(default=False)

    # Validity
    valid_from = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Created by
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_coupons'
    )
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.discount_type}: {self.discount_value}"


    
    @property
    def is_valid(self):
        """Check if coupon is currently valid"""
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        if self.usage_limit and self.current_usage >= self.usage_limit:
            return False
        return True
    
    def can_be_used_by(self, user):
        """Check if user can use this coupon"""
        if not self.is_valid:
            return False
        if self.usage_limit_per_user:
            user_usage = CouponRedemption.objects.filter(
                coupon=self,
                user=user
            ).count()
            return user_usage < self.usage_limit_per_user
        return True


class CouponRedemption(models.Model):
    """Track coupon usage by users"""
    
    coupon = models.ForeignKey(
        Coupon, 
        on_delete=models.CASCADE,
        related_name='redemptions'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='coupon_redemptions'
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coupon_redemptions'
    )
    
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    redeemed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['coupon', 'user']),
            models.Index(fields=['user', '-redeemed_at']),
        ]
        ordering = ['-redeemed_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.coupon.code} - {self.redeemed_at}"


class PaymentWebhookLog(models.Model):
    """Log webhook events from payment gateways"""
    
    EVENT_TYPES = [
        ("payment.succeeded", "Payment Succeeded"),
        ("payment.failed", "Payment Failed"),
        ("payment.refunded", "Payment Refunded"),
        ("payout.succeeded", "Payout Succeeded"),
        ("payout.failed", "Payout Failed"),
        ("dispute.created", "Dispute Created"),
        ("other", "Other"),
    ]

    gateway = models.CharField(max_length=50)
    event_type = models.CharField(max_length=100)
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='webhook_logs'
    )
    
    payload = models.JSONField()
    
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gateway', '-created_at']),
            models.Index(fields=['event_id']),
            models.Index(fields=['processed']),
        ]
    
    def __str__(self):
        return f"{self.gateway} - {self.event_type} - {self.created_at}"


class PaymentDispute(models.Model):
    """Track payment disputes and chargebacks"""
    
    STATUS_CHOICES = [
        ("opened", "Opened"),
        ("under_review", "Under Review"),
        ("won", "Won"),
        ("lost", "Lost"),
        ("closed", "Closed"),
    ]

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='disputes'
    )
    
    dispute_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="opened")
    
    evidence = models.JSONField(default=dict, blank=True)
    admin_notes = models.TextField(blank=True)
    
    # Timestamps
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Dispute #{self.dispute_id} - Payment #{self.payment.id} - {self.status}"
