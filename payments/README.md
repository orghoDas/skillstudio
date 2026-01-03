# Payments App - Complete Documentation

## Overview
Complete payment processing system for the Skillstudio learning platform with support for multiple payment gateways, coupons, refunds, and instructor payouts.

## Features

### Payment Processing
- **Multiple Payment Methods**: Stripe, PayPal, Bank Transfer, Wallet
- **Course & Event Purchases**: Unified payment system
- **Coupon System**: Percentage and fixed amount discounts
- **Fee Calculation**: Automatic 20% platform fee calculation
- **Status Tracking**: Comprehensive payment lifecycle management

### Refund Management
- **Full & Partial Refunds**: Flexible refund options
- **Approval Workflow**: Admin review and approval process
- **Automatic Processing**: Integration with payment gateways
- **Reason Tracking**: Document refund requests and rejections

### Instructor Payouts
- **Balance Tracking**: Real-time earnings calculation
- **Multiple Payout Methods**: Stripe Connect, PayPal, Bank Transfer
- **Minimum Threshold**: $10 minimum payout
- **Approval Process**: Admin review before processing

### Coupon System
- **Discount Types**: Percentage or fixed amount
- **Usage Limits**: Total and per-user restrictions
- **Expiration Dates**: Time-based validity
- **Targeting**: Course-specific, event-specific, or platform-wide
- **Minimum Order**: Optional minimum purchase amount

## Models

### Payment
Primary payment transaction model with:
- User and instructor references
- Course or event reference
- Amount and discount tracking
- Payment method and provider details
- Fee distribution (platform_fee, instructor_earnings)
- Status workflow (8 states)
- Billing information
- IP tracking

### Payout
Instructor payout requests:
- Instructor reference
- Amount and currency
- Related payments (M2M)
- Payout method
- Transaction tracking
- Admin notes

### Refund
Payment refund requests:
- Payment reference
- Requested by user
- Processed by admin
- Refund type (full/partial)
- Approval workflow
- Provider refund ID

### Coupon
Discount coupons:
- Code (unique)
- Discount type and value
- Applies to (all/courses/events/specific)
- Usage limits
- Validity period
- Max discount cap

### CouponRedemption
Track coupon usage:
- Coupon and user reference
- Payment reference
- Discount amount
- Timestamp

### PaymentGatewayConfig
Gateway configuration:
- Gateway name (Stripe/PayPal)
- Test/Live mode
- API credentials
- Webhook secrets

### PaymentWebhookLog
Webhook event logging:
- Gateway and event type
- Event ID (unique)
- Payload
- Processing status

### PaymentDispute
Chargeback tracking:
- Payment reference
- Dispute ID
- Amount and reason
- Evidence storage
- Resolution workflow

## API Endpoints

### Payment Endpoints
```
GET    /api/payments/                    - List user payments
POST   /api/payments/create/             - Create payment
GET    /api/payments/{id}/               - Payment details
POST   /api/payments/{id}/cancel/        - Cancel pending payment
```

### Refund Endpoints
```
GET    /api/payments/refunds/            - List refunds
POST   /api/payments/refunds/request/    - Request refund
POST   /api/payments/refunds/{id}/approve/ - Approve (admin)
POST   /api/payments/refunds/{id}/reject/  - Reject (admin)
```

### Payout Endpoints
```
GET    /api/payments/payouts/            - List payouts
POST   /api/payments/payouts/request/    - Request payout
GET    /api/payments/payouts/balance/    - Get balance
POST   /api/payments/payouts/{id}/approve/ - Approve (admin)
```

### Coupon Endpoints
```
GET    /api/payments/coupons/            - List coupons
POST   /api/payments/coupons/create/     - Create coupon (admin)
POST   /api/payments/coupons/validate/   - Validate coupon
DELETE /api/payments/coupons/{id}/deactivate/ - Deactivate
```

### Analytics Endpoints
```
GET    /api/payments/stats/              - Platform stats (admin)
GET    /api/payments/instructor/earnings/ - Instructor earnings
```

### Webhook Endpoints
```
POST   /api/payments/webhooks/stripe/    - Stripe webhook
POST   /api/payments/webhooks/paypal/    - PayPal webhook
```

## Usage Examples

### Creating a Payment
```python
from payments import services

payment = services.create_payment(
    user=request.user,
    amount=Decimal('99.99'),
    course=course,
    payment_method='stripe',
    coupon_code='SAVE20',
    billing_email='user@example.com',
    ip_address=request.META.get('REMOTE_ADDR')
)
```

### Processing Payment Success
```python
payment = services.process_payment_success(
    payment=payment,
    provider_id='pi_stripe_id_123',
    metadata={'receipt_url': 'https://...'}
)
# Automatically calculates:
# - Platform fee (20%)
# - Instructor earnings (80%)
# - Records coupon redemption
```

### Validating Coupon
```python
coupon = services.validate_and_apply_coupon(
    coupon_code='SAVE20',
    user=user,
    amount=Decimal('100.00'),
    course=course
)

discount = services.calculate_coupon_discount(coupon, amount)
final_amount = amount - discount
```

