# SkillStudio Backend Review and Remediation Plan

**Review date:** 2026-07-21

**Deep re-audit:** 2026-07-21

**Last remediation update:** 2026-07-23

**Scope:** Django project configuration and all backend applications: `accounts`, `courses`, `enrollments`, `assessments`, `exams`, `certificates`, `students`, `instructors`, `social`, `live`, `payments`, and `core`.

## 1. Executive summary

The backend is a substantial Django prototype with clear domain separation, 27,698 lines of project Python, 241 authored test methods, and several recent security/correctness fixes. It is still **not safe for production deployment** as either a learning platform or a money-moving system.

The deep re-audit changed three earlier conclusions, and the 2026-07-23 remediation pass has since closed several of those concrete failures:

1. **Paid-content containment was incomplete.** The public course-detail serializer was safe, but the public module/section and lesson-list endpoints reused `LessonSerializer` and returned `content_text`, `video_url`, `metadata`, and resources. These known catalog aliases now use summary serializers and negative exposure tests.
2. **Assessment authorization had a parallel bypass.** The canonical quiz-start endpoint enforced publication and active enrollment, but `/quiz/<id>/attempt/start/` created an attempt for any authenticated user. The alternate route now delegates to the canonical eligibility/start service.
3. **The executable baseline exists, but it is red.** `manage.py check` and migration-drift checks pass; `check --deploy` reports five security warnings; the full suite discovers 227 cases and ends with 214 passing, 12 account-route failures, and one payment test-module import error.

The highest-risk current facts are:

1. **Payments remain broken and insecure.** Payment creation passes a deleted `event` field, public requests control the amount, coupon serialization references `specific_events`, webhook signatures are not verified, and fulfillment is disconnected from payment success.
2. **Financial state remains irreconcilable.** `accounts.Profile.wallet` and `students.Wallet` both hold balances; `payments.Payout` and `instructors.InstructorPayout` both represent payouts; the enrollment wallet path charges a 10% fee while the payment service uses 20%; students can credit their own wallet.
3. **Paid lesson content containment has been extended to known public catalog aliases.** Course detail, module/section lists, slug sections, and lesson-list aliases now return catalog-safe summaries; this boundary should stay regression-protected as new resource/download routes are added.
4. **Assessment attempt and authoring paths still need consolidation.** The alternate quiz-start bypass is fixed and student-by-lesson submission no longer creates assignments, but quiz replacement still deletes question rows after attempts may exist and upload/resubmission policy remains unclear.
5. **The previously probed course/assessment routed 500s are fixed.** Course resume, admin course analytics, and quiz-question analytics now have route tests. Payment creation and coupon serializer initialization still fail before a valid workflow can complete.
6. **Recent exam, completion, social, live-containment, and certificate fixes are real and covered.** They should be preserved while the remaining parallel paths are removed.
7. **Repository and production configuration are not clean.** `.env`, 5,965 files under a Windows `venv`, and 158 bytecode/cache files remain tracked; `requirements.txt` is UTF-16; there is no CI/deployment definition; production HTTPS/cookie hardening is absent.

### Remediation status as of 2026-07-23

| Finding | Status | Current evidence / decision | Verification |
|---|---|---|---|
| P0-01 payment model drift | Open / runtime-broken | `create_payment()` still supplies `event=...`; coupon serializers/views still reference deleted event relationships. Remove the event concept completely before deeper payment work. | Runtime probe: `TypeError: Payment() got unexpected keyword arguments: 'event'`; `CouponSerializer` raises `ImproperlyConfigured`. |
| P0-02 client-controlled payment amount | Open | `PaymentCreateSerializer.amount` is accepted and used as the purchase price. Price must be loaded and snapshotted from the course on the server. | Static contract inspection; payment suite cannot currently import. |
| P0-03 unsigned webhooks | Open | Stripe and PayPal webhook views parse raw JSON but perform no cryptographic signature verification. | `payments/webhooks.py`; no signed provider contract tests. |
| P0-04 disconnected fulfillment | Open | Marking payment completed does not atomically/idempotently create or reactivate enrollment and ledger effects. | Payment/enrollment service inspection. |
| P0-05 duplicate wallets/payouts | Open | Two balance fields/models, two payout models, different fee rates, and a student self-credit endpoint remain active. | `accounts.Profile.wallet`, `students.Wallet`, `payments.Payout`, `instructors.InstructorPayout`; `/api/students/wallet/` POST. |
| P0-06 paid lesson content exposure | Remediated for known catalog aliases | Public course detail, module list, section aliases, slug sections, and section/module lesson lists now use catalog-safe serializers and restrict unpublished courses to owner/admin. Continue applying the same policy to any future resource/download routes. | `courses.tests.CourseDetailContentExposureTest`; current focused `courses enrollments assessments exams certificates live social` suite passes 188 tests. |
| P0-07 moderation bypass | Remediated | Generic course create/update no longer accepts writable `status`; instructors cannot publish through normal payloads; published/archived course content cannot be changed through course/module/lesson authoring endpoints. | `courses.tests.CourseModerationWorkflowAPITest`; included in `courses enrollments assessments exams certificates` suite. |
| P0-08 exam ownership/access | Remediated | Exam/question querysets and instructor endpoints are scoped by course ownership; students must be actively enrolled to view/start/submit exams and can only submit their own attempts. | `exams.tests.ExamAccessControlAPITest`; included in `courses enrollments assessments exams certificates` suite. |
| P0-09 exam answer disclosure | Remediated | Student exam serializers recursively strip answer metadata such as `is_correct`, `correct_answer`, `answer`, model answers, and explanations from standard and custom questions. | `exams.tests.ExamAccessControlAPITest`; included in `courses enrollments assessments exams certificates` suite. |
| P0-10 assessment/exam scoring drift | Remediated | Quiz scoring now delegates to one service; the duplicate quiz-submit URL was removed; exam scoring uses actual question/custom-question marks and manual grading overwrites marks rather than adding repeatedly. | Assessment/exam regression tests; included in `courses enrollments assessments exams certificates` suite. |
| P0-11 premature/inconsistent completion | Remediated | Required lesson progress is computed from non-free required lessons only; completion uses one atomic evaluator; course-progress reads no longer complete enrollment; manual lesson completion requires watch threshold and assessment requirements. A separate lesson-progress GET side effect remains under P1-13. | Enrollment regression tests; included in `courses enrollments assessments exams certificates` suite. |
| P0-12 social-circle schema drift and privacy leaks | Remediated | Social circle policies now scope private circle visibility and child resources to active members/admins; `join_code` is removed from general serializers; legacy request fields are mapped to current model fields; rejoin reactivates existing memberships; last admin cannot leave without transfer. | `social.tests.LearningCircleAccessControlAPITest`; included in `courses enrollments assessments exams certificates live social` suite. |
| P0-13 live HTTP/WebSocket authorization and provider layer | Provider integrated / containment hardened | Live access policy now scopes HTTP list/detail/child resources; meeting credentials are hidden except for managers or successful joins; WebSocket connections require authenticated, authorized users and derive sender identity server-side; LiveKit is now the default built-in provider with backend-issued room tokens and subscribe-only student grants. Redis channel layer is selected when `REDIS_URL` is configured. | `live.tests.LiveAccessControlAPITestCase` and `live.tests.LiveWebSocketAccessControlTestCase`; included in `courses enrollments assessments exams certificates live` suite. |
| P0-14 parallel quiz-start authorization bypass | Remediated | `/quiz/<id>/attempt/start/` now requires active enrollment and delegates to the canonical `start_quiz_attempt()` service, so unpublished quizzes are rejected consistently. | `assessments.tests.QuizAPITest`; current focused `courses enrollments assessments exams certificates live social` suite passes 188 tests. |
| P1-01 account verification/reset lifecycle | Open | Accounts are active before verification; email delivery, throttling, token hashing, and issued-token revocation are absent. Self-registration can grant instructor role immediately. | Accounts model/serializer/view/settings inspection. |
| P1-02 role/superuser invariants | Open | Platform permissions rely on `role`; `create_superuser()` does not set `role=admin`, and staff/superuser handling varies by domain. | Accounts manager and permission inspection. |
| P1-03 API key lifecycle | Open / unsupported | Full API-key secrets are stored and listed, but no authentication backend consumes them. | Accounts model/serializer/DRF settings inspection. |
| P1-04 profile sources of truth | Open | Shared identity data and display-name assumptions span three profile models and inconsistent response contracts. | Accounts/students/instructors inspection. |
| P1-05 watch-progress trust/concurrency | Open | Client can jump absolute watch time to duration; no elapsed-time plausibility check or row lock protects updates. | Enrollment progress view/service inspection. |
| P1-06 enrollment purchase/reactivation | Open / unsafe | Serializer owns debit/payment/enrollment workflow, contains fail-open/best-effort branches, lacks idempotency/locking, and reports reactivation incorrectly. | Enrollment serializer inspection. |
| P1-07 certificate lifecycle/request coupling | Remediated | Certificate issuance now creates/gets the certificate record atomically and schedules PDF rendering after commit with an idempotent renderer; PDF/storage failures are logged and no longer block completion or certificate record creation. Regeneration now uses the correct service contract, and invalid verification codes return a clean invalid response. | `certificates.tests.IssueCertificateTests`, `RenderCertificatePDFTests`, and `CertificateViewTests`; included in `courses enrollments assessments exams certificates live social` suite. |
| P1-08 certificate grade calculation | Remediated | Certificate grade calculation now uses a deterministic points policy: best completed attempt per published quiz, graded assignment submissions, bounded earned points, and `None` when no graded assessment evidence exists instead of a fake 100%. | `certificates.tests.CalculateCourseGradeTests`; included in `courses enrollments assessments exams certificates live social` suite. |
| P1-09 invalid assessment mutations | Partially remediated / still open | Student-by-lesson submission no longer creates missing assignments and returns a stable 404. Quiz-management GET no longer creates quiz definitions. Quiz question replacement is rejected once attempts exist. Remaining work: objective-question validation, upload policy, resubmission grading semantics, and product-grade quiz versioning/snapshots. | `assessments.tests.AssignmentAPITest` and `ManageQuizAPITest`; full `assessments` suite passes 30 tests. |
| P1-10 attempt/concurrency invariants | Open | Multiple start services use incompatible uniqueness assumptions; no meaningful attempt number or database-enforced one-active-attempt rule exists. | Models/services/URL inspection plus P0-14 probe. |
| P1-11 live counters/attendance | Open | Poll changes/upvotes/counters and participant finalization rely on drift-prone read-modify-save behavior. | Live model/service inspection. |
| P1-12 refund/payout invariants | Open | Cumulative refund, entitlement reversal, payout allocation, and concurrent earnings reservation are not safely enforced. | Payments/instructors models and services inspection. |
| P1-13 GET side effects/error exposure | Open | Lesson-progress GET creates rows, live-list GET changes lifecycle state, and multiple views expose raw exception strings. Quiz-management GET side effects were removed under P1-09. | Routed view inspection. |
| P1-14 routed API/model drift | Remediated | Course resume now passes a `Course` object and uses the correct progression helper; admin course stats sums completed `Payment.amount`; quiz-question analytics uses `QuestionOption.is_correct` and selected option IDs. | `courses.tests.CourseRoutedAPIDriftTest` and `assessments.tests.QuizAPITest`; current focused `courses enrollments assessments exams certificates live social` suite passes 188 tests. |
| Staticfiles configuration warning | Remediated | Added tracked `.gitkeep` files for the static source/output directories so configured static paths exist without committing generated static assets. | `DATABASE_URL=sqlite:////private/tmp/skillstudio-static-check.sqlite3 .venv/bin/python manage.py check` returns no issues. |

