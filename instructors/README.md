# instructors

The instructor's profile and dashboards.

## Model
- **`InstructorProfile`**: headline, bio, expertise, links and cached totals. It is created on first use (`get_or_create_instructor_profile`).

## Rules: `services.py`
- `get_course_overview` and `get_student_engagement` aggregate enrollments and progress across the instructor's courses.
- `get_revenue_summary` reads the **wallet ledger** via `payments.services.calculate_instructor_balance`. It shows earnings net of refunds, the platform fee, the available balance, pending payouts and money already paid out.
- Payouts live in `payments` (`/api/payments/payouts/...`). There is no separate instructor payout model.
- `/api/instructors/featured/` is public: it lists instructors with published courses, most students first.
- `/api/instructors/dashboard/` has two aliases kept for older pages: `/api/instructors/stats/` and `/api/enrollments/instructor/dashboard/`.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apiinstructors). That file is generated from the URLconf, so it is always current.