### Requesting Refund
```python
refund = services.request_refund(
    payment=payment,
    amount=payment.amount,
    reason='Customer request',
    user=request.user,
    refund_type='full'
)
```

### Calculating Instructor Balance
```python
balance = services.calculate_instructor_balance(instructor)
# Returns:
# {
#     'total_earnings': Decimal('1000.00'),
#     'paid_out': Decimal('500.00'),
#     'pending': Decimal('200.00'),
#     'available': Decimal('300.00')
# }
```

### Creating Payout
```python
payout = services.create_payout(
    instructor=instructor,
    amount=Decimal('300.00'),
    payout_method='stripe_connect',
    account_details={'account_id': 'acct_...'}
)
```

## Business Logic

### Payment Flow
1. User initiates purchase (course/event)
2. Apply coupon if provided (validate and calculate discount)
3. Create pending payment
4. Process with payment gateway
5. On success:
   - Mark payment as completed
   - Calculate fees (20% platform, 80% instructor)
   - Record coupon redemption
   - Trigger enrollment/registration
   - Send confirmation email

### Refund Flow
1. User/admin requests refund
2. Create refund record (status: requested)
3. Admin reviews:
   - Approve → Process with gateway → Update payment status
   - Reject → Record reason
4. Send refund notification

### Payout Flow
1. Instructor requests payout (minimum $10)
2. Calculate available balance
3. Create payout request (status: pending)
4. Admin approves (status: processing)
5. Process with payment gateway
6. Mark as paid (status: paid)
7. Send confirmation

### Coupon Validation
1. Check code exists and is active
2. Verify not expired
3. Check usage limits (total and per-user)
4. Validate minimum order amount
5. Check applicability (course/event restrictions)
6. Calculate discount amount
7. Apply max discount cap if percentage

## Configuration

### Platform Settings
```python
# services.py
PLATFORM_FEE_RATE = Decimal("0.20")  # 20%
MIN_PAYOUT_AMOUNT = Decimal("10.00")  # $10
```

### Payment Methods
- stripe (default)
- paypal
- bank_transfer
- wallet
- manual

### Payment Statuses
- pending
- processing
- completed
- failed
- refunded
- partially_refunded
- disputed
- cancelled

### Refund Statuses
- requested
- approved
- rejected
- processing
- processed
- failed

### Payout Statuses
- pending
- processing
- paid
- failed
- cancelled

## Database Indexes

Optimized for performance:
- Payment: status, instructor, user, payment_method, created_at, provider_id
- Payout: instructor+created_at, status
- Refund: status, payment
- Coupon: code, is_active+expires_at
- WebhookLog: gateway+created_at, event_id, processed
- CouponRedemption: coupon+user, user+redeemed_at

## Security Features

- **IP Tracking**: Record IP for fraud prevention
- **Webhook Verification**: Signature validation (to be implemented)
- **Transaction Atomicity**: All money operations are atomic
- **Decimal Precision**: Accurate money calculations
- **Provider ID Tracking**: Prevent duplicate payments
- **Event Deduplication**: Webhook event ID uniqueness

## Testing

Run payment tests:
```bash
python manage.py test payments --verbosity=2
```

Test coverage:
- ✅ Model creation and validation
- ✅ Service functions
- ✅ API endpoints
- ✅ Coupon validation
- ✅ Balance calculations
- ✅ Refund workflows
- ✅ Permission checks

## Admin Interface

Django admin configured for all models:
- List views with filters
- Search functionality
- Color-coded status displays
- Readonly fields for sensitive data
- Date hierarchy navigation

Access at: `/admin/payments/`

## Webhook Integration

### Stripe Webhook Setup
1. Configure webhook endpoint: `/api/payments/webhooks/stripe/`
2. Events to listen:
   - payment_intent.succeeded
   - payment_intent.payment_failed
   - charge.refunded
   - charge.dispute.created

### PayPal Webhook Setup
1. Configure webhook endpoint: `/api/payments/webhooks/paypal/`
2. Events to listen:
   - PAYMENT.CAPTURE.COMPLETED
   - PAYMENT.CAPTURE.DENIED
   - PAYMENT.CAPTURE.REFUNDED

## Migration

Create migrations:
```bash
python manage.py makemigrations payments
python manage.py migrate payments
```

## Dependencies

- Django 6.0+
- Django REST Framework 3.16.1+
- PostgreSQL (recommended)
- Python 3.12+

## Future Enhancements

- [ ] Recurring payments/subscriptions
- [ ] Multi-currency support
- [ ] Split payments
- [ ] Payment plans/installments
- [ ] Gift cards
- [ ] Wallet system
- [ ] Cryptocurrency support
- [ ] Advanced fraud detection
- [ ] Revenue sharing rules
- [ ] Tax calculation integration

## Support

For issues or questions:
- Check test cases for usage examples
- Review service function docstrings
- Examine model properties and methods
- Test in admin interface first