Latest full-suite command:

```bash
DATABASE_URL=sqlite:////private/tmp/skillstudio-deep-review-tests.sqlite3 .venv/bin/python manage.py test
```

Latest result:

```text
Found 227 test(s).
Ran 227 tests in 79.161s

FAILED (failures=12, errors=1)
```

The 12 failures are stale account tests requesting an extra `/api/` path segment and receiving 404. The single error is `payments.tests` failing import because it still imports `events.models.Event`; therefore its 15 authored tests do not collect. The other 214 discovered tests passed at the last full-suite run. The focused seven-app regression command now passes 188 tests after the P0-06, P0-14, P1-14, and first P1-09 assignment-submission fixes; the focused `assessments` suite now passes 30 tests after the quiz-management GET and attempted-quiz replacement fixes.

Additional results:

- `manage.py check`: passes with no issues.
- `manage.py makemigrations --check --dry-run`: no model drift detected.
- `manage.py check --deploy`: five warnings (`security.W004`, `W008`, `W009`, `W012`, `W016`) for HSTS, HTTPS redirect, insecure fallback secret, and secure session/CSRF cookies.
- Clean SQLite migrations: all project migrations, including the LiveKit platform migration, apply successfully.
- Runtime contract probes from the deep re-audit originally confirmed the paid-content leak, alternate quiz-start bypass, and course resume/admin analytics/quiz analytics 500s; those have since been covered by regression tests and fixed. Payment creation and coupon serializer still fail against current models.

### Overall assessment

| Area | Current state | Priority |
|---|---|---|
| Authentication and account lifecycle | Registration is immediately active, verification/reset email delivery is absent, roles conflict with staff flags, and auth tests target stale URLs | P1 |
| Authorization | Exam/social/live containment improved; paid-content catalog aliases and parallel quiz-start bypass are fixed; remaining high-risk authorization work is concentrated in payments/wallets and assessment authoring/history | P0 |
| Courses and content access | Moderation, catalog serialization, and known curriculum aliases are safer; remaining course risk is mostly purchase/access lifecycle and progress trust | P0 |
| Enrollment and progress | Completion evaluator is consolidated; purchase/wallet flow, watch-time trust, locking, and reactivation semantics remain unsafe | P0 |
| Assessments and exams | Exam access/scoring, alternate quiz start, and question analytics are improved; quiz authoring history, upload policy, resubmission semantics, and concurrency remain unsafe | P1/P0 depending on release scope |
| Payments, wallets, refunds, payouts | Runtime-broken model contract plus unsafe pricing, webhook, ledger, refund, and payout invariants | P0 |
| Certificates | Record/PDF lifecycle and immediate grade policy are safer; immutable/versioned evidence and async status remain | P1 |
| Social | Private-circle containment and schema mapping are substantially improved; retain policy regression tests | P2 follow-up |
| Live | HTTP/WebSocket containment and LiveKit token provider are implemented; state-on-GET, counters, attendance, rate limits, Redis deployment, and recording automation remain | P1 |
| Operations and deployment | Local environment works, but full suite/deploy checks are red; tracked secrets/generated artifacts, UTF-16 requirements, no CI/runbook | P0 |

**Recommendation:** keep production release frozen. If payments remain intentionally deferred, the next implementation order is: (1) finish P1-09 by validating objective-question shapes and defining upload/resubmission policy; (2) repair P1-10 attempt-count/concurrency invariants; and (3) continue GET side-effect cleanup under P1-13. For an actual production release, payment P0-01 through P0-05 and repository-secret rotation remain mandatory before launch.

---

## 2. Review method and limitations

The deep re-audit covered:

- project settings, routing, ASGI, and Celery configuration;
- models, serializers, permissions, services, views, URL routing, admin modules, signals, and management commands;
- migrations and cross-app model relationships;
- all routed backend URL configurations and the template routes that consume them;
- test inventory, static Python parsing, model/serializer drift searches, authorization boundaries, and transaction/locking sites;
- repository/dependency/deployment hygiene;
- frontend-to-backend route use where it exposed an API contract mismatch.

The current source contains 27,698 lines of project Python and 241 authored `test_*` methods. A local `.venv` is available and was used for real Django checks, migrations, the full test suite, and focused runtime probes. The tracked Windows `venv` remains unusable on this host and should not be part of the repository.

Runtime validation used isolated SQLite databases under `/private/tmp`; it did not modify application data. This validates URL dispatch, serializers, migrations, and ordinary ORM behavior, but it does **not** validate PostgreSQL row locking, concurrent transactions, Redis multi-process delivery, LiveKit connectivity, object-storage behavior, Celery workers, or real Stripe/PayPal signatures. Those require integration environments.

The full test result is evidence, not a clean bill of health: 214 discovered tests passed, 12 account API tests failed because their paths have an extra `/api/`, and `payments.tests` failed import before its 15 test methods could collect. Several high-risk routes have no regression tests, which is why the explicit runtime probes found failures outside the passing suites.

---

## 3. Severity and remediation rules

- **P0 — release blocker:** exploitable authorization/data exposure, money correctness, broken core endpoint, or a condition that prevents trustworthy deployment.
- **P1 — high:** incorrect lifecycle behavior, significant data inconsistency, or a reliability issue likely to affect real users.
- **P2 — medium:** maintainability, observability, performance, or incomplete product behavior that should follow stabilization.
- **P3 — low:** cleanup or polish that can safely wait.

Every P0/P1 correction should include all of the following:

1. a failing regression test written before or with the change;
2. an explicit authorization and transaction-boundary decision;
3. a safe migration/backfill plan if persistent data changes;
4. structured logging without secrets or full request payloads;
5. API documentation and error-contract updates;
6. an idempotency decision for any endpoint that moves money or advances lifecycle state.

---

## 4. P0 findings: immediate release blockers

### P0-01 — Payment creation is out of sync with the data model

**Evidence**

- `payments/services.py` passes `event=event` to `Payment.objects.create`, but the field has been removed from `Payment`.
- `payments/views.py` still references an undefined `Event` class and sends `event` to the service.
- `CouponSerializer` includes the deleted `specific_events` relationship.
- `payments/tests.py` imports `events.models.Event`, although the application is disabled/removed.

**Impact**

Normal payment creation can fail at runtime. Coupon serializer initialization and the payment test suite can also fail. This is an incomplete feature removal that crosses models, services, views, serializers, tests, and documentation.

**Fix approach**

1. Decide explicitly whether events are permanently removed. The present repository indicates that they are.
2. Remove every event parameter, branch, serializer field, choice, test fixture, README statement, and dead import from `payments`.
3. Add a data migration changing/removing event-related coupon choices such as `events` and define how existing rows are mapped.
4. Change payment creation to accept a typed purchase target (`course_id`) only.
5. Add a startup serializer smoke test and an API test covering payment creation through the real URL.

**Acceptance criteria**

- `rg "specific_events|events\.models|event=event|payment\.event" payments` returns only intentional migration history, if retained.
- The payment serializer module imports successfully.
- A course payment can be created in a transaction using a server-derived amount.
- The entire test suite collects successfully.

### P0-02 — The server trusts the client-supplied purchase amount

**Evidence**

`PaymentCreateSerializer` accepts `amount`, and the service uses the submitted value. The canonical price already exists on `Course`.

**Impact**

