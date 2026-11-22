// Global API helper
const API_BASE = '/api';

// Get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// ---------------------------------------------------------------
// XSS-safety helpers for interpolating untrusted API data into markup.
// Use escapeHtml() for any user-authored value placed inside innerHTML
// (text OR a quoted attribute); use safeUrl() for any value used as an
// href/src. A plain HTML escape does NOT neutralise javascript: URLs,
// which is why href/src need safeUrl instead.
// ---------------------------------------------------------------
function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function safeUrl(value) {
    if (value === null || value === undefined) return '#';
    const url = String(value).trim();
    // Same-origin relative/root-relative paths are safe.
    if (url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) {
        return escapeHtml(url);
    }
    try {
        const parsed = new URL(url, window.location.origin);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
            return escapeHtml(url);
        }
    } catch (e) {
        // Unparseable — fall through to the safe default.
    }
    return '#';
}

// API fetch helper.
// Auth travels as httpOnly cookies (sent automatically on same-origin
// requests), so no token is read from JS. CSRF token is sent on mutations.
async function apiRequest(endpoint, options = {}) {
    const isFormData = (typeof FormData !== 'undefined') && (options.body instanceof FormData);
    const headers = {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
    };

    if (options.method && options.method !== 'GET') {
        headers['X-CSRFToken'] = getCookie('csrftoken');
    }

    const fetchOpts = { ...options, headers, credentials: 'same-origin' };
    let response = await fetch(`${API_BASE}${endpoint}`, fetchOpts);

    if (response.status === 401) {
        // Access cookie expired — try a cookie-based refresh, then retry.
        const refreshed = await refreshAccess();
        if (refreshed.ok) {
            response = await fetch(`${API_BASE}${endpoint}`, fetchOpts);
        } else if (refreshed.status === 401) {
            // Refresh failed — session is gone; send them to login.
            logout();
            return null;
        } else {
            response = refreshed;
        }
    }

    if (!response.ok) {
        // Try to parse JSON error body for nicer client messages
        let errorBody = null;
        try {
            errorBody = await response.json();
        } catch (e) {
            // ignore parse errors
        }
        const errMsg = (errorBody && errorBody.detail) || `HTTP error! status: ${response.status}`;
        const err = new Error(errMsg);
        err.status = response.status;
        err.body = errorBody;
        throw err;
    }

    return parseJsonBody(response);
}

// 204 No Content (e.g. a successful DELETE) or an empty body has no JSON
// to parse; response.json() would throw and make the call look failed.
async function parseJsonBody(response) {
    if (response.status === 204) return null;
    const text = await response.text();
    return text ? JSON.parse(text) : null;
}

// Logout helper: clears the httpOnly auth cookies server-side, drops the
// cached (non-sensitive) user display info, and returns to login.
async function logout() {
    try {
        await fetch(`${API_BASE}/accounts/logout/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            credentials: 'same-origin',
        });
    } catch (e) {
        // Even if the call fails, clear local state and redirect.
    }
    localStorage.removeItem('user');
    window.location.href = '/auth/login/';
}

let refreshRequest;
function refreshAccess() {
    if (!refreshRequest) {
        refreshRequest = fetch(`${API_BASE}/accounts/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            credentials: 'same-origin',
        }).finally(() => { refreshRequest = null; });
    }
    return refreshRequest;
}

// Bind allowlisted actions for controls that may be rendered after page load.
function bindActions(actions) {
    for (const [eventName, handlers] of Object.entries(actions)) {
        const attribute = `data-${eventName}`;
        document.addEventListener(eventName, event => {
            const control = event.target.closest?.(`[${attribute}]`);
            const action = control?.getAttribute(attribute);
            if (Object.hasOwn(handlers, action)) handlers[action](event, control);
        });
    }
}

// Restore the server-rendered navbar when a returning user's access has expired.
if (!document.body.dataset.pageRole && localStorage.getItem('user') &&
    !window.location.pathname.startsWith('/auth/')) {
    refreshAccess().then(response => {
        if (response.ok) window.location.reload();
        else if (response.status === 401) localStorage.removeItem('user');
    }).catch(() => { /* Keep the public page available while offline. */ });
}

document.getElementById('mobile-menu-btn')?.addEventListener('click', () => {
    document.getElementById('mobile-menu').classList.toggle('hidden');
});
document.getElementById('navbar-logout')?.addEventListener('click', logout);
const userMenuButton = document.getElementById('user-menu-btn');
const userMenu = document.getElementById('user-menu');
if (userMenuButton && userMenu) {
    userMenuButton.addEventListener('click', () => userMenu.classList.toggle('hidden'));
    document.addEventListener('click', event => {
        if (!userMenu.contains(event.target) && !userMenuButton.contains(event.target)) {
            userMenu.classList.add('hidden');
        }
    });
}
