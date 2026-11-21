# SkillStudio — Full Repository Audit

**Date:** 2026-11-21
**Scope:** Whole repository:
- Django config and all 10 apps (`accounts`, `courses`, `enrollments`, `assessments`, `exams`, `certificates`, `students`, `instructors`, `payments`, `core`).
- For every app: models, views, serializers, services, policies/permissions, URLs, admin, migrations, management commands, template tags, PDF generation and tests.
- The 42 templates and their inline JS, and the backend↔frontend contract.
- `scripts/`, dependencies, repo hygiene, and docs.
**Supersedes:** `BACKEND_CONDITION_REPORT.md`, `BACKEND_REVIEW_AND_REMEDIATION_PLAN.md`, `FRONTEND_AND_INTEGRATION_REPORT.md`. Their still-open items are carried over here and marked *(carried over)*.

---

## 1. How this audit was done

Every finding below was read in source, and the ones marked **✔ verified** were also reproduced by running code. The checks used:

| Check | Command / method | Result |
|---|---|---|
| System check | `manage.py check` | ✅ clean |
| Migration drift | `manage.py makemigrations --check --dry-run` | ✅ no changes |
| Deploy check | `DEBUG=False DJANGO_SECRET_KEY=… manage.py check --deploy` | ✅ clean *(but see OPS-01: the check cannot see the ignored storage setting)* |
| Full test suite | `DATABASE_URL=sqlite:///… manage.py test` | ❌ **226 tests, 1 error**: `payments.tests` cannot import (`No module named 'events'`), so payments has **zero** running tests |
| Route resolution | `django.urls.resolve()` on every API URL the templates call | ❌ **24 calls hit no route**, 3 resolve to the wrong view, 2 use a method the view does not support |
| Runtime probes | Instantiating the suspect serializers, models and querysets | ❌ 5 confirmed crashes or silently dropped fields (see the ✔ marks) |
| JS parse probe | Node `vm`: two classic scripts declaring the same top-level `const` | ❌ `SyntaxError: Identifier 'API_BASE' has already been declared` |

### Severity scale

- **P0, critical:** an exploitable security or money hole, or a core user journey that does not work at all. Fix before anything else.
- **P1, high:** a serious bug, data-integrity risk, or security weakness, or a major feature that is dead.
- **P2, medium:** inconsistency, a correctness edge case, performance at scale, or hardening.
- **P3, low:** hygiene, dead code, docs.

---

## 2. Executive summary

The domain layering (services, policies, serializers per app) is good, and the auth primitives are solid. However, **the platform is not usable end to end and is not safe to take money**:

1. **Money can be created from nothing.** Any student can top up their own wallet for free (`POST /api/students/wallet/`), buy any course with it, and the instructor gets credited "earnings" that can then be paid out twice.
2. **The core learning journey is broken.**
   - The learn page never receives lesson content: the only content endpoint is shadowed by another route.
   - Video lessons can never be marked complete, because the page never reports watch time.
   - A student who *does* complete a course loses access to it.
3. **About a quarter of the frontend talks to endpoints that don't exist.** Assessments, checkout, payment history, resources, and featured instructors are all dead. The four exam pages also crash on load because of a duplicate JS `const`.
4. **The payments app is still runtime-broken and insecure** *(carried over)*: event-domain drift, client-supplied amounts, unsigned webhooks, and no fulfilment.

| Severity | Count |
|---|---|
| P0 | 12 |
| P1 | 23 |
| P2 | 25 |
| P3 | 7 |
| **Total** | **67** |
| *Resolved so far* | *31 (SEC-02, SEC-04, SEC-05, SEC-06, SEC-07, ASM-01, ASM-02, API-01, API-02, API-03, PAY-01, PAY-02, PAY-03, PAY-06, PAY-07, PAY-08, PAY-09, ENR-01, LRN-01, LRN-02, LRN-03, FE-01, BUG-01, BUG-02, OPS-01, OPS-02, OPS-03, CRS-01, TEST-01, OPS-05, TEST-02; all 2026-11-21); 36 open, of which SEC-01, SEC-03, PAY-04, PAY-05, API-04, ENR-03, DEP-01 are partially done* |

### Fix these first (in order)

