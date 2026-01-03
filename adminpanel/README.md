# Admin Panel Application

## Overview
The Admin Panel provides comprehensive administrative tools for managing the entire Skillstudio platform. This includes user management, content moderation, payment oversight, platform settings, and detailed activity logging.

## Features

### 📊 Dashboard & Overview
- **Comprehensive Dashboard**: Real-time platform statistics and metrics
- **Growth Metrics**: Track platform growth over customizable time periods
- **Top Performers**: View top courses and instructors by revenue and engagement
- **Recent Activity**: Monitor recent admin actions and platform changes

### 👥 User Management
- **User Listing**: View all users with filtering by role, status, and search
- **User Details**: Detailed information about individual users
- **Instructor Approval**: Approve or reject instructor applications
- **Account Management**: Suspend, activate, or delete user accounts
- **User Statistics**: Comprehensive user analytics and demographics

### 📚 Course Moderation
- **Pending Courses**: Review courses awaiting approval
- **Course Approval/Rejection**: Approve or reject courses with reasons
- **Course Management**: Archive or delete courses
- **Course Statistics**: Track course metrics and performance

### 🛡️ Content Moderation
- **Moderation Queue**: Centralized queue for all flagged content
- **Review Management**: Moderate user reviews and ratings
- **Flagged Content**: Handle reported content across the platform
- **Content Actions**: Approve, reject, or remove flagged content

### 💰 Payment & Revenue Management
- **Payment Oversight**: View and filter all platform payments
- **Revenue Statistics**: Comprehensive revenue analytics and reporting
- **Refund Processing**: Process payment refunds with tracking
- **Payout Management**: Review and approve instructor payouts
- **Financial Reports**: Detailed financial breakdowns and trends

### ⚙️ Platform Settings
- **Global Settings**: Manage platform-wide configuration settings
- **Setting Types**: Support for string, integer, float, boolean, and JSON values
- **Public/Private Settings**: Control visibility of settings to non-admin users
- **Setting History**: Track who changed what and when

### 🔔 System Alerts
- **Alert Creation**: Create system-wide alerts and announcements
- **Alert Types**: Info, warning, error, and maintenance alerts
- **Targeted Alerts**: Target specific user roles (students, instructors, admins)
- **Scheduled Alerts**: Set start and end times for alerts
- **Alert Management**: Activate, deactivate, or delete alerts

### 📝 Activity Logging
- **Comprehensive Logging**: All admin actions are automatically logged
- **Action Types**: Track 15+ different admin action types
- **Audit Trail**: Complete audit trail with timestamps and metadata
- **Admin Activity Reports**: View activity by admin user or action type
- **IP Tracking**: Log IP addresses for security auditing

## Models

### AdminAction
Tracks all administrative actions for audit purposes.

**Fields:**
- `admin_user`: The admin who performed the action
- `action_type`: Type of action (suspend, approve, delete, etc.)
- `target_model`: The model being acted upon
- `target_id`: ID of the target object
- `description`: Human-readable description
- `metadata`: JSON field for additional data
- `ip_address`: IP address of the admin
- `created_at`: When the action was performed

### ContentModerationQueue
Manages content that needs moderation.

**Fields:**
- `content_type`: Type of content (course, review, post, etc.)
- `content_id`: ID of the content
- `reported_by`: User who reported the content
- `reason`: Reason for reporting
- `status`: Current status (pending, approved, rejected, flagged)
- `reviewed_by`: Admin who reviewed
- `admin_notes`: Notes from the admin
- `created_at`: When it was reported

### PlatformSettings
Global platform configuration settings.

**Fields:**
- `key`: Unique setting key
- `value`: Setting value (stored as text)
- `description`: Description of the setting
- `data_type`: Type of value (string, integer, float, boolean, json)
- `is_public`: Whether non-admins can access
- `updated_by`: Last admin to update
- `updated_at`: Last update time

### SystemAlert
System-wide alerts and announcements.

**Fields:**
- `title`: Alert title
- `message`: Alert message
- `alert_type`: Type (info, warning, error, maintenance)
- `is_active`: Whether the alert is currently active
- `target_roles`: JSON array of target roles
- `start_time`: When the alert becomes active
- `end_time`: When the alert expires
- `created_by`: Admin who created the alert

## API Endpoints

### Dashboard
```
GET  /api/adminpanel/dashboard/          # Main dashboard with all metrics
GET  /api/adminpanel/stats/              # Detailed platform statistics
```

