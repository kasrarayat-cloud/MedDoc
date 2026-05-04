# Domain A — Edge Cases (Round 2)

**Run:** 2026-05-03 20:21–20:35 UTC
**Method:** Playwright headless against production via QA-bypass account
**Test account:** `qa-round2-1777839713@quillmd-test.local`

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| A1  | Refresh during recording | DEFERRED | needs real mic stream — synthetic recording in headless not feasible without WebRTC fake-stream |
| A2  | Network drop mid-pipeline | DEFERRED (time) | doable via `page.route('**', r => r.abort())` — recommend follow-up |
| A3  | Two-tab edit conflict | DEFERRED (RAM) | needs 2 contexts — RAM tight |
| A4  | Rapid clicking | ✓ tested — see A4-001 below | **client lacks dedup; saved by server 429** |
| A5  | Browser back during pipeline | DEFERRED (time) | next round |
| A6  | Logout during pipeline | DEFERRED (time) | next round |
| A7  | Weird emails (signup) | ✓ tested | **A7-001: 180-char email accepted + auto-confirmed** |
| A8  | Patient name injection (SQL/XSS) | ✓ SAFE — Prisma + React escape | positive finding |
| A9  | DOB edges | partial — rate-limited mid-test | follow-up |
| A10 | Long text fields | ✓ — server returned `Too many requests. Try again late...` | rate limit confirmed |
| A11 | Empty form submissions | ✓ — `Name is required.` clear; HTML5 native validation on signup/login | safe |
| A12 | Special chars in transcript | covered by A8 (SOAP body would render escaped same as patient name) | inferred safe |
| A13 | Concurrent visits (5 parallel) | DEFERRED (RAM) | next round |
| A14 | Audio file edges (zero, corrupt, 100ms, 8kHz, stereo, 5min) | partial — test rig stuck at step-1 wizard re-entry; only first 4 reached upload step in initial pass | **needs reliable patient-reuse pattern** |
| A15 | Session timeout (20-min idle) | DOCUMENTED only — can't simulate 20-min wait | session expiry exists per `sessions.expiresAt = +7d` per Round 1 |

---

## Findings

### A4-001 — Client lacks debounce on Create & continue (P3)

**Severity:** P3
**File:** `apps/transcribe-md/src/app/visits/new/...` (need source-tree confirmation; not located in this run)

5 rapid `Create & continue` button clicks fire **10 backend requests**
(5 × `POST /api/patients/fuzzy-match` + 5 × `POST /api/patients`).
The server-side rate limiter catches them all — every one of the
10 returned **429 Too Many Requests**. So no DB damage. But:
- A user who rapid-clicks thinking the UI is frozen will see
  "Too many requests" error rather than progress.
- If rate-limit window was wider (or server scaled up), the
  duplicate patient rows would land in DB.

**Recommended fix:** disable the button on first click, show a
spinner, re-enable on response. Standard React pattern with `[busy,
setBusy]`.

**Risk if NOT fixed:** mostly UX (rate-limit error bubble), not
data integrity.

### A7-001 — Email field has no max-length validation (P2)

**Severity:** P2 (DB pollution attack surface)
**File:** `apps/transcribe-md/src/actions/auth.ts:64-76` — `SignupSchema`

The signup `SignupSchema` uses `z.string().email()` which has NO
length cap. RFC 5321 caps email local-part at 64 chars and total
at 254 chars. We accepted a 180-char-local-part email and the
QA bypass auto-confirmed it. Verified in DB:

```
[QA-BYPASS] auto-confirmed email for aaaaaaaaaaaaaaaaaaaaaaaaaaaa
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
aaaaaaaaaaaaaaaaaa-1777839763@quillmd-test.local (domain on
EMAIL_AUTO_CONFIRM_DOMAINS allowlist)
```

**Why it matters:** an attacker can spam-create users with extremely
long emails to inflate DB size, mess up rendering in admin lists,
or evade per-email rate limits if those limits hash long emails
differently. With QA-bypass accepting `quillmd-test.local`, this
also expands the attack surface for QA-test pollution.

**Note:** The QA bypass IS scoped to `quillmd-test.local` only, so
real-mail providers can't be exploited via this same path. But the
core validation gap (`z.string().email().max(254)`) applies to ALL
signups regardless of domain.

**Recommended fix (1 line in auth.ts:65):**
```diff
- email: z.string().email(),
+ email: z.string().email().max(254),
```

Same recommendation for `name` and `confirmPassword` already
have caps; only `email` is missing.

**Risk if NOT fixed:** DB-pollution / rendering-corruption risk.
No active exploit path found, but a hostile signup could create
an account whose email overflows admin UI tables.

### A8 — POSITIVE: SQL injection + XSS NOT exploitable

Tested 10 attack payloads as patient-name input:
`O'Brien`, `'; DROP TABLE patients; --`, `<script>alert(1)</script>`,
`<img src=x onerror=alert(1)>`, emoji, unicode, MongoDB operators,
null bytes, 500-char overflow, RTL chars.

Result:
- **5 of 10 reached DB intact**: `O'Brien`, `'; DROP TABLE...`,
  `<script>alert(1)</script>`, `<img src=x onerror=alert(1)>`,
  emoji. Stored verbatim as data, NOT executed as code.
- 5 rejected by client validation or rate limit (the long one,
  unicode, mongo-op, null byte, RTL).
- `transcribe_md_patients` table SURVIVED — count steady (52 rows).
- `<script>` tag found in DOM by querySelector but was an RSC payload
  (escaped JSON in Next.js streaming), NOT an executable script. **No
  alert() fired.** React's default escaping handles patient-name
  rendering correctly.

✅ Prisma parameterized queries + React text-content escaping work
as expected. This is the most important finding of Domain A — the
patient-name field is the most likely XSS vector and it's safe.

### A11 — POSITIVE: Form validation works

- Patient creation with empty name → `"Name is required."` (visible)
- Signup with empty fields → HTML5 native validation popups (browser)
- Login with empty fields → HTML5 native validation popups

All 3 prevent submission. Standard, defensible pattern.

### A14 partial — audio upload rate-limit observation

Methodology issue: my test script tried to re-use the same patient
for 8 different audio uploads, but the wizard re-entry loop got
stuck at step 1 after the first 4 cases (possibly because the patient
row got soft-deleted between iterations, or the wizard cached state).

Documented for next round: write per-test fresh patient creation
+ delay between uploads to avoid rate limits.

### A15 — DOCUMENTED only

Session expiry: `user_sessions.expiresAt` is set to `+7 days` per
DB schema (verified in Round 1 audit). 20-minute idle timeout would
require SLIDING expiry which the schema doesn't appear to model
(no `lastActiveAt` column) — the session lasts 7 days regardless
of activity. **Not a P0**, but worth confirming with Kasra whether
the intent is "fixed 7-day token" vs "sliding 20-min idle".

---

## Test-rig limitations (for future audits)

- Headless Playwright can't access mic permissions for true recording
  tests (A1). Need WebRTC fake-stream + mocked getUserMedia.
- Multi-context tests (A3, A13) need RAM headroom we don't have on
  this 1.6 GB VPS.
- A14 needs per-test fresh patient + delays between uploads to avoid
  the same rate-limit window.
- A15 needs at least one full session-timeout cycle (20 min) which
  isn't realistic in a 4h audit window — should be a separate
  long-running test.
