# SkillStudio Backend Review and Remediation Plan

**Review date:** 2026-07-21  
**Last remediation update:** 2026-07-21  
**Scope:** Django project configuration and all backend applications: `accounts`, `courses`, `enrollments`, `assessments`, `exams`, `certificates`, `students`, `instructors`, `social`, `live`, `payments`, and `core`.

## 1. Executive summary

The backend is a substantial prototype with a broad feature set, meaningful model coverage, and a sizeable test directory. It is not currently safe to deploy as a production learning and payments platform.

The main concern is not style or isolated technical debt. Several core workflows have two or more competing sources of truth, and some public API paths either bypass authorization or do not match the current models. The highest-risk areas are:

1. **Payments are currently broken and insecure.** The main payment creation service still supplies a deleted `event` model field, webhook signatures are not verified, the client supplies the purchase amount, and successful payments do not reliably grant enrollment.
2. **Object-level authorization is missing from several instructor, exam, live-session, social, and WebSocket operations.** A role check is not sufficient when one instructor must not modify another instructor's data.
3. **Paid course content exposure was remediated.** Public course/module responses now use catalog-safe lesson summaries rather than full paid lesson payloads.
4. **Financial state has competing implementations.** There are two wallet representations and two payout models. Fee calculations also differ between workflows. This makes balance correctness and reconciliation impossible to guarantee.
5. **Course completion and scoring were consolidated.** Completion now has one evaluator and assessment/exam scoring has one authoritative path per assessment type; certificate rendering/operational concerns still need later hardening.
6. **Several endpoints have direct model/API drift.** The payments and social modules reference deleted or nonexistent fields, one certificate action calls its service with the wrong arguments, assessment routes collide, and assessment analytics references a nonexistent model field.
7. **The repository is not fully reproducible or hygienic.** A real `.env`, a Windows virtual environment, bytecode, and caches are tracked. A fresh local `.venv` was created and ignored for testing, but the dependency file is still UTF-16, there is no CI pipeline, and the checked-in virtual environment cannot be used on the current host.

### Remediation status as of 2026-07-21

| Finding | Status | Implemented change | Verification |
|---|---|---|---|
| P0-06 paid lesson content exposure | Remediated | Public course detail now uses catalog-safe module/lesson serializers; paid `content_text`, `video_url`, `metadata`, resources, and file URLs are not emitted from the public course detail response. | `courses.tests.CourseDetailContentExposureTest`; included in `courses enrollments assessments exams certificates` suite. |
| P0-07 moderation bypass | Remediated | Generic course create/update no longer accepts writable `status`; instructors cannot publish through normal payloads; published/archived course content cannot be changed through course/module/lesson authoring endpoints. | `courses.tests.CourseModerationWorkflowAPITest`; included in `courses enrollments assessments exams certificates` suite. |
| P0-08 exam ownership/access | Remediated | Exam/question querysets and instructor endpoints are scoped by course ownership; students must be actively enrolled to view/start/submit exams and can only submit their own attempts. | `exams.tests.ExamAccessControlAPITest`; included in `courses enrollments assessments exams certificates` suite. |
| P0-09 exam answer disclosure | Remediated | Student exam serializers recursively strip answer metadata such as `is_correct`, `correct_answer`, `answer`, model answers, and explanations from standard and custom questions. | `exams.tests.ExamAccessControlAPITest`; included in `courses enrollments assessments exams certificates` suite. |
| P0-10 assessment/exam scoring drift | Remediated | Quiz scoring now delegates to one service; the duplicate quiz-submit URL was removed; exam scoring uses actual question/custom-question marks and manual grading overwrites marks rather than adding repeatedly. | Assessment/exam regression tests; included in `courses enrollments assessments exams certificates` suite. |
| P0-11 premature/inconsistent completion | Remediated | Required lesson progress is computed from non-free required lessons only; completion uses one atomic evaluator; GET progress is read-only; manual lesson completion requires watch threshold and assessment requirements. | Enrollment regression tests; included in `courses enrollments assessments exams certificates` suite. |

