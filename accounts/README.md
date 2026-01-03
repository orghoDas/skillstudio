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

### Profile
- **Fields:**
  - `user` (OneToOneField to User)
  - `full_name` (CharField)
  - `bio` (TextField)
  - `avatar` (URLField)
  - `social_links` (JSONField)
  - `interests` (JSONField)
  - `created_at`, `updated_at` (DateTimeField)

### EmailVerificationToken
- Used for email verification during registration
- **Fields:** `user`, `token` (UUID), `created_at`, `expires_at`, `is_used`

### PasswordResetToken
- Used for password reset functionality
- **Fields:** `user`, `token` (UUID), `created_at`, `expires_at`

### APIKey
- For API key authentication
- **Fields:** `user`, `key` (UUID), `label`, `created_at`, `is_active`

## API Endpoints

### Authentication
- `POST /accounts/api/register/` - Register new user
- `POST /accounts/api/token/` - Obtain JWT token (login)
- `POST /accounts/api/token/refresh/` - Refresh JWT token

### Email Verification
- `POST /accounts/api/verify-email/` - Verify email with token
- `POST /accounts/api/resend-verification/` - Resend verification email

### Password Management
- `POST /accounts/api/password-reset/` - Request password reset
- `POST /accounts/api/password-reset/confirm/` - Confirm password reset with token
- `POST /accounts/api/change-password/` - Change password (authenticated)

### User Profile
- `GET /accounts/api/me/` - Get current user info
- `PATCH /accounts/api/me/` - Update current user info
- `GET /accounts/api/profile/` - Get user profile
- `PATCH /accounts/api/profile/` - Update user profile

### User Management (Admin Only)
- `GET /accounts/api/users/` - List all users (supports ?role= filter)
- `GET /accounts/api/users/{id}/` - Get user details
- `PATCH /accounts/api/users/{id}/role/` - Update user role
- `POST /accounts/api/users/{id}/promote/` - Promote user to instructor
- `POST /accounts/api/users/{id}/activate/` - Activate user
- `POST /accounts/api/users/{id}/deactivate/` - Deactivate user

### API Keys
- `GET /accounts/api/api-keys/` - List user's API keys
- `POST /accounts/api/api-keys/` - Create new API key
- `GET /accounts/api/api-keys/{id}/` - Get API key details
- `DELETE /accounts/api/api-keys/{id}/` - Delete API key
- `PATCH /accounts/api/api-keys/{id}/toggle/` - Toggle API key active status

### Test Endpoints
- `GET /accounts/api/instructor-only/` - Test endpoint for instructor access

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
POST /accounts/api/register/
{
  "email": "student@example.com",
  "username": "student123",
  "password": "SecurePass123!",
  "password2": "SecurePass123!"
}
```

**Register as Instructor:**
```json
POST /accounts/api/register/
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
POST /accounts/api/token/
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
PATCH /accounts/api/profile/
Headers: Authorization: Bearer {access_token}
{
  "full_name": "John Doe",
  "bio": "Software developer and lifelong learner",
  "interests": ["Python", "Django", "Machine Learning"]
}
```

### Create API Key
```json
POST /accounts/api/api-keys/
Headers: Authorization: Bearer {access_token}
{
  "label": "My Application Key"
}

Response:
{
  "id": 1,
  "key": "a8f5f167-0e5a-4f2b-8e0a-5c7f8d9e0f1a",
  "label": "My Application Key",
  "created_at": "2026-01-02T10:30:00Z",
  "is_active": true
}
```

### Password Reset Flow
```json
# 1. Request reset
POST /accounts/api/password-reset/
{
  "email": "user@example.com"
}

# 2. Confirm reset (using token from email)
POST /accounts/api/password-reset/confirm/
{
  "token": "a8f5f167-0e5a-4f2b-8e0a-5c7f8d9e0f1a",
  "new_password": "NewSecurePass123!",
  "new_password2": "NewSecurePass123!"
}
```

## Signals

### Post-Save Signal for User
- Automatically creates a Profile instance when a User is created
- Defined in `signals.py`, registered in `apps.py`

## Admin Interface

All models are registered in the Django admin with custom configurations:
- User: Custom UserAdmin with proper fieldsets
- Profile: List display with user, name, and dates
- EmailVerificationToken: Shows verification status
- PasswordResetToken: Shows expiration status
- APIKey: Shows active status and creation date

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