A client can attempt to buy a paid course for an arbitrary amount. UI restrictions do not protect an API.

**Fix approach**

1. Remove `amount` from the public purchase request.
2. Lock and load the purchasable course on the server.
3. Calculate `original_amount` from the server-side price, validate/apply the coupon under a row lock, then calculate discount, tax if applicable, platform fee, instructor earnings, and final amount in one money-domain service.
4. Store the pricing inputs/snapshot on the payment so later course-price changes do not alter historical records.
5. Use `Decimal` only and define currency-specific rounding rules.

**Acceptance criteria**

- Altering the browser request cannot alter the charge amount.
- Tests cover free, normal, discounted, expired-coupon, and minimum-order cases.
- Platform fee and instructor earnings always sum to the captured amount according to one documented formula.

### P0-03 — Webhook signatures are not verified

**Evidence**

The webhook views parse request JSON and read a signature header but do not cryptographically verify Stripe or PayPal messages.

**Impact**

An attacker can forge payment-success or other provider events. This is a direct financial and entitlement vulnerability.

**Fix approach**

1. Keep the exact raw request body; do not reserialize it before verification.
2. Verify Stripe signatures with the configured endpoint secret and Stripe's supported SDK.
3. Implement PayPal's documented webhook verification flow or its supported SDK.
4. Reject unverifiable messages before any database write.
5. Store provider event IDs with a unique constraint and return success for already-processed duplicates.
6. Process each verified event inside `transaction.atomic()`, lock the target payment, and enforce allowed state transitions.
7. Record sanitized audit metadata, never whole sensitive payloads by default.

**Acceptance criteria**

- Invalid/missing signatures receive an error and cause no state change.
- Replaying a valid event returns a stable successful response without duplicate enrollment, coupon use, or ledger entries.
- Provider contract tests use signed fixtures.

### P0-04 — Payment and fulfillment are disconnected

**Evidence**

Marking a payment successful does not consistently create/reactivate an enrollment. The wallet enrollment path independently creates payment-like records and applies a different fee percentage.

**Impact**

Users can pay without receiving access, or receive access through a different accounting path. Retries can double-charge or duplicate side effects.

**Fix approach**

Create one idempotent application command such as:

```text
fulfill_successful_course_payment(payment_id)
  lock Payment
  verify status == succeeded and target == course
  create/reactivate Enrollment idempotently
  create immutable ledger postings
  redeem coupon once
  record fulfillment timestamp/key
  enqueue email/analytics after commit
```

Card/provider and wallet purchases should both enter this same state machine. The funding mechanism differs; price calculation, ledger, enrollment fulfillment, fee allocation, refunds, and audit rules do not.

**Acceptance criteria**

- One successful payment produces exactly one active enrollment.
- Replaying fulfillment has no additional effect.
- A failed transaction leaves payment, ledger, coupon usage, and enrollment mutually consistent.

### P0-05 — Wallet balances and payouts have multiple sources of truth

**Evidence**

- Wallet-like balances exist in both `accounts.Profile.wallet` and `students.Wallet`.
- Payouts exist in both `payments.Payout` and `instructors.InstructorPayout`.
- Different paths use different balances and different platform fee percentages.
- A student-facing wallet endpoint can add arbitrary funds.

**Impact**

Balances cannot be reconciled reliably. Concurrent requests can lose updates or overspend. The public credit endpoint can create money.

**Fix approach**

1. Immediately disable arbitrary wallet credits outside admin/test-only fixtures.
2. Choose one canonical wallet/balance system and one payout model. Recommended: put all financial records in `payments`; keep student/instructor apps as read-only projections.
3. Introduce an immutable double-entry-style ledger with an idempotency key and references to payment/refund/payout.
4. Treat displayed balance as a ledger-derived or transactionally maintained projection, never an independently editable field.
5. Lock account/ledger projection rows with `select_for_update()` during debit, refund, and payout reservation.
6. Introduce `available`, `pending`, and `reserved` concepts for instructor funds.
7. Encrypt payout account details using an application-managed encryption scheme or store only provider tokens.
8. Backfill and reconcile existing duplicate balances before removing legacy columns/models.

**Acceptance criteria**

- There is one documented source of truth for each user balance and payout.
- Concurrent debit tests cannot make a balance negative or lose an update.
- Every balance change has an immutable reason, actor/source, amount, currency, timestamp, and idempotency key.
- Fee calculation is identical across funding methods.

### P0-06 — Public APIs expose paid lesson content

**Current status:** Remediated for known public catalog aliases on 2026-07-23. Public course detail, module lists, section aliases, slug sections, and module/section lesson lists now emit catalog-safe summaries and restrict unpublished curriculum visibility to owner/admin.

**Evidence**

- `CourseDetailView` uses `CourseDetailModuleSerializer` and `CourseDetailLessonSerializer`, which omit lesson bodies and resource URLs.
- `ModuleListView` now returns `CatalogModuleSerializer` for reads, and `LessonListView` returns `CatalogLessonSummarySerializer` for reads.
- Anonymous and unenrolled tests cover `/modules/`, `/sections/`, slug sections, `/sections/<id>/lessons/`, and `/modules/<id>/lessons/` and assert absence of `content_text`, `video_url`, `metadata`, `resources`, and `file_url`.
- Draft/unpublished course curriculum aliases now return 403 for public users and remain visible to the owner through catalog-safe serializers.

**Impact**

The original unauthenticated paid-content leak is closed for the known course/module/lesson catalog aliases. The remaining operational requirement is to apply the same policy to any new resource/download/recording route before exposing it.

**Fix approach**

1. Split serializers by audience:
   - `CatalogCourseSerializer` / `CatalogLessonSummarySerializer`: IDs, titles, order, duration, preview flag only;
   - `LearningCourseSerializer` / `AccessibleLessonSerializer`: content only after access policy succeeds;
   - management serializers: instructor-only authoring fields.
2. Centralize `can_view_course_catalog(user, course)`, `can_access_course_content(user, course)`, and `can_access_lesson(user, lesson)` policies.
3. Make public module/lesson routes use summary serializers and restrict unpublished courses to owner/admin. Rich lesson routes must require free-preview status, active enrollment, course ownership, or admin.
4. Apply the same policy to resources, recordings, downloads, curriculum, bookmarks, assignment files, and assessment definitions.
5. Inventory routes by representation rather than view name so aliases such as `/modules/`, `/sections/`, and slug/id forms cannot diverge.
6. Avoid relying on a client to hide fields.

**Acceptance criteria**

- Anonymous and unenrolled API snapshots contain no paid content URLs/text/resources.
- Every alias of module, section, lesson, resource, and curriculum endpoints is included in the negative snapshot matrix.
- Active learners, course owners, and admins receive the correct view.
- Revoked/refunded/expired enrollment removes access immediately according to policy.

### P0-07 — Instructors can bypass course moderation

**Current status:** Remediated on 2026-07-21. Generic course create/update no longer accepts `status`; instructor publish attempts through normal payloads are ignored, the admin-only publish endpoint remains protected, and published course lesson mutations are blocked. Covered by `CourseModerationWorkflowAPITest`.

**Evidence**

The course update serializer exposes writable `status`. Course creation forces `draft`, but the update endpoint lets an owner submit `published`. Editing rules also differ among course, module, and lesson endpoints.

**Impact**

An instructor can publish without moderation and can mutate published course content through selected endpoints.

**Fix approach**

1. Remove `status` from generic create/update serializers.
2. Add explicit state-transition commands: `submit_for_review`, `approve`, `reject`, `archive`, and optionally `create_revision`.
3. Define a transition table by role and current state.
4. Enforce one published-editing policy across courses/modules/lessons/resources. Recommended: edits create a draft revision while the published version remains immutable.
5. Record reviewer, timestamp, reason, and old/new state in an audit log.

**Acceptance criteria**

- Generic PATCH cannot change publication state.
- Invalid transitions return a stable 409/validation error.
- Instructor tests prove they cannot approve/publish their own course.
- Published course content does not silently change through module or lesson endpoints.

### P0-08 — Exam ownership and student access controls are missing

**Current status:** Remediated on 2026-07-21. Exam/query ownership checks now scope instructor management by course ownership, students must have active enrollment for student exam actions, and attempt submission is constrained to the authenticated student's own attempt and matching exam. Covered by `ExamAccessControlAPITest`.

**Evidence**

- `ExamListCreateView` is authenticated but does not restrict POST to instructors/admins.
- `ExamDetailView` and `QuestionBankDetailView` do not consistently restrict updates/deletes to owners.
- Analytics, attempt listing, and manual grading check instructor role without checking that the instructor owns the exam/course.
- Exam start paths do not consistently require active enrollment.

**Impact**

Students can create exam data; an instructor can inspect or modify another instructor's exams and grades; unenrolled users can access attempts.

**Fix approach**

1. Implement reusable policy classes/functions for `can_manage_course`, `can_manage_exam`, `can_take_exam`, and `can_grade_attempt`.
2. Filter querysets to objects visible to the requester before lookup; also enforce object permission in mutation services.
3. Require active enrollment and published/available exam windows for student attempts.
4. Cross-check every nested URL object: `attempt.exam_id == exam_id`, question belongs to exam, answer belongs to attempt/question.
5. Add a permission matrix test suite with at least anonymous, unrelated student, enrolled student, unrelated instructor, owning instructor, staff, and superuser.

**Acceptance criteria**

- Unrelated instructors receive 404/403 and cannot infer another instructor's data.
- Students cannot create/update/delete exam definitions.
- Only an eligible enrolled student can start/submit their own attempt.

