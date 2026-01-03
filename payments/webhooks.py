"""
Payment Webhooks
Webhook handlers for payment gateways (Stripe, PayPal)
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
import json
import logging

from payments.models import Payment, PaymentWebhookLog
from payments import services

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    """Handle Stripe webhook events"""
    
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        try:
            event_data = json.loads(payload)
            event_id = event_data.get('id')
            event_type = event_data.get('type')
            
            # Log webhook
            webhook_log = services.log_webhook_event(
                gateway='stripe',
                event_type=event_type,
                event_id=event_id,
                payload=event_data
            )
            
            # Process event
            try:
                self._process_stripe_event(event_data, webhook_log)
                services.mark_webhook_processed(webhook_log)
                
                return Response({'status': 'success'}, status=status.HTTP_200_OK)
            
            except Exception as e:
                logger.error(f"Error processing Stripe webhook: {str(e)}")
                services.mark_webhook_processed(webhook_log, error=str(e))
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error parsing Stripe webhook: {str(e)}")
            return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
    
    def _process_stripe_event(self, event_data, webhook_log):
        """Process different Stripe event types"""
        event_type = event_data.get('type')
        event_obj = event_data.get('data', {}).get('object', {})
        
        if event_type == 'payment_intent.succeeded':
            self._handle_payment_success(event_obj, webhook_log)
        
        elif event_type == 'payment_intent.payment_failed':
            self._handle_payment_failure(event_obj, webhook_log)
        
        elif event_type == 'charge.refunded':
            self._handle_refund(event_obj, webhook_log)
        
        elif event_type == 'charge.dispute.created':
            self._handle_dispute(event_obj, webhook_log)
        
        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")
    
    def _handle_payment_success(self, payment_intent, webhook_log):
        """Handle successful payment"""
        provider_id = payment_intent.get('id')
        
        # Find payment by provider_id or metadata
        payment = services.get_payment_by_provider_id('stripe', provider_id)
        
        if payment:
            services.process_payment_success(
                payment=payment,
                provider_id=provider_id,
                metadata={'stripe_payment_intent': payment_intent}
            )
            webhook_log.payment = payment
            webhook_log.save(update_fields=['payment'])
            logger.info(f"Payment {payment.id} marked as successful")
    
    def _handle_payment_failure(self, payment_intent, webhook_log):
        """Handle failed payment"""
        provider_id = payment_intent.get('id')
        error = payment_intent.get('last_payment_error', {})
        
        payment = services.get_payment_by_provider_id('stripe', provider_id)
        
        if payment:
            services.process_payment_failure(
                payment=payment,
                reason=error.get('message', 'Payment failed'),
                metadata={'stripe_error': error}
            )
            webhook_log.payment = payment
            webhook_log.save(update_fields=['payment'])
            logger.warning(f"Payment {payment.id} marked as failed")
    
    def _handle_refund(self, charge, webhook_log):
        """Handle refund"""
        charge_id = charge.get('id')
        refunds = charge.get('refunds', {}).get('data', [])
        
        payment = services.get_payment_by_provider_id('stripe', charge_id)
        
        if payment and refunds:
            refund = refunds[0]  # Get first refund
            
            # Find matching refund in our system
            payment_refund = payment.refunds.filter(status='approved').first()
            
            if payment_refund:
                services.process_refund(
                    refund=payment_refund,
                    provider_refund_id=refund.get('id')
                )
                logger.info(f"Refund {payment_refund.id} processed")
    
    def _handle_dispute(self, dispute, webhook_log):
        """Handle dispute/chargeback"""
        charge_id = dispute.get('charge')
        
        payment = services.get_payment_by_provider_id('stripe', charge_id)
        
        if payment:
            services.create_dispute(
                payment=payment,
                dispute_id=dispute.get('id'),
                amount=dispute.get('amount', 0) / 100,  # Convert cents to dollars
                reason=dispute.get('reason', 'Unknown')
            )
            logger.warning(f"Dispute created for payment {payment.id}")


@method_decorator(csrf_exempt, name='dispatch')
class PayPalWebhookView(APIView):
    """Handle PayPal webhook events"""
    
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        payload = request.body
        
        try:
            event_data = json.loads(payload)
            event_id = event_data.get('id')
            event_type = event_data.get('event_type')
            
            # Log webhook
            webhook_log = services.log_webhook_event(
                gateway='paypal',
                event_type=event_type,
                event_id=event_id,
                payload=event_data
            )
            
            # Process event
            try:
                self._process_paypal_event(event_data, webhook_log)
                services.mark_webhook_processed(webhook_log)
                
                return Response({'status': 'success'}, status=status.HTTP_200_OK)
            
            except Exception as e:
                logger.error(f"Error processing PayPal webhook: {str(e)}")
                services.mark_webhook_processed(webhook_log, error=str(e))
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error parsing PayPal webhook: {str(e)}")
            return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
    
    def _process_paypal_event(self, event_data, webhook_log):
        """Process different PayPal event types"""
        event_type = event_data.get('event_type')
        resource = event_data.get('resource', {})
        
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            self._handle_payment_success(resource, webhook_log)
        
        elif event_type == 'PAYMENT.CAPTURE.DENIED':
            self._handle_payment_failure(resource, webhook_log)
        
        elif event_type == 'PAYMENT.CAPTURE.REFUNDED':
            self._handle_refund(resource, webhook_log)
        
        else:
            logger.info(f"Unhandled PayPal event type: {event_type}")
    
    def _handle_payment_success(self, capture, webhook_log):
        """Handle successful payment"""
        provider_id = capture.get('id')
        
        payment = services.get_payment_by_provider_id('paypal', provider_id)
        
        if payment:
            services.process_payment_success(
                payment=payment,
                provider_id=provider_id,
                metadata={'paypal_capture': capture}
            )
            webhook_log.payment = payment
            webhook_log.save(update_fields=['payment'])
            logger.info(f"PayPal payment {payment.id} marked as successful")
    
    def _handle_payment_failure(self, capture, webhook_log):
        """Handle failed payment"""
        provider_id = capture.get('id')
        
        payment = services.get_payment_by_provider_id('paypal', provider_id)
        
        if payment:
            services.process_payment_failure(
                payment=payment,
                reason='Payment denied by PayPal',
                metadata={'paypal_capture': capture}
            )
            webhook_log.payment = payment
            webhook_log.save(update_fields=['payment'])
            logger.warning(f"PayPal payment {payment.id} marked as failed")
    
    def _handle_refund(self, refund, webhook_log):
        """Handle refund"""
        # PayPal refunds reference the original capture
        # Would need to implement lookup logic based on your PayPal integration
        logger.info(f"PayPal refund processed: {refund.get('id')}")
