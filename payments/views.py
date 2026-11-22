"""
Payment Views
API endpoints for payment history, refunds, payouts, and coupons.

There is deliberately no "pay for a course by card" endpoint: courses are
bought from the wallet via POST /api/enrollments/enroll/ (payments.services.
purchase_course), and money enters the wallet only through the Stripe
test-mode top-up flow (AUDIT_REPORT.md Decision D-01).
"""

from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from decimal import Decimal
from django.utils import timezone

from payments.models import Payment, Payout, Refund, Coupon
from payments.serializers import (
    PaymentSerializer,
    PayoutSerializer, PayoutRequestSerializer,
    RefundSerializer, RefundRequestSerializer,
    CouponSerializer, CouponCreateSerializer, CouponValidationSerializer,
    PublicCouponSerializer,
    PaymentStatsSerializer, InstructorBalanceSerializer
)
from payments import services
from accounts.permissions import IsInstructor, IsAdmin
from accounts.utils import is_platform_admin
from courses.models import Course
from core.pagination import SummaryPageNumberPagination
from students.activity import learning_timezone


# ==========================================
# PAYMENT VIEWS
# ==========================================

class PaymentHistoryPagination(SummaryPageNumberPagination):
    summary_properties = {
        'successful_count': {'type': 'integer'}, 'pending_count': {'type': 'integer'},
        'total_spent': {'type': 'string'}, 'month_spent': {'type': 'string'},
    }


