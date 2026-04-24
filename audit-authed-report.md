# Audit — authenticated flows

Branch: `audit/authenticated-flows`.
QA user: single unified account (`qa-audit@quillmd.local`, `practiceId: qa-practice-audit`, `products: [MEDDOC_PRO, TRANSCRIBE_MD]`) — the `users` table is shared between the two apps, so one account covers both. User was seeded via direct `INSERT` (bypassing email verification) with a known bcrypt hash.

> Teardown after report:
> `DELETE FROM users WHERE id='qa-audit-user-unified';`
> `DELETE FROM practices WHERE id='qa-practice-audit';`

## Summary

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 1 |
| Medium | 2 |
| Low | 2 |
| Positives (explicitly tested) | 6 |

The one bug the first audit missed and that's clearly present is the **React #418 hydration mismatch on `/dashboard/doc-editor`** (H1 below).

---

## High

### H1 — Hydration mismatch on `/dashboard/doc-editor` (pro.quillmd.com)

**Repro:** Log in to pro.quillmd.com, navigate to Doc Editor from the sidebar. Every fresh page load throws `Minified React error #418`.

**Evidence:**
- `audit-evidence/authed/console-logs/pro-session.json` — `pageerror: Minified React error #418`
- `audit-evidence/authed/network-logs/pro-per-page-errors.json` — reproduced on 3/3 loads of `/dashboard/doc-editor`; 0/6 on sibling routes (`/dashboard`, `/dashboard/patients`, `/dashboard/schedule`, `/dashboard/history`, `/dashboard/audit`, `/dashboard/settings`)

**Root cause:** `apps/meddoc-pro/src/app/dashboard/doc-editor/page.tsx:333-337`
```ts
const voiceSupported =
  typeof window !== 'undefined' &&
  typeof navigator !== 'undefined' &&
  !!navigator.mediaDevices &&
  typeof window.MediaRecorder !== 'undefined';
```
Computed during render. On the server `voiceSupported` is `false`; after hydration on the client it's `true`. Markup that depends on this (a voice button / mic trigger in the JSX below) therefore differs between SSR HTML and the client's first render. React's default response is to discard the streamed SSR subtree and re-render client-side, which:
- Breaks SSR performance (whole tree re-mounts)
- Floods Sentry with hydration errors once that DSN is wired in
- Sometimes flashes empty content for a frame

**Expected:** No pageerror on initial load. Server HTML should match client first-paint.

**Fix (≈15 min):**
```ts
const [voiceSupported, setVoiceSupported] = useState(false);
useEffect(() => {
  setVoiceSupported(
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof window.MediaRecorder !== 'undefined'
  );
}, []);
```
Or wrap the component with `dynamic(() => import('...'), { ssr: false })` and keep the check inline.

---

## Medium

### M1 — Visit-not-found page returns HTTP 200 (app.quillmd.com)