Latest verification command:

```bash
DATABASE_URL=sqlite:////private/tmp/skillstudio-test.sqlite3 .venv/bin/python manage.py test courses enrollments assessments exams certificates
```

Latest result:

```text
Ran 105 tests in 33.542s

OK
```

Additional checks passed: `git diff --check`, focused `py_compile` for touched modules, and `.venv/bin/python manage.py check`. The only remaining check warning is the existing missing static directory warning: `staticfiles.W004`.

### Overall assessment

| Area | Current state | Priority |
|---|---|---|
| Authentication and account lifecycle | Partially implemented; verification/reset delivery and revocation missing | P1 |
| Authorization | Role checks exist, object ownership and enrollment checks are inconsistent | P0 |
| Courses and content access | Useful data model; publication workflow and paid-content boundary are unsafe | P0 |
| Enrollment and progress | Functional concepts, but completion logic and concurrency are inconsistent | P0 |
| Assessments and exams | Duplicate implementations and correctness/ownership defects | P0 |
| Payments, wallets, refunds, payouts | Broken model contract and unsafe financial invariants | P0 |
| Certificates | Core flow exists; eligibility, transaction boundary, and runtime defects remain | P1 |
| Social and live | Large schema/authorization drift; WebSocket access is unsafe | P0 |
| Operations and deployment | No reproducible clean install, CI, production channel layer, or deployment recipe | P0 |

**Recommendation:** freeze production release work and first complete the P0 containment sequence in section 12. Do not begin by refactoring every app. Establish security and financial invariants, repair the executable baseline, then consolidate duplicated domains behind tested services.

---

## 2. Review method and limitations

The review covered:

- project settings, routing, ASGI, and Celery configuration;
- models, serializers, permissions, services, views, URL routing, admin modules, signals, and management commands;
- migrations and cross-app model relationships;
- test inventory and static Python parsing;
- repository/dependency/deployment hygiene;
- frontend-to-backend route use where it exposed an API contract mismatch.

Static parsing succeeded for the source Python files. A full Django check and test execution could not be completed in this environment because Django is not installed in the host Python environment and the tracked virtual environment contains Windows executables that cannot run on macOS. This is itself a release blocker, not a reason to discount the code-level findings.

The review found approximately 26k lines of Python and 195 test methods. Test quantity is encouraging, but the current payment test module imports the removed `events` application, so the suite is expected to fail during collection even after dependencies are installed.

The first remediation PR must create a clean, repeatable test environment. After that, runtime checks may reveal additional defects that static review cannot expose, particularly around migrations, serializer initialization, URL behavior, and PostgreSQL constraints.

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

**Current status:** Remediated on 2026-07-21. Public course detail now emits catalog-safe lesson summaries and no longer exposes paid lesson bodies, video URLs, private metadata, resources, or file URLs. Covered by `CourseDetailContentExposureTest`.

**Evidence**

Public course detail uses nested module/lesson serializers containing fields such as `content_text`, `video_url`, and resources. The same rich lesson serializer is reused for catalog and enrolled learning use cases.

**Impact**

Unauthenticated users can receive content intended for paying students.

**Fix approach**

1. Split serializers by audience:
   - `CatalogCourseSerializer` / `CatalogLessonSummarySerializer`: IDs, titles, order, duration, preview flag only;
   - `LearningCourseSerializer` / `AccessibleLessonSerializer`: content only after access policy succeeds;
   - management serializers: instructor-only authoring fields.
2. Centralize `can_access_course_content(user, course)` and `can_access_lesson(user, lesson)` policies.
3. Apply the policy to lesson detail, resources, recordings, downloads, curriculum, bookmarks, and related assessment endpoints.
4. Avoid relying on a client to hide fields.

**Acceptance criteria**

- Anonymous and unenrolled API snapshots contain no paid content URLs/text/resources.
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

**Current status:** Remediated on 2026-07-21. Completion now uses one atomic enrollment evaluator, required progress counts only completed non-free required lessons, progress GET is read-only, and manual completion requires watch threshold plus assessment requirements. Covered by enrollment regression tests.

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

