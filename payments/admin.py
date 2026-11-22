"""
Payment Admin Configuration
Django admin interface for payment models
"""

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from core.admin import DecisionForm, ReadOnlyAdmin, WorkflowAdmin
from payments import services
from payments.models import (
    Payment, Payout, Refund, Coupon, CouponRedemption,
    PaymentWebhookLog, PaymentDispute
)


class MonetaryWorkflowAdmin(WorkflowAdmin):
    def apply_decision(self, request, obj, data):
        try:
            return self.process_decision(request, obj, data)
        except services.PaymentsError as error:
            raise ValidationError(error.message) from error


class PayoutDecisionForm(DecisionForm):
    transaction_id = forms.CharField(required=False, max_length=255, label='Transfer reference')

    def __init__(self, *args, choices, **kwargs):
        super().__init__(*args, choices=choices, **kwargs)
        self.fields['note'].label = 'Approval note or rejection reason'
        if not any(value == 'complete' for value, _ in choices):
            self.fields.pop('transaction_id')

    def clean(self):
        data = super().clean()
        if data.get('action') == 'complete' and not data.get('transaction_id'):
            self.add_error('transaction_id', 'Enter the reference from the completed bank transfer.')
        return data


class RefundDecisionForm(DecisionForm):
    absorb_shortfall = forms.BooleanField(required=False, label='Cover an instructor shortfall from the platform')


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdmin):
    list_display = [
        'id', 'user_email', 'amount_display', 'status_display',
        'payment_method', 'item_display', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['user__email', 'provider_id', 'billing_email']
    readonly_fields = [
        'id', 'user', 'instructor', 'course',
        'amount', 'status',
        'platform_fee', 'instructor_earnings', 'provider_id',
        'created_at', 'updated_at', 'completed_at'
    ]
    date_hierarchy = 'created_at'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def amount_display(self, obj):
        return f"${obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'gray',
            'disputed': 'purple',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'
    
    def item_display(self, obj):
        if obj.course:
            return f"Course: {obj.course.title}"
        return "N/A"
    item_display.short_description = 'Item'


@admin.register(Payout)
class PayoutAdmin(MonetaryWorkflowAdmin):
    decision_form = PayoutDecisionForm
    decision_help = 'Record a payout as sent only after the external transfer is complete. Rejecting returns the reserved funds to the instructor’s wallet.'
    exclude = ('account_details_encrypted', 'provider_details')
    list_select_related = ('instructor',)

    def decision_details(self, obj):
        return [
            *super().decision_details(obj),
            ('Instructor', obj.instructor.email),
            ('Amount', f'{obj.currency} {obj.amount}'),
            ('Method', obj.get_payout_method_display()),
            ('Destination on file', 'Yes' if obj.account_details_encrypted else 'No'),
        ]

    def workflow_choices(self, obj):
        if obj.status == 'pending':
            return [('approve', 'Approve payout'), ('reject', 'Reject payout')]
        if obj.status == 'processing':
            return [('complete', 'Record as sent'), ('reject', 'Reject payout')]
        return []

    def process_decision(self, request, obj, data):
        if data['action'] == 'approve':
            services.approve_payout(obj.pk, request.user, data['note'])
            return 'Payout approved.'
        if data['action'] == 'complete':
            services.complete_payout(obj.pk, data['transaction_id'], admin_user=request.user)
            return 'Payout recorded as sent.'
        services.reject_payout(obj.pk, request.user, data['note'])
        return 'Payout rejected.'

    list_display = [
        'id', 'instructor_email', 'amount_display', 'status_display',
        'payout_method', 'created_at'
    ]
    list_filter = ['status', 'wallet_debited', 'payout_method', 'created_at']
    search_fields = ['instructor__email', 'transaction_id']
    readonly_fields = [
        'id', 'instructor', 'amount', 'status', 'wallet_debited',
        'created_at', 'updated_at', 'processed_at', 'destination_on_file',
    ]
    date_hierarchy = 'created_at'
    filter_horizontal = ['payments']

    @admin.display(boolean=True, description='Payout destination on file')
    def destination_on_file(self, obj):
        return bool(obj.account_details_encrypted)
    
    def instructor_email(self, obj):
        return obj.instructor.email
    instructor_email.short_description = 'Instructor'
    
    def amount_display(self, obj):
        return f"${obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'paid': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'


@admin.register(Refund)
class RefundAdmin(MonetaryWorkflowAdmin):
    decision_form = RefundDecisionForm
    decision_help = 'Approving immediately returns money to the buyer’s wallet. Review the payment and request before submitting.'
    list_select_related = ('payment', 'requested_by')

    def decision_details(self, obj):
        return [
            *super().decision_details(obj),
            ('Requested by', obj.requested_by.email if obj.requested_by else '—'),
            ('Amount', f'{obj.payment.currency} {obj.amount}'),
            ('Course', obj.payment.course or '—'),
            ('Reason', obj.reason),
        ]

    def workflow_choices(self, obj):
        return [('approve', 'Approve wallet refund'), ('reject', 'Reject refund')] if obj.status == 'requested' else []

    def process_decision(self, request, obj, data):
        if data['action'] == 'approve':
            services.approve_refund(obj.pk, request.user, data['note'], absorb_shortfall=data['absorb_shortfall'])
            return 'Wallet refund approved.'
        services.reject_refund(obj.pk, request.user, data['note'])
        return 'Refund rejected.'

    list_display = [
        'id', 'payment_id', 'amount_display', 'refund_type',
        'status_display', 'requested_by_email', 'created_at'
    ]
    list_filter = ['status', 'refund_type', 'created_at']
    search_fields = ['payment__id', 'requested_by__email', 'reason']
    readonly_fields = [
        'id', 'payment', 'requested_by', 'requested_at', 'amount', 'status',
        'refund_type', 'instructor_debit', 'platform_absorbed',
        'created_at', 'updated_at', 'processed_at'
    ]
    date_hierarchy = 'created_at'
    
    def payment_id(self, obj):
        return obj.payment.id
    payment_id.short_description = 'Payment ID'
    
    def requested_by_email(self, obj):
        return obj.requested_by.email if obj.requested_by else 'N/A'
    requested_by_email.short_description = 'Requested By'
    
    def amount_display(self, obj):
        return f"${obj.amount}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'requested': 'orange',
            'approved': 'blue',
            'processed': 'green',
            'rejected': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'discount_display', 'is_active', 'is_valid',
        'usage_display', 'expires_at', 'created_at'
    ]
    list_filter = ['is_active', 'discount_type', 'applies_to', 'created_at']
    search_fields = ['code']
    readonly_fields = ['id', 'current_usage', 'is_valid', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    filter_horizontal = ['specific_courses']
    
    def discount_display(self, obj):
        if obj.discount_type == Coupon.PERCENT:
            return f"{obj.discount_value}%"
        return f"${obj.discount_value}"
    discount_display.short_description = 'Discount'
    
    def usage_display(self, obj):
        if obj.usage_limit:
            return f"{obj.current_usage} / {obj.usage_limit}"
        return str(obj.current_usage)
    usage_display.short_description = 'Usage'


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(ReadOnlyAdmin):
    list_display = ['id', 'coupon_code', 'user_email', 'discount_amount', 'redeemed_at']
    list_filter = ['redeemed_at']
    search_fields = ['coupon__code', 'user__email']
    readonly_fields = ['id', 'coupon', 'user', 'payment', 'redeemed_at']
    date_hierarchy = 'redeemed_at'
    
    def coupon_code(self, obj):
        return obj.coupon.code
    coupon_code.short_description = 'Coupon'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(ReadOnlyAdmin):
    list_display = [
        'id', 'gateway', 'event_type', 'event_id',
        'processed_display', 'payment_id', 'created_at'
    ]
    list_filter = ['gateway', 'processed', 'created_at']
    search_fields = ['event_id', 'event_type']
    readonly_fields = ['id', 'gateway', 'event_type', 'event_id', 'payload', 'created_at', 'processed_at']
    date_hierarchy = 'created_at'
    
    def payment_id(self, obj):
        return obj.payment.id if obj.payment else 'N/A'
    payment_id.short_description = 'Payment'
    
    def processed_display(self, obj):
        color, label = ('green', 'Processed') if obj.processed else ('orange', 'Pending')
        return format_html('<span style="color: {};">{}</span>', color, label)
    processed_display.short_description = 'Status'


@admin.register(PaymentDispute)
class PaymentDisputeAdmin(ReadOnlyAdmin):
    list_display = [
        'dispute_id', 'payment_id', 'amount_display',
        'status_display', 'opened_at'
    ]
    list_filter = ['status', 'opened_at']
    search_fields = ['dispute_id', 'payment__id']
    readonly_fields = ['id', 'payment', 'dispute_id', 'opened_at', 'created_at', 'updated_at']
    date_hierarchy = 'opened_at'
    
    def payment_id(self, obj):
        return obj.payment.id
    payment_id.short_description = 'Payment ID'
    
    def amount_display(self, obj):
        return f"${obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'opened': 'orange',
            'under_review': 'blue',
            'won': 'green',
            'lost': 'red',
            'closed': 'gray',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'
