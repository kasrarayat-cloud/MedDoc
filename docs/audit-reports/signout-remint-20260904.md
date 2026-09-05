# Finding — sign-out returned 200 without clearing the session cookie

**2026-09-04. Found in CI, not by looking for it.** Surfaced by the first-ever
`e2e` run on GitHub-hosted 2-vCPU hardware (PR #955); every green `e2e` before it
ran on the 8-core self-hosted box.

**Status: OPEN. Not fixed here.** This file records what was measured and what
was not, so the next person starts from evidence rather than from the symptom.

## The observation

`tests/e2e/scenarios/13-auth-logout.spec.ts`, via `helpers/auth.ts:71`
(`logoutViaMenu`), run `33896529655`:

```
expect(page).toHaveURL(/\/login$/) failed
  Received string: "http://localhost:9020/board"
```

and one line further down, on retry, polling for the session cookie to be gone:

```
at helpers/auth.ts:72
  Expected: false   Received: true
  Timeout 10000ms exceeded while waiting on the predicate
```

## What the trace establishes

From the run's uploaded `trace.zip` network log:

| request | status | response headers | `set-cookie` |
|---|---|---|---|
| `GET /api/auth/csrf` | 200 OK | 10 | **present** |
| `POST /api/auth/signout` | 200 OK | 6 | **ABSENT** |

⚠️ **The csrf row is the positive control, and it is the reason the absence is a
measurement rather than a gap in the instrument.** The trace demonstrably records
`set-cookie` headers — it recorded one on the immediately preceding request. The
signout response carrying none is therefore a fact about the response.

**The click landed.** The a11y snapshot at failure shows the account-menu button
with no open menu and no menuitem. Playwright's `.click()` on line 70
(`getByRole('menuitem', {name: /sign out/i})`) would have THROWN had the item been
absent; the failure is at line 71. Line 70 completed.

So: **sign-out fired, the server answered 200, and the session cookie was not
cleared.** The UI stayed on `/board` with full authenticated navigation for the
15s the assertion waited.

## ⚠️ A correction, recorded because it was mine

The first reading filed on #955 was that this was test flake — a menu click
landing before the menu was interactive, which would explain both symptoms at
once and is likelier on slow hardware. **The trace refuted it**, by the two
paragraphs above. The parsimonious explanation was the wrong one.

## What the code says

`src/lib/nextauth.ts:346` — the `signOut` event handler's own comment describes
this exact failure as the thing it exists to prevent:

> *"Without this only the cookie is cleared and the row survives — so a JWT that
> lingers in-flight … re-validates the session and re-mints the cookie,
> intermittently leaving the user signed in."*

Two defects in that guard, both found by reading it:

**1 · `sessionId` is READ in three places and WRITTEN in none.**

| site | what it does |
|---|---|
| `nextauth.ts:362` | reads `token.sessionId` to revoke ONE session |
| `auth.ts:133` | reads `session.user.sessionId`; its comment already hedges *"their token pre-dates T-M2 (no sessionId yet)"* |
| *nowhere* | assigns it |

The session strategy is `jwt` (`nextauth.ts:49`), and no `jwt` callback mints a
`sessionId` claim. So `'sessionId' in token` is **always false**, the targeted
`revokeSession(sessionId)` path is **dead code**, and every sign-out takes the
`revokeAllUserSessions(userId)` fallback — i.e. **signing out of one device
revokes every device**. That may be tolerable, but it is not what the code says
it does, and the hedge in `auth.ts` suggests it was believed to be sometimes
present.

**2 · The no-identifier case is a SILENT no-op.**

```ts
if (sessionId) await revokeSession(sessionId);
else if (userId) await revokeAllUserSessions(userId);
```

If both are null, nothing is revoked and **nothing is logged**. The `try/catch`
around it catches revoke *errors*, not the case where there was nothing to revoke
with. A guard whose failure mode is silence cannot be distinguished from a guard
that worked.

## What is NOT established

- **Whether the server-side `UserSession` row was revoked in this instance.** The
  missing `Set-Cookie` is NextAuth's own cookie-clearing, which is UPSTREAM of the
  event handler above. If revocation did happen, the retained cookie is inert and
  this is ugly but not dangerous. If it did not, a doctor who clicked Sign out
  still holds a live session. **The test's next assertions measure exactly this
  and it never reached them.**
- ⚠️ **And the log that would have settled it is gone, for a reason worth
  recording: the failed job was RE-RUN, and the re-run replaced the logs.** A grep
  for `[auth:signOut]` against that run now searches the SUCCESSFUL attempt — a
  zero about the wrong universe. **Pull artifacts BEFORE re-running a job whose
  failure you intend to diagnose.**

## Frequency

Intermittent. `main`'s `e2e` was green 11 of its last 12 runs, and the *same
commit* passed at 41m08s an hour before failing. It is a race, not a break.

## Why the hardware change matters

Every green `e2e` in this repo's history ran on an 8-core box. The first run on a
2-vCPU hosted runner hit this. That is evidence the race is **timing-sensitive and
was being hidden by fast hardware** — which is a reason to take it more seriously,
not less: a doctor's browser on clinic wifi is not an 8-core CI box.

## Suggested next step

Reproduce against the QA stack with the app logs retained, and answer the one open
question: **at the moment the cookie survives, does the `UserSession` row still
validate?** That single query separates "ugly race" from "sign-out does not sign
you out", and the remedy differs completely between them.

---

# ⚠️ CORRECTION, 2026-09-04 — THE LOAD-BEARING CLAIM ABOVE IS FALSE

**Appended, not rewritten.** The original text is kept above because the
correction is the point: what follows says which part was wrong, how it was
found, and what the mechanism actually is.

## WHAT WAS WRONG

> *"`sessionId` is read in three places and written in none … the targeted
> `revokeSession(sessionId)` path is **dead code**."*

**It is written.** `packages/auth/src/index.ts` assigns it inside the shared
`jwt()` callback on the sign-in branch, and `apps/transcribe-md/src/lib/
nextauth.ts` inherits that callback wholesale — it declares no `callbacks` key
of its own. `revokeSession` is therefore live and resolves.

⚠️ **THE ERROR WAS A SCOPED GREP.** I searched `apps/transcribe-md` and the
write is in `packages/auth`. One workspace of a monorepo is not the tree, and
the search returned a confident, complete-looking zero — the
incomplete-watched-set failure, with the watched set drawn along a directory
boundary nobody had reason to question. Found by an adversarial verification
lens and confirmed by hand before this correction was written.

## THE MECHANISM, WHICH IS WORSE

The original symptom was real and correctly measured: `POST /api/auth/signout`
answered **200 with no `Set-Cookie`**, the session cookie survived, and the UI
stayed authenticated. The cause is not the `sessionId` claim.

`events.signOut` holds **both** the `revokeSession` call **and** the LOGOUT
audit row, and `@auth/core/lib/index.js` reaches it only through
`actions.signOut`, which is gated:

    case "signout":
        validateCSRF(action, csrfTokenVerified);
        return await actions.signOut(cookies, sessionStore, options);

A failed CSRF check throws first, so **the revoke and the audit row are skipped
together** — the session stays live for the remaining 7 days of the JWT's
`maxAge`, and the incident leaves no artefact.

The 200 comes from the client always sending `X-Auth-Return-Redirect`, which
makes the framework's error path answer `Response.json({ url })` — status 200,
no cookies. And the trigger needs **no race**: `getCsrfToken()` in
`next-auth/react` ends `return response?.csrfToken ?? ""`, so one transient blip
on the preceding GET silently produces an unverifiable POST. It is
self-concealing: the client lands on `/login?error=MissingCSRF`, and `/login`
bounces a still-authenticated user to `/board` — the exact measured symptom.

**Every link above was read first-hand in `node_modules`**, not inferred.

## STATUS

Fixed by ruling #182 (PR #965), which routes every client sign-out through a
server action that revokes in-process, so there is no CSRF token to lose and no
200 that means nothing. What survives from the original filing: the observation,
its positive control, the intermittency, and the note that re-running a failed
job destroys the logs you needed.
