"""EXM-01: exam questions stay hidden until the student is taking the exam, and
the exam window is enforced at start *and* at submit."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from courses.models import Category, Course
from enrollments.models import Enrollment
from exams.models import Exam, ExamAttempt, QuestionBank


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