### P0-09 — Exam payloads disclose correct answers

**Current status:** Remediated on 2026-07-21. Student-facing exam serializers now recursively remove correct-answer and explanation metadata from standard and custom questions while preserving instructor/admin management representations. Covered by `ExamAccessControlAPITest`.

**Evidence**

The exam detail path nests question-bank data including option JSON. That JSON contains correctness information. Visibility flags such as `show_correct_answers` are not consistently enforced.

**Impact**

Students may receive answers before or during an attempt.

**Fix approach**

1. Create separate author, attempt, and result serializers.
2. The attempt serializer must emit opaque option IDs/text only and never correctness, grading notes, or solution data.
3. The result serializer may reveal answers only after the configured release condition.
4. Add negative assertions that serialized student payloads do not contain keys such as `is_correct`, `correct_answer`, or solutions.

**Acceptance criteria**

- A recursive payload test proves answer metadata is absent before release.
- Owners/admins retain a management representation with correct-answer data.

### P0-10 — Assessment/exam scoring has competing algorithms

**Current status:** Remediated on 2026-07-21. Quiz scoring has one authoritative service path, the duplicate submit route was removed, exam scoring includes custom questions and actual marks, and manual grading overwrites per-question marks instead of accumulating on retries. Covered by assessment and exam regression tests.

**Evidence**

- Assessment scoring exists in both `assessments/services.py` and `assessments/services_scoring.py`; one uses question marks and sets `passed`, while the other awards one point and omits equivalent state updates.
- The same quiz-attempt submit URL is registered twice; the latter view is unreachable.
- Exam scoring ignores custom questions, uses `exam.total_marks` rather than the actual selected question marks, and different code paths interpret answers as an option index versus option text.
- Re-running manual grading can add marks again.

**Impact**

Grades depend on the endpoint used and can be wrong or inflated. Some attempt records become incompatible with other analytics code.

**Fix approach**

1. Freeze a versioned answer schema, e.g. `{question_id, selected_option_id}` and a separate structure for free-text/custom answers.
2. Define one authoritative scoring service per assessment type.
3. Store an immutable attempt question snapshot (question text, option ordering, correct answer reference/hash, and marks available) when an attempt starts.
4. Calculate denominator from the attempt snapshot, not a mutable exam field.
5. Make submit atomic and one-way; reject or idempotently return an already-submitted result.
6. Make manual grading an assignment of marks per answer, not an increment of aggregate score.
7. Delete/redirect the duplicate URL and retire duplicate services after regression tests cover legacy behavior.

**Acceptance criteria**

- Every submission path produces the same score for the same snapshot/answers.
- Retrying submit or manual grade does not increase marks.
- Randomized and custom-question attempts are included in score totals.

### P0-11 — Course completion can be awarded prematurely and inconsistently

**Current status:** Remediated on 2026-07-21 for completion correctness. Completion now uses one atomic enrollment evaluator, required progress counts only completed non-free required lessons, course-progress reads no longer award completion, and manual completion requires watch threshold plus assessment requirements. `LessonProgressView.get()` still creates a progress row and remains tracked separately under P1-13.

**Evidence**

- Required-lesson count excludes free lessons, while completed progress can include all lessons; `completed >= required` can therefore complete a course early.
- A client can directly mark a lesson complete without meeting watch/assessment rules.
- A progress GET endpoint mutates enrollment state but does not issue a certificate.
- Completion is recalculated in enrollment, assessment grading, and certificate-related code.

**Impact**

Completion and certificate eligibility vary by call order. Users can self-complete lessons or receive a certificate without required work.

**Fix approach**

1. Define an explicit course-completion policy: required lessons, required quizzes/assignments/exams, thresholds, and treatment of free/preview lessons.
2. Implement one atomic, idempotent command: `evaluate_and_complete_enrollment(enrollment_id)`.
3. Lock the enrollment, compute eligibility from authoritative records, transition once, and record an evidence snapshot/version.
4. Trigger certificate issuance after commit, asynchronously and idempotently.
5. Make GET endpoints read-only. Progress events may be reported by clients, but the server should enforce monotonicity and completion thresholds.
6. Remove or restrict direct “complete lesson” endpoints to trusted internal/instructor actions, if needed.

**Acceptance criteria**

- Preview/free lesson progress cannot satisfy paid required lessons.
- Calling evaluation repeatedly yields one completion timestamp and one certificate.
- GET requests never mutate enrollment state.
- Assessment requirements are enforced before certificate issuance.

### P0-12 — Social-circle endpoints are out of sync with their models and leak private data

**Current status:** Remediated on 2026-07-21. Private circle detail and child resources now require visibility/member policies, general circle serializers no longer expose `join_code`, stale request fields are mapped to the current models, left memberships are reactivated instead of creating duplicates, and last-admin leave is blocked until ownership/admin coverage exists. Covered by `LearningCircleAccessControlAPITest`.

**Evidence**

The social views/services use multiple nonexistent or incorrectly named fields:

- `course_id` is passed while the service reads `course`;
- `parent_id` versus `parent`;
- `reply_to_id` versus `reply_to`;
- goals use `goal_text`, `week_start_date`, `target_hours`, `is_completed`, and `actual_hours` although the model uses a different schema;
- events use `scheduled_time` instead of `scheduled_at`;
- resources use `link`/`uploaded_by` instead of `url`/`shared_by`.

Private circle detail/resources/messages/goals/events do not consistently require active membership, and serializers can expose the join code.

**Impact**

Several create/update paths fail or silently discard relationships. Authenticated non-members can read private group data and secrets.

**Fix approach**

1. Align each request serializer, service signature, and model field; avoid forwarding untyped `**validated_data` across mismatched layers.
2. Add `require_active_circle_member`, `require_circle_moderator`, and `require_circle_admin` policies and apply them consistently.
3. Never include `join_code` in a general detail serializer; expose it through an owner/admin-only action.
4. Make membership rejoin reactivate an existing row rather than violating the uniqueness constraint.
5. Lock the circle during capacity checks.
6. Prevent the last admin/creator from leaving without ownership transfer or circle closure.

**Acceptance criteria**

- CRUD contract tests cover the actual model schema.
- A non-member cannot list/read private circle child objects.
- Join codes are visible only to authorized managers.
- Concurrent joins cannot exceed capacity.

### P0-13 — Live session HTTP and WebSocket authorization is unsafe

**Current status:** Provider integrated and containment hardened on 2026-07-21. HTTP live-session resources now use shared access policies, meeting credentials are only returned to managers or authorized join responses, WebSocket connections are rejected unless the user is authenticated and already authorized for the live session, sender identity is derived server-side, and LiveKit is now the default built-in provider path. Django issues short-lived LiveKit room tokens after enrollment/ownership checks; instructors receive publish/admin grants and students receive subscribe-only grants. Recording/egress automation remains a follow-up.

**Evidence**

- Live session detail/update/delete is broadly authenticated rather than owner-scoped.
- The WebSocket consumer accepts anonymous connections and trusts client messages/sender IDs without checking enrollment, session visibility, participant status, or instructor-only message types.
- JWTs are accepted in query strings.
- The project previously hard-coded `InMemoryChannelLayer`. Settings now select Redis when `REDIS_URL` is present, but silently fall back to in-memory delivery otherwise; production configuration does not fail closed when Redis is absent.

**Impact**

Unauthorized users can observe or inject live-session signaling/chat, impersonate senders, or modify sessions. Multi-process deployment will produce missing messages.

**Fix approach**

1. Authenticate the WebSocket handshake using a secure cookie or a short-lived, one-use WebSocket ticket; avoid durable access tokens in URLs.
2. Authorize the user against the specific session before `group_add`.
3. Derive sender identity from `scope["user"]`; ignore sender identity in client payloads.
4. Validate each message with an explicit schema and allowlist message types by role.
5. Enforce size/rate limits and close connections on invalid behavior.
6. Replace the in-memory layer with Redis in non-local environments.
7. Owner-scope HTTP querysets and mutations.
8. Add integration tests with two students, an unrelated user, the owner, and multiple channel workers.

**Acceptance criteria**

- Anonymous and unauthorized users cannot join the group.
- A student cannot emit instructor-only control/signaling actions or spoof another user.
- Messages work across separate application processes using Redis.

### P0-14 — A parallel quiz-start route bypasses enrollment and publication policy

**Current status:** Remediated on 2026-07-23. The alternate start route now uses the same active-enrollment check and canonical `start_quiz_attempt()` service as the main quiz-start route.

**Evidence**

- The canonical `StartQuizView` loads the quiz, calls `require_active_enrollment()`, and delegates to `start_quiz_attempt()`, which rejects unpublished quizzes.
- `StartQuizAttemptView` now calls `require_active_enrollment()` and delegates to `start_quiz_attempt()` instead of creating attempts directly.
- Both are routed: `/quiz/<id>/start/` and `/quiz/<id>/attempt/start/`.
- Regression tests prove the alternate route returns 403 for an unenrolled student, returns 403 for an unpublished quiz, and still starts an attempt for an enrolled student.
- The incremental answer route belongs to the alternate implementation and writes arbitrary `question_id`/`option_id` pairs into JSON without first proving the question and option belong to the attempt's quiz. Scoring later ignores invalid pairs, but stored attempt evidence is still untrusted.

**Impact**

The direct authorization bypass is closed. Parallel attempt state and incremental-answer evidence validation remain part of P1-10.

**Fix approach**