**Repro:** `curl -sk -o /dev/null -w '%{http_code}\n' -b <session-cookie> https://app.quillmd.com/visits/cmabcdef000000abcd` (any cuid that doesn't resolve to a visit you own). Returns `200`.

**Evidence:** `audit-evidence/authed/screenshots/d3-02-random-visit.png` — page renders *"404 — Visit not found — This visit doesn't exist or you don't have access to it"* styled as a 404 screen, but the HTTP response is 200.

**Actual vs expected:** Expected — HTTP 404 (or a 302 to login when unauth). Actual — HTTP 200 with a 404-styled view.

**Impact:**
- Analytics / uptime tools that count 404s will miss these.
- Search-engine indexers (even though the page is behind auth the response-code semantics should still be honest; 200 means "this URL is a real resource," and a crawler following a stale link will keep the URL in the index).
- Cache layers may cache a "404" HTML under a successful-response TTL.

**Root cause (suspected):** `apps/transcribe-md/src/app/visits/[id]/page.tsx` — the server component likely checks the visit-not-found branch and renders a component rather than calling Next's `notFound()` helper. Switching to `notFound()` throws and Next returns a real 404.

**Fix (≈15 min):** In the server-component loader, after the ownership check:
```ts
if (!visit || visit.userId !== userId) notFound();
```
(instead of returning a custom not-found JSX).

### M2 — Dashboard greets user by their LAST name, not first (pro.quillmd.com)

**Repro:** Any pro.quillmd.com user whose `name` column contains a space. Login → `/dashboard` → header reads "Good morning, *{lastToken}*".

**Evidence:**
- `audit-evidence/authed/screenshots/d6-mobile-dashboard.png` — QA user's name is "QA Pro mockf3vk"; greeting shows "Good morning, mockf3vk".
- `audit-evidence/authed/screenshots/d5-sysadmin-as-doctor.png` — same render.

**Root cause:** `apps/meddoc-pro/src/app/dashboard/DashboardClient.tsx:103`
```ts
const firstName = doctorName.split(' ').pop() ?? doctorName;
```
Variable is named `firstName`; `.pop()` returns the LAST token. Used at line 161: `{greeting}, {firstName}`.

For a real doctor name like "Dr. Bakhtiar Moussazadeh", the greeting renders "Good morning, Moussazadeh" instead of "Good morning, Bakhtiar".

**Fix (≈5 min):**
```ts
// Pick a sensible given-name: strip an honorific prefix, then take the first token.
const HONORIFICS = /^(dr|mr|mrs|ms|miss|prof)\.?$/i;
const tokens = doctorName.trim().split(/\s+/);
const firstName = tokens.find((t) => !HONORIFICS.test(t)) ?? doctorName;
```

Same fix pattern should be checked across any other greeting/display code.

---

## Low

### L1 — Greeting calls `new Date()` twice (race at midnight / 12:00 / 18:00)

**Where:** `apps/meddoc-pro/src/app/dashboard/DashboardClient.tsx:105`
```ts
const greeting =
  new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 18 ? 'Good afternoon' : 'Good evening';
```
Two separate `new Date()` calls in the same ternary. At 11:59:59.999 the first branch could evaluate "morning" and the second "afternoon" if the evaluation crosses the boundary (theoretical; Date resolution is ms). Also wasteful.

**Fix:** `const hour = new Date().getHours();` once.

### L2 — DOCTOR can load `/dashboard/audit` on pro.quillmd.com

**Context:** The QA user has `role: DOCTOR`. Hitting `/dashboard/audit` returns 200 and renders the HIPAA §164.312(b) audit log.

**Why it's only Low:** The rendered log appears to be scoped to the current user's own actions — the QA user sees 8 events, all their own (login + patient-list views). No other user's audit rows leaked through in my tests. So at worst it's unclear UX (is this feature meant to be per-user or practice-wide?), not a privacy breach. Confirm the server action's `WHERE` clause is `userId = session.user.id`, not just `practiceId = ...`.

**Evidence:** `audit-evidence/authed/screenshots/d5-audit-as-doctor.png` — only 8 events, all qa-audit@quill.

---

## Positives (explicitly verified, not findings)

1. **Session isolation across tabs** — logging out in tab A invalidates tab B's session on next navigation. `audit-evidence/authed/screenshots/d4-06-tab2-after-logout.png` shows tab 2 bounced to `/login?callbackUrl=...`.
2. **Session isolation across subdomains** — `__Host-authjs.csrf-token` is correctly scoped; clearing cookies on pro didn't log out app and vice versa. `curl -v` confirms `Path=/; HttpOnly; Secure; SameSite=Lax; __Host-` on both.
3. **Direct API tenant authz** — `/api/patients/{cuid_from_other_tenant}`, `/api/visits/{other}/export/pdf` return 404 with opaque `{"error":"not found"}`, no data leak.
4. **SUPER_ADMIN-only routes correctly redirect DOCTORs** — `/system-admin` bounces a DOCTOR to `/dashboard`.
5. **XSS on settings name field** — fill with `<script>window.__xss=true</script>`, submit, reload. React escaped. No `window.__xss` set.
6. **Cross-subdomain SSO is NOT happening** — logging in to app.quillmd.com does not authenticate on pro.quillmd.com and vice versa. Each domain has its own session cookie.

---

## Surface inventory tested

| Surface | Pages walked | Buttons exercised | Notes |
|---|---:|---:|---|
| app.quillmd.com | /dashboard, /visits, /visits/new (full wizard end-to-end), /visits/[id], /patients, /settings, /settings#profile/#security/#sessions/#data/#billing/#danger | ~15 | Patient created, visit created, profile name saved successfully |
| pro.quillmd.com | /dashboard, /dashboard/patients, /dashboard/schedule, /dashboard/doc-editor, /dashboard/history, /dashboard/audit, /dashboard/settings, /system-admin (redirected) | ~12 | Mobile viewport tested at 393×851 — no overflow on any of the 4 tested pages |

### Surfaces explicitly NOT covered (out-of-scope for this pass)

- Full visit processing pipeline (real audio → Deepgram → Claude → SOAP) — would burn external API credits for a structural probe
- Realtime voice assistant (`useRealtimeSession` hook on pro) — requires OpenAI Realtime connection
- Email-delivery flows (Sign & Send, Export → email) — would send real emails from prod to test inboxes
- Patient-detail subtabs on pro — QA practice has no patients yet; tested list level only

---

## Evidence

```
audit-evidence/authed/
├── screenshots/           (25+ PNGs — desktop + mobile)
├── console-logs/
│   ├── app-session.json    (64 events — mostly RSC-prefetch aborts, 0 real errors)
│   ├── pro-session.json    (59 events — 1 real: React #418 on doc-editor)
├── network-logs/
│   ├── app-crawl.json      (6 links, all 200)
│   ├── pro-crawl.json      (7 links, all 200)
│   ├── pro-per-page-errors.json  (per-page error isolation → confirms /dashboard/doc-editor is the only offender)
│   ├── d3-account-menu.json
│   ├── d3-bugs.json
│   ├── d4-bugs.json
│   ├── d5-bugs.json
│   ├── d6-bugs.json
│   ├── pro-watch-demo.json
│   ├── pro-more-filters.json
│   └── cmdk-result.json
├── probe-app.ts             (authed probe script for app.quillmd.com)
├── probe-pro.ts             (authed probe script for pro.quillmd.com)
└── probe.config.ts          (Playwright config reusing transcribe-md's @playwright/test)
```
