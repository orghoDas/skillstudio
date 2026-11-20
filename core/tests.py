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