class PaymentListView(ListAPIView):
    """List the user's payments (top-ups and course purchases).

    Optional filters: ?status=<status>&purpose=<course_purchase|wallet_topup>
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    pagination_class = PaymentHistoryPagination

    def get_queryset(self):
        payments = (
            Payment.objects.filter(user=self.request.user)
            .select_related('course', 'instructor', 'user')
            .order_by('-created_at', '-pk')
        )
        status_filter = self.request.query_params.get('status')
        if status_filter:
            payments = payments.filter(status=status_filter)
        purpose = self.request.query_params.get('purpose')
        if purpose:
            payments = payments.filter(purpose=purpose)
        return payments

    def list(self, request, *args, **kwargs):
        payments = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(payments)
        month_start = timezone.localtime(timezone=learning_timezone(request)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        successful = Q(status__in=('completed', 'partially_refunded'))
        purchases = Q(status__in=services.SETTLED_PAYMENT_STATUSES, purpose=Payment.PURPOSE_COURSE_PURCHASE)
        summary = services.with_payment_refunds(payments).aggregate(
            successful_count=Count('pk', filter=successful),
            pending_count=Count('pk', filter=Q(status='pending')),
            total_spent=Sum('net_amount', filter=purchases, default=0),
            month_spent=Sum('net_amount', filter=purchases & Q(created_at__gte=month_start), default=0),
        )
        for field in ('total_spent', 'month_spent'):
            summary[field] = format(summary[field], '.2f')
        response = self.get_paginated_response(self.get_serializer(page, many=True).data)
        response.data['summary'] = summary
        return response


class PaymentDetailView(APIView):
    """Get payment details"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
            serializer = PaymentSerializer(payment)
            return Response(serializer.data)
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class PaymentCancelView(APIView):
    """Cancel one of the user's own pending payments (e.g. an abandoned top-up)."""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, payment_id):
        try:
            # Row lock so a cancel can't race the webhook that completes it.
            payment = Payment.objects.select_for_update().get(id=payment_id, user=request.user)
            
            if payment.status != 'pending':
                return Response(
                    {'error': 'Only pending payments can be cancelled'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            payment.status = 'cancelled'
            payment.save(update_fields=['status', 'updated_at'])
            
            return Response({'message': 'Payment cancelled successfully'})
        
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ==========================================
# REFUND VIEWS
# ==========================================
# Refunds of course purchases go back to the student's wallet (PAY-08).

def _payments_error_response(exc):
    """Map a PaymentsError to an API error response."""
    code = {
        "not_found": status.HTTP_404_NOT_FOUND,
        "payout_details_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    }.get(exc.code, status.HTTP_400_BAD_REQUEST)
    return Response({'detail': exc.message, 'code': exc.code}, status=code)


class RefundListView(ListAPIView):
    """Admins see all refunds; everyone else sees the refunds they requested."""
    permission_classes = [IsAuthenticated]
    serializer_class = RefundSerializer

    def get_queryset(self):
        if is_platform_admin(self.request.user):
            refunds = Refund.objects.all()
        else:
            refunds = Refund.objects.filter(requested_by=self.request.user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            refunds = refunds.filter(status=status_filter)
        return refunds.select_related('payment', 'requested_by', 'processed_by').order_by('-created_at', '-pk')


class RefundRequestView(APIView):
    """Request a refund of one of your course purchases (amount defaults to all refundable)."""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RefundRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            refund = services.request_refund(
                user=request.user,
                payment_id=data['payment_id'],
                reason=data['reason'],
                amount=data.get('amount'),
            )
        except services.PaymentsError as exc:
            return _payments_error_response(exc)
        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)


class RefundApproveView(APIView):
    """Approve a refund (admin only). Money moves immediately, wallet to wallet.

    Body: {"notes": str, "absorb_shortfall": bool} — absorb_shortfall lets the
    platform cover what the instructor's wallet can't.
    """
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, refund_id):
        absorb = str(request.data.get('absorb_shortfall', '')).lower() in ('1', 'true', 'yes')
        try:
            refund = services.approve_refund(
                refund_id, request.user, notes=request.data.get('notes', ''), absorb_shortfall=absorb,
            )
        except services.PaymentsError as exc:
            return _payments_error_response(exc)
        return Response(RefundSerializer(refund).data)


class RefundRejectView(APIView):
    """Reject a refund (admin only)"""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, refund_id):
        try:
            refund = services.reject_refund(refund_id, request.user, request.data.get('reason', ''))
        except services.PaymentsError as exc:
            return _payments_error_response(exc)
        return Response(RefundSerializer(refund).data)


# ==========================================
# PAYOUT VIEWS
# ==========================================
# Withdrawable money = the instructor's wallet balance. Requesting a payout
# reserves (debits) the amount immediately (PAY-06 / PAY-07).

class PayoutListView(ListAPIView):
    """Instructors see their payouts; admins see all (optional ?status=)."""
    permission_classes = [IsAuthenticated, IsInstructor]
    serializer_class = PayoutSerializer

    def get_queryset(self):
        if is_platform_admin(self.request.user):
            payouts = Payout.objects.all()
        else:
            payouts = Payout.objects.filter(instructor=self.request.user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            payouts = payouts.filter(status=status_filter)
        return payouts.select_related('instructor', 'instructor__profile').order_by('-created_at', '-pk')


class PayoutRequestView(APIView):
    """Request a payout from your wallet balance (amount defaults to all of it)."""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsInstructor]

    def post(self, request):
        serializer = PayoutRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            payout = services.create_payout(
                instructor=request.user,
                amount=data.get('amount'),
                payout_method=data.get('payout_method', 'stripe_connect'),
                account_details=data.get('account_details'),
            )
        except services.PaymentsError as exc:
            return _payments_error_response(exc)
        return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)


class PayoutBalanceView(APIView):
    """Get instructor balance"""
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        balance = services.calculate_instructor_balance(request.user)
        serializer = InstructorBalanceSerializer(balance)
        return Response(serializer.data)


class PayoutCancelView(APIView):
    """Instructor cancels their own pending payout; the amount returns to the wallet."""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsInstructor]

    def post(self, request, payout_id):
        try:
            payout = services.cancel_payout(payout_id, request.user)
        except services.PaymentsError as exc:
            return _payments_error_response(exc)
        return Response(PayoutSerializer(payout).data)


