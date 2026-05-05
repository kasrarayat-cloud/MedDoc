---
id: A11-P2-003
severity: P2
domain: error-handling-observability
title: Caddyfile has no `handle_errors` block — upstream 502 / 503 shows Caddy's default white page
---

# A11-P2-003 — Caddy upstream-failure UX is the default Caddy error page

## Issue

`/opt/meddoc-pro/Caddyfile` defines reverse_proxy blocks for
`quillmd.com`, `app.quillmd.com`, `admin.quillmd.com`, `pro.quillmd.com`
but does NOT define a `handle_errors` block on any of them, nor a global
default. When the upstream (e.g. `transcribe-md:3011`) is down or
returning a 502/503/504 to Caddy, the doctor's browser shows the default
unstyled Caddy error page:

```
502 Bad Gateway
```

…which contains no branding, no contact info, no "we're aware, try again
in a minute" copy, no support email. The runbook's "5xx handling" expectation
is unmet. The user-facing in-app error fallback (`app/error.tsx` →
`ErrorFallback`) only fires for in-app render errors — it cannot help if
the *container itself* is unreachable.

## Evidence

```
$ grep -n "handle_errors\|@error" /opt/meddoc-pro/Caddyfile
# (no matches — no error-page block anywhere)
```

`Caddyfile:65-79`, `82-96`, `216-238` — all the `reverse_proxy` blocks for
quillmd.com / app.quillmd.com / pro.quillmd.com follow the same shape,
none with a fallback page.

## Risk

Three concrete scenarios:

1. **Deploy mid-rolling-restart**: `docker compose up -d --build
   transcribe-md` takes ~60 s for the container to start serving. During
   the swap, Caddy's reverse_proxy will return 502 to a fraction of in-flight
   requests. A doctor mid-recording sees a raw 502 and either reloads
   (losing the recording in browser-side state) or contacts support.

2. **Worker unreachable but app responsive**: enqueue fails (see the upload
   route's 502 handler), but a similar failure on the upload itself
   bubbles up as a Caddy 502 if the transcribe-md container flapped
   between "alive" and "503 from /api/health". User sees raw Caddy page.

3. **Pilot-launch first impression**: the marketing site goes 502 because
   a build pulled a missing env var on first deploy. A prospect lands on
   quillmd.com, sees a raw Caddy page, leaves. No bookmark, no retry, no
   conversion.

## Recommended fix

Add a shared `handle_errors` snippet in `Caddyfile`:

```caddy
(branded_error_page) {
    handle_errors {
        @5xx expression {http.error.status_code} >= 500
        @4xx expression {http.error.status_code} >= 400 && {http.error.status_code} < 500
        handle @5xx {
            respond "We're temporarily unavailable. Please try again in a moment.

If this persists, contact support@quillmd.com.
Status: {http.error.status_code}" {http.error.status_code} {
                close
            }
        }
        handle @4xx {
            respond "Page not found." {http.error.status_code}
        }
    }
}
```

Then `import branded_error_page` inside each `quillmd.com {…}`,
`app.quillmd.com {…}`, etc. block.

For polish: serve a static HTML file (e.g. `caddy_data/error-503.html`
mounted into the caddy container) with the QuillMD logo, support email,
a 30-second auto-refresh meta tag, and a status-page link if/when one
exists. The static file approach is cleaner than inline `respond` for
multi-line branded copy.

Independent of fix: confirm that `app.quillmd.com/api/health` returning
503 from the *application* gets propagated as 503 to the client (not
re-mapped to 502 by Caddy). Currently the Caddyfile does no
`@status` matching so 503 should pass through — but verify with a
deliberate test (down the postgres container; curl the public URL;
confirm 503 + branded page).
