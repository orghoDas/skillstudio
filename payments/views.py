"""
Payment Views
API endpoints for payment processing, refunds, payouts, and coupons
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from decimal import Decimal
from django.utils import timezone

from payments.models import Payment, Payout, Refund, Coupon
from payments.serializers import (
    PaymentSerializer, PaymentCreateSerializer,
    PayoutSerializer, PayoutRequestSerializer,
    RefundSerializer, RefundRequestSerializer,
    CouponSerializer, CouponCreateSerializer, CouponValidationSerializer,
    PaymentStatsSerializer, InstructorBalanceSerializer
)
from payments import services
from accounts.permissions import IsInstructor, IsAdmin
from courses.models import Course
from events.models import Event


# ==========================================
# PAYMENT VIEWS
# ==========================================

class PaymentListView(APIView):
    """List user's payments"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        payments = Payment.objects.filter(user=request.user).order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)


class PaymentCreateView(APIView):
    """Create a new payment"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get course or event
        course = None
        event = None
        
        if data.get('course_id'):
            try:
                course = Course.objects.get(id=data['course_id'])
            except Course.DoesNotExist:
                return Response(
                    {'error': 'Course not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if data.get('event_id'):
            try:
                event = Event.objects.get(id=data['event_id'])
            except Event.DoesNotExist:
                return Response(
                    {'error': 'Event not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        try:
            payment = services.create_payment(
                user=request.user,
                amount=data['amount'],
                course=course,
                event=event,
                payment_method=data.get('payment_method', 'stripe'),
                coupon_code=data.get('coupon_code'),
                billing_email=data.get('billing_email'),
                billing_address=data.get('billing_address'),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response(
                PaymentSerializer(payment).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


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
    """Cancel a pending payment"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
            
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
        if hasattr(request.user, 'is_staff') and request.user.is_staff:
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
    """List coupons (admin) or active coupons (public)"""
    
    def get(self, request):
        if hasattr(request.user, 'is_staff') and request.user.is_staff:
            # Admin sees all coupons
            coupons = Coupon.objects.all().order_by('-created_at')
        else:
            # Public sees only active coupons
            coupons = services.get_active_coupons()
        
        serializer = CouponSerializer(coupons, many=True)
        return Response(serializer.data)


class CouponCreateView(APIView):
    """Create a coupon (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @transaction.atomic
    def post(self, request):
        serializer = CouponCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            # Handle specific courses/events
            specific_course_ids = data.pop('specific_course_ids', [])
            specific_event_ids = data.pop('specific_event_ids', [])
            
            # Extract required parameters
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
            
            # Add specific courses/events
            if specific_course_ids:
                coupon.specific_courses.set(specific_course_ids)
            if specific_event_ids:
                coupon.specific_events.set(specific_event_ids)
            
            return Response(
                CouponSerializer(coupon).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CouponValidateView(APIView):
    """Validate a coupon"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = CouponValidationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get course or event
        course = None
        event = None
        
        if data.get('course_id'):
            try:
                course = Course.objects.get(id=data['course_id'])
            except Course.DoesNotExist:
                pass
        
        if data.get('event_id'):
            try:
                event = Event.objects.get(id=data['event_id'])
            except Event.DoesNotExist:
                pass
        
        try:
            coupon = services.validate_and_apply_coupon(
                coupon_code=data['code'],
                user=request.user,
                amount=data['amount'],
                course=course,
                event=event
            )
            
            discount = services.calculate_coupon_discount(coupon, data['amount'])
            final_amount = data['amount'] - discount
            
            return Response({
                'valid': True,
                'coupon': CouponSerializer(coupon).data,
                'original_amount': float(data['amount']),
                'discount_amount': float(discount),
                'final_amount': float(final_amount)
            })
        
        except Exception as e:
            return Response(
                {'valid': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


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
