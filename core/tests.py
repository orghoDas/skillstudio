import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates"
DECLARATION = re.compile(r"^\s*(?:const|let|class)\s+([A-Za-z_$][\w$]*)", re.MULTILINE)


def top_level_globals_of_base():
    """Names base.html declares with const/let/class in its global <script>."""
    base = (TEMPLATES_DIR / "base.html").read_text()
    names = set()
    for script in re.findall(r"<script>(.*?)</script>", base, re.S):
        # Only indentation level 8 = top level inside base.html's <script>.
        names.update(re.findall(r"^ {8}(?:const|let|class)\s+([A-Za-z_$][\w$]*)", script, re.M))
    return names


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
            for script in re.findall(r"<script>(.*?)</script>", text, re.S):
                for line in script.splitlines():
                    match = re.match(r"^(?:const|let|class)\s+([A-Za-z_$][\w$]*)", line)  # column 0 = top level
                    if match and match.group(1) in base_globals:
                        offenders.append(f"{template.relative_to(TEMPLATES_DIR)}: {line.strip()}")
        self.assertEqual(offenders, [], "Templates must not re-declare base.html globals")


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
        for template in TEMPLATES_DIR.rglob("*.html"):
            text = template.read_text()
            for pattern in _CALL_PATTERNS:
                for match in pattern.finditer(text):
                    raw = match.group("u")
                    path = _concrete_path(raw)
                    if not path:
                        continue  # fully dynamic (e.g. apiRequest(endpoint)) — can't check statically
                    line = text[: match.start()].count("\n") + 1
                    where = f"{template.relative_to(TEMPLATES_DIR)}:{line}"
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