**Evidence**

- Live session detail/update/delete is broadly authenticated rather than owner-scoped.
- The WebSocket consumer accepts anonymous connections and trusts client messages/sender IDs without checking enrollment, session visibility, participant status, or instructor-only message types.
- JWTs are accepted in query strings.
- The project uses `InMemoryChannelLayer`, which does not coordinate multiple server processes.

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

---

## 5. P1 findings: high-priority correctness and lifecycle work

### P1-01 — Account verification and password reset are incomplete

Registration creates a verification token but users are active immediately and no verification email is sent. Password reset similarly creates a token without a delivery path. Tokens are stored directly and there is no endpoint throttling or access-token revocation strategy after a password change.

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

Watch-time APIs accept client-supplied absolute time and can jump directly to the duration. Type/monotonicity validation is incomplete. This makes lesson thresholds easy to bypass and permits lost updates.

**Approach**

- Accept bounded progress events or monotonic checkpoints and reject regressions/unreasonable jumps.
- Cap at authoritative media duration and update with a row lock or an atomic maximum expression.
- Treat watch time as one signal, not proof by itself, where assessments are required.
- Define behavior for videos without known duration and for text lessons.

### P1-06 — Enrollment purchase/reactivation is not safely transactional

The enrollment serializer performs wallet lookup, debit, payment creation, fee allocation, reactivation, and enrollment changes with broad exception handling and best-effort mirrors. Reactivation reporting is calculated incorrectly, and concurrent requests are not locked.

**Approach**

- Move business logic out of the serializer into the unified purchase/fulfillment command.
- Lock purchaser balance, existing enrollment, coupon, and relevant accounting rows.
- Use a client/request idempotency key.
- Remove broad `except Exception` fallbacks and never silently pass failed money writes.
- Return a typed result describing `created`, `reactivated`, or `already_active`.

### P1-07 — Certificate lifecycle is coupled to request transactions

PDF generation occurs synchronously near enrollment completion. A PDF/storage failure can block or roll back a valid completion. The regenerate view calls `regenerate_certificate_pdf` with a signature that does not match the service, and invalid verification codes do not follow the view's expected error flow.

**Approach**

- Separate certificate eligibility, certificate record issuance, and document rendering.
- Create the certificate record atomically and enqueue PDF rendering with `transaction.on_commit`.
- Make rendering retryable/idempotent and store generation status/error.
- Correct the regenerate service contract and add an end-to-end test.
- Define verification response and privacy policy; map invalid/revoked codes to deliberate HTTP statuses.
- Use `F()` updates for counters.

### P1-08 — Certificate grade calculation is not defensible

Grade calculation aggregates all quiz attempts rather than an explicit best/latest policy, mixes assignment data without clear weights, and can default to 100 when no assessments exist.

**Approach**

- Define and version grading policy at course publication time.
- Use required assessment weights that sum to 100, or explicitly define points-based calculation.
- Choose best/latest/first attempt policy per assessment.
- Store the completion/grade evidence snapshot used for a certificate so later content edits do not rewrite history.

### P1-09 — Assignment and quiz management permit invalid mutations

A student submission endpoint creates an `Assignment` automatically when one is missing. Question replacement deletes all existing questions and recreates them, which can invalidate attempt history. File uploads lack a clear server-enforced type/size/storage policy.

**Approach**

- Only course managers may create curriculum assessments.
- Snapshot attempt questions/answers before allowing mutable authoring; do not delete rows referenced by historical attempts.
- Validate that objective questions have exactly the permitted correct-option configuration.
- Generate storage keys server-side and validate file size, content type, extension, and malware-scanning status.
- Prefer direct-to-object-storage signed uploads with a finalized-upload record.

### P1-10 — Attempt count and concurrency invariants are ineffective

Quiz attempts can be created through different paths with incompatible assumptions. Exam attempt uniqueness includes `started_at`, which does not enforce a meaningful business rule. Concurrent starts can exceed maximum attempts.

