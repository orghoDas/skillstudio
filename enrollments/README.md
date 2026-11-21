# enrollments

Who is enrolled in what, how far they have got, and when a course is complete.

## Models
- **`Enrollment`** (`user`, `course`): `status` is `active`, `completed` or `canceled`.
  - `ACCESS_STATUSES = ("active", "completed")` (`constants.py`) is the one definition of "owns the course".
  - Paid enrollments are created only by `payments.services.purchase_course`. Free enrollments are created by the enroll endpoint.
- **`LessonProgress`**: completion and watch time per (user, lesson).
- **`Wishlist`**.

## Rules: `services.py`
- **`lesson_lock_state`** is the single progression rule:
  - Free lessons are never locked.
  - A required lesson unlocks when every earlier required lesson (in module/lesson order) is complete.
  - Owners, admins and visitors of free courses see nothing locked.
- `mark_lesson_completed` refuses locked lessons.
- A quiz lesson counts as complete only when `assessments.services.is_lesson_assessment_completed` says so.
- **`evaluate_and_complete_enrollment`** marks the enrollment `completed` once every required lesson and assessment is done, then issues the certificate (`certificates.services.issue_certificate`).
- `require_active_enrollment` and `get_access_enrollment` are the helpers views use to load the caller's enrollment.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apienrollments). That file is generated from the URLconf, so it is always current.
