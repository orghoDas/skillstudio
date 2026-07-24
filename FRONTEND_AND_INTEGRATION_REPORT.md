# Frontend & Integration Condition Report — SkillStudio

**Reviewer:** Independent code review
**Date:** 2026-07-24
**Scope:** 42 Django templates + inline client JS, and how they integrate with the `/api/` backend.

**Stack:** Django templates rendered as empty shells + inline `fetch()` against DRF · Tailwind via CDN · JWT in `localStorage`. No separate JS/CSS files — `static/` contains only `.gitkeep`.

---

## Verdict

A hand-rolled SPA living inside Django templates, with no build step and no framework. Functional, but with real security and maintainability problems. The frontend and backend also quietly disagree on the auth model.

| Area | State |
|---|---|
| Frontend security | 🟢 Tokens httpOnly + DOM-XSS sinks escaped; CSP still recommended |
| Build / delivery | 🟠 CDN Tailwind, no build, no static assets, no SSR |
| Code consistency | 🟠 Shared helper now used more widely; a few raw GET fetches remain |
| Integration (auth/contract) | 🟠 Auth split-brain + page gating fixed; no API contract remains |

---

# Part A — Frontend

Every `core` view is just `render(request, 'x.html')` with **no context** (`core/views.py`). All data is fetched client-side via inline `fetch()`.

## 🔴 Critical

### 1. DOM-XSS across nearly every page
API data is injected into `innerHTML` via template literals with **no escaping**. Example — `courses/list.html:153`:

```js
container.innerHTML = courses.map(course => `...<h3>${course.title}</h3>...`);
```

Course titles, categories, bios, and instructor names are **user-authored**, so this is **stored XSS**. The pattern appeared in essentially all 20+ data templates.

- **RESOLVED 2026-07-24.** Two layers: (1) the token-theft payoff was removed by moving JWTs to httpOnly cookies (#2), and (2) every interpolation of API data into an `innerHTML` template literal is now routed through `escapeHtml()` (text/quoted-attribute) or `safeUrl()` (`href`/`src`) — **387 `escapeHtml` + 8 `safeUrl` wraps across 31 templates**, including recursion into HTML-producing ternaries so nested user data (e.g. `${course.category_name}` inside a `<span>`) is escaped too. Developer-composed HTML variables (`statusBadge`, `videoEmbed`) were deliberately left unescaped, with their *internal* user data (e.g. the video ID) escaped instead. `querySelector` selector strings were correctly left untouched. Verified: no unescaped user-data interpolation remains in any HTML text/attribute context; `manage.py check` clean; template-rendering tests pass.
  - **Residual (defense-in-depth, not blocking):** inline `onclick="fn('${id}')"` handlers pass escaped IDs, which is safe for the numeric/UUID IDs in use but is not a general JS-context defense — the clean long-term fix is `addEventListener` + `data-` attributes (also needed for a strict CSP). A CSP header is still worth adding.

### 2. JWTs stored in `localStorage` — RESOLVED 2026-07-24
JWTs are no longer in `localStorage`. The server issues access/refresh as **httpOnly cookies** (`CookieJWTAuthentication` + `CustomTokenObtainPairView`/`CookieTokenRefreshView`), so JS — and therefore XSS — cannot read them. `login.html` stores only non-sensitive `user` display info; `apiRequest`/logout rely on the cookie. Because auth is now cookie-borne, CSRF is enforced on cookie-authenticated mutations (see Part B).

## 🟠 High

- **Inconsistent API access → duplicated, weaker logic.** `base.html` has a solid global `apiRequest` helper (401 → cookie refresh → retry, CSRF header, error-body parsing). The `exams/*` templates' local `apiRequest` shadows were removed during the cookie migration so they now use the global one; a few templates still use raw `fetch()` for public GETs.
- **Tailwind loaded from `cdn.tailwindcss.com`** (`base.html:11`) — the CDN build explicitly warns it is not for production: no purge/tree-shaking, large payload, runtime compilation, hard network dependency. No build pipeline, minification, or cache-busting exists.
- **No SSR / SEO / crawlability.** Pages ship empty and hydrate client-side, so crawlers and no-JS clients see blank pages; there is a content flash on every load.
- **Leftover debug code** — `console.log('API Response', ...)` shipped in `courses/list.html`.

## 🟢 What's good

- Consistent dark-theme design system and shared components (`components/navbar.html`, `alert`, `sidebar`).
- The `apiRequest` helper itself is well-written (refresh + retry + graceful error extraction) — it just isn't used everywhere.
- Defensive response handling (`data.results || data`) shows awareness of pagination shapes.

---

# Part B — Integration (backend ↔ frontend)

Where the two halves quietly disagree:

- **Split-brain auth model — RESOLVED 2026-07-24.** Auth is now cookie-based end to end. Protected page routes are gated **server-side** via `@cookie_login_required` (`core/auth.py`) — anonymous users are redirected to `/auth/login/?next=…` before the page renders (no content flash, no structure leak), and the ~25 client-side `if (!token) redirect` gates were removed. UI still reads the non-sensitive `user` object for display state only.
- **CSRF/JWT model — now deliberate.** With auth on an httpOnly cookie, CSRF is a real concern and is now **enforced**: `CookieJWTAuthentication` runs Django's CSRF check on cookie-authenticated unsafe methods, `base.html` guarantees the `csrftoken` cookie, and the helper sends `X-CSRFToken` on mutations. Header-based API clients remain CSRF-exempt (a bearer header is not auto-attached cross-site). Covered by CSRF negative/positive tests.
- **No API contract.** The frontend hardcodes route strings and guesses response shapes (`data.results || data` everywhere) — a symptom of contract instability. No OpenAPI/schema gate, so backend changes silently break pages.
- **End-to-end price integrity is broken.** `payments/checkout.html` computes `final_amount` client-side and posts `amount`, which the backend then trusts (`payments/views.py:80`). The client-controlled-amount flaw is **full-stack**, not just backend.
- **Dead removed-feature wiring.** The AI recommender was removed from the backend, but `core/urls.py` still routes `recommendations/` → `ai_recommendations` and `base.html:78` keeps an "AI recommender widget removed" placeholder. Stale surface on both sides.

---

## Recommended fix order

1. ~~Move the JWT out of `localStorage` into an httpOnly cookie~~ — **done 2026-07-24** (kills token exfiltration).
2. ~~Add server-side auth guards on protected page routes~~ — **done 2026-07-24** (`@cookie_login_required`).
3. ~~Kill the XSS sinks: route all interpolated API data through `escapeHtml()`/`safeUrl()`~~ — **done 2026-07-24** (387 `escapeHtml` + 8 `safeUrl` across 31 templates).
4. Add a Content-Security-Policy header and migrate inline `onclick="fn('${id}')"` handlers to `addEventListener` + `data-` attributes (remaining defense-in-depth for the XSS class).
5. Replace CDN Tailwind with a real build (purge + minify + cache-bust) and move JS into versioned static files.
6. Publish an OpenAPI schema and align template route/response assumptions to it.
