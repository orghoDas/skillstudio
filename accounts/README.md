# Accounts App Documentation

## Overview
The accounts app handles user authentication, authorization, profile management, and related functionality for the SkillStudio platform.

## Models

### User (Custom User Model)
- **Fields:**
  - `email` (EmailField, unique, USERNAME_FIELD)
  - `username` (CharField, optional)
  - `role` (CharField with choices: admin, student, instructor)
  - `is_active` (BooleanField)
  - `is_staff` (BooleanField)
  - `created_at` (DateTimeField)

**Role and flag policy:**
- `role=admin` is the platform-admin role and always implies `is_staff=True`.
- `is_superuser=True` always implies `role=admin` and `is_staff=True`.
- Bare `is_staff=True` may be used for operational staff actions, but it does not grant platform-admin role permissions by itself.

### Profile
- **Fields:**
  - `user` (OneToOneField to User)
  - `full_name` (CharField)
  - `bio` (TextField)
  - `avatar` (URLField)
  - `social_links` (JSONField)
  - `interests` (JSONField)
  - `created_at`, `updated_at` (DateTimeField)

### APIKey
- For API key authentication
- Secrets are shown only once at creation time.
- **Fields:** `user`, `key_hash`, `prefix`, `label`, `scopes`, `created_at`, `last_used_at`, `revoked_at`, `is_active`

## API Endpoints

### Authentication
- `POST /api/accounts/register/` - Register new user
- `POST /api/accounts/token/` - Obtain JWT token (login)
- `POST /api/accounts/token/refresh/` - Refresh JWT token
- `POST /api/accounts/logout/` - Blacklist the supplied refresh token

### Password Management
- `POST /api/accounts/change-password/` - Change password (authenticated); revokes existing refresh tokens

### User Profile
- `GET /api/accounts/me/` - Get current user info with a stable profile envelope
- `PATCH /api/accounts/me/` - Update current user info
- `GET /api/accounts/profile/` - Get account, student, and instructor profile sections in one stable envelope
- `PATCH /api/accounts/profile/` - Update shared account-owned profile fields only

`/api/accounts/profile/` returns `account_profile`, `student_profile`, and `instructor_profile` keys for every role. Student learning preferences remain owned by `/api/students/profile/`; instructor professional fields remain owned by `/api/instructors/profile/`.

### User Management (Admin Only)
- `GET /api/accounts/users/` - List all users (supports ?role= filter)
- `GET /api/accounts/users/{id}/` - Get user details
- `PATCH /api/accounts/users/{id}/role/` - Update user role
- `POST /api/accounts/users/{id}/promote/` - Promote user to instructor
- `POST /api/accounts/users/{id}/activate/` - Activate user
- `POST /api/accounts/users/{id}/deactivate/` - Deactivate user

### API Keys
- `GET /api/accounts/api-keys/` - List user's API keys
- `POST /api/accounts/api-keys/` - Create new API key
- `GET /api/accounts/api-keys/{id}/` - Get API key details
- `DELETE /api/accounts/api-keys/{id}/` - Delete API key
- `PATCH /api/accounts/api-keys/{id}/toggle/` - Toggle API key active status

### Test Endpoints
- `GET /api/accounts/instructor-only/` - Test endpoint for instructor access

## Permissions

### Custom Permissions
- `IsStudent` - Only students can access
- `IsInstructor` - Only instructors (and admins) can access
- `IsAdmin` - Only admins can access

All custom permissions automatically grant access to admin users.

## Example Usage

### Registration

**Register as Student (default):**
```json
POST /api/accounts/register/
{
  "email": "student@example.com",
  "username": "student123",
  "password": "SecurePass123!",
  "password2": "SecurePass123!"
}
```

**Register as Instructor:**
```json
POST /api/accounts/register/
{
  "email": "instructor@example.com",
  "username": "instructor123",
  "password": "SecurePass123!",
  "password2": "SecurePass123!",
  "role": "instructor"
}
```

**Response:**
```json
{
  "message": "User registered successfully. Please check your email for verification.",
  "user": {
    "id": 1,
    "email": "instructor@example.com",
    "username": "instructor123",
    "role": "instructor"
  }
}
```

**Note:** Only `student` or `instructor` roles are allowed during registration. Admin roles can only be assigned by existing admins.

### Login
```json
POST /api/accounts/token/
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Update Profile
```json
PATCH /api/accounts/profile/
Headers: Authorization: Bearer {access_token}
{
  "full_name": "John Doe",
  "bio": "Software developer and lifelong learner",
  "interests": ["Python", "Django", "Machine Learning"]
}
```

Response includes the stable profile envelope:

```json
{
  "id": 1,
  "email": "john@example.com",
  "role": "student",
  "account_profile": {},
  "student_profile": {},
  "instructor_profile": null
}
```

### Create API Key
```json
POST /api/accounts/api-keys/
Headers: Authorization: Bearer {access_token}
{
  "label": "My Application Key"
}

Response:
{
  "id": 1,
  "key": "ss_example-one-time-secret",
  "prefix": "ss_example-one-t",
  "label": "My Application Key",
  "scopes": [],
  "created_at": "2026-01-02T10:30:00Z",
  "last_used_at": null,
  "revoked_at": null,
  "is_active": true
}
```

Use API keys with `Authorization: Api-Key {key}` or `X-API-Key: {key}`. List, detail, and toggle responses never return the full secret.

### Change Password
```json
POST /api/accounts/change-password/
{
  "old_password": "CurrentPass123!",
  "new_password": "NewSecurePass123!",
  "new_password2": "NewSecurePass123!"
}
```
Changing the password blacklists all of the user's outstanding refresh tokens, so other sessions must log in again. Self-service reset for logged-out users is intentionally not provided; an admin resets a forgotten password.

## Signals

### Post-Save Signal for User
- Automatically creates a Profile instance when a User is created
- Defined in `signals.py`, registered in `apps.py`

## Admin Interface

All models are registered in the Django admin with custom configurations:
- User: Custom UserAdmin with proper fieldsets
- Profile: List display with user, name, and dates
- APIKey: Shows prefix, active status, last-used, revocation, and creation dates

## Testing

Run tests with:
```bash
python manage.py test accounts
```

Test coverage includes:
- User model creation
- Registration API
- Authentication
- Profile management
- Password changes
- API key management
- Permission checks

## Email Configuration

To enable email sending (verification, password reset), configure in `settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'noreply@skillstudio.com'
FRONTEND_URL = 'http://localhost:3000'  # Your frontend URL
```

## Security Considerations

1. **Password Validation**: Uses Django's built-in password validators
2. **JWT Tokens**: Uses rest_framework_simplejwt for secure token handling
3. **Email Verification**: 7-day expiration on verification tokens
4. **Password Reset**: 24-hour expiration on reset tokens
5. **Role-Based Access**: Implemented through custom permission classes
6. **API Keys**: UUID-based keys with activation toggle

## Future Enhancements

- [ ] Two-factor authentication (2FA)
- [ ] OAuth social login (Google, GitHub, etc.)
- [ ] Account deletion/anonymization
- [ ] Session management (view/revoke active sessions)
- [ ] Login attempt rate limiting
- [ ] Email notification preferences
