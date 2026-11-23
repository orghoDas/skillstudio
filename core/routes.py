"""Build the API endpoint reference (docs/API_ROUTES.md) from the URLconf.

The reference is generated, so it can't drift from the code the way the old
hand-written app READMEs did (AUDIT_REPORT.md DOC-02). A test fails when the
committed file is stale; regenerate with:

    python manage.py api_routes --write
"""

from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver

DOC_PATH = Path(settings.BASE_DIR) / "docs" / "API_ROUTES.md"
HTTP_METHODS = ("get", "post", "put", "patch", "delete")

HEADER = """# API routes

> Generated from the URLconf by `python manage.py api_routes --write`; do not
> edit by hand. `core.tests` fails when this file is out of date.

Paths use Django converter syntax (`<int:pk>`, `<slug:slug>`). **Auth** lists
the view's DRF permission classes (`AllowAny` = public). Authenticated calls
from the browser use the httpOnly JWT cookie plus the `X-CSRFToken` header;
other clients send `Authorization: Bearer <access token>`.
"""


def _pattern_text(pattern):
    return str(pattern.pattern).lstrip("^").rstrip("$")


def _walk(patterns, prefix=""):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + _pattern_text(entry))
        elif isinstance(entry, URLPattern):
            yield prefix + _pattern_text(entry), entry


def _describe(callback):
    view_class = getattr(callback, "view_class", None) or getattr(callback, "cls", None)
    if view_class is None:  # plain Django function view
        return "GET", "", f"{callback.__module__}.{callback.__name__}"
    initkwargs = getattr(callback, "view_initkwargs", None) or getattr(callback, "initkwargs", {}) or {}
    actions = getattr(callback, "actions", None)  # ViewSet routes
    if actions:
        methods = sorted(m.upper() for m in actions)
    else:
        allowed = getattr(view_class, "http_method_names", HTTP_METHODS)
        methods = [m.upper() for m in HTTP_METHODS if m in allowed and hasattr(view_class, m)]
    permissions_by_method = {}
    for method in methods:
        view = view_class(**initkwargs)
        view.request = SimpleNamespace(method=method)
        if actions:
            view.action = actions[method.lower()]
        permissions = ", ".join(type(permission).__name__ for permission in view.get_permissions()) or "AllowAny"
        permissions_by_method.setdefault(permissions, []).append(method)
    auth = " / ".join(
        f'{" ".join(group)}: {permission}' if len(permissions_by_method) > 1 else permission
        for permission, group in permissions_by_method.items()
    )
    name = f"{view_class.__module__}.{view_class.__name__}"
    if name.endswith(".WrappedAPIView"):  # @api_view function
        name = f"{callback.__module__}.{callback.__name__}"
    return " ".join(methods), auth, name


def render_routes():
    sections = {}
    for path, pattern in _walk(get_resolver().url_patterns):
        if not path.startswith("api/"):
            continue
        group = path.split("/")[1]
        methods, auth, view = _describe(pattern.callback)
        sections.setdefault(group, []).append((f"/{path}", methods, auth, view))

    lines = [HEADER]
    for group in sorted(sections):
        lines.append(f"\n## `/api/{group}/`\n")
        lines.append("| Path | Methods | Auth | View |")
        lines.append("|---|---|---|---|")
        for path, methods, auth, view in sections[group]:
            lines.append(f"| `{path}` | {methods} | {auth} | `{view}` |")
    return "\n".join(lines) + "\n"
