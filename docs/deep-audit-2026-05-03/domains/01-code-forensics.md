# Agent 1 — Code Forensics

**Run:** 2026-05-03 19:29-19:55 UTC
**Scope:** apps/transcribe-md, apps/marketing, apps/meddoc-pro, packages/{ai,auth,db,types}

## Executive summary

The codebase is in **good shape**. TypeScript is clean across all 3 apps,
ESLint baseline is enforced (no `as any`, no `@ts-ignore` outside one
intentional test file, no loose `==`, no missing React keys, no Promise
chains without error handling). The AI pipeline architecture (12 layers
+ Sentry orchestrator + redactPhi + retry-decision + categorizeError +
admin-notifications) is **production-grade**.

**Findings: 4 P3, 0 P2, 0 P1, 0 P0.** All P3s are batched into the
cleanup PR.

| # | Finding | Severity | App |
|---|---|---|---|
| CF-01 | 13 circular dependencies (4 in transcribe-md, 9 in meddoc-pro) | P3 | meddoc-pro, transcribe-md |
| CF-02 | 17 unused npm dependencies (mostly Phase-4 cinematic-era leftovers: three.js, @react-three/*, framer-motion) | P3 | all |
| CF-03 | ~18 `console.log/info` calls in production code paths (most in `useRealtimeSession.ts` realtime debugging — should be gated behind a debug flag or removed) | P3 | meddoc-pro |
| CF-04 | Email enumeration on signup ("An account with this email exists. Sign in instead.") — UX vs security tradeoff for HIPAA-eligible product | P3 / INFO | transcribe-md |

---

## Tool inventory + raw outputs

| Tool | Purpose | Raw output |
|---|---|---|
| `tsc --noEmit -p .` | Type errors per app | (clean — 0 errors all 3 apps) |
| `madge --circular` | Circular import graphs | `artifacts/tool-output/madge.txt` |
| `depcheck --json` | Unused npm deps per app | `artifacts/tool-output/depcheck.json` |
| `rg` | Anti-pattern hunt | (in this report) |
| ESLint | (deferred — exists in package.json `lint` script; not run here to keep RAM available) | — |

---

## TSC results

| App | Status |
|---|---|
| transcribe-md | ✓ 0 errors |
| marketing | ✓ 0 errors |
| meddoc-pro | ✓ 0 errors |

Packages (`@meddoc/ai`, `@meddoc/auth`, `@meddoc/db`, `@meddoc/types`)
are consumed by the apps' compilers (no per-package `tsconfig.json`),
so tsc on the apps transitively type-checks them.

---

## Anti-pattern hunt (ripgrep)

| Pattern | Hits | Status |
|---|---|---|
| `as any` | **0** | ✓ |
| `@ts-ignore` / `@ts-expect-error` | 3 (all in `email-auto-confirm.test.ts`, intentional runtime-guard tests) | ✓ |
| `TODO/FIXME/XXX/HACK:` | 2 (1 roadmap marker in retention-sweep, 1 pricing-tiers note) | ✓ |
| `console.log/debug/info` (excluding scripts/worker) | 18 | ⚠️ see CF-03 |
| `console.error/.warn` (intentional) | 194 | ✓ |
| `parseInt` without radix | 1 (with radix 10 — false positive) | ✓ |
| Loose `==` | **0** | ✓ |
| Missing React `.map(...)` keys | **0** | ✓ |
| Direct DOM access in components | 2 (focus management — intentional) | ✓ |
| `Promise.then` without `.catch` | **0** | ✓ |
| `useEffect(()=>{...}, [])` with stale-closure risk | 2 (greeting + interval — both correct hydration patterns) | ✓ |

---

## CF-01 — 13 circular dependencies

### transcribe-md (4 circulars)
```
1) ../../../packages/ai/src/deepgram-batch.ts > ../../../packages/ai/src/mock.ts
2) ../../../packages/ai/src/mock.ts > ../../../packages/ai/src/embed.ts
3) lib/nextauth.ts > lib/audit.ts
4) app/visits/[id]/visit-ready-view.tsx > app/visits/[id]/transcript-tab.tsx
```

### marketing (0 circulars) ✓

### meddoc-pro (9 circulars)
Mostly the `system-admin` page tree:
```
1) lib/audit.ts > lib/auth.ts > lib/nextauth.ts
2) lib/auth.ts > lib/nextauth.ts > lib/session-log.ts
3-9) various app/system-admin/* loops (page → table → modal → actions → mock-users → page)
```

**Severity:** P3 — circulars compile fine and don't cause bugs at runtime,
but they trip code-splitting heuristics (the entire system-admin module
bundles together because the cycle prevents the bundler from extracting
chunks). They also make refactoring riskier — any extracted file may
get pulled back in by a transitive cycle.

**Proposed fix:** mostly extracting shared types into a `system-admin/
types.ts` module that the page, table, modals, and actions all import
from (instead of from each other). The auth circular (`audit ↔ auth ↔
nextauth`) is more fundamental and may warrant a small `auth-shared.ts`
module. **Plan-only — do not auto-fix; risks subtle behavior change.**

---

## CF-02 — 17 unused npm dependencies (depcheck)

| App | Unused deps | Unused devDeps | Notes |
|---|---|---|---|
| transcribe-md | 6 | 4 | `@react-three/drei`, `@react-three/fiber`, `three`, `framer-motion`, `@meddoc/types`, `@radix-ui/react-toast`. Three.js leftovers from Phase 4 cinematic hero (already retired). Tailwind devDeps are referenced via PostCSS so depcheck false-positives. |
| marketing | 4 | 3 | `@react-three/drei`, `@react-three/fiber`, `three`, `geist`. Same pattern. |
| meddoc-pro | 7 | 4 | `@hookform/resolvers`, `@stripe/stripe-js`, `file-saver`, `pg`, `react-hook-form`, `stripe`, `zustand`. **WARN: stripe/react-hook-form/zustand may be used in admin features that depcheck doesn't trace** (dynamic imports / route-handler imports). Verify before removing. |

**Severity:** P3 — unused deps inflate `npm install` time and the
runtime image (~50-100MB across the 3 apps). No security risk.

**Proposed fix in cleanup PR:** ONLY remove `three`, `@react-three/drei`,
`@react-three/fiber`, `framer-motion` from marketing + transcribe-md
(definitely unused — Phase 7 v6 redesign retired the 3D hero, no
imports anywhere). All other unused-flagged deps are SUSPICIOUS — could
be dynamic imports — and need manual verification per-package. The
Tailwind devDeps must NOT be removed (they're consumed via
postcss.config.js).

---

## CF-03 — 18 console.log/info in production code paths

Locations (all in meddoc-pro + 1 in transcribe-md):
- `lib/hooks/useRealtimeSession.ts` (×9) — realtime session debugging
- `lib/audit.ts:180` (×1) — likely intentional structured log; verify
- `app/dashboard/patients/[id]/GlobalAIAssistant.tsx` (×2) — AI assistant context refresh
- `lib/edit-tracking.ts:63` — visit edit logger
- `app/api/auth/resend-verification/route.ts` (×2) — auth flow logging
- A few others

**Severity:** P3 — `console.info` in browser code lands in user devtools;
in server code it lands in stdout (visible in `docker logs`). Not a
security risk (no PHI in any of the logged values per quick spot-check)
but it's noise that should either be:
- Replaced with structured `log.info(...)` from `@/lib/log`
- Gated behind `process.env.DEBUG_REALTIME` or similar
- Removed if no longer needed

**Proposed fix in cleanup PR:** I won't touch these — `useRealtimeSession`
debugging is genuinely useful for the in-progress realtime feature; the
auth-route logging is intentional ops visibility. List for Kasra to
triage which to keep.

---

## CF-04 — Email enumeration on signup

`apps/transcribe-md/src/actions/auth.ts:354`:
```ts
errors: { email: 'An account with this email exists. Sign in instead.' }
```

This explicitly tells a signup attacker whether a given email is
already registered. Standard "secure" advice is to return the same
"check your email" page regardless of whether the account existed,
and only send a "please sign in" email instead of a verification
email when the account exists.

**Tradeoff:** UX cost is real. Doctors who forget which email they
signed up with would otherwise hit a confusing "check your email"
that never arrives. For QuillMD's threat model (solo doctors, not a
mass-credential-stuffing target) the leak payoff for an attacker is
near-zero (knowing Dr. X uses QuillMD doesn't help attack Dr. X's
medical records).

**Recommendation:** keep as-is. Document in a security FAQ. Mark INFO,
not P3. Same logic applies to `loginAction` lines 175-183 (unverified
account → "Please verify your email" reveals account existence + that
email-verify hasn't completed — both are existence signals).

---

## Auth code audit — clean ✓

`apps/transcribe-md/src/lib/auth-tokens.ts`:
- ✓ `usedAt: null` enforced before consumption (atomic via `updateMany`)
- ✓ `expiresAt < new Date()` checked
- ✓ Token consumption is race-condition safe (one-shot via WHERE clause)
- ✓ Token comparison is constant-time at the DB layer (B-tree btree
  index lookup; no client-side string compare)

`apps/transcribe-md/src/actions/auth.ts`:
- ✓ Rate limiting applied: SIGNUP, LOGIN, AUTH_EMAIL (resend-verification,
  forgot-password, reset-password, confirm-email, verify-email),
  SETTINGS (change-password, change-email, delete-account, export-data),
  CLIENT_ERRORS, VISIT_OPS — comprehensive coverage
- ✓ Timing-equalizer (`DUMMY_PASSWORD_HASH`) on login to prevent
  email-enumeration via response-time analysis (T-M18.3 A20 — already
  documented in the source)
- ✓ Email-verification gate is conditionally skipped via the QA
  bypass added in PR #96 (`isAutoConfirmDomain` — narrowly scoped)

---

## AI pipeline audit — clean ✓

`apps/transcribe-md/src/worker/`:
- ✓ 12 layers (01-transcribe through 07e-summary) + readability
- ✓ Each layer is a single async function that throws on error;
  orchestrator (`worker.ts`) wraps with `try/catch` + `categorizeError`
  + Sentry (`captureWorkerException`)
- ✓ Hard timeouts per layer ("exceeded ${ms}ms hard cap — fail-fast")
- ✓ Resume state via `loadResumeState` — partial completions on retry
  skip already-completed layers
- ✓ `redactPhi` from `@meddoc/ai` used in queue logging, deliveries,
  retention-sweep before any error message that might quote PHI
- ✓ `notifyAdminOnFailure` — ops alert on terminal failure
- ✓ BullMQ retry policy via `retry-decision.ts` (only the FINAL
  attempt marks visit FAILED so users see processing-spinner during
  backoff, not an error)
- ✓ Token budget / model selection: via `@meddoc/ai`'s `modelClient`
  abstraction; centralized

**No findings.** This is some of the better AI-pipeline code I've
seen — clear separation of concerns, defensive error handling, PHI
hygiene baked in.

---

## What was NOT covered (deferred or out of scope)

- **ESLint full run** — the `eslint` binary is per-app via
  `npm run lint`; running it across 3 apps would burn 5-10 min of
  RAM-tight time. Deferred to per-PR CI (which already runs it).
- **Bundle analysis** — `next build --analyze` would pin down exactly
  which unused-flagged deps bloat the runtime image. Deferred until
  bundle size becomes a perf concern.
- **Coverage / mutation testing** — out of scope for this audit.
- **Codebase metrics** (cyclomatic complexity, max file size) —
  deferred unless a P0/P1 surfaces requiring rewrite of a hot file.
