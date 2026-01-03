# Certificates App Documentation

## Overview
The certificates app handles certificate issuance, verification, PDF generation, and management for the SkillStudio platform. Certificates are automatically issued to students upon course completion based on enrollment status and course requirements.

## Features
- **Automated Certificate Issuance**: Automatically issue certificates when students complete courses
- **PDF Generation**: Generate professional PDF certificates with course and student details
- **Verification System**: Public verification of certificates via unique verification codes
- **Grade Calculation**: Calculate and display final course grades on certificates
- **Download Tracking**: Track certificate downloads and usage statistics
- **Unique Identifiers**: Each certificate has a unique ID and verification code for authenticity

## Models

### Certificate
The main certificate model representing issued certificates.

**Fields:**
- `id` (UUIDField, primary key) - Unique certificate identifier
- `user` (ForeignKey to User) - Student who earned the certificate
- `course` (ForeignKey to Course) - Course for which certificate was issued
- `enrollment` (OneToOneField to Enrollment) - Associated enrollment record
- `certificate_id` (UUIDField, unique) - Public certificate identifier
- `verification_code` (CharField, unique) - Code for public verification
- `pdf` (FileField) - Stored PDF file
- `grade` (DecimalField) - Final course grade percentage
- `completion_date` (DateTimeField) - When the course was completed
- `issued_at` (DateTimeField) - When certificate was issued
- `download_count` (IntegerField) - Number of times certificate was downloaded
- `last_downloaded_at` (DateTimeField) - Last download timestamp

**Constraints:**
- Unique constraint on (user, course) - one certificate per user per course

**Methods:**
- `generate_verification_code()` - Generate unique verification code
- `get_verification_url()` - Get public verification URL
- `__str__()` - String representation

## Services

### issue_certificate(user, course)
Issues a certificate for a completed course.

**Args:**
- `user` - User instance
- `course` - Course instance

**Returns:**
- Certificate instance

**Raises:**
- `ValidationError` if:
  - User is not enrolled in the course
  - Enrollment is canceled
  - Enrollment is not completed

**Process:**
1. Validates active enrollment exists
2. Validates enrollment is completed
3. Creates or retrieves existing certificate
4. Calculates course grade
5. Generates PDF if needed
6. Returns certificate instance

### calculate_course_grade(user, course)
Calculates the final course grade from assessments and progress.

**Args:**
- `user` - User instance
- `course` - Course instance

**Returns:**
- Decimal grade percentage (0-100)

**Calculation Logic:**
1. Gets all quiz/assessment attempts for the course
2. Calculates weighted average based on assessment scores
3. Considers completion percentage if applicable
4. Returns final grade as percentage

### verify_certificate(verification_code)
Verifies a certificate by its verification code.

**Args:**
- `verification_code` - String verification code

**Returns:**
- Certificate instance if valid, None otherwise

### regenerate_certificate_pdf(certificate)
Regenerates the PDF file for an existing certificate.

**Args:**
- `certificate` - Certificate instance

**Returns:**
- Updated certificate instance with new PDF

**Use Cases:**
- Template updates
- Fixing errors in existing certificates
- Rebranding

## PDF Generation

### generate_certificate_pdf(certificate)
Generates a professional PDF certificate.

**Args:**
- `certificate` - Certificate instance

**Returns:**
- File object containing PDF

**PDF Contents:**
- Student name (from user profile)
- Course title
- Completion date
- Certificate ID
- Verification code and URL
- Grade (if applicable)
- Instructor information
- Platform branding

**Technical Details:**
- Uses ReportLab for PDF generation
- Landscape A4 format
- Professional styling with colors and fonts
- QR code for verification URL
- Stored in media/certificates/YYYY/MM/ directory

## API Endpoints

### User Endpoints (Authenticated)

#### List My Certificates
```http
GET /api/certificates/my/
```
Lists all certificates earned by the authenticated user.

**Response:**
```json
[
  {
    "id": "uuid",
    "course": {
      "id": 1,
      "title": "Course Title"
    },
    "certificate_id": "uuid",
    "verification_code": "CODE123",
    "grade": "95.50",
    "completion_date": "2024-01-15T10:30:00Z",
    "issued_at": "2024-01-15T10:35:00Z",
    "download_count": 3
  }
]
```

#### Get Certificate Details
```http
GET /api/certificates/my/{course_id}/
```
Get certificate details for a specific course.

**Response:**
```json
{
  "id": "uuid",
  "course": {
    "id": 1,
    "title": "Course Title",
    "instructor": "Instructor Name"
  },
  "certificate_id": "uuid",
  "verification_code": "CODE123",
  "verification_url": "https://example.com/verify/CODE123",
  "pdf_url": "https://example.com/media/certificates/2024/01/cert.pdf",
  "grade": "95.50",
  "completion_date": "2024-01-15T10:30:00Z",
  "issued_at": "2024-01-15T10:35:00Z",
  "download_count": 3,
  "last_downloaded_at": "2024-01-20T14:00:00Z"
}
```

#### Download Certificate
```http
GET /api/certificates/download/{course_id}/
```
Download the certificate PDF. Increments download counter.

**Response:**
- PDF file download
- Content-Type: application/pdf
- Content-Disposition: attachment

### Public Endpoints (No Authentication)

