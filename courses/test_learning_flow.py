"""
End-to-end learning flow tests:

* LRN-01 — lesson content endpoint (/api/courses/lessons/<id>/content/) and the
  curriculum share one progression rule.
* LRN-02 — video URLs are parsed/validated; watch time completes video lessons.
* LRN-03 — a completed course stays accessible; canceled enrollments don't.
"""

from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import timezone
from django.urls import resolve
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from courses.models import Category, Course, Lesson, Module
from courses.serializers import LessonCreateUpdateSerializer
from courses.video import parse_video_url
from enrollments.models import Enrollment, LessonProgress
from enrollments.services import lesson_lock_state, ordered_course_lessons

YOUTUBE = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


class VideoUrlParserTests(SimpleTestCase):
    def test_supported_sources(self):
        cases = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s": {"provider": "youtube", "id": "dQw4w9WgXcQ"},
            "https://youtu.be/dQw4w9WgXcQ": {"provider": "youtube", "id": "dQw4w9WgXcQ"},
            "https://www.youtube.com/embed/dQw4w9WgXcQ": {"provider": "youtube", "id": "dQw4w9WgXcQ"},
            "https://m.youtube.com/shorts/dQw4w9WgXcQ": {"provider": "youtube", "id": "dQw4w9WgXcQ"},
            "https://vimeo.com/76979871": {"provider": "vimeo", "id": "76979871"},
            "https://player.vimeo.com/video/76979871": {"provider": "vimeo", "id": "76979871"},
            "https://cdn.example.com/media/intro.MP4": {"provider": "file", "url": "https://cdn.example.com/media/intro.MP4"},
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(parse_video_url(url), expected)

    def test_unsupported_or_unsafe_sources(self):
        for url in ["", None, "javascript:alert(1)", "ftp://x.com/a.mp4", "https://example.com/watch",
                    "https://www.youtube.com/watch?v=<script>", "https://evil.com/?youtube.com",
                    "https://vimeo.com/channels/staffpicks"]:
            with self.subTest(url=url):
                self.assertIsNone(parse_video_url(url))

    def test_lesson_serializer_rejects_unplayable_links(self):
        bad = LessonCreateUpdateSerializer(data={"title": "x", "video_url": "https://example.com/page"})
        self.assertFalse(bad.is_valid())
        self.assertIn("video_url", bad.errors)
        good = LessonCreateUpdateSerializer(data={"title": "x", "video_url": YOUTUBE})
        self.assertTrue(good.is_valid(), good.errors)


class LearningFlowFixture:
    def setUp(self):
        super().setUp()
        self.student = User.objects.create_user(email="student@test.com", password="pw", role="student")
        self.instructor = User.objects.create_user(email="teacher@test.com", password="pw", role="instructor")
        self.category = Category.objects.create(name="Tech", slug="tech")
        self.course = Course.objects.create(
            title="Course", instructor=self.instructor, category=self.category,
            status="published", price=Decimal("10.00"),
        )
        self.module = Module.objects.create(course=self.course, title="M1", position=1)
        self.free_intro = Lesson.objects.create(module=self.module, title="Intro", position=1, is_free=True,
                                                content_type="text", content_text="Welcome")
        self.lesson1 = Lesson.objects.create(module=self.module, title="L1", position=2, content_type="text",
                                             content_text="Body 1")
        self.lesson2 = Lesson.objects.create(module=self.module, title="L2", position=3, content_type="video",
                                             video_url=YOUTUBE, duration_seconds=100)

    def enroll(self, status_="active"):
        return Enrollment.objects.create(user=self.student, course=self.course, status=status_)

    def complete(self, enrollment, lesson):
        LessonProgress.objects.create(enrollment=enrollment, user=self.student, lesson=lesson, is_completed=True)

    def content_url(self, lesson):
        return f"/api/courses/lessons/{lesson.id}/content/"


class LessonLockRuleTests(LearningFlowFixture, APITestCase):
    def test_free_lessons_never_lock_or_gate(self):
        enrollment = self.enroll()
        state = lesson_lock_state(enrollment, ordered_course_lessons(self.course))
        self.assertEqual(state, {self.free_intro.id: False, self.lesson1.id: False, self.lesson2.id: True})
        self.complete(enrollment, self.lesson1)
        self.assertFalse(lesson_lock_state(enrollment)[self.lesson2.id])

    def test_no_enrollment_means_nothing_locked(self):
        self.assertFalse(any(lesson_lock_state(None, ordered_course_lessons(self.course)).values()))