1. [SEC-01](#sec-01) Remove free wallet top-up (to be replaced by Stripe test-mode top-ups for the demo). 🟡 Free top-up removed 2026-11-21; Stripe top-up pending.
2. ~~[PAY-01](#pay-01) Stop double-charging on enroll.~~ ✅ Done 2026-11-21.
3. ~~[SEC-02](#sec-02) Fix the login `next` open redirect / `javascript:` XSS.~~ ✅ Done 2026-11-21.
4. [SEC-03](#sec-03) Rotate and untrack the committed secrets. 🟡 Untracking, `.env.example`, key guard, secret scanning and the git-history scrub are done (2026-11-21); **DB password + production key rotation are still owner actions.**
5. [PAY-02](#pay-02)–[PAY-05](#pay-05) Put the payments API behind a kill switch until it is rebuilt. 🟡 Superseded by [D-01](#d-01): card route deleted, PAY-02/03 done, webhook rejects all, course fulfilment done (2026-11-21); the Stripe top-up remains.
6. ~~[LRN-01](#lrn-01)–[LRN-03](#lrn-03) Make the learn → complete → certificate journey work.~~ ✅ Done 2026-11-21.
7. ~~[FE-01](#fe-01) Unbreak the exam pages (a one-line fix in each of 4 files).~~ ✅ Done 2026-11-21.
8. ~~[SEC-04](#sec-04), [SEC-05](#sec-05) Fix the ordering injection and the cross-course content injection.~~ ✅ Done 2026-11-21.

### Decisions

<a id="d-01"></a>
#### D-01 (2026-11-21): Payments architecture is "Stripe → wallet → course"

**Decision.** There is **one money path**:
- Money enters only through a **wallet top-up** paid with **Stripe in test mode** (demonstration only, see [SEC-01](#sec-01)).
- **Courses are bought only from the wallet** (`POST /api/enrollments/enroll/` → `payments.services.purchase_course`).
- There is **no "pay for a course by card" route.**

**Why:**
- The card route never worked: every call crashed on the removed `events` code, and its checkout page called a non-existent endpoint.
- Two purchase paths had already drifted apart (different fees, coupons, fulfilment, double-charge rules). Most PAY findings came from that drift.
- With one path, Stripe only ever handles "top-up paid → credit wallet". That's one verified webhook, which is easy to demo and reason about.

**What this means for the code:**
- `Payment` gets `purpose` ∈ {`course_purchase`, `wallet_topup`}.
- Revenue figures count course purchases only.
- One platform fee (`settings.PLATFORM_FEE_RATE`, default 10%).
- Coupons apply at wallet checkout. Refunds of course purchases go back to the wallet.
- A direct card-to-course route can be added later on top of the same fulfilment service if a real marketplace needs it.

**Effect on the findings:**

| Finding | Re-scoped to |
|---|---|
| [PAY-02](#pay-02) | Mostly **delete** the card route and event code, rather than repair it. |
| [PAY-03](#pay-03) | No client amount anywhere: course price is always server-side. A top-up amount is user-chosen by design and needs only min/max bounds (`WALLET_TOPUP_MIN/MAX`). |
| [PAY-05](#pay-05) | Course fulfilment = `purchase_course` (wallet). Top-up fulfilment = the verified Stripe webhook (with the Stripe work). |
| [PAY-04](#pay-04) | Stripe only; PayPal dropped. |
| [PAY-08](#pay-08) | Refunds of course purchases credit the wallet. Refunding a top-up itself to a card is out of scope for the demo. |
| [PAY-06](#pay-06) / [PAY-07](#pay-07) | Unchanged in substance (payouts are internal). PAY-07's "where do earnings live" becomes: **in the instructor wallet ledger**. |

<a id="d-02"></a>
#### D-02 (2026-11-21): Signup role comes from the email domain

**Decision (owner).** The client no longer picks a role at signup. It is derived from the email address, matching the domain exactly and case-insensitively:

| Email domain | Account created |
|---|---|
| `@instructor.com` | instructor |
| `@student.com` | student |
| any other domain (e.g. `@gmail.com`, `@evil.instructor.com`) | student |
| `@admin.com` | **refused** |

**Admins are never created by signing up.** Emails aren't verified, so anyone could type an `@admin.com` address. Admins come from `manage.py createsuperuser` or an existing admin's promotion.

**Where it lives:** `settings.SIGNUP_ROLE_BY_EMAIL_DOMAIN`, `SIGNUP_DEFAULT_ROLE` and `SIGNUP_FORBIDDEN_EMAIL_DOMAINS`, applied by `accounts.utils.signup_role_for_email`.

**Accepted trade-off:** because emails aren't verified, anyone who types an `@instructor.com` address becomes an instructor. That's mitigated by courses still needing admin review before they're published.


<a id="d-03"></a>
#### D-03 (2026-11-21): The project is not deployed

**Decision (owner).** There are no deployments any more; SkillStudio only runs locally.

**Repo-side changes:**
- `ALLOWED_HOSTS` is now `localhost`, `127.0.0.1` and `[::1]`; the Railway domains and `RAILWAY_PUBLIC_DOMAIN` were removed.
- The Railway notes were removed from `.env.example`.
- The production-only servers `gunicorn` and `daphne` were dropped from `requirements.txt`.
- The `if not DEBUG` security block stays: it's inert with `DEBUG=True` and only protects a non-debug run.

**Owner action:** delete the Railway project/service, and disconnect Railway's GitHub app from the repo, so pushes stop triggering deploys. The repo holds no Railway config file, so this can only be done on Railway's side.

**Effect on findings:**
- [OPS-01](#ops-01) and [OPS-02](#ops-02) were first marked not applicable, but were then fixed for local use on request (2026-11-21).
- [OPS-03](#ops-03) is resolved (`gunicorn` removed).
- [OPS-04](#ops-04) drops its deploy-only items (Procfile, health and readiness checks).
- [SEC-03](#sec-03)'s Railway secret-key step is no longer needed once the service is deleted. The Neon database password still has to be rotated.
---

## 3. Findings index

| ID | Sev | Title |
|---|---|---|
| [SEC-01](#sec-01) | P0 | Students can add unlimited funds to their own wallet — 🟡 hole closed 2026-11-21; Stripe test-mode top-up pending |
| [SEC-02](#sec-02) | P0 | ~~Login `?next=` is an open redirect and a DOM-XSS sink~~ ✅ resolved 2026-11-21 |
| [SEC-03](#sec-03) | P0 | Secrets committed to git; rotation still pending *(carried over)* — 🟡 repo side + history scrub done 2026-11-21; Neon password + production key rotation pending |
| [PAY-01](#pay-01) | P0 | ~~Enrolling charges again for courses already owned (and on double-click)~~ ✅ resolved 2026-11-21 |
| [PAY-02](#pay-02) | P0 | ~~Payments API crashes: removed `events` domain still referenced~~ ✅ resolved 2026-11-21 (card route deleted, D-01) |
| [PAY-03](#pay-03) | P0 | ~~Payment amount is client-controlled~~ ✅ resolved 2026-11-21 (server-side pricing, D-01) |
| [PAY-04](#pay-04) | P0 | Webhooks are unsigned and not idempotent — 🟡 contained 2026-11-21 (webhook rejects all); verified Stripe handler pending |
| [PAY-05](#pay-05) | P0 | A successful payment never grants an enrollment — 🟡 course side resolved 2026-11-21; top-up side pending (Stripe) |
| [LRN-01](#lrn-01) | P0 | ~~Learn page never receives lesson content~~ ✅ resolved 2026-11-21 |
| [LRN-02](#lrn-02) | P0 | ~~Video lessons can never be completed from the UI~~ ✅ resolved 2026-11-21 |
| [LRN-03](#lrn-03) | P0 | ~~Completing a course locks the student out of it~~ ✅ resolved 2026-11-21 |
| [FE-01](#fe-01) | P0 | ~~All 4 exam pages crash on load (duplicate `const API_BASE`)~~ ✅ resolved 2026-11-21 |
| [SEC-04](#sec-04) | P1 | ~~`?ordering=` is passed raw to `order_by()`~~ ✅ resolved 2026-11-21 |
| [SEC-05](#sec-05) | P1 | ~~Instructors can move modules/lessons into other instructors' courses~~ ✅ resolved 2026-11-21 |
| [SEC-06](#sec-06) | P1 | ~~Token endpoints return JWTs in the JSON body, undoing httpOnly cookies~~ ✅ resolved 2026-11-21 |
| [SEC-07](#sec-07) | P1 | ~~Anyone can self-register as an instructor~~ ✅ resolved 2026-11-21 (role from email domain, D-02) |
| [PAY-06](#pay-06) | P1 | ~~Instructor payout requests are not reserved or locked~~ ✅ resolved 2026-11-21 |
| [PAY-07](#pay-07) | P1 | ~~Two payout systems, two fee rates, and earnings counted twice~~ ✅ resolved 2026-11-21 (payouts on the wallet ledger) |
| [PAY-08](#pay-08) | P1 | ~~Refunds can exceed the payment and have no financial effect~~ ✅ resolved 2026-11-21 (refunds to wallet) |
| [PAY-09](#pay-09) | P1 | ~~Every active coupon code is listed to every logged-in user~~ ✅ resolved 2026-11-21 |
| [ASM-01](#asm-01) | P1 | ~~Unpublished or failed quizzes permanently block course completion~~ ✅ resolved 2026-11-21 |
| [ASM-02](#asm-02) | P1 | ~~Quiz time limit can be bypassed~~ ✅ resolved 2026-11-21 |
| [EXM-01](#exm-01) | P1 | Exam questions are visible before the exam window opens |
| [API-01](#api-01) | P1 | ~~24 frontend calls target endpoints that don't exist~~ ✅ resolved 2026-11-21 (contract test added) |
| [API-02](#api-02) | P1 | ~~Route shadowing: `tags/`, `search/`, lesson content, numeric slugs~~ ✅ resolved 2026-11-21 |
| [API-03](#api-03) | P1 | ~~Section and lesson delete buttons return 405~~ ✅ resolved 2026-11-21 |
| [BUG-01](#bug-01) | P1 | ~~Instructor lesson-analytics CSV export always 500s~~ ✅ resolved 2026-11-21 |
| [BUG-02](#bug-02) | P1 | ~~`InstructorCoursesView` error path raises `NameError`~~ ✅ resolved 2026-11-21 |
| [CRS-01](#crs-01) | P1 | ~~Access policy is fragmented and inconsistent~~ ✅ resolved 2026-11-21 |
| [OPS-01](#ops-01) | P1 | ~~WhiteNoise storage setting is silently ignored on Django 6~~ ✅ resolved 2026-11-21 |
| [OPS-02](#ops-02) | P1 | ~~Certificate PDFs live on local disk and aren't served in production~~ ✅ resolved 2026-11-21 (local scope) |
| [OPS-03](#ops-03) | P1 | ~~`gunicorn==21.2.0` has known request-smuggling CVEs~~ ✅ resolved 2026-11-21 (gunicorn removed) |
| [TEST-01](#test-01) | P1 | ~~Payments tests don't run, and tests write into the real `media/`~~ ✅ resolved 2026-11-21 |
| [TEST-02](#test-02) | P1 | ~~No tests cover the frontend↔API contract~~ ✅ resolved 2026-11-21 (contract + browser smoke tests) |
| [OPS-05](#ops-05) | P1 | ~~Tests and scratch scripts run against the hosted database by default~~ ✅ resolved 2026-11-21 |
| [ADM-01](#adm-01) | P2 | Django admin actions and fields bypass the domain logic |
| [SEC-09](#sec-09) | P2 | Gateway secrets and payout bank details stored in plaintext |
| [EXM-03](#exm-03) | P2 | Exam grading and marks integrity (no snapshot, unpassable exams) |
| [STU-02](#stu-02) | P2 | Dashboard numbers are wrong or never populated |
| [CRS-02](#crs-02) | P2 | Ownership failures return 400 instead of 403; admins can't moderate content |
| [CRS-03](#crs-03) | P2 | Course lifecycle and editability rules contradict each other |
| [CRS-04](#crs-04) | P2 | Category creation is broken (slug never generated) |
| [CRS-05](#crs-05) | P2 | Course price, free flag and tags aren't validated |
| [CRS-06](#crs-06) | P2 | Public course endpoints expose instructor emails |
| [CRS-07](#crs-07) | P2 | Fake or stub features in the course API |
| [ENR-01](#enr-01) | P2 | ~~`was_reactivated` is always `true`~~ ✅ resolved 2026-11-21 |
| [ENR-02](#enr-02) | P2 | Serializer fields silently dropped (`thumbnail_url`, `get_full_name`) |
| [ENR-03](#enr-03) | P2 | Three different lesson-unlock algorithms — 🟡 locking unified 2026-11-21 |
| [ERR-01](#err-01) | P2 | Broad `except Exception` leaks internals and hides bugs |
| [STU-01](#stu-01) | P2 | Bookmarks leak unpublished content; instructors can't see their wallet |
| [EXM-02](#exm-02) | P2 | Exam settings that do nothing; analytics disagree with grading |
| [CRT-01](#crt-01) | P2 | Certificate admin, verification and rendering issues |
| [ACC-01](#acc-01) | P2 | Account-management inconsistencies |
| [PERF-01](#perf-01) | P2 | N+1 queries and unpaginated list endpoints |
| [API-04](#api-04) | P2 | No API contract: inconsistent error and pagination shapes — 🟡 duplicate route names fixed |
| [OPS-04](#ops-04) | P2 | No throttling, logging, health check or real background jobs — re-scoped (deploy items dropped) |
| [SEC-08](#sec-08) | P2 | Frontend hardening: CSP, CDN Tailwind, inline handlers, cookie scope |
| [FE-02](#fe-02) | P2 | Role-based navbar never works; debug logs and stale routes |
| [ASM-03](#asm-03) | P2 | Quiz editing ignores course lock; error points to a non-existent feature |
| [INS-01](#ins-01) | P2 | Instructor dashboard swallows errors and returns fake zeros |
| [REPO-01](#repo-01) | P3 | 5,965 vendored `venv` files, `.pyc`, and scratch scripts tracked in git |
| [REPO-02](#repo-02) | P3 | Dead code and stale comments |
| [REPO-03](#repo-03) | P3 | Migration churn in `accounts` |
| [DOC-01](#doc-01) | P3 | README advertises features that don't exist and has no setup guide |
| [DOC-02](#doc-02) | P3 | App READMEs document a different API |
| [DEP-01](#dep-01) | P3 | Dependencies installed but unused; no lock file — 🟡 gunicorn/daphne removed |
| [ASM-04](#asm-04) | P3 | Assessment model and analytics gaps |

---

## 4. P0: Critical

<a id="sec-01"></a>
### SEC-01: Students can add unlimited funds to their own wallet — 🟡 HOLE CLOSED 2026-11-21, STRIPE TOP-UP PENDING

> **Progress 2026-11-21:** the free self-credit is gone.
> - `WalletView` no longer accepts `POST` (it returns 405, covered by a test), and `AddFundsSerializer` was deleted.
> - The **Add Funds** buttons and modals were removed from `student/wallet.html` and `dashboard/student.html`. The wallet page now shows a disabled "Top up — coming soon (Stripe test mode)" control.
> - The course page's "Insufficient balance" dialog now links to the real `/wallet/` page; it used to link to `/student/wallet/`, which doesn't exist.
> - **Still open:** the Stripe test-mode top-up (Decision [D-01](#d-01)) and the data audit of past `Funds added to wallet` credits (step 3 below).

*Original finding:*

**Evidence:**
- [students/views.py:199](students/views.py#L199): `WalletView.post` calls `wallet.add_money(amount)` for any `IsStudent` user with no payment behind it.
- [students/serializers.py:183](students/serializers.py#L183): `AddFundsSerializer` has `min_value=1` and no maximum.
- The UI exposes it in [templates/dashboard/student.html:267](templates/dashboard/student.html#L267) and [templates/student/wallet.html:196](templates/student/wallet.html#L196).

**Impact:** Free money. A student tops up, buys any paid course ([PAY-01](#pay-01) flow), and the instructor is credited 90% as "earnings". Those earnings are also payout-eligible ([PAY-07](#pay-07)). Amounts above the column's 10 digits overflow and 500 on Postgres.

**Fix approach:**
1. Remove `POST` from `WalletView` now, along with the two UI "Add funds" buttons.
2. If top-ups are a product requirement, re-introduce them only as: create a pending top-up `Payment` → provider checkout → **verified** webhook ([PAY-04](#pay-04)) → `wallet.add_money()` inside the fulfilment transaction.
3. Run a data audit: list `WalletTransaction` rows with `description='Funds added to wallet'`, reconcile them, and decide whether to reverse them.

**Done when:** no unauthenticated-by-provider code path can credit a wallet; a test asserts `POST /api/students/wallet/` returns 405.

> **Decision (2026-11-21): wallet top-ups will go through a Stripe gateway in dev/test mode, for demonstration only.** Status: **open, planned.** Intended shape:
> - **Keys:** Stripe **test** keys only (`sk_test_…` / `pk_test_…` / `whsec_…`), read from env vars (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`). Never stored in the DB (see [SEC-09](#sec-09)). Settings refuse to start if the secret key isn't an `sk_test_` key while the demo flag `STRIPE_TEST_MODE=True` is on.
> - **Flow:** `POST /api/students/wallet/top-up/ {amount}` → create a `pending` `Payment` (purpose = wallet top-up, server-validated amount within min/max) → create a Stripe Checkout Session (or PaymentIntent) carrying the payment id in `metadata` → redirect to Stripe's hosted page. Pay with Stripe test cards (`4242 4242 4242 4242`).
> - **Crediting the wallet happens only in the webhook.** `checkout.session.completed` / `payment_intent.succeeded`, verified with `stripe.Webhook.construct_event` and deduplicated by Stripe event id ([PAY-04](#pay-04)), locks the `Payment`, moves it `pending → completed`, and calls `wallet.add_money()` in the same transaction ([PAY-05](#pay-05)). The browser's success redirect never credits anything.
> - **Local dev:** `stripe listen --forward-to localhost:8000/api/payments/webhooks/stripe/` supplies the webhook secret.
> - **UI:** show a visible "TEST MODE — no real money" banner on the wallet page.
> - **Until this lands,** the free self-credit `POST` must still be removed (step 1 above). The Stripe work depends on PAY-02 (payments app runtime fixes) and PAY-04 (webhook verification).

<a id="sec-02"></a>
### SEC-02: Login `?next=` is an open redirect and a DOM-XSS sink — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** [templates/auth/login.html](templates/auth/login.html) now sends both post-login paths through `postLoginDestination(role)`, which only honours `next` via `safeNextPath()`:
> - The value must start with a single `/`, must parse with `new URL(raw, location.origin)`, and the resulting **origin must equal the page's origin**. That origin comparison is the authoritative check.
> - It also must not point back at `/auth/login`.
> - Anything else falls back to the role default (`/instructor/dashboard/` or `/dashboard/`).
>
> Verified in Node against 20 cases. All of these are rejected: `https://evil`, `//evil`, `/\evil`, `\/evil`, `/<TAB>/evil`, `/<LF>/evil`, `javascript:`, mixed-case `JaVaScRiPt:`, leading-space `javascript:`, `data:`, and a login-page loop. Legitimate paths keep their query string and hash. The script passes `node --check`, and `manage.py test accounts core` passes (37 tests).
>
> **Related bug fixed in the same block:** the "already logged in" branch used to trust the display-only `localStorage.user`. After the auth cookies expired, that caused an infinite redirect loop (the server gate sent the user to `/auth/login/?next=…`, and the page sent them straight back). It now confirms the session with `GET /api/accounts/me/` first, clears the stale cached user on failure, and also honours a safe `next`.
>
> *Remaining follow-up (not blocking):* the JS check has no automated test in the repo yet. Add it when the JS/Playwright harness from [TEST-02](#test-02) exists. No server-side code uses `next`; if one ever does, use `url_has_allowed_host_and_scheme`.

*Original finding:*

**Evidence:** [templates/auth/login.html:156](templates/auth/login.html#L156) assigns `window.location.href = redirectUrl` straight from `URLSearchParams.get('next')`.

**Impact:**
- `/auth/login/?next=https://evil.example` sends the user to a phishing site straight after a real login.
- `?next=javascript:fetch('/api/accounts/token/refresh/',{method:'POST'}).then(...)` runs script in the app's origin. Combined with [SEC-06](#sec-06), that script can steal fresh tokens.

**Fix approach:** Accept `next` only if it is a same-origin relative path:
```js
function safeNext(raw) {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/\\')) return null;
  const u = new URL(raw, window.location.origin);
  return u.origin === window.location.origin ? u.pathname + u.search + u.hash : null;
}
```
Mirror the same check server-side if `next` is ever used in a Django redirect (`url_has_allowed_host_and_scheme`).

**Done when:** `next=//evil`, `next=https://evil`, `next=javascript:…` and `next=/\evil` all fall back to the role default.

<a id="sec-03"></a>
### SEC-03: Secrets committed to git; rotation still pending *(carried over)* — 🟡 REPO SIDE + HISTORY SCRUB DONE 2026-11-21, CREDENTIAL ROTATION PENDING

> **History scrub done 2026-11-21.** GitHub `main` was force-pushed (`--force-with-lease`) from `91e3e0d` to the rewritten `5f9cb72`. **Every commit ID changed;** the commit IDs quoted in the progress note below refer to the *old* history.
>
> **Two more leaks turned up while preparing the rewrite** (my earlier pattern scan missed both):
> - The original hard-coded `SECRET_KEY` was compiled into the **tracked `skillstudio/__pycache__/settings.cpython-312.pyc`**, which was still present in `HEAD`.
> - `DB_PASSWORD` was used as the example `"password"` in **`courses/QUICKSTART.md`** (also in `HEAD`) and in a since-deleted `SETUP_GUIDE.md`.
>
> **What the rewrite did** (`git filter-repo`):
> - Removed `.env`, `BACKEND_CONDITION_REPORT.md`, every `*.pyc`, and the whole vendored `venv/` (5,965 files) from **all** commits.
> - Replaced every leaked value (the old settings key, the `.env` `SECRET_KEY`, `DB_PASSWORD`, the full `DATABASE_URL` and its password, plus any `npg_*` token) with `***REMOVED***`. In the QUICKSTART example it became `<your-password>`.
> - Pack size went from 27.6 MiB to 1.5 MiB.
>
> **Verified:**
> - 92 commits remain; none contains a removed path.
> - Zero occurrences of any leaked value in all 1,085 blobs, both on GitHub's new history and in this local clone (old objects purged locally, including two stale local `refs/codex/turn-diffs/checkpoints/*` refs that pinned the old history).
> - The new `HEAD` differs from the old one only by the removed `venv/`/`.pyc` files and the one redacted doc line.
> - `manage.py check` is clean.
>
> A full pre-rewrite backup mirror is at `../skillstudio-history-backup-2026-11-21.git`. **It still contains the secrets,** so delete it once you're satisfied.
>
> **Still required:**
> 1. **Rotate the Neon DB password.**
> 2. ~~**Set a new `DJANGO_SECRET_KEY` in Railway.**~~ Not needed once the Railway service is deleted ([D-03](#d-03)); the leaked key only ever signed tokens for that deployment.
>
> The scrub does not invalidate already-leaked values. GitHub may also keep serving old commits by their SHA (and any forks keep the old history). If the repo is or was public, ask GitHub Support to purge cached views. Any other clone must be re-cloned; pulling into an old clone would bring the secrets back.

> **Progress 2026-11-21: repo-side remediation done.**
> - **Untracked:** `git rm --cached .env` is **staged** (not yet committed). The local file is kept, still git-ignored, and now `chmod 600`.
> - **Local key rotated:** the local `.env` got a freshly generated `DJANGO_SECRET_KEY` (never printed). The dead, leaked `SECRET_KEY=` line was removed; settings only ever read `DJANGO_SECRET_KEY`. The `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` keys are also unused by the code. Delete them when you update the password.
> - **`.env.example` added:** placeholders only, a local SQLite default (so new clones don't point at the hosted DB, see [OPS-05](#ops-05)), and the planned Stripe test-mode keys.
> - **Production key guard:** [skillstudio/settings.py](skillstudio/settings.py) now raises `ImproperlyConfigured` when `DEBUG=False` and the key is missing, starts with `django-insecure-`, or is shorter than 50 characters. Verified for all three cases, plus a strong key passing.
> - **Secret scanning:**
>   - `.gitleaks.toml` (default rules; `venv/` and `.env.example` allow-listed).
>   - `.pre-commit-config.yaml` (gitleaks hook, plus a hook that blocks committing any `.env*` except `.env.example`; enable with `pre-commit install`).
>   - `.github/workflows/secret-scan.yml` (gitleaks on every push and PR).
> - **Verified:** `manage.py check` is clean locally and under `DEBUG=False` with a strong key. The full suite is unchanged from baseline (226 tests; only the known `payments.tests` import error, [TEST-01](#test-01)).
>
> **Still required (outside the repo, owner action):**
> 1. **Rotate the Neon DB password** (Neon console → role → reset password). Update `DATABASE_URL` in your local `.env`. Until this is done, the leaked password is valid.
> 2. ~~**Set a new production `DJANGO_SECRET_KEY` in Railway** and redeploy.~~ Superseded by [D-03](#d-03): no deployment.
> 3. ~~**Commit the staged `.env` removal** together with the new files.~~ ✅ Done by the owner (`git: secrets removed`).
> 4. ~~**Scrub history.**~~ ✅ Done 2026-11-21; see the note above. *Original plan kept for reference:* This is destructive and needs a force-push, so it was not run. Rotation (steps 1–2) is what actually fixes the exposure; the scrub is hygiene. The leaks are:
>    - `.env` in commits `0365a9c` and `c423c29`
>    - the original hard-coded key in `settings.py` in `741ff0f` (made harmless by step 2)
>    - a **prefix of the DB password** quoted in the old `BACKEND_CONDITION_REPORT.md` (still in `HEAD`)
>
>    ```bash
>    git clone --mirror <repo-url> skillstudio-backup.git           # safety copy
>    git clone --mirror <repo-url> skillstudio-rewrite.git && cd skillstudio-rewrite.git
>    pip install git-filter-repo
>    git filter-repo --invert-paths --path .env --path BACKEND_CONDITION_REPORT.md
>    git push --force --mirror                                      # rewrites every branch/tag
>    ```
>    Afterwards every clone (including this working copy) must be re-cloned or hard-reset, because old clones still contain the secrets. If the GitHub repo is or was public, also ask GitHub Support to purge cached views of the old commits.
> 5. Run `gitleaks detect --config .gitleaks.toml` once after the scrub. It should report nothing outside the allow-list.

*Original finding:*

**Evidence:** `git ls-files .env` shows it is still tracked (it was committed before `.gitignore` covered it). It holds the database URL and password, plus the old `SECRET_KEY`. Settings now require `DJANGO_SECRET_KEY` when `DEBUG=False`, which is good, but the leaked values are still valid until rotated.

**Fix approach:**
1. Rotate the Neon DB password and generate a new `DJANGO_SECRET_KEY`. Rotating the key invalidates all existing JWTs, which is expected.
2. `git rm --cached .env`, commit, and add a committed `.env.example` with placeholder values.
3. Scrub history with `git filter-repo --path .env --invert-paths`, then force-push and coordinate with any collaborators. Treat the old values as public whether or not you scrub.
4. Add a secret scanner (gitleaks) to CI ([OPS-04](#ops-04)).

<a id="pay-01"></a>
### PAY-01: Enrolling charges again for courses already owned (and on double-click) — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Purchasing moved into `payments.services.purchase_course(user, course_id, coupon_code=None)`, a single atomic service:
> - It locks the buyer's and instructor's wallets in a stable order. That serialises one user's purchases (double-clicks and retries) without risking deadlocks.
> - If the user already owns the course, meaning the enrollment is `active` **or** `completed` (`enrollments.constants.ACCESS_STATUSES`), it returns `already_enrolled` and charges nothing.
> - A **canceled** enrollment that was paid for before is **reactivated for free**. One that was never paid is charged.
> - Instructors can't buy their own course, and draft courses can't be bought.
>
> `EnrollmentCreateSerializer` is now input-only (`course_id`, optional `coupon_code`). `EnrollCourseView` returns 201 `created`, 200 `reactivated`/`already_enrolled`, or 400 `{detail, code}`. Covered by service and API tests in `payments/tests.py`.

*Original finding:*

**Evidence:** [enrollments/serializers.py:196-266](enrollments/serializers.py#L196). Inside `EnrollmentCreateSerializer.create`, the wallet debit, instructor credit and `Payment` row are all written **before** `Enrollment.objects.get_or_create(...)`.

**Impact:**
- Calling `POST /api/enrollments/enroll/` for a course the user already has (active **or** completed) debits the wallet again, credits the instructor again, and creates another `Payment`.
- A double-click or retry produces two charges.
- Reactivating after a self-cancel ([CancelEnrollmentView](enrollments/views.py#L104)) charges full price again with no refund policy.
- An instructor can "buy" their own course and pay themselves.

**Fix approach:** Move purchasing into a domain service `enrollments.services.purchase_course(user, course, idempotency_key=None)`:
1. In `transaction.atomic()`, lock the course row and `select_for_update()` any existing `Enrollment(user, course)`.
2. If an enrollment exists with status `active` or `completed`, return it with `200 {"already_enrolled": true}` and **no charge**.
3. Define the reactivation policy explicitly: either free reactivation for a previously paid enrollment, or charge only if a refund was issued.
4. Reject purchases by the course's own instructor.
5. Debit, credit and write `Payment` + `Enrollment` in the same transaction, and store the `Payment` FK on the enrollment for auditability.
6. Optionally accept an `Idempotency-Key` header and store it uniquely on `Payment`.

The serializer becomes validation only; the view calls the service.

**Done when:** these tests pass: re-enroll while active → no new `WalletTransaction` or `Payment`; two concurrent enroll requests → exactly one debit; instructor buying their own course → 400.

<a id="pay-02"></a>
### PAY-02: Payments API crashes: removed `events` domain still referenced *(carried over, expanded)* — ✅ RESOLVED 2026-11-21 (re-scoped by D-01)

> **Resolved 2026-11-21.** Per [D-01](#d-01), the broken card path was **deleted** rather than repaired:
> - **Card purchase removed:** `POST /api/payments/create/`, `PaymentCreateSerializer`, `services.create_payment`, the old `process_payment_success`/`failure` handlers, and `templates/payments/checkout.html` with its `/checkout/` route.
> - **All `event`/`Event`/`specific_events`/`event_id` references removed** from payments views, services and serializers. `CouponSerializer` builds again (coupon list, create and validate no longer 500).
> - **Payout fix:** `get_unpaid_payments_for_instructor` no longer `select_related('event')`, which made `create_payout` crash.
> - **Migration `payments/0002`:** adds `Payment.purpose` and `Coupon.is_public`, and drops the `events` coupon scope. Legacy events coupons are deactivated.
> - **Tests:** `payments/tests.py` was rewritten and now collects and runs (38 tests), including a smoke test that builds every payments serializer.
> - **Found and fixed while testing:** `PayoutSerializer.get_instructor_name` read `User.first_name`, which doesn't exist, so every non-empty payout list returned 500.

*Original finding:*

**Evidence (✔ verified):**
- `Payment(event=None)` raises `TypeError: unexpected keyword arguments: 'event'`, and [payments/services.py:69](payments/services.py#L69) passes `event=event`. So **every** `POST /api/payments/create/` fails. The `except Exception` in the view turns that into a 400 that echoes the Python error.
- `CouponSerializer().fields` raises `ImproperlyConfigured: Field name 'specific_events' is not valid` ([payments/serializers.py:166](payments/serializers.py#L166)). So `GET /api/payments/coupons/`, coupon create, and coupon validate all 500.
- [payments/views.py](payments/views.py): `Event` is referenced (`Event.objects.get`, `Event.DoesNotExist`) but its import is commented out, giving a `NameError` whenever `event_id` is sent.
- [payments/services.py](payments/services.py): `payment.event.instructor`, `coupon.specific_events`, `select_related('course', 'event')`.
- [payments/tests.py:15](payments/tests.py#L15): `from events.models import Event` stops the whole test module from loading.

**Fix approach:**
1. Delete every `event`/`Event`/`specific_events`/`event_id` reference from payments views, services, serializers, admin and tests. `rg -n "event" payments/` should only match migrations and webhook "event" wording.
2. Make `course` required on `Payment` creation, and drop `applies_to='events'` from `Coupon` (with a data migration mapping any `events` coupons to `inactive`).
3. Add smoke tests that build every payments serializer's `.fields` and hit every payments route once.

**Done when:** `manage.py test payments` collects and runs, and every payments route returns a non-500 for a valid request.

<a id="pay-03"></a>
### PAY-03: Payment amount is client-controlled *(carried over)* — ✅ RESOLVED 2026-11-21 (re-scoped by D-01)

> **Resolved 2026-11-21.**
> - **No client-supplied amount anywhere:** the card route that trusted `amount` is gone.
> - **Server-side pricing:** `quote_course_price` computes every course price from the course record (with the coupon applied server-side, `Decimal`, half-up rounding). Only `published` courses can be bought.
> - **Coupon preview:** `POST /api/payments/coupons/validate/` now takes `{code, course_id}` only and ignores any `amount`.
> - **Tests:** a test posts `amount=0.01` for a 100.00 course and still gets charged 100.00.
> - **Remaining (Stripe work):** enforce the top-up amount bounds `WALLET_TOPUP_MIN/MAX` (already in settings) in the top-up endpoint.

*Original finding:*

**Evidence:** [payments/views.py:80](payments/views.py#L80) passes `amount=data['amount']` from the request body into `create_payment`. `CouponValidateView` also trusts the client `amount`. The course isn't required to be `published`.

**Fix approach:**
- Remove `amount` from `PaymentCreateSerializer` and `CouponValidationSerializer`.
- Load `Course.objects.select_for_update().get(id=…, status='published')` and price server-side as `course.price`, then apply the coupon to that.
- Snapshot `original_amount`, `discount_amount`, `platform_fee`, `instructor_earnings` and `currency` on the `Payment`, using `Decimal` with one rounding helper (`quantize(Decimal('0.01'), ROUND_HALF_UP)`).

**Done when:** a test that posts `amount=0.01` for a 200.00 course still creates a 200.00 payment, and a draft course returns 404.

<a id="pay-04"></a>
### PAY-04: Webhooks are unsigned and not idempotent *(carried over)* — 🟡 CONTAINED 2026-11-21, VERIFIED HANDLER PENDING (Stripe)

> **Contained 2026-11-21.**
> - The PayPal webhook and its route were removed (D-01: Stripe only).
> - `StripeWebhookView` now **rejects every request with 503** and changes nothing, so a forged `payment_intent.succeeded` can't complete a payment (covered by a test).
> - The steps the real handler must follow (signature verification, event-id dedup, locked `pending → completed` + wallet credit, no payload echo) are documented in [payments/webhooks.py](payments/webhooks.py).
> - **Still open:** implement it as part of the Stripe test-mode top-up.

*Original finding:*

**Evidence:** [payments/webhooks.py:30](payments/webhooks.py#L30) reads `HTTP_STRIPE_SIGNATURE` but never verifies it; the PayPal handler is the same. Any POST to `/api/payments/webhooks/stripe/` with `payment_intent.succeeded` marks a payment completed. The full payload, including PII, is stored in `PaymentWebhookLog`, and error responses echo `str(e)`.

**Fix approach:**
- Verify with `stripe.Webhook.construct_event(request.body, sig_header, STRIPE_WEBHOOK_SECRET)` before any DB write. For PayPal, call the verify-webhook-signature API.
- Add a `UniqueConstraint(gateway, event_id)` on `PaymentWebhookLog`, and `get_or_create` on it so duplicates short-circuit with 200.
- Store only an allow-listed subset of the payload.
- Return generic error bodies.

<a id="pay-05"></a>
### PAY-05: A successful payment never grants an enrollment *(carried over)* — 🟡 COURSE SIDE RESOLVED 2026-11-21, TOP-UP SIDE PENDING (Stripe)

> **Progress 2026-11-21 (re-scoped by [D-01](#d-01)).** Course fulfilment is now a single transaction in `purchase_course`:
> - wallet debit + instructor credit (ledger rows)
> - `Payment(purpose=course_purchase, status=completed)` with fee and earnings snapshot
> - coupon redemption with an atomic `F('current_usage') + 1`
> - the enrollment created or reactivated
>
> Either all of these happen or none do. Card payments no longer exist, so "payment succeeded but no enrollment" can't happen for courses.
>
> **Still open:** top-up fulfilment (`pending wallet_topup Payment → completed + wallet credit`, called only by the verified webhook) as part of the Stripe work.

*Original finding:*

**Evidence:** `process_payment_success` ([payments/services.py](payments/services.py)) updates the payment and coupon usage but never creates or reactivates an `Enrollment`. The two purchase paths (wallet via enrollments, provider via payments) share no fulfilment code.

**Fix approach:** Create one `fulfil_payment(payment_id)` service.
- It should: lock the payment, enforce the `pending → completed` transition, create or reactivate the enrollment, record the coupon redemption with `F('current_usage') + 1`, and write ledger rows, all in one transaction.
- Both the webhook and the wallet purchase ([PAY-01](#pay-01)) call it.

<a id="lrn-01"></a>
### LRN-01: Learn page never receives lesson content — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **New endpoint.** Student lesson content has its own route, `GET /api/courses/lessons/<id>/content/` (`LessonDetailView`). The shadowed duplicate in `urls_extras.py` was removed.
> - **Access rules.** The course must be visible to you (published, or you own or administer it). Free lessons and free courses are open to anyone who can see the course. Otherwise you need to be the owner, an admin, or a student who owns the course (enrollment `active` or `completed`) and has unlocked the lesson. Refusals return 403 with a code: `not_enrolled`, `lesson_locked` or `login_required`. A draft course returns 404 to anyone else.
> - **View counts.** `view_count` is only incremented when the content is actually served.
> - **One lock rule** (the core of [ENR-03](#enr-03)). The new `enrollments.services.lesson_lock_state` is now used by both the content endpoint and `CourseCurriculumView`, so the sidebar and the server always agree (a test checks every lesson). The rule: free lessons never lock and never gate later lessons; a required lesson unlocks once every earlier required lesson is done. Order is fixed: module position, module id, lesson position, lesson id.
> - **Learn page rewritten** ([templates/students/learn.html](templates/students/learn.html)). The sidebar comes from the curriculum endpoint (shows completed and locked lessons; locked lessons can't be opened), and lesson content comes from the new endpoint. Progress is re-read from the server after each completion.
> - **Bug found and fixed while doing this:**
>   - The earlier XSS pass had wrapped already-built HTML in `escapeHtml` (the sidebar, each section's lessons, and the quiz questions), so they rendered as raw markup.
>   - The stale `localStorage` login check, durations read from a non-existent field, and quiz pass/fail hard-coded at 50% were also fixed. Pass/fail now comes from the server.
> - **Tests** are in `courses/test_learning_flow.py`.

*Original finding:*

**Evidence:**
- [templates/students/learn.html:53](templates/students/learn.html#L53) loads `GET /api/courses/<slug>/sections/`, served by `CatalogModuleSerializer` → `CatalogLessonSummarySerializer` ([courses/serializers.py:186](courses/serializers.py#L186)). That serializer has **no** `video_url` or `content_text`.
- [learn.html:259](templates/students/learn.html#L259) still reads `currentLesson.video_url` and `currentLesson.content_text`, so every lesson shows "No content available".
- The real content endpoint, `LessonDetailView` ([courses/views.py:479](courses/views.py#L479)), is mounted at `api/courses/lessons/<int:lesson_id>/` in `urls_extras`. **✔ verified** that this path resolves to the instructor-only `LessonRetrieveUpdateView` from `courses/urls.py:51`, because that file is included first. So no student-facing content endpoint exists.

**Fix approach:**
1. Give student content its own path, e.g. `api/courses/lessons/<int:lesson_id>/content/` → `LessonDetailView`, and delete the duplicate `lessons/<int:lesson_id>/` entry in `urls_extras`.
2. In `learn.html`, when a lesson is selected, fetch that endpoint and render `video_url` / `content_text` / `resources` from its response.
3. Keep the catalog serializers content-free; that part is correct.

**Done when:** an enrolled student's learn page renders video or text for a paid lesson, an unenrolled user gets 403, and a test covers the URL→view mapping.

<a id="lrn-02"></a>
### LRN-02: Video lessons can never be completed from the UI — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **Server-side URL parsing.** The new `courses/video.py` turns lesson video links into a player descriptor: YouTube (`watch`, `youtu.be`, `embed`, `shorts`), Vimeo, or a direct `.mp4/.webm/.ogg/.m4v/.mov` file. The content endpoint returns it as `video`, and saving a lesson with an unplayable link is rejected (`validate_video_url`).
> - **Real players.** The learn page uses the official YouTube and Vimeo player APIs, or a plain `<video>` element for files.
> - **Watch tracking.** A tracker counts only seconds the video is **actually playing while the page is visible**; seeking ahead doesn't count. It reports bounded deltas to `PATCH /api/enrollments/lessons/<id>/watch-time/` every 30 s, on pause, and when the page is hidden or closed (`keepalive`). A live "Watched N%" bar is shown.
> - **Automatic completion.** At 80% the server completes the lesson, and the course when everything's done. The page then refreshes progress and moves on. The manual **Mark as Complete** button is disabled for trackable videos.
> - **Untrackable links don't trap students.** `CompleteLessonView` requires watch time only for videos the page can actually play and observe. A lesson whose link can't be tracked shows an "open in a new tab" link and can be completed manually.
> - **Tests.** End-to-end, two watch-time reports complete the lesson and the course.
> - **Known limits:**
>   - Watch time is real elapsed time, so watching at 2× speed only counts half.
>   - `duration_seconds` is still typed in by the instructor.
>   - The YouTube and Vimeo scripts load from their own domains (relevant for a future CSP, [SEC-08](#sec-08)).

*Original finding:*

**Evidence:**
- `CompleteLessonView` ([enrollments/views.py](enrollments/views.py)) rejects lessons with `duration_seconds > 0` until watch time reaches 80%.
- Watch time only grows through `PATCH /api/enrollments/lessons/<id>/watch-time/`, and no template calls that endpoint (`grep watch-time templates/` → nothing).

**Impact:** Any course with a video lesson that has a duration can never be completed, so `issue_certificate` never runs. The core value of the product (course → certificate) is unreachable.

**Also:** the player in [learn.html:255-290](templates/students/learn.html#L255) only embeds URLs containing `youtube.com` or `vimeo.com`.
- `youtu.be` short links, direct `.mp4`/HLS files and every other host fall through to a placeholder. There is no `<video>` element at all.
- The lesson types `assignment` and `resource` offered in `Lesson.CONTENT_CHOICES` have no rendering or backend (see [CRS-07](#crs-07)).

**Fix approach:**
- Parse video URLs with a proper helper (`youtu.be`, `youtube.com/watch`, `/embed/`, `vimeo.com/<id>`, direct files → `<video>`), and validate the format server-side in `LessonCreateUpdateSerializer.validate_video_url`.
- In `learn.html`, for HTML5 `<video>` use `timeupdate`; for YouTube/Vimeo use their iframe player APIs.
- Accumulate real played seconds and send `{watch_time_delta}` every 30–60 s and on `pause` / `ended` / `visibilitychange`, respecting the server's 120 s cap.
- After the response's `completed: true`, refresh the curriculum.
- For lessons without a trackable player (an external link, or `duration_seconds = 0`), keep the current "Mark complete" button path.

**Done when:** an end-to-end test (Playwright, or a JS-less API test that simulates the PATCH sequence) shows video → complete → certificate.

<a id="lrn-03"></a>
### LRN-03: Completing a course locks the student out of it — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Every *access* check now uses `enrollments.constants.ACCESS_STATUSES = ('active', 'completed')`:
> - `courses.policies.can_access_course_content`
> - `require_active_enrollment` and the new `get_access_enrollment`
> - curriculum and lesson content
> - course, lesson, resume and next progress; watch time; lesson completion
> - student notes
> - exam access, list and detail
> - quiz access (through `require_active_enrollment`)
> - `CourseDetailSerializer.is_enrolled` and the lesson `is_locked` flag
>
> `CanAccessLesson` no longer grants access to **canceled** enrollments. Counts of in-progress learners (My Learning, dashboard stats, cancel) deliberately keep `active`. The learn page treats a completed course as open and shows a "Course completed" note. Tests cover a completed enrollment keeping access everywhere, and a canceled one being refused.

*Original finding:*

**Evidence:**
- [enrollments/services.py:88](enrollments/services.py#L88) sets `enrollment.status = 'completed'`.
- Almost every access check filters `status='active'`, so a completed enrollment fails all of them:
  - [courses/policies.py:29](courses/policies.py#L29)
  - [enrollments/services.py:236](enrollments/services.py#L236) (`require_active_enrollment`)
  - [courses/views.py:551](courses/views.py#L551) (curriculum)
  - `CourseProgressView`, `LessonProgressView`, `LessonWatchTimeView`, `CompleteLessonView`, `ResumeLessonView`, `NextLessonView`
  - `create_student_note`
  - exam access (`has_active_course_enrollment`)
  - `CourseDetailSerializer.get_is_enrolled` and `get_is_locked`

**Impact:** The moment a student finishes, they get 403 "Active enrollment required" on their own course. They can't review it or take notes, and the detail page shows "Enroll" again. Enrolling again then charges them ([PAY-01](#pay-01)).

**Fix approach:**
1. Add one helper in `enrollments/services.py`: `ACCESS_STATUSES = ('active', 'completed')` and `get_access_enrollment(user, course)`.
2. Replace every `status='active'` access filter with `status__in=ACCESS_STATUSES`. Keep `'active'` only where "in progress" is really meant, such as the My Learning tab.
3. Drop the redundant `Enrollment.is_completed` boolean in favour of `status`, or keep it and enforce consistency with a `CheckConstraint`.

**Done when:** a test completes a course, then asserts that curriculum, lesson content, notes and exam access still return 200.

<a id="fe-01"></a>
### FE-01: All 4 exam pages crash on load (duplicate `const API_BASE`) — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** The four `const API_BASE = '/api';` lines were removed from `exams/list.html`, `take.html`, `results.html` and `create.html`; they only use `apiRequest`, so the base global is enough. A regression test (`core/tests.py`) fails if any template extending `base.html` re-declares one of its top-level `const`/`let`/`class` globals. I checked that it flags the old `exams/list.html`.

*Original finding:*

**Evidence (✔ verified with Node `vm`):**
- [templates/base.html:146](templates/base.html#L146) declares a top-level `const API_BASE`.
- `exams/list.html:60`, `take.html:75`, `results.html:108` and `create.html:240` declare it again in their own top-level `<script>`.
- Classic scripts share one global lexical scope, so the second declaration throws `SyntaxError`. The page script (in `{% block content %}`) renders **before** the base script, so it is the **base** script that fails. That leaves `apiRequest`, `escapeHtml`, `safeUrl`, the CSRF helper and logout undefined on every exam page.

**Fix approach:** Delete the four `const API_BASE = '/api';` lines (the global is enough). Longer term, move shared JS into a versioned `static/js/api.js` loaded in `<head>` ([SEC-08](#sec-08)) and add a lint step that fails on re-declared globals.

---

## 5. P1: High

<a id="sec-04"></a>
### SEC-04: `?ordering=` is passed raw to `order_by()` — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - `CourseListView` now accepts only an allow-list: `created_at`, `published_at`, `price`, `title`, `level` (each optionally prefixed `-`), plus `popular`. Anything else falls back to `-created_at`; that includes `instructor__password`, unknown fields, and the never-implemented `rating`.
> - Every ordering adds a stable `-id` tie-breaker for pagination.
> - It was the only user-controlled `order_by()` in the codebase.
> - Tests in `courses/test_security_fixes.py` confirm sensitive and unknown fields are ignored and no request 500s. They fail on the old code.

*Original finding:*

**Evidence:** [courses/views.py:114-122](courses/views.py#L114) does `queryset.order_by(sort_by)` with `sort_by = request.query_params.get('ordering')`. The endpoint is `AllowAny`.

**Impact:**
- `?ordering=instructor__password` sorts by instructors' password hashes, a known side-channel that leaks hash prefixes by bisection.
- Any unknown field raises `FieldError`, giving a public 500.

**Fix approach:** Use an allow-list, e.g. `{'created_at','-created_at','published_at','-published_at','price','-price','title','-title','popular'}`, or DRF `OrderingFilter` with explicit `ordering_fields`. Unknown values fall back to the default.

<a id="sec-05"></a>
### SEC-05: Instructors can move modules/lessons into other instructors' courses — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Enforced in the serializers, so it covers every view that uses them (`sections/<id>/`, `modules/<id>/update/`, `lessons/<id>/`, `lessons/<id>/update/`):
> - `ModuleCreateUpdateSerializer` refuses to change a module's `course` on update.
> - `LessonCreateUpdateSerializer` only lets a lesson move to a module of the **same** course.
>
> `ModuleCreateView` / `LessonCreateView` return 400 instead of a `KeyError` 500 when the parent is missing; ownership of the parent was already checked on create. Tests cover cross-course moves, a same-course move (still allowed), missing parents, and creating inside someone else's course. They fail on the old code.

*Original finding:*

**Evidence:**
- `ModuleCreateUpdateSerializer.course` ([courses/serializers.py:136](courses/serializers.py#L136)) and `LessonCreateUpdateSerializer.module` ([courses/serializers.py:55](courses/serializers.py#L55)) are writable on **update**.
- `ModuleUpdateView`, `LessonUpdateView` and `LessonRetrieveUpdateView` only check ownership of the *current* parent.

**Impact:** An instructor can PATCH their own lesson with `{"module": <victim module id>}` and inject content into someone else's course, including a published one. `ModuleCreateView` also raises `KeyError` (500) when `course` is omitted.

**Fix approach:**
- Make `course` / `module` read-only on update, with separate create serializers.
- In create views, validate the parent with `can_manage_course(user, parent.course)` and the editable status.
- Return 400 if the parent is missing.

<a id="sec-06"></a>
### SEC-06: Token endpoints return JWTs in the JSON body, undoing httpOnly cookies — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** [accounts/custom_token.py](accounts/custom_token.py) now has two explicit modes.
>
> **Cookie mode (the default, browsers):**
> - Login and refresh are **CSRF-checked**, which closes login CSRF.
> - JWTs are set only as httpOnly cookies, and the body contains **no tokens** (`{"detail": "Logged in."}` / `"Token refreshed."`). Injected JS can trigger a refresh but can't read a token.
>
> **Token mode (header-based API clients):**
> - Login with `{"token_in_body": true}`, or refresh by sending `{"refresh": …}` in the body. Tokens are returned in the body and **no cookies are set**, so no ambient credential exists and CSRF doesn't apply.
> - Login still needs the password; refresh needs a refresh token the client already holds.
>
> The login page already sent `X-CSRFToken` and never read body tokens, so the browser flow is unchanged. There are 7 new tests, covering login CSRF, the cookie-refresh body, refresh CSRF and both token-mode paths; they fail on the old code. Existing tests that read tokens from the login body now use token mode.
>
> **Deliberately not done:** scoping the refresh cookie's `path` to `/api/accounts/`. The server-side page gate (`core/auth.py`) reads the refresh cookie on page loads so users with an expired 30-minute access token aren't bounced to the login page. The cookie is httpOnly, `SameSite=Lax` and `Secure` in production, so narrowing its path gains little. Revisit if the page gate changes.

*Original finding:*

**Evidence:** [accounts/custom_token.py:53](accounts/custom_token.py#L53): `CookieTokenRefreshView` responds with `serializer.validated_data` (`access` and `refresh`) as well as setting cookies. Login does the same.

**Impact:** The reason for moving JWTs to httpOnly cookies was that XSS can't read them. But any injected script can simply `POST /api/accounts/token/refresh/` (the cookie is sent automatically) and read new tokens from the body. This chains with [SEC-02](#sec-02).

**Fix approach:**
- When the refresh token came from the cookie, and on login from a browser, strip `access`/`refresh` from the body (return `{}` or user info only).
- Header-based API clients keep body tokens through an explicit flag (e.g. `?token_in_body=1` honoured only with an `Authorization`/API-key context), or use API keys.
- Also scope the refresh cookie `path` to `/api/accounts/token/` so it isn't sent on every request.
- Add CSRF protection to login and refresh (they are currently CSRF-exempt, which allows login CSRF).

<a id="sec-07"></a>
### SEC-07: Anyone can self-register as an instructor *(carried over; mislabelled resolved)* — ✅ RESOLVED 2026-11-21 (Decision D-02)

> **Resolved 2026-11-21 by owner decision [D-02](#d-02).**
> - `RegisterSerializer` no longer accepts a client `role`; any `role` sent is ignored. The role is derived from the email domain: `@instructor.com` → instructor, everything else → student.
> - `@admin.com` signups are refused, so no account can register as admin.
> - The signup page's role picker was replaced by a short explanation of the rule, and the success message names the account type that was created.
> - Tests cover each domain, case-insensitivity, look-alike domains (`@evil.instructor.com`, `@instructor.com.evil.io`), an ignored client `role`, and the admin refusal.
> - The remaining exposure (no email verification) is the accepted trade-off recorded in D-02.

*Original finding:*

**Evidence:** [accounts/serializers.py:14](accounts/serializers.py#L14) accepts `role='instructor'` at signup. In the old remediation plan, P1-01 is titled after this issue, but its "Resolved" note describes email and refresh-token work. This issue was never fixed.

**Fix approach:** Product decision. Either:
- **(a)** Default every signup to `student` and gate instructor status behind the existing `PromoteToInstructorView` or an "apply to teach" flow with `InstructorProfile.is_verified`; or
- **(b)** Keep open instructor signup, but require `is_verified` before a course can be submitted for review or published.

Document the choice either way.

<a id="pay-06"></a>
### PAY-06: Instructor payout requests are not reserved or locked — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** `payments.services.create_payout` (alias `request_payout`) locks the instructor's wallet, validates the amount as a `Decimal` (minimum $10.00; it defaults to the whole balance), and **debits (reserves) it immediately** (`Payout.wallet_debited=True`).
> - Pending requests can therefore never add up to more than the wallet, and the same money can't be requested twice.
> - Rejected, failed or cancelled payouts credit the amount back.
> - All state changes lock the payout row and enforce `pending → processing → paid` (or `→ cancelled/failed`).
> - Bad input returns 400 `{detail, code}` instead of a 500.

*Original finding:*

**Evidence:** [instructors/services.py:161-191](instructors/services.py#L161)
- `request_payout` computes `available = earnings − (completed + processing)`, so **pending** requests are not subtracted.
- An instructor can file any number of pending requests, each for the full balance.
- There is no row lock.
- `amount` comes straight from `request.data`: a string or `None` raises `TypeError` (500), and a float mixes with `Decimal`.

**Fix approach:**
- Parse `amount` with a serializer `DecimalField(min_value=MIN_PAYOUT)`.
- Lock the instructor's balance row (or a per-instructor advisory lock).
- Include `pending` in reserved funds.
- Fold this into the single payout model from [PAY-07](#pay-07).

<a id="pay-07"></a>
### PAY-07: Two payout systems, two fee rates, and earnings counted twice — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21 (payouts on the wallet ledger).**
> - **The instructor wallet is the single source of truth** for withdrawable money. `calculate_instructor_balance` reports `available` = wallet balance, `pending` = reserved open payouts, `paid_out`, and `total_earnings` net of refunds. `Payment.instructor_earnings` is now only an immutable reporting snapshot, so earnings can't be withdrawn twice (covered by a test).
> - **One payout model:** `instructors.InstructorPayout`, its routes (`/api/instructors/payouts/…`), services, serializers, admin and tests were removed. Migration `instructors/0003` first **copies every legacy row into `payments.Payout`** (`completed → paid`) with `wallet_debited=False`. Approving or completing such a legacy payout reserves the money from the wallet first, and refuses if the wallet can't cover it.
> - **Full admin lifecycle** under `/api/payments/payouts/<id>/`: `approve/`, `complete/` (needs `transaction_id`), and `reject/` (returns funds). Instructors can `cancel/` their own pending request. Admins can list all payouts (`?status=`).
> - **Instructors can read their own wallet:** `GET /api/students/wallet/` and its transactions are no longer student-only.
> - **Dashboard:** the instructor dashboard revenue comes from the same ledger (adds `available`, `pending_payouts`, `paid_out`).
> - **Reconciliation:** `python manage.py reconcile_payout_ledger` (dry run unless `--apply`) debits legacy *paid* payouts that never left the wallet, which is the money the old system counted twice. It skips and reports any instructor whose wallet can't cover it. **Run it once after deploying.**
> - **No admin bypass:** the Payout and Refund admin forms now show money and state fields as read-only.
> - The deprecated `Payout.payments` M2M is kept only for history.
> - There is now **one fee rate**, `settings.PLATFORM_FEE_RATE` (env-overridable, default `0.10`, which keeps the rate users actually experienced). It's applied through `payments.services.split_platform_fee`; the unused `0.20` constant is gone.
> - Revenue stats (`get_payment_stats`, `AdminCourseStatsView`) count only `course_purchase` payments, so top-ups aren't revenue.
> - *(Earlier progress the same day: one fee rate, `settings.PLATFORM_FEE_RATE` (default `0.10`), applied via `split_platform_fee`; revenue stats count only `course_purchase` payments.)*

*Original finding:*

**Evidence:**
- **Two payout models:** `payments.Payout` (statuses `paid`/`processing`/…, with an M2M to payments) and `instructors.InstructorPayout` (statuses `completed`/`processing`/…).
- `/api/instructors/payouts/request/` writes `InstructorPayout`, but the instructor dashboard reads `payments.Payout` ([instructors/services.py:64](instructors/services.py#L64)), so an instructor never sees their own requests.
- **Two fee rates:** 10% in the enrollment wallet flow ([enrollments/serializers.py](enrollments/serializers.py)) vs `PLATFORM_FEE_RATE = 0.20` ([payments/services.py:23](payments/services.py#L23)).
- **Earnings counted twice:** a wallet purchase credits the instructor's `Wallet` **and** writes a `Payment(status='completed', instructor_earnings=…)` that both payout systems count as withdrawable. The same money can be spent from the wallet *and* paid out.

**Also:** `InstructorPayout` has no approval or completion API. `instructors.services.complete_payout` is never called, so requests can only be moved by hand-editing them in Django admin. The admin side of `payments.Payout` only has `approve` (no complete/fail endpoint either).

**Fix approach:**
1. Pick one payout model: keep `payments.Payout`, migrate `InstructorPayout` rows into it, delete the other model and the `/api/instructors/payouts/*` routes (or turn them into aliases). Give it a full admin lifecycle (`approve → processing → paid | failed`) through service functions.
2. Put one `PLATFORM_FEE_RATE` in settings and import it everywhere.
3. Decide where instructor earnings live. Either the `Wallet` ledger (then payouts debit the wallet), or `Payment.instructor_earnings` (then don't credit the wallet on purchase). Never both.
4. Add a reconciliation management command: Σ purchases − Σ fees − Σ payouts − Σ refunds = Σ balances.

<a id="pay-08"></a>
### PAY-08: Refunds can exceed the payment and have no financial effect *(carried over, expanded)* — ✅ RESOLVED 2026-11-21 (re-scoped by D-01)

> **Resolved 2026-11-21.** Refunds apply to `course_purchase` payments and move money **wallet to wallet**.
> - **Requesting** (`request_refund`, from the student): locks the payment. Only one open request per payment is allowed. `amount` defaults to everything still refundable, and **cumulative refunds can never exceed the payment**. Top-ups and other users' payments are refused.
> - **Approving** (`approve_refund`, admin): credits the student's wallet and debits the instructor's **pro-rata share**. That share is cent-exact overall: the final refund takes back exactly what remains, so there's no rounding drift. It records `instructor_debit` on the refund and sets the payment to `partially_refunded` or `refunded`.
> - **Full refund revokes access:** the enrollment is canceled. Re-buying then charges again. Certificate revocation is still CRT-01.
> - **Instructor already paid out:** if their wallet can't cover the share, approval is refused (`instructor_balance_insufficient`) unless the admin passes `absorb_shortfall=true`. In that case the platform covers the rest, recorded as `platform_absorbed`.
> - **Rejecting** moves no money.
> - **Removed:** the webhook-only `process_refund`. Views return `{detail, code}` and no longer echo Python errors.
> - Refunding a Stripe top-up back to a card stays out of scope for the demo.

*Original finding:*

**Evidence:** [payments/services.py:214](payments/services.py#L214)
- `request_refund` checks each request against the payment amount individually, so repeated partial requests can sum to more than the payment.
- `approve_refund` flips statuses but never credits the wallet or revokes the enrollment.
- `process_refund` zeros **all** instructor earnings even on a partial refund.
- There is no locking.

**Fix approach:**
- Lock the payment and enforce `Σ(approved + requested) ≤ amount`.
- On approval, credit the wallet (for wallet payments) or call the provider refund API.
- Define entitlement reversal (a full refund cancels the enrollment and revokes the certificate).
- Pro-rate the fee and earnings reversal for partial refunds.

<a id="pay-09"></a>
### PAY-09: Every active coupon code is listed to every logged-in user — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **Visibility:** `Coupon.is_public` was added. Existing coupons default to private, so nothing is newly exposed. Students see only public, active coupons, through a slim `PublicCouponSerializer` (no usage stats or admin fields). Admins see all.
> - **Race fixed:** the usage counter increments with `F('current_usage') + 1`.
> - **Coupon creation:** validates `specific_course_ids` and requires them for `applies_to='specific'`.
> - **Tests:** visibility, admin creation and student refusal are covered.

*Original finding:*

**Evidence:** [payments/views.py:343](payments/views.py#L343): `CouponListView` returns `get_active_coupons()` to any authenticated user. That includes private and targeted codes. (It currently 500s because of [PAY-02](#pay-02); fixing PAY-02 exposes this.) `current_usage += 1` is also a read-modify-write race.

**Fix approach:** Make the list admin-only and add `Coupon.is_public` for codes meant to be advertised. Increment with `F('current_usage') + 1` and check `usage_limit` under the lock.

<a id="asm-01"></a>
### ASM-01: Unpublished or failed quizzes permanently block course completion — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **What counts:** `is_lesson_assessment_completed` only counts a quiz that is **published and has questions** (`Quiz.counts_for_completion`). Drafts and empty quizzes never block a lesson.
> - **Retakes:** new `Quiz.max_attempts` (default **3**; null = unlimited; instructors set it through the quiz-management API, where 0 or empty means unlimited). `QuizAttempt.attempt_number` and a `(quiz, user, attempt_number)` unique constraint replace the old one-attempt-per-student constraint, and a partial unique constraint allows only **one open attempt** per student. Migration `assessments/0006` backfills existing rows as attempt 1.
> - **Passing:** passing any attempt is enough. Starting again after passing is refused, and so is starting when no attempts are left. An open attempt is resumed; one whose time ran out is graded first.
> - **Student status:** `GET /api/assessments/quiz/lesson/<id>/` returns the student's `attempt_status` (attempts used and remaining, passed, can start, last result) and returns 404 to students for unpublished quizzes.
> - **Learn page:** shows the attempt count and a **Try again** button after a failed attempt, a "passed" state, and "No attempts left".
> - **Tests:** `assessments/test_quiz_rules.py`.

*Original finding:*

**Evidence:**
- [assessments/services.py:255](assessments/services.py#L255): `is_lesson_assessment_completed` requires a passed attempt whenever `hasattr(lesson, 'quiz')`, **including unpublished quizzes**, which `start_quiz_attempt` refuses to start.
- Attempts are limited to one per user per quiz (DB constraint, migration `0003`), so one failed attempt blocks the lesson forever.

**Impact:**
- An instructor drafting a quiz silently makes the lesson impossible to complete for every student.
- A student who fails once can never complete the course or earn its certificate.

**Fix approach:**
- Count only `quiz.is_published` quizzes.
- Add `Quiz.max_attempts` (default 1 is fine) or a policy setting, and change the unique constraint to `(quiz, user, attempt_number)`. The exams app already does this.
- Alternatively, make passing optional per quiz with `Quiz.required_to_complete`.

<a id="asm-02"></a>
### ASM-02: Quiz time limit can be bypassed — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** The deadline is enforced in the grading service itself (`submit_quiz_attempt`), so every route obeys it.
> - **After the deadline:** once the time limit plus a `QUIZ_SUBMIT_GRACE_SECONDS = 10` network allowance has passed, posted answers are **ignored**. Only answers saved in time through the per-answer endpoint are graded, and the attempt is marked `is_auto_submitted`.
> - **Saving answers:** `save_quiz_answer` refuses saves after the deadline, and the answer endpoint uses the same rule, auto-grading at that point.
> - **One grading path:** the timer's `auto_submit_attempt` now uses the same function, and the unrouted duplicate `SubmitQuizAttemptView` was deleted.
> - **Learn page:** saves each selected answer immediately, so a timed quiz keeps everything answered before time ran out, and explains when an attempt was auto-submitted.
> - **Tests** cover late answers being ignored, saved answers still graded, the grace window, a late answer-save auto-submitting, and an expired open attempt graded on the next start.

*Original finding:*

**Evidence:**
- [assessments/views.py:49](assessments/views.py#L49): `SubmitQuizView` (the endpoint `learn.html` uses) grades whatever is sent, with no `is_expired()` check.
- `SubmitQuizAnswerView` does enforce expiry, so the two paths disagree.

**Fix approach:** In `submit_quiz_attempt`, if `quiz.has_time_limit() and attempt.is_expired()`, grade only the answers already saved, set `is_auto_submitted`, and ignore the posted `answers`. Delete the unrouted duplicate `SubmitQuizAttemptView`.

<a id="exm-01"></a>
### EXM-01: Exam questions are visible before the exam window opens

**Evidence:**
- `start_exam_attempt` ([exams/services.py](exams/services.py)) correctly refuses to start outside `start_datetime`/`end_datetime` via `Exam.is_active()`.
- However, `ensure_student_can_access_exam` ([exams/views.py:45](exams/views.py#L45)) only checks `status` and enrollment. So `GET /api/exams/<id>/` (`ExamDetailView`, used by `take.html`) returns the **full question set and options** to enrolled students days before the exam opens.
- Submission doesn't re-check the window either.
- `start_exam` turns every `ValueError` into a generic "could not be started", so students never learn *why* (not open yet / closed / attempts used up).

**Fix approach:**
- Call `exam.is_active()` in `ensure_student_can_access_exam` for non-owners, and have the student detail serializer omit `questions`/`custom_questions` unless the user has an `in_progress` attempt.
- Re-check `end_datetime` (with a grace period of `duration_minutes`) in `submit_exam_attempt`.
- Map the service errors to explicit, safe messages.

<a id="api-01"></a>
### API-01: 24 frontend calls target endpoints that don't exist — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Every template API call now resolves to a real route. A new test, `core.tests.TemplateApiContractTests`, fails if any template calls an endpoint that doesn't exist; I checked that it flags the old templates. Per page:
>
> - **Assessments pages** (`/assessments/` list, attempt, results) — **deleted** along with their views and routes. Nothing linked to them, all 8 of their endpoints were fictional, and quizzes are taken in the learn page ([ASM-01](#asm-01)).
> - **Resources pages** (`/courses/<id>/resources/`, `/instructor/resources/`) — **deleted** along with their views and routes. Nothing linked to them, and no resources API exists. Lesson resources are shown per lesson on the learn page. *Gap noted:* there's still no API or UI for instructors to add `LessonResource`s (admin only).
> - **Checkout and payment history** — fixed earlier ([D-01](#d-01)).
> - **Certificates page download** — was already correct: `cert.id` is the UUID primary key the `<uuid:…>/download/` route expects. The audit's resolver had substituted a number.
> - **My Courses certificate button** — now downloads from the existing `GET /api/certificates/download/<course_id>/`.
> - **Featured instructors** (browse page) — new public `GET /api/instructors/featured/`: instructors with published courses, most students first, name, headline and counts only (no emails). Cards link to `/courses/?instructor=<id>` instead of a non-existent `/instructors/<id>/` page.
> - **Search page** — called `apiRequest('/api/courses/search/')`, which was both a doubled `/api/api/` prefix and a shadowed route. It now uses `GET /api/courses/?search=…`, with its sort values mapped to the allow-listed `ordering`. `CourseListView` gained comma-separated `category`/`level` and a `duration` filter in hours (`0-2`, `2-5`, `5-10`, `10+`). The never-implemented rating filter and "Highest Rated" sort were removed.
> - **Course list page — two more silent contract bugs fixed:**
>   - Its "Most Popular" sort sent `-enrollment_count` (now `popular`).
>   - Its "Free only" box sent `free_only`, which the API ignored (now `is_free=true`).
>   - It also now honours `?instructor=` and `?search=` from the page URL, and a non-numeric `instructor` no longer 500s.
> - **Tests:** `courses/test_discovery.py`.

*Original finding:*

**Evidence (✔ verified by resolving every call site):**

| Template | Calls (all 404) | Effect |
|---|---|---|
| [assessments/list.html:122](templates/assessments/list.html#L122), [attempt.html:45-306](templates/assessments/attempt.html#L45), [results.html:38-253](templates/assessments/results.html#L38) | `/assessments/?…`, `/assessments/<id>/questions/`, `/assessments/<id>/start-attempt/`, `/assessments/attempts/<id>/`, `…/save/`, `…/submit/`, `…/results/`, `…/certificate/` | The whole `/assessments/` section is dead. The real API is `/api/assessments/quiz/...`. |
| ~~payments/checkout.html:239~~ | `POST /payments/checkout/` | ✅ **Resolved 2026-11-21:** page and `/checkout/` route deleted (D-01: courses are bought from the wallet on the course page). |
| [payments/history.html](templates/payments/history.html) | `/payments/transactions/…` (list, detail, invoice, retry) | ✅ **Resolved 2026-11-21:** rewired to `GET /api/payments/?status=` (which also fixes a doubled `/api/api/` prefix). It labels top-ups vs purchases, counts "spent" from purchases only, and renders its own icons unescaped. The non-existent invoice/receipt/retry actions were removed. |
| [courses/resources.html:158,409](templates/courses/resources.html#L158), [instructor/resources.html:193-464](templates/instructor/resources.html#L193) | `/courses/<id>/resources/`, `/resources/<id>/download/`, `/instructor/courses/…`, `…/resources/upload/`, `…/folders/`, `PATCH`/`DELETE /resources/<id>/` | The resources feature has no backend at all (only a `LessonResource` model). |
| [search/browse.html:145](templates/search/browse.html#L145) | `/instructors/featured/` | Featured instructors section is empty. |
| [certificates/list.html:184](templates/certificates/list.html#L184) | `/certificates/<id>/download/` built with `${API_BASE}` | Resolves only if `<id>` is the UUID PK. Verify it uses `cert.id`, not `certificate_id`. |
| [students/my-courses.html:207](templates/students/my-courses.html#L207) | `/enrollments/<id>/certificate/` | Certificate button is dead. Use `/api/certificates/my/<course_id>/`. |

**Fix approach:** For each feature, decide **build or remove**.
- Rewire the assessments pages to the existing quiz API, or delete them (the learn page already handles quizzes inline).
- Rewire payment history to `GET /api/payments/` and `/api/payments/<id>/`.
- Delete `checkout.html` until the payments rebuild lands; the course page already enrolls via the wallet.
- Hide the resources and featured-instructor UI until the endpoints exist.

Then add the contract test from [TEST-02](#test-02) so this can't regress.

<a id="api-02"></a>
### API-02: Route shadowing: `tags/`, `search/`, lesson content, numeric slugs — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **One route file.** `courses/urls_extras.py` was merged into [courses/urls.py](courses/urls.py) and deleted. All fixed paths come first and the slug catch-alls last, so `tags/`, `categories/create/`, `modules/…`, `lessons/…`, `instructor/…` and `admin/…` are all reachable. The duplicate `categories/` route is gone.
> - **Safe slugs.** `Course.save()` now uses `safe_course_slug_base`: a slug is never empty (`course`), never purely numeric (where `<int:id>/` would win), and never a reserved route word (`tags`, `create`, `categories`, …); those get a `-course` suffix.
> - **Existing data.** Migration `courses/0003` re-slugs any existing course that collides, keeping slugs unique.
> - **Earlier the same day:** lesson content got its own route ([LRN-01](#lrn-01)), and search moved to `?search=` ([API-01](#api-01)).
> - **Duplicate route names.** The duplicate `instructor-dashboard` URL name (an alias under `/api/enrollments/`) was renamed.
> - **Tests:** `courses/test_routes.py` (route resolution, reserved and numeric slugs, the migration).

*Original finding:*

**Evidence (✔ verified with `resolve()`):** `courses/urls.py` (which ends in a `<slug:slug>/` catch-all) is included before `courses/urls_extras.py` on the same `api/courses/` prefix ([skillstudio/urls.py:27](skillstudio/urls.py#L27)). As a result:
- `/api/courses/tags/` resolves to `CourseDetailView(slug='tags')` (404), so `TagListCreateView` is unreachable.
- `/api/courses/search/` resolves to `CourseDetailView(slug='search')` (404), so the search page ([search/results.html:234](templates/search/results.html#L234)) is dead. There is no search view; search is a `?search=` param on the list view.
- `/api/courses/lessons/<id>/` resolves to the instructor editor view, never `LessonDetailView` ([LRN-01](#lrn-01)).
- `/api/courses/categories/` is defined twice (duplicate name `category-list`).
- A course whose slug is all digits (title "2024") is fetched by **id** through `<int:id>/`.

**Fix approach:**
- Merge `urls_extras.py` into `urls.py` with the slug catch-all last, or move slug routes under `by-slug/<slug>/`.
- Point the search page at `/api/courses/?search=…`.
- Make `slugify` output never purely numeric (append `-course`).

<a id="api-03"></a>
### API-03: Section and lesson delete buttons return 405 — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **Server.** `ModuleUpdateView` (`sections/<id>/`) and `LessonRetrieveUpdateView` (`lessons/<id>/`) are now `RetrieveUpdateDestroyAPIView`. DELETE follows the same rules as the existing delete views: owner only, course in `draft`; otherwise a 400 with the reason.
> - **Client.** Found while fixing: a successful delete returns `204 No Content`, and the shared `apiRequest` helper always called `response.json()`, so it threw and the page said "Failed to delete" even when the delete worked. `apiRequest` now returns `null` for empty or 204 responses (`parseJsonBody`, also on the token-refresh retry path), and the delete buttons show the server's error message.
> - **Regression guard.** `core.tests.TemplateApiContractTests` now also checks that each template call's HTTP method is handled by the resolved view.
> - **Tests:** `courses/test_routes.py` (owner delete in draft → 204, refused outside draft, non-owner refused).

*Original finding:*

**Evidence:** [instructor/course-content.html:348](templates/instructor/course-content.html#L348) and [:361](templates/instructor/course-content.html#L361) send `DELETE /courses/sections/<id>/` and `DELETE /courses/lessons/<id>/`. Those paths resolve to `ModuleUpdateView` (UpdateAPIView) and `LessonRetrieveUpdateView` (RetrieveUpdateAPIView), neither of which allows DELETE. The real delete routes are `/modules/<id>/delete/` and `/lessons/<id>/delete/`.

**Fix approach:** Use `RetrieveUpdateDestroyAPIView` for both, with the same ownership and draft checks as the existing delete views. Then delete the redundant `…/delete/` routes or keep them as aliases.

<a id="bug-01"></a>
### BUG-01: Instructor lesson-analytics CSV export always 500s — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** `InstructorLessonAnalyticsCSVView` now:
> - counts the correct relation (`lesson_progress`);
> - computes the drop-off rate in Python, so an unstarted lesson is 0% instead of a SQL division by zero;
> - prefixes cells that start with `= + - @ TAB CR` with `'` (CSV formula injection);
> - lists lessons in study order;
> - uses `can_manage_course`, so the owner or an admin can export and others get 404.
>
> A test parses the CSV, including a formula-like title and an unstarted lesson.

*Original finding:*

**Evidence (✔ verified):**
- [enrollments/views.py:569](enrollments/views.py#L569): `Count('lessonprogress')` raises `FieldError` because the reverse name is `lesson_progress`.
- After that is fixed, `drop_off_rate = drop_off_count * 100.0 / started_count` divides by zero on Postgres for lessons nobody started.
- Lesson titles are written into the CSV unescaped (formula injection: `=HYPERLINK(...)`).

**Fix approach:**
- Use `Count('lesson_progress', …)`.
- Wrap the division: `Case(When(started_count=0, then=Value(0.0)), default=…)`.
- Prefix cells that start with `= + - @` with `'`.
- Add a route test.

<a id="bug-02"></a>
### BUG-02: `InstructorCoursesView` error path raises `NameError` — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** The try/except wrappers (with the un-imported `logging` that caused the `NameError`) were removed, so errors now go through DRF's normal handler. The queryset gained a stable `-id` tie-breaker. A route test covers the list.

*Original finding:*

**Evidence:** [courses/views.py:259](courses/views.py#L259): `list()` calls `logging.getLogger` inside `except`, but `logging` is only imported locally inside `get_queryset`. Any error becomes `NameError`.

**Fix approach:** Import `logging` at module level with a module `logger`, and delete the try/except wrappers entirely. DRF's exception handler already returns a 500 and logs it.

<a id="crs-01"></a>
### CRS-01: Access policy is fragmented and inconsistent — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** [courses/policies.py](courses/policies.py) is now the single source of truth. It answers four questions, each built on the previous one:
> - `can_view_course_catalog`: published, or you're the owner or an admin.
> - `can_access_course_content`: you can see the course **and** it's free, or you're the owner or an admin, or you have an `active`/`completed` enrollment.
> - `can_access_lesson`: a free-preview lesson of a visible course is open to anyone.
> - `can_manage_course`: owner or admin.
>
> **Changes:**
> - **Bug fixed:** content access used to skip the visibility check for free courses, so a **draft free course was open to anyone**.
> - `LessonDetailView`, `CourseCurriculumView` and the course-detail `is_locked` flag now call these policies instead of re-implementing them. The progression lock applies to every enrolled non-manager, so it matches the curriculum for free courses too.
> - `courses/permissions.py` was deleted: `CanAccessLesson` was unused, and `CanEditCourse` was attached to a view that never runs object permissions.
> - **Tests:** `courses/test_access_policy.py` checks the full matrix: 8 kinds of viewer × 4 course statuses × free/paid, for catalog, content, manage, a paid lesson and a free-preview lesson.

*Original finding:*

**Evidence:**
- [courses/permissions.py](courses/permissions.py): `CanAccessLesson` grants access for **any** enrollment status (including `canceled`).
- `policies.can_access_course_content` requires `active`.
- `CourseCurriculumView` ([courses/views.py:530](courses/views.py#L530)) has no `can_view_course_catalog` check, so the curriculum of a free **draft** course is public by id.
- `CanEditCourse` is attached to `SubmitCourseForReviewView` but never runs, because `APIView` doesn't call `get_object`.

**Fix approach:**
- Make `courses/policies.py` the only place access is decided (catalog visibility, content access, manage), using `ACCESS_STATUSES` from [LRN-03](#lrn-03).
- Delete `courses/permissions.py` or make it delegate to the policies.
- Add a policy test matrix: role × course status × enrollment status.

<a id="ops-01"></a>
### OPS-01: WhiteNoise storage setting is silently ignored on Django 6 — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21** (done on request despite [D-03](#d-03)).
> - **Setting.** `STATICFILES_STORAGE` was replaced with `STORAGES` (`staticfiles` → `CompressedManifestStaticFilesStorage`).
> - **Verified with `DEBUG=False`:** `collectstatic` writes the manifest, the admin page links `base.<hash>.css`, and WhiteNoise serves it gzipped with `Cache-Control: max-age=315360000, public, immutable`.
> - **Tests** use plain static storage (see the test runner under [OPS-02](#ops-02)), because Django runs tests with `DEBUG=False`, where the manifest would require a prior `collectstatic`.
> - **Local note:** with `DEBUG=True`, `runserver` serves unhashed files as before; for a `DEBUG=False` run, run `collectstatic` first.

*Original finding:*

**Evidence (✔ verified):** `STATICFILES_STORAGE` ([skillstudio/settings.py:194](skillstudio/settings.py#L194)) was removed in Django 5.1. At runtime, `settings.STORAGES['staticfiles']` is the plain `StaticFilesStorage`, so there are no compressed or hashed static files and no long-cache headers. `check --deploy` doesn't flag it.

**Fix approach:**
```python
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
```
Delete `STATICFILES_STORAGE`, run `collectstatic` in the build step, and confirm hashed filenames are served.

<a id="ops-02"></a>
### OPS-02: Certificate PDFs live on local disk and aren't served in production — ✅ RESOLVED 2026-11-21 (local scope, D-03)

> **Resolved 2026-11-21** for a local-only project ([D-03](#d-03)); object storage isn't needed while nothing is deployed.
> - **Missing files.** `certificate_has_pdf` now checks that the file **exists in storage**, not just that a name is recorded. The new `ensure_certificate_pdf` re-renders a missing PDF on download, so a deleted or never-rendered file downloads normally instead of a `FileNotFoundError` 500. If rendering fails, the view returns a clean 503.
> - **Not public.** PDFs are **no longer served at `/media/`.** The `DEBUG` media route exposed every certificate to anyone with the URL; now they're only reachable through the authenticated `/api/certificates/.../download/` endpoints. Certificate PDFs are the only stored files.
> - **Test isolation.** A project test runner (`skillstudio/test_runner.py`, `TEST_RUNNER`) gives each run a temporary `MEDIA_ROOT` (deleted afterwards), which closes [TEST-01](#test-01).
> - **Tests:** `certificates/test_storage.py`.

*Original finding:*

**Evidence:**
- `Certificate.pdf` uses the default `FileSystemStorage` under `MEDIA_ROOT`.
- Media is only routed when `DEBUG` ([skillstudio/urls.py](skillstudio/urls.py)).
- Railway's filesystem is ephemeral, so after a redeploy `certificate.pdf` still names a missing file and `DownloadCertificateView` 500s on `FileNotFoundError`.

**Fix approach:** Use object storage (S3/R2 via `django-storages`) for `STORAGES['default']`. In `certificate_has_pdf`, check `storage.exists(name)`, and if the file is missing, re-render on demand.

<a id="ops-03"></a>
### OPS-03: `gunicorn==21.2.0` has known request-smuggling CVEs — ✅ RESOLVED 2026-11-21 (D-03)

> **Resolved 2026-11-21:** `gunicorn` was only the production web server. With no deployments it was removed from `requirements.txt` (along with the unused `daphne`), so the vulnerable version is gone.

*Original finding:*

**Evidence:** [requirements.txt](requirements.txt) pins `gunicorn==21.2.0`. That version is affected by CVE-2024-1135 (fixed in 22.0.0) and CVE-2024-6827 (fixed in 23.0.0).

**Fix approach:** Bump to `gunicorn>=23.0.0`, and add `pip-audit` to CI ([OPS-04](#ops-04)) so dependency CVEs fail the build.

<a id="test-01"></a>
### TEST-01: Payments tests don't run, and tests write into the real `media/` — ✅ RESOLVED 2026-11-21

> **Progress 2026-11-21:** `payments/tests.py` was rewritten for the D-01 architecture and runs **38 tests**. The full suite is now **263 tests, all passing**; before, it was 226 with the payments module failing to import.
>
> Two account CSRF tests used the removed wallet top-up as their sample mutation; they now use `PATCH /api/accounts/me/`.
>
> **Closed 2026-11-21:** tests no longer write certificate PDFs into the real `media/`. The project test runner (`skillstudio/test_runner.py`) uses a temporary `MEDIA_ROOT` per run ([OPS-02](#ops-02)); a test asserts this.

*Original finding:*

**Evidence:**
- [payments/tests.py:15](payments/tests.py#L15) imports `events`, so the whole money path runs **0** tests.
- Certificate tests write PDFs into the real `media/certificates/2026/…`. Files appeared during this audit's test run.

**Fix approach:**
- Fix the import (with [PAY-02](#pay-02)) and rewrite the payment tests around the new services.
- Use `@override_settings(MEDIA_ROOT=tempfile.mkdtemp())` in a shared base `TestCase` (or `STORAGES['default']` = `InMemoryStorage`, available since Django 4.2) for all tests.

<a id="test-02"></a>
### TEST-02: No tests cover the frontend↔API contract — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **Static contract** (`core/tests.py`): every template `apiRequest`/`fetch` URL must resolve to a route, and the view must handle the HTTP method used. `TemplateGlobalsTests` guards [FE-01](#fe-01).
> - **Browser smoke suite** (`core/test_browser_smoke.py`, headless Chromium via Playwright, tag `browser`):
>   - It renders the public, student and instructor pages, about 30 in total.
>   - It runs the **enroll → learn → mark complete** flow and the **instructor deletes a lesson** flow.
>   - It fails on JS exceptions, `console.error`, any `/api/` response ≥ 400, or **raw HTML markup visible as text**.
>   - It's offline: Tailwind, fonts and the YouTube/Vimeo scripts are stubbed locally.
>   - It uses a single-threaded live server, because the in-memory SQLite test DB is one shared connection.
>   - It's skipped automatically unless `requirements-dev.txt` (Playwright 1.49.1) and Chromium are installed. Run with `manage.py test --tag browser`, or skip with `--exclude-tag browser`.
> - **Bugs the browser suite found and fixed.** The earlier XSS pass had escaped HTML that the pages build themselves, so it showed up as literal markup:
>   - **Every alert toast** showed its SVG icon as raw markup (`components/alert.html`).
>   - The course-content page's **lesson list** (so the delete buttons didn't exist) and lesson icons.
>   - The **enrollments** page's cards.
>   - The course-preview page's lesson icons.
>   - The lesson editor's **quiz options**.
>
>   Each inner render function was checked to escape its own data before the outer escape was removed.
> - **Still open (not blocking):** response-*shape* checks need the OpenAPI schema ([API-04](#api-04)).

*Original finding:*

**Evidence:** [API-01](#api-01), [API-02](#api-02), [API-03](#api-03), [LRN-01](#lrn-01) and [FE-01](#fe-01) all exist because nothing checks that templates call real routes or that pages parse.

**Fix approach:**
1. Add a Django test that walks `templates/**/*.html`, extracts `apiRequest(...)` / `fetch(...)` URLs and HTTP methods, and asserts each one `resolve()`s to a view that allows that method. The extractor used for this audit can be adapted.
2. Add a small Playwright smoke suite (login → course → enroll → learn → complete → certificate; instructor create → submit; exam take) that fails on any console error.

<a id="ops-05"></a>
### OPS-05: Tests and scratch scripts run against the hosted database by default — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **Tests can't reach `.env`'s database.** `manage.py test` now ignores `DATABASE_URL`: tests use `TEST_DATABASE_URL` if you set it, otherwise SQLite (in memory). Verified: with `.env` still pointing at the hosted Neon database, a plain `manage.py test` runs on SQLite.
> - **Remote test databases are refused.** The project test runner refuses a non-local test database host unless `ALLOW_REMOTE_TEST_DATABASE=1`, and refuses *before* any connection. Verified with a fake remote host.
> - **Scratch scripts deleted:** `scripts/run_enrollment_test.py`, `scripts/run_insufficient_test.py`, `scripts/check_profile_columns.py` and `enrollments/verify_app.py`. They wrote to whatever database was configured (including deleting wallets). Their behaviour is covered by the payments/enrollment tests.
> - **Missing `DATABASE_URL`.** An unset `DATABASE_URL` now falls back to a local `db.sqlite3` instead of crashing at startup.
> - **Still your call:** your own local `.env` still points the *dev server* at the hosted database. Point it at a local database (as in `.env.example`) if you don't want local experiments touching it.

**Evidence:**
- `settings.py` calls `load_dotenv('.env')`, and the tracked `.env` sets `DATABASE_URL` to the hosted Neon Postgres. A plain `python manage.py test` therefore creates and drops a `test_…` database **on the hosted cluster**.
- Worse, `scripts/run_enrollment_test.py` and `scripts/run_insufficient_test.py` call `django.setup()` against that same DB and write real rows: users, courses, payments, and `Wallet.objects.filter(user=student).delete()`.
- This audit only ran tests safely by overriding `DATABASE_URL=sqlite:///…` by hand.

> *Partial progress 2026-11-21:* `.env.example` now defaults `DATABASE_URL` to local SQLite for new clones (done with [SEC-03](#sec-03)). Your own local `.env` still points at the hosted DB, and the items below are still open.

**Fix approach:**
- Delete the two scripts, or turn them into `TestCase`s ([REPO-01](#repo-01)).
- Add `skillstudio/settings_test.py` (or a `pytest.ini` / `DJANGO_SETTINGS_MODULE` override) that forces a local SQLite/Postgres test DB.
- Make `.env.example` default to a local DB.
- Optionally refuse to run `test` when the DB host isn't `localhost`/CI.

---

## 6. P2: Medium

<a id="adm-01"></a>
### ADM-01: Django admin actions and fields bypass the domain logic

**Evidence:**
- `EnrollmentAdmin.mark_as_completed` ([enrollments/admin.py:163](enrollments/admin.py#L163)) and `LessonProgressAdmin.mark_as_completed` ([:301](enrollments/admin.py#L301)) use `queryset.update(...)`. That skips `evaluate_and_complete_enrollment`, so admin-completed enrollments **never get a certificate**, and lesson completion never re-evaluates the course.
- `CourseAdmin.archive_courses` archives courses in **any** status (including drafts) with `update()`, outside the lifecycle in [CRS-03](#crs-03).
- `WalletAdmin` leaves `balance` editable, so a typo silently changes a balance with no `WalletTransaction` row. The ledger and balance then disagree permanently.
- `PaymentAdmin` leaves `status` and `amount` editable. Flipping a payment to `completed` grants nothing ([PAY-05](#pay-05)) but counts toward payouts ([PAY-07](#pay-07)).

**Fix approach:**
- Make admin actions loop and call the service functions (`evaluate_and_complete_enrollment`, `transition(course, …)`).
- Make `Wallet.balance`, `Payment.status` and `Payment.amount` read-only in admin.
- Add explicit admin actions ("Credit wallet…", "Mark payment captured…") that go through the ledger/fulfilment services and record the acting admin.

<a id="sec-09"></a>
### SEC-09: Gateway secrets and payout bank details stored in plaintext

**Evidence:**
- `payments.PaymentGatewayConfig` has `secret_key` and `webhook_secret` as plain `CharField`s, fully visible and editable in Django admin. No code reads this model; real secrets should come from env vars.
- `InstructorPayout.payment_details` (bank or account details) is a plaintext `JSONField` echoed back by `InstructorPayoutSerializer`, and so is `payments.Payout.account_details`.

**Fix approach:**
- Delete `PaymentGatewayConfig` (with a migration) and read gateway keys from environment variables only.
- Store payout destinations as provider tokens (e.g. Stripe Connect account id) instead of raw bank data. If raw data is unavoidable, encrypt the field (`django-fernet-fields` / KMS) and return only a masked summary.

<a id="exm-03"></a>
### EXM-03: Exam grading and marks integrity

**Evidence:** [exams/services.py](exams/services.py), [exams/views.py](exams/views.py)
- **No snapshot.** `calculate_exam_attempt_score` grades against the *live* `exam.questions` and `custom_questions`. Unlike quizzes ([ASM-01](#asm-01) snapshots), an instructor can edit or remove questions or change correct options on a published exam while attempts are in progress. `ExamDetailView` allows `PUT`/`PATCH` on published exams that have attempts.
- **Disconnected marks.** `Exam.total_marks` (default 100) and `passing_marks` (default 50) are free inputs, never validated against the real sum of question marks. `passed = score >= passing_marks` compares *raw* earned marks, so an exam whose questions total 10 marks with the default `passing_marks=50` is **impossible to pass**.
- **Publish bypass.** `status` is writable through `ExamSerializer` on create/update, bypassing `publish_exam`'s "has questions" check.
- **Submit races.** `submit_exam_attempt` isn't atomic or row-locked, so a double submit races `create_exam_result`.
- **Late submissions lose everything.** A submit after expiry discards every answer and marks the attempt `abandoned` (it still counts toward `max_attempts`). There is no server-side autosave.

**Fix approach:**
- Snapshot questions on the attempt at start, as quizzes do.
- Lock exams with attempts against question edits (require a new version).
- Derive `total_marks` from the questions and validate `0 < passing_marks <= total_marks`, or switch to a passing *percentage*.
- Make `status` read-only (use the publish/archive endpoints).
- Wrap submit in `transaction.atomic()` + `select_for_update()`.
- Add an answer-save endpoint so expiry auto-grades saved answers instead of discarding them.

<a id="stu-02"></a>
### STU-02: Dashboard numbers are wrong or never populated

**Evidence:** [students/services.py](students/services.py), [students/models.py](students/models.py), [instructors/models.py](instructors/models.py)
- `get_student_dashboard_data` counts **all** completed `LessonProgress` (including free lessons) over a total that **excludes** free lessons, so progress can exceed 100%. It also disagrees with `get_lesson_completion_stats`.
- `get_learning_streak` builds streaks from each progress row's *last* `updated_at`. Older activity days are overwritten, so streaks under-count.
- The current streak is 0 unless the student was active *today*, even if they studied yesterday. Days are UTC, not the user's timezone.
- `has_certificate` mirrors `enrollment.is_completed`, not whether a `Certificate` exists.
- `StudentProfile.total_*` and `InstructorProfile.total_courses/total_students/total_revenue` are exposed by the profile APIs, but `update_statistics()` is never called anywhere, so they always read 0.
- `InstructorProfile.is_verified` is returned but gates nothing (see [SEC-07](#sec-07)).

**Fix approach:**
- Reuse `get_lesson_completion_stats` in the dashboard.
- Add a small `LearningActivity(user, date)` table, upserted on every progress event, and compute streaks from it in the user's timezone, counting "yesterday" as unbroken.
- Use `Certificate.objects.filter(...).exists()` for `has_certificate`.
- Either compute the profile totals on read (annotations) and drop the columns, or update them from the enrollment/payment services.

---

<a id="crs-02"></a>
### CRS-02: Ownership failures return 400 instead of 403; admins can't moderate content

**Evidence:**
- Course, module and lesson update/delete views raise `ValidationError("You don't have permission…")`, which is HTTP 400 ([courses/views.py:193](courses/views.py#L193) and around 12 other places).
- Their checks are `course.instructor != request.user`, so platform admins can't edit or delete content, contradicting `policies.can_manage_course`.

**Fix approach:** Replace them with `if not can_manage_course(user, course): raise PermissionDenied`. Put the shared check in one mixin (`CourseOwnedObjectMixin.get_object`).

<a id="crs-03"></a>
### CRS-03: Course lifecycle and editability rules contradict each other

**Evidence:**
- Create and update are allowed in `draft` **and** `under_review`, but delete is allowed only in `draft`.
- `CanEditCourse` and `Course.is_editable()` disagree.
- Content edited while `under_review` is published without being re-reviewed.
- A published course can't be edited at all, and there is no unpublish or archive endpoint (the `archived` status is unreachable through the API).
- `CourseVersion` exists but is unused.

**Fix approach:** Write the state machine down once:

`draft → under_review → (published | draft)`, `published → archived`, and `published → draft` (via "new version").

Rules:
- Edits are allowed only in `draft`. Editing an `under_review` course moves it back to `draft`.
- Published edits happen on a copy, which is where `CourseVersion` comes in.

Encode it in `courses/services.py` (`transition(course, to_state, actor)`) and make every view call it.

<a id="crs-04"></a>
### CRS-04: Category creation is broken (slug never generated)

**Evidence:**
- `CategorySerializer` marks `slug` read-only ([courses/serializers.py:20](courses/serializers.py#L20)), and `Category` has no auto-slug.
- So `POST /api/courses/categories/create/` stores `slug=''`, and the second category raises `IntegrityError` (500).
- `get_course_count` also runs one query per category.

**Fix approach:** Add a `Category.save()` that slugifies `name` (with uniqueness handling like `Course.save`), and annotate `course_count` in the queryset.

<a id="crs-05"></a>
### CRS-05: Course price, free flag and tags aren't validated

**Evidence:** `CourseCreateUpdateSerializer`:
- Allows negative `price`.
- Allows `is_free=False` with `price=0`, which creates a "paid" course that costs 0 and skips payment because of `price > 0`.
- Passes invalid `tag_ids` through to an FK `IntegrityError` (500).

**Fix approach:** Validate `price >= 0`. Enforce `is_free ⇔ price == 0` with a serializer check and a DB `CheckConstraint`. Validate `tag_ids` against `Tag.objects.filter(id__in=…)`, and use `bulk_create`.

<a id="crs-06"></a>
### CRS-06: Public course endpoints expose instructor emails

**Evidence:** `CourseListSerializer` and `CourseDetailSerializer` include `instructor_email` (and the detail view includes `rejection_reason`) on `AllowAny` endpoints ([courses/serializers.py:225](courses/serializers.py#L225)). The instructor dashboard also lists `student_email`s, which is acceptable for owners, but check it against your privacy policy.

**Fix approach:** Drop `instructor_email` from public serializers, and expose `instructor_id` plus the display name instead. Only include `rejection_reason` for the owner or an admin.

<a id="crs-07"></a>
### CRS-07: Fake or stub features in the course API

**Evidence:**
- `?ordering=rating` silently sorts by `created_at` (reviews were removed).
- `learning_outcomes` always returns `[]`.
- `?limit=3` (used by [home.html](templates/home.html) and the instructor dashboard) is ignored by `PageNumberPagination`, so 20 items come back.
- The lesson `content_type` choices `assignment` and `resource` exist in the model and editor, but there is no submission model, grading, or student rendering for them.

**Fix approach:**
- Remove `rating` from the UI, or return 400 for it.
- Remove `learning_outcomes`, or add the model field.
- Remove `assignment`/`resource` from `CONTENT_CHOICES` (data-migrate existing rows to `text`) until those features are built.
- Switch to a pagination class with `page_size_query_param='page_size'` and `max_page_size`, then update the templates to send `page_size=3`.

<a id="enr-01"></a>
### ENR-01: `was_reactivated` is always `true` — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21** with [PAY-01](#pay-01). The enroll response carries `outcome` (`created`/`reactivated`/`already_enrolled`), a truthful `was_reactivated`, `charged_amount` and `payment_id`. It returns 201 only when a new enrollment was created. The course page shows a matching message.

*Original finding:*

**Evidence:** [enrollments/views.py:92](enrollments/views.py#L92) runs the `exists()` check *after* `serializer.save()`, so the row always exists.

**Fix approach:** Have the purchase service from [PAY-01](#pay-01) return `(enrollment, outcome)`, where `outcome ∈ {'created','reactivated','already_enrolled'}`. Respond with 201 for created and 200 otherwise.

<a id="enr-02"></a>
### ENR-02: Serializer fields silently dropped (`thumbnail_url`, `get_full_name`)

**Evidence (✔ verified):**
- `Course.thumbnail_url` doesn't exist, and the custom `User` has no `get_full_name`.
- DRF silently skips read-only fields whose source raises `AttributeError`, so these keys **never appear** in responses:
  - `course_thumbnail` and `instructor_name` in `EnrollmentListSerializer` ([enrollments/serializers.py:64-65](enrollments/serializers.py#L64))
  - `created_by_name` (×2) and `user_name` in the exams serializers ([exams/serializers.py:37](exams/serializers.py#L37))

**Fix approach:**
- Add `User.get_full_name()` returning `profile.full_name or email`.
- Change the source to `course.thumbnail`.
- Add a serializer test asserting that these keys are present.

<a id="enr-03"></a>
### ENR-03: Three different lesson-unlock algorithms — 🟡 LOCKING UNIFIED 2026-11-21

> **Progress 2026-11-21 (with [LRN-01](#lrn-01)):** the content endpoint and the curriculum now share `lesson_lock_state` / `ordered_course_lessons`. **Still open:** the two "next lesson" helpers (`courses/progression.get_next_lesson`, `enrollments.services.get_next_lesson`) and the course-detail `is_locked` flag (enrollment-based, not progression-based) should be moved onto the same helpers. A `UniqueConstraint(module, position)` is also still missing.

*Original finding:*

**Evidence:**
- `LessonDetailView` counts **free** lessons as required predecessors and compares `module__position` (so ties break across modules).
- `CourseCurriculumView` skips free lessons.
- `courses/progression.get_next_lesson` and `enrollments/services.get_next_lesson` are two more variants.

The UI can show a lesson as unlocked that the server then refuses.

**Fix approach:** Write one `enrollments.services.lesson_lock_state(enrollment)` that returns `{lesson_id: locked}` using `(module.position, module.id, lesson.position, lesson.id)` ordering, and use it in curriculum, lesson detail and resume. Delete `courses/progression.py`, and add `UniqueConstraint(module, position)`.

<a id="err-01"></a>
### ERR-01: Broad `except Exception` leaks internals and hides bugs

**Evidence:**
- `payments/views.py` (around 10 times), `payments/webhooks.py` and `enrollments/serializers.py:263` all do `except Exception as e: return {'error': str(e)}` → 400.
- Real bugs such as [PAY-02](#pay-02)'s `TypeError` are reported as client errors containing Python messages.

**Fix approach:**
- Catch only domain errors (`django.core.exceptions.ValidationError`, a custom `DomainError`) and map them to 400.
- Let everything else propagate to DRF's handler as a logged 500.
- Add a custom `EXCEPTION_HANDLER` that turns Django `ValidationError` into a DRF 400 with a stable shape ([API-04](#api-04)).

<a id="stu-01"></a>
### STU-01: Bookmarks leak unpublished content; instructors can't see their wallet

**Evidence:**
- `create_bookmark` accepts any course or lesson id, and the response includes `course_title` / `lesson_title`, so draft course titles are enumerable.
- Instructors are credited into `Wallet` ([PAY-07](#pay-07)), but `WalletView` is `IsStudent`-only.
- `StudentDashboardView(APIView, StudentOnlyMixin)` has the MRO backwards, so the mixin's `initial` never runs (harmless only because `IsStudent` is also set).

**Fix approach:** Check `can_view_course_catalog` in `create_bookmark`. Let a wallet's owner of any role read it, or move instructor earnings out of `Wallet` ([PAY-07](#pay-07)). Remove the unused mixins.

<a id="exm-02"></a>
### EXM-02: Exam settings that do nothing; analytics disagree with grading

**Evidence:**
- `randomize_questions` and `show_correct_answers` are stored and editable but never read by any service or serializer.
- `get_exam_analytics` ([exams/services.py:312](exams/services.py#L312)) matches answers by option **text**, while grading (`_answer_matches_options`) matches by **index** first. Analytics under-reports correct answers.
- `timezone.utc` ([exams/serializers.py:115](exams/serializers.py#L115)) was removed in Django 5.0, so this crashes if reached. It's currently unreachable because DRF already makes datetimes aware.
- Instructors can attach other instructors' question-bank items to an exam (no course check on `questions`).

**Fix approach:**
- Implement or remove the two flags (shuffle per attempt with a seed stored on the attempt; strip `question_results[*].correct_option` unless `show_correct_answers`).
- Reuse `_answer_matches_options` in analytics.
- Replace the `timezone.utc` calls with `datetime.timezone.utc`, or delete the validators.
- Validate `questions` belong to `course`.

<a id="crt-01"></a>
### CRT-01: Certificate admin, verification and rendering issues

**Evidence:**
- `regenerate_certificate` ([certificates/views.py:135-143](certificates/views.py#L135)) picks the latest certificate for a **course** (any user), and checks `is_staff` instead of `is_platform_admin`.
- `verification_url` ([certificates/models.py:97](certificates/models.py#L97)) points the QR code at a JSON API, not a human page.
- `FRONTEND_URL` defaults to a non-existent `localhost:3000`.
- PDF rendering runs synchronously in `on_commit`, inside the request.
- Certificates aren't revoked on refund or cancel.
- The model has two UUIDs (`id`, `certificate_id`), which invites frontend mix-ups.
- The QR URL is built from `BACKEND_URL`, which defaults to `http://localhost:8000`. If that env var isn't set in production, every PDF permanently embeds a localhost link.
- `calculate_course_grade` only uses quiz attempts. **Exams never affect the grade, completion or certificate**, so the exam engine is disconnected from the course outcome.
- [certificates/pdf.py](certificates/pdf.py) uses built-in Helvetica (non-Latin names render as empty boxes) and `drawCentredString` with no wrapping, so long course titles run off the page.
- `increment_download_count` is a read-modify-write race.

**Fix approach:**
- Fail at startup if `BACKEND_URL` is unset or points to localhost when `DEBUG=False`.
- Decide whether passing a course's exams is a completion requirement. If so, add it to `evaluate_and_complete_enrollment` and include the exam percentage in the grade.
- Embed a Unicode TTF (e.g. Noto Sans) and wrap or shrink-fit titles.
- Use `F('download_count') + 1`.
- Route regeneration by certificate id with `IsAdmin`.
- Add a public `/certificates/verify/<code>/` HTML page and point the QR code there.
- Render via a Celery task ([OPS-04](#ops-04)).
- Add `Certificate.revoked_at`, set it in refund fulfilment, and show it on the verify page.
- Expose a single public id.

<a id="acc-01"></a>
### ACC-01: Account-management inconsistencies

**Evidence:**
- `LogoutView` requires `IsAuthenticated` ([accounts/views.py:55](accounts/views.py#L55)), but its docstring says "succeeds even without a token". With expired cookies, logout 401s and never clears them.
- Demoting an admin to student leaves `is_staff=True` (Django-admin access remains). Demoting a superuser is silently reverted, but the response says "updated".
- `MeSerializer` lets a user PATCH their own `is_active`.
- API key `scopes` are stored but never enforced.

**Fix approach:**
- Use `AllowAny` on logout.
- In `normalize_role_flags`, clear `is_staff` for non-admin roles, and reject demoting a superuser with 400.
- Make `is_active` read-only in `MeSerializer`.
- Either enforce scopes in a `HasAPIKeyScope` permission or remove the field.

<a id="perf-01"></a>
### PERF-01: N+1 queries and unpaginated list endpoints

**Evidence:**
- `CourseListSerializer`: 3 queries per course (enrollment count, module count, lesson count).
- `CourseDetailView` prefetches **all** enrollments of the course.
- `EnrollmentListSerializer` calls `get_lesson_completion_stats` 3 times per row, plus a count.
- `EnrollmentStatsView`, `LearningProgressDashboardView` and `InstructorStudentsView` loop with per-row queries.
- `CourseDetailLessonSerializer.get_is_locked` queries per lesson.
- `PaymentListView`, `RefundListView` and `InstructorStudentsView` return unpaginated lists.

**Fix approach:**
- Annotate counts in querysets (`Count(..., distinct=True, filter=Q(...))`).
- Compute enrollment stats once per row (`to_representation` cache or a single aggregate query).
- Pass `is_enrolled` in serializer context instead of querying per lesson.
- Paginate all list endpoints.
- Add `assertNumQueries` budget tests for course list, enrollment list and dashboards.

<a id="api-04"></a>
### API-04: No API contract: inconsistent error and pagination shapes — 🟡 DUPLICATE ROUTE NAMES FIXED 2026-11-21

> *Progress 2026-11-21:* the duplicate URL names are gone: `category-list` was removed by the [API-02](#api-02) merge, `instructor-dashboard` was renamed, and `logout` only clashes with the namespaced `admin:logout`. **Still open:** OpenAPI schema, one error envelope, consistent pagination.

*Original finding:*

**Evidence:**
- Errors come back as `{"error": …}`, `{"detail": …}`, `{"errors": [...]}` and field dicts.
- Some list endpoints are paginated (`{count, results}`) and others return bare arrays, so templates guess (`data.results || data`).
- There are duplicate URL names (`logout`, `category-list`, `instructor-dashboard`), and `InstructorDashboardView` is mounted at 3 URLs.
- There is no OpenAPI schema.

**Fix approach:**
- Add `drf-spectacular` and publish `/api/schema/`.
- Standardise on one error envelope (`{"detail": str, "code": str, "fields": {…}}`) via a custom exception handler.
- Paginate every list.
- Remove the duplicate names and aliases.
- Have CI diff the schema on PRs.

<a id="ops-04"></a>
### OPS-04: No throttling, logging, health check or real background jobs — re-scoped by D-03

> *Re-scoped 2026-11-21 ([D-03](#d-03)):* the deploy-only items (Procfile/deploy manifest, `/healthz` and `/readyz`, `check --deploy` in CI) no longer apply. **Still useful locally:** auth throttling, a `LOGGING` config (and replacing the stray `print`), CI running the test suite plus `pip-audit`/`gitleaks` (secret scanning already exists), and the Celery decision.

*Original finding:*

**Evidence:**
- No `DEFAULT_THROTTLE_*`, so login, register, enroll and payment endpoints can be brute-forced or spammed.
- No `LOGGING` config, plus a stray `print()` in [instructors/views.py:45](instructors/views.py#L45).
- No health or readiness endpoint, and no CI at all.
- Celery and Redis are configured, but **zero tasks exist** (`grep shared_task` → nothing).
- `CELERY_BEAT_SCHEDULE` still says "run recommender hourly".
- A missing `DATABASE_URL` crashes with an obscure `dj_database_url` error.
- There is no deploy manifest (Procfile / `railway.json`).

**Fix approach:**
1. Add DRF throttles: a `ScopedRateThrottle` for `login` (5/min), `register`, `enroll` and `payments`.
2. Add `LOGGING` with JSON output to stdout and replace the `print`.
3. Add `/healthz` (process up) and `/readyz` (DB reachable).
4. Add GitHub Actions running `check`, `check --deploy`, `makemigrations --check`, the full test suite on Postgres, `pip-audit` and `gitleaks`.
5. Either move certificate rendering and payment fulfilment into Celery tasks, or remove Celery, Redis and daphne until they're needed ([DEP-01](#dep-01)).
6. Fail fast with a clear message when `DATABASE_URL` is unset.
7. Commit a Procfile: `web: gunicorn skillstudio.wsgi`, `release: python manage.py migrate`.

<a id="sec-08"></a>
### SEC-08: Frontend hardening: CSP, CDN Tailwind, inline handlers, cookie scope

**Evidence:**
- No Content-Security-Policy.
- Tailwind's runtime JIT is loaded from `cdn.tailwindcss.com` ([base.html:11](templates/base.html#L11)) without SRI. It's not meant for production, and a compromised CDN means full XSS.
- Inline `onclick="fn('${escapeHtml(id)}')"` handlers remain (e.g. [payments/history.html:235](templates/payments/history.html#L235), [certificates/list.html:163](templates/certificates/list.html#L163)). They're safe for UUID/int ids but block a strict CSP.
- 130 `innerHTML` sinks rely on manual `escapeHtml`.

**Fix approach:**
- Build Tailwind with the CLI into `static/css/app.css` (purged, hashed by [OPS-01](#ops-01)).
- Move the shared JS into `static/js/`.
- Replace inline handlers with `addEventListener` and `data-` attributes.
- Add a CSP via `django-csp` (`script-src 'self'`).
- Over time, prefer `textContent` / DOM building over `innerHTML`.

<a id="fe-02"></a>
### FE-02: Role-based navbar never works; debug logs and stale routes

**Evidence:**
- [components/navbar.html:74](templates/components/navbar.html#L74) reads `localStorage.user_role`, which nothing ever sets (login stores `user`). Role-specific nav items never render correctly.
- There are 29 `console.log` / `console.debug` calls in templates.
- `templates/profile/profile.html` is not rendered by any view.
- `/recommendations/` still routes to the removed AI recommender ([core/urls.py:52](core/urls.py#L52)).
- Three `path()` calls are on one line in [core/urls.py:46](core/urls.py#L46).
- Instructor page shells are reachable by students (the API still enforces access, so this only matters for UX).
- 26 native `alert()` / `confirm()` dialogs are used instead of the shared `components/alert.html` system.

**Fix approach:**
- Read the role from the stored `user` object, or better, render it server-side: page views can decode the access cookie and pass `role` into the template context.
- Strip the `console.*` calls (or gate them behind a debug flag).
- Delete the orphan template and the stale route.
- Add a `role_required` page decorator for instructor shells.

<a id="asm-03"></a>
### ASM-03: Quiz editing ignores course lock; error points to a non-existent feature

**Evidence:**
- `ManageQuizView` lets the owner create a quiz or change `passing_percentage` / `time_limit` on a **published** course, unlike every other content endpoint.
- Its 409 says "Create a new quiz version instead", but versioning doesn't exist.
- Admins are excluded (owner-only check).

**Fix approach:** Apply the same editability rule as [CRS-03](#crs-03) through the shared mixin from [CRS-02](#crs-02), and reword the 409 to describe what the instructor can actually do.

<a id="ins-01"></a>
### INS-01: Instructor dashboard swallows errors and returns fake zeros

**Evidence:** [instructors/views.py:37-55](instructors/views.py#L37) catches every exception, `print`s a traceback, and returns `200` with zero revenue and empty lists. Real failures look like "no data".

**Fix approach:** Remove the try/except and let errors 500 and get logged. Fix the data source mismatch from [PAY-07](#pay-07), and collapse the three duplicate count queries into one aggregate.

---

## 7. P3: Low

<a id="repo-01"></a>
### REPO-01: 5,965 vendored `venv` files, `.pyc`, and scratch scripts tracked in git — 🟡 PARTIALLY DONE 2026-11-21

> **Progress 2026-11-21:** `venv/` (5,965 files) and all 136 tracked `*.pyc` were removed from the whole git history as part of the [SEC-03](#sec-03) scrub. The local `venv/` folder and `.pyc` files are still on disk, ignored. A pre-commit hook now blocks `.env*`. **Still open:**
> - Delete the scratch scripts (`scripts/run_*.py`, `scripts/check_profile_columns.py`, `enrollments/verify_app.py`; see [OPS-05](#ops-05)).
> - Extend the pre-commit hook to block `venv/` and `*.pyc`.

*Original finding:*

**Evidence:**
- `git ls-files | cut -d/ -f1 | sort | uniq -c` shows **5,965** tracked files under `venv/` (a Windows virtualenv), plus `__pycache__/*.pyc` in every app.
- One-off scripts are tracked: `scripts/run_enrollment_test.py`, `scripts/run_insufficient_test.py`, `scripts/check_profile_columns.py` and `enrollments/verify_app.py`.

**Fix approach:**
- `git rm -r --cached venv '**/__pycache__'` (the ignore rules already exist).
- Delete the scratch scripts, or convert them into tests or management commands.
- Add a pre-commit hook that blocks `venv/`, `.env` and `*.pyc`.

<a id="repo-02"></a>
### REPO-02: Dead code and stale comments

**Evidence:**
- `assessments/views_attempt.SubmitQuizAttemptView` (not routed).
- `courses/views_analytics.py`'s docstring refers to a removed `analytics` app.
- `CourseVersion` and `CourseVersionSerializer` are unused.
- There is commented-out event, recommender and dropoff code across payments, instructors, enrollments and settings.
- `Course.clean()` and `Lesson.clean()/save()` are no-ops with misleading comments.
- `accounts/utils.normalize_role_flags` duplicates `User.normalize_role_flags`.
- `MeView.get` swallows exceptions around `refresh_from_db` with a stale "latest wallet" comment.
- `core/templatetags/core_extras.get_item` is never used by any template.
- `instructors.services.get_lesson_dropoff` is imported but never called.
- `PaymentGatewayConfig` is never read by any code ([SEC-09](#sec-09)).

**Fix approach:** Delete the dead code in one cleanup PR after the P0/P1 work. Git history keeps it.

<a id="repo-03"></a>
### REPO-03: Migration churn in `accounts`

**Evidence:** `accounts/migrations` has two `0002_*` files plus a merge (`0003`), and a wallet field that is added, removed, added and removed again (`0002`, `0004`, `0005`, `0009`).

Several data migrations are **destructive and irreversible** (`reverse = noop`):
- `core/0001` and `core/0002` run `DROP TABLE` on the removed live/social feature tables.
- `assessments/0004` and `exams/0003` delete every non-MCQ question.

**Fix approach:**
- Once every environment has migrated past `0009`, squash with `squashmigrations accounts 0001 0009` to speed up test DB creation and remove the confusion.
- Document in the deploy runbook that a DB snapshot is mandatory before applying migrations, and add a `--plan` review step in CI for any migration containing `RunSQL`/`RunPython` deletes.

<a id="doc-01"></a>
### DOC-01: README advertises features that don't exist and has no setup guide

**Evidence:**
- [README.md](README.md) lists an AI recommender, badges, streak calendar, content versioning, password reset, an admin panel, fraud detection and more. Several were removed, and others were never built.
- It still says "your original text, unchanged — only formatted".
- There are no install, env, run or test instructions, and no `.env.example`.

**Fix approach:** Rewrite the README with:
- what exists today
- an architecture diagram (apps → responsibilities)
- local setup (venv, `.env.example`, `migrate`, `create_categories`, `runserver`)
- how to run tests
- deploy notes
- a link to this audit

Move aspirational features to a "Roadmap" section.

<a id="doc-02"></a>
### DOC-02: App READMEs document a different API

**Evidence:** There are about 5,200 lines of per-app docs.
- `courses/README.md` documents `/api/v1/courses/...`, slug-based update/delete, and `submit-review/` / `unpublish/` endpoints, none of which exist.
- `accounts/README.md` documents email verification and password-reset tokens, which were removed on purpose.
- `payments/README.md` describes event payments.

**Fix approach:** Once the OpenAPI schema ([API-04](#api-04)) exists, delete the hand-written endpoint lists and keep a short domain/invariants README per app that links to `/api/schema/`.

<a id="dep-01"></a>
### DEP-01: Dependencies installed but unused; no lock file — 🟡 PARTIAL 2026-11-21

> *Progress 2026-11-21:* the unused or deploy-only `gunicorn` and `daphne` were removed ([D-03](#d-03)). **Still open:** Celery, Redis and kombu (no tasks exist), and hash-locked requirements.

*Original finding:*

**Evidence:**
- `daphne` is installed and `ASGI_APPLICATION` is set, but `daphne` isn't in `INSTALLED_APPS` and nothing is async.
- `celery`, `redis` and `kombu` have no tasks.
- `requirements.txt` is pinned but not hash-locked *(carried over)*.
- There are no dev/test extras (coverage, Playwright, linters).

**Fix approach:**
- Remove unused packages, or adopt them deliberately per [OPS-04](#ops-04).
- Move to `uv` / `pip-tools` with `requirements.in` → hashed `requirements.txt`, and a separate `requirements-dev.txt`.

<a id="asm-04"></a>
### ASM-04: Assessment model and analytics gaps

**Evidence:** [assessments/models.py](assessments/models.py), [assessments/analytics.py](assessments/analytics.py)
- `Quiz` has no timestamps and no `__str__`.
- `QuizQuestion.difficulty` is free text with no choices, so analytics by difficulty can't be trusted.
- `Quiz.is_published` defaults to `True`, so a half-written quiz is live immediately (and combined with [ASM-01](#asm-01) it changes completion rules mid-course).
- `Quiz.total_marks` is a stored copy recomputed only by `ManageQuizView`, so it drifts if questions are edited in admin.
- `get_course_assessment_overview` and `get_quiz_question_analytics` include **in-progress** attempts (null `score`), which skews averages and pass rates.
- Both analytics views are owner-only (admins excluded).

**Fix approach:**
- Add `created_at`/`updated_at`, use `TextChoices` for difficulty, and default `is_published=False`.
- Compute `total_marks` with an annotation (or a `post_save` on questions).
- Filter analytics to `completed_at__isnull=False`.
- Use `can_manage_course` for analytics access.

---

## 8. What is in good shape

- **Domain layering.** `services.py` / `policies.py` / `serializers.py` per app is a sound structure; most fixes above are about routing work *through* it consistently.
- **Custom `User`.** DB `CheckConstraint`s on role/staff/superuser invariants, plus role normalisation on save.
- **API keys.** SHA-256 hashed secrets, a prefix index, and `hmac.compare_digest`.
- **Cookie JWT + CSRF.** httpOnly cookies, CSRF enforced only on cookie-authenticated unsafe methods, and refresh rotation with blacklist. ([SEC-06](#sec-06) is the remaining gap.)
- **Wallet ledger.** `Wallet._apply_delta` row-locks and always writes a `WalletTransaction`. The *model* is right; the problem is who is allowed to call it ([SEC-01](#sec-01), [PAY-07](#pay-07)).
- **Assessments integrity.** Attempt question snapshots, frozen grading evidence, `select_for_update` on answers, and no `is_correct` leakage in student serializers.
- **Exams.** Student serializers strip answer keys recursively, and attempt numbering is constrained in the DB.
- **Watch-time anti-cheat.** Server-side delta caps tied to elapsed time ([LRN-02](#lrn-02) only needs the client side).
- **XSS hygiene.** API data is consistently passed through `escapeHtml` / `safeUrl` (387 + 8 call sites).

---

## 9. Recommended implementation plan

| Phase | Goal | Items | Rough size |
|---|---|---|---|
| **0: Stop the bleeding** | Close money and security holes; nothing new built | SEC-01 🟡, ~~PAY-01~~ ✅, ~~SEC-02~~ ✅, SEC-03 🟡, ~~OPS-05~~ ✅, ~~FE-01~~ ✅, ~~SEC-04~~ ✅, ~~SEC-05~~ ✅, ~~BUG-01~~ ✅, ~~BUG-02~~ ✅, OPS-03; ~~put `/api/payments/*` behind a flag~~ (superseded by D-01: the card route is deleted and the webhook rejects all) | 1–2 days |
| **1: Make learning work** | A student can enroll → learn → complete → get a certificate, and keep access | ~~LRN-01~~ ✅, ~~LRN-02~~ ✅, ~~LRN-03~~ ✅, ~~ASM-01~~ ✅, ~~ASM-02~~ ✅, EXM-01, EXM-03, ~~API-02~~ ✅, ~~API-03~~ ✅, ~~CRS-01~~ ✅, ENR-03 🟡, ~~TEST-02~~ ✅ | 3–5 days |
| **2: One coherent money domain** | Single pricing, fulfilment, ledger, payout and refund path | ~~PAY-02~~ ✅ → ~~PAY-03~~ ✅ → PAY-05 🟡 → PAY-04 🟡 (Stripe top-up + verified webhook) → ~~PAY-07~~ ✅ → ~~PAY-06~~ ✅ → ~~PAY-08~~ ✅ → ~~PAY-09~~ ✅, ~~SEC-07~~ ✅, SEC-09, ADM-01, ~~TEST-01~~ ✅ | 1–2 weeks |
| **3: Frontend/API alignment** | Every page talks to a real, documented endpoint | ~~API-01 (build or remove each)~~ ✅, API-04 (OpenAPI + error envelope), ENR-01, ENR-02, CRS-06, CRS-07, FE-02, ERR-01 | 3–5 days |
| **4: Hardening** *(re-scoped by [D-03](#d-03): no deployment)* | Observable and hardened for local use | ~~OPS-01~~ ✅, ~~OPS-02~~ ✅, OPS-04 (local items), ~~SEC-06~~ ✅, SEC-08, PERF-01, CRT-01, CRS-02–05, ACC-01, STU-01, STU-02, EXM-02, ASM-03, INS-01 | 1 week |
| **5: Hygiene** | Clean repo and truthful docs | REPO-01–03, DOC-01–02, DEP-01, ASM-04 | 1–2 days |

### Definition of done for release

- The full test suite (including payments) collects and passes on Postgres in CI.
- The template→route contract test and the Playwright happy-path smoke suite pass.
- No code path credits a wallet or grants an enrollment without a verified payment.
- Reconciliation shows zero unexplained differences.
- No tracked secrets, virtualenvs, bytecode or generated files; secrets rotated.
- ~~`check --deploy` is clean, static files are hashed, media is on object storage, and~~ throttles and logging are in place. *(Deployment items dropped by [D-03](#d-03).)*
- The OpenAPI schema is published, and templates use only routes in it.
