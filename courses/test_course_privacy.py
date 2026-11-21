from rest_framework.test import APITestCase

from accounts.models import Profile, User
from courses.models import Course
from enrollments.models import Enrollment


class CoursePrivacyTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email='course-owner@example.test', username='course-owner@example.test', role='instructor',
        )
        cls.admin = User.objects.create_user(email='reviewer@example.test', role='admin')
        cls.other_instructor = User.objects.create_user(email='other-instructor@example.test', role='instructor')
        cls.student = User.objects.create_user(email='private-student@example.test')
        Profile.objects.update_or_create(user=cls.owner, defaults={'first_name': 'Rina', 'last_name': 'Das'})
        cls.published = Course.objects.create(
            title='Published course', instructor=cls.owner, status='published', rejection_reason='Private review notes',
        )
        cls.draft = Course.objects.create(
            title='Draft course', instructor=cls.owner, rejection_reason='Private draft notes',
        )
        Enrollment.objects.create(course=cls.published, user=cls.student)

    def course_responses(self):
        return [
            ('/api/courses/', list),
            (f'/api/courses/?instructor={self.owner.pk}', list),
            (f'/api/courses/{self.published.pk}/', dict),
            (f'/api/courses/{self.published.slug}/', dict),
        ]

    def test_catalog_shows_instructor_ids_and_names_without_private_fields(self):
        for viewer in (None, self.student, self.other_instructor):
            self.client.force_authenticate(viewer)
            for url, shape in self.course_responses():
                with self.subTest(viewer=viewer, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200, response.data)
                    course = response.data['results'][0] if shape is list else response.data
                    self.assertEqual((course['instructor_id'], course['instructor_name']), (self.owner.pk, 'Rina Das'))
                    self.assertNotIn('instructor_email', course)
                    self.assertNotIn('rejection_reason', course)
                    self.assertNotContains(response, self.owner.email)

    def test_missing_or_unsafe_profile_name_uses_a_generic_display_name(self):
        for copied_email in (True, False):
            with self.subTest(copied_email=copied_email):
                if copied_email:
                    Profile.objects.filter(user=self.owner).update(
                        full_name=self.owner.email.upper(), first_name=None, last_name=None,
                    )
                else:
                    Profile.objects.filter(user=self.owner).delete()
                detail = self.client.get(f'/api/courses/{self.published.pk}/')
                self.assertEqual(detail.data['instructor_name'], 'Instructor')
                self.assertNotContains(detail, self.owner.email)
                featured = self.client.get('/api/instructors/featured/')
                listed = next(instructor for instructor in featured.data if instructor['id'] == self.owner.pk)
                self.assertEqual(listed['name'], 'Instructor')
                self.assertNotContains(featured, self.owner.email)

    def test_review_notes_are_visible_to_the_course_owner_and_platform_admin(self):
        for manager in (self.owner, self.admin):
            self.client.force_authenticate(manager)
            for course in (self.draft, self.published):
                with self.subTest(manager=manager.role, course=course.status):
                    response = self.client.get(f'/api/courses/{course.slug}/')
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data['rejection_reason'], course.rejection_reason)
                    self.assertNotIn('instructor_email', response.data)
        self.client.force_authenticate(self.other_instructor)
        self.assertEqual(self.client.get(f'/api/courses/{self.draft.slug}/').status_code, 403)

    def test_student_contact_details_are_scoped_to_the_instructors_courses(self):
        url = '/api/instructors/dashboard/'
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(url).data['students'][0]['student_email'], self.student.email)
        for viewer in (self.other_instructor, self.admin):
            self.client.force_authenticate(viewer)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['students'], [])
            self.assertNotContains(response, self.student.email)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)
