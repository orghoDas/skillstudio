from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Profile, EmailVerificationToken, PasswordResetToken, APIKey

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
        """Test user registration"""
        data = {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'password': 'TestPass123!',
            'password2': 'TestPass123!'
        }
        response = self.client.post('/accounts/api/register/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())

    def test_register_with_mismatched_passwords(self):
        """Test registration fails with mismatched passwords"""
        data = {
            'email': 'newuser@example.com',
            'password': 'TestPass123!',
            'password2': 'DifferentPass123!'
        }
        response = self.client.post('/accounts/api/register/', data)
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
        response = self.client.post('/accounts/api/token/', data)
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
        response = self.client.get('/accounts/api/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_profile(self):
        """Test updating user profile"""
        data = {
            'full_name': 'Test User',
            'bio': 'This is my bio'
        }
        response = self.client.patch('/accounts/api/profile/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, 'Test User')


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
        response = self.client.post('/accounts/api/change-password/', data)
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
        response = self.client.post('/accounts/api/api-keys/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(APIKey.objects.filter(user=self.user, label='My API Key').exists())

    def test_list_api_keys(self):
        """Test listing user's API keys"""
        APIKey.objects.create(user=self.user, label='Key 1')
        APIKey.objects.create(user=self.user, label='Key 2')
        response = self.client.get('/accounts/api/api-keys/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


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
        response = self.client.get('/accounts/api/instructor-only/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Instructor should have access
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get('/accounts/api/instructor-only/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Admin should have access
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/accounts/api/instructor-only/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_only_user_list(self):
        """Test admin-only user list access"""
        # Student should be denied
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/accounts/api/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin should have access
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/accounts/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