#### Verify Certificate
```http
GET /api/certificates/verify/{verification_code}/
```
Publicly verify a certificate's authenticity.

**Response (Valid Certificate):**
```json
{
  "valid": true,
  "user_name": "Student Name",
  "course_title": "Course Title",
  "issued_at": "2024-01-15T10:35:00Z",
  "completion_date": "2024-01-15T10:30:00Z",
  "grade": "95.50",
  "certificate_id": "uuid"
}
```

**Response (Invalid Certificate):**
```json
{
  "valid": false
}
```

### Admin Endpoints (Staff Only)

#### Regenerate Certificate
```http
POST /api/certificates/regenerate/{course_id}/
```
Regenerate PDF for an existing certificate.

**Query Parameters:**
- `user_id` (required) - User ID

**Response:**
```json
{
  "message": "Certificate PDF regenerated successfully",
  "certificate_id": "uuid"
}
```

## Integration Points

### Enrollments App
- Triggered when enrollment is marked complete
- Validates enrollment status before issuing
- Links certificate to enrollment record

### Courses App
- Retrieves course details for certificate
- Gets instructor information
- Accesses course completion requirements

### Assessments App
- Retrieves quiz/assessment scores
- Calculates weighted grade
- Determines passing status

### Accounts App
- Gets student profile information
- Retrieves user name for certificate
- Validates user permissions

## Automatic Certificate Issuance

Certificates are NOT automatically issued upon course completion in the current implementation. They must be explicitly requested or issued through the enrollment completion process.

To enable automatic issuance, implement a signal handler in enrollments app:
```python
# In enrollments/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Enrollment
from certificates.services import issue_certificate

@receiver(post_save, sender=Enrollment)
def auto_issue_certificate(sender, instance, **kwargs):
    if instance.is_completed and not hasattr(instance, 'certificate'):
        try:
            issue_certificate(instance.user, instance.course)
        except Exception as e:
            # Log error but don't block enrollment completion
            pass
```

## Testing

The certificates app includes 18 comprehensive tests covering:

### Model Tests (6 tests)
- Certificate creation and uniqueness
- Verification code generation
- Field validations
- Constraints

### Service Tests (8 tests)
- Certificate issuance success cases
- Certificate issuance validation failures
- Grade calculation logic
- Certificate verification
- PDF regeneration

### API Tests (4 tests)
- List user certificates
- Certificate detail retrieval
- Certificate download
- Public verification

Run tests:
```bash
python manage.py test certificates
```

Run with verbose output:
```bash
python manage.py test certificates -v 2
```

## Usage Examples

### Issuing a Certificate
```python
from certificates.services import issue_certificate
from django.contrib.auth import get_user_model
from courses.models import Course

User = get_user_model()
user = User.objects.get(email='student@example.com')
course = Course.objects.get(id=1)

# Issue certificate (validates completion)
certificate = issue_certificate(user, course)
print(f"Certificate issued: {certificate.verification_code}")
```

### Verifying a Certificate
```python
from certificates.services import verify_certificate

# Verify by code
certificate = verify_certificate('ABC123XYZ')
if certificate:
    print(f"Valid certificate for {certificate.course.title}")
else:
    print("Invalid certificate")
```

### Regenerating PDF
```python
from certificates.services import regenerate_certificate_pdf
from certificates.models import Certificate

certificate = Certificate.objects.get(id='uuid')
regenerate_certificate_pdf(certificate)
print("PDF regenerated successfully")
```

## Error Handling

The app handles various error scenarios:

- **No Enrollment**: Returns validation error if user not enrolled
- **Canceled Enrollment**: Prevents certificate issuance for canceled enrollments
- **Incomplete Enrollment**: Requires completion before issuing
- **Duplicate Certificates**: Uses get_or_create to prevent duplicates
- **PDF Generation Failures**: Logs errors and allows retry
- **Invalid Verification Codes**: Returns None for invalid codes

## Performance Considerations

- **select_related**: Certificate queries include course and user joins
- **PDF Caching**: PDFs are stored and not regenerated unless explicitly requested
- **Download Tracking**: Atomic updates for download counter
- **Verification Index**: Verification code field is indexed for fast lookups
- **Unique Constraints**: Database-level constraints prevent duplicate certificates

## Security

- **Unique Verification Codes**: Each certificate has a unique, hard-to-guess code
- **One Certificate Per Course**: Database constraint ensures one certificate per user/course
- **PDF Integrity**: PDFs stored in protected media directory
- **Permission Checks**: Only certificate owner can download
- **Public Verification**: Anyone can verify, but limited information exposed

## Future Enhancements

Potential improvements for the certificates app:

1. **Certificate Templates**: Multiple certificate designs
2. **Digital Signatures**: Cryptographic signatures for enhanced security
3. **Blockchain Integration**: Store certificate hashes on blockchain
4. **Batch Issuance**: Issue certificates for multiple users at once
5. **Certificate Expiry**: Support for time-limited certificates
6. **Multi-language**: Generate certificates in different languages
7. **Custom Fields**: Allow instructors to add custom fields
8. **Social Sharing**: Easy sharing to LinkedIn, Twitter, etc.
9. **Certificate Revocation**: Ability to revoke certificates if needed
10. **Analytics**: Certificate issuance and verification statistics
