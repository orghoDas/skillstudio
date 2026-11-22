"""
ASM-01: unpublished/empty quizzes never block completion; failed quizzes can be
retaken up to Quiz.max_attempts. ASM-02: the time limit is enforced by the
server — answers posted after the deadline are ignored.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from assessments.models import QuestionOption, Quiz, QuizAttempt, QuizQuestion
from assessments.services import (
    QUIZ_SUBMIT_GRACE_SECONDS, is_lesson_assessment_completed, start_quiz_attempt,
)
from courses.models import Category, Course, Lesson, Module
from enrollments.models import Enrollment


class QuizFixture:
    def setUp(self):
        super().setUp()
        self.student = User.objects.create_user(email="s@student.com", password="pw", role="student")
        self.instructor = User.objects.create_user(email="t@instructor.com", password="pw", role="instructor")
        category = Category.objects.create(name="Tech", slug="tech")
        self.course = Course.objects.create(title="C", instructor=self.instructor, category=category,
                                            status="published")
        module = Module.objects.create(course=self.course, title="M", position=1)
        self.lesson = Lesson.objects.create(module=module, title="Quiz lesson", content_type="quiz", position=1)
        Enrollment.objects.create(user=self.student, course=self.course)
        self.quiz = Quiz.objects.create(is_published=True, lesson=self.lesson, title="Q", passing_percentage=50, max_attempts=2)
        self.question = QuizQuestion.objects.create(quiz=self.quiz, question_text="2+2?", marks=1)
        self.right = QuestionOption.objects.create(question=self.question, option_text="4", is_correct=True)
        self.wrong = QuestionOption.objects.create(question=self.question, option_text="5", is_correct=False)
        self.client.force_authenticate(self.student)

    def start(self):
        response = self.client.post(f"/api/assessments/quiz/{self.quiz.id}/start/")
        return response

    def submit(self, attempt_id, option):
        return self.client.post(
            f"/api/assessments/quiz/attempt/{attempt_id}/submit/",
            {"answers": {str(self.question.id): str(option.id)}}, format="json",
        )

    def complete_lesson(self):
        return self.client.post(f"/api/enrollments/lessons/{self.lesson.id}/complete/")


class QuizCompletionRuleTests(QuizFixture, APITestCase):
    """ASM-01."""

    def test_unpublished_quiz_does_not_block_completion(self):
        self.quiz.is_published = False
        self.quiz.save()
        self.assertTrue(is_lesson_assessment_completed(self.student, self.lesson))
        self.assertEqual(self.complete_lesson().status_code, status.HTTP_200_OK)

    def test_quiz_without_questions_does_not_block_completion(self):
        self.question.delete()
        self.assertTrue(is_lesson_assessment_completed(self.student, self.lesson))

    def test_published_quiz_blocks_until_passed(self):
        self.assertFalse(is_lesson_assessment_completed(self.student, self.lesson))
        self.assertEqual(self.complete_lesson().status_code, status.HTTP_400_BAD_REQUEST)

    def test_fail_then_retake_and_pass_completes_lesson(self):
        first = self.start().data
        self.assertEqual(self.submit(first["id"], self.wrong).data["passed"], False)
        self.assertEqual(self.complete_lesson().status_code, status.HTTP_400_BAD_REQUEST)

        second = self.start()
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["attempt_number"], 2)
        self.assertTrue(self.submit(second.data["id"], self.right).data["passed"])
        self.assertEqual(self.complete_lesson().status_code, status.HTTP_200_OK)

    def test_attempt_limit_is_enforced(self):
        for _ in range(2):
            attempt = self.start().data
            self.submit(attempt["id"], self.wrong)
        response = self.start()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['detail'], "You have no attempts left for this quiz.")

    def test_unlimited_attempts(self):
        self.quiz.max_attempts = None
        self.quiz.save()
        for _ in range(5):
            attempt = self.start().data
            self.submit(attempt["id"], self.wrong)
        self.assertEqual(self.start().status_code, status.HTTP_200_OK)

    def test_one_open_attempt_is_resumed(self):
        first = self.start().data
        again = self.start().data
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(QuizAttempt.objects.filter(quiz=self.quiz, user=self.student).count(), 1)

    def test_quiz_detail_reports_attempt_status(self):
        attempt = self.start().data
        self.submit(attempt["id"], self.wrong)
        status_ = self.client.get(f"/api/assessments/quiz/lesson/{self.lesson.id}/").data["attempt_status"]
        self.assertEqual(
            {k: status_[k] for k in ("attempts_used", "max_attempts", "attempts_remaining", "has_passed", "can_start")},
            {"attempts_used": 1, "max_attempts": 2, "attempts_remaining": 1, "has_passed": False, "can_start": True},
        )
        self.assertFalse(status_["last_attempt"]["passed"])

    def test_unpublished_quiz_hidden_from_students_visible_to_owner(self):
        self.quiz.is_published = False
        self.quiz.save()
        url = f"/api/assessments/quiz/lesson/{self.lesson.id}/"
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.instructor)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_instructor_sets_attempt_limit(self):
        Course.objects.filter(pk=self.course.pk).update(status="draft")
        self.client.force_authenticate(self.instructor)
        url = f"/api/assessments/quiz/lesson/{self.lesson.id}/manage/"
        self.assertEqual(self.client.post(url, {"max_attempts": 5}, format="json").status_code, 200)
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.max_attempts, 5)
        self.client.post(url, {"max_attempts": 0}, format="json")  # 0 = unlimited
        self.quiz.refresh_from_db()
        self.assertIsNone(self.quiz.max_attempts)
        bad = self.client.post(url, {"max_attempts": -3}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)


class QuizTimeLimitTests(QuizFixture, APITestCase):
    """ASM-02."""

    def setUp(self):
        super().setUp()
        self.quiz.time_limit_minutes = 1
        self.quiz.save()

    def expire(self, attempt_id, extra_seconds):
        QuizAttempt.objects.filter(pk=attempt_id).update(
            started_at=timezone.now() - timedelta(seconds=60 + extra_seconds)
        )

    def test_answers_posted_after_deadline_are_ignored(self):
        attempt = self.start().data
        self.expire(attempt["id"], QUIZ_SUBMIT_GRACE_SECONDS + 5)
        response = self.submit(attempt["id"], self.right)  # all correct, but too late
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data["score"]), 0.0)
        self.assertFalse(response.data["passed"])
        self.assertTrue(response.data["is_auto_submitted"])

    def test_answers_saved_in_time_are_graded_after_deadline(self):
        attempt = self.start().data
        saved = self.client.post(
            f"/api/assessments/quiz/attempt/{attempt['id']}/answer/submit/",
            {"question_id": self.question.id, "option_id": self.right.id}, format="json",
        )
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.expire(attempt["id"], QUIZ_SUBMIT_GRACE_SECONDS + 5)
        response = self.submit(attempt["id"], self.wrong)  # late change is ignored
        self.assertTrue(response.data["passed"])
        self.assertTrue(response.data["is_auto_submitted"])

    def test_submission_within_grace_period_counts(self):
        attempt = self.start().data
        self.expire(attempt["id"], QUIZ_SUBMIT_GRACE_SECONDS - 5)
        response = self.submit(attempt["id"], self.right)
        self.assertTrue(response.data["passed"])
        self.assertFalse(response.data["is_auto_submitted"])

    def test_saving_answer_after_deadline_auto_submits(self):
        attempt = self.start().data
        self.expire(attempt["id"], QUIZ_SUBMIT_GRACE_SECONDS + 5)
        response = self.client.post(
            f"/api/assessments/quiz/attempt/{attempt['id']}/answer/submit/",
            {"question_id": self.question.id, "option_id": self.right.id}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        graded = QuizAttempt.objects.get(pk=attempt["id"])
        self.assertIsNotNone(graded.completed_at)
        self.assertTrue(graded.is_auto_submitted)

    def test_expired_open_attempt_is_graded_when_starting_again(self):
        first = self.start().data
        self.expire(first["id"], QUIZ_SUBMIT_GRACE_SECONDS + 5)
        attempt = start_quiz_attempt(self.student, self.quiz)
        self.assertEqual(attempt.attempt_number, 2)
        expired = QuizAttempt.objects.get(pk=first["id"])
        self.assertTrue(expired.is_auto_submitted)
        self.assertIsNotNone(expired.completed_at)
