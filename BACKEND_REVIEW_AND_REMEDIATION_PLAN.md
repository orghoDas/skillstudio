# SkillStudio Backend Active Review and Remediation Plan

**Original review date:** 2026-07-21

**Last active-list update:** 2026-07-24

**Scope:** Django project configuration and backend applications: `accounts`, `courses`, `enrollments`, `assessments`, `exams`, `certificates`, `students`, `instructors`, `payments`, and `core`.

This document tracks only backend work that still needs attention so it can be used as a practical next-fix queue.

## Current Release Position

The backend is still **not production-ready**, mainly because the money path is runtime-broken/insecure, account lifecycle policy is incomplete, and repository/deployment hygiene is not clean.

### Current Verification Snapshot

```bash
DATABASE_URL=sqlite:////private/tmp/skillstudio-p115-focused.sqlite3 .venv/bin/python manage.py test accounts courses enrollments assessments exams certificates instructors
```

```text
Found 181 test(s).
Ran 181 tests in 59.664s

OK
```

Additional current checks:

- `manage.py check`: clean.
- `makemigrations --check --dry-run`: clean.
- `git diff --check`: clean.
- `manage.py check --deploy`: still reports production security warnings for HSTS, HTTPS redirect, insecure fallback secret, and secure session/CSRF cookies.

The last full-suite baseline remains red because `payments.tests` still imports the removed `events` app. Treat this as an active test-baseline issue until the full suite collects and passes.

## Priority Queue

1. **P0 payment and entitlement containment**
   Fix payment model drift, server-side pricing, signed webhooks, idempotent fulfillment, and financial state reconciliation.

2. **P0 repository/deployment gate**
   Remove tracked secrets/generated artifacts, fix dependency encoding, add CI, and satisfy deploy security checks.

3. **P1 account lifecycle and identity policy**
   Implement verification/reset delivery and token lifecycle.

4. **P1 enrollment/progress trust**
   Fix wallet/enrollment transaction flow and reactivation semantics.

5. **P2 platform reliability**
   Add background jobs/outbox, OpenAPI/client contract checks, observability, throttling, health checks, query budgets, and runbooks.

---

## P0 Open Issues

### P0-01 Payment Model Drift

**Problem:** Payment code still references the removed event domain.

**Evidence needing attention:**

- `payments/services.py` passes `event=...` into `Payment.objects.create()`.
- Payment serializers/views still reference event-specific coupon relationships.
- `payments/tests.py` imports `events.models.Event`, so the payment test module does not collect.

**Required fix:**

- Remove the event concept from payment services, serializers, views, tests, and docs.
- Decide how existing event-scoped coupon rows should migrate.
- Add serializer import smoke tests and route-level payment creation tests.

**Acceptance criteria:**

- `rg "specific_events|events\\.models|event=event|payment\\.event" payments` returns only intentional migration/history notes, if any.
- Payment serializer modules import cleanly.
- The full test suite collects.

### P0-02 Client-Controlled Payment Amount

**Problem:** Payment creation accepts client-supplied `amount` and uses it as the purchase price.

**Required fix:**

- Remove public `amount` from purchase requests.
- Lock and load the course server-side.
- Snapshot course price, discount, tax, platform fee, instructor earnings, currency, and final amount.
- Use `Decimal` with one documented rounding policy.

**Acceptance criteria:**

- Altering a browser/API request cannot change the payable amount.
- Tests cover normal, free, discounted, expired-coupon, and minimum-order cases.

### P0-03 Unsigned Payment Webhooks

**Problem:** Stripe and PayPal webhook views parse raw JSON without cryptographic signature verification.

**Required fix:**

- Verify provider signatures using the raw request body before any database write.
- Store provider event IDs with a uniqueness guarantee.
- Make duplicate verified events idempotent.
- Log only safe metadata, not full provider payloads.

**Acceptance criteria:**

- Forged or replayed webhooks cannot change payment, entitlement, wallet, or payout state.
- Signed-provider contract tests cover success, failure, replay, and malformed payloads.

### P0-04 Disconnected Payment Fulfillment

**Problem:** Marking payment completed does not atomically and idempotently create/reactivate enrollment and ledger effects.

**Required fix:**

- Add one fulfillment service that locks the payment and target course/enrollment.
- Enforce allowed payment state transitions.
- Create or reactivate the entitlement exactly once.
- Write ledger/payment allocation records in the same transaction.

**Acceptance criteria:**

- One captured payment produces exactly one entitlement and one auditable ledger result.
- Concurrent fulfillment calls are idempotent.

### P0-05 Duplicate Wallets, Payouts, and Fee Policies

**Problem:** Money state has multiple sources of truth.

**Evidence needing attention:**

- `accounts.Profile.wallet` and `students.Wallet` both represent balances.
- `payments.Payout` and `instructors.InstructorPayout` both represent payouts.
- Enrollment wallet flow and payment service use different platform fee rates.
- Students can credit their own wallet.

**Required fix:**

- Define one ledger-backed wallet/balance model.
- Define one payout allocation model.
- Remove or quarantine student self-credit until backed by real payment capture.
- Backfill and reconcile existing balances before switching reads/writes.

**Acceptance criteria:**

- Reconciliation has zero unexplained differences.
- Balance/payout reads derive from canonical ledger state.

---

## P1 Open Issues

### P1-01 Account Verification and Password Reset Lifecycle

**Problem:** Accounts are active before verification, email delivery is not wired, reset/verification tokens are not hashed/consumed robustly, and refresh tokens are not revoked after sensitive lifecycle events.

**Required fix:**

- Decide whether new accounts start inactive until verification.
- Implement delivery, throttling, hashed one-time tokens, expiry, consumption, and audit metadata.
- Revoke refresh/session tokens after password reset and high-risk account changes.
- Prevent self-registration from immediately granting privileged instructor capability unless that is explicitly the product policy.