1. Choose one public attempt API. Recommended: keep the canonical service-backed start/submit flow and remove the duplicate route/views.
2. If incremental answer saving is required, move it behind the same `can_take_quiz()` policy and validate question/option ownership before writing.
3. Scope all attempt reads/mutations to `user=request.user`, active enrollment (or course manager), published quiz/course, and the exact nested quiz.
4. Put eligibility, active-attempt allocation, and attempt limits in one atomic service used by every transport.
5. Add a permission matrix for anonymous, unenrolled student, enrolled student, other instructor, owner, staff, unpublished quiz, canceled enrollment, and completed attempt.

**Acceptance criteria**

- Only one routed start command exists.
- Unenrolled/canceled users and users of unpublished courses cannot create or update attempts.
- Every stored option belongs to the stored question, and every question belongs to the attempt quiz snapshot.
- Concurrent starts cannot allocate more active/total attempts than policy allows.

---

## 5. P1 findings: high-priority correctness and lifecycle work

### P1-01 — Account verification and password reset are incomplete

Registration creates a verification token but users are active immediately and no verification email is sent. Password reset similarly creates a token without a delivery path. Tokens are stored directly and there is no endpoint throttling or access-token revocation strategy after a password change.

Additional current evidence:

- `User.is_active` defaults to `True`, and registration never changes it, so the verification token has no effect on login eligibility.
- Resend-verification requires `IsAuthenticated` but immediately rejects active users as already verified; under the current default, a newly registered user cannot exercise a meaningful resend flow.
- The registration serializer allows anyone to self-select `role="instructor"`, immediately granting instructor permissions even though `InstructorProfile.is_verified` defaults to false and role permissions do not consult it.
- The repository defines no email backend/default sender/task and contains no `send_mail`/email-delivery implementation.
- Password change/reset does not revoke already-issued refresh tokens.

**Approach**

- Decide whether email verification is mandatory. If yes, separate login eligibility/verified status from general record activation.
- Store only a hash of single-use verification/reset tokens, with purpose, expiry, consumed timestamp, and attempt limits.
- Send email after transaction commit through a background task.
- Throttle register/login/reset/verify endpoints by IP and account identity.
- Revoke/blacklist refresh tokens or increment a user token version on password change/reset.
- Avoid revealing whether an email address exists.

### P1-02 — User role and superuser invariants conflict

`create_superuser` does not set the custom `role` to admin. Some permissions rely on Django staff/superuser flags, while others rely on `role`. A superuser can therefore fail admin-role checks or be treated as a student by role-based code.

**Approach**

- Define a single authorization rule: superusers always pass global admin policy; domain roles remain explicit.
- Set/validate the admin role in `create_superuser` if the role is intended to mirror platform administration.
- Add a data migration for existing staff/superusers and tests for all permission classes.
- Prevent unrestricted self-registration as instructor if instructors require approval; introduce an application/approval state.
- Make all admin permission helpers treat `is_superuser`/`is_staff` consistently, or deliberately separate Django administration from platform administration and document that decision.

### P1-03 — API keys exist but are not an authentication mechanism

API keys are modeled and returned in full by list endpoints, but no DRF authentication backend consumes them.

**Approach**

- If API access is not a product feature, remove the model/endpoints.
- Otherwise show the secret once, store only a keyed hash, expose a prefix/last characters for identification, add scopes/expiry/revocation/last-used timestamps, and implement a tested authentication class.
- Never return existing full secrets from a list endpoint.

### P1-04 — Profile data has three competing models

Identity/profile data is split across `accounts.Profile`, `students.StudentProfile`, and `instructors.InstructorProfile`. API profile responses vary by role and code assumes name fields on `User` even though the custom user model does not provide them.

**Approach**

- Make `accounts.Profile` the canonical shared identity record (name, avatar, locale, contact basics).
- Keep student/instructor models only for role-specific domain fields.
- Expose a stable `/me` contract with a shared profile and optional role-specific objects.
- Replace direct `user.first_name`, `user.last_name`, and `user.get_full_name` assumptions with a single tested display-name method/property.
- Backfill before deleting duplicate columns.

### P1-05 — Progress reporting trusts absolute client state

Watch-time APIs accept client-supplied absolute time and can jump directly to the lesson duration. Negative/type checks and capping now exist, but there is no rate/elapsed-time plausibility check and the progress row is not locked before the read-modify-save. This makes the 90% threshold easy to bypass and permits lost updates under concurrency.

**Approach**

- Accept bounded progress events or monotonic checkpoints and reject regressions/unreasonable jumps.
- Cap at authoritative media duration and update with a row lock or an atomic maximum expression.
- Treat watch time as one signal, not proof by itself, where assessments are required.
- Define behavior for videos without known duration and for text lessons.

### P1-06 — Enrollment purchase/reactivation is not safely transactional

The enrollment serializer performs wallet lookup, debit, payment creation, fee allocation, reactivation, and enrollment changes with broad exception handling and best-effort mirrors. Reactivation reporting is calculated incorrectly, and concurrent requests are not locked.

The deep re-audit also found a fail-open branch: if no wallet balance is available, the serializer logs a warning, creates a completed payment, and continues to enrollment without a debit. When a dedicated wallet exists, it attempts to mirror `Profile.wallet` and create `WalletTransaction` inside nested broad `except Exception: pass` blocks. The enrollment path uses a 10% platform fee, while `payments.services.PLATFORM_FEE_RATE` is 20%.

**Approach**

- Move business logic out of the serializer into the unified purchase/fulfillment command.
- Lock purchaser balance, existing enrollment, coupon, and relevant accounting rows.
- Use a client/request idempotency key.
- Remove broad `except Exception` fallbacks and never silently pass failed money writes.
- Return a typed result describing `created`, `reactivated`, or `already_active`.

### P1-07 — Certificate lifecycle was coupled to request transactions

Original issue: PDF generation occurred synchronously near enrollment completion, so a PDF/storage failure could block or roll back a valid completion. The regenerate view also called `regenerate_certificate_pdf` with a signature that did not match the service, and invalid verification codes did not follow the view's expected error flow.

**Current status — remediated on 2026-07-21**

Certificate record issuance is now separated from PDF rendering. `issue_certificate()` creates or reuses the certificate record inside the transaction and schedules document rendering after commit; rendering is idempotent and logs failures instead of rolling back enrollment completion or certificate creation. The regenerate endpoint now uses the service contract correctly, staff-only regeneration forces a fresh render, and invalid verification codes return a deliberate invalid/404 response.

This does not yet introduce a Celery-backed certificate rendering worker or a persisted generation-status/error model. Those remain useful operational upgrades under the broader background-task and observability work, but the request-transaction coupling and broken view/service contract are fixed.

**Approach**

- Completed: separate certificate record issuance from document rendering.
- Completed: create/reuse the certificate record atomically and schedule PDF rendering with `transaction.on_commit`.
- Completed: make rendering idempotent for normal render/regenerate paths.
- Completed: correct the regenerate service contract and cover it with API tests.
- Completed: map invalid verification codes to a deliberate invalid response.
- Remaining operational hardening: move rendering to a Celery task, persist generation status/error for admin retry visibility, and use `F()` updates for simple certificate counters.

### P1-08 — Certificate grade calculation was not defensible

Original issue: grade calculation aggregated all quiz attempts rather than an explicit best/latest policy, mixed assignment data without clear weights, and defaulted to 100 when no assessments existed.

**Current status — remediated on 2026-07-21**

The immediate certificate-grade policy is now deterministic and safer: use the best completed attempt per published quiz, use graded assignment submissions, cap earned points to the assessment maximum, calculate `earned / possible * 100`, and return `None` when no graded assessment evidence exists. Certificates therefore no longer print a fake perfect grade for courses without assessed work, and repeated quiz attempts no longer inflate or dilute a learner's certificate grade.

This is a pragmatic policy-level fix. The later product-grade version should still snapshot the exact grading/evidence policy at course publication or certificate issuance so historical certificates remain explainable after curriculum edits.

**Approach**

- Completed: explicitly define the current points-based calculation in `calculate_course_grade()`.
- Completed: choose best completed attempt per published quiz.
- Completed: include graded assignment submissions and ignore ungraded work.
- Completed: return no grade when there is no graded assessment evidence instead of defaulting to 100%.
- Remaining product hardening: version the grading policy at course publication time and store the completion/grade evidence snapshot used for each certificate.

### P1-09 — Assignment and quiz management permit invalid mutations

**Current status:** Partially remediated on 2026-07-23. Learner submission by lesson no longer creates an `Assignment` when one is missing, quiz-management GET no longer creates quiz definitions, and quiz question replacement is rejected after attempts exist. Objective-question validation, upload policy, resubmission grading semantics, and product-grade quiz versioning/snapshots remain open.

The learner-facing by-lesson submission endpoint no longer creates an `Assignment` automatically when one is missing, reading quiz-management state is now read-only, and attempted quizzes are protected from question replacement. Remaining assessment-authoring risk is concentrated in validation, upload policy, resubmission grading semantics, and formal versioned snapshots. File uploads lack a clear server-enforced type/size/storage policy.

**Evidence**

