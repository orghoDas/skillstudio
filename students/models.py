from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

User = get_user_model()


class StudentProfile(models.Model):
    """Extended profile information for students."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    
    # Learning preferences
    preferred_learning_style = models.CharField(
        max_length=20,
        choices=[
            ('visual', 'Visual'),
            ('auditory', 'Auditory'),
            ('reading', 'Reading/Writing'),
            ('kinesthetic', 'Kinesthetic'),
        ],
        blank=True,
        null=True
    )
    
    # Goals and interests
    learning_goals = models.TextField(blank=True, help_text="Student's learning objectives")
    interests = models.JSONField(default=list, help_text="List of interest tags")
    
    # Time availability
    weekly_study_hours = models.IntegerField(
        default=0,
        help_text="Target study hours per week"
    )
    preferred_study_time = models.CharField(
        max_length=20,
        choices=[
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
            ('evening', 'Evening'),
            ('night', 'Night'),
        ],
        blank=True,
        null=True
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Student Profile: {self.user.email}"
    
    @property
    def total_courses_enrolled(self) -> int:
        from enrollments.models import Enrollment

        return Enrollment.objects.filter(user_id=self.user_id).count()

    @property
    def total_courses_completed(self) -> int:
        from enrollments.models import Enrollment

        return Enrollment.objects.filter(user_id=self.user_id, is_completed=True).count()

    @property
    def total_certificates_earned(self) -> int:
        from certificates.models import Certificate

        return Certificate.objects.filter(user_id=self.user_id, revoked_at__isnull=True).exclude(
            enrollment__status='canceled',
        ).count()

    @property
    def total_watch_time(self) -> int:
        from enrollments.models import LessonProgress

        return LessonProgress.objects.filter(user_id=self.user_id).aggregate(total=models.Sum('watch_time', default=0))['total']


class LearningActivity(models.Model):
    """One day of learning activity in the timezone used when recording it."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_activity')
    date = models.DateField()
    watch_seconds = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_learning_activity_day'),
        ]


class StudentNote(models.Model):
    """Notes taken by students during lessons."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_notes')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='student_notes')
    
    # Note content
    content = models.TextField()
    timestamp = models.IntegerField(
        default=0,
        help_text="Video timestamp in seconds where note was taken"
    )
    
    # Organization
    is_pinned = models.BooleanField(default=False)
    tags = models.JSONField(default=list)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'lesson']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_pinned', '-created_at']),
        ]
    
    def __str__(self):
        return f"Note by {self.user.email} on {self.lesson.title}"


class StudentBookmark(models.Model):
    """Bookmarked lessons or courses for later review."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    
    # Bookmarked content
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='bookmarks',
        null=True,
        blank=True
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='bookmarks',
        null=True,
        blank=True
    )
    
    # Notes
    note = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'student_bookmarks'
        ordering = ['-created_at']
        unique_together = [
            ['user', 'course'],
            ['user', 'lesson'],
        ]
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        if self.lesson:
            return f"Bookmark: {self.user.email} -> {self.lesson.title}"
        return f"Bookmark: {self.user.email} -> {self.course.title}"


class Wallet(models.Model):
    """Student wallet for purchasing courses."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_wallets'
    
    def __str__(self):
        return f"Wallet: {self.user.email} - ${self.balance}"
    
    def add_money(self, amount, description='Funds added to wallet'):
        """Atomically credit the wallet and record a ledger transaction.

        Returns the created WalletTransaction. Row-locks the wallet so
        concurrent credits/debits cannot lose updates.
        """
        return self._apply_delta('credit', amount, description)

    def deduct_money(self, amount, description='Purchase'):
        """Atomically debit the wallet and record a ledger transaction.

        Returns the created WalletTransaction. Raises ValueError on
        insufficient balance (checked under the row lock).
        """
        return self._apply_delta('debit', amount, description)

    def _apply_delta(self, kind, amount, description):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        with transaction.atomic():
            # Re-read under a row lock so the balance check and write are atomic.
            locked = Wallet.objects.select_for_update().get(pk=self.pk)
            if kind == 'debit':
                if locked.balance < amount:
                    raise ValueError("Insufficient balance")
                locked.balance -= amount
            else:
                locked.balance += amount
            locked.save(update_fields=['balance', 'updated_at'])
            txn = WalletTransaction.objects.create(
                wallet=locked,
                transaction_type=kind,
                amount=amount,
                description=description,
                balance_after=locked.balance,
            )
            # Keep this instance's in-memory balance consistent for callers.
            self.balance = locked.balance
        return txn


class WalletTransaction(models.Model):
    """Transaction history for wallet."""
    
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'wallet_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type}: ${self.amount} - {self.description}"
