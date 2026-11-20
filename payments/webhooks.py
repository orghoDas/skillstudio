"""
Payment webhooks.

Only Stripe is used, in test mode, and only for wallet top-ups
(AUDIT_REPORT.md Decision D-01). Until the verified handler exists, this
endpoint rejects every request so that nobody can forge a "payment succeeded"
event (PAY-04).

When the Stripe flow is built, this view must, in order:
  1. verify the signature: stripe.Webhook.construct_event(request.body,
     request.META["HTTP_STRIPE_SIGNATURE"], settings.STRIPE_WEBHOOK_SECRET);
  2. de-duplicate by Stripe event id (unique PaymentWebhookLog row);
  3. for checkout.session.completed / payment_intent.succeeded, lock the
     pending wallet_topup Payment named in the event metadata, move it
     pending -> completed and credit the wallet in the same transaction;
  4. never trust the browser's success redirect, and never echo errors or
     store full provider payloads.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class StripeWebhookView(APIView):
    """Stripe webhook endpoint — disabled until signature verification exists."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        logger.warning(
            "Rejected Stripe webhook: the verified handler is not implemented yet "
            "(remote_addr=%s)", request.META.get("REMOTE_ADDR")
        )
        return Response(
            {"detail": "Stripe webhooks are not enabled."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