- `SubmitAssignmentByLessonView` previously called `Assignment.objects.get_or_create()` after checking only student enrollment. It now performs a lookup only and returns `{"error": "Assignment not found for this lesson."}` with HTTP 404 when no instructor-created assignment exists.
- `ManageQuizView.get()` previously created a quiz as a side effect of GET. It now returns `{"error": "Quiz not found for this lesson."}` with HTTP 404 when no quiz exists; POST remains the explicit creation/update command.
- `ManageQuizView.post()` previously executed `quiz.questions.all().delete()` before recreating questions. It now rejects question replacement with HTTP 409 once attempts exist, preserving existing question rows and attempt answer evidence. Full versioning/snapshot support remains a follow-up.
- Uploaded file names are embedded directly in a storage path and saved without explicit size, MIME, extension, quarantine, or malware-scanning policy.
- Resubmission uses `update_or_create()` but does not clear the prior grade, feedback, grader, or graded timestamp; a changed submission can remain graded with stale feedback.
- Raw dictionaries are accepted without serializer validation. A question may have no correct option, multiple correct options, empty text/options, invalid question type, invalid passing percentage, or inconsistent total marks.

**Approach**

- Only course managers may create curriculum assessments.
- Completed: make quiz-management GET read-only; use explicit POST to create a quiz definition.
- Completed: reject question replacement after attempts exist so existing rows referenced by historical attempts are not deleted.
- Remaining: snapshot attempt questions/answers and support product-grade quiz versions for future edits.
- Validate that objective questions have exactly the permitted correct-option configuration.
- Generate storage keys server-side and validate file size, content type, extension, and malware-scanning status.
- Prefer direct-to-object-storage signed uploads with a finalized-upload record.
- On resubmission, deliberately clear grade/feedback/grader state or create a versioned submission attempt according to product policy.

**Acceptance criteria**

- A learner cannot create or edit an assignment definition through the by-lesson submission route.
- A learner cannot create or edit a quiz definition through any submission route.
- Quiz-management GET never creates a quiz.
- Editing quiz questions after attempts exist is rejected; full versioned editing remains future work.
- Invalid objective-question shapes are rejected atomically without deleting existing valid content.
- Assignment upload and resubmission behavior is explicitly tested.

### P1-10 — Attempt count and concurrency invariants are ineffective

Quiz attempts can be created through different paths with incompatible assumptions. Exam attempt uniqueness includes `started_at`, which does not enforce a meaningful business rule. Concurrent starts can exceed maximum attempts.

**Approach**

- Define whether one active attempt is allowed and how maximum attempts are counted.
- Add conditional database constraints where possible (e.g. one active attempt per user/exam).
- Lock the user/exam enrollment or a dedicated attempt-counter row while allocating an attempt number.
- Replace timestamp-based uniqueness with `(user, exam, attempt_number)`.
- Make submit idempotent under two concurrent requests by locking the attempt and accepting only an allowed one-way transition.

The canonical quiz service currently behaves as one lifetime attempt per user/quiz because `get_or_create(quiz, user)` has no completion filter, while the alternate route behaves as one active attempt and permits new attempts after completion. Exam start counts attempts in application code before insert, so two concurrent transactions can both pass `max_attempts`. These are product-policy differences, not merely implementation details.

### P1-11 — Live polling, attendance, and counters drift

Changing a poll vote deletes the old vote without decrementing the old option count. Questions can be upvoted repeatedly. Ending a session does not reliably finalize duration for still-connected participants before calculating attendance. Several counters use read-modify-save operations.

**Approach**

- Use unique vote/upvote rows and derive or atomically maintain counters.
- Make vote changes one transaction that locks affected options.
- Finalize participant leave/duration before attendance calculation.
- Use `F()` expressions for simple counters and reconciliation jobs for projections.

### P1-12 — Refund and payout invariants are incomplete

Refunds do not clearly prevent cumulative over-refunding or consistently reverse enrollment/ledger/payout effects. Payouts can select whole payments whose sum exceeds the requested amount, and concurrent requests can reserve the same earnings.

**Approach**

- Track refundable and refunded amount from immutable ledger allocations.
- Lock the payment while accepting a refund and enforce cumulative total `<= captured amount`.
- Define access policy for full/partial refund and execute entitlement changes as part of fulfillment reversal.
- Model payout allocations explicitly rather than attaching arbitrary whole payments.
- Reserve earnings transactionally before provider payout; release or retry reservations on failure.

### P1-13 — GET requests and serializers have side effects or unsafe logging

Course progress and live-session list requests mutate state. Course update error handling logs the full request body. Some views return raw exception strings.

Current examples include `LessonProgressView.get()` creating a progress row, `ManageQuizView.get()` creating a quiz, and `LiveSessionListView.get_queryset()` advancing scheduled/live/ended states. Payment webhook logs persist full provider payload JSON, and many payment/live views expose `str(exception)` directly to clients.

**Approach**

- Make GET/HEAD strictly read-only.
- Move lifecycle advancement to explicit commands, domain events, or scheduled tasks.
- Log request IDs, actor ID, resource ID, error class, and safe context—not full content, tokens, addresses, or provider payloads.
- Return stable public error codes/messages and capture detailed exceptions only in server logs/error monitoring.

### P1-14 — Routed course and assessment endpoints have verified API/model drift

**Current status:** Remediated on 2026-07-23. The three originally probed non-payment endpoints now have real URL regression tests and return stable successful responses for valid authorized requests.

Three non-payment endpoints previously returned HTTP 500 under ordinary valid setup:

1. `ResumeLearningView` calls `require_active_enrollment(user, course_id)` with an integer. The service expects a `Course` and reads `course.instructor`.
2. `AdminCourseStatsView` calculates revenue using `Sum('amount_paid')`, but `Enrollment` has no `amount_paid` field.
3. `get_quiz_question_analytics()` reads `QuizQuestion.correct_answer`, but correctness lives on `QuestionOption.is_correct`.

The full suite did not cover these routes when the drift was found. They were confirmed with authenticated runtime probes against a migrated isolated database; each returned HTTP 500.

**Approach**

- Completed: resume loads the course, authorizes through `require_active_enrollment()`, and uses the correct progression helper.
- Completed: admin course revenue is derived from completed `Payment.amount`, not enrollment rows.
- Completed: quiz question analytics uses selected option IDs and `QuestionOption.is_correct`.
- Completed: API tests cover the real URLs for resume, admin course stats, and question analytics.
- Remaining analytics hardening: distinguish unanswered from wrong more explicitly in the public contract and decide whether in-progress attempts should be included.
- Add schema-generation/import smoke tests so nonexistent serializer/model fields fail CI early.

**Acceptance criteria**

- All three routes return a documented response for valid authorized requests.
- No analytics query references fields absent from migrations/models.
- Revenue, question correctness, and resume position each use the domain's canonical source of truth.

---

## 6. P2 findings: maintainability, performance, and product completion

### P2-01 — Course versioning exists but is not integrated

The version model does not drive the authoring/publishing workflow. Use it as the basis for immutable published snapshots, or remove it until the product needs revisions. A half-integrated version model adds complexity without protecting published content.

### P2-02 — Query patterns will produce N+1 and expensive aggregate work

Nested course serializers and dashboard statistics call counts/ratings per object. Apply `select_related`, `prefetch_related`, annotated aggregates, and query-budget tests to list endpoints. Validate allowed ordering fields instead of passing arbitrary values to `order_by()`.

### P2-03 — Denormalized student/instructor stats become stale

Profile statistics are updated on selected paths or profile creation and do not reflect every domain change. Prefer query-time aggregates for low-volume dashboards or explicit projection tables updated from transactional outbox events, with a reconciliation command.

### P2-04 — Analytics code is not contract-tested

The immediate 500-level defects are promoted to P1-14. Beyond those crashes, analytics definitions remain inconsistent: some averages include incomplete attempts, question analytics cannot reliably distinguish unanswered/wrong without an attempt snapshot, enrollment analytics derives progress repeatedly in Python, and denormalized counters can disagree with source rows. Define metric names, numerator/denominator, inclusion windows, and source records; then cover every analytics endpoint with database and query-budget tests.

### P2-05 — Background-task configuration is incomplete

Celery is configured with Redis defaults, but `CELERY_BEAT_SCHEDULE` is empty and no application task modules are present. Certificate rendering currently runs from an `on_commit` callback in the web process, and live-session state is advanced by GET requests. Use tasks for email, certificate rendering, recording processing, reconciliation, and lifecycle scheduling. Tasks must be idempotent, receive record IDs rather than serialized model objects, record retry/failure state, and be monitored.

### P2-06 — WebRTC architecture is suitable only for a narrow prototype

LiveKit is now the selected SFU/provider and Django issues policy-checked, short-lived room tokens. That is the correct direction. Production completeness still requires verified LiveKit deployment credentials, webhook verification, disconnect/revocation behavior, room cleanup, recording/egress orchestration, TURN/network validation, token TTL/replay decisions, and load tests. Remove or explicitly isolate legacy browser peer-to-peer signaling so two competing media topologies do not remain active.

### P2-07 — API and frontend contracts have drifted

Template JavaScript calls several routes or shapes that are not present in the backend:

- assessment pages call `/assessments/attempts/...` and `/assessments/<id>/start-attempt/`, while routed assessment URLs are quiz/assignment-specific;
- payment pages call `/payments/checkout/` and `/payments/transactions/...`, while the backend exposes `/payments/create/` and payment-ID routes;
- resource/discussion/search templates call applications/endpoints that are not installed or routed;
- an enrollment certificate link is used even though certificate routes live under `/api/certificates/`;
- account tests prepend `/api/accounts/api/...`, while the real include is already `/api/accounts/`.

Introduce an OpenAPI schema, validate it in CI, test URL reversing instead of hardcoded test strings, and centralize/generate the first-party client instead of embedding ad hoc URL strings in templates.

