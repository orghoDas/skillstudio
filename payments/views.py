"""
Payment Views
API endpoints for payment history, refunds, payouts, and coupons.

There is deliberately no "pay for a course by card" endpoint: courses are
bought from the wallet via POST /api/enrollments/enroll/ (payments.services.
purchase_course), and money enters the wallet only through the Stripe
test-mode top-up flow (AUDIT_REPORT.md Decision D-01).
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
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


# ==========================================
# PAYMENT VIEWS
# ==========================================

class PaymentListView(APIView):
    """List the user's payments (top-ups and course purchases).

    Optional filters: ?status=<status>&purpose=<course_purchase|wallet_topup>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = (
            Payment.objects.filter(user=request.user)
            .select_related('course', 'instructor')
            .order_by('-created_at')
        )
        status_filter = request.query_params.get('status')
        if status_filter:
            payments = payments.filter(status=status_filter)
        purpose = request.query_params.get('purpose')
        if purpose:
            payments = payments.filter(purpose=purpose)
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)


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

class RefundListView(APIView):
    """List refunds"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Users see their own refunds, admins see all
        if is_platform_admin(request.user):
            refunds = Refund.objects.all()
        else:
            refunds = Refund.objects.filter(requested_by=request.user)
        
        refunds = refunds.order_by('-created_at')
        serializer = RefundSerializer(refunds, many=True)
        return Response(serializer.data)


class RefundRequestView(APIView):
    """Request a refund"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        serializer = RefundRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            payment = Payment.objects.get(id=data['payment_id'], user=request.user)
            
            refund = services.request_refund(
                payment=payment,
                amount=data['amount'],
                reason=data['reason'],
                user=request.user,
                refund_type=data.get('refund_type', 'full')
            )
            
            return Response(
                RefundSerializer(refund).data,
                status=status.HTTP_201_CREATED
            )
        
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class RefundApproveView(APIView):
    """Approve a refund (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @transaction.atomic
    def post(self, request, refund_id):
        try:
            refund = Refund.objects.get(id=refund_id)
            notes = request.data.get('notes', '')
            
            refund = services.approve_refund(refund, request.user, notes)
            
            return Response(RefundSerializer(refund).data)
        
        except Refund.DoesNotExist:
            return Response(
                {'error': 'Refund not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class RefundRejectView(APIView):
    """Reject a refund (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @transaction.atomic
    def post(self, request, refund_id):
        try:
            refund = Refund.objects.get(id=refund_id)
            reason = request.data.get('reason', 'No reason provided')
            
            refund = services.reject_refund(refund, request.user, reason)
            
            return Response(RefundSerializer(refund).data)
        
        except Refund.DoesNotExist:
            return Response(
                {'error': 'Refund not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ==========================================
# PAYOUT VIEWS
# ==========================================

class PayoutListView(APIView):
    """List payouts"""
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def get(self, request):
        payouts = Payout.objects.filter(instructor=request.user).order_by('-created_at')
        serializer = PayoutSerializer(payouts, many=True)
        return Response(serializer.data)


class PayoutRequestView(APIView):
    """Request a payout"""
    permission_classes = [IsAuthenticated, IsInstructor]
    
    @transaction.atomic
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
                account_details=data.get('account_details')
            )
            
            return Response(
                PayoutSerializer(payout).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PayoutBalanceView(APIView):
    """Get instructor balance"""
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def get(self, request):
        balance = services.calculate_instructor_balance(request.user)
        serializer = InstructorBalanceSerializer(balance)
        return Response(serializer.data)


class PayoutApproveView(APIView):
    """Approve a payout (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @transaction.atomic
    def post(self, request, payout_id):
        try:
            payout = Payout.objects.get(id=payout_id)
            notes = request.data.get('notes', '')
            
            payout = services.approve_payout(payout, request.user, notes)
            
            return Response(PayoutSerializer(payout).data)
        
        except Payout.DoesNotExist:
            return Response(
                {'error': 'Payout not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ==========================================
# COUPON VIEWS
# ==========================================

class CouponListView(APIView):
    """Admins see every coupon; everyone else sees only public, active coupons.

    Private coupon codes are never listed (PAY-09) — they are shared
    out-of-band and still work at checkout for whoever has them.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if is_platform_admin(request.user):
            coupons = Coupon.objects.all().order_by('-created_at')
            return Response(CouponSerializer(coupons, many=True).data)

        coupons = services.get_active_coupons().filter(is_public=True)
        return Response(PublicCouponSerializer(coupons, many=True).data)


class CouponCreateView(APIView):
    """Create a coupon (admin only)"""
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

        try:
            coupon = services.create_coupon(
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                created_by=request.user,
                **data
            )
        except DjangoValidationError as exc:
            return Response({'error': exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        if specific_course_ids:
            coupon.specific_courses.set(specific_course_ids)

        return Response(CouponSerializer(coupon).data, status=status.HTTP_201_CREATED)


class CouponValidateView(APIView):
    """Preview a coupon for a course before buying it.

    The price is always the server-side course price; the response is a
    quote only — the real charge happens in POST /api/enrollments/enroll/.
    """
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
