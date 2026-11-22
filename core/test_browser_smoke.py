"""
Browser smoke tests (TEST-02): drive the real pages in headless Chromium and
fail on JavaScript errors, failing API calls, or broken core flows — the class
of bugs (FE-01, LRN-01, API-01, API-03) that server-side tests can't see.

Offline and hermetic: every request to another host (Google Fonts and
YouTube/Vimeo player scripts) is answered with a local stub.

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
    from playwright.sync_api import expect, sync_playwright
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
                                           status="draft", price=Decimal("15.00"))
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
            content_type = "text/css" if "fonts" in (parsed.hostname or "") else "application/javascript"
            return route_obj.fulfill(status=200, content_type=content_type, body="")

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

    def login(self, page, user, *, next_path=None):
        path = f"/auth/login/?next={next_path}" if next_path else "/auth/login/"
        if next_path:
            page.allowed_api_errors = getattr(page, "allowed_api_errors", set()) | {("/api/accounts/token/refresh/", 401)}
        self.visit(page, path)
        page.fill("#email", user.email)
        page.fill("#password", self.password)
        page.click("#login-btn")
        page.wait_for_url(lambda url: "/auth/login" not in url, timeout=15000)
        page.wait_for_load_state("networkidle")

    def staff_login(self, page, operator):
        page.locator("#id_username").fill(operator.email)
        page.locator("#id_password").fill(self.password)
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_role("heading", name="Operations overview")).to_be_visible()

    VISIBLE_MARKUP = ("<div", "<span", "<path", "<svg", "<button", "<a href", "&lt;", "&gt;")

    def assert_no_errors(self, page, where):
        self.assertEqual(page.errors, [], f"Errors on {where}")
        # Generated HTML that was escaped again shows up as literal markup text.
        text = page.inner_text("body")
        leaked = [m for m in self.VISIBLE_MARKUP if m in text]
        self.assertEqual(leaked, [], f"Raw markup visible as text on {where}")

    # ----------------------------------------------------------------- tests

    def test_staff_console_can_read_dashboard_and_publish_from_review_queue(self):
        from django.contrib.auth.models import Permission
        from django.urls import reverse

        from accounts.models import User

        operator = User.objects.create_user(
            email="reviewer@example.com", password=self.password, role="admin", admin_console_only=True,
        )
        operator.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="courses", codename__in=("view_course", "change_course"),
        ))
        self.draft.status = "under_review"
        self.draft.save(update_fields=["status"])

        page = self.new_page()
        page.set_viewport_size({"width": 390, "height": 844})
        self.visit(page, "/auth/login/")
        page.get_by_role("link", name="Staff sign in").click()
        self.staff_login(page, operator)
        expect(page.get_by_role("heading", name="Course review")).to_be_visible()
        expect(page.get_by_text("Net course sales")).to_have_count(0)
        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))

        page.get_by_role("link", name=self.draft.title, exact=True).click()
        expect(page.get_by_role("heading", name="Review course")).to_be_visible()
        page.get_by_label("Decision").select_option("published")
        page.get_by_role("button", name="Apply decision").click()
        page.wait_for_url(f"**{reverse('admin:courses_course_change', args=[self.draft.pk])}")
        expect(page.get_by_text("Course status changed to published.", exact=True)).to_be_visible()
        self.draft.refresh_from_db()
        self.assertEqual((self.draft.status, self.draft.reviewed_by_id), ("published", operator.pk))

        self.visit(page, "/admin/")
        expect(page.get_by_text("Course status changed to published.", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name=self.draft.title, exact=True)).to_have_count(0)
        self.assert_no_errors(page, "admin console")

    def test_finance_operator_handles_refund_and_manual_payout_from_dashboard(self):
        from django.contrib.auth.models import Permission

        from accounts.models import User
        from payments import services
        from students.models import Wallet

        operator = User.objects.create_user(
            email="finance@example.com", password=self.password, role="admin", admin_console_only=True,
        )
        operator.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="payments",
            codename__in=("view_refund", "change_refund", "view_payout", "change_payout", "view_payment"),
        ))
        self.course.price = Decimal("30.00")
        self.course.is_free = False
        self.course.save(update_fields=["price", "is_free"])
        wallet, _ = Wallet.objects.get_or_create(user=self.student)
        wallet.add_money("30.00")
        payment = services.purchase_course(self.student, self.course.pk).payment
        refund = services.request_refund(self.student, payment.pk, "Browser refund", Decimal("5.00"))
        payout = services.create_payout(self.instructor, Decimal("10.00"), payout_method="bank_transfer")

        page = self.new_page()
        self.visit(page, "/admin/")
        self.staff_login(page, operator)
        page.get_by_role("link", name=f"Refund #{refund.pk}", exact=False).click()
        expect(page.get_by_text("Browser refund", exact=True)).to_be_visible()
        page.get_by_label("Decision").select_option("approve")
        page.get_by_role("button", name="Apply decision").click()
        expect(page.get_by_text("Wallet refund approved.", exact=True)).to_be_visible()
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("5.00"))

        self.visit(page, "/admin/")
        expect(page.get_by_text("USD 25.00", exact=True)).to_be_visible()
        page.get_by_role("link", name=f"Payout #{payout.pk}", exact=False).click()
        page.get_by_label("Decision").select_option("approve")
        page.get_by_role("button", name="Apply decision").click()
        expect(page.get_by_text("Payout approved.", exact=True)).to_be_visible()
        page.get_by_role("link", name="Review workflow").click()
        page.get_by_label("Decision").select_option("complete")
        page.get_by_label("Transfer reference").fill("browser-transfer-fixture")
        page.get_by_role("button", name="Apply decision").click()
        expect(page.get_by_text("Payout recorded as sent.", exact=True)).to_be_visible()
        payout.refresh_from_db()
        self.assertEqual((payout.status, payout.transaction_id), ("paid", "browser-transfer-fixture"))
        self.assert_no_errors(page, "finance workflow")

    def test_public_pages_render_without_errors(self):
        page = self.new_page()
        for path in ["/", "/courses/", f"/courses/{self.course.slug}/", "/search/", "/browse/",
                     "/auth/login/", "/auth/register/"]:
            with self.subTest(path=path):
                page.errors.clear()
                self.visit(page, path)
                self.assert_no_errors(page, path)

    def test_role_navigation_recovers_after_access_expiry_and_logout(self):
        from django.conf import settings

        page = self.new_page()
        self.login(page, self.student)
        page.evaluate("localStorage.clear()")
        response = page.goto(self.live_server_url + '/instructor/courses/')
        self.assertEqual(response.status, 403)

        page.context.clear_cookies(name=settings.JWT_AUTH_COOKIE)
        cookies = {cookie['name']: cookie for cookie in page.context.cookies()}
        self.assertEqual(cookies[settings.JWT_AUTH_REFRESH_COOKIE]['path'], '/api/accounts/')
        with page.expect_response('**/api/accounts/token/refresh/') as refreshed:
            page.goto(self.live_server_url + '/my-courses/')
        self.assertEqual(refreshed.value.status, 200)
        page.wait_for_url('**/my-courses/')
        page.locator('#user-menu-btn').click()
        page.get_by_role('link', name='My Learning').wait_for()
        page.get_by_role('button', name='Sign Out').click()
        page.wait_for_url('**/auth/login/')
        self.assertFalse({settings.JWT_AUTH_COOKIE, settings.JWT_AUTH_REFRESH_COOKIE}
                         & {cookie['name'] for cookie in page.context.cookies()})
        self.assert_no_errors(page, 'student session recovery and logout')

    def test_catalog_preview_limits_and_course_creation_use_real_data(self):
        from courses.models import Course

        for number in range(4):
            Course.objects.create(
                title=f"Extra course {number}", status="published", instructor=self.instructor,
            )

        public_page = self.new_page()
        self.visit(public_page, "/")
        self.assertEqual(public_page.locator("#popular-courses > a").count(), 3)
        self.visit(public_page, f"/courses/{self.course.slug}/")
        public_page.locator("#course-curriculum summary").click()
        self.assertTrue(public_page.get_by_text(self.lesson1.title, exact=True).is_visible())
        self.assert_no_errors(public_page, "public course curriculum")

        page = self.new_page()
        self.login(page, self.instructor)
        self.assertEqual(page.locator("#my-courses h3").count(), 3)
        self.visit(page, "/instructor/courses/create/")
        page.fill("#title", "Actual course details")
        page.fill("#description", "A short description")
        page.select_option("#category", str(self.course.category_id))
        page.select_option("#level", "beginner")
        page.locator("#is_free").check()
        with page.expect_response("**/api/courses/create/") as created:
            page.get_by_role("button", name="Create draft").click()
        self.assertEqual(created.value.status, 201)
        course = Course.objects.get(title="Actual course details")
        self.assertEqual(course.category_id, self.course.category_id)
        page.wait_for_url(f"**/instructor/courses/{course.slug}/content/")
        self.assert_no_errors(page, "course creation")

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

    def test_student_dashboard_and_profile_show_completed_courses_separately_from_certificates(self):
        from django.utils import timezone

        from enrollments.models import Enrollment, LessonProgress

        enrollment = Enrollment.objects.create(
            user=self.student, course=self.course, status="completed",
            is_completed=True, completed_at=timezone.now(),
        )
        LessonProgress.objects.create(
            enrollment=enrollment, lesson=self.lesson1, user=self.student,
            is_completed=True, completed_at=timezone.now(),
        )
        page = self.new_page()
        self.login(page, self.student)
        self.visit(page, "/dashboard/")
        self.assertEqual(page.locator("#enrolled-count").inner_text(), "1")
        self.assertEqual(page.locator("#completed-count").inner_text(), "1")
        self.assertEqual(page.locator("#certificates-count").inner_text(), "0")
        self.assertIn("No courses in progress", page.locator("#continue-learning").inner_text())
        self.assert_no_errors(page, "student dashboard totals")

        self.visit(page, "/profile/")
        self.assertEqual(page.locator("#stats-enrolled").inner_text(), "1")
        self.assertEqual(page.locator("#stats-certificates").inner_text(), "0")
        self.assert_no_errors(page, "student profile totals")

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

    def test_certificate_list_download_and_public_verification(self):
        from certificates.models import Certificate
        from enrollments.models import Enrollment

        enrollment = Enrollment.objects.create(
            user=self.student, course=self.course, status='completed', is_completed=True,
        )
        certificate = Certificate.objects.create(user=self.student, course=self.course, enrollment=enrollment)
        page = self.new_page()
        self.login(page, self.student)
        self.visit(page, '/certificates/')
        share = page.locator('button[data-verification-url]')
        self.assertEqual(share.get_attribute('data-verification-url'), certificate.verification_url)
        with page.expect_download() as download:
            page.get_by_role('button', name='Download').click()
        self.assertTrue(download.value.suggested_filename.endswith('.pdf'))
        self.assert_no_errors(page, 'certificate list and download')

        visitor = self.new_page()
        self.visit(visitor, urlparse(certificate.verification_url).path)
        visitor.get_by_text('Verified certificate').wait_for()
        self.assert_no_errors(visitor, 'public certificate verification')

    def test_instructor_can_open_wallet_from_sidebar(self):
        from students.models import Wallet

        wallet, _ = Wallet.objects.get_or_create(user=self.instructor)
        wallet.add_money(Decimal("45.00"), description="Course earnings")
        page = self.new_page()
        self.login(page, self.instructor)
        self.visit(page, "/instructor/dashboard/")
        page.locator("#sidebar").get_by_role("link", name="My Wallet").click()
        page.wait_for_url("**/wallet/")
        page.wait_for_selector("#wallet-balance >> text=$45.00")
        page.wait_for_selector("#transactions-container >> text=Course earnings")
        self.assert_no_errors(page, "instructor wallet")

    def test_payment_history_and_instructor_roster_paginate_without_changing_totals(self):
        from accounts.models import User
        from enrollments.models import Enrollment
        from payments.models import Payment

        learners = User.objects.bulk_create([User(email=f'roster-{index}@example.test') for index in range(21)])
        Enrollment.objects.bulk_create([Enrollment(course=self.course, user=user) for user in learners])
        Payment.objects.bulk_create([
            Payment(
                user=self.student, course=self.course, purpose=Payment.PURPOSE_COURSE_PURCHASE,
                amount=Decimal('2.00'), original_amount=Decimal('2.00'), status='completed',
            )
            for _ in range(21)
        ])

        for user, path, prefix, table, summary, expected in (
            (self.student, '/payments/history/', 'payments', '#transactions-tbody', '#total-spent', '$42.00'),
            (self.instructor, '/instructor/students/', 'students', '#students-table', '#total-students', '21'),
        ):
            with self.subTest(path=path):
                page = self.new_page()
                self.login(page, user)
                self.visit(page, path)
                self.assertEqual(page.locator(f'{table} tr').count(), 20)
                self.assertEqual(page.locator(summary).inner_text(), expected)
                page.locator(f'#{prefix}-next').click()
                page.wait_for_selector(f'#{prefix}-page >> text=Page 2')
                self.assertEqual(page.locator(f'{table} tr').count(), 1)
                self.assertEqual(page.locator(summary).inner_text(), expected)
                page.locator(f'#{prefix}-previous').click()
                page.wait_for_selector(f'#{prefix}-page >> text=Page 1')
                self.assertEqual(page.locator(f'{table} tr').count(), 20)
                self.assert_no_errors(page, path)

    def test_platform_admin_can_save_another_instructors_course_in_the_editor(self):
        from accounts.models import User

        moderator = User.objects.create_user(email="moderator@admin.com", password=self.password, role="admin")
        page = self.new_page()
        edit_path = f"/instructor/courses/{self.draft.slug}/edit/"
        self.login(page, moderator, next_path=edit_path)
        expect(page.locator('#category')).to_have_value(str(self.draft.category_id))
        page.fill("#title", "Moderated draft title")
        with page.expect_response(f"**/api/courses/{self.draft.pk}/update/") as edited:
            page.get_by_role("button", name="Save changes").click()
        self.assertEqual(edited.value.status, 200)
        page.wait_for_url(f"**/instructor/courses/{self.draft.slug}/content/")
        page.wait_for_load_state("networkidle")
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.title, "Moderated draft title")
        self.assertEqual(self.draft.instructor_id, self.instructor.pk)
        self.assertEqual(self.draft.category_id, self.course.category_id)
        self.assertFalse(self.draft.is_free)
        self.assertEqual(self.draft.price, Decimal("15.00"))
        self.assert_no_errors(page, "platform admin course moderation")

    def test_paid_course_requires_a_price_and_can_be_changed_to_free(self):
        page = self.new_page()
        self.login(page, self.instructor)
        self.visit(page, f"/instructor/courses/{self.draft.slug}/edit/")
        price = page.locator("#price")
        price.fill("0")
        self.assertTrue(price.evaluate("input => input.validity.rangeUnderflow"))
        page.get_by_role("button", name="Save changes").click()
        self.assertTrue(page.url.endswith("/edit/"))

        page.locator("#is_free").check()
        self.assertTrue(price.is_disabled())
        with page.expect_response(f"**/api/courses/{self.draft.pk}/update/") as edited:
            page.get_by_role("button", name="Save changes").click()
        self.assertEqual(edited.value.status, 200)
        page.wait_for_url(f"**/instructor/courses/{self.draft.slug}/content/")
        self.draft.refresh_from_db()
        self.assertTrue(self.draft.is_free)
        self.assertEqual(self.draft.price, Decimal("0.00"))
        self.assert_no_errors(page, "course price validation")

    def test_course_revision_can_be_reviewed_while_the_original_remains_available_to_its_student(self):
        from accounts.models import User
        from courses.models import Course
        from enrollments.models import Enrollment

        Enrollment.objects.create(course=self.course, user=self.student)
        moderator = User.objects.create_user(email="reviewer@admin.com", password=self.password, role="admin")
        author_page = self.new_page()
        self.login(author_page, self.instructor)
        self.visit(author_page, f"/instructor/courses/{self.course.slug}/content/")
        author_page.get_by_role("button", name="Open draft revision").click()
        expect(author_page.locator('#course-content-status')).to_have_text('draft')
        revision = Course.objects.get(revision_of=self.course)
        self.assertEqual(Course.objects.get(pk=self.course.pk).status, "published")
        author_page.get_by_role("button", name="Submit for review").click()
        expect(author_page.locator('#course-content-status')).to_have_text('under review')
        self.assert_no_errors(author_page, "revision submission")

        reviewer_page = self.new_page()
        revision_path = f"/instructor/courses/{revision.slug}/content/"
        self.login(reviewer_page, moderator, next_path=revision_path)
        reviewer_page.get_by_role("button", name="Publish course").click()
        expect(reviewer_page.locator('#course-content-status')).to_have_text('published')
        self.assertEqual(Course.objects.get(pk=self.course.pk).status, "archived")
        self.assert_no_errors(reviewer_page, "revision approval")

        student_page = self.new_page()
        self.login(student_page, self.student)
        self.visit(student_page, f"/learn/{self.course.slug}/")
        student_page.wait_for_selector("#lesson-content >> text=Body one of the course.")
        self.assert_no_errors(student_page, "archived course learning")

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
        self.assertTrue(page.locator("#next-lesson").is_disabled())
        page.click("#mark-complete")
        page.wait_for_selector(f".lesson-item[data-lesson-id='{self.lesson1.id}'] .text-green-400", timeout=10000)
        page.wait_for_load_state("networkidle")
        self.assertTrue(
            LessonProgress.objects.filter(lesson=self.lesson1, user=self.student, is_completed=True).exists(),
            "Marking the lesson complete didn't record progress",
        )
        page.click("#next-lesson")
        page.wait_for_selector("#lesson-content >> text=Body two.", timeout=10000)
        self.assert_no_errors(page, "learn page")

    def test_quiz_editor_preserves_zero_marks_and_explanation(self):
        from assessments.models import Quiz

        page = self.new_page()
        self.login(page, self.instructor)
        self.visit(page, f"/instructor/lessons/{self.draft_lesson.id}/edit/")
        manage = f"**/api/assessments/quiz/lesson/{self.draft_lesson.id}/manage/"
        page.allowed_api_errors = {(f"/api/assessments/quiz/lesson/{self.draft_lesson.id}/manage/", 404)}
        page.select_option("#lesson-type", "quiz")
        page.fill(".question-text", "How much is two plus two?")
        page.locator(".option-text").nth(0).fill("Four")
        page.locator(".option-text").nth(1).fill("Five")
        page.locator(".quiz-option input[type=radio]").first.check()
        page.fill(".question-marks", "7")
        page.fill(".question-explanation", "Two added to two makes four.")
        page.fill("#quiz-passing-score", "0")
        with page.expect_response(lambda r: r.url.endswith(manage[2:]) and r.request.method == "POST") as saved:
            page.get_by_role("button", name="Save Draft").click()
        self.assertEqual(saved.value.status, 200)
        quiz = Quiz.objects.get(lesson=self.draft_lesson)
        self.assertFalse(quiz.is_published)
        self.assertEqual((quiz.passing_percentage, quiz.total_marks), (0, 7))
        page.reload()
        expect(page.locator("#quiz-passing-score")).to_have_value("0")
        expect(page.locator(".question-explanation")).to_have_value("Two added to two makes four.")
        expect(page.locator(".question-marks")).to_have_value("7")
        with page.expect_response(lambda r: r.url.endswith(manage[2:]) and r.request.method == "POST") as published:
            page.get_by_role("button", name="Save & Publish").click()
        self.assertEqual(published.value.status, 200)
        quiz.refresh_from_db()
        self.assertTrue(quiz.is_published)

    def test_learning_library_and_formatted_article(self):
        from enrollments.models import Enrollment

        self.lesson1.content_text = "<p><strong>Formatted article.</strong></p>"
        self.lesson1.save(update_fields=["content_text"])
        Enrollment.objects.create(user=self.student, course=self.course)
        page = self.new_page()
        self.login(page, self.student)
        self.visit(page, f"/courses/{self.course.slug}/")
        page.get_by_role("button", name="Add to wishlist").click()
        page.get_by_role("button", name="View wishlist").click()
        expect(page.locator("#wishlist").get_by_role("link", name=self.course.title)).to_be_visible()
        self.visit(page, f"/learn/{self.course.slug}/")
        expect(page.locator("#article-content strong")).to_have_text("Formatted article.")
        page.get_by_text("Notes and bookmarks", exact=True).click()
        page.get_by_label("Private lesson note").fill("A private note")
        page.get_by_role("button", name="Save note").click()
        page.get_by_text("Lesson note saved.", exact=True).wait_for()
        page.get_by_role("button", name="Bookmark lesson").click()
        page.get_by_text("Lesson bookmarked.", exact=True).wait_for()
        self.visit(page, "/library/")
        expect(page.locator("#notes textarea")).to_have_value("A private note")
        expect(page.locator("#bookmarks").get_by_role("link", name=self.lesson1.title)).to_be_visible()
        page.locator("#notes textarea").fill("Updated note")
        page.get_by_role("button", name="Save changes").click()
        page.get_by_text("Note updated.", exact=True).wait_for()
        page.locator("#notes").get_by_role("button", name="Remove").click()
        page.get_by_role("button", name="Confirm", exact=True).click()
        expect(page.get_by_text("No notes yet.", exact=True)).to_be_visible()
        self.assert_no_errors(page, "saved learning")

    def test_partial_refund_keeps_net_amount_in_mobile_history_and_receipt(self):
        from accounts.models import User
        from payments.services import approve_refund, purchase_course, request_refund
        from students.models import Wallet

        moderator = User.objects.create_user(email="operator@admin.com", role="admin")
        self.course.is_free = False
        self.course.price = Decimal("12.00")
        self.course.save()
        wallet, _ = Wallet.objects.get_or_create(user=self.student)
        wallet.add_money(Decimal("25.00"), description="Test balance")
        payment = purchase_course(self.student, self.course.id).payment
        refund = request_refund(self.student, payment.id, "Test refund", Decimal("3.00"))
        approve_refund(refund.id, moderator)

        page = self.new_page()
        page.set_viewport_size({"width": 390, "height": 844})
        self.login(page, self.student)
        self.visit(page, "/payments/history/")
        expect(page.locator("#total-spent")).to_have_text("$9.00")
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        page.get_by_role("link", name="Receipt", exact=True).click()
        expect(page.get_by_role("heading", name="Wallet purchase receipt")).to_be_visible()
        expect(page.get_by_text("9.00 USD", exact=True)).to_be_visible()
        self.assert_no_errors(page, "receipt")

    def test_coupon_refund_and_manual_payout_in_the_browser(self):
        from cryptography.fernet import Fernet

        from accounts.models import User
        from payments.models import Coupon, Payment, Payout
        from students.models import Wallet

        moderator = User.objects.create_user(
            email="wallet-operator@admin.com", password=self.password, role="admin"
        )
        self.course.is_free = False
        self.course.price = Decimal("20.00")
        self.course.save()
        Coupon.objects.create(code="SAVE5", discount_type=Coupon.FIXED, discount_value=5, created_by=moderator)
        wallet, _ = Wallet.objects.get_or_create(user=self.student)
        wallet.add_money(Decimal("40.00"), description="Synthetic checkout funds")

        buyer = self.new_page()
        self.login(buyer, self.student)
        self.visit(buyer, f"/courses/{self.course.slug}/")
        buyer.get_by_label("Coupon code").fill("SAVE5")
        buyer.get_by_role("button", name="Check coupon").click()
        expect(buyer.locator("#coupon-quote")).to_have_text("Price with coupon: $15.00")
        buyer.locator("#enroll-btn").click()
        buyer.wait_for_url("**/dashboard/")
        self.assertEqual(Payment.objects.get(user=self.student).amount, Decimal("15.00"))
        self.visit(buyer, "/payments/history/")
        buyer.get_by_role("link", name="Request refund", exact=True).click()
        buyer.get_by_label("Amount in USD", exact=False).fill("3.00")
        buyer.get_by_label("Reason", exact=True).fill("Synthetic partial refund")
        buyer.get_by_role("button", name="Request wallet refund").click()
        buyer.get_by_text("Refund request submitted.", exact=True).wait_for()

        operator = self.new_page()
        self.login(operator, moderator)
        self.visit(operator, "/payments/refunds/")
        operator.get_by_role("button", name="Approve", exact=True).click()
        operator.get_by_role("button", name="Confirm", exact=True).click()
        expect(operator.get_by_text("processed", exact=False)).to_be_visible()
        self.assertEqual(Wallet.objects.get(user=self.student).balance, Decimal("28.00"))

        with self.settings(PAYOUT_DETAILS_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            instructor = self.new_page()
            self.login(instructor, self.instructor)
            self.visit(instructor, "/payments/payouts/")
            instructor.get_by_label("Amount in USD", exact=False).fill("10.00")
            instructor.get_by_label("Account holder").fill("Synthetic Payee")
            instructor.get_by_label("Bank name").fill("Test Bank")
            instructor.get_by_label("Bank account number or IBAN").fill("test-account-only")
            instructor.get_by_role("button", name="Request payout").click()
            instructor.get_by_role("button", name="Confirm", exact=True).click()
            instructor.get_by_text("Payout requested.", exact=True).wait_for()

            self.visit(operator, "/payments/payouts/")
            operator.get_by_role("button", name="Approve", exact=True).click()
            operator.get_by_role("button", name="Confirm", exact=True).click()
            operator.get_by_label("Bank transfer reference").fill("test-transfer-receipt")
            operator.get_by_role("button", name="Mark as sent").click()
            operator.get_by_role("button", name="Confirm", exact=True).click()
            operator.get_by_text("Transfer reference: test-transfer-receipt").wait_for()
            self.assertEqual(Payout.objects.get(instructor=self.instructor).status, "paid")
            self.assert_no_errors(instructor, "manual payout request")
        self.assert_no_errors(buyer, "coupon checkout and refund")
        self.assert_no_errors(operator, "refund and payout decisions")

    def test_navbar_search_reaches_the_second_page(self):
        from courses.models import Course

        for index in range(25):
            Course.objects.create(title=f"Paging result {index:02}", category=self.course.category,
                                  instructor=self.instructor, status="published")
        page = self.new_page()
        self.visit(page, "/courses/")
        field = page.get_by_role("searchbox", name="Search courses and instructors").first
        field.fill("Paging result")
        field.press("Enter")
        page.wait_for_url("**/search/?q=*")
        expect(page.locator("#results-count")).to_have_text("25")
        expect(page.locator("#results-container a")).to_have_count(20)
        page.locator("#page-controls").get_by_role("button", name="Next", exact=True).click()
        expect(page.locator("#page-controls [data-page-number]")).to_have_text("Page 2")
        expect(page.locator("#results-container a")).to_have_count(5)
        self.assert_no_errors(page, "search pagination")

    def test_api_key_can_be_created_and_revoked_from_settings(self):
        from accounts.models import APIKey

        page = self.new_page()
        self.login(page, self.student)
        self.visit(page, "/settings/")
        page.get_by_role("link", name="API keys").click()
        page.get_by_label("Key name").fill("Read-only key")
        page.get_by_role("button", name="Create API key").click()
        expect(page.locator("#new-key-panel")).to_be_visible()
        key = APIKey.objects.get(user=self.student)
        self.assertEqual(key.scopes, ["read"])
        page.get_by_role("button", name="Revoke", exact=True).click()
        page.get_by_role("button", name="Confirm", exact=True).click()
        page.get_by_role("button", name="Restore", exact=True).wait_for()
        key.refresh_from_db()
        self.assertFalse(key.is_active)
        self.assert_no_errors(page, "API key settings")

    def test_exam_publishes_and_resumes_with_saved_answers_and_server_time(self):
        from datetime import timedelta

        from django.utils import timezone

        from enrollments.models import Enrollment
        from exams.models import Exam, ExamAttempt, QuestionBank

        Enrollment.objects.create(user=self.student, course=self.course)
        question = QuestionBank.objects.create(
            course=self.course, question_text="Which answer is correct?", marks=3,
            options=[{"text": "First", "is_correct": True}, {"text": "Second", "is_correct": False}],
        )
        other_question = QuestionBank.objects.create(
            course=self.course, question_text="Which animal barks?", marks=1,
            options=[{"text": "Dog", "is_correct": True}, {"text": "Cat", "is_correct": False}],
        )
        instructor_page = self.new_page()
        self.login(instructor_page, self.instructor)
        self.visit(instructor_page, "/exams/create/")
        instructor_page.select_option("#course-select", str(self.course.pk))
        instructor_page.fill("#title", "Browser exam")
        instructor_page.fill("#duration", "2")
        instructor_page.fill("#start-datetime", "2020-01-01T00:00")
        instructor_page.check("#randomize-questions")
        instructor_page.check("#show-answers")
        instructor_page.get_by_role("button", name="Add Questions").click()
        instructor_page.locator(f'#question-bank-list input[value="{question.pk}"]').check()
        instructor_page.locator(f'#question-bank-list input[value="{other_question.pk}"]').check()
        instructor_page.get_by_role("button", name="Add Selected").click()
        self.assertEqual(instructor_page.input_value("#total-marks"), "4.00")
        self.assertEqual(instructor_page.input_value("#passing-marks"), "2.00")
        instructor_page.get_by_role("button", name="Publish Exam").click()
        instructor_page.wait_for_url("**/exams/")
        exam = Exam.objects.get(title="Browser exam")
        self.assertEqual((exam.status, exam.total_marks), ("published", Decimal("4.00")))
        self.assert_no_errors(instructor_page, "exam publication")

        page = self.new_page()
        self.login(page, self.student)
        self.visit(page, "/exams/")
        page.get_by_role("button", name="Start Exam").click()
        page.get_by_role("button", name="Confirm", exact=True).click()
        page.wait_for_url(f"**/exams/take/{exam.pk}/?attempt=*")
        with page.expect_response(f"**/api/exams/{exam.pk}/save-answers/") as saved:
            page.get_by_role("radio", name="First").check()
        self.assertEqual(saved.value.status, 200)
        attempt = ExamAttempt.objects.get(exam=exam, user=self.student)
        self.assertEqual(attempt.answers, {str(question.pk): 0})
        expected_order = [item["question_text"] for item in attempt.snapshot["questions"]]
        headings = page.locator("#questions-container h3")
        self.assertEqual(headings.all_text_contents(), expected_order)
        ExamAttempt.objects.filter(pk=attempt.pk).update(started_at=timezone.now() - timedelta(seconds=30))
        page.reload()
        self.assertTrue(page.get_by_role("radio", name="First").is_checked())
        self.assertEqual(headings.all_text_contents(), expected_order)
        self.assertNotEqual(page.locator("#timer").inner_text(), "02:00")
        page.get_by_role("radio", name="Dog").check()
        page.get_by_role("button", name="Submit Exam").first.click()
        page.get_by_role("button", name="Confirm", exact=True).click()
        page.wait_for_url(f"**/exams/results/{exam.pk}/?attempt=*")
        expect(page.locator('#score-display')).to_have_text('4/4')
        page.get_by_text("Correct answer: Dog").wait_for()
        self.assertEqual(page.locator("#correct-answers").inner_text(), "2")
        attempt.refresh_from_db()
        self.assertTrue(attempt.passed)
        self.assert_no_errors(page, "exam take and results")

    def test_instructor_deletes_a_lesson_from_the_content_page(self):
        from courses.models import Lesson

        page = self.new_page()
        self.login(page, self.instructor)
        self.visit(page, f"/instructor/courses/{self.draft.slug}/content/")
        delete_button = f"button[data-click='deleteLesson'][data-value-one='{self.draft_lesson.id}']"
        page.click(delete_button)
        page.get_by_role("button", name="Confirm", exact=True).click()
        page.wait_for_selector(delete_button, state="detached", timeout=10000)  # list re-rendered
        page.wait_for_load_state("networkidle")
        self.assertFalse(Lesson.objects.filter(pk=self.draft_lesson.pk).exists(),
                         "Deleting a lesson from the content page didn't delete it")
        self.assert_no_errors(page, "course content page")