### P2-08 — Database constraints do not encode important domain invariants

Most constraints are legacy `unique_together` declarations; critical numeric/state relationships are application-only. Examples include course price versus `is_free`, passing percentages, quiz/exam marks, lesson/module position uniqueness, poll vote cardinality, provider payment IDs, payout/refund totals, and cross-field enrollment completion state.

Add constraints only after reconciliation/backfill. Prioritize uniqueness/checks that protect money, entitlement, one-active-attempt rules, and immutable evidence. Serializer validation remains necessary for friendly errors, but it is not a concurrency boundary.

### P2-09 — Error contracts, throttling, health checks, and observability are absent

There is no DRF throttling configuration, no health/readiness endpoint, no structured logging configuration, and no error-monitoring integration. Several views catch broad exceptions and return raw messages; the instructor dashboard prints tracebacks to stdout and returns HTTP 200 with fabricated zero values when internal queries fail.

Define a stable error envelope/codes, let unexpected errors reach centralized monitoring, add request/correlation IDs, configure endpoint-specific throttles, and expose liveness/readiness separately. Dashboard partial-data behavior should be explicit and observable rather than silently indistinguishable from real zero activity.

---

## 7. Target backend shape

This does not require splitting into microservices. A well-structured Django monolith is the best near-term target.

### 7.1 Application boundaries

| Domain | Owns | Must not own |
|---|---|---|
| Accounts | authentication identity, shared profile, roles, token lifecycle | wallets, payouts, course progress |
| Courses | catalog, authoring, content versions, publication state | payment capture, student balances |
| Learning | enrollment, lesson progress, completion policy/evidence | provider payment implementation |
| Assessments | assessment definitions, versioned attempts, answers, scoring | direct certificate generation |
| Payments | price snapshot, payments, ledger, coupons, refunds, payout allocations | course content mutation |
| Certificates | eligibility result reference, certificate record, rendering/verification | recomputing all progress independently |
| Social | circles/posts/messages with membership policy | authentication/session implementation |
| Live | session scheduling, participation, signaling policy, recordings | general course ownership rules duplicated locally |

The existing app names can remain; the important change is a single owner for each invariant.

### 7.2 Command/query separation

Views and serializers should validate transport data and call an application command. Commands own mutations and transactions. Query services construct authorized, optimized querysets/representations.

Example:

```python
@transaction.atomic
def start_exam_attempt(*, exam_id: int, user: User) -> ExamAttempt:
    exam = get_exam_locked_for_attempt(exam_id, user=user)
    assert_can_take_exam(user, exam)
    enforce_attempt_limit(exam, user)
    return create_attempt_from_snapshot(exam, user)
```

Do not put a multi-model purchase, grading, or completion workflow inside a serializer's `create()` method.

### 7.3 Authorization policy

Create small, reusable policies and apply them twice where necessary:

1. **queryset scoping** prevents discovery/listing;
2. **command/object assertion** prevents unauthorized mutation even if called outside the view.

Minimum policies:

- `is_platform_admin(user)`
- `can_manage_course(user, course)`
- `has_active_enrollment(user, course)`
- `can_access_lesson(user, lesson)`
- `can_manage_assessment(user, assessment)`
- `can_take_assessment(user, assessment)`
- `can_grade_attempt(user, attempt)`
- `is_active_circle_member(user, circle)` / `can_manage_circle(...)`
- `can_join_live_session(user, session)` / `can_manage_live_session(...)`

### 7.4 Transaction and side-effect policy

- Use `transaction.atomic()` for each business command.
- Use `select_for_update()` for balance, attempt-limit, capacity, coupon-usage, refund, fulfillment, completion, and payout-reservation decisions.
- Put external calls and slow rendering outside database transactions.
- Use `transaction.on_commit()` to enqueue notifications/rendering.
- Add idempotency keys for payment creation/fulfillment, webhook processing, refunds, payouts, certificate issuance, and retryable tasks.
- For reliable async publication, add a transactional outbox instead of enqueueing before commit.

### 7.5 API contract policy

- Add `/api/v1/` before making breaking corrections, or explicitly coordinate one breaking cutover.
- Generate an OpenAPI schema and make schema generation fail CI on serializer errors.
- Standardize error responses, pagination, filtering, ordering allowlists, and timezone handling.
- Separate list/detail/management/student-result serializers rather than conditionally leaking fields from one serializer.

---

## 8. Data consolidation and migration plan

The wallet/profile/payout cleanup must be treated as a data migration, not a model rename.

### Step 1 — Inventory and reconcile

Create read-only management commands/reports that identify:

- users with mismatched `Profile.wallet` and `students.Wallet.balance`;
- instructors represented in both payout models;
- successful payments without active enrollments and active paid enrollments without successful payment/ledger evidence;
- duplicate or over-refunded payments;
- duplicate active quiz/exam attempts;
- completed enrollments without certificates and certificates without valid completion evidence;
- circle rows with invalid state, orphaned resources, or missing admins.

Export reconciliation results before changing data.

### Step 2 — Add canonical structures

Add ledger accounts/entries, payment fulfillment markers, payout allocations/reservations, attempt numbers/snapshots, and completion evidence fields. Add nullable fields and non-destructive constraints first.

### Step 3 — Backfill deterministically

Write idempotent, batched management commands. Each should support dry-run, resume/cursor, counts, and a reconciliation checksum. Never infer financial truth silently where sources disagree; emit an exception report for manual resolution.

### Step 4 — Switch reads, then writes

Deploy code that reads canonical data with telemetry for fallback hits. Move all writes to canonical services. If a short dual-write period is unavoidable, make the canonical write authoritative and alert on mirror failures.

### Step 5 — Enforce constraints

After data is clean, add unique/check constraints such as:

- unique provider event ID per provider;
- unique provider payment ID when present;
- nonnegative ledger projection balances where overdraft is forbidden;
- one fulfillment per payment;
- one certificate per enrollment/course policy;
- unique attempt number per user/exam;
- conditional one-active-attempt rule;
- refund allocation total enforced in command logic and reconciliation.

### Step 6 — Remove legacy state

Only after at least one verified release should legacy wallet/payout fields/models and compatibility code be removed. Keep an auditable migration record and rollback plan.

---

## 9. Testing strategy

### 9.1 Establish a runnable baseline

A runnable local `.venv` now exists and isolated SQLite migrations/checks/tests execute. The baseline is not green or reproducible from a clean clone: `requirements.txt` is UTF-16, the full suite is red, the payment test module cannot import, and no lockfile or CI validates installation. Convert dependencies to UTF-8, use a supported Python version for Django 6, and prefer a `pyproject.toml` plus a locked dependency artifact. Do not reuse or commit the tracked platform-specific environment.

Current test triage:

| Result | Count | Meaning |
|---|---:|---|
| Authored `test_*` methods | 241 | Source inventory across backend test modules. |
| Discovered by `manage.py test` | 227 | The payment module import failure replaces its 15 tests with one loader error. |
| Passing | 214 | Useful regression base, especially recent course/exam/completion/certificate/social/live fixes. |
| Failing | 12 | Account tests call stale `/api/accounts/api/...` URLs and receive 404. |
| Loader errors | 1 | `payments.tests` imports removed `events.models.Event`. |

Baseline CI commands should include:

```bash
python -m compileall -q accounts assessments certificates core courses enrollments exams instructors live payments skillstudio social students
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py test
```

Add coverage, linting, and formatting after the suite runs. A reasonable initial coverage gate is based on the measured baseline, followed by a ratchet; require high branch coverage for permissions, pricing, ledger, scoring, completion, and webhooks.

Before accepting the suite as a gate, add direct regressions for the six runtime probes in this review; otherwise a green subset can coexist with publicly exposed content and routed 500s.

### 9.2 Required test layers

1. **Model/constraint tests:** uniqueness, checks, transition invariants.
2. **Service tests:** money, grading, completion, refund, payout, and concurrency rules.
3. **API contract tests:** serializer fields, status/error shape, nested object validation.
4. **Permission matrix tests:** every sensitive object against relevant roles/ownership/enrollment.
5. **Idempotency tests:** repeated payment, webhook, fulfillment, submit, completion, certificate, refund, and payout calls.
6. **Concurrency tests:** two debits, joins, attempt starts, coupon redemptions, refunds, and payout reservations against PostgreSQL.
7. **WebSocket integration tests:** handshake authorization, group isolation, spoof prevention, rate/size validation.
8. **Migration tests:** upgrade a representative pre-fix database and validate reconciliation.

### 9.3 Essential adversarial cases

- student attempts to publish a course or create an exam;
- instructor A reads/grades/deletes instructor B's objects;
- anonymous user requests paid lesson/resource/recording data;
- client submits a payment amount lower than course price;
- forged and replayed provider webhook;
- two simultaneous wallet debits or payout requests;
- repeated manual grade and repeated exam submit;
- completion using only free/preview lessons;
- private-circle child-resource access by a non-member;
- anonymous WebSocket connection and spoofed sender ID.

---

## 10. Security and operational hardening

### Repository and secrets

The repository tracks `.env`, a platform-specific virtual environment, bytecode, and cache artifacts despite ignore rules. Ignore rules do not untrack existing files.

1. Rotate every credential that has ever been present in the tracked `.env` or git history.
2. Remove `.env`, `venv`, `__pycache__`, and `*.pyc` from version control using index-only removal; do not delete a developer's local environment as part of the cleanup.
3. If the repository has been shared, evaluate history rewriting with the team. Rotation is required even if history is rewritten.
4. Commit `.env.example` containing names and safe placeholders only.
5. Add automated secret scanning and dependency vulnerability scanning in CI.