### User Management
```
GET    /api/adminpanel/users/                        # List all users
GET    /api/adminpanel/users/{id}/                   # User details
POST   /api/adminpanel/users/{id}/approve-instructor/ # Approve instructor
POST   /api/adminpanel/users/{id}/suspend/           # Suspend user
POST   /api/adminpanel/users/{id}/activate/          # Activate user
DELETE /api/adminpanel/users/{id}/delete/            # Delete user
```

### Course Moderation
```
GET    /api/adminpanel/courses/pending/           # Pending courses
POST   /api/adminpanel/courses/{id}/approve/      # Approve course
POST   /api/adminpanel/courses/{id}/reject/       # Reject course
DELETE /api/adminpanel/courses/{id}/delete/       # Delete course
```

### Content Moderation
```
GET    /api/adminpanel/moderation/queue/          # Moderation queue
POST   /api/adminpanel/moderation/{id}/           # Moderate content
GET    /api/adminpanel/reviews/flagged/           # Flagged reviews
DELETE /api/adminpanel/reviews/{id}/remove/       # Remove review
POST   /api/adminpanel/reviews/{id}/approve/      # Approve review
```

### Payments & Revenue
```
GET  /api/adminpanel/payments/                  # List payments
GET  /api/adminpanel/revenue/                   # Revenue statistics
POST /api/adminpanel/payments/{id}/refund/      # Process refund
GET  /api/adminpanel/payouts/                   # List payouts
POST /api/adminpanel/payouts/{id}/approve/      # Approve payout
```

### Settings & Alerts
```
GET  /api/adminpanel/settings/                  # Get settings
POST /api/adminpanel/settings/                  # Update setting
GET  /api/adminpanel/alerts/                    # List alerts
POST /api/adminpanel/alerts/                    # Create alert
PATCH /api/adminpanel/alerts/{id}/              # Update alert
DELETE /api/adminpanel/alerts/{id}/             # Delete alert
```

### Activity Log
```
GET  /api/adminpanel/activity-log/              # View activity log
```

## Usage Examples

### Dashboard Access
```python
# Get comprehensive dashboard data
response = client.get('/api/adminpanel/dashboard/?days=30')

# Response includes:
# - platform_stats
# - user_stats
# - course_stats
# - revenue_stats
# - event_stats
# - growth_metrics
# - top_courses
# - top_instructors
# - recent_actions
```

### Suspend a User
```python
response = client.post(
    f'/api/adminpanel/users/{user_id}/suspend/',
    {
        'reason': 'Violation of terms of service'
    }
)
```

### Approve a Course
```python
response = client.post(
    f'/api/adminpanel/courses/{course_id}/approve/'
)
```

### Create System Alert
```python
response = client.post(
    '/api/adminpanel/alerts/',
    {
        'title': 'Scheduled Maintenance',
        'message': 'Platform will be down for 2 hours starting at midnight',
        'alert_type': 'maintenance',
        'target_roles': ['student', 'instructor'],
        'end_time': '2026-01-04T02:00:00Z'
    }
)
```

## Services

All business logic is separated into services in `services.py`:

- **User Management**: `get_all_users`, `approve_instructor`, `suspend_user`, `activate_user`
- **Course Moderation**: `get_pending_courses`, `approve_course`, `reject_course`
- **Content Moderation**: `get_flagged_content`, `moderate_content`, `remove_review`
- **Payment Management**: `get_all_payments`, `refund_payment`, `approve_payout`
- **Platform Analytics**: `platform_stats`, `get_growth_metrics`, `get_top_performing_courses`
- **Settings**: `get_platform_settings`, `update_platform_setting`
- **Alerts**: `get_active_system_alerts`, `create_system_alert`

## Permissions

All admin panel endpoints require:
- User must be authenticated
- User must have `role='admin'`
- Uses `IsAdmin` permission class

## Testing

Run tests with:
```bash
python manage.py test adminpanel
```

Tests cover:
- Model creation and validation
- Service function logic
- API endpoint access control
- Admin action logging
- Content moderation workflows

## Security Features

1. **Action Logging**: All admin actions are logged with timestamps and metadata
2. **IP Tracking**: Admin IP addresses are recorded for security auditing
3. **Permission Checks**: Strict role-based access control
4. **Audit Trail**: Complete audit trail of all platform changes
5. **Soft Deletes**: Users are deactivated rather than hard-deleted

## Integration with Other Apps

- **Accounts**: User management and role changes
- **Courses**: Course approval and moderation
- **Payments**: Payment and payout management
- **Social**: Review moderation
- **Events**: Event management and cancellation
- **Analytics**: Platform statistics and metrics

## Future Enhancements

- Advanced analytics dashboards
- Automated fraud detection
- Bulk operations for user/course management
- Custom admin role permissions
- Enhanced reporting and export features
- Real-time notifications for admin actions