### P1-06 Enrollment Purchase and Reactivation Flow

**Problem:** Enrollment serializer owns debit/payment/enrollment workflow, includes fail-open/best-effort branches, lacks idempotency/locking, and reports reactivation incorrectly.

**Required fix:**

- Move enrollment purchase/reactivation into a domain service.
- Lock user/course/enrollment/payment state.
- Remove best-effort financial side effects.
- Make reactivation response semantics explicit.

### P1-12 Refund and Payout Invariants

**Problem:** Refund and payout state is not safely enforceable.

**Required fix:**

- Track refundable/refunded amounts from immutable payment ledger allocations.
- Lock payment rows while accepting refunds and enforce cumulative total `<= captured amount`.
- Define entitlement reversal for full/partial refunds.
- Model payout allocations explicitly rather than attaching arbitrary whole payments.
- Reserve earnings transactionally before provider payout.

## P2 Open Issues

### P2-01 Course and Assessment Versioning Is Not Integrated

`CourseVersion` exists but is not consistently tied to publication, moderation, enrollment evidence, certificate evidence, assessment definition history, or rollback. Quiz attempts now carry evidence snapshots, but future authoring policy still needs an explicit versioning model if product requirements allow published assessment edits.

### P2-02 Query and Aggregate Performance

Several serializers/views still risk N+1 queries and expensive per-row aggregate work at scale. Add query-budget tests for dashboard, course-list, enrollment, and analytics views.

### P2-03 Denormalized Stats Drift

Course/student/instructor counters can become stale. Define derived-vs-cached fields, atomic update paths, and reconciliation jobs.

### P2-04 Analytics Contract Coverage

Some analytics endpoints now have targeted route tests, but analytics as a domain still needs schema/contract tests, authorization matrices, and query-budget tests.

### P2-05 Background Tasks and Outbox

Celery is configured, but production-grade task usage is incomplete. Email, certificate rendering, payment fulfillment, reconciliation, and notification fanout should use idempotent task/outbox patterns.

### P2-06 API and Frontend Contract Drift

There is no OpenAPI-backed contract gate. Templates and first-party clients still rely on ad hoc route strings and response assumptions.

### P2-07 Database Constraints for Remaining Domains

Recent assessment attempt constraints improved the assessment domain, but payments, wallets, payouts, refunds, and lifecycle states still need database-enforced invariants after data cleanup.

### P2-08 Error Contracts, Throttling, Health Checks, and Observability

Define stable error codes, add throttles for auth/payment mutation routes, add health/readiness checks, and introduce structured logs/metrics/tracing without secrets or full payloads.

---

## Test Baseline Work Still Needed

### Full Suite Collection

The full suite must collect and pass before release work can be trusted.

Known active blockers:

- Stale account tests still request an extra `/api/` path segment.
- `payments.tests` imports the removed `events` app.
- Payment tests cannot meaningfully pass until P0-01 through P0-04 are fixed.

### Migration Caution

The new quiz no-retake constraint assumes existing deployed databases have at most one `QuizAttempt` per `(quiz, user)`. Before applying that migration outside local test databases, run a duplicate-audit query and decide whether to preserve, merge, or archive historical duplicate attempts.

---

## Security and Repository Hygiene

These are still active release blockers:

- `.env` remains tracked and any real secrets must be rotated.
- A Windows `venv` and bytecode/cache files remain tracked.
- `requirements.txt` is UTF-16 and should be converted to UTF-8 with reproducible dependency locking.
- Static/generated artifacts should stay ignored.
- CI should run checks, migrations, full tests, deploy checks, dependency audit, and secret scanning.
- Production settings must enable HTTPS redirect/proxy headers, secure cookies, HSTS, content-type nosniff, trusted CSRF origins, production logging, and safe secret loading.

---

## Recommended Implementation Sequence

### Phase 0: Trustworthy Baseline

1. Remove tracked secrets/generated artifacts and rotate exposed secrets.
2. Fix dependency encoding/locking.
3. Fix account test URLs and payment test imports so the full suite collects.
4. Add CI for checks, migrations, focused tests, full tests, deploy checks, dependency audit, and secret scanning.

### Phase 1: Payment and Entitlement Containment

1. Remove event drift from payments.
2. Move pricing to server-derived course snapshots.
3. Verify provider webhook signatures and provider event idempotency.
4. Fulfill entitlements and ledger effects atomically.
5. Consolidate wallet/payout sources of truth.

### Phase 2: Account and Enrollment Lifecycle

1. Implement account verification/reset/token lifecycle.
2. Resolve role/superuser/staff invariants.
3. Move enrollment purchase/reactivation into a locked domain service.

### Phase 3: Platform Reliability

1. Add background jobs/outbox for email, certificates, payments, reconciliation, and notifications.
2. Publish OpenAPI v1 and align templates/clients.
3. Add observability, throttling, health/readiness checks, query budgets, backup/restore, replay/reconciliation, and rollback runbooks.

---

## Definition of Done for Release

- Full test suite collects and passes.
- Payment creation, pricing, webhook verification, fulfillment, refund, payout, and ledger flows are transactionally tested.
- No tracked secrets, virtual environments, bytecode, or generated local artifacts remain.
- Deployment checks pass or each remaining warning has a documented production-specific control.
- Account lifecycle, role policy, enrollment purchase/reactivation, and progress trust have one documented policy and one transactional implementation path.
- Assessment evidence has reproducible, auditable behavior.
- OpenAPI and first-party clients agree on paths and response shapes.
- CI blocks migration drift, missing tests, deploy warnings, dependency risk, and secret leakage.
