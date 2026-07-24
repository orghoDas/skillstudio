# Accounts App - Quick Reference Guide

## ✅ Completed Features

### 1. **Authentication & Authorization**
- ✅ JWT token-based authentication (access + refresh tokens)
- ✅ Custom user model with email as username
- ✅ Role-based access control (Admin, Instructor, Student)
- ✅ Permission classes for role enforcement
- ✅ Decorators and mixins for view protection

### 2. **User Registration & Verification**
- ✅ User registration endpoint
- ✅ Role selection during registration (student or instructor)
- ✅ Email verification with UUID tokens
- ✅ Resend verification email
- ✅ Automatic profile creation on user signup
- ✅ 7-day token expiration

### 3. **Password Management**
- ✅ Password reset request (email-based)
- ✅ Password reset confirmation
- ✅ Change password (authenticated users)
- ✅ 24-hour reset token expiration
- ✅ Django password validation

### 4. **Profile Management**
- ✅ Get/update user profile
- ✅ Get/update current user info
- ✅ Profile fields: full_name, bio, avatar, social_links, interests

### 5. **User Management (Admin)**
- ✅ List all users (with role filtering)
- ✅ Get user details
- ✅ Update user role
- ✅ Promote to instructor
- ✅ Activate/deactivate users

### 6. **API Key Management**
- ✅ Create API keys with labels
- ✅ List user's API keys
- ✅ Delete API keys
- ✅ Toggle API key active status
- ✅ UUID-based keys

### 7. **Admin Interface**
- ✅ Custom UserAdmin with proper fieldsets
- ✅ Profile admin with search/filter
- ✅ APIKey admin

### 8. **Testing**
- ✅ User model tests
- ✅ Registration API tests
- ✅ Authentication tests
- ✅ Profile management tests
- ✅ Password management tests
- ✅ API key tests
- ✅ Permission tests

### 9. **Documentation**
- ✅ Comprehensive README with API docs
- ✅ Example settings configuration
- ✅ API endpoint documentation
- ✅ Usage examples

## 📁 File Structure

```
accounts/
├── migrations/
├── __init__.py
├── admin.py              # Django admin configuration
├── apps.py               # App configuration with signals
├── decorators.py         # Role-based decorators
├── mixins.py             # Role-based mixins
├── models.py             # User, Profile, Token models
├── permissions.py        # Custom permission classes
├── serializers.py        # DRF serializers
├── signals.py            # Profile auto-creation
├── tests.py              # Comprehensive tests
├── urls.py               # URL routing
├── utils.py              # Email utilities
├── views.py              # API views
├── README.md             # Detailed documentation
└── SETTINGS_EXAMPLE.py   # Configuration guide
```

## 🔑 API Endpoints Summary

| Method | Endpoint | Description | Auth Required | Role |
|--------|----------|-------------|---------------|------|
| POST | `/api/accounts/register/` | Register new user | No | - |
| POST | `/api/accounts/token/` | Login (get JWT) | No | - |
| POST | `/api/accounts/token/refresh/` | Refresh JWT | No | - |
| POST | `/api/accounts/logout/` | Blacklist refresh token | Yes | - |
| POST | `/api/accounts/change-password/` | Change password (revokes refresh tokens) | Yes | - |
| GET/PATCH | `/api/accounts/me/` | Current user info | Yes | - |
| GET/PATCH | `/api/accounts/profile/` | User profile | Yes | - |
| GET | `/api/accounts/users/` | List users | Yes | Admin |
| GET | `/api/accounts/users/{id}/` | User details | Yes | Admin |
| PATCH | `/api/accounts/users/{id}/role/` | Update role | Yes | Admin |
| POST | `/api/accounts/users/{id}/promote/` | Promote to instructor | Yes | Admin |
| POST | `/api/accounts/users/{id}/activate/` | Activate user | Yes | Admin |
| POST | `/api/accounts/users/{id}/deactivate/` | Deactivate user | Yes | Admin |
| GET/POST | `/api/accounts/api-keys/` | List/create API keys | Yes | - |
| GET/DELETE | `/api/accounts/api-keys/{id}/` | Get/delete API key | Yes | - |
| PATCH | `/api/accounts/api-keys/{id}/toggle/` | Toggle API key | Yes | - |

## 🚀 Quick Start

1. **Ensure settings are configured** (see SETTINGS_EXAMPLE.py)
2. **Run migrations:**
   ```bash
   python manage.py migrate accounts
   ```
3. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   ```
   Superusers are created with `role=admin` and `is_staff=True`.
4. **Run tests:**
   ```bash
   python manage.py test accounts
   ```

## 📝 Common Tasks

### Register a new user
```bash
curl -X POST http://localhost:8000/api/accounts/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Pass123!","password2":"Pass123!"}'
```

### Login
```bash
curl -X POST http://localhost:8000/api/accounts/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Pass123!"}'
```

### Access protected endpoint
```bash
curl http://localhost:8000/api/accounts/me/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 🔒 Security Features

- ✅ Password validation (min 8 chars, complexity requirements)
- ✅ JWT token expiration (60 min access, 7 day refresh)
- ✅ Token rotation on refresh
- ✅ Email verification before activation
- ✅ Password reset token expiration (24 hours)
- ✅ Role-based access control
- ✅ Admin-only user management
- ✅ API key management

## 🎯 Next Steps

The accounts app is fully functional! You can now:

1. Configure email settings for production
2. Customize email templates
3. Add OAuth providers (Google, GitHub, etc.)
4. Implement 2FA (optional)
5. Add rate limiting for security
6. Customize JWT settings as needed

## 📚 Additional Resources

- See [README.md](README.md) for detailed API documentation
- See [SETTINGS_EXAMPLE.py](SETTINGS_EXAMPLE.py) for configuration
- Run `python manage.py test accounts` for test examples
