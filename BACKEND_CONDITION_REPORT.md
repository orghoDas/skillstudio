# Backend Condition Report — SkillStudio

**Reviewer:** Independent code review
**Date:** 2026-07-24
**Scope:** Django project config + 9 domain apps (`accounts`, `courses`, `enrollments`, `assessments`, `exams`, `payments`, `certificates`, `students`, `instructors`) and `core` (page shells).

**Stack:** Django 6.0 + DRF + SimpleJWT · Postgres (Neon) · Celery/Redis configured · WhiteNoise.

---

## Verdict

Well-structured but **not production-ready.** The domain layering is above average for a project this size — but the payments path is runtime-broken, secrets are committed to git, and the full test suite will not even collect.

| Area | State |
|---|---|
| Architecture / app separation | 🟢 Strong (service/policy/serializer layering, custom user, DB constraints) |
| Money path (payments) | 🔴 Broken & insecure |
| Repo & secret hygiene | 🔴 Live DB credentials + insecure signing key committed to git (rotation pending) |
| Auth / account lifecycle | 🟢 Solid primitives; refresh-token revocation added |
| Test baseline | 🔴 Full suite does not collect (payments import error) |

---

## 🔴 Critical

### 1. Live database credentials committed to git
`.env` is tracked (`git ls-files .env` confirms) despite appearing in `.gitignore` — it was committed **before** being ignored, so it remains in history from the initial commit. It contains a **live Neon Postgres URL with a real password** (`npg_5SNBIWLFhe7q...`).

- **Fix:** Rotate the credential now, then `git rm --cached .env`. A `.gitignore` entry does nothing once a file is already tracked. Consider history scrubbing (BFG/`git filter-repo`) since the secret is in past commits.
- **Also rotate the Django `SECRET_KEY`.** The committed `django-insecure-…` fallback was the live signing key (it signs JWTs, so it enabled token forgery for any user) — treat it as compromised and generate a fresh one. *(Settings now require `DJANGO_SECRET_KEY` in production and fail loudly without it, and production TLS hardening + env-driven `CSRF_TRUSTED_ORIGINS` are in place — fixed 2026-07-24. Rotation of the actual key value is still pending.)*

### 2. Payments test module can't import → full suite is red
`payments/tests.py:15` does `from events.models import Event`, but the `events` app was deleted.

```
ModuleNotFoundError: No module named 'events'
```

The "181 tests pass" baseline **excludes payments entirely** — the money code is effectively untested.

### 3. Client-controlled payment amounts
`payments/views.py:80`, `:182`, `:437` take `amount=data['amount']` from the request body and use it as the price. A user can pay `$0.01` for a `$200` course by editing the request.

- **Fix:** Derive price server-side from the course record; never accept a client-supplied payable amount.

### 4. Unsigned payment webhooks
`payments/webhooks.py:30` reads `HTTP_STRIPE_SIGNATURE` but **never verifies it** — it just `json.loads(payload)` and processes the event. Anyone who knows the URL can forge a "payment succeeded" event and unlock content or trigger payouts.

- **Fix:** Verify the provider signature against the raw body before any DB write; store provider event IDs uniquely for idempotency.

### 5. Event-domain drift throughout payments
The removed `events` domain is still referenced and will raise at runtime:

- `payments/services.py:36,59` — passes `event=` into `Payment.objects.create()`
- `payments/services.py:149` — `payment.event.instructor`
- `payments/serializers.py:166` — `specific_events`
- `payments/views.py:82,392,437` — `event=`, `coupon.specific_events`

---

## 🟠 High

- **Duplicate payout models + no single cross-domain ledger (deferred to payments).** `payments.Payout` *and* `instructors.InstructorPayout` both model payouts, and a true single ledger (purchases, wallet moves, payouts, refunds, reconciliation) spans the payments domain. Deferred to the payments phase per sequencing.

> **Resolved 2026-07-24 — duplicate wallet/balance sources.** `students.Wallet` + `WalletTransaction` is now the single balance store: credit/debit are atomic (row-locked) and always write a ledger row; the enrollment purchase flow's best-effort dual-write to `Profile.wallet` is gone; account serializers derive `wallet` from the canonical ledger; and `Profile.wallet` was backfilled into `students.Wallet` and dropped (migration `accounts/0009`). Covered by new tests in `students`, `enrollments`, and `accounts`.

---

## 🟢 What's genuinely good

- **Clean domain layering** — `services.py`, `policies.py`, `serializers.py`, `permissions.py` are properly separated per app. Strongest part of the codebase.
- **Custom `User` model is well done** (`accounts/models.py:38-99`) — DB `CheckConstraint`s enforcing role/staff/superuser invariants, clean role normalization on save.
- **APIKey auth is correct** (`accounts/authentication.py`) — SHA-256 hashed secrets, `hmac.compare_digest`, indexed prefix lookup.
- **Thoughtful per-view permissions** — public catalog endpoints correctly `AllowAny` while gating curriculum via `can_view_course_catalog` and summary serializers (`courses/views.py:365-383`). Not a naive entitlement leak.
- `manage.py check` is clean; models even carry documented raw-SQL schemas.

---

## Recommended fix order

1. Rotate + untrack the DB credentials **and the `SECRET_KEY`** (Critical #1).
2. Fix the payments `events` import so the suite collects (Critical #2 / #5).
3. Verify webhook signatures + move pricing server-side (Critical #3 / #4).
4. Consolidate wallet/payout onto a single ledger (High).
5. Add reproducible dependency locking (hashes) and CI running `check --deploy` + tests + secret scan.

> A prior `BACKEND_REVIEW_AND_REMEDIATION_PLAN.md` exists in the repo; its P0 claims were independently verified here and remain accurate and current.
