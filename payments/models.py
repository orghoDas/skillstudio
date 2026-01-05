from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal

User = settings.AUTH_USER_MODEL


class Payment(models.Model):
    """Payment transaction model for course and event purchases"""
    
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
    
    PAYMENT_METHOD_CHOICES = [
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("bank_transfer", "Bank Transfer"),
        ("wallet", "Wallet"),
        ("manual", "Manual"),
    ]

    # User and instructor
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="payments"
    )
    instructor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
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
    # event = models.ForeignKey(
    #     "events.Event",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="payments",
    # )

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
        item = self.course or "Unknown"  # Removed event reference - events app disabled
        return f"Payment #{self.id} - {self.user.email} - {item} - {self.status}"


# PostgreSQL equivalent for payments:
# CREATE TABLE IF NOT EXISTS payments_payment (
#     id serial PRIMARY KEY,
#     user_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     instructor_id integer NULL REFERENCES accounts_user(id) ON DELETE SET NULL,
#     course_id integer NULL REFERENCES courses_course(id) ON DELETE SET NULL,
#     amount numeric(12,2) NOT NULL,
#     original_amount numeric(12,2) NOT NULL,
#     discount_amount numeric(12,2) NOT NULL DEFAULT 0,
#     currency varchar(10) NOT NULL DEFAULT 'USD',
#     platform_fee numeric(12,2) NOT NULL DEFAULT 0,
#     instructor_earnings numeric(12,2) NOT NULL DEFAULT 0,
#     payment_method varchar(50) NOT NULL DEFAULT 'stripe',
#     provider varchar(100) NULL,
#     provider_id varchar(255) NULL,
#     coupon_id integer NULL REFERENCES payments_coupon(id) ON DELETE SET NULL,
#     status varchar(30) NOT NULL DEFAULT 'pending',
#     failure_reason text NOT NULL DEFAULT '',
#     billing_email varchar(254) NOT NULL DEFAULT '',
#     billing_address jsonb NOT NULL DEFAULT '{}',
#     metadata jsonb NOT NULL DEFAULT '{}',
#     ip_address inet NULL,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now(),
#     completed_at timestamptz NULL
# );
# CREATE INDEX IF NOT EXISTS idx_payments_payment_status ON payments_payment (status);
# CREATE INDEX IF NOT EXISTS idx_payments_payment_instructor ON payments_payment (instructor_id);
# CREATE INDEX IF NOT EXISTS idx_payments_payment_user ON payments_payment (user_id);
# CREATE INDEX IF NOT EXISTS idx_payments_payment_method ON payments_payment (payment_method);
# CREATE INDEX IF NOT EXISTS idx_payments_payment_created ON payments_payment (created_at);
# CREATE INDEX IF NOT EXISTS idx_payments_payment_provider_id ON payments_payment (provider_id);
    
    @property
    def is_successful(self):
        return self.status == 'completed'
    
    @property
    def can_be_refunded(self):
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
        User, on_delete=models.CASCADE, related_name="payouts"
    )

    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('10.00'))]
    )
    currency = models.CharField(max_length=10, default="USD")

    payments = models.ManyToManyField(
        Payment, related_name="payouts"
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    
    payout_method = models.CharField(
        max_length=50,
        choices=METHOD_CHOICES,
        default="stripe_connect"
    )
    
    # Account details (encrypted in production)
    account_details = models.JSONField(default=dict, blank=True)
    
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


# PostgreSQL equivalent for payouts:
# CREATE TABLE IF NOT EXISTS payments_payout (
#     id serial PRIMARY KEY,
#     instructor_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     amount numeric(12,2) NOT NULL,
#     currency varchar(10) NOT NULL DEFAULT 'USD',
#     status varchar(20) NOT NULL DEFAULT 'pending',
#     payout_method varchar(50) NOT NULL DEFAULT 'stripe_connect',
#     account_details jsonb NOT NULL DEFAULT '{}',
#     transaction_id varchar(255) NOT NULL DEFAULT '',
#     provider_details jsonb NOT NULL DEFAULT '{}',
#     failure_reason text NOT NULL DEFAULT '',
#     admin_notes text NOT NULL DEFAULT '',
#     processed_at timestamptz NULL,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now()
# );
# -- M2M table for payout payments (auto by Django):
# CREATE TABLE IF NOT EXISTS payments_payout_payments (
#     id serial PRIMARY KEY,
#     payout_id integer NOT NULL REFERENCES payments_payout(id) ON DELETE CASCADE,
#     payment_id integer NOT NULL REFERENCES payments_payment(id) ON DELETE CASCADE
# );
# CREATE INDEX IF NOT EXISTS idx_payments_payout_instructor_created ON payments_payout (instructor_id, created_at DESC);
# CREATE INDEX IF NOT EXISTS idx_payments_payout_status ON payments_payout (status);
    
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


# PostgreSQL equivalent for refunds:
# CREATE TABLE IF NOT EXISTS payments_refund (
#     id serial PRIMARY KEY,
#     payment_id integer NOT NULL REFERENCES payments_payment(id) ON DELETE CASCADE,
#     requested_by_id integer NULL REFERENCES accounts_user(id) ON DELETE SET NULL,
#     processed_by_id integer NULL REFERENCES accounts_user(id) ON DELETE SET NULL,
#     amount numeric(12,2) NOT NULL,
#     refund_type varchar(20) NOT NULL DEFAULT 'full',
#     reason text NOT NULL,
#     status varchar(20) NOT NULL DEFAULT 'requested',
#     admin_notes text NOT NULL DEFAULT '',
#     rejection_reason text NOT NULL DEFAULT '',
#     provider_refund_id varchar(255) NOT NULL DEFAULT '',
#     requested_at timestamptz NOT NULL DEFAULT now(),
#     processed_at timestamptz NULL,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now()
# );
# CREATE INDEX IF NOT EXISTS idx_payments_refund_status ON payments_refund (status);
# CREATE INDEX IF NOT EXISTS idx_payments_refund_payment ON payments_refund (payment_id);


class Coupon(models.Model):
    """Discount coupon model"""
    
    PERCENT = "percent"
    FIXED = "fixed"

    TYPE_CHOICES = [
        (PERCENT, "Percentage Discount"),
        (FIXED, "Fixed Amount Discount"),
    ]
    
    APPLIES_TO_CHOICES = [
        ("all", "All Items"),
        ("courses", "Courses Only"),
        ("events", "Events Only"),
        ("specific", "Specific Items"),
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
    # specific_events = models.ManyToManyField(
    #     'events.Event',
    #     blank=True,
    #     related_name='coupons'
    # )
    
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


# PostgreSQL equivalent for coupons:
# CREATE TABLE IF NOT EXISTS payments_coupon (
#     id serial PRIMARY KEY,
#     code varchar(64) NOT NULL UNIQUE,
#     discount_type varchar(20) NOT NULL,
#     discount_value numeric(10,2) NOT NULL,
#     applies_to varchar(20) NOT NULL DEFAULT 'all',
#     max_discount_amount numeric(10,2) NULL,
#     min_order_amount numeric(12,2) NULL,
#     usage_limit integer NULL,
#     usage_limit_per_user integer NULL,
#     current_usage integer NOT NULL DEFAULT 0,
#     is_active boolean NOT NULL DEFAULT true,
#     valid_from timestamptz NOT NULL DEFAULT now(),
#     expires_at timestamptz NULL,
#     created_by_id integer NULL REFERENCES accounts_user(id) ON DELETE SET NULL,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now()
# );
# CREATE INDEX IF NOT EXISTS idx_payments_coupon_code ON payments_coupon (code);
# CREATE INDEX IF NOT EXISTS idx_payments_coupon_active_expires ON payments_coupon (is_active, expires_at);

# PostgreSQL equivalent for coupon redemptions:
# CREATE TABLE IF NOT EXISTS payments_couponredemption (
#     id serial PRIMARY KEY,
#     coupon_id integer NOT NULL REFERENCES payments_coupon(id) ON DELETE CASCADE,
#     user_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     payment_id integer NULL REFERENCES payments_payment(id) ON DELETE SET NULL,
#     discount_amount numeric(10,2) NOT NULL DEFAULT 0,
#     redeemed_at timestamptz NOT NULL DEFAULT now()
# );
# CREATE INDEX IF NOT EXISTS idx_payments_couponredemption_coupon_user ON payments_couponredemption (coupon_id, user_id);
# CREATE INDEX IF NOT EXISTS idx_payments_couponredemption_user_redeemed ON payments_couponredemption (user_id, redeemed_at DESC);
    
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


class PaymentGatewayConfig(models.Model):
    """Configuration for payment gateways"""
    
    GATEWAY_CHOICES = [
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
    ]

    gateway_name = models.CharField(
        max_length=50,
        choices=GATEWAY_CHOICES,
        unique=True
    )
    is_active = models.BooleanField(default=True)
    is_test_mode = models.BooleanField(default=True)
    
    # API credentials (should be encrypted in production)
    public_key = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    webhook_secret = models.CharField(max_length=255, blank=True)
    
    # Configuration
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional gateway-specific configuration"
    )
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Payment Gateway Configs"
    
    def __str__(self):
        mode = "Test" if self.is_test_mode else "Live"
        status = "Active" if self.is_active else "Inactive"
        return f"{self.gateway_name} ({mode}) - {status}"


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


# PostgreSQL equivalent for payment gateway config:
# CREATE TABLE IF NOT EXISTS payments_paymentgatewayconfig (
#     id serial PRIMARY KEY,
#     gateway_name varchar(50) NOT NULL UNIQUE,
#     is_active boolean NOT NULL DEFAULT true,
#     is_test_mode boolean NOT NULL DEFAULT true,
#     public_key varchar(255) NOT NULL,
#     secret_key varchar(255) NOT NULL,
#     webhook_secret varchar(255) NOT NULL DEFAULT '',
#     config jsonb NOT NULL DEFAULT '{}',
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now()
# );

# PostgreSQL equivalent for payment webhook logs:
# CREATE TABLE IF NOT EXISTS payments_paymentwebhooklog (
#     id serial PRIMARY KEY,
#     gateway varchar(50) NOT NULL,
#     event_type varchar(100) NOT NULL,
#     event_id varchar(255) NOT NULL UNIQUE,
#     payment_id integer NULL REFERENCES payments_payment(id) ON DELETE SET NULL,
#     payload jsonb NOT NULL,
#     processed boolean NOT NULL DEFAULT false,
#     processing_error text NOT NULL DEFAULT '',
#     created_at timestamptz NOT NULL DEFAULT now(),
#     processed_at timestamptz NULL
# );
# CREATE INDEX IF NOT EXISTS idx_payments_paymentwebhooklog_gateway_created ON payments_paymentwebhooklog (gateway, created_at DESC);
# CREATE INDEX IF NOT EXISTS idx_payments_paymentwebhooklog_event_id ON payments_paymentwebhooklog (event_id);
# CREATE INDEX IF NOT EXISTS idx_payments_paymentwebhooklog_processed ON payments_paymentwebhooklog (processed);

# PostgreSQL equivalent for payment disputes:
# CREATE TABLE IF NOT EXISTS payments_paymentdispute (
#     id serial PRIMARY KEY,
#     payment_id integer NOT NULL REFERENCES payments_payment(id) ON DELETE CASCADE,
#     dispute_id varchar(255) NOT NULL UNIQUE,
#     amount numeric(12,2) NOT NULL,
#     currency varchar(10) NOT NULL DEFAULT 'USD',
#     reason text NOT NULL,
#     status varchar(20) NOT NULL DEFAULT 'opened',
#     evidence jsonb NOT NULL DEFAULT '{}',
#     admin_notes text NOT NULL DEFAULT '',
#     opened_at timestamptz NOT NULL DEFAULT now(),
#     closed_at timestamptz NULL,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now()
# );


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
