"""
Browser smoke tests (TEST-02): drive the real pages in headless Chromium and
fail on JavaScript errors, failing API calls, or broken core flows — the class
of bugs (FE-01, LRN-01, API-01, API-03) that server-side tests can't see.

Offline and hermetic: every request to another host (Tailwind CDN, Google
Fonts, YouTube/Vimeo player scripts) is answered with a local stub.

Skipped automatically unless Playwright and Chromium are installed
(`pip install -r requirements-dev.txt && python -m playwright install chromium`).
Run only these:  python manage.py test --tag browser
Skip them:       python manage.py test --exclude-tag browser
"""

import os
import unittest
from decimal import Decimal
from urllib.parse import urlparse

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.servers.basehttp import WSGIServer
from django.test import tag
from django.test.testcases import LiveServerThread, QuietWSGIRequestHandler

# Playwright's sync API runs an event loop in this thread; Django's ORM calls in
# the test body are still synchronous, so allow them.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - dev dependency not installed
    sync_playwright = None


def _launch_browser():
    """Start Chromium, or return (None, None) if it isn't available."""
    if sync_playwright is None:
        return None, None
    try:
        manager = sync_playwright().start()
        return manager, manager.chromium.launch()
    except Exception:  # browser binary not installed
        return None, None


class SerialLiveServerThread(LiveServerThread):
    """Handle one request at a time.

    With SQLite's in-memory test database, Django shares ONE connection between
    the test thread and every live-server request thread; a page firing several
    API calls at once could then collide on it (seen as random 500s). Serving
    requests sequentially in the server thread avoids that.
    """

    def _create_server(self, connections_override=None):
        return WSGIServer((self.host, self.port), QuietWSGIRequestHandler, allow_reuse_address=False)


# Answers for requests to other hosts (keeps the tests offline).
EXTERNAL_STUBS = {
    "cdn.tailwindcss.com": ("application/javascript", "window.tailwind = window.tailwind || {};"),
}


