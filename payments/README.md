# payments

Money: course purchases, platform fee, coupons, refunds, payouts, webhook log and disputes.

## The one money path (Decision D-01)
1. Money enters a student's wallet through a top-up. The top-up will use Stripe in **test mode**; it isn't built yet, and the webhook returns `503`.
2. **`purchase_course(user, course_id, coupon_code=None)`** is the only way to buy a course.
   - It is idempotent per (user, course).
   - It locks both wallets in a fixed order, so concurrent purchases can't deadlock.
   - It debits the student, credits the instructor with the price minus `PLATFORM_FEE_RATE` (default 10%), records the `Payment` and the coupon redemption, and creates the enrollment.
3. There is no "pay for a course by card" route.

## Models
- **`Payment`** (`purpose` = course purchase or wallet top-up). Statuses: `pending`, `processing`, `completed`, `partially_refunded`, `failed`, `refunded`.
- **`Refund`**: requested → approved/rejected. Approving moves money wallet-to-wallet:
  - The student is refunded.
  - The instructor's share is debited (`instructor_debit`).
  - Whatever the instructor can no longer cover is absorbed by the platform (`platform_absorbed`).
  - Refunds can never exceed what's refundable on the payment.
- **`Payout`**: requested by the instructor from the wallet balance.
  - The amount is **reserved** (debited) when the payout is requested.
  - It is released back to the wallet if the payout is rejected, failed or cancelled.
- **`Coupon`** and **`CouponRedemption`**: only coupons with `is_public=True` are listed to users. Usage is checked and counted inside the purchase transaction.
- **`PaymentWebhookLog`** and **`PaymentDispute`**.

## Operations
- `python manage.py reconcile_payout_ledger` checks that payouts and wallet debits agree.
- Errors raised by the services are subclasses of `PaymentsError` (`PurchaseError`, `RefundError`, `PayoutError`). Views turn them into `4xx` responses.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apipayments). That file is generated from the URLconf, so it is always current.
