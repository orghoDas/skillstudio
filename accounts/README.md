# accounts

Users, roles, profiles, API keys and login.

## Models
- **`User`** (`AUTH_USER_MODEL`): login is by email. `role` is `student`, `instructor` or `admin`.
  - Database constraints reserve `is_staff` for admins and require every superuser to be an admin.
  - `User.save()` normalises the role flags.
- **`Profile`**: name, bio, avatar URL, social links and interests. It is created for every user.
- **`APIKey`**: stores only a SHA-256 hash of the secret, plus a lookup prefix. Keys are checked with `hmac.compare_digest`, and the plain secret is shown once, at creation.
  - `read` permits GET, HEAD, and OPTIONS. `write` permits mutation methods. An empty scope list grants the owner's normal API access. Role and ownership checks apply in every case. A scoped key can create another key with the same or narrower access.

## Rules
- **Signup role comes from the email domain** (Decision D-02, `accounts/utils.signup_role_for_email`):
  - `@instructor.com` → instructor.
  - Any other domain → student.
  - Domains in `SIGNUP_FORBIDDEN_EMAIL_DOMAINS` (`admin.com`) can't sign up.
  - Admins are created by an existing admin (`/api/accounts/users/<id>/role/`) or with `createsuperuser`.
- **Login** (`custom_token.py`) supports two modes:
  - **Browser:** cookie mode sets httpOnly `access` and `refresh` JWT cookies and requires the CSRF token on login and refresh.
  - **Other clients:** token mode returns the tokens in the response body.
- Logout clears the auth cookies even with an expired or missing access token. Cookie-based requests require CSRF, and supplied refresh tokens are blacklisted.
- Account status is read-only in the current-user API. Admins cannot change a superuser's role away from admin.
- Role checks live in `permissions.py` (`IsStudent`, `IsInstructor`, `IsAdmin`). `utils.is_platform_admin` means a superuser or `role == "admin"`.
- There is no email verification and no password-reset flow; both were removed on purpose.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apiaccounts). That file is generated from the URLconf, so it is always current.
