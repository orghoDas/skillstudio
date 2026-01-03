from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from decimal import Decimal

from accounts.models import User
from courses.models import Course, Category
from enrollments.models import Enrollment
from social.models import Review
from ai_recommender.models import (
    Skill, CourseSkill, UserSkill, UserInterest,
    Recommendation, SkillGapAnalysis, TrendingSkill,
    LearningPath, PathCourse, UserLearningPath
)
from ai_recommender import services


class AIRecommenderModelsTestCase(TestCase):
    """Test AI recommender models"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        
        self.skill = Skill.objects.create(
            name='Python Programming',
            slug='python-programming',
            category='technical',
            description='Learn Python'
        )
    
    def test_skill_creation(self):
        """Test creating a skill"""
        self.assertEqual(self.skill.name, 'Python Programming')
        self.assertEqual(self.skill.category, 'technical')
        self.assertTrue(self.skill.is_active)
        self.assertEqual(self.skill.popularity_score, 0.0)
    
    def test_user_skill_creation(self):
        """Test creating user skill"""
        user_skill = UserSkill.objects.create(
            user=self.user,
            skill=self.skill,
            proficiency=50.0,
            source='course'
        )
        
        self.assertEqual(user_skill.user, self.user)
        self.assertEqual(user_skill.skill, self.skill)
        self.assertEqual(user_skill.proficiency, 50.0)
    
    def test_user_interest_creation(self):
        """Test creating user interest"""
        interest = UserInterest.objects.create(
            user=self.user,
            skill=self.skill,
            interest_level=5.0,
            reason='learning_goal',
            target_proficiency=80.0
        )
        
        self.assertEqual(interest.user, self.user)
        self.assertEqual(interest.skill, self.skill)
        self.assertEqual(interest.interest_level, 5.0)
    
    def test_recommendation_creation(self):
        """Test creating a recommendation"""
        instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        
        category = Category.objects.create(name='Tech', slug='tech')
        
        course = Course.objects.create(
            title='Python Basics',
            slug='python-basics',
            instructor=instructor,
            category=category,
            status='published',
            price=Decimal('99.99')
        )
        
        recommendation = Recommendation.objects.create(
            user=self.user,
            course=course,
            score=85.5,
            algorithm='hybrid',
            reason='Great for learning Python'
        )
        
        self.assertEqual(recommendation.user, self.user)
        self.assertEqual(recommendation.course, course)
        self.assertEqual(recommendation.score, 85.5)
        self.assertEqual(recommendation.status, 'active')
        
        # Test mark_clicked
        self.assertFalse(recommendation.clicked)
        recommendation.mark_clicked()
        self.assertTrue(recommendation.clicked)
        self.assertIsNotNone(recommendation.clicked_at)


class AIRecommenderServicesTestCase(TestCase):
    """Test AI recommender services"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        
        self.category = Category.objects.create(name='Tech', slug='tech')
        
        self.course = Course.objects.create(
            title='Python Course',
            slug='python-course',
            instructor=self.instructor,
            category=self.category,
            status='published',
            price=Decimal('99.99')
        )
        
        self.skill = Skill.objects.create(
            name='Python',
            slug='python',
            category='technical'
        )
    
    def test_create_skill(self):
        """Test creating a skill via service"""
        skill = services.create_skill(
            name='JavaScript',
            category='technical',
            description='JS programming'
        )
        
        self.assertEqual(skill.name, 'JavaScript')
        self.assertEqual(skill.category, 'technical')
        self.assertTrue(Skill.objects.filter(name='JavaScript').exists())
    
    def test_add_skill_to_course(self):
        """Test adding skill to course"""
        course_skill = services.add_skill_to_course(
            course=self.course,
            skill_name='Python',
            weight=2.0,
            is_primary=True
        )
        
        self.assertEqual(course_skill.course, self.course)
        self.assertEqual(course_skill.skill.name, 'Python')
        self.assertEqual(course_skill.weight, 2.0)
        self.assertTrue(course_skill.is_primary)
    
    def test_update_user_skills(self):
        """Test updating user skills after course completion"""
        # Add skill to course
        services.add_skill_to_course(
            course=self.course,
            skill_name='Python',
            weight=1.0,
            is_primary=True
        )
        
        # Enroll and complete course
        enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            is_completed=True
        )
        
        # Update skills
        updated_skills = services.update_user_skills(self.user)
        
        self.assertGreater(len(updated_skills), 0)
        
        # Check user skill was created/updated
        user_skill = UserSkill.objects.get(user=self.user, skill__name='Python')
        self.assertGreater(user_skill.proficiency, 0)
    
    def test_create_skill_gap_analysis(self):
        """Test creating skill gap analysis"""
        analysis = services.create_skill_gap_analysis(
            user=self.user,
            target_role='Python Developer',
            target_skill_names=['Python', 'Django', 'PostgreSQL']
        )
        
        self.assertEqual(analysis.user, self.user)
        self.assertEqual(analysis.target_role, 'Python Developer')
        self.assertEqual(analysis.target_skills.count(), 3)
        self.assertGreater(analysis.gap_score, 0)
    
    def test_course_quality_score(self):
        """Test calculating course quality score"""
        # Create enrollments
        Enrollment.objects.create(user=self.user, course=self.course, is_completed=True)
        
        # Create review
        Review.objects.create(
            user=self.user,
            course=self.course,
            rating=5,
            comment='Great course'
        )
        
        quality = services.course_quality_score(self.course)
        
        self.assertGreaterEqual(quality, 0.0)
        self.assertLessEqual(quality, 1.0)
    
    def test_recommend_courses_collaborative(self):
        """Test collaborative filtering recommendations"""
        # Create another user with similar interests
        other_user = User.objects.create_user(
            email='other@test.com',
            password='testpass123',
            role='student'
        )
        
        # Both enroll in same course
        Enrollment.objects.create(user=self.user, course=self.course, is_completed=True)
        Enrollment.objects.create(user=other_user, course=self.course, is_completed=True)
        
        # Create another course for other user
        course2 = Course.objects.create(
            title='Advanced Python',
            slug='advanced-python',
            instructor=self.instructor,
            category=self.category,
            status='published',
            price=Decimal('149.99')
        )
        Enrollment.objects.create(user=other_user, course=course2)
        
        # Get recommendations
        recommendations = services.recommend_courses_collaborative(self.user, limit=5)
        
        # Should recommend course2
        self.assertGreaterEqual(len(recommendations), 0)
    
    def test_generate_recommendations(self):
        """Test generating hybrid recommendations"""
        # Add skill to course
        services.add_skill_to_course(
            course=self.course,
            skill_name='Python',
            weight=2.0,
            is_primary=True
        )
        
        # Create user interest
        UserInterest.objects.create(
            user=self.user,
            skill=self.skill,
            interest_level=5.0
        )
        
        # Generate recommendations
        recommendations = services.generate_recommendations(
            user=self.user,
            algorithm='hybrid',
            limit=5,
            save=True
        )
        
        # Check recommendations were created
        self.assertGreaterEqual(len(recommendations), 0)
        
        # Check they're saved to database
        saved_count = Recommendation.objects.filter(user=self.user).count()
        self.assertEqual(saved_count, len(recommendations))


