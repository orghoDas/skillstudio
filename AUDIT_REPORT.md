# SkillStudio — Full Repository Audit

**Date:** 2026-11-21
**Scope:** Whole repository:
- Django config and all 10 apps (`accounts`, `courses`, `enrollments`, `assessments`, `exams`, `certificates`, `students`, `instructors`, `payments`, `core`).
- For every app: models, views, serializers, services, policies/permissions, URLs, admin, migrations, management commands, template tags, PDF generation and tests.
- The 42 templates (43 at the 2026-11-22 re-audit) and their inline JS, and the backend↔frontend contract.
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

**Re-audit 2026-11-22 (second pass, after the fixes at `d0ad799`):**

| Check | Command / method | Result |
|---|---|---|
| Full suite, SQLite | `manage.py test` | ✅ 498 tests OK (3 skipped: Postgres-only lock tests) |
| Full suite, Postgres 16 | Throwaway local cluster, `TEST_DATABASE_URL=postgres://…@127.0.0.1` | ✅ 498 tests OK, 0 skipped |
| System, migration, deploy checks | `check`, `makemigrations --check`, `check --deploy` | ✅ clean |
| API contract snapshots | `spectacular --validate --fail-on-warn`, `api_routes` diffed with `docs/` | ✅ identical |
| Static analysis | pyflakes / ruff `F,B`, vulture, a repo-wide reference search | ❌ about 45 unused imports, about 20 unreferenced functions/classes ([REPO-04](#repo-04)) |
| Live end-to-end in Chromium | `runserver` on a fresh migrated Postgres DB, driven by Playwright through the real UI. The run covered signup, login, course building (sections, text, video and quiz lessons), submit for review, console publish, coupon, wallet purchase, learning, quiz, certificate (PDF and public verify), notes and bookmarks, exams, refund (student request → console approval), payout (instructor request → console approve → record sent), API keys, password change and revision. Every JS error and every API ≥400 response was recorded. | ✅ The main journeys work, and the money totals reconcile after purchase, coupon, refund and payout. ❌ new findings, listed below. |
| Abuse and edge probes | Out-of-order completion, admin-API escalation, malformed parameters, deleted category, closed exam window | ❌ [LRN-04](#lrn-04), [SEC-10](#sec-10), [ERR-02](#err-02), [ADM-02](#adm-02), [EXM-04](#exm-04) |
| Route and guard matrix | Each of 36 page routes visited as anonymous, student, instructor and admin. The final URL and status were recorded. | ✅ Anonymous visitors always go to `/auth/login/?next=…`, and the login returns them to the deep link. A hostile `?next=//evil…` is ignored. Students get 403 on instructor pages. Instructors are redirected from student-only pages, receipts return 404 to non-owners, and an exam take page without an attempt goes back to `/exams/`. Logout clears both cookies, and refresh then returns 401. ❌ Inconsistencies: [FE-06](#fe-06) |
| Business-scenario suite | 59 scenario checks run through the real DRF stack (full middleware) on a fresh Postgres DB. Each one asserts DB state afterwards. Money: insufficient balance, 7 coupon rules, 100% coupon, partial → full refund → re-buy → certificate re-issue, refund after the instructor withdrew (shortfall/absorb), the payout state machine. Learning: quiz attempts used up, quiz time limit, a course of only free previews, the published-course edit lock, locked-lesson quiz, exam retry and hidden results. Accounts: deactivated and console-only users, email case, role promotion. Courses: archive/delete, cross-instructor edits, admin moderation. Ledger invariants at the end. | ✅ 55 pass. The ledger holds everywhere: balance = credits − debits, never negative, fee + earnings = amount, refunds ≤ amount, the reconcile command finds nothing. ❌ 4 real failures: [EXM-04](#exm-04) (free-preview-only course), [LRN-04](#lrn-04) (quiz on a locked lesson), [ACC-03](#acc-03) (email case), [API-05](#api-05) (error code) |
| Per-module suite | 149 table-driven checks across accounts, courses, tags/categories, modules/lessons, enrollments, wishlist, CSV, quizzes, exams, certificates, payments, students and instructors. They cover validation, cross-user access (IDOR), role permissions and computed numbers checked against the DB. | ✅ 144 pass, including every cross-user access check (other users' enrollments, notes, payments, refunds, payouts, API keys, attempts, certificates, question banks, CSV) and the dashboard, earnings and progress numbers. ❌ [EXM-04](#exm-04) (inverted exam window accepted and publishable), [PAY-10](#pay-10) (150% coupon), [STU-03](#stu-03) (duplicate bookmarks, profile PATCH before GET), and [API-05](#api-05) (unordered pagination) |
| Business-workflow transitions | Each state machine was driven through the UI and the console, and the stored state, ledger rows and landing page were checked after every step | ✅ **Course:** draft → review → returned to draft with a reason → editing under review returns it to draft → resubmit → publish revision (the original is archived, the catalogue shows only the revision, an active learner keeps the original, a refunded learner gets 403). **Enrollment:** active → completed. A full refund cancels it and revokes the certificate. Cancel → "Enroll Again" reactivates it for free and keeps progress. **Refund:** approve moves money and cancels access; reject moves nothing and shows the reason to the student. **Payout:** request reserves the amount, instructor cancel returns it, console reject returns it, and approve → record sent pays it (ledger $37 → $27 → $37, then $20 paid). **Quiz/exam:** start, answer, submit, results. ❌ [CRS-09](#crs-09) (the rejection reason is never shown), [EXM-04](#exm-04) |

**Mobile responsiveness audit 2026-11-24:**

| Check | Command / method | Result |
|---|---|---|
| Phone-width overflow on every page | Headless Chromium (Playwright) loaded 49 page states at 320, 375, 768 and 1024px. These were the 36 page routes plus the open navbar menu, user menu and sidebar drawer, a live exam attempt and the staff console. It visited them as anonymous, student, instructor, website admin and console operator, with deliberately long course titles, names and emails. Each page recorded `scrollWidth` against the viewport, the deepest elements past the edge, tap targets under 24px and form fields under 16px, plus full-page screenshots. | ❌ Before the fixes: 5 pages overflowed at 375px and 5 more at 320px, and the exam builder cut off a button ([FE-07](#fe-07), [FE-09](#fe-09)). The lesson editor's styles never loaded ([FE-08](#fe-08)). ✅ After the fixes: all 49 states fit at every width, with no JS or API errors. |
| Interactive states on phones | A second Chromium pass opened 23 interactive states at 320×568, 375×667 and landscape 667×375: the confirm and text-prompt dialogs, a long toast, the insufficient-balance modal, the add-section, add-lesson and question-bank modals, the enrollment-cancel and delete confirmations, the open menus and sidebar drawer, the expanded curriculum, settings tabs, the new API key panel, certificate sharing, exam results, the lesson editor's quiz and video modes, and the learn page with an article containing a long URL and code line. It flagged text clipped by its container or squeezed narrower than 24px, and any modal wider than the screen or with an unreachable control. | ❌ Before the fixes: lessons on the learn page got no width on phones ([FE-10](#fe-10)), and the course content editor and quiz editor clipped their rows ([FE-11](#fe-11)). ✅ After the fixes: all 69 checks pass. The dialogs, toasts and modals were already fine: they fit at every size, and tall modals scroll inside themselves. |

### Severity scale

- **P0, critical:** an exploitable security or money hole, or a core user journey that does not work at all. Fix before anything else.
- **P1, high:** a serious bug, data-integrity risk, or security weakness, or a major feature that is dead.
- **P2, medium:** inconsistency, a correctness edge case, performance at scale, or hardening.
- **P3, low:** hygiene, dead code, docs.

---

## 2. Original audit summary

The following findings describe the 2026-11-21 baseline. The status table and dated notes record subsequent remediation.

The domain layering (services, policies, serializers per app) is good, and the auth primitives are solid. However, **the platform is not usable end to end and is not safe to take money**:

1. **Money can be created from nothing.** Any student can top up their own wallet for free (`POST /api/students/wallet/`), buy any course with it, and the instructor gets credited "earnings" that can then be paid out twice.
2. **The core learning journey is broken.**
   - The learn page never receives lesson content: the only content endpoint is shadowed by another route.
   - Video lessons can never be marked complete, because the page never reports watch time.
   - A student who *does* complete a course loses access to it.
3. **About a quarter of the frontend talks to endpoints that don't exist.** Assessments, checkout, payment history, resources, and featured instructors are all dead. The four exam pages also crash on load because of a duplicate JS `const`.
4. **The payments app is still runtime-broken and insecure** *(carried over)*: event-domain drift, client-supplied amounts, unsigned webhooks, and no fulfilment.

| Severity | Count | Added by the 2026-11-22 re-audit |
|---|---|---|
| P0 | 12 | 0 |
| P1 | 28 | 4 (LRN-04, SEC-10, FE-03, EXM-04); +1 from the 2026-11-24 mobile audit (FE-10) |
| P2 | 39 | 11 (ERR-02, STU-03, CRS-08, CRS-09, PAY-10, ADM-02, LRN-05, FE-04, ACC-02, ACC-03, RPT-01); +3 from the 2026-11-24 mobile audit (FE-07, FE-08, FE-11) |
| P3 | 14 | 6 (REPO-04, DOC-03, FE-05, FE-06, API-05, TEST-03); +1 from the 2026-11-24 mobile audit (FE-09) |
| **Total** | **93** | **21** (+5 from the 2026-11-24 mobile audit) |
| *Resolved so far* | *89 (SEC-02, SEC-04, SEC-05, SEC-06, SEC-07, ASM-01, ASM-02, API-01, API-02, API-03, PAY-01, PAY-02, PAY-03, PAY-06, PAY-07, PAY-08, PAY-09, ENR-01, LRN-01, LRN-02, LRN-03, FE-01, BUG-01, BUG-02, OPS-01, OPS-02, OPS-03, CRS-01, TEST-01, OPS-05, TEST-02, EXM-01, REPO-01, REPO-02, REPO-03, DOC-01, DOC-02, DEP-01, ASM-04, ADM-01, SEC-09, EXM-03, STU-02, CRS-02, CRS-03, CRS-04, CRS-05, CRS-06, CRS-07, ENR-02, ENR-03, ERR-01, STU-01, EXM-02, CRT-01, ACC-01, PERF-01, API-04 on 2026-11-21, OPS-04, SEC-08, FE-02, ASM-03, INS-01 on 2026-11-22, and FE-03, LRN-04, SEC-10, EXM-04, ERR-02, STU-03, CRS-08, CRS-09, PAY-10, ADM-02, LRN-05, FE-04, ACC-02, ACC-03, RPT-01, REPO-04, DOC-03, FE-05, FE-06, API-05, TEST-03 on 2026-11-23, and FE-07, FE-08, FE-09, FE-10, FE-11 on 2026-11-24). Four partially resolved P0 items remain open (SEC-01, SEC-03, PAY-04, PAY-05). All P1, P2 and P3 findings are resolved.* |

### Follow-up after the 2026-11-22 re-audit

The follow-up repairs populated wishlist and webhook admin lists, locks quiz and money records to their application workflows, protects accounts with financial history, and fixes course progress, formatted articles, refund reporting, pagination, and mobile payment history. Browser controls now cover notes, bookmarks, wishlists, coupons, wallet refunds, manual payouts, payment receipts, CSV export, and API keys. Removed unsupported settings controls and placeholder links. The four open P0 entries below retain their existing scope.

### Mobile responsiveness audit and fixes 2026-11-24

A phone-width browser audit of every page found three new findings, all resolved the same day:
- [FE-07](#fe-07) (P2): five instructor and exam pages scrolled sideways on a standard 375px phone. The worst was the instructor course list, at 645px wide.
- [FE-08](#fe-08) (P2): the lesson editor's stylesheet never rendered at any width.
- [FE-09](#fe-09) (P3): five more pages overflowed on 320px phones, the exam builder cut off a button, and some phone controls were too small or made iOS zoom.

Public pages, the student dashboard, payment and certificate pages, and the staff console already fit. The learn page only appeared to fit; see [FE-10](#fe-10) below.

The fix keeps header rows, course cards and tab bars from forcing a wider page on small screens. A new browser test loads the affected pages at 320px with long titles and names, and fails if any page scrolls sideways or the lesson editor's styles are missing. With the template changes reverted, it failed on all 8 broken pages and the editor styling.

**Follow-up the same day: interactive states.** The first pass only loaded pages, so a second pass opened every modal, dialog, menu and revealed panel, and checked for clipped content as well as page overflow. It found two more issues, both resolved:
- [FE-10](#fe-10) (P1): on phones, the learn page gave the whole width to the lesson list, so students could not read lessons. The page didn't widen, so the first pass missed it.
- [FE-11](#fe-11) (P2): the course content editor's section and lesson rows, and the quiz editor's answer rows, clipped or overflowed on 320px phones.

The phone-width browser test now also checks that a lesson is readable on the learn page and that the outline opens, and it covers the course content editor and the quiz editor. With those three templates reverted, it fails at the learn page.

Verification passed with 529 SQLite tests (including 29 Chromium tests) and three PostgreSQL-only skips. The Tailwind build passed.

### P3 remediation 2026-11-23

All six P3 findings from the re-audit are resolved in code and the local virtual environment is synced. Certificate codes are retained when superseded from this release onward. Existing payout rows retain their recorded status and reason.

Verification passed with 497 SQLite tests and three PostgreSQL-only skips, 500 PostgreSQL tests, and 28 Chromium tests. Ruff, Django checks, the OpenAPI and route snapshots, and the Tailwind build passed.

### P2 remediation 2026-11-23

All 11 P2 findings from the re-audit are resolved in code. The email and coupon data migrations stop on normalization conflicts so existing data can be reconciled without discarding records. The payment migration preserves older discount history and links it when the original payment identifies the course.

Verification passed with 493 SQLite tests and three PostgreSQL-only skips, 496 PostgreSQL tests, and 27 Chromium tests. The OpenAPI snapshot, API route reference, migration checks, and Tailwind build also passed.

### P1 remediation 2026-11-23

All four P1 findings from the re-audit are resolved. Verification on isolated test databases passed with 479 SQLite tests and three PostgreSQL-only skips, 145 focused PostgreSQL tests, and 24 Chromium browser tests. The OpenAPI snapshot, API route reference and migration checks passed.

### Second re-audit 2026-11-22: full-repo pass and live E2E run after `d0ad799`

**Verdict:** The fixes hold. Both test suites pass (SQLite and Postgres), the API snapshots are current, and a browser walkthrough from an empty database works end to end:
- An instructor builds a course and submits it.
- A console operator publishes it.
- A student buys it from the wallet (with a coupon), learns it, passes the quiz and gets a verifiable PDF certificate.
- The student requests a refund and the console approves it.
- The instructor requests a payout and the console approves it and records it as sent.

Wallet and ledger totals reconcile at every step: $40 + $30 sales at a 10% fee left the instructor $63, the refund brought that to $27, and the $20 payout left $7.

A route matrix (36 pages × 4 roles) and every business state machine were also checked; each one lands on the right page and stores the right state, with the exceptions listed below. Two API-level suites then ran 208 more checks (59 business scenarios and 149 per-module cases). Every cross-user access check passed, and the wallet ledger stayed consistent through every money path.

The pass found **21 new issues** that the green suite doesn't cover:
- **P1 findings (resolved 2026-11-23):**
  - [FE-03](#fe-03): a wrong password silently freezes the login form.
  - [LRN-04](#lrn-04): locked lessons can be completed out of order.
  - [SEC-10](#sec-10): website admins can mint admins and deactivate the superuser through the API.
  - [EXM-04](#exm-04): a closed exam window or used-up attempts make completion impossible, with no recovery.
- **P2 findings (resolved 2026-11-23):**
  - [ERR-02](#err-02): 9 inputs still 500.
  - [STU-03](#stu-03): profile and note writes are unvalidated.
  - [CRS-08](#crs-08): instructor emails leak through `get_full_name()`, and the certificate PDF prints the learner's email.
  - [CRS-09](#crs-09): a rejected course never shows the instructor why.
  - [PAY-10](#pay-10): lower-case console coupons can't be redeemed.
  - [ADM-02](#adm-02): the console decision page 500s without a category.
  - [LRN-05](#lrn-05): watch-time cheating.
  - [FE-04](#fe-04): field errors are hidden behind "Invalid input.".
  - [ACC-02](#acc-02): password change and API-key revoke semantics.
  - [ACC-03](#acc-03): `S1@x.com` and `s1@x.com` become two accounts.
  - [RPT-01](#rpt-01): learner and revenue counts disagree.
- **P3 findings (resolved 2026-11-23):**
  - [REPO-04](#repo-04): dead code and about 45 unused imports.
  - [DOC-03](#doc-03): docs drift.
  - [FE-05](#fe-05): dead UI controls.
  - [FE-06](#fe-06): routing and status inconsistencies.
  - [API-05](#api-05): create responses without ids, unordered pagination, contract drift.
  - [TEST-03](#test-03): test blind spots and local venv drift.

**Caveats that are by design but worth knowing:**
- Publishing a course revision doesn't move existing learners. They stay on the archived original and never see the update. The new version is a separate course that new buyers pay for again.
- No user-facing way to add funds exists yet ([SEC-01](#sec-01)). The E2E run had to credit wallets from the Django shell.
- When the student hasn't set a profile name, the public verify page shows "SkillStudio learner", but the **PDF prints the student's email** ([CRS-08](#crs-08)). A cached PDF is re-rendered only when its verification URL or grade changes, so a name set later doesn't appear until an admin regenerates it.
- Throttle counters (login 5/min, signup 10/hour per IP) are in-process memory. They reset when the server restarts, and they are shared by everyone behind one IP.

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
| [EXM-01](#exm-01) | P1 | ~~Exam questions are visible before the exam window opens~~ ✅ resolved 2026-11-21 |
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
| [LRN-04](#lrn-04) | P1 | Locked lessons can be completed out of order — ✅ resolved 2026-11-23 |
| [SEC-10](#sec-10) | P1 | Website admins can mint admins and deactivate the superuser through the REST API — ✅ resolved 2026-11-23 |
| [FE-03](#fe-03) | P1 | Login and signup errors are never shown; the button stays stuck — ✅ resolved 2026-11-23 |
| [EXM-04](#exm-04) | P1 | Course completion can become permanently impossible (exams and quiz attempts) — ✅ resolved 2026-11-23 |
| [FE-10](#fe-10) | P1 | Students can't read lessons on a phone — ✅ resolved 2026-11-24 |
| [ADM-01](#adm-01) | P2 | ~~Django admin actions and fields bypass the domain logic~~ ✅ resolved 2026-11-21 |
| [SEC-09](#sec-09) | P2 | ~~Gateway secrets and payout bank details stored in plaintext~~ ✅ resolved in code 2026-11-21 |
| [EXM-03](#exm-03) | P2 | ~~Exam grading and marks integrity (no snapshot, unpassable exams)~~ ✅ resolved in code 2026-11-21 |
| [STU-02](#stu-02) | P2 | ~~Dashboard numbers are wrong or never populated~~ ✅ resolved in code 2026-11-21 |
| [CRS-02](#crs-02) | P2 | ~~Ownership failures return 400 instead of 403; admins can't moderate content~~ ✅ resolved 2026-11-21 |
| [CRS-03](#crs-03) | P2 | ~~Course lifecycle and editability rules contradict each other~~ ✅ resolved in code 2026-11-21 |
| [CRS-04](#crs-04) | P2 | ~~Category creation is broken (slug never generated)~~ ✅ resolved in code 2026-11-21 |
| [CRS-05](#crs-05) | P2 | ~~Course price, free flag and tags aren't validated~~ ✅ resolved in code 2026-11-21 |
| [CRS-06](#crs-06) | P2 | ~~Public course endpoints expose instructor emails~~ ✅ resolved 2026-11-21 |
| [CRS-07](#crs-07) | P2 | ~~Fake or stub features in the course API~~ ✅ resolved in code 2026-11-21 |
| [ENR-01](#enr-01) | P2 | ~~`was_reactivated` is always `true`~~ ✅ resolved 2026-11-21 |
| [ENR-02](#enr-02) | P2 | ~~Serializer fields silently dropped (`thumbnail_url`, `get_full_name`)~~ ✅ resolved 2026-11-21 |
| [ENR-03](#enr-03) | P2 | Three different lesson-unlock algorithms — ✅ resolved 2026-11-21 |
| [ERR-01](#err-01) | P2 | Broad `except Exception` leaks internals and hides bugs — ✅ resolved 2026-11-21 |
| [STU-01](#stu-01) | P2 | Bookmarks leak unpublished content; instructors can't see their wallet — ✅ resolved 2026-11-21 |
| [EXM-02](#exm-02) | P2 | Exam settings that do nothing; analytics disagree with grading — ✅ resolved 2026-11-21 |
| [CRT-01](#crt-01) | P2 | Certificate admin, verification and rendering issues — ✅ resolved 2026-11-21 |
| [ACC-01](#acc-01) | P2 | Account-management inconsistencies — ✅ resolved 2026-11-21 |
| [PERF-01](#perf-01) | P2 | N+1 queries and unpaginated list endpoints — ✅ resolved 2026-11-21 |
| [API-04](#api-04) | P2 | No API contract: inconsistent error and pagination shapes — ✅ resolved 2026-11-21 |
| [OPS-04](#ops-04) | P2 | Local throttling, logging and CI ✅ resolved 2026-11-22 |
| [SEC-08](#sec-08) | P2 | Frontend CSP, local Tailwind, event listeners and cookie scope ✅ resolved 2026-11-22 |
| [FE-02](#fe-02) | P2 | Role-based navbar, page guards and stale frontend code ✅ resolved 2026-11-22 |
| [ASM-03](#asm-03) | P2 | Quiz editing respects the course lock ✅ resolved 2026-11-22 |
| [INS-01](#ins-01) | P2 | Instructor dashboard error handling and aggregate counts ✅ resolved 2026-11-22 |
| [ERR-02](#err-02) | P2 | Malformed query parameters and request bodies still return 500 — ✅ resolved 2026-11-23 |
| [STU-03](#stu-03) | P2 | Student profile and note writes bypass their serializers — ✅ resolved 2026-11-23 |
| [CRS-08](#crs-08) | P2 | Instructor (and student) emails still reach other users — ✅ resolved 2026-11-23 |
| [CRS-09](#crs-09) | P2 | A rejected course never shows the instructor why — ✅ resolved 2026-11-23 |
| [PAY-10](#pay-10) | P2 | Console-created coupons can be unredeemable; coupon form exposes every account — ✅ resolved 2026-11-23 |
| [ADM-02](#adm-02) | P2 | Console course decision page crashes when the course has no category — ✅ resolved 2026-11-23 |
| [LRN-05](#lrn-05) | P2 | Watch-time anti-cheat lets a client skip most of a video — ✅ resolved 2026-11-23 |
| [FE-04](#fe-04) | P2 | API field-validation messages never reach the user — ✅ resolved 2026-11-23 |
| [ACC-02](#acc-02) | P2 | Password change and API-key revocation don't do what the UI says — ✅ resolved 2026-11-23 |
| [ACC-03](#acc-03) | P2 | Email addresses are case-sensitive: duplicate accounts and failed logins — ✅ resolved 2026-11-23 |
| [RPT-01](#rpt-01) | P2 | The same statistic is calculated differently in different places — ✅ resolved 2026-11-23 |
| [FE-07](#fe-07) | P2 | Instructor and exam pages scroll sideways on phones — ✅ resolved 2026-11-24 |
| [FE-08](#fe-08) | P2 | The lesson editor's stylesheet never renders — ✅ resolved 2026-11-24 |
| [FE-11](#fe-11) | P2 | Course content and quiz editor rows clip on phones — ✅ resolved 2026-11-24 |
| [REPO-01](#repo-01) | P3 | ~~5,965 vendored `venv` files, `.pyc`, and scratch scripts tracked in git~~ ✅ resolved 2026-11-21 |
| [REPO-02](#repo-02) | P3 | ~~Dead code and stale comments~~ ✅ resolved 2026-11-21 |
| [REPO-03](#repo-03) | P3 | ~~Migration churn in `accounts`~~ ✅ resolved 2026-11-21 (squashed 0001–0008) |
| [DOC-01](#doc-01) | P3 | ~~README advertises features that don't exist and has no setup guide~~ ✅ resolved 2026-11-21 |
| [DOC-02](#doc-02) | P3 | ~~App READMEs document a different API~~ ✅ resolved 2026-11-21 (generated route reference) |
| [DEP-01](#dep-01) | P3 | ~~Dependencies installed but unused; no lock file~~ ✅ resolved 2026-11-21 (hash-locked) |
| [ASM-04](#asm-04) | P3 | ~~Assessment model and analytics gaps~~ ✅ resolved 2026-11-21 |
| [REPO-04](#repo-04) | P3 | Dead code and leftovers after the fix rounds — ✅ resolved 2026-11-23 |
| [DOC-03](#doc-03) | P3 | Docs and this report have drifted from the code — ✅ resolved 2026-11-23 |
| [FE-05](#fe-05) | P3 | Dead, misleading or inconsistent UI controls — ✅ resolved 2026-11-23 |
| [FE-06](#fe-06) | P3 | Routing and status-display inconsistencies — ✅ resolved 2026-11-23 |
| [API-05](#api-05) | P3 | API contract gaps found by the scenario suites — ✅ resolved 2026-11-23 |
| [TEST-03](#test-03) | P3 | Gaps the green suite doesn't catch; noisy output; local env drift — ✅ resolved 2026-11-23 |
| [FE-09](#fe-09) | P3 | Small-phone overflow, small tap targets and iOS input zoom — ✅ resolved 2026-11-24 |

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
> - **Full refund revokes access:** the enrollment is canceled. Re-buying then charges again. Certificate revocation was completed in [CRT-01](#crt-01).
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
### EXM-01: Exam questions are visible before the exam window opens — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.**
> - **Questions only during an attempt.** For students, `GET /api/exams/<id>/` returns questions and custom questions **only while the student has an in-progress, unexpired attempt**. Otherwise they're empty, with `questions_hidden: true`, plus `availability` (`open` / `not_open_yet` / `closed` / `not_published`) and the `start_datetime`/`end_datetime`, so the page can say when the exam opens. Attempts can only start inside the window, so questions can't leak early. Instructors and admins still see everything.
> - **Submit re-checks.** `submit_exam_attempt` refuses an attempt that wasn't started inside the window (`outside_window`) or whose exam is no longer published. An attempt started just before the window closes can still be finished within its own duration.
> - **Clear reasons.** Start and submit return `409 {error, code}` with an explicit reason ("This exam opens at … UTC", "closed at …", "You have used all N attempt(s)") instead of "could not be started". The exam list page already shows that message.
> - **Tests:** `exams/test_exam_window.py`. The existing answer-hiding test now starts an attempt first.

*Original finding:*

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
> - [API-04](#api-04) adds an OpenAPI snapshot and response-shape checks for errors and paginated collections.

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

<a id="lrn-04"></a>
### LRN-04: Locked lessons can be completed out of order — ✅ RESOLVED 2026-11-23

**Resolution:** Lesson completion, watch time, and quiz detail, start, answer and submit all use the same prerequisite rule. A rejected completion does not create a progress record.

**Evidence (✔ verified in the live E2E run):**
- A student enrolled in "Git Essentials" called `POST /api/enrollments/lessons/<2nd lesson>/complete/` before finishing the 1st lesson. `GET .../lessons/<id>/content/` correctly returned **403 `lesson_locked`**, but `complete/` returned **200 "Lesson marked as completed."**
- [enrollments/views.py](enrollments/views.py) `CompleteLessonView` and `LessonWatchTimeView` only check for an access enrollment. Neither calls `lesson_lock_state`, so the single progression rule from [ENR-03](#enr-03) is enforced on reads only.
- ✔ The same applies to quizzes. `POST /api/assessments/quiz/<id>/start/` (and submit) on a quiz whose lesson is still **locked** returned **200**. The quiz views only call `require_active_enrollment`.
- `CompleteLessonView` also runs `LessonProgress.get_or_create` *before* it checks the watch threshold or quiz, so a refused request still creates a progress row. Those rows count as "Started" in the lesson-analytics CSV.

**Impact:** Students can skip ahead and complete text lessons, and video lessons through watch-time, without unlocking them. Course progress, completion and certificates then no longer prove that lessons were taken in order.

**Fix approach:** In both views, and in quiz start/submit, return 403 `lesson_locked` when `lesson_lock_state(enrollment)[lesson.id]` is true, using the same check as `LessonDetailView`. Create the progress row only after the request is accepted. Add API tests for both endpoints.

<a id="sec-10"></a>
### SEC-10: Website admins can mint admins and deactivate the superuser through the REST API — ✅ RESOLVED 2026-11-23

**Resolution:** Only superusers can grant or revoke admin privileges or change staff accounts through the REST API. Newly promoted admins are console-only. Staff and self-deactivation are blocked on the API.

**Evidence (✔ verified):** A non-superuser `role=admin` account that can use the website signed in on the website and called the following:
- `PATCH /api/accounts/users/<student>/role/ {"role":"admin"}` returned **200**. The student became `role=admin, is_staff=True, admin_console_only=False`, which gives website admin powers and staff console access.
- `POST /api/accounts/users/<superuser>/deactivate/` returned **200**, and the superuser was locked out.

The new console ([accounts/admin.py](accounts/admin.py)) deliberately restricts these actions. Only superusers can change roles, groups or staff accounts, and accounts promoted to admin become console-only. `UpdateUserRoleView`, `PromoteToInstructorView`, `DeactivateUserView` and `ActivateUserView` in [accounts/views.py](accounts/views.py) bypass all of that, because `IsAdmin` admits any platform admin. The views also let admins deactivate themselves.

**Impact:** The console's governance model can be bypassed. Any website admin, or anyone holding their session, can escalate other accounts and lock out every superuser.

**Fix approach:** Use one rule for both paths. Require `is_superuser` to grant or revoke the admin role or to change staff accounts. Refuse to deactivate superusers, staff accounts and yourself through the API. Set `admin_console_only=True` whenever the API grants the admin role, as the console does. Alternatively, remove these REST endpoints and keep user management in the console only.

<a id="fe-03"></a>
### FE-03: Login and signup errors are never shown; the button stays stuck — ✅ RESOLVED 2026-11-23

**Resolution:** The login and signup forms preserve their general error message nodes when clearing field errors. A wrong password or throttled signup displays the error and re-enables submission.

**Evidence (✔ verified in Chromium):**
- Signing in with a wrong password showed no message. `#login-error` stayed hidden, the button stayed disabled with "Signing in...", and the page threw `TypeError: Cannot set properties of null (setting 'textContent')`.
- Cause: [templates/auth/login.html](templates/auth/login.html) and [templates/auth/register.html](templates/auth/register.html) clear old errors with `querySelectorAll('[id$="-error"]').forEach(el => el.textContent = '')`. That selector also matches the `#login-error` / `#register-error` container and deletes its inner `<p>`. Every later `container.querySelector('p').textContent = ...` throws, including in the `catch` block, so the button reset never runs.
- Signup has the same problem. It also happens on the throttled-signup 429 response and on the "accept the Terms" message. Field errors such as `email` still display, because they use their own elements.
- No test covers the wrong-password or failed-signup UI. The browser smoke tests only sign in successfully.

**Impact:** Every failed sign-in fails silently. That covers a mistyped password, the 5/min throttle and a deactivated account. Users have to reload the page to try again.

**Fix approach:** Exclude the containers from the selector (`[id$="-error"]:not(#login-error):not(#register-error)`) or write to a dedicated message element. Add Playwright tests for a wrong password and for a throttled signup.

<a id="exm-04"></a>
### EXM-04: Course completion can become permanently impossible (exams and quiz attempts) — ✅ RESOLVED 2026-11-23

**Resolution:** Exams with a closing date are optional for course completion. Published exams without a closing date must be passed. The console can grant an extra attempt from a failed quiz or eligible exam attempt, retaining its grade and logging the decision. Create, edit and publish validate exam windows. Exam changes go through a draft course or revision. New paid courses require a non-preview lesson. An existing course with only previews can be completed by finishing all lessons. Operators can use **Evaluate selected enrollments for completion** for existing enrollments that already meet the updated requirements.

**Evidence (✔ verified):**
- An instructor published a second exam on an already-published course with a 45-second window. A student then completed every lesson and passed the quiz: progress was 100%, but the enrollment stayed `active`. `POST /api/exams/<id>/start/` now returns **409 "This exam closed at ..."**, so the student can never complete the course or earn its certificate.
- `course_exam_requirements_met` ([exams/services.py](exams/services.py)) requires every **published** exam on the course to be passed. That includes exams whose window has closed and exams where the student has used up `max_attempts`.
- Quizzes have the same dead end. Once a student fails `Quiz.max_attempts` times (default 3), the lesson can never be completed ([ASM-01](#asm-01) moved the block from 1 attempt to 3 attempts). No admin or instructor tool can reset attempts or grant an extra one. A repo-wide search finds none.
- ✔ **An exam whose `end_datetime` is before its `start_datetime` is accepted (201) and can be published (200).** Nobody can ever start it, so every student of that course is blocked permanently.
- ✔ **A paid course whose lessons are all free previews can never be completed.** A student paid $15 and finished every lesson, and the enrollment stayed `active`. `get_lesson_completion_stats` requires `total_lessons > 0`, and free lessons don't count. Submission and publishing allow such a course, and every lesson is readable for free anyway.
- Exams are not covered by the course lock or by admin review. An instructor can create and publish an exam on a published course without a draft revision or review. Doing so changes the completion rule for every enrolled student after they enrolled. In the run above, the course status stayed `published` while its completion rule changed.

**Impact:** Students can lose the ability to finish a course they paid for, through no action of their own. The resulting support cases have no in-app remedy.

**Fix approach:**
- Decide which rule applies and write it down. Options: count only exams that the student can still take, or that were published before the student enrolled; or make exams optional with `Exam.required_for_completion`.
- Add an operator action in the console to grant an extra attempt or reset an attempt (quiz and exam), and record it in the log.
- Validate `start_datetime < end_datetime` on create, update and publish. Require at least one required (non-preview) lesson to submit a paid course, or treat a course with no required lessons as complete once the student has finished every lesson.
- Put exam create, publish and edit on a published course behind the same course edit lock and revision used for lessons, or at least behind review.

<a id="fe-10"></a>
### FE-10: Students can't read lessons on a phone — ✅ RESOLVED 2026-11-24

**Resolution:** Below the `lg` breakpoint, the learn page stacks: the course header and progress bar come first, then a **Course contents** toggle that opens the lesson list. Picking a lesson closes the list and scrolls to the lesson, which uses the full width. The lesson controls show a full-width **Mark as Complete** above **Previous** and **Next**. Long URLs and words in lesson articles wrap (`.lesson-article { overflow-wrap: anywhere }`). Desktop keeps the side-by-side layout. The phone-width browser test checks that the lesson text is visible and at least 250px wide at 320px, and that the outline opens.

**Evidence (✔ verified in Chromium at 320, 375 and 667px wide):** `templates/students/learn.html` rendered a fixed `flex h-screen overflow-hidden` row: a `w-96` (384px) lesson list beside the lesson. On a phone the list took the entire width and the lesson column shrank to nothing. The screen showed the course outline and footer, and the lesson that had just loaded was invisible. Because the row clips its content instead of widening the page, the page-overflow check in the first mobile pass ([FE-07](#fe-07)) reported it as fitting. The interactive pass found it by checking for squeezed and clipped content.

**Impact:** The core learning journey didn't work on phones: students could open a course but not read or watch its lessons, or reach **Mark as Complete**.

---

## 6. P2: Medium

<a id="adm-01"></a>
### ADM-01: Django admin actions and fields bypass the domain logic — ✅ RESOLVED 2026-11-21

> - Enrollment and lesson progress records are view-only in admin. Staff with the corresponding change permission can evaluate enrollment completion, mark lesson progress complete, or cancel an enrollment through the relevant action. Completion checks the lesson and assessment requirements, issues a certificate, and can repair a missing certificate for an eligible legacy completion. Canceled enrollments are excluded.
> - Admin publishing and archiving use the same row-locked course transition service as the review API. Publishing requires a course under review and archiving requires a published course. The admin form displays the status and review metadata as read-only. The remaining editing and versioning rules are tracked under [CRS-03](#crs-03).
> - Wallets, wallet transactions, and payments are view-only in admin. [D-01](#d-01) reserves wallet funding for verified Stripe top-ups, so admin has no manual credit or capture action.

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
### SEC-09: Gateway secrets and payout bank details stored in plaintext — ✅ RESOLVED IN CODE 2026-11-21

> - The legacy `InstructorPayout` table was already migrated into `payments.Payout`. Migration `payments/0005` encrypts existing destinations with a dedicated Fernet key and removes the plaintext column.
> - New payout requests encrypt destinations before reserving wallet funds. The API and Django admin show only whether a destination is on file.
> - Applying the migration to Neon still requires configuring `PAYOUT_DETAILS_ENCRYPTION_KEY`. See [the migration notes](README.md#migrations).

**Evidence:**
- `payments.PaymentGatewayConfig` has `secret_key` and `webhook_secret` as plain `CharField`s, fully visible and editable in Django admin. No code reads this model; real secrets should come from env vars.
- `InstructorPayout.payment_details` (bank or account details) is a plaintext `JSONField` echoed back by `InstructorPayoutSerializer`, and so is `payments.Payout.account_details`.

**Fix approach:**
- Delete `PaymentGatewayConfig` (with a migration) and read gateway keys from environment variables only. *(Done 2026-11-21 with [REPO-02](#repo-02), migration `payments/0004`.)*
- Store payout destinations as provider tokens (e.g. Stripe Connect account id) instead of raw bank data. If raw data is unavoidable, encrypt the field (`django-fernet-fields` / KMS) and return only a masked summary.

<a id="exm-03"></a>
### EXM-03: Exam grading and marks integrity — ✅ RESOLVED IN CODE 2026-11-21

> - Attempts snapshot bank and custom questions, answer keys, marks, the passing threshold, and timing rules. Students receive the question text and options from their active snapshot. Once an exam has attempts, editing its questions or grading rules requires a new exam. Exam records are view-only in Django admin.
> - The server derives total marks and validates the passing threshold. The create page saves a draft and uses the publish endpoint to publish it.
> - Answer changes save to the server and reload restores them with the time remaining. Submit and autosave lock the attempt. On expiry, the next attempt, result, or analytics request finalizes the saved answers. Repeated submissions return the existing grade.
> - Migration `exams/0004` snapshots open attempts from the question data available at migration time, converts out-of-range legacy passing marks to the equivalent proportion of the actual total, and preserves stored grades for completed attempts. The migration has been tested locally. *(Neon was rebuilt from all migrations later on 2026-11-21, see [REPO-03](#repo-03).)*

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
### STU-02: Dashboard numbers are wrong or never populated — ✅ RESOLVED IN CODE 2026-11-21

> - The dashboard uses the shared required-lesson completion calculation. Course completion and issued certificates are counted independently, including legacy certificates without an enrollment link.
> - Lesson watch updates and new completions record daily activity in the browser's timezone. Yesterday keeps a current streak alive. Weekly watch time sums the seconds credited to each day.
> - Student and instructor profile totals are calculated on read. Instructor revenue uses the same earnings calculation as the wallet ledger, including processed refunds. Instructor verification is informational under the email-domain eligibility policy in [D-02](#d-02).
> - The migrations recover historical activity dates available in existing progress rows and remove the stale profile counters. Daily watch seconds are recorded from this change forward because historical progress holds cumulative time. Applying these migrations to Neon is pending.

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
### CRS-02: Ownership failures return 400 instead of 403; admins can't moderate content — ✅ RESOLVED 2026-11-21

> Course, module, and lesson management routes check `can_manage_course` through a shared object mixin or the parent-course check on create. Non-owners without platform admin privileges receive HTTP 403. Admins can edit eligible content through the normal editor, and their changes preserve the assigned instructor. Draft-only deletion rules and cross-course move validation still apply.

**Evidence:**
- Course, module and lesson update/delete views raise `ValidationError("You don't have permission…")`, which is HTTP 400 ([courses/views.py:193](courses/views.py#L193) and around 12 other places).
- Their checks are `course.instructor != request.user`, so platform admins can't edit or delete content, contradicting `policies.can_manage_course`.

**Fix approach:** Replace them with `if not can_manage_course(user, course): raise PermissionDenied`. Put the shared check in one mixin (`CourseOwnedObjectMixin.get_object`).

<a id="crs-03"></a>
### CRS-03: Course lifecycle and editability rules contradict each other — ✅ RESOLVED IN CODE 2026-11-21

> - Submission, approval, rejection, and archive use the shared row-locked lifecycle. Changes to a course under review return it to draft in the same transaction. Failed changes preserve its review. The browser editor uses the review actions and Django admin displays course records with service-backed moderation actions.
> - A published course can have one separate draft revision. Publishing it records a `CourseVersion` snapshot and archives its predecessor. New buyers enroll in the revision at its own slug. Existing learners retain access to their original course and progress. Archived courses leave the public catalog.
> - Migration `courses/0004` adds the revision link. *(Neon was rebuilt from all migrations later on 2026-11-21, see [REPO-03](#repo-03).)*

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
### CRS-04: Category creation is broken (slug never generated) — ✅ RESOLVED IN CODE 2026-11-21

> - Category saves generate a unique slug if the slug is blank. Name collisions receive numbered suffixes, and existing slugs stay stable through renames. A duplicate category name is a validation error.
> - The category list annotates the published-course count so the query count is fixed across each page.
> - Migration `courses/0005` repairs legacy blank slugs. Applying it to Neon is pending.

**Evidence:**
- `CategorySerializer` marks `slug` read-only ([courses/serializers.py:20](courses/serializers.py#L20)), and `Category` has no auto-slug.
- So `POST /api/courses/categories/create/` stores `slug=''`, and the second category raises `IntegrityError` (500).
- `get_course_count` also runs one query per category.

**Fix approach:** Add a `Category.save()` that slugifies `name` (with uniqueness handling like `Course.save`), and annotate `course_count` in the queryset.

<a id="crs-05"></a>
### CRS-05: Course price, free flag and tags aren't validated — ✅ RESOLVED IN CODE 2026-11-21

> - The course API and database enforce zero prices for free courses and positive prices for paid courses. The create and edit forms require a positive price in paid mode. A failed edit preserves the price, tags, and review state.
> - Tag IDs are validated together and duplicates collapse. The tag rows are locked before the course's tag associations are written in bulk within the same transaction.
> - Migration `courses/0006` normalizes legacy free, zero-cost, and negative-price rows to zero-priced free courses before adding the constraint. Valid paid prices are preserved. Applying the migration to Neon is pending.

**Evidence:** `CourseCreateUpdateSerializer`:
- Allows negative `price`.
- Allows `is_free=False` with `price=0`, which creates a "paid" course that costs 0 and skips payment because of `price > 0`.
- Passes invalid `tag_ids` through to an FK `IntegrityError` (500).

**Fix approach:** Validate `price >= 0`. Enforce `is_free ⇔ price == 0` with a serializer check and a DB `CheckConstraint`. Validate `tag_ids` against `Tag.objects.filter(id__in=…)`, and use `bulk_create`.

<a id="crs-06"></a>
### CRS-06: Public course endpoints expose instructor emails — ✅ RESOLVED 2026-11-21

> - Course list and detail return `instructor_id` and a profile display name. Catalog and featured instructor names use a generic fallback when no suitable profile name is set.
> - The assigned course instructor and platform admins can read review notes. Other viewers receive a course response with the review field omitted.
> - Instructor dashboard student contact details are scoped to enrollments in the signed-in instructor's own courses.

**Evidence:** `CourseListSerializer` and `CourseDetailSerializer` include `instructor_email` (and the detail view includes `rejection_reason`) on `AllowAny` endpoints ([courses/serializers.py:225](courses/serializers.py#L225)). The instructor dashboard also lists `student_email`s, which is acceptable for owners, but check it against your privacy policy.

**Fix approach:** Drop `instructor_email` from public serializers, and expose `instructor_id` plus the display name instead. Only include `rejection_reason` for the owner or an admin.

<a id="crs-07"></a>
### CRS-07: Fake or stub features in the course API — ✅ RESOLVED IN CODE 2026-11-21

> - Rating order returns HTTP 400. The preview page removed its placeholder rating, the detail API removed the stub `learning_outcomes` field, and the course forms and pages use saved course fields and the real curriculum.
> - Course lists accept `page_size` (20 by default, 100 maximum). The home and instructor dashboard request three courses. The home page uses real enrollment-based popularity.
> - The lesson API accepts video, text, and quiz. Migration `courses/0007` converts legacy assignments and resource lessons to text and preserves their content and attachments. Applying the migration to Neon is pending.

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
### ENR-02: Serializer fields silently dropped (`thumbnail_url`, `get_full_name`) — ✅ RESOLVED 2026-11-21

> Enrollment lists include `course_thumbnail` from `Course.thumbnail` and `instructor_name`. Exam and question detail include `created_by_name`, and attempt responses include `user_name`. The authenticated name fields use the profile name with an account email fallback. Missing thumbnails and absent exam or question creators are represented as null. Regression tests cover the API responses.

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
### ENR-03: Three different lesson-unlock algorithms — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Course detail, catalog lesson summaries, curriculum, and lesson content share the progression rule in `enrollments.services.lesson_lock_state`. Both resume routes, the next-lesson route, enrollment details, and the student dashboard use the first unlocked, incomplete required lesson. Free previews remain accessible without gating later lessons.
> - Study order is module position, module ID, lesson position, then lesson ID. Migration `courses.0008` resolves duplicate positions in that order, preserves lesson IDs, and enforces unique positions per module.
> - Lesson creation assigns the next position when omitted. Explicit duplicates return a field validation error.

*Original finding:*

**Evidence:**
- `LessonDetailView` counts **free** lessons as required predecessors and compares `module__position` (so ties break across modules).
- `CourseCurriculumView` skips free lessons.
- `courses/progression.get_next_lesson` and `enrollments/services.get_next_lesson` are two more variants.

The UI can show a lesson as unlocked that the server then refuses.

**Fix approach:** Write one `enrollments.services.lesson_lock_state(enrollment)` that returns `{lesson_id: locked}` using `(module.position, module.id, lesson.position, lesson.id)` ordering, and use it in curriculum, lesson detail and resume. Delete `courses/progression.py`, and add `UniqueConstraint(module, position)`.

<a id="err-01"></a>
### ERR-01: Broad `except Exception` leaks internals and hides bugs — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** The shared DRF exception handler returns a structured 400 for Django validation errors and logs unexpected exceptions with their tracebacks before returning a generic 500. Payments and enrollment purchases still handle their typed business errors. The instructor dashboard and certificate regeneration now let unexpected exceptions reach the handler. Regression tests verify field errors, safe 500 responses, and rollback after a failed coupon write.

*Original finding:*

**Evidence:**
- `payments/views.py` (around 10 times), `payments/webhooks.py` and `enrollments/serializers.py:263` all do `except Exception as e: return {'error': str(e)}` → 400.
- Real bugs such as [PAY-02](#pay-02)'s `TypeError` are reported as client errors containing Python messages.

**Fix approach:**
- Catch only domain errors (`django.core.exceptions.ValidationError`, a custom `DomainError`) and map them to 400.
- Let everything else propagate to DRF's handler as a logged 500.
- Add a custom `EXCEPTION_HANDLER` that turns Django `ValidationError` into a DRF 400 with a stable shape ([API-04](#api-04)).

<a id="stu-01"></a>
### STU-01: Bookmarks leak unpublished content; instructors can't see their wallet — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Course and lesson bookmarks follow catalog visibility on create, update, and read. When access ends, saved bookmarks stop appearing in the list or detail and their owner can still delete them. Wallet and transaction reads are already scoped to the signed-in account for every role. The sidebar now shows **My Wallet** under **Account**, including on instructor pages. The dashboards use their DRF role permissions directly.

*Original finding:*

**Evidence:**
- `create_bookmark` accepts any course or lesson id, and the response includes `course_title` / `lesson_title`, so draft course titles are enumerable.
- Instructors are credited into `Wallet` ([PAY-07](#pay-07)), but `WalletView` is `IsStudent`-only.
- `StudentDashboardView(APIView, StudentOnlyMixin)` has the MRO backwards, so the mixin's `initial` never runs (harmless only because `IsStudent` is also set).

**Fix approach:** Check `can_view_course_catalog` in `create_bookmark`. Let a wallet's owner of any role read it, or move instructor earnings out of `Wallet` ([PAY-07](#pay-07)). Remove the unused mixins.

<a id="exm-02"></a>
### EXM-02: Exam settings that do nothing; analytics disagree with grading — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Randomized exams store the seed and combined bank/custom question order in each new attempt snapshot. Reloads and resumes use that order. Student question review uses the submitted attempt snapshot and requires both released results and enabled answer review. Completed attempts without snapshots keep their recorded grades. Analytics use the recorded correctness where available and the same matcher as grading otherwise. They include custom questions and zero scores. Exam creation, updates, publication, and attempt start enforce course ownership for question-bank membership. DRF's datetime fields handle timezone conversion.

*Original finding:*

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
### CRT-01: Certificate admin, verification and rendering issues — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Regeneration targets a certificate UUID and requires a platform administrator. The API and UI use a single certificate ID. Verification has a public HTML page, and the PDF QR and share link point there. Non-debug startup requires a non-local backend origin.
> - Certificates are issued without rendering. Authorized downloads render on demand and reuse the cached PDF when its verification URL and released grade match. This fits the local-only deployment and removal of Celery in [DEP-01](#dep-01).
> - Cancellation and full refunds revoke certificates in the same transaction. Migration `certificates.0002` marks legacy canceled enrollments' certificates revoked. A learner who qualifies again receives a fresh verification link.
> - Passing published course exams is required for new completion and exam attempts contribute to the grade. The displayed grade follows exam result release settings. PDFs embed shaped Unicode fonts and wrap long names and titles. Download counters use atomic increments.

*Original finding:*

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
### ACC-01: Account-management inconsistencies — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Logout accepts expired or missing access tokens, clears the authentication cookies, and blacklists valid refresh tokens. Cookie requests still require CSRF. Removing the admin role clears Django staff access, and migration `accounts.0010` cleans up legacy staff flags before enforcing the rule in the database. Both role endpoints and the Django admin form reject superuser demotion. The current-user API treats account status as read-only. API keys enforce `read` and `write` scopes in addition to the owner's permissions. Existing unscoped keys keep their normal access, and scoped keys cannot create broader credentials.

*Original finding:*

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
### PERF-01: N+1 queries and unpaginated list endpoints — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** Course counts are annotated and course detail loads only the viewer's enrollment and progress. Enrollment lists batch completed lesson IDs, and the dashboards and instructor roster calculate progress without per-course queries. Payment history, refunds, the instructor roster, and the detailed learning dashboard now return page-number responses with `count`, `next`, `previous`, and `results`. Payment history and the roster also return a `summary` for the entire filtered result set. Their pages expose Previous and Next controls. Query-budget tests cover the changed reads.

*Original finding:*

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
### API-04: No API contract: inconsistent error and pagination shapes — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21.** The OpenAPI schema is served at `/api/schema/`, with a validated snapshot in [docs/openapi.yaml](docs/openapi.yaml) and a pull-request drift check. It documents supported authentication methods, pagination and the shared error envelope. Some hand-built success responses retain a free-form schema.
> - API errors return JSON with `detail`, `code`, and `fields`. Certificate and coupon verification retain their status metadata. The frontend reads the common envelope, including after an access-token refresh.
> - Standalone list endpoints use `count`, `next`, `previous`, and `results`. Exam attempt history has page navigation. The instructor dashboard uses one canonical route.

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
### OPS-04: No throttling, logging, health check or real background jobs — re-scoped by D-03 — ✅ RESOLVED 2026-11-22

> **Resolved 2026-11-22.** DRF scopes limit login (5/min), registration (10/hour), refresh (60/min), enrollment (30/min) and payment mutations (30/min). Requests use the direct client IP for anonymous limits and the authenticated user for enrollment and payment limits. Django and API errors use JSON logs on stdout. CI runs Django checks, migrations drift, the suite on PostgreSQL with Chromium, Tailwind bundle drift and a locked dependency audit. The existing secret scan still runs independently. Celery and Redis were already removed under DEP-01. Local SQLite remains the default. D-03 excludes deployment work. The seven dependency pins reported by the initial scan were updated, and the locked runtime requirements passed pip-audit.

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
### SEC-08: Frontend hardening: CSP, CDN Tailwind, inline handlers, cookie scope — ✅ RESOLVED 2026-11-22

> **Resolved 2026-11-22.** The frontend serves a checked-in Tailwind bundle built with the pinned CLI and local shared JavaScript. Django enforces a per-response CSP nonce for page scripts and blocks inline event attributes and eval. The learning page allows the player scripts it needs. Controls use explicit event listeners, and the lesson editor rebuilds stored rich text from permitted formatting elements. The refresh cookie is scoped to the accounts API and legacy sessions rotate into that scope. The root access cookie supplies identity to page views. Existing inline styles and Google Fonts remain allowed.

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
### FE-02: Role-based navbar never works; debug logs and stale routes — ✅ RESOLVED 2026-11-22

> **Resolved 2026-11-22.** Navbar and sidebar roles come from the authenticated account on the server. Instructor pages and exam creation enforce the instructor or platform-admin role. Expired access is renewed through the accounts API before retrying a protected page. Removed debug traces and the orphan profile template. The recommendations route was already removed by REPO-02. Native dialogs were replaced with the shared notification and confirmation component.

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
### ASM-03: Quiz editing ignores course lock; error points to a non-existent feature — ✅ RESOLVED 2026-11-22

> **Resolved 2026-11-22.** Quiz management uses the same course edit lock as lesson and module edits for owners and platform admins. Published and archived courses require a draft revision. A successful edit returns a course under review to draft, while a rejected edit leaves its status intact. Questions with attempt history keep their 409 protection, and the response now points to adding a new quiz lesson.

**Evidence:**
- `ManageQuizView` lets the owner create a quiz or change `passing_percentage` / `time_limit` on a **published** course, unlike every other content endpoint.
- Its 409 says "Create a new quiz version instead", but versioning doesn't exist.
- Admins are excluded (owner-only check).

**Fix approach:** Apply the same editability rule as [CRS-03](#crs-03) through the shared mixin from [CRS-02](#crs-02), and reword the 409 to describe what the instructor can actually do.

<a id="ins-01"></a>
### INS-01: Instructor dashboard swallows errors and returns fake zeros — ✅ RESOLVED 2026-11-22

> **Resolved 2026-11-22.** Unexpected failures use the standard logged 500 API response. The dashboard reuses wallet and payout calculations from PAY-07, counts the courses it already fetches, and computes distinct learners and active enrollments in one aggregate.

**Evidence:** [instructors/views.py:37-55](instructors/views.py#L37) catches every exception, `print`s a traceback, and returns `200` with zero revenue and empty lists. Real failures look like "no data".

**Fix approach:** Remove the try/except and let errors 500 and get logged. Fix the data source mismatch from [PAY-07](#pay-07), and collapse the three duplicate count queries into one aggregate.

<a id="err-02"></a>
### ERR-02: Malformed query parameters and request bodies still return 500 — ✅ RESOLVED 2026-11-23

**Resolution:** The reported payment date, enrollment, question-bank and note filters return field-level HTTP 400 errors for malformed input. Payment datetime filters use timezone-aware values.

**Evidence (✔ each one returned `500 internal_error` against the live server):**

| Request | Cause |
|---|---|
| `GET /api/payments/stats/?start_date=garbage` | `timezone.datetime.fromisoformat()` raises `ValueError` ([payments/views.py](payments/views.py)) |
| `GET /api/payments/instructor/earnings/?end_date=nope` | same |
| `GET /api/enrollments/?course=abc` | the raw value goes to `filter(course_id=...)` |
| `GET /api/exams/questions/?course_id=abc` | same pattern ([exams/views.py](exams/views.py)) |
| `GET /api/students/notes/?lesson=abc` | same pattern ([students/views.py](students/views.py)) |
| `PATCH /api/students/profile/ {"weekly_study_hours":"abc"}` | see [STU-03](#stu-03) |
| `PATCH /api/students/notes/<id>/ {"timestamp":"abc"}` | see [STU-03](#stu-03) |
| `POST /api/students/notes/ {"lesson":1}` (no content) | see [STU-03](#stu-03) |
| `POST /api/students/notes/ {"lesson":"x","content":"y"}` | see [STU-03](#stu-03) |

The date parameters also produce naive datetimes while `USE_TZ=True`. Similar parameters elsewhere already return 400: `?attempt=abc` on exams, and `?course=abc` on bookmarks.

**Impact:** Typos and bad clients produce logged server errors instead of 400s. [ERR-01](#err-01) set the goal that bad input returns a readable 400.

**Fix approach:** Parse query parameters with a small helper or a DRF `Serializer` (`IntegerField`, `DateTimeField`) and raise `ValidationError`. Add one table-driven test that sends bad values to every list filter.

<a id="stu-03"></a>
### STU-03: Student profile and note writes bypass their serializers — ✅ RESOLVED 2026-11-23

**Resolution:** Profile and note writes validate through their serializers. Students and instructors can update a profile before their first GET. Repeating a lesson or course bookmark returns the existing row with HTTP 200.

**Evidence:** `StudentProfileView.put/patch` calls `update_student_profile(request.user, **request.data)`. `StudentNoteListCreateView.post` and `StudentNoteDetailView.put/patch` call the note services with raw request values ([students/views.py](students/views.py), [students/services.py](students/services.py)). The services use a field allowlist, so there is no mass assignment, but no type validation runs.
- ✔ Wrong types and missing content return 500 (see [ERR-02](#err-02)).
- ✔ Negative values are stored: `weekly_study_hours=-5` returned 200, and a note with `timestamp=-9` returned 201.

- ✔ **Profile PATCH fails for new accounts.** A brand-new student's `PATCH /api/students/profile/` and a brand-new instructor's `PATCH /api/instructors/profile/` return **400 "profile not found"** until a GET has lazily created the profile. The update services use `objects.get(...)` while the readers use `get_or_create`. The web pages GET first, so the UI works, but API clients can't.
- ✔ **Duplicate bookmarks.** Bookmarking the same lesson twice returned 201 both times and created two rows.

**Fix approach:** Validate with `StudentProfileSerializer` / `StudentNoteSerializer` (`partial=True` for PATCH) and pass `validated_data` to the services. Use `get_or_create` in both profile update services. Add a unique `(user, lesson)` constraint on bookmarks and return 200 for an existing one.

<a id="crs-08"></a>
### CRS-08: Instructor (and student) emails still reach other users — ✅ RESOLVED 2026-11-23

**Resolution:** Learner-facing course, payment and certificate responses use display names and generic fallbacks. Certificate PDFs now match public verification and are refreshed on download when the display name changes. Instructor roster and dashboard emails are limited to that instructor’s own courses.

**Evidence (✔ seen in live API responses):** [CRS-06](#crs-06) removed instructor emails from public course endpoints, but `User.get_full_name()` returns the **email** whenever the profile has no name, and several serializers still use it or expose the email directly:
- A student's `POST /api/enrollments/enroll/` and `GET /api/enrollments/...` returned `"instructor": {"name": "ina@instructor.com"}` (`EnrollmentDetailSerializer`). `EnrollmentListSerializer.instructor_name` behaves the same way.
- A student's `GET /api/payments/` returns `instructor_email`, and `GET /api/payments/payouts/` returns `instructor_name: "<email>"`.
- The instructor dashboard and students list return `student_email` for every learner. This may be intended, but it isn't written down.
- **The certificate PDF prints the learner's email** when the profile has no name (`certificates/pdf.py:88`: `profile_display_name(user) or user.email`). People share that document, and its QR code points to a public page. Public verification shows "SkillStudio learner" for the same certificate, so the two disagree. `CertificateSerializer.user_name` has the same fallback, but only the owner sees it.
- `AdminCourseStatsView` lists instructor emails, which is acceptable for admins.

**Fix approach:** Use `accounts.utils.public_instructor_name()` in every learner-facing serializer and drop `instructor_email` from student payment responses. Use the same fallback on the PDF as on the verify page, and re-render the PDF when the name changes. Make `get_full_name()` stop falling back to the email, or stop using it in serializers. Document whether instructors may see learner emails.

<a id="crs-09"></a>
### CRS-09: A rejected course never shows the instructor why — ✅ RESOLVED 2026-11-23

**Resolution:** The course list and content editor show the review date and private rejection reason for returned drafts. Resubmitting clears the feedback from both views.

**Evidence (✔ verified):** The console reviewer chose "Return to draft" with the note "Please add a summary lesson". The course went back to `draft`, and `GET /api/courses/<slug>/` returns `rejection_reason` to the owner. However, no template reads `rejection_reason`. A repo-wide search over `templates/` only finds the unrelated refund reason. The instructor's content page, course list and edit page show the course as a plain draft, so the review loop has no feedback in the UI. [courses/README.md](courses/README.md) says "Review notes are available on course detail to the assigned instructor", which is true only for the API.

**Fix approach:** Show the latest `rejection_reason` and `reviewed_at` on the content page and in the instructor course list while the course is a draft, and clear it on resubmit (the service already does that).

<a id="pay-10"></a>
### PAY-10: Console-created coupons can be unredeemable; coupon form exposes every account — ✅ RESOLVED 2026-11-23

**Resolution:** Coupon codes are normalized and unique regardless of case. The console assigns the operator and shares discount validation with the API. Refunds retain coupon usage. Zero-cost redemptions tied to a course retain the learner’s entitlement when reactivated. Legacy redemptions acquire a course only when there is a linked payment that identifies it. Earlier payment-free redemptions with no course evidence are preserved for manual reconciliation.

**Evidence (✔ verified):**
- An operator created coupon `spring25` in the console coupon form, which is a plain `ModelAdmin`. It was stored lower-case and appeared in the public `GET /api/payments/coupons/` list as `spring25`. Every redemption attempt returned **"Invalid coupon code."**, including one typed exactly as listed, because `validate_coupon_for_course` upper-cases the input and matches exactly. The API path (`services.create_coupon`) upper-cases codes, but the console doesn't.
- The console form requires a hand-picked **Created by** user from a dropdown of **every account's email**. The API sets it automatically. The coupon model also allows a percent value above 100, a negative `min_order_amount` and similar values that the API serializer rejects.
- ✔ The **API** also accepts `discount_type=percent, discount_value=150` (201). The discount is capped at the price, so the coupon silently becomes "100% off".
- ✔ After a student gets a course with a 100% coupon (no `Payment` row) and the enrollment is cancelled, re-enrolling **charges the full $40**. `purchase_course` only treats an earlier *payment* as "previously paid", not an earlier free redemption.
- Refunds don't decrement `current_usage` or delete the redemption. A refunded buyer has still used up their per-user allowance.

**Fix approach:** Normalise `code` in `Coupon.save()` or a `clean_code`, use a case-insensitive lookup (`code__iexact`) and a unique constraint on `Upper('code')`. Set `created_by` from `request.user` in `CouponAdmin.save_model` and make it read-only. Share validation between the admin form and the API. Decide what a refund does to coupon usage.

<a id="adm-02"></a>
### ADM-02: Console course decision page crashes when the course has no category — ✅ RESOLVED 2026-11-23

**Resolution:** The course decision form renders an uncategorized course and preserves its review actions.

**Evidence (✔ 500 in the live run):** `Course.category` is `on_delete=SET_NULL, null=True`, but `CourseAdmin.decision_details` ([courses/admin.py](courses/admin.py)) reads `obj.category.name`. After a category was deleted, `/admin/courses/course/<id>/decision/` raised `AttributeError: 'NoneType' object has no attribute 'name'`. Reviewers can't publish or archive such a course from the console.

**Fix approach:** `obj.category.name if obj.category else '—'`, plus a regression test. Consider `PROTECT` on categories in use.

<a id="lrn-05"></a>
### LRN-05: Watch-time anti-cheat lets a client skip most of a video — ✅ RESOLVED 2026-11-23

**Resolution:** The first watch event can credit at most 15 seconds. Each later event is capped by server elapsed time, with no repeat grace grant. Responses report the actual credited delta.

**Evidence (✔ verified):** `update_lesson_watch_progress` ([enrollments/services.py](enrollments/services.py)):
- skips the elapsed-time check on the **first** event for a lesson, because the progress row is created in that call. One `PATCH .../watch-time/ {"watch_time_delta": 60}` credited 60 seconds and completed a 1-minute video in **0.0 s**. Any video up to 150 seconds long completes from a single request, since the cap is 120 s and the threshold is 80%.
- gives a 15-second grace on **every** event, so a client can send 15 seconds of credit every second and finish a 10-minute video in about 40 seconds.
- Section 8 of this report called this "server-side delta caps tied to elapsed time". That is true only after the first event, and only up to the grace window.

**Fix approach:** Credit the first event at most the grace window, and make the grace cumulative (`watch_time <= elapsed_since_started + grace`) rather than per event. Alternatively, accept the limits as demo-grade and say so in the docs.

<a id="fe-04"></a>
### FE-04: API field-validation messages never reach the user — ✅ RESOLVED 2026-11-23

**Resolution:** The shared browser API client surfaces field messages when the response detail is generic, including nested validation errors.

**Evidence (✔ verified):** With the [API-04](#api-04) envelope, field errors arrive in `fields` and `detail` is the generic "Invalid input.". `apiRequest()` ([static/js/app.js](static/js/app.js)) builds its error from `detail` only. Saving a lesson with a non-video URL therefore showed just **"Invalid input."**, while the reason (`fields.video_url`) was dropped. Only three pages read `error.body.fields`, and each reads only specific fields: course create/edit read `price`, and settings reads the password fields. Every other form behaves like the lesson editor, including the exam builder, quiz builder, payouts, refunds, notes and profile.

**Fix approach:** In `apiRequest()`, when `detail` is the generic message, use the first entry of `fields` as the error message. Better, add a shared helper that marks each invalid input.

<a id="acc-02"></a>
### ACC-02: Password change and API-key revocation don't do what the UI says — ✅ RESOLVED 2026-11-23

**Resolution:** Changing a password invalidates old JWT access and refresh tokens, clears the browser cookies, and returns the browser to login. API-key revocation is permanent and idempotent through the revoke endpoint and the legacy toggle URL. The unsupported account-deletion control was removed.

**Evidence (✔ verified):**
- After a password change, the page says "Password changed successfully. Please log in again." The user stays on Settings, and `/api/accounts/me/` still returns 200. The access cookie stays valid for up to 30 minutes. The refresh token was silently blacklisted, so the session ends later at an unpredictable moment. Other browsers also keep working until their access token expires.
- An API key "revoked" in settings can be restored by calling the same toggle endpoint again. `PATCH /api/accounts/api-keys/<id>/toggle/` flips `is_active` back and clears `revoked_at`. Revocation is expected to be permanent, and the README says "create and revoke API keys".
- The **Delete Account** button in Settings has no handler and no backend endpoint. Accounts with financial history can't be deleted on purpose.

**Fix approach:** After a password change, clear the auth cookies in the response and redirect to the login page. Make revocation one-way: split the toggle into a `revoke` endpoint. Remove the Delete Account block, or replace it with "contact an admin".

<a id="acc-03"></a>
### ACC-03: Email addresses are case-sensitive: duplicate accounts and failed logins — ✅ RESOLVED 2026-11-23

**Resolution:** Email identity is case-insensitive for creation, sign-in and storage. The migration normalizes existing addresses in place and reports conflicting account IDs before modifying any rows. Collision resolution requires a decision about the existing accounts and their records.

**Evidence (✔ verified):** With `s1@student.com` registered, `POST /api/accounts/register/ {"email": "S1@student.com", …}` returned **201** and created a second account. The DB then held both `s1@student.com` and `S1@student.com`. Logging in as `S1@STUDENT.COM` returned **401** for the original user. `BaseUserManager.normalize_email` lower-cases only the domain part, `User.email` is a case-sensitive unique field, and the login backend matches exactly.

**Impact:** One person can end up with two accounts, each with its own wallet, purchases and certificates. Users who type their email with a capital letter can't sign in. The [D-02](#d-02) role-by-domain rule is unaffected because it compares the domain case-insensitively.

**Fix approach:** Lower-case the whole address on save and registration, add a unique constraint on `Lower('email')`, and authenticate with `email__iexact`. Check existing rows for case duplicates before adding the constraint.

<a id="rpt-01"></a>
### RPT-01: The same statistic is calculated differently in different places — ✅ RESOLVED 2026-11-23

**Resolution:** Catalog, course detail, popularity, instructor course reporting and the console count both active and completed enrollments. Admin course and payment reports share the same net course-sale calculation and return revenue strings.

**Evidence (read in source; the revenue figures were confirmed in the live run):**
- `enrollments_count` on course list and detail counts only `active` enrollments, so the number shown **drops when students complete the course**. `ordering=popular` and the console use `ACCESS_STATUSES` (active + completed) ([courses/views.py](courses/views.py)).
- `AdminCourseStatsView.total_revenue` ([courses/views_analytics.py](courses/views_analytics.py)) sums gross `amount` over `status='completed'` only. That excludes partially refunded sales entirely and isn't net of refunds, and it returns a `float`. `PaymentStatsView` and the console use net amounts across `SETTLED_PAYMENT_STATUSES`. `top_courses` also counts only `active` enrollments, and its docstring names a non-existent route (`/api/courses/admin/stats/`).

**Fix approach:** Define "learners", "revenue" and "sales" once, for example in `payments.services` and `courses.services`, reuse those definitions, and return money as strings.

<a id="fe-07"></a>
### FE-07: Instructor and exam pages scroll sideways on phones — ✅ RESOLVED 2026-11-24

**Resolution:** Header rows stack below the `sm` breakpoint (`lg` for course preview) and their buttons wrap. Instructor course cards put the thumbnail above the text on phones, and their action buttons wrap. Long titles break instead of widening the page. On phones, the exam header shows only the title, a one-line course summary and the timer; Submit stays in the fixed bottom bar, which now has space reserved under the questions. The card's **Students** button now opens the instructor roster. `core.test_browser_smoke` `test_pages_fit_a_small_phone_screen` checks these pages at 320px.

**Evidence (✔ verified in Chromium at 375px, screenshots reviewed):**

| Page | Page width | Cause |
|---|---|---|
| `/instructor/courses/` | **645px** | Each course card is a fixed row: a 192px thumbnail beside the text, and four action buttons that never wrap. Titles were squeezed to about three words per line. |
| `/instructor/courses/<slug>/preview/` | 563px | The title, status badge, **Edit Course** and **Manage Content** share one non-wrapping row. |
| `/exams/take/<id>/?attempt=<id>` | 410px | The sticky header pushes **Submit Exam** off-screen. |
| `/instructor/lessons/<id>/edit/` | 404px | **Save & Publish** is pushed off-screen. |
| `/exams/` (instructor) | 387px | The title, **Create Exam** and the status filter share one row. |

All five use the same pattern: `flex items-center justify-between` with no wrapping or stacking at small widths. The same course card's **Students** button linked to `/instructor/courses/<slug>/students/`, which has no route, so it returned 404 at every width.

**Impact:** Instructors on a phone had to scroll sideways to reach the main actions on their course list, preview and editor. A student taking an exam on a phone saw a header with its Submit button cut off.

<a id="fe-08"></a>
### FE-08: The lesson editor's stylesheet never renders — ✅ RESOLVED 2026-11-24

**Resolution:** The styles moved to `{% block extra_head %}`. No other template uses a block that `base.html` lacks. The toolbar buttons also got a 40px minimum size for touch. The phone-width browser test checks that the toolbar's styles are applied.

**Evidence (✔ verified):** `templates/instructor/lesson-editor.html` put its `<style>` in `{% block extra_css %}`, but `base.html` only defines `extra_head`. Django drops content in a block the parent never renders. So the formatting toolbar, editor area and quiz-builder styles were missing at every width. The toolbar showed as bare text, with the Italic button 4px wide.

<a id="fe-11"></a>
### FE-11: Course content and quiz editor rows clip on phones — ✅ RESOLVED 2026-11-24

**Resolution:** On phones, section headers on the course content page stack the title above the lesson count and buttons, and lesson rows put **Edit Content** and **Delete** under the title. Answer inputs in the quiz editor and the exam builder's question form have `min-width: 0`, so they shrink instead of pushing the remove button out. The phone-width browser test loads a draft course's content page and the quiz editor at 320px.

**Evidence (✔ verified in Chromium at 320px):**
- `/instructor/courses/<slug>/content/`: section titles were squeezed into a narrow column beside the lesson count, **+ Add Lesson** and delete. The section card's `overflow-hidden` clipped the lesson count and the **Delete** buttons.
- `/instructor/lessons/<id>/edit/` in quiz mode: each answer row (radio, text input, × button) was 338px wide. A text input in a flex row doesn't shrink below about 20 characters without `min-width: 0`.

---

## 7. P3: Low

<a id="repo-01"></a>
### REPO-01: 5,965 vendored `venv` files, `.pyc`, and scratch scripts tracked in git — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21:** the scratch scripts were deleted with [OPS-05](#ops-05). `.pre-commit-config.yaml` now has a `forbid-venv-and-bytecode` hook that blocks `venv/`, `.venv/`, `env/`, `__pycache__/` and `*.py[cod]`, next to the existing `.env` and gitleaks hooks.
>
> *Earlier progress:* `venv/` (5,965 files) and all 136 tracked `*.pyc` were removed from the whole git history as part of the [SEC-03](#sec-03) scrub. The local `venv/` folder and `.pyc` files are still on disk, ignored. A pre-commit hook now blocks `.env*`. **Still open:**
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
### REPO-02: Dead code and stale comments — ✅ RESOLVED 2026-11-21

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

> **Resolved 2026-11-21:**
> - Deleted `views_attempt.SubmitQuizAttemptView` (earlier) and `CourseVersionSerializer`. The `CourseVersion` model stays, because `Course.current_version` points at it.
> - Deleted the no-op `Lesson.clean()/save()`. `Course.clean()`'s "free means price 0" rule moved into `Course.save()`, so it now holds on every save and not only in admin forms.
> - Deleted `accounts/utils.normalize_role_flags`, `core/templatetags/` (`get_item`), the dead `/recommendations/` page, `instructors.services.get_lesson_dropoff` and its import, and the unused, unpaid wallet helpers in `students/services.py` (`add_funds_to_wallet`, `deduct_funds_from_wallet`, `get_wallet_balance`, `get_wallet_transactions`).
> - Deleted `PaymentGatewayConfig`, its admin and imports (migration `payments/0004`).
> - Removed the commented-out event, recommender and dropoff code (settings, root URLconf, payments models and admin, instructors, enrollments). `MeView.get` no longer swallows exceptions.
> - Removed about 520 lines of hand-written "PostgreSQL equivalent" SQL comments from every `models.py`. They had drifted from the real schema (for example, `auth_user` references); migrations are the schema source of truth.
> - `views_analytics.py` now has an accurate docstring and no unused re-export.

<a id="repo-03"></a>
### REPO-03: Migration churn in `accounts` — ✅ RESOLVED 2026-11-21

**Evidence:** `accounts/migrations` has two `0002_*` files plus a merge (`0003`), and a wallet field that is added, removed, added and removed again (`0002`, `0004`, `0005`, `0009`).

Several data migrations are **destructive and irreversible** (`reverse = noop`):
- `core/0001` and `core/0002` run `DROP TABLE` on the removed live/social feature tables.
- `assessments/0004` and `exams/0003` delete every non-MCQ question.

**Fix approach:**
- Once every environment has migrated past `0009`, squash with `squashmigrations accounts 0001 0009` to speed up test DB creation and remove the confusion.
- Document in the deploy runbook that a DB snapshot is mandatory before applying migrations, and add a `--plan` review step in CI for any migration containing `RunSQL`/`RunPython` deletes.

> **Resolved 2026-11-21:**
> - New `accounts/0001_squashed_0008.py` is one clean initial migration (`replaces` 0001–0008, including the duplicate `0002`s and the merge). New databases run it plus `0009`. Databases that already applied the old files keep using them.
> - `0009` stays separate. It depends on `students.0002`, and folding it into the squash creates a dependency cycle (`students` depends on the user model).
> - The data steps in `0006`, `0007` and `0009` are marked `elidable`.
> - **Verified:**
>   - A fresh database migrates cleanly.
>   - A database built from the previous commit upgrades cleanly (it marks the squash applied).
>   - Both end with identical `accounts` tables.
> - Delete the replaced files once no database still needs them.
> - The README's **Migrations** section makes a backup (`pg_dump`) and a `migrate --plan` review (read every `Raw Python`/`Raw SQL` operation) mandatory, and names the destructive migrations. There is no deploy CI ([D-03](#d-03)). Instead, `core.tests.ProjectHygieneTests` fails when a model changes without a migration.
> - **Neon database rebuilt 2026-11-21 (on the owner's instruction, no backup):** its history was inconsistent (`certificates.0001` recorded before `enrollments.0001`). Its schema had also drifted from the migrations: some tables were never recorded, some recorded apps had no tables, and removed apps had left tables and history behind.
>   - All 104 tables were dropped, deleting the test data in them.
>   - `migrate` was run from scratch: 50 tables, every migration applied, and `accounts` on `0001_squashed_0008`.
>   - `create_categories` was run to seed the categories.

<a id="doc-01"></a>
### DOC-01: README advertises features that don't exist and has no setup guide — ✅ RESOLVED 2026-11-21

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

> **Resolved 2026-11-21:** [README.md](README.md) was rewritten from the code. It covers:
> - what exists today, per role, and what doesn't exist yet (the Stripe top-up)
> - an architecture diagram and a table of what each app owns
> - the rules to know before changing code (one money path, policies, signup roles)
> - local setup (venv, hash-locked install, `.env.example`, `migrate`, `create_categories`, `createsuperuser`, `runserver`)
> - how to run tests, including the browser tag
> - a migrations safety section, secrets hygiene, and the roadmap (which links here)
>
> There are no deploy notes, by [D-03](#d-03).

<a id="doc-02"></a>
### DOC-02: App READMEs document a different API — ✅ RESOLVED 2026-11-21

**Evidence:** There are about 5,200 lines of per-app docs.
- `courses/README.md` documents `/api/v1/courses/...`, slug-based update/delete, and `submit-review/` / `unpublish/` endpoints, none of which exist.
- `accounts/README.md` documents email verification and password-reset tokens, which were removed on purpose.
- `payments/README.md` describes event payments.

**Fix approach:** Once the OpenAPI schema ([API-04](#api-04)) exists, delete the hand-written endpoint lists and keep a short domain/invariants README per app that links to `/api/schema/`.

> **Resolved 2026-11-21** (without waiting for API-04):
> - The roughly 5,200 lines of hand-written app docs were replaced by short READMEs per app (about 25–50 lines each), checked against the code. Each covers the models, the rules and invariants, and where the logic lives.
> - `accounts/QUICKSTART.md`, `courses/QUICKSTART.md`, `enrollments/QUICKSTART.md` and `enrollments/IMPLEMENTATION_SUMMARY.md` were deleted.
> - Endpoints now live in **[docs/API_ROUTES.md](docs/API_ROUTES.md)**. `python manage.py api_routes --write` generates it from the URLconf: path, methods, DRF permission classes and view, for all 132 API routes.
> - `core.tests.ProjectHygieneTests` fails when the file is stale.
> - [API-04](#api-04) publishes the OpenAPI schema at `/api/schema/`.

<a id="dep-01"></a>
### DEP-01: Dependencies installed but unused; no lock file — ✅ RESOLVED 2026-11-21

> **Resolved 2026-11-21:**
> - Removed Celery: `skillstudio/celery.py`, the import in `skillstudio/__init__.py`, the `CELERY_*` settings and the `.env.example` block.
> - Removed every package only Celery or Redis needed: `celery`, `kombu`, `amqp`, `billiard`, `vine`, `redis`, `click*`, `prompt_toolkit`, `wcwidth`, `tzlocal`, `python-dateutil`, `six`, `msgpack`, `colorama`, `exceptiongroup` and `packaging`.
> - Direct dependencies are now declared in `requirements.in` and `requirements-dev.in`. `requirements.txt` and `requirements-dev.txt` are generated by `pip-compile --generate-hashes`, which gives 15 runtime packages (it was 35) with hashes.
> - **Verified:** a clean venv installed with `pip install --require-hashes -r requirements.txt -r requirements-dev.txt` passes `manage.py check` and the test suite.
> - Earlier: `gunicorn` and `daphne` were removed ([D-03](#d-03)).
> - **Your existing `.venv` still has the old packages.** Run `pip-sync requirements.txt requirements-dev.txt` (from `pip-tools`) to match the lock files.

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
### ASM-04: Assessment model and analytics gaps — ✅ RESOLVED 2026-11-21

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

> **Resolved 2026-11-21** (migration `assessments/0007`):
> - `Quiz` has `created_at`/`updated_at`, a `__str__` and `verbose_name_plural`.
> - `QuizQuestion.difficulty` uses `TextChoices` (`easy`/`medium`/`hard`). The migration maps existing free-text values onto them, with unknown values becoming `medium`.
> - `Quiz.is_published` now defaults to `False`. Existing quizzes keep their value.
>   - `ManageQuizView` accepts `is_published`, and a new quiz is a draft unless it's set.
>   - The lesson editor uses **Save Draft** and **Save & Publish**. It also sends `max_attempts` now; that field was in the form but never saved.
> - `total_marks` is kept equal to the sum of the questions' marks by `post_save`/`post_delete` signals on `QuizQuestion` (`assessments/signals.py`), so admin and shell edits stay in sync too. The migration recomputes it for existing quizzes.
> - Both analytics functions count finished attempts only. Both analytics views and `ManageQuizView` use `can_manage_course`, so admins have access.
> - Tests: `assessments/test_quiz_model.py`.

<a id="repo-04"></a>
### REPO-04: Dead code and leftovers after the fix rounds — ✅ RESOLVED 2026-11-23

**Resolution:** Removed unused code, the quiz scoring test shim, the instructor-only test endpoint, unused imports and the obsolete ASGI setting. Ruff checks for undefined names and unused code in CI. Historical financial columns and payout relationships remain stored outside the current API response. Provider helpers retained for PAY-04 are marked. Local obsolete scripts, report outputs and the Windows virtual environment were archived under the ignored `output/pdf/.p3-archive/`. Certificate media stays in its storage location.

**Evidence (pyflakes, vulture and a repo-wide reference search over tracked files):**
- **Unreferenced functions and classes** (no caller in code, templates or tests):
  - `accounts/decorators.py` (the whole module, `role_required`)
  - `accounts.serializers.UserBasicSerializer`
  - `courses.serializers.LessonListSerializer`
  - `courses.services.is_course_completed`, which also encodes a different completion rule from `evaluate_and_complete_enrollment`
  - `enrollments.services.get_previous_lesson`
  - `instructors.serializers.CourseOverviewSerializer` and `StudentEngagementSerializer`
  - in `payments.services`: `fail_payout`, `get_payment_by_provider_id`, `get_pending_payouts`, `log_webhook_event`, `mark_webhook_processed`, `create_dispute`, `resolve_dispute`, and the `request_payout` alias. The webhook and dispute helpers may be kept for the Stripe work, but should say so.
- **Test-only or vestigial code:**
  - `assessments/services_scoring.py`, a one-line shim used only by tests
  - `assessments/constants.PASS_PERCENTAGE = 70`, which is unused and contradicts the real default pass mark of 50
  - `core/models.py`, empty boilerplate
  - `settings.ASGI_APPLICATION`, which only Channels/Daphne read, and both were removed
- **Test endpoint shipped in the URLconf:** `GET /api/accounts/instructor-only/` (`InstructorOnlyView`, "Test endpoint"). It is also published in `docs/API_ROUTES.md` and the OpenAPI schema.
- **About 45 unused imports** in non-test modules. Examples: `students/views.py` has 10, `enrollments/serializers.py` 6, `courses/views.py` 4, `instructors/views.py` 4 and `students/services.py` 4. There is also an f-string without placeholders at `certificates/services.py:218` and unused locals in tests.
- **Unused model surface:**
  - `Payment.billing_address`, `ip_address` and `provider_refund_id`
  - `Refund` statuses `approved`, `processing` and `failed`, which no code path sets
  - the deprecated `Payout.payments` M2M, which `PayoutSerializer.payment_count` still serializes (always 0)
  - `Payout.METHOD_CHOICES`, whose default is `stripe_connect` although only manual bank transfers exist (the UI sends `bank_transfer`, but the API default doesn't)
- **Untracked local leftovers** (git-ignored, but they confuse a reader):
  - `venv/`, an old Windows virtualenv next to `.venv/`
  - `tmp/pdfs`, `output/pdf` and `scripts/render_backend_review_*.py`, which render the deleted reports
  - `core/__pycache__/test_zz_dbg.cpython-313.pyc` from a deleted debug test
  - `media/certificates/` from before OPS-02

**Fix approach:** Delete the unreferenced code and imports in one PR. Remove the test endpoint and regenerate `docs/API_ROUTES.md` and `docs/openapi.yaml`. Add `ruff check --select F` (pyflakes) to CI so unused imports can't build up again.

<a id="doc-03"></a>
### DOC-03: Docs and this report have drifted from the code — ✅ RESOLVED 2026-11-23

**Resolution:** The READMEs now describe direct video files, the instructor preview route and the existing OpenAPI contract. The audit index, resolutions and implementation plan agree with the feature states.

**Evidence:**
- [README.md](README.md) **Roadmap** still lists "An OpenAPI schema (API-04)" as open, while the same README documents `docs/openapi.yaml` and API-04 is resolved.
- README ("Video lessons support YouTube and Vimeo URLs") and [courses/README.md](courses/README.md) ("must be YouTube or Vimeo") are out of date. `courses/video.py`, the serializer, the lesson editor and the learn page all also accept direct video-file URLs (`.mp4`, `.webm` and so on).
- The [ASM-04](#asm-04) resolution says the lesson editor has a **Published to students** checkbox. The editor actually uses **Save Draft** / **Save & Publish** buttons.
- In this report:
  - The REPO-02, REPO-03, DOC-02 and ASM-04 headings lacked the ✅ status that the index showed. Fixed in this pass.
  - Phase 3 of the plan listed ENR-01 without striking it through. Fixed.
  - The CRS-03 and EXM-03 notes said their migrations "still need to be applied to Neon", which the REPO-03 rebuild made stale. Fixed.
  - Section 8 called SEC-06 "the remaining gap" and described the watch-time caps as sound (see [LRN-05](#lrn-05)). Fixed.

**Fix approach:** Fix the two READMEs. Keep this report's headings, index and plan in sync in the same commit as each fix.

<a id="fe-05"></a>
### FE-05: Dead, misleading or inconsistent UI controls — ✅ RESOLVED 2026-11-23

**Resolution:** Removed the inert login and section fields and the wallet action from the insufficient-funds dialog. Paid checkout confirms the quoted price and the server rejects a higher charge. Review feedback and editor URL prompts use app dialogs. Purchase clears the wishlist entry. An empty quiz editor receives 204 without creating a quiz.

**Evidence (✔ each one seen while driving the UI):**
- **Remember me** on the login page has no code reading it. **Delete Account** in Settings has no handler (see [ACC-02](#acc-02)).
- **Section description:** the Add Section modal collects a description, but `Module` has no such field and `ModuleCreateUpdateSerializer` silently drops it. The content page has a branch that renders `section.description`, which is never set.
- **Insufficient funds:** the modal offers **Add funds** and links to a wallet page that has no way to add funds until the Stripe top-up exists ([SEC-01](#sec-01)). That's a dead end in the main purchase path.
- **Paid enrolment** charges the wallet on one click, with no confirmation showing the price. The rest of the app uses `showConfirm` for money actions, such as payout and refund requests.
- **Native dialogs:** "Return to draft" (course content) and "Insert link/image" (lesson editor) use the browser's `prompt()`, while everything else uses the app's `<dialog>`.
- **Wishlist:** a purchased course stays in the wishlist (Saved learning showed the owned course).
- **Quiz editor:** opening a new quiz lesson logs a 404 console error (`GET .../quiz/lesson/<id>/manage/` before a quiz exists). The page handles it, but it's noise.

**Fix approach:** Remove or wire each control. Add a `description` field to `Module`, or drop the textarea. Hide the Add-funds action until top-ups exist. Confirm paid purchases with the price.

<a id="fe-06"></a>
### FE-06: Routing and status-display inconsistencies — ✅ RESOLVED 2026-11-23

**Resolution:** Wrong-role pages have a 403 with navigation. Website admins land on an administration page, and course managers opening a learning link go to preview. A session hint cookie prevents anonymous login refresh probes. New payout rejections have a distinct status. Learners can cancel enrollment with a certificate and refund warning.

**Evidence (✔ from the route matrix and workflow run):**
- **Role mismatch behaves two ways.** `/dashboard/` and `/enrollments/` *redirect* an instructor to their dashboard. A student on any `/instructor/...`, `/exams/create/` or `/payments/payouts/` page, and an instructor on `/library/`, instead get Django's bare **"403 Forbidden"** page. There is no `403.html`, so the page has no navigation back.
- **Admins land on the student dashboard** after login and from `/`. Its widgets are student-only, such as enrolled courses and streak. The website has no admin home. The work queues are in the console.
- **Learn page needs an enrollment.** `/learn/<slug>/` sends course owners and admins to the course page, even though the API (`can_access_course_content`) lets them study it. Owners have the separate preview page, but this isn't documented.
- **Login page probe.** Every redirected anonymous visit to the login page sends `POST /api/accounts/token/refresh/` and gets a **401**, which appears as a console error. The run recorded 30 of them.
- **Payout status names.** A payout the console *rejects* is stored as `cancelled`, the same status as an instructor's own cancellation. Only `failure_reason` tells them apart.
- **Enrollment cancel without a UI.** `PATCH /api/enrollments/enrollments/<id>/cancel/` exists, and it revokes the certificate, but no page offers it.

**Fix approach:** Add a `403.html` that links back to the role's home, or redirect consistently. Give admins a small website landing page or send them to the console. Skip the refresh probe when no refresh cookie is likely, for example from a non-httpOnly hint cookie. Add a `rejected` payout status. Either expose enrollment cancel with a warning or remove the endpoint.

<a id="api-05"></a>
### API-05: API contract gaps found by the scenario suites — ✅ RESOLVED 2026-11-23

**Resolution:** Section and lesson creation responses include IDs. Enrollment returns the documented unavailable-course code. User and tag lists have stable ordering, route docs show per-method permissions, and quiz starts use one route. Superseded certificate links return 410 with a reason. Bank payout requests require a destination before funds are reserved.

**Evidence (✔ each one observed):**
- **Created objects have no id in the response.** `POST /api/courses/<id>/modules/`, `/sections/<id>/lessons/` and `/lessons/create/` answer 201 with a body that has no `id`, because the serializers list only writable fields. A client can't address what it just created. The course content page reloads the whole list to cope.
- **Error codes differ from the documentation.** `EnrollCourseView` says it returns `code: course_unavailable` for an unpublished course. The serializer intercepts first and returns `code: validation_error` with `fields.course_id`.
- **Unordered pagination.** `GET /api/accounts/users/` and `GET /api/courses/tags/` paginate querysets with no `order_by`. They emit `UnorderedObjectListWarning`, and pages can repeat or skip rows.
- **Duplicate quiz start route.** `POST /api/assessments/quiz/<id>/attempt/start/` (`StartQuizAttemptView`) duplicates `quiz/<id>/start/` with a different response shape, and no page uses it.
- **Re-issued certificates.** After a refund and re-purchase, the certificate gets a new verification code. The **old** code then returns 404 "not found" rather than "superseded" or "revoked", so a QR code on an old PDF looks fake.
- **Payout requests without a destination.** The API accepts a `bank_transfer` payout with no `account_details` (201), which leaves the operator nothing to pay to. The payouts page requires them.
- `docs/API_ROUTES.md` lists `/api/courses/tags/` GET as `IsAuthenticated`, but anonymous GET is allowed, because the generator reads the class attribute rather than `get_permissions()`.

**Fix approach:** Return the read serializer, including `id`, from every create endpoint. Use explicit codes, or update the docstring. Add `ordering` to both querysets. Delete the duplicate route. Keep revoked or superseded codes resolvable with `valid: false` and a reason. Validate payout destinations server-side.

<a id="test-03"></a>
### TEST-03: Gaps the green suite doesn't catch; noisy output; local env drift — ✅ RESOLVED 2026-11-23

**Resolution:** Added regression checks and a browser journey that registers the learner and instructor, authors and reviews a new course, buys it with a coupon, completes the course, verifies the certificate, cancels enrollment, requests a refund and records a manual payout. The journey seeds a reviewer, coupon and test wallet balance. Expected Django request warnings are quiet, and the local virtual environment matches both lockfiles.

**Evidence:**
- The suite passes on both databases: SQLite **498 tests OK, 3 skipped** (Postgres-only lock tests) and local Postgres 16 **498 OK, 0 skipped**. `check`, `makemigrations --check`, `check --deploy`, `spectacular --validate --fail-on-warn` and the `docs/API_ROUTES.md` / `docs/openapi.yaml` snapshots are all clean. Even so, none of [LRN-04](#lrn-04), [SEC-10](#sec-10), [FE-03](#fe-03), [EXM-04](#exm-04), [ERR-02](#err-02), [PAY-10](#pay-10) or [ADM-02](#adm-02) is caught. The browser smoke tests seed data straight into the database, and none of them tries a failure path in the UI.
- Test output is flooded with JSON `django.request` warnings for every expected 4xx (hundreds of lines), which hides real failures. Raise the `django.request` level during tests.
- The local `.venv` doesn't match the hash-locked requirements. It still has `gunicorn==21.2.0` (the CVE version from OPS-03), `daphne`, `channels`, `celery` and `redis` installed. CI is unaffected, but `pip-sync requirements.txt requirements-dev.txt` hasn't been run locally since DEP-01.

**Fix approach:** Add tests for each finding above as it is fixed. Add an E2E journey that starts from an empty database and goes through the UI (see the re-audit run in section 1). Quiet request logging in the test runner. Run `pip-sync` locally.

<a id="fe-09"></a>
### FE-09: Small-phone overflow, small tap targets and iOS input zoom — ✅ RESOLVED 2026-11-24

**Resolution:**
- Tab bars stay on one line and scroll inside their own row.
- Profile headers stack the avatar above the name, and long names, emails and usernames break.
- The exam builder's button rows wrap.
- The navbar **Sign In**, phone-menu button and footer links have larger tap areas.
- Form fields reached on phones use 16px text: the phone-menu search box and fields on the console's custom pages.

**Evidence (✔ verified in Chromium at 320px):**
- `/my-courses/` (352px) and `/enrollments/` (345px): the three tabs don't fit, so **Completed** is cut off.
- `/profile/` (329px) and `/instructor/profile/` (352px): the avatar and name row doesn't stack, and a long name or email overflows.
- `/dashboard/`: "Welcome back, *username*" doesn't break a long username (324px).
- `/exams/create/`: the right-aligned Cancel / Save as Draft / Publish row pushes **Cancel** 28px past the left edge.
- At 375px, the navbar **Sign In** link is 17px tall. The phone-menu search box uses 14px text, which makes iOS Safari zoom the page on focus. The console's refund and payout decision pages have the same zoom problem.

**Left as is:** checkboxes and radios stay 16–20px; their labels are clickable. The staff console's header links come from Django's stock admin.

---

## 8. What is in good shape

- **Domain layering.** `services.py` / `policies.py` / `serializers.py` per app is a sound structure; most fixes above are about routing work *through* it consistently.
- **Custom `User`.** DB `CheckConstraint`s on role/staff/superuser invariants, plus role normalisation on save.
- **API keys.** SHA-256 hashed secrets, a prefix index, and `hmac.compare_digest`.
- **Cookie JWT + CSRF.** httpOnly cookies, CSRF enforced only on cookie-authenticated unsafe methods, and refresh rotation with blacklist. ([SEC-06](#sec-06) is resolved.)
- **Wallet ledger.** `Wallet._apply_delta` row-locks and always writes a `WalletTransaction`. The *model* is right; the problem is who is allowed to call it ([SEC-01](#sec-01), [PAY-07](#pay-07)).
- **Assessments integrity.** Attempt question snapshots, frozen grading evidence, `select_for_update` on answers, and no `is_correct` leakage in student serializers.
- **Exams.** Student serializers strip answer keys recursively, and attempt numbering is constrained in the DB.
- **Watch-time anti-cheat.** Server-side delta caps tied to elapsed time. *(Re-audit: the first event and the per-event grace weaken it, see [LRN-05](#lrn-05).)*
- **XSS hygiene.** API data is consistently passed through `escapeHtml` / `safeUrl` (387 + 8 call sites).

---

## 9. Recommended implementation plan

| Phase | Goal | Items | Rough size |
|---|---|---|---|
| **0: Stop the bleeding** | Close money and security holes; nothing new built | SEC-01 🟡, ~~PAY-01~~ ✅, ~~SEC-02~~ ✅, SEC-03 🟡, ~~OPS-05~~ ✅, ~~FE-01~~ ✅, ~~SEC-04~~ ✅, ~~SEC-05~~ ✅, ~~BUG-01~~ ✅, ~~BUG-02~~ ✅, ~~OPS-03~~ ✅; ~~put `/api/payments/*` behind a flag~~ (superseded by D-01: the card route is deleted and the webhook rejects all) | 1–2 days |
| **1: Make learning work** | A student can enroll → learn → complete → get a certificate, and keep access | ~~LRN-01~~ ✅, ~~LRN-02~~ ✅, ~~LRN-03~~ ✅, ~~ASM-01~~ ✅, ~~ASM-02~~ ✅, ~~EXM-01~~ ✅, ~~EXM-03~~ ✅, ~~API-02~~ ✅, ~~API-03~~ ✅, ~~CRS-01~~ ✅, ~~ENR-03~~ ✅, ~~TEST-02~~ ✅ | 3–5 days |
| **2: One coherent money domain** | Single pricing, fulfilment, ledger, payout and refund path | ~~PAY-02~~ ✅ → ~~PAY-03~~ ✅ → PAY-05 🟡 → PAY-04 🟡 (Stripe top-up + verified webhook) → ~~PAY-07~~ ✅ → ~~PAY-06~~ ✅ → ~~PAY-08~~ ✅ → ~~PAY-09~~ ✅, ~~SEC-07~~ ✅, ~~SEC-09~~ ✅, ~~ADM-01~~ ✅, ~~TEST-01~~ ✅ | 1–2 weeks |
| **3: Frontend/API alignment** | Every page talks to a real, documented endpoint | ~~API-01 (build or remove each)~~ ✅, ~~API-04 (OpenAPI + error envelope)~~ ✅, ~~ENR-01~~ ✅, ~~ENR-02~~ ✅, ~~CRS-06~~ ✅, ~~CRS-07~~ ✅, ~~FE-02~~ ✅, ~~ERR-01~~ ✅ | 3–5 days |
| **4: Hardening** *(re-scoped by [D-03](#d-03): no deployment)* | Observable and hardened for local use | ~~OPS-01~~ ✅, ~~OPS-02~~ ✅, ~~OPS-04 (local items)~~ ✅, ~~SEC-06~~ ✅, ~~SEC-08~~ ✅, ~~PERF-01~~ ✅, ~~CRT-01~~ ✅, ~~CRS-02~~ ✅, ~~CRS-03~~ ✅, ~~CRS-04~~ ✅, ~~CRS-05~~ ✅, ~~ACC-01~~ ✅, ~~STU-01~~ ✅, ~~STU-02~~ ✅, ~~EXM-02~~ ✅, ~~ASM-03~~ ✅, ~~INS-01~~ ✅ | 1 week |
| **5: Hygiene** | Clean repo and truthful docs | ~~REPO-01–03~~ ✅, ~~DOC-01–02~~ ✅, ~~DEP-01~~ ✅, ~~ASM-04~~ ✅ | done |
| **6: Re-audit follow-up (2026-11-22)** | Close what the second pass and the live E2E run found | ~~FE-03~~ ✅, ~~LRN-04~~ ✅, ~~SEC-10~~ ✅, ~~EXM-04~~ ✅. ~~ERR-02~~ ✅, ~~STU-03~~ ✅, ~~CRS-08~~ ✅, ~~CRS-09~~ ✅, ~~PAY-10~~ ✅, ~~ADM-02~~ ✅, ~~FE-04~~ ✅, ~~ACC-02~~ ✅, ~~ACC-03~~ ✅, ~~LRN-05~~ ✅, ~~RPT-01~~ ✅. ~~REPO-04~~ ✅, ~~DOC-03~~ ✅, ~~FE-05~~ ✅, ~~FE-06~~ ✅, ~~API-05~~ ✅, ~~TEST-03~~ ✅ | Complete |
| **7: Mobile responsiveness (2026-11-24)** | Every page fits a phone screen | ~~FE-10~~ ✅, ~~FE-07~~ ✅, ~~FE-08~~ ✅, ~~FE-11~~ ✅, ~~FE-09~~ ✅ | Complete |

### Definition of done for release

- The full test suite (including payments) collects and passes on Postgres in CI.
- The template→route contract test and the Playwright happy-path smoke suite pass.
- No code path credits a wallet or grants an enrollment without a verified payment.
- Reconciliation shows zero unexplained differences.
- No tracked secrets, virtualenvs, bytecode or generated files; secrets rotated.
- ~~`check --deploy` is clean, static files are hashed, media is on object storage, and~~ throttles and logging are in place. *(Deployment items dropped by [D-03](#d-03).)*
- The OpenAPI schema is published, and templates use only routes in it.