class LessonContentEndpointTests(LearningFlowFixture, APITestCase):
    """LRN-01."""

    def test_route_resolves_to_content_view(self):
        self.assertEqual(resolve(self.content_url(self.lesson1)).func.view_class.__name__, "LessonDetailView")

    def test_enrolled_student_gets_full_content(self):
        self.enroll()
        self.client.force_authenticate(self.student)
        response = self.client.get(self.content_url(self.lesson1))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content_text"], "Body 1")
        self.lesson1.refresh_from_db()
        self.assertEqual(self.lesson1.view_count, 1)

    def test_video_lesson_returns_player_descriptor(self):
        enrollment = self.enroll()
        self.complete(enrollment, self.lesson1)
        self.client.force_authenticate(self.student)
        response = self.client.get(self.content_url(self.lesson2))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["video"], {"provider": "youtube", "id": "dQw4w9WgXcQ"})

    def test_locked_lesson_is_refused_with_code(self):
        self.enroll()
        self.client.force_authenticate(self.student)
        response = self.client.get(self.content_url(self.lesson2))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "lesson_locked")
        self.lesson2.refresh_from_db()
        self.assertEqual(self.lesson2.view_count, 0)  # refused views aren't counted

    def test_unenrolled_student_gets_free_lesson_only(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(self.content_url(self.free_intro)).status_code, status.HTTP_200_OK)
        response = self.client.get(self.content_url(self.lesson1))
        self.assertEqual((response.status_code, response.data["code"]), (403, "not_enrolled"))

    def test_owner_sees_everything_and_draft_is_hidden_from_others(self):
        self.client.force_authenticate(self.instructor)
        self.assertEqual(self.client.get(self.content_url(self.lesson2)).status_code, status.HTTP_200_OK)
        self.course.status = "draft"
        self.course.save()
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(self.content_url(self.free_intro)).status_code, status.HTTP_404_NOT_FOUND)

    def test_curriculum_matches_content_endpoint(self):
        self.enroll()
        self.client.force_authenticate(self.student)
        curriculum = self.client.get(f"/api/courses/{self.course.id}/curriculum/")
        self.assertEqual(curriculum.status_code, status.HTTP_200_OK)
        lessons = {l["id"]: l for m in curriculum.data["modules"] for l in m["lessons"]}
        for lesson_id, summary in lessons.items():
            lesson = Lesson.objects.get(id=lesson_id)
            served = self.client.get(self.content_url(lesson)).status_code == 200
            with self.subTest(lesson=lesson.title):
                self.assertEqual(served, not summary["is_locked"])


class WatchTimeCompletesVideoLessonTests(LearningFlowFixture, APITestCase):
    """LRN-02: reporting real watch time completes the video lesson and the course."""

    def test_watch_time_completes_lesson_and_course(self):
        enrollment = self.enroll()
        self.complete(enrollment, self.lesson1)
        self.client.force_authenticate(self.student)
        url = f"/api/enrollments/lessons/{self.lesson2.id}/watch-time/"

        first = self.client.patch(url, {"watch_time_delta": 50}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        self.assertFalse(first.data["completed"])
        # Pretend 60s of real playback time passed before the next report
        # (the server only accepts deltas plausible for the elapsed time).
        LessonProgress.objects.filter(enrollment=enrollment, lesson=self.lesson2).update(
            updated_at=timezone.now() - timedelta(seconds=60)
        )
        second = self.client.patch(url, {"watch_time_delta": 40}, format="json")
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertTrue(second.data["completed"])

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, "completed")


class CompletedCourseStaysAccessibleTests(LearningFlowFixture, APITestCase):
    """LRN-03."""

    def setUp(self):
        super().setUp()
        self.enrollment = self.enroll("completed")
        for lesson in (self.lesson1, self.lesson2):
            self.complete(self.enrollment, lesson)
        self.client.force_authenticate(self.student)

    def test_content_curriculum_and_progress_still_work(self):
        for url in [
            self.content_url(self.lesson2),
            f"/api/courses/{self.course.id}/curriculum/",
            f"/api/enrollments/courses/{self.course.id}/progress/",
            f"/api/enrollments/lessons/{self.lesson2.id}/progress/",
            f"/api/enrollments/courses/{self.course.id}/resume-lesson/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_course_detail_shows_enrolled_and_unlocked(self):
        response = self.client.get(f"/api/courses/{self.course.id}/")
        self.assertTrue(response.data["is_enrolled"])
        locks = [l["is_locked"] for m in response.data["modules"] for l in m["lessons"]]
        self.assertFalse(any(locks))

    def test_notes_quiz_and_exams_still_work(self):
        from assessments.models import Quiz
        from exams.models import Exam

        note = self.client.post("/api/students/notes/", {"lesson": self.lesson1.id, "content": "Review"}, format="json")
        self.assertEqual(note.status_code, status.HTTP_201_CREATED, note.data)

        Quiz.objects.create(is_published=True, lesson=self.lesson1, title="Q", total_marks=1)
        self.assertEqual(self.client.get(f"/api/assessments/quiz/lesson/{self.lesson1.id}/").status_code, 200)

        exam = Exam.objects.create(course=self.course, title="Final", duration_minutes=30,
                                   status="published", created_by=self.instructor)
        listing = self.client.get("/api/exams/")
        ids = [e["id"] for e in (listing.data.get("results", listing.data) if isinstance(listing.data, dict) else listing.data)]
        self.assertIn(exam.id, ids)

    def test_enrolling_again_is_not_charged(self):
        response = self.client.post("/api/enrollments/enroll/", {"course_id": self.course.id}, format="json")
        self.assertEqual((response.status_code, response.data["outcome"]), (200, "already_enrolled"))

    def test_canceled_enrollment_does_not_grant_access(self):
        Enrollment.objects.filter(pk=self.enrollment.pk).update(status="canceled")
        response = self.client.get(self.content_url(self.lesson1))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.get(f"/api/courses/{self.course.id}/curriculum/").status_code, status.HTTP_403_FORBIDDEN
        )
