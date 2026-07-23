from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Profile, EmailVerificationToken, PasswordResetToken, APIKey
from .utils import is_platform_admin
from instructors.models import InstructorProfile
from students.models import StudentProfile

User = get_user_model()


class UserModelTest(TestCase):
    def test_create_user(self):
        """Test creating a regular user"""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        """Test creating a superuser"""
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_create_superuser_rejects_non_admin_role_or_flags(self):
        """Superusers must be platform admins with staff access."""
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email='bad-role@example.com',
                password='adminpass123',
                role=User.Role.STUDENT
            )
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email='bad-staff@example.com',
                password='adminpass123',
                is_staff=False
            )
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email='bad-superuser@example.com',
                password='adminpass123',
                is_superuser=False
            )

    def test_admin_role_normalizes_staff_flag_on_save(self):
        """Platform admins must always be Django staff users."""
        admin = User.objects.create_user(
            email='role-admin@example.com',
            password='pass123',
            role=User.Role.ADMIN,
            is_staff=False
        )

        self.assertTrue(admin.is_staff)
        self.assertFalse(admin.is_superuser)

    def test_admin_role_normalizes_staff_flag_with_update_fields(self):
        """Partial saves must also persist role/staff normalization."""
        user = User.objects.create_user(
            email='partial-admin@example.com',
            password='pass123'
        )

        user.role = User.Role.ADMIN
        user.save(update_fields=['role'])
        user.refresh_from_db()

        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)

    def test_superuser_normalizes_role_and_staff_on_save(self):
        """Legacy or programmatic superusers are normalized on save."""
        user = User.objects.create_user(
            email='legacy-super@example.com',
            password='pass123',
            role=User.Role.STUDENT,
            is_staff=False,
            is_superuser=True
        )

        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_database_rejects_admin_role_without_staff(self):
        """Bulk/manual writes cannot bypass admin/staff invariants."""
        user = User.objects.create_user(
            email='bulk-admin@example.com',
            password='pass123'
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.filter(id=user.id).update(role=User.Role.ADMIN, is_staff=False)

    def test_database_rejects_superuser_without_admin_role(self):
        """Bulk/manual writes cannot bypass superuser/admin invariants."""
        user = User.objects.create_user(
            email='bulk-super@example.com',
            password='pass123'
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.filter(id=user.id).update(
                    role=User.Role.STUDENT,
                    is_staff=True,
                    is_superuser=True
                )

    def test_platform_admin_helper_honors_role_or_superuser_not_staff(self):
        role_admin = User.objects.create_user(
            email='helper-admin@example.com',
            password='pass123',
            role=User.Role.ADMIN
        )
        superuser = User.objects.create_superuser(
            email='helper-super@example.com',
            password='pass123'
        )
        staff_user = User.objects.create_user(
            email='helper-staff@example.com',
            password='pass123',
            is_staff=True
        )

        self.assertTrue(is_platform_admin(role_admin))
        self.assertTrue(is_platform_admin(superuser))
        self.assertFalse(is_platform_admin(staff_user))

    def test_profile_created_on_user_creation(self):
        """Test that profile is automatically created when user is created"""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, Profile)


class RegistrationAPITest(APITestCase):
    def test_register_user(self):
        """Test user registration defaults to student"""
        data = {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'password': 'TestPass123!',
            'password2': 'TestPass123!'
        }
        response = self.client.post('/api/accounts/register/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
        
        # Verify default role is student
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertEqual(response.data['user']['role'], 'student')

    def test_register_as_instructor(self):
        """Test user can register as instructor"""
        data = {
            'email': 'instructor@example.com',
            'username': 'instructor',
            'password': 'TestPass123!',
            'password2': 'TestPass123!',
            'role': 'instructor'
        }
        response = self.client.post('/api/accounts/register/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify role is instructor
        user = User.objects.get(email='instructor@example.com')
        self.assertEqual(user.role, User.Role.INSTRUCTOR)
        self.assertEqual(response.data['user']['role'], 'instructor')

    def test_register_with_invalid_role(self):
        """Test registration fails with admin role"""
        data = {
            'email': 'admin@example.com',
            'username': 'admin',
            'password': 'TestPass123!',
            'password2': 'TestPass123!',
            'role': 'admin'
        }
        response = self.client.post('/api/accounts/register/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)

    def test_register_with_mismatched_passwords(self):
        """Test registration fails with mismatched passwords"""
        data = {
            'email': 'newuser@example.com',
            'password': 'TestPass123!',
            'password2': 'DifferentPass123!'
        }
        response = self.client.post('/api/accounts/register/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthenticationAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

    def test_obtain_token(self):
        """Test obtaining JWT token"""
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post('/api/accounts/token/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)


class ProfileAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_get_profile(self):
        """Test retrieving user profile"""
        response = self.client.get('/api/accounts/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('account_profile', response.data)
        self.assertIn('student_profile', response.data)
        self.assertIn('instructor_profile', response.data)
        self.assertIsNotNone(response.data['account_profile'])
        self.assertIsNotNone(response.data['student_profile'])
        self.assertIsNone(response.data['instructor_profile'])

    def test_update_profile(self):
        """Test updating user profile"""
        data = {
            'full_name': 'Test User',
            'bio': 'This is my bio'
        }
        response = self.client.patch('/api/accounts/profile/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, 'Test User')
        self.assertEqual(response.data['account_profile']['full_name'], 'Test User')

    def test_profile_shape_is_stable_for_instructor(self):
        instructor = User.objects.create_user(
            email='instructor-profile@example.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        InstructorProfile.objects.create(
            user=instructor,
            headline='Senior Instructor',
            bio='Instructor bio'
        )
        self.client.force_authenticate(user=instructor)

        response = self.client.get('/api/accounts/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('account_profile', response.data)
        self.assertIn('student_profile', response.data)
        self.assertIn('instructor_profile', response.data)
        self.assertIsNone(response.data['student_profile'])
        self.assertEqual(response.data['instructor_profile']['headline'], 'Senior Instructor')
        self.assertEqual(response.data['instructor_profile']['bio'], 'Instructor bio')

    def test_account_profile_update_does_not_mutate_instructor_profile(self):
        instructor = User.objects.create_user(
            email='instructor-update@example.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        instructor_profile = InstructorProfile.objects.create(
            user=instructor,
            headline='Original headline',
            bio='Original instructor bio'
        )
        self.client.force_authenticate(user=instructor)

        response = self.client.patch(
            '/api/accounts/profile/',
            {'bio': 'Account bio', 'headline': 'Ignored headline'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        instructor.refresh_from_db()
        instructor.profile.refresh_from_db()
        instructor_profile.refresh_from_db()
        self.assertEqual(instructor.profile.bio, 'Account bio')
        self.assertEqual(instructor_profile.headline, 'Original headline')
        self.assertEqual(instructor_profile.bio, 'Original instructor bio')

    def test_me_uses_same_stable_profile_envelope(self):
        StudentProfile.objects.create(
            user=self.user,
            weekly_study_hours=6
        )

        response = self.client.get('/api/accounts/me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('account_profile', response.data)
        self.assertIn('student_profile', response.data)
        self.assertIn('instructor_profile', response.data)
        self.assertEqual(response.data['student_profile']['weekly_study_hours'], 6)


class PasswordManagementTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='oldpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_change_password(self):
        """Test password change"""
        data = {
            'old_password': 'oldpass123',
            'new_password': 'NewPass123!',
            'new_password2': 'NewPass123!'
        }
        response = self.client.post('/api/accounts/change-password/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!'))


class APIKeyTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_create_api_key(self):
        """Test creating an API key"""
        data = {'label': 'My API Key'}
        response = self.client.post('/api/accounts/api-keys/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('key', response.data)
        self.assertTrue(response.data['key'].startswith('ss_'))
        self.assertIn('prefix', response.data)

        api_key = APIKey.objects.get(user=self.user, label='My API Key')
        self.assertNotEqual(api_key.key_hash, response.data['key'])
        self.assertEqual(api_key.key_hash, APIKey.hash_secret(response.data['key']))
        self.assertEqual(api_key.prefix, response.data['key'][:16])

    def test_list_api_keys(self):
        """Test listing user's API keys"""
        APIKey.create_for_user(user=self.user, label='Key 1')
        APIKey.create_for_user(user=self.user, label='Key 2')
        response = self.client.get('/api/accounts/api-keys/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 2)
        self.assertNotIn('key', response.data['results'][0])
        self.assertIn('prefix', response.data['results'][0])

    def test_api_key_authenticates_request_and_tracks_last_used(self):
        """Test API key authentication consumes the hashed secret."""
        api_key, secret = APIKey.create_for_user(user=self.user, label='Service Client')
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Api-Key {secret}')

        response = self.client.get('/api/accounts/me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.last_used_at)

    def test_revoked_api_key_cannot_authenticate(self):
        """Test revoked API keys cannot authenticate."""
        api_key, secret = APIKey.create_for_user(user=self.user, label='Revoked Client')
        api_key.revoke()
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Api-Key {secret}')

        response = self.client.get('/api/accounts/me/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PermissionsTest(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email='student@example.com',
            password='pass123',
            role=User.Role.STUDENT
        )
        self.instructor = User.objects.create_user(
            email='instructor@example.com',
            password='pass123',
            role=User.Role.INSTRUCTOR
        )
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='pass123',
            role=User.Role.ADMIN
        )

    def test_instructor_only_access(self):
        """Test instructor-only endpoint access"""
        # Student should be denied
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/accounts/instructor-only/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Instructor should have access
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get('/api/accounts/instructor-only/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Admin should have access
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/accounts/instructor-only/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_only_user_list(self):
        """Test admin-only user list access"""
        # Student should be denied
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin should have access
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
