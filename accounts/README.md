# accounts

Users, roles, profiles, API keys and login.

## Models
- **`User`** (`AUTH_USER_MODEL`): login is by email. `role` is `student`, `instructor` or `admin`.
  - Database `CheckConstraint`s keep the flags consistent: an `admin` must have `is_staff`, and a superuser must be an admin.
  - `User.save()` normalises the role flags.
- **`Profile`**: name, bio, avatar URL, social links and interests. It is created for every user.
- **`APIKey`**: stores only a SHA-256 hash of the secret, plus a lookup prefix. Keys are checked with `hmac.compare_digest`, and the plain secret is shown once, at creation.

## Rules
- **Signup role comes from the email domain** (Decision D-02, `accounts/utils.signup_role_for_email`):
  - `@instructor.com` → instructor.
  - Any other domain → student.
  - Domains in `SIGNUP_FORBIDDEN_EMAIL_DOMAINS` (`admin.com`) can't sign up.
  - Admins are created by an existing admin (`/api/accounts/users/<id>/role/`) or with `createsuperuser`.
- **Login** (`custom_token.py`) supports two modes:
  - **Browser:** cookie mode sets httpOnly `access` and `refresh` JWT cookies and requires the CSRF token on login and refresh.
  - **Other clients:** token mode returns the tokens in the response body.
- Role checks live in `permissions.py` (`IsStudent`, `IsInstructor`, `IsAdmin`). `utils.is_platform_admin` means a superuser or `role == "admin"`.
- There is no email verification and no password-reset flow; both were removed on purpose.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apiaccounts). That file is generated from the URLconf, so it is always current.