class PayoutApproveView(APIView):
    """Approve a payout (admin only): pending -> processing."""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, payout_id):
        try:
            payout = services.approve_payout(payout_id, request.user, request.data.get('notes', ''))
        except services.PaymentsError as exc:
            return _payments_error_response(exc)
        return Response(PayoutSerializer(payout).data)


class PayoutCompleteView(APIView):
    """Mark a payout as sent (admin only): processing -> paid. Body: {"transaction_id"}."""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, payout_id):
        try:
            payout = services.complete_payout(
                payout_id, request.data.get('transaction_id', ''), admin_user=request.user,
            )
        except services.PaymentsError as exc:
            return _payments_error_response(exc)
        return Response(PayoutSerializer(payout).data)


class PayoutRejectView(APIView):
    """Reject a payout (admin only); the reserved amount returns to the wallet."""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, payout_id):
        try:
            payout = services.reject_payout(payout_id, request.user, request.data.get('reason', ''))
        except services.PaymentsError as exc:
            return _payments_error_response(exc)
        return Response(PayoutSerializer(payout).data)


# ==========================================
# COUPON VIEWS
# ==========================================

class CouponListView(ListAPIView):
    """Admins see every coupon; everyone else sees only public, active coupons.

    Private coupon codes are never listed (PAY-09) — they are shared
    out-of-band and still work at checkout for whoever has them.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return CouponSerializer if is_platform_admin(self.request.user) else PublicCouponSerializer

    def get_queryset(self):
        if is_platform_admin(self.request.user):
            return Coupon.objects.select_related('created_by').order_by('-created_at', '-pk')
        return services.get_active_coupons().filter(is_public=True).order_by('-created_at', '-pk')


class CouponCreateView(APIView):
    """Create a coupon (admin only)"""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @transaction.atomic
    def post(self, request):
        serializer = CouponCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        specific_course_ids = data.pop('specific_course_ids', [])
        code = data.pop('code')
        discount_type = data.pop('discount_type')
        discount_value = data.pop('discount_value')

        coupon = services.create_coupon(
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            created_by=request.user,
            **data
        )

        if specific_course_ids:
            coupon.specific_courses.set(specific_course_ids)

        return Response(CouponSerializer(coupon).data, status=status.HTTP_201_CREATED)


class CouponValidateView(APIView):
    """Preview a coupon for a course before buying it.

    The price is always the server-side course price; the response is a
    quote only — the real charge happens in POST /api/enrollments/enroll/.
    """
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CouponValidationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        course = Course.objects.filter(id=data['course_id'], status='published').first()
        if course is None:
            return Response(
                {'valid': False, 'error': 'Course not found or not published.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            quote = services.quote_course_price(request.user, course, data['code'])
        except DjangoValidationError as exc:
            return Response(
                {'valid': False, 'error': exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'valid': True,
            'coupon': PublicCouponSerializer(quote.coupon).data,
            'original_amount': str(quote.original_amount),
            'discount_amount': str(quote.discount_amount),
            'final_amount': str(quote.final_amount),
        })


class CouponDeactivateView(APIView):
    """Deactivate a coupon (admin only)"""
    throttle_scope = "payments"
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @transaction.atomic
    def delete(self, request, coupon_id):
        try:
            coupon = services.deactivate_coupon(coupon_id)
            return Response({'message': f'Coupon {coupon.code} deactivated'})
        except Coupon.DoesNotExist:
            return Response(
                {'error': 'Coupon not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ==========================================
# ANALYTICS VIEWS
# ==========================================

class PaymentStatsView(APIView):
    """Get payment statistics (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Parse dates if provided
        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date)
        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date)
        
        stats = services.get_payment_stats(start_date, end_date)
        serializer = PaymentStatsSerializer(stats)
        return Response(serializer.data)


class InstructorEarningsView(APIView):
    """Get instructor earnings"""
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date)
        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date)
        
        earnings = services.get_instructor_earnings(request.user, start_date, end_date)
        
        return Response(earnings)
