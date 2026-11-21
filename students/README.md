# students

The student's own space, and the **wallet ledger** that every money movement uses.

## Models
- **`StudentProfile`**, **`StudentNote`** and **`StudentBookmark`**: learning preferences and goals, plus per-lesson notes and bookmarks.
- **`Wallet`** (one per user) and **`WalletTransaction`** (an append-only ledger).
  - Every balance change goes through `Wallet._apply_delta`: it locks the wallet row, refuses to go negative and writes a transaction row with `balance_after`.
  - `add_money` and `deduct_money` are thin wrappers around it.
  - Course purchases, refunds and payouts all use this path (see `payments`).
  - Don't change `balance` any other way.

## Rules
- There is **no endpoint that adds funds**: `POST /api/students/wallet/` returns `405` (SEC-01). Funds will arrive through a Stripe test-mode top-up (Decision D-01), which isn't built yet.
- The dashboard, streak, achievements and weekly-progress data come from `services.py` and are computed from enrollments and lesson progress.
- Taking notes requires an `active` or `completed` enrollment in the lesson's course.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apistudents). That file is generated from the URLconf, so it is always current.