**Approach**

- Define whether one active attempt is allowed and how maximum attempts are counted.
- Add conditional database constraints where possible (e.g. one active attempt per user/exam).
- Lock the user/exam enrollment or a dedicated attempt-counter row while allocating an attempt number.
- Replace timestamp-based uniqueness with `(user, exam, attempt_number)`.

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

**Approach**

- Make GET/HEAD strictly read-only.
- Move lifecycle advancement to explicit commands, domain events, or scheduled tasks.
- Log request IDs, actor ID, resource ID, error class, and safe context—not full content, tokens, addresses, or provider payloads.
- Return stable public error codes/messages and capture detailed exceptions only in server logs/error monitoring.

---

## 6. P2 findings: maintainability, performance, and product completion

### P2-01 — Course versioning exists but is not integrated

The version model does not drive the authoring/publishing workflow. Use it as the basis for immutable published snapshots, or remove it until the product needs revisions. A half-integrated version model adds complexity without protecting published content.

### P2-02 — Query patterns will produce N+1 and expensive aggregate work

Nested course serializers and dashboard statistics call counts/ratings per object. Apply `select_related`, `prefetch_related`, annotated aggregates, and query-budget tests to list endpoints. Validate allowed ordering fields instead of passing arbitrary values to `order_by()`.

### P2-03 — Denormalized student/instructor stats become stale

Profile statistics are updated on selected paths or profile creation and do not reflect every domain change. Prefer query-time aggregates for low-volume dashboards or explicit projection tables updated from transactional outbox events, with a reconciliation command.

### P2-04 — Analytics code is not contract-tested

Assessment analytics references a nonexistent `correct_answer` field, and exam analytics expects an answer representation different from scoring. Build analytics only from the versioned attempt snapshot/result schema and cover every analytics query with database tests.

### P2-05 — Background-task configuration is incomplete

Celery is configured but no meaningful beat schedule/application tasks are visible. Use tasks for email, certificate rendering, recording processing, reconciliation, and lifecycle scheduling. Tasks must be idempotent and should receive record IDs, not serialized model objects.

### P2-06 — WebRTC architecture is suitable only for a narrow prototype

The browser flow appears to use a single peer connection for multiple participants and there is no complete TURN/SFU production design. Decide the expected room size:

- very small rooms: one peer connection per peer plus TURN and explicit signaling authorization;
- larger rooms: use an SFU/provider rather than full-mesh WebRTC.

Do not expose meeting passwords/links in general list serializers. Return join credentials only through a policy-protected, short-lived join action.

### P2-07 — API and frontend contracts have drifted

Template JavaScript calls several routes or shapes that are not present in the backend, including search, checkout/transactions, generic assessment routes, and some instructor/resource/discussion endpoints. Introduce an OpenAPI schema, validate it in CI, and generate or centralize a small client instead of embedding ad hoc URL strings in templates.

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

Use a supported Python version for Django 6, convert dependencies to UTF-8, and prefer a `pyproject.toml` plus a locked dependency artifact. Build a new local virtual environment; do not reuse or commit one.

Baseline CI commands should include:

```bash
python -m compileall -q accounts assessments certificates core courses enrollments exams instructors live payments skillstudio social students
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py test
```

Add coverage, linting, and formatting after the suite runs. A reasonable initial coverage gate is based on the measured baseline, followed by a ratchet; require high branch coverage for permissions, pricing, ledger, scoring, completion, and webhooks.

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

The repository currently lacks a Dockerfile/process declaration/CI workflow and has no verified clean installation path.

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

Estimates below are relative and assume one experienced backend engineer with review support. Runtime findings or real-data reconciliation may change them.

### Phase 0 — Reproducible baseline (1–2 engineering days)

1. Rotate/remove tracked secrets and generated artifacts.
2. Convert dependency declaration to UTF-8 and build a clean environment.
3. Remove stale `events` references until tests collect.
4. Add CI with PostgreSQL/Redis, Django checks, migration checks, tests, and secret scanning.
5. Capture the initial failing test/check report; do not suppress failures.

