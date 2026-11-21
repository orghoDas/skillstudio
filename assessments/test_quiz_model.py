"""ASM-04: quiz drafts, total_marks sync, difficulty choices, and analytics that
ignore in-progress attempts and admit platform admins."""

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from assessments.models import QuestionOption, Quiz, QuizAttempt, QuizQuestion
from courses.models import Category, Course, Lesson, Module


class QuizModelTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(email="t@instructor.com", password="pw", role="instructor")
        self.admin = User.objects.create_user(email="root@example.com", password="pw", role="admin")
        self.student = User.objects.create_user(email="s@student.com", password="pw")
        course = Course.objects.create(title="C", instructor=self.instructor,
                                       category=Category.objects.create(name="T", slug="t"), status="published")
        module = Module.objects.create(course=course, title="M", position=1)
        self.lesson = Lesson.objects.create(module=module, title="Quiz lesson", content_type="quiz", position=1)
        self.course = course

    def manage(self, payload):
        return self.client.post(f"/api/assessments/quiz/lesson/{self.lesson.id}/manage/", payload, format="json")

    def payload(self, **extra):
        return {"title": "Q", "questions": [{"text": "2+2?", "marks": 3, "options": [
            {"text": "4", "is_correct": True}, {"text": "5", "is_correct": False}]}], **extra}

    def test_new_quiz_is_a_draft_until_published(self):
        self.assertFalse(Quiz.objects.create(lesson=self.lesson).is_published)

        self.client.force_authenticate(self.instructor)
        self.assertEqual(self.manage(self.payload()).status_code, status.HTTP_200_OK)
        quiz = Quiz.objects.get(lesson=self.lesson)
        self.assertFalse(quiz.is_published)

        self.client.force_authenticate(self.student)
        response = self.client.get(f"/api/assessments/quiz/lesson/{self.lesson.id}/")
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

        self.client.force_authenticate(self.instructor)
        self.manage({"is_published": True})  # settings-only update keeps the questions
        quiz.refresh_from_db()
        self.assertTrue(quiz.is_published)
        self.assertEqual(quiz.questions.count(), 1)

    def test_total_marks_follows_the_questions(self):
        quiz = Quiz.objects.create(lesson=self.lesson, title="Q", total_marks=99)
        first = QuizQuestion.objects.create(quiz=quiz, question_text="a", marks=2)
        QuizQuestion.objects.create(quiz=quiz, question_text="b", marks=5)
        quiz.refresh_from_db()
        self.assertEqual(quiz.total_marks, 7)

        first.marks = 4
        first.save()  # e.g. edited in the admin
        first.refresh_from_db()
        quiz.refresh_from_db()
        self.assertEqual(quiz.total_marks, 9)

        first.delete()
        quiz.refresh_from_db()
        self.assertEqual(quiz.total_marks, 5)

        quiz.delete()  # cascading question deletes must not fail

    def test_manage_view_reports_synced_total(self):
        self.client.force_authenticate(self.instructor)
        response = self.manage(self.payload())
        self.assertEqual(response.data["quiz"]["total_marks"], 3)
        self.assertEqual(Quiz.objects.get(lesson=self.lesson).total_marks, 3)

    def test_difficulty_has_fixed_choices_and_str(self):
        quiz = Quiz.objects.create(lesson=self.lesson, title="Final check")
        question = QuizQuestion(quiz=quiz, question_text="x", difficulty="impossible")
        with self.assertRaises(Exception):
            question.full_clean()
        self.assertEqual(str(quiz), "Final check")
        self.assertIsNotNone(quiz.created_at)

    def test_analytics_ignore_in_progress_attempts_and_allow_admins(self):
        quiz = Quiz.objects.create(lesson=self.lesson, title="Q", is_published=True)
        question = QuizQuestion.objects.create(quiz=quiz, question_text="q", marks=1)
        right = QuestionOption.objects.create(question=question, option_text="r", is_correct=True)
        QuizAttempt.objects.create(quiz=quiz, user=self.student, answers={str(question.id): str(right.id)},
                                   score=1, passed=True, completed_at=timezone.now())
        other = User.objects.create_user(email="o@student.com", password="pw")
        QuizAttempt.objects.create(quiz=quiz, user=other, answers={str(question.id): "0"})  # still in progress

        self.client.force_authenticate(self.admin)
        overview = self.client.get(f"/api/assessments/analytics/course/{self.course.id}/overview/")
        self.assertEqual(overview.status_code, status.HTTP_200_OK, overview.data)
        stats = list(overview.data["quiz_overview"])
        self.assertEqual((stats[0]["attempts"], stats[0]["pass_count"]), (1, 1))

        per_question = self.client.get(f"/api/assessments/analytics/quiz/{quiz.id}/questions/")
        self.assertEqual(per_question.status_code, status.HTTP_200_OK)
        self.assertEqual((per_question.data[0]["attempts"], per_question.data[0]["wrong_attempts"]), (1, 0))

        self.client.force_authenticate(self.student)
        denied = self.client.get(f"/api/assessments/analytics/quiz/{quiz.id}/questions/")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