### Django settings

- Remove duplicate `SECRET_KEY`, `DEBUG`, and CORS assignments.
- Fail startup when production secrets/allowed hosts/database settings are missing.
- Never use an insecure fallback secret outside local/test settings.
- Replace `CORS_ALLOW_ALL_ORIGINS=True` with an explicit origin allowlist. Combining allow-all behavior with credentials is unsafe.
- Split settings into base/local/test/production or use one validated environment settings layer.
- Configure secure cookies, SSL redirect/proxy headers, HSTS, content-type/nosniff/referrer protections, trusted CSRF origins, upload limits, and production logging.
- Use Redis for Channels and configure cache/task broker isolation appropriately.

### Tokens and browser authentication

The templates store JWTs in `localStorage`, which increases impact of an XSS defect. Prefer secure, `HttpOnly`, `SameSite` cookies with CSRF protection for the first-party browser application, or document and harden a deliberate bearer-token design. Keep access tokens short-lived and rotate/revoke refresh tokens.

### Observability

- Add structured JSON logs with request/correlation ID and actor/resource IDs.
- Add error monitoring and alerting for payment webhook failures, fulfillment lag, task retries, reconciliation mismatches, and permission denials.
- Add health/readiness endpoints for database, Redis, worker, migrations, and storage dependencies.
- Define backup/restore tests for PostgreSQL and certificate/media storage.

---

## 11. Repository and deployment baseline

The repository currently lacks a Dockerfile/process declaration/CI workflow and has no verified clean-clone installation path. A local `.venv` proves that the code can run on this host, but the repository still tracks `.env`, 5,965 `venv/` files (about 54 MB), and 158 bytecode/cache files. Ignore rules are present but do not untrack them.

Recommended baseline:

- UTF-8 dependency metadata with deterministic locking;
- local development composition for PostgreSQL and Redis;
- separate web, worker, and scheduler processes;
- ASGI server configuration appropriate for Django Channels;
- environment validation at startup;
- CI on every PR with PostgreSQL and Redis services;
- migration step separated from application rollout;
- static/media storage configuration and retention policy;
- production runbook for rollback, webhook replay, ledger reconciliation, and certificate rerendering.

Do not use SQLite as the only CI database because locking, constraints, and concurrency behavior need PostgreSQL coverage.

---

## 12. Recommended implementation sequence

Estimates are relative and assume one experienced backend engineer with review support. Previously remediated exam, moderation, completion, social, live-containment, and certificate work should remain in place; the sequence below starts from the newly audited state.

### Phase 0 — Security/repository gate and trustworthy test baseline (1–3 engineering days)

1. Rotate credentials from the tracked `.env`; untrack `.env`, `venv/`, bytecode, and caches without deleting local developer files.
2. Add a safe `.env.example`; remove the insecure production secret fallback; convert dependency metadata to UTF-8 and lock it.
3. Remove remaining event references so payment serializers import and payment tests collect.
4. Correct account test URLs using `reverse()` and add serializer/schema import smoke tests.
5. Add CI with PostgreSQL and Redis services, full tests, `check --deploy`, migration drift, secret scan, and dependency scan.

**Exit gate:** clean clone/install succeeds; all 241+ intended tests collect; full suite and deployment checks are green; no real secret/generated environment is tracked.

### Phase 1 — Immediate non-payment containment (2–5 engineering days)

1. **Completed P0-06:** public module/lesson catalog aliases use safe summaries and share course catalog visibility policy.
2. **Completed P0-14:** alternate quiz start delegates to the canonical eligibility/attempt service.
3. **Completed P1-14:** course resume and analytics 500s have real URL tests and model-aligned implementations.
4. **Partially completed P1-09:** student-by-lesson assignment submission no longer creates assignments; quiz-management GET is read-only; question replacement is rejected after attempts exist.
5. **Next P1-09/P1-10 work:** validate quiz definitions, define upload/resubmission policy, add product-grade attempt snapshots/versioning, and enforce attempt allocation under lock.
6. Lock down upload type/size/storage policy and remove raw exception responses in the touched surfaces.

**Exit gate:** anonymous/unenrolled content and attempt adversarial matrices pass; assessment history is reproducible; the verified course/assessment 500s are gone.

### Phase 2 — Payment and entitlement containment (4–8 engineering days; currently deferred, but mandatory for release)

1. Disable student self-credit and fail-open enrollment purchase paths.
2. Remove client-controlled price and all event drift; snapshot server-derived pricing with one fee formula.
3. Verify Stripe/PayPal signatures and make provider-event processing idempotent.
4. Implement one payment state machine and idempotent fulfillment/reversal command connecting payment, enrollment, coupon, and ledger.
5. Stop new writes through duplicate wallet/payout models and add reconciliation reports.

**Exit gate:** forged/replayed webhooks do nothing; price cannot be altered by the client; one captured payment creates exactly one entitlement and ledger result; concurrent financial tests pass on PostgreSQL.

### Phase 3 — Account and lifecycle correctness (about 1 engineering week)

1. Implement real verification/reset delivery, token hashing/consumption, throttling, and refresh-token revocation.
2. Resolve role/staff/superuser and instructor-approval policy; migrate inconsistent users.
3. Consolidate shared profile/name contracts and remove unsupported API-key behavior or implement it securely.
4. Add immutable attempt/completion/certificate evidence versions and persisted certificate render status.
5. Fix live poll/attendance/counter state and move state transitions off GET.

**Exit gate:** account and lifecycle transitions have one policy, one transactional command, and idempotent tests.

### Phase 4 — Data consolidation and production reliability (1–2 engineering weeks plus reconciliation)

1. Add canonical ledger/payout allocations and reconcile/backfill duplicate financial state.
2. Enforce post-backfill database constraints and retire legacy writes.
3. Add Celery/outbox tasks, Redis multi-process tests, LiveKit webhook/egress operations, and storage lifecycle policy.
4. Publish OpenAPI v1 and align all template/client routes.
5. Add throttling, structured logs, monitoring, readiness, query budgets, backup/restore, webhook replay, reconciliation, and rollback runbooks.

**Exit gate:** reconciliation has zero unexplained differences, client/schema contracts agree, and deployment/rollback/restore/multi-process tests pass in staging.

---

## 13. Suggested pull-request breakdown

Keep each PR deployable and narrowly reviewable. The next recommended PRs from the current state are:

1. **PR A — Close the paid-content boundary**
   Central course-content policy; catalog/learning/management serializers on every alias; negative payload matrix for anonymous, unenrolled, canceled, enrolled, owner, and admin users.

2. **PR B — One assessment attempt/authoring path**
   Remove duplicate start route; validate incremental answers; prevent learner curriculum mutation; version or freeze quiz questions; resubmission and upload policy tests.

3. **PR C — Repair routed contract drift**
   Course resume and analytics fixes, account URL tests via `reverse()`, serializer/schema smoke tests, documented errors.

4. **PR D — Repository hygiene and CI**
   Credential rotation support, untrack generated files, UTF-8 locked dependencies, PostgreSQL/Redis CI, deploy/migration/secret/dependency checks.

5. **PR E — Payment contract and wallet containment**
   Remove event drift and client amount, disable self-credit/fail-open purchase, server pricing, one fee formula, reconciliation report.

6. **PR F — Verified webhooks and fulfillment**
   Provider verification, event dedupe, state machine, ledger postings, enrollment fulfillment/reversal.

7. **PR G — Account lifecycle and authorization invariants**
   Verification/reset delivery, throttling/revocation, role/staff policy, instructor approval, API-key decision.

8. **PR H — Data consolidation and production operations**
   Ledger/payout/profile migrations, constraints, Celery/outbox, LiveKit operations, OpenAPI/client alignment, monitoring/runbooks.

Already-completed remediation work for moderation, exam ownership/answer disclosure/scoring, course completion, social privacy, live HTTP/WebSocket containment/provider tokens, and certificate issuance/grade calculation should be treated as regression-protected foundations, not repeated projects.

---

## 14. Definition of done

The backend should not be called production-ready until all of the following are true:

- clean clone/install/start/test works on a documented supported toolchain;
- no real secrets or generated environment artifacts are tracked;
- all P0 permission, data-exposure, payment, webhook, scoring, and completion tests pass;
- one source of truth exists for wallets, payouts, profiles, scoring, and completion;
- every money/lifecycle command is atomic and idempotent where retries are possible;
- successful payment, enrollment access, refund/revocation, completion, and certificate state reconcile;
- object-level authorization is tested across roles and ownership boundaries;
- student payloads cannot reveal paid content or correct answers early;
- GET requests are side-effect free;
- Redis-backed Channels works across processes and WebSockets authenticate/authorize per session;
- schema generation, deployment checks, migrations, tests, secret scan, and dependency scan run in CI;
- staging has verified backup/restore, rollback, webhook replay, and reconciliation procedures;
- OpenAPI and the first-party web client agree on paths and response shapes.

---

## 15. What is already worth preserving

The project has useful foundations: domain-specific Django apps, a custom user model established early, PostgreSQL targeting, DRF serializers/views, explicit service modules in several domains, broad feature modeling, and a meaningful body of tests. The recommended work is not a rewrite. The safest path is to retain the Django monolith and existing models where they correctly express the domain, then replace competing mutation paths with one policy-controlled, transactional implementation at a time.

The key engineering rule for the remediation is simple: **each critical business fact must have one owner and one tested way to change it.**