**Exit gate:** a clean clone installs deterministically, Django starts, serializers import, migrations apply, and CI produces a trustworthy result.

### Phase 1 — Contain security and money risk (3–6 engineering days)

1. Disable arbitrary wallet credit.
2. Remove public paid-content fields and protect resources/recordings.
3. Lock down exam, live, social, grading, and WebSocket object access.
4. Remove client-controlled payment amounts.
5. Verify webhook signatures and make event handling idempotent.
6. Prevent new writes through duplicate wallet/payout paths.

**Exit gate:** adversarial P0 tests pass; no untrusted client controls money, answers, publication, ownership, or sender identity.

### Phase 2 — Restore core workflow correctness (1–2 engineering weeks)

1. Implement canonical payment pricing and fulfillment.
2. Consolidate assessment/exam attempt schemas and scoring.
3. Implement single enrollment completion/eligibility service.
4. Decouple certificate record issuance from PDF rendering.
5. Repair social schema drift and live attendance/poll state.
6. Publish an OpenAPI v1 contract and align the template client.

**Exit gate:** purchase-to-enrollment, learn-to-completion, exam-to-grade, and completion-to-certificate pass end-to-end and retry tests.

### Phase 3 — Data-model consolidation (1–2 engineering weeks plus reconciliation)

1. Add canonical ledger and payout allocations.
2. Reconcile/backfill duplicate wallet and payout data.
3. Consolidate common profile/name fields.
4. Add attempt snapshots/numbers and completion evidence.
5. Add constraints after backfill and retire legacy writes.

**Exit gate:** reconciliation reports zero unexplained differences and legacy paths are read-only or removed.

### Phase 4 — Production reliability and scale (about 1 engineering week)

1. Redis channel layer and production-safe Celery/outbox tasks.
2. Rate limiting, upload security, structured logs, monitoring, and alerts.
3. Query optimization and performance budgets.
4. Backup/restore, webhook replay, reconciliation, and rollback runbooks.
5. Decide and implement appropriate live-video topology/provider.

**Exit gate:** deployment, rollback, restoration, task retry, and multi-process live-message tests pass in staging.

---

## 13. Suggested pull-request breakdown

Keep each PR deployable and narrowly reviewable:

1. **PR 01 — Repository hygiene and executable CI**  
   Secrets rotation support, untrack generated files, UTF-8 dependencies, clean environment, remove stale test imports, CI.

2. **PR 02 — Authorization policy foundation**  
   Shared object policies plus permission matrix tests; owner-scope exams, grading, live HTTP, social, recordings.

3. **PR 03 — Content serialization boundary**  
   Catalog/learning/management serializers; protect paid lessons/resources and correct answers.

4. **PR 04 — Payment contract repair**  
   Remove event drift, server-side pricing, one fee calculator, provider intent abstraction.

5. **PR 05 — Verified idempotent webhooks and fulfillment**  
   Signature verification, webhook dedupe, state machine, enrollment fulfillment.

6. **PR 06 — Ledger and wallet containment**  
   Disable public credit, canonical service, locking/idempotency; add reconciliation report before migration.

7. **PR 07 — Assessment/exam attempt and scoring consolidation**  
   Versioned snapshot/schema, duplicate route/service removal, idempotent submit/manual grade.

8. **PR 08 — Completion and certificate orchestration**  
   Single eligibility service, immutable evidence, async idempotent PDF generation.

9. **PR 09 — Social schema repair and membership policy**  
   Align fields/services, private access, join/rejoin/capacity/admin rules.

10. **PR 10 — Live WebSocket and attendance hardening**  
    Auth ticket/cookie flow, per-message policy, Redis, counters/attendance.

11. **PR 11 — Profile/payout consolidation migrations**  
    Backfill, switch reads/writes, constraints, then legacy removal in a later PR.

12. **PR 12 — API schema, performance, and production runbook**  
    OpenAPI, frontend alignment, query budgets, monitoring, deployment/restore procedures.

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
