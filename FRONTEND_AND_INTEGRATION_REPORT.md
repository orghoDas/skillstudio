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
| Frontend security | 🔴 Pervasive DOM-XSS + tokens in `localStorage` |
| Build / delivery | 🟠 CDN Tailwind, no build, no static assets, no SSR |
| Code consistency | 🟠 Shared helper exists but ~7 templates bypass it |
| Integration (auth/contract) | 🟠 Session/JWT split-brain, unprotected pages, no API contract |

---

# Part A — Frontend

Every `core` view is just `render(request, 'x.html')` with **no context** (`core/views.py`). All data is fetched client-side via inline `fetch()`.

## 🔴 Critical

### 1. DOM-XSS across nearly every page
API data is injected into `innerHTML` via template literals with **no escaping**. Example — `courses/list.html:153`:

```js
container.innerHTML = courses.map(course => `...<h3>${course.title}</h3>...`);
```

Course titles, categories, bios, and instructor names are **user-authored**, so this is **stored XSS**. The pattern appears in essentially all 20+ data templates (`students/learn.html` alone has 10 `innerHTML` writes). Combined with Critical #2, one malicious course title can steal every visitor's session.

- **Fix:** Add a single HTML-escaping helper and route all interpolated API data through it, or build nodes with `textContent`/`createElement`.

### 2. JWTs stored in `localStorage`
32 `getItem('access_token')` reads across templates. Any XSS (see #1) reads the token directly.

- **Fix:** Prefer `httpOnly` cookies for the token, or at minimum eliminate the XSS surface in #1.

## 🟠 High

- **Inconsistent API access → duplicated, weaker logic.** `base.html:165-230` has a solid `apiRequest` helper (401 → refresh → retry, CSRF header, error-body parsing). But ~7 templates (`courses/list.html`, `home.html`, `exams/*`) use **raw `fetch()`**, bypassing token refresh and unified error handling.
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

- **Split-brain auth model.** Templates are **session-rendered** but auth is **JWT-in-`localStorage`**. So `{% if user.is_authenticated %}` (`base.html:77`) is **always false** — dead code. More importantly, **page routes have zero server-side protection**: `/dashboard/`, `/instructor/...`, `/checkout/` all render for anyone; only the API enforces auth. Result: protected pages load, then redirect client-side (content flash + structure leak).
- **Confused CSRF/JWT mix.** The helper sends `X-CSRFToken` on mutations (`base.html:178`), but JWT bearer auth does not use CSRF and there is no session cookie. Harmless, but signals the security model was not deliberately chosen.
- **No API contract.** The frontend hardcodes route strings and guesses response shapes (`data.results || data` everywhere) — a symptom of contract instability. No OpenAPI/schema gate, so backend changes silently break pages.
- **End-to-end price integrity is broken.** `payments/checkout.html` computes `final_amount` client-side and posts `amount`, which the backend then trusts (`payments/views.py:80`). The client-controlled-amount flaw is **full-stack**, not just backend.
- **Dead removed-feature wiring.** The AI recommender was removed from the backend, but `core/urls.py` still routes `recommendations/` → `ai_recommendations` and `base.html:78` keeps an "AI recommender widget removed" placeholder. Stale surface on both sides.

---

## Recommended fix order

1. Kill the XSS: add an escaping helper and route all interpolated API data through it (Frontend Critical #1).
2. Add server-side auth guards on protected page routes (Integration).
3. Route every data call through `apiRequest`; delete raw `fetch()` duplicates (Frontend High).
4. Replace CDN Tailwind with a real build (purge + minify + cache-bust) and move JS into versioned static files.
5. Publish an OpenAPI schema and align template route/response assumptions to it.