@tag("browser")
class BrowserSmokeTests(StaticLiveServerTestCase):
    host = "localhost"
    server_thread_class = SerialLiveServerThread

    @classmethod
    def setUpClass(cls):
        cls._playwright, cls.browser = _launch_browser()
        if cls.browser is None:
            raise unittest.SkipTest("Playwright/Chromium not installed (see requirements-dev.txt)")
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if cls.browser is not None:
            cls.browser.close()
            cls._playwright.stop()

    # ------------------------------------------------------------------ data

    def setUp(self):
        from accounts.models import Profile, User
        from courses.models import Category, Course, Lesson, Module

        self.password = "Sm0ke-test-pass!"
        self.student = User.objects.create_user(email="sam@student.com", password=self.password)
        self.instructor = User.objects.create_user(email="ivy@instructor.com", password=self.password,
                                                   role="instructor")
        Profile.objects.filter(user=self.instructor).update(full_name="Ivy Instructor")
        category = Category.objects.create(name="Programming", slug="programming")
        self.course = Course.objects.create(
            title="Smoke Free Course", instructor=self.instructor, category=category,
            status="published", is_free=True, price=Decimal("0"),
            description="A free course for browser smoke tests.",
        )
        module = Module.objects.create(course=self.course, title="Basics", position=1)
        self.lesson1 = Lesson.objects.create(module=module, title="Read me first", position=1,
                                             content_type="text", content_text="Body one of the course.")
        self.lesson2 = Lesson.objects.create(module=module, title="Second lesson", position=2,
                                             content_type="text", content_text="Body two.")
        self.draft = Course.objects.create(title="Smoke Draft", instructor=self.instructor, category=category,
                                           status="draft")
        draft_module = Module.objects.create(course=self.draft, title="Draft module", position=1)
        self.draft_lesson = Lesson.objects.create(module=draft_module, title="Delete me", position=1,
                                                  content_type="text", content_text="x")

    # --------------------------------------------------------------- helpers

    def new_page(self):
        context = self.browser.new_context()
        page = context.new_page()
        self.addCleanup(context.close)
        page.errors = []
        live_host = urlparse(self.live_server_url).netloc

        def route(route_obj):
            parsed = urlparse(route_obj.request.url)
            if parsed.netloc == live_host:
                return route_obj.continue_()
            content_type, body = EXTERNAL_STUBS.get(
                parsed.hostname,
                ("text/css", "") if parsed.path.endswith(".css") or "fonts" in (parsed.hostname or "")
                else ("application/javascript", ""),
            )
            return route_obj.fulfill(status=200, content_type=content_type, body=body)

        page.route("**/*", route)
        page.on("pageerror", lambda exc: page.errors.append(f"JS exception: {exc}"))

        def on_console(msg):
            # Resource failures are judged by HTTP status below, not by console text.
            if msg.type == "error" and "Failed to load resource" not in msg.text:
                page.errors.append(f"console.error: {msg.text}")

        def on_response(response):
            parsed = urlparse(response.url)
            if parsed.netloc == live_host and parsed.path.startswith("/api/") and response.status >= 400:
                if (parsed.path, response.status) not in getattr(page, "allowed_api_errors", set()):
                    page.errors.append(f"API {response.request.method} {parsed.path} -> {response.status}")

        page.on("console", on_console)
        page.on("response", on_response)
        return page

    def visit(self, page, path):
        page.goto(self.live_server_url + path)
        page.wait_for_load_state("networkidle")

    def login(self, page, user):
        self.visit(page, "/auth/login/")
        page.fill("#email", user.email)
        page.fill("#password", self.password)
        page.click("#login-btn")
        page.wait_for_url(lambda url: "/auth/login" not in url, timeout=15000)
        page.wait_for_load_state("networkidle")

    VISIBLE_MARKUP = ("<div", "<span", "<path", "<svg", "<button", "<a href", "&lt;", "&gt;")

    def assert_no_errors(self, page, where):
        self.assertEqual(page.errors, [], f"Errors on {where}")
        # Generated HTML that was escaped again shows up as literal markup text.
        text = page.inner_text("body")
        leaked = [m for m in self.VISIBLE_MARKUP if m in text]
        self.assertEqual(leaked, [], f"Raw markup visible as text on {where}")

    # ----------------------------------------------------------------- tests

    def test_public_pages_render_without_errors(self):
        page = self.new_page()
        for path in ["/", "/courses/", f"/courses/{self.course.slug}/", "/search/", "/browse/",
                     "/auth/login/", "/auth/register/"]:
            with self.subTest(path=path):
                page.errors.clear()
                self.visit(page, path)
                self.assert_no_errors(page, path)

    def test_student_pages_render_without_errors(self):
        from enrollments.models import Enrollment

        Enrollment.objects.create(user=self.student, course=self.course)  # so lists/cards render
        page = self.new_page()
        self.login(page, self.student)
        for path in ["/dashboard/", "/my-courses/", "/enrollments/", "/courses/", "/search/", "/browse/",
                     "/certificates/", "/wallet/", "/payments/history/", "/exams/", "/profile/", "/settings/",
                     f"/learn/{self.course.slug}/"]:
            with self.subTest(path=path):
                page.errors.clear()
                self.visit(page, path)
                self.assert_no_errors(page, path)

    def test_instructor_pages_render_without_errors(self):
        page = self.new_page()
        self.login(page, self.instructor)
        for path in ["/instructor/dashboard/", "/instructor/courses/", "/instructor/students/",
                     f"/instructor/courses/{self.draft.slug}/content/", f"/instructor/courses/{self.draft.slug}/edit/",
                     f"/instructor/courses/{self.draft.slug}/preview/",
                     f"/instructor/lessons/{self.draft_lesson.id}/edit/", "/exams/", "/exams/create/"]:
            with self.subTest(path=path):
                page.errors.clear()
                self.visit(page, path)
                self.assert_no_errors(page, path)

    def test_student_enrolls_learns_and_completes_a_lesson(self):
        from enrollments.models import Enrollment, LessonProgress

        page = self.new_page()
        self.login(page, self.student)

        self.visit(page, f"/courses/{self.course.slug}/")
        page.click("#enroll-btn")
        # The course page redirects to the dashboard after a successful enroll.
        page.wait_for_url("**/dashboard/", timeout=15000)
        page.wait_for_load_state("networkidle")
        self.assertTrue(Enrollment.objects.filter(user=self.student, course=self.course).exists(),
                        "Enrolling from the course page didn't create an enrollment")
        self.assert_no_errors(page, "dashboard after enrolling")

        self.visit(page, f"/learn/{self.course.slug}/")
        page.wait_for_selector("#lesson-content >> text=Body one of the course.", timeout=10000)
        page.click("#mark-complete")
        page.wait_for_selector(f".lesson-item[data-lesson-id='{self.lesson1.id}'] .text-green-400", timeout=10000)
        page.wait_for_load_state("networkidle")
        self.assertTrue(
            LessonProgress.objects.filter(lesson=self.lesson1, user=self.student, is_completed=True).exists(),
            "Marking the lesson complete didn't record progress",
        )
        self.assert_no_errors(page, "learn page")

    def test_instructor_deletes_a_lesson_from_the_content_page(self):
        from courses.models import Lesson

        page = self.new_page()
        self.login(page, self.instructor)
        self.visit(page, f"/instructor/courses/{self.draft.slug}/content/")
        page.on("dialog", lambda dialog: dialog.accept())
        delete_button = f"button[onclick='deleteLesson({self.draft_lesson.id})']"
        page.click(delete_button)
        page.wait_for_selector(delete_button, state="detached", timeout=10000)  # list re-rendered
        page.wait_for_load_state("networkidle")
        self.assertFalse(Lesson.objects.filter(pk=self.draft_lesson.pk).exists(),
                         "Deleting a lesson from the content page didn't delete it")
        self.assert_no_errors(page, "course content page")