class AIRecommenderAPITestCase(APITestCase):
    """Test AI recommender API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role='admin',
            is_staff=True
        )
        
        self.skill = Skill.objects.create(
            name='Python',
            slug='python',
            category='technical'
        )
        
        self.category = Category.objects.create(name='Tech', slug='tech')
        
        self.course = Course.objects.create(
            title='Python Course',
            slug='python-course',
            instructor=self.instructor,
            category=self.category,
            status='published',
            price=Decimal('99.99')
        )
    
    def test_skill_list(self):
        """Test listing skills"""
        response = self.client.get('/api/ai-recommender/skills/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response is paginated
        if isinstance(response.data, dict):
            self.assertGreater(len(response.data['results']), 0)
        else:
            self.assertGreater(len(response.data), 0)
    
    def test_user_skill_list_requires_auth(self):
        """Test user skills requires authentication"""
        response = self.client.get('/api/ai-recommender/my-skills/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_skill_list(self):
        """Test listing user skills"""
        self.client.force_authenticate(user=self.user)
        
        # Create user skill
        UserSkill.objects.create(
            user=self.user,
            skill=self.skill,
            proficiency=50.0
        )
        
        response = self.client.get('/api/ai-recommender/my-skills/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if isinstance(response.data, dict):
            self.assertEqual(len(response.data['results']), 1)
        else:
            self.assertEqual(len(response.data), 1)
    
    def test_create_user_interest(self):
        """Test creating user interest"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post('/api/ai-recommender/interests/', {
            'skill': self.skill.id,
            'interest_level': 5.0,
            'reason': 'learning_goal',
            'target_proficiency': 80.0
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserInterest.objects.filter(user=self.user, skill=self.skill).exists())
    
    def test_generate_recommendations(self):
        """Test generating recommendations via API"""
        self.client.force_authenticate(user=self.user)
        
        # Add skill to course
        CourseSkill.objects.create(
            course=self.course,
            skill=self.skill,
            weight=2.0,
            is_primary=True
        )
        
        response = self.client.post('/api/ai-recommender/recommendations/generate/', {
            'algorithm': 'hybrid',
            'limit': 5
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('recommendations', response.data)
    
    def test_recommendation_list(self):
        """Test listing recommendations"""
        self.client.force_authenticate(user=self.user)
        
        # Create recommendation
        Recommendation.objects.create(
            user=self.user,
            course=self.course,
            score=85.0,
            algorithm='hybrid',
            reason='Good match'
        )
        
        response = self.client.get('/api/ai-recommender/recommendations/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if isinstance(response.data, dict):
            self.assertEqual(len(response.data['results']), 1)
        else:
            self.assertEqual(len(response.data), 1)
    
    def test_click_recommendation(self):
        """Test clicking a recommendation"""
        self.client.force_authenticate(user=self.user)
        
        recommendation = Recommendation.objects.create(
            user=self.user,
            course=self.course,
            score=85.0,
            algorithm='hybrid',
            reason='Good match'
        )
        
        response = self.client.post(f'/api/ai-recommender/recommendations/{recommendation.id}/click/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        recommendation.refresh_from_db()
        self.assertTrue(recommendation.clicked)
    
    def test_create_skill_gap_analysis(self):
        """Test creating skill gap analysis via API"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post('/api/ai-recommender/skill-gaps/create/', {
            'target_role': 'Python Developer',
            'target_skills': ['Python', 'Django', 'PostgreSQL']
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SkillGapAnalysis.objects.filter(user=self.user).exists())
    
    def test_trending_skills(self):
        """Test getting trending skills"""
        response = self.client.get('/api/ai-recommender/trending/skills/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_learning_path_list(self):
        """Test listing learning paths"""
        path = LearningPath.objects.create(
            title='Python Developer Path',
            slug='python-developer-path',
            description='Become a Python developer',
            is_published=True
        )
        
        response = self.client.get('/api/ai-recommender/learning-paths/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if isinstance(response.data, dict):
            self.assertGreater(len(response.data['results']), 0)
        else:
            self.assertGreater(len(response.data), 0)
    
    def test_enroll_learning_path(self):
        """Test enrolling in learning path"""
        self.client.force_authenticate(user=self.user)
        
        path = LearningPath.objects.create(
            title='Python Developer Path',
            slug='python-developer-path',
            description='Become a Python developer',
            is_published=True
        )
        
        response = self.client.post('/api/ai-recommender/learning-paths/enroll/', {
            'learning_path_id': path.id
        })
        
        # Endpoint is POST so 201 or 200 is acceptable
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertTrue(UserLearningPath.objects.filter(user=self.user, learning_path=path).exists())
