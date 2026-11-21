# certificates

Completion certificates with a PDF and a public verification link.

## Model
- **`Certificate`**: one per (user, course), linked to the completed enrollment.
  - Has a unique `verification_code` and an optional grade.
  - Has a `pdf` file in the default storage.

## Rules: `services.py`
- `issue_certificate` is called when an enrollment is completed (`enrollments.services.evaluate_and_complete_enrollment`). It refuses users who aren't enrolled and cancelled enrollments.
- `calculate_course_grade` takes the best completed attempt of each **published** quiz. With no graded evidence, there is no grade.
- **PDFs** are rendered with ReportLab, plus a QR code that points at `BACKEND_URL/api/certificates/verify/<code>/` (`pdf.py`).
  - `certificate_has_pdf` checks the file really exists in storage.
  - If the file is missing, the download endpoint renders it again, or returns `503` if it can't.
- Verification is public and needs no login. It only confirms the certificate details.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apicertificates). That file is generated from the URLconf, so it is always current.
