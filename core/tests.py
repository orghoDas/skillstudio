import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates"
SHARED_JS_DIR = Path(settings.BASE_DIR) / "static" / "js"
DECLARATION = re.compile(r"^(?:const|let|class)\s+([A-Za-z_$][\w$]*)", re.MULTILINE)


def top_level_globals_of_base():
    """Names declared by the shared scripts loaded in base.html."""
    return {name for script in SHARED_JS_DIR.glob("*.js") for name in DECLARATION.findall(script.read_text())}


class TemplateGlobalsTests(SimpleTestCase):
    """FE-01: a page script that re-declares a base.html global with const/let
    throws a SyntaxError, which (because page scripts render before base.html's
    script) kills apiRequest/escapeHtml/CSRF/logout on that page."""

    def test_base_globals_detected(self):
        self.assertIn("API_BASE", top_level_globals_of_base())

    def test_no_template_redeclares_a_base_global(self):
        base_globals = top_level_globals_of_base()
        offenders = []
        for template in TEMPLATES_DIR.rglob("*.html"):
            if template.name == "base.html":
                continue
            text = template.read_text()
            if "{% extends 'base.html' %}" not in text and '{% extends "base.html" %}' not in text:
                continue
            for script in re.findall(r"<script\b[^>]*>(.*?)</script>", text, re.S):
                offenders.extend(
                    f"{template.relative_to(TEMPLATES_DIR)}: {name}"
                    for name in base_globals.intersection(DECLARATION.findall(script))
                )
        self.assertEqual(offenders, [], "Templates must not re-declare shared JavaScript globals")


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'login-throttle-test',
}})
class AuthThrottleTests(SimpleTestCase):
    def test_login_limits_repeated_requests_and_sets_retry_after(self):
        from django.core.cache import cache

        cache.clear()
        self.addCleanup(cache.clear)
        client = APIClient()
        for _ in range(5):
            response = client.post('/api/accounts/token/', {'token_in_body': True}, format='json')
            self.assertEqual(response.status_code, 400)

        response = client.post('/api/accounts/token/', {'token_in_body': True}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertEqual(response.json()['code'], 'throttled')

    def test_staff_login_limits_repeated_requests(self):
        from django.core.cache import cache
        from django.urls import reverse

        cache.clear()
        self.addCleanup(cache.clear)
        client = APIClient()
        url = reverse('admin:login')
        for _ in range(5):
            self.assertEqual(client.post(url, {}).status_code, 200)
        response = client.post(url, {})
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)


# ----------------------------------------------------------------------------
# API-01 / TEST-02: every API call a template makes must hit a real route.
# ----------------------------------------------------------------------------

_CALL_PATTERNS = [
    re.compile(r"apiRequest\(\s*(['\"`])(?P<u>.*?)\1", re.S),
    re.compile(r"fetch\(\s*`\$\{API_BASE\}(?P<u>[^`]*)`", re.S),
    re.compile(r"fetch\(\s*(['\"`])/api(?P<u>.*?)\1", re.S),
    re.compile(r"const url = `\$\{API_BASE\}(?P<u>[^`]*)`", re.S),
]
_PLACEHOLDER_UUID = "123e4567-e89b-12d3-a456-426614174000"


def _concrete_path(raw):
    """Turn a template-literal URL into a concrete path to resolve."""
    def sub(match):
        expr = match.group(1).lower()
        if "slug" in expr:
            return "some-slug"
        if "certid" in expr or "uuid" in expr:
            return _PLACEHOLDER_UUID
        if "params" in expr or "tostring" in expr:
            return ""
        return "1"
    path = re.sub(r"\$\{([^}]*)\}", sub, raw).split("?")[0]
    return path if path.startswith("/") else None


_METHOD = re.compile(r"method:\s*['\"](\w+)['\"]")


def _call_method(text, end):
    """HTTP method from the call's options object (default GET)."""
    options = text[end:end + 250].split(");")[0]
    match = _METHOD.search(options)
    return match.group(1).upper() if match else "GET"


def _view_handles(func, method):
    view = getattr(func, "view_class", None) or getattr(func, "cls", None)
    if view is None:
        return True  # plain function view: can't introspect statically
    return hasattr(view, method.lower())


class TemplateApiContractTests(SimpleTestCase):
    def _template_calls(self):
        sources = [*TEMPLATES_DIR.rglob("*.html"), *SHARED_JS_DIR.glob("*.js")]
        for source in sources:
            text = source.read_text()
            for pattern in _CALL_PATTERNS:
                for match in pattern.finditer(text):
                    raw = match.group("u")
                    path = _concrete_path(raw)
                    if not path:
                        continue  # fully dynamic (e.g. apiRequest(endpoint)) — can't check statically
                    line = text[: match.start()].count("\n") + 1
                    where = f"{source.relative_to(settings.BASE_DIR)}:{line}"
                    yield where, raw, path, _call_method(text, match.end())

    def test_every_template_api_call_resolves(self):
        from django.urls import Resolver404, resolve

        unresolved = []
        for where, raw, path, _method in self._template_calls():
            try:
                resolve("/api" + path)
            except Resolver404:
                unresolved.append(f"{where} {raw}")
        self.assertEqual(unresolved, [], "Templates call API endpoints that don't exist")

    def test_every_template_api_call_uses_a_supported_method(self):
        """API-03: e.g. DELETE sent to an update-only view returns 405."""
        from django.urls import Resolver404, resolve

        unsupported = []
        for where, raw, path, method in self._template_calls():
            try:
                func = resolve("/api" + path).func
            except Resolver404:
                continue  # reported by the test above
            if not _view_handles(func, method):
                unsupported.append(f"{where} {method} {raw}")
        self.assertEqual(unsupported, [], "Templates use HTTP methods the views don't support")


class ProjectHygieneTests(SimpleTestCase):
    """DOC-02 / REPO-03: generated docs and migrations must match the code."""

    databases = {"default"}  # makemigrations reads the applied-migrations table

    def test_api_route_reference_is_up_to_date(self):
        from core.routes import DOC_PATH, render_routes

        self.assertTrue(DOC_PATH.exists(), "Run: python manage.py api_routes --write")
        self.assertEqual(
            DOC_PATH.read_text(), render_routes(),
            "docs/API_ROUTES.md is stale. Run: python manage.py api_routes --write",
        )

    def test_no_model_changes_without_a_migration(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        try:
            call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
        except SystemExit:
            self.fail(f"Model changes without a migration. Run makemigrations.\n{out.getvalue()}")
