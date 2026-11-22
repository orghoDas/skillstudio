from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from assessments.models import Quiz, QuizQuestion, QuestionOption
from courses.models import Course, CourseTag, CourseVersion, Lesson, LessonResource, Module, Tag
from enrollments.models import Enrollment, LessonProgress
from exams.models import Exam, QuestionBank


class CourseLifecycleTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='version-owner@example.test', role='instructor')
        self.admin = User.objects.create_user(email='version-admin@example.test', role='admin')
        self.student = User.objects.create_user(email='version-student@example.test')
        self.course = Course.objects.create(title='Course version one', instructor=self.owner, price='10.00')
        self.module = Module.objects.create(course=self.course, title='Module')
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson', content_text='Original lesson text')
        self.base = f'/api/courses/{self.course.pk}/'
        self.client.force_authenticate(self.owner)

    def test_valid_edits_send_a_review_back_to_draft_and_require_resubmission(self):
        changes = (
            ('patch', f'{self.base}update/', {'title': 'Edited title'}),
            ('patch', f'/api/courses/sections/{self.module.pk}/', {'title': 'Edited module'}),
            ('patch', f'/api/courses/lessons/{self.lesson.pk}/update/', {'title': 'Edited lesson'}),
            ('post', f'/api/courses/sections/{self.module.pk}/lessons/', {'title': 'Another lesson'}),
            ('delete', f'/api/courses/lessons/{self.lesson.pk}/', {}),
        )
        for method, route, payload in changes:
            with self.subTest(method=method, route=route):
                self.assertEqual(self.client.post(f'{self.base}submit/').status_code, 200)
                response = getattr(self.client, method)(route, payload, format='json')
                self.assertIn(response.status_code, (200, 201, 204), response.data)
                self.course.refresh_from_db()
                self.assertEqual(self.course.status, 'draft')
                self.assertIsNone(self.course.submitted_for_review_at)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f'{self.base}publish/').status_code, 400)
        self.assertFalse(self.course.versions.exists())

    def test_invalid_edit_preserves_the_review_and_its_submission_time(self):
        self.assertEqual(self.client.post(f'{self.base}submit/').status_code, 200)
        self.course.refresh_from_db()
        submitted_at = self.course.submitted_for_review_at
        response = self.client.patch(f'{self.base}update/', {'title': ''}, format='json')
        self.assertEqual(response.status_code, 400)
        self.course.refresh_from_db()
        self.assertEqual((self.course.status, self.course.submitted_for_review_at), ('under_review', submitted_at))

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f'{self.base}reject/', {'reason': 'Clarify the examples'}, format='json').status_code, 200)
        self.course.refresh_from_db()
        self.assertEqual((self.course.status, self.course.rejection_reason), ('draft', 'Clarify the examples'))

    def test_course_submission_requires_a_published_quiz_with_questions(self):
        self.lesson.content_type = 'quiz'
        self.lesson.save(update_fields=['content_type'])
        self.assertEqual(self.client.post(f'{self.base}submit/').status_code, 400)
        manage = f'/api/assessments/quiz/lesson/{self.lesson.pk}/manage/'
        self.assertEqual(self.client.post(manage, {'is_published': True, 'questions': []}, format='json').status_code, 400)
        payload = {'is_published': True, 'questions': [{
            'text': 'Choose one', 'options': [{'text': 'A', 'is_correct': True}, {'text': 'B'}],
        }]}
        self.assertEqual(self.client.post(manage, payload, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'{self.base}submit/').status_code, 200)

    def test_revision_copies_content_and_keeps_original_learning_records(self):
        CourseTag.objects.create(course=self.course, tag=Tag.objects.create(name='revision tag'))
        LessonResource.objects.create(lesson=self.lesson, file_url='https://example.test/handout')
        quiz = Quiz.objects.create(lesson=self.lesson, is_published=True)
        item = QuizQuestion.objects.create(quiz=quiz, question_text='Quiz question', marks=2)
        QuestionOption.objects.create(question=item, option_text='Correct', is_correct=True)
        bank_item = QuestionBank.objects.create(course=self.course, question_text='Exam question')
        exam = Exam.objects.create(course=self.course, title='Final', duration_minutes=5, status='published')
        exam.questions.add(bank_item)

        self.assertEqual(self.client.post(f'{self.base}submit/').status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f'{self.base}publish/').status_code, 200)
        self.course.refresh_from_db()
        self.assertEqual(self.course.current_version.version_number, 1)
        enrollment = Enrollment.objects.create(user=self.student, course=self.course)
        recorded_progress = LessonProgress.objects.create(user=self.student, enrollment=enrollment, lesson=self.lesson)

        self.client.force_authenticate(self.owner)
        forked = self.client.post(f'{self.base}new-version/')
        self.assertEqual(forked.status_code, 201, forked.data)
        revision = Course.objects.get(pk=forked.data['id'])
        retried = self.client.post(f'{self.base}new-version/')
        self.assertEqual((retried.status_code, retried.data['id']), (200, revision.pk))
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, 'published')
        self.assertEqual((revision.status, revision.revision_of_id), ('draft', self.course.pk))
        self.assertNotEqual(revision.slug, self.course.slug)
        self.assertEqual(revision.tags.get().name, 'revision tag')
        new_lesson = revision.modules.get().lessons.get()
        self.assertEqual(new_lesson.resources.get().file_url, 'https://example.test/handout')
        self.assertEqual(new_lesson.quiz.questions.get().options.get().option_text, 'Correct')
        self.assertEqual(new_lesson.quiz.total_marks, 2)
        self.assertEqual(revision.exams.get().status, 'draft')
        self.assertEqual(revision.exams.get().questions.get().course_id, revision.pk)
        self.assertFalse(revision.enrollments.exists())
        self.assertFalse(LessonProgress.objects.filter(lesson=new_lesson).exists())

        lesson_url = f'/api/courses/lessons/{new_lesson.pk}/update/'
        self.assertEqual(self.client.patch(lesson_url, {'content_text': 'New version text'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/courses/{revision.pk}/submit/').status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f'/api/courses/{revision.pk}/publish/').status_code, 200)
        self.course.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual((self.course.status, revision.status), ('archived', 'published'))
        self.assertEqual(revision.current_version.version_number, 2)
        version_lesson = revision.current_version.data['modules'][0]['lessons'][0]
        self.assertEqual(version_lesson['content_text'], 'New version text')
        recorded_progress.refresh_from_db()
        self.assertEqual(recorded_progress.lesson_id, self.lesson.pk)

        self.client.force_authenticate(self.student)
        old = self.client.get(f'/api/courses/lessons/{self.lesson.pk}/content/')
        self.assertEqual(old.status_code, 200, old.data)
        self.assertEqual(old.data['content_text'], 'Original lesson text')
        self.assertEqual(self.client.get(f'{self.base}curriculum/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/courses/lessons/{new_lesson.pk}/content/').status_code, 403)
        self.client.force_authenticate(user=None)
        catalog = self.client.get('/api/courses/').data['results']
        self.assertIn(revision.pk, [record['id'] for record in catalog])
        self.assertNotIn(self.course.pk, [record['id'] for record in catalog])

    def test_archive_requires_a_manager_and_preserves_legacy_snapshots(self):
        Course.objects.filter(pk=self.course.pk).update(status='published')
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(f'{self.base}archive/').status_code, 403)
        self.assertEqual(self.client.post(f'{self.base}new-version/').status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post(f'{self.base}archive/').status_code, 200)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, 'archived')
        self.assertEqual(CourseVersion.objects.get(course=self.course).version_number, 1)
        self.assertEqual(self.client.post(f'{self.base}new-version/').status_code, 400)


class ReviewConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_edit_and_approval_cannot_publish_unreviewed_content(self):
        owner = User.objects.create_user(email='race-owner@example.test', role='instructor')
        admin = User.objects.create_user(email='race-admin@example.test', role='admin')
        course = Course.objects.create(title='Original', instructor=owner, status='under_review')
        module = Module.objects.create(course=course, title='Module')
        Lesson.objects.create(module=module, title='Lesson')
        barrier = Barrier(2, timeout=10)

        def request(user, approve=False):
            try:
                client = APIClient()
                client.force_authenticate(user)
                barrier.wait()
                if approve:
                    return client.post(f'/api/courses/{course.pk}/publish/').status_code
                return client.patch(f'/api/courses/{course.pk}/update/', {'title': 'Edited'}, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            edited = pool.submit(request, owner)
            approved = pool.submit(request, admin, approve=True)
            outcomes = edited.result(), approved.result()
        course.refresh_from_db()
        self.assertIn(outcomes, ((200, 400), (400, 200)))
        if course.status == 'published':
            self.assertEqual(course.current_version.data['course']['title'], 'Original')
        else:
            self.assertEqual((course.status, course.title), ('draft', 'Edited'))
