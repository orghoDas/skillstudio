"""EXM-01: exam questions stay hidden until the student is taking the exam, and
the exam window is enforced at start *and* at submit."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from courses.models import Category, Course
from enrollments.models import Enrollment
from exams.models import Exam, ExamAttempt, ExamResult, QuestionBank
from exams.services import start_exam_attempt, submit_exam_attempt


class ExamWindowTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(email="s@student.com", password="pw")
        self.instructor = User.objects.create_user(email="t@instructor.com", password="pw", role="instructor")
        course = Course.objects.create(title="C", instructor=self.instructor,
                                       category=Category.objects.create(name="T", slug="t"), status="published")
        Enrollment.objects.create(user=self.student, course=course)
        self.question = QuestionBank.objects.create(
            course=course, question_text="2+2?", question_type="mcq", marks=1, created_by=self.instructor,
            options=[{"text": "4", "is_correct": True}, {"text": "5", "is_correct": False}],
        )
        now = timezone.now()
        self.exam = Exam.objects.create(
            course=course, title="Final", duration_minutes=30, total_marks=1, passing_marks=1,
            status="published", max_attempts=1, created_by=self.instructor,
            start_datetime=now + timedelta(days=1), end_datetime=now + timedelta(days=2),
        )
        self.exam.questions.add(self.question)
        self.client.force_authenticate(self.student)

    def detail(self):
        return self.client.get(f"/api/exams/{self.exam.id}/")

    def start(self):
        return self.client.post(f"/api/exams/{self.exam.id}/start/")

    def open_window(self):
        now = timezone.now()
        Exam.objects.filter(pk=self.exam.pk).update(start_datetime=now - timedelta(hours=1),
                                                    end_datetime=now + timedelta(hours=1))
        self.exam.refresh_from_db()

    def test_questions_hidden_before_the_window_opens(self):
        response = self.detail()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((response.data["questions"], response.data["custom_questions"]), ([], []))
        self.assertTrue(response.data["questions_hidden"])
        self.assertEqual(response.data["availability"], "not_open_yet")
        self.assertIsNotNone(response.data["start_datetime"])  # students can see when it opens

    def test_start_before_window_explains_why(self):
        response = self.start()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "not_open_yet")
        self.assertIn("opens at", response.data["error"])

    def test_start_after_window_closed(self):
        now = timezone.now()
        Exam.objects.filter(pk=self.exam.pk).update(start_datetime=now - timedelta(days=2),
                                                    end_datetime=now - timedelta(days=1))
        response = self.start()
        self.assertEqual((response.status_code, response.data["code"]), (409, "closed"))

    def test_questions_visible_only_during_an_attempt(self):
        self.open_window()
        self.assertTrue(self.detail().data["questions_hidden"])  # open, but not started yet

        started = self.start()
        self.assertEqual(started.status_code, status.HTTP_201_CREATED)
        during = self.detail().data
        self.assertFalse(during["questions_hidden"])
        self.assertEqual([q["id"] for q in during["questions"]], [self.question.id])
        self.assertNotIn("is_correct", during["questions"][0]["options"][0])

        submitted = self.client.post(f"/api/exams/{self.exam.id}/submit/",
                                     {"attempt_id": started.data["id"], "answers": {str(self.question.id): 0}},
                                     format="json")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK, submitted.data)
        self.assertTrue(self.detail().data["questions_hidden"])  # hidden again afterwards

    def test_attempt_limit_reason(self):
        self.open_window()
        ExamAttempt.objects.create(exam=self.exam, user=self.student, attempt_number=1, status="completed")
        response = self.start()
        self.assertEqual((response.status_code, response.data["code"]), (409, "max_attempts"))

    def test_submit_rejects_attempt_started_outside_the_window(self):
        attempt = ExamAttempt.objects.create(exam=self.exam, user=self.student, attempt_number=1)  # window not open
        response = self.client.post(f"/api/exams/{self.exam.id}/submit/",
                                    {"attempt_id": attempt.id, "answers": {str(self.question.id): 0}}, format="json")
        self.assertEqual((response.status_code, response.data["code"]), (409, "outside_window"))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "in_progress")

    def test_submit_rejects_unpublished_exam(self):
        self.open_window()
        attempt_id = self.start().data["id"]
        Exam.objects.filter(pk=self.exam.pk).update(status="archived")
        response = self.client.post(f"/api/exams/{self.exam.id}/submit/",
                                    {"attempt_id": attempt_id, "answers": {}}, format="json")
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_409_CONFLICT))

    def test_attempt_started_inside_window_can_finish_after_it_closes(self):
        self.open_window()
        attempt_id = self.start().data["id"]
        # The window closes while the student is still within the attempt's duration.
        Exam.objects.filter(pk=self.exam.pk).update(end_datetime=timezone.now() - timedelta(seconds=1))
        ExamAttempt.objects.filter(pk=attempt_id).update(started_at=timezone.now() - timedelta(minutes=5))
        Exam.objects.filter(pk=self.exam.pk).update(start_datetime=timezone.now() - timedelta(hours=2))
        response = self.client.post(f"/api/exams/{self.exam.id}/submit/",
                                    {"attempt_id": attempt_id, "answers": {str(self.question.id): 0}},
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_expiry_grades_saved_answers_and_retries_return_the_same_result(self):
        self.open_window()
        attempt_id = self.start().data['id']
        base = f'/api/exams/{self.exam.pk}'
        answers = {'attempt_id': attempt_id, 'answers': {str(self.question.pk): 0}}
        saved = self.client.post(f'{base}/save-answers/', answers, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        resumed = self.client.get(f'{base}/?attempt={attempt_id}').data['attempt']
        self.assertEqual(resumed['answers'], answers['answers'])
        self.assertGreater(resumed['time_remaining'], 0)

        started_at = timezone.now() - timedelta(minutes=31)
        ExamAttempt.objects.filter(pk=attempt_id).update(started_at=started_at)
        late = {'attempt_id': attempt_id, 'answers': {str(self.question.pk): 1}}
        for _ in range(2):
            result = self.client.post(f'{base}/submit/', late, format='json')
            self.assertEqual(result.status_code, 200, result.data)
            self.assertEqual((result.data['score'], result.data['passed']), (Decimal('1.00'), True))
        attempt = ExamAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.answers, answers['answers'])
        self.assertEqual(attempt.completed_at, started_at + timedelta(minutes=30))
        self.assertEqual(ExamResult.objects.filter(attempt=attempt).count(), 1)
        self.assertTrue(self.detail().data['questions_hidden'])

    def test_expired_attempt_grades_even_if_start_refuses_another_attempt(self):
        self.open_window()
        attempt_id = self.start().data['id']
        ExamAttempt.objects.filter(pk=attempt_id).update(started_at=timezone.now() - timedelta(minutes=31))
        self.assertEqual(self.start().data['code'], 'max_attempts')
        self.assertEqual(ExamAttempt.objects.get(pk=attempt_id).status, 'completed')
        self.assertTrue(ExamResult.objects.filter(attempt_id=attempt_id).exists())

    def test_exam_and_bank_edits_cannot_change_an_attempts_questions_or_scoring(self):
        self.open_window()
        attempt_id = self.start().data['id']
        base = f'/api/exams/{self.exam.pk}'
        self.client.force_authenticate(self.instructor)
        self.assertEqual(self.client.patch(f'{base}/', {'questions': []}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'{base}/', {'duration_minutes': 60}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'{base}/').status_code, 400)
        question_url = f'/api/exams/questions/{self.question.pk}/'
        self.assertEqual(self.client.patch(question_url, {'marks': 3}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(question_url).status_code, 400)
        self.assertEqual(self.client.patch(f'{base}/', {'title': 'Updated title'}, format='json').status_code, 200)

        # Verify that even an out-of-band data change can't change an attempt.
        QuestionBank.objects.filter(pk=self.question.pk).update(
            question_text='Replaced', marks=2,
            options=[{'text': '4', 'is_correct': False}, {'text': '5', 'is_correct': True}],
        )
        Exam.objects.filter(pk=self.exam.pk).update(total_marks=2, passing_marks=2)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.detail().data['questions'][0]['question_text'], '2+2?')
        result = self.client.post(
            f'{base}/submit/', {'attempt_id': attempt_id, 'answers': {str(self.question.pk): 0}}, format='json',
        )
        self.assertEqual((result.data['score'], result.data['total_marks'], result.data['passed']), (1, 1, True))

    def test_status_and_total_are_server_owned_and_publish_validates_passing_marks(self):
        self.client.force_authenticate(self.instructor)
        payload = {'course': self.exam.course_id, 'title': 'Small exam', 'duration_minutes': 5}
        draft = self.client.post('/api/exams/', {**payload, 'status': 'published'}, format='json')
        self.assertEqual(draft.status_code, 201, draft.data)
        self.assertEqual(draft.data['status'], 'draft')
        publish_url = f"/api/exams/{draft.data['id']}/publish/"
        self.assertEqual(self.client.post(publish_url).data['code'], 'no_questions')

        payload.update(questions=[self.question.pk], total_marks=100)
        url = f"/api/exams/{draft.data['id']}/"
        invalid = self.client.patch(url, {**payload, 'passing_marks': 2}, format='json')
        self.assertEqual(invalid.status_code, 400, invalid.data)
        valid = self.client.patch(url, {**payload, 'status': 'published'}, format='json')
        self.assertEqual(valid.status_code, 200, valid.data)
        self.assertEqual((valid.data['total_marks'], valid.data['passing_marks']), ('1.00', '0.50'))
        self.assertEqual(valid.data['status'], 'draft')
        self.assertEqual(self.client.post(publish_url).data['exam']['status'], 'published')


class ConcurrentExamSubmissionTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_parallel_submissions_keep_one_grade_and_one_result(self):
        instructor = User.objects.create_user(email='parallel-instructor@example.test', role='instructor')
        student = User.objects.create_user(email='parallel-student@example.test')
        course = Course.objects.create(title='Parallel exam course', instructor=instructor)
        exam = Exam.objects.create(
            course=course, title='Parallel exam', duration_minutes=5, status='published',
            total_marks=1, passing_marks=1,
            custom_questions=[{
                'id': 'q1', 'marks': 1, 'question_text': 'Question',
                'options': [{'text': 'Yes', 'is_correct': True}, {'text': 'No', 'is_correct': False}],
            }],
        )
        attempt = start_exam_attempt(exam, student)
        barrier = Barrier(2, timeout=10)

        def submit(answer):
            try:
                barrier.wait()
                result = submit_exam_attempt(attempt, {'q1': answer})
                return result.score, result.answers
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(submit, [0, 1])
        self.assertEqual(first, second)
        self.assertEqual(ExamResult.objects.filter(attempt=attempt).count(), 1)
