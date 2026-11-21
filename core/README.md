# core

The server-rendered pages and the project-wide tests.

- **Pages** (`views.py`, `urls.py`): Django templates in `templates/` that call the JSON API with `fetch`.
  - Pages for signed-in users are behind `cookie_login_required` (`auth.py`), which checks the JWT access cookie.
  - The pages never trust that check for data: every API call is authorised again by DRF.
- **`templates/base.html`** defines the shared JS helpers every page relies on (`apiRequest`, `escapeHtml`, `showAlert`, ...). `TemplateGlobalsTests` fails when a page calls a helper that doesn't exist.
- **`TemplateApiContractTests`** fails when a template calls an `/api/...` path or HTTP method that no view serves.
- **`test_browser_smoke.py`** drives the real pages in headless Chromium (Playwright). It fails on JS errors, failing API calls, raw markup shown as text, and broken enroll/learn/delete flows. It is tagged `browser`.
- **`ProjectHygieneTests`** fails when a model changed without a migration, or when `docs/API_ROUTES.md` is stale.
- **`python manage.py api_routes [--write]`** prints or regenerates [docs/API_ROUTES.md](../docs/API_ROUTES.md) (see `routes.py`).
