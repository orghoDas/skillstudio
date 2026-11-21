# students

The student's own space, and the **wallet ledger** that every money movement uses.

## Models
- **`StudentProfile`**, **`StudentNote`** and **`StudentBookmark`**: learning preferences and goals, plus per-lesson notes and bookmarks.
- **`LearningActivity`** stores one row per student and local calendar day, including the watch seconds credited that day.
- **`Wallet`** (one per user) and **`WalletTransaction`** (an append-only ledger).
  - Every balance change goes through `Wallet._apply_delta`: it locks the wallet row, refuses to go negative and writes a transaction row with `balance_after`.
  - `add_money` and `deduct_money` are thin wrappers around it.
  - Course purchases, refunds and payouts all use this path (see `payments`).
  - Don't change `balance` any other way.

## Rules
- There is **no endpoint that adds funds**: `POST /api/students/wallet/` returns `405` (SEC-01). Funds will arrive through a Stripe test-mode top-up (Decision D-01), which isn't built yet.
- Dashboard progress uses required lessons. Completion comes from enrollment records and certificates come from certificate records. Profile totals are calculated from the current records.
- The dashboard and lesson watch-time and completion endpoints accept an optional `timezone` query parameter with an IANA name such as `Asia/Dhaka`. The browser supplies it automatically. Missing or invalid values use the project timezone, UTC.
- A streak stays current when the last activity was yesterday. Migration `students/0003` recovers the UTC dates still visible in old progress timestamps. Daily watch totals start with newly recorded activity because old progress rows contain only cumulative watch time.
- Taking notes requires an `active` or `completed` enrollment in the lesson's course.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apistudents). That file is generated from the URLconf, so it is always current.
