# Rule library — Code Quality / Pattern Auditor

> **Every rule below is grounded in a specific reference file/line in the
> QuillMD codebase as of merge-base `cefb2be` (PR #175 head, 2026-05-06).**
> When the canonical reference moves, the citation moves with it. Rules
> without a live citation are deleted, not preserved.
>
> Ordered by category. Within a category, severity tier is `BLOCK` → `WARN`
> → `NIT`. The auditor mechanically dereferences each rule's citation when
> running so a rule whose anchor disappeared surfaces as a `RULE_STALE`
> finding before any diff is scored.

## Severity tiers (referenced throughout)

- **BLOCK** — pattern violation that breaks consistency or risks safety:
  silent server-only import in client bundle, Prisma model mutating PHI
  without audit row, hardcoded API key, cross-app import into the
  decommissioned `apps/meddoc-pro/`, missing `'use client'` / `'use server'`
  on a file that needs one.
- **WARN** — drift from established convention but not breaking. Hardcoded
  hex when a `--color-linear-*` token exists, deviation from the
  `RxWarningsRail` state pattern, custom CSS where a `qm-lin-*` utility
  applies. Author should fix before merge or get reviewer agreement.
- **NIT** — style preference. Import ordering, naming taste, comment voice.
  Author may ignore.

Every finding emits this shape:

```json
{
  "rule_id": "TOKEN-001",
  "severity": "WARN",
  "category": "design-tokens",
  "file": "apps/transcribe-md/src/components/foo.tsx",
  "line": 42,
  "snippet": "color: '#7AA68C'",
  "message": "Hardcoded sage hex; use var(--color-linear-sage) or Tailwind text-linear-sage.",
  "canonical_ref": "apps/transcribe-md/src/app/globals.css:70",
  "fix_hint": "Replace #7AA68C with var(--color-linear-sage) (literal CSS) or text-linear-sage (Tailwind utility)."
}
```

## Scope guard

- Auditor reads diffs from `apps/transcribe-md/**` and `apps/marketing/**` only.
- `apps/meddoc-pro/**` is **excluded** — legacy decommissioned per
  `docs/POST_MERGE_TODO.md §21` and per memory (transcribe-md only). Any
  diff line in `apps/meddoc-pro/**` is silently dropped from the input set;
  any diff that *references* `apps/meddoc-pro/**` from inside the in-scope
  apps emits `SCOPE-001` BLOCK (see below).
- `_design-references/`, `docs/`, `infra/`, `scripts/`, agent files
  themselves are **out of scope for content rules** but `SCOPE-002` still
  fires on a cross-app symbol import to or from those.

---

## 1 · Design-token rules

Canonical reference: **`apps/transcribe-md/src/app/globals.css:36–97`** —
the `@theme { … }` block declaring every `--color-linear-*` and
`--font-*` token. Tailwind v4 auto-exports these as utilities; consumers
should reach for the token, not the underlying value.

### `TOKEN-001` — WARN — Hardcoded color hex/rgb/hsl when a token exists

**Trigger.** A `*.tsx`, `*.ts`, or `*.css` line under `apps/transcribe-md/**`
or `apps/marketing/**` contains a hex (`#0d0e10`, `#7AA68C`, `#21232a`,
…), `rgb(…)`, `rgba(…)`, `hsl(…)` literal that maps to a declared token.
The auditor's lookup table is built once per run from `globals.css:36–97`
plus the five derived values intentionally hard-coded in production (the
allowlist below).

**Scope split.** This rule covers *drift* — a hex literal where a token
exists but no regression-class signal applies. **Banned values
(`#9eb5a0`, `#050607`) are split out into `TOKEN-002` BLOCK** rather
than being a footnote on this rule. That keeps each rule single-tier
(WARN here; BLOCK there) and mirrors the LAYOUT-001 / SCOPE-001 family
pattern where regression-class concerns get their own rule ID.

**Allowlist (don't flag — these are intentional production values):**

| Hex | Where | Why allowed |
|---|---|---|
| `#0d1611` | `globals.css:417, 4182, 4226, 4489` (Bump CTA + btn-primary text-on-sage) | Hand-mixed dark sage; not a token; production comment marks it sacred. |
| `#88b599` | `globals.css:4192, 4498` | Bump CTA hover; one step brighter than `--color-linear-sage`; intentional. |
| `#e3b984` | `globals.css:310` | `pill--review` text; production decision (richer than `var(--color-linear-warning)` which is too saturated for a pill foreground). |
| `#e3b950` | `globals.css:3483` | `pulse-meta--boost` text; production tuned. |
| `#9bc4d9` | `globals.css:324` | `pill--processing` text; tuned vs `--color-linear-sky`. |

**Violation example** (from a hypothetical bad diff):
```tsx
// apps/transcribe-md/src/components/foo.tsx
<div style={{ background: '#08090a', color: '#f7f8f8' }}>
```

**Correct.** Use the Tailwind v4 utility (preferred) or the CSS var:
```tsx
// Tailwind utility — auto-generated from @theme block
<div className="bg-linear-bg text-linear-text">
// or, when an inline style is unavoidable
<div style={{ background: 'var(--color-linear-bg)', color: 'var(--color-linear-text)' }}>
```

**Canonical example.** `apps/transcribe-md/src/app/globals.css:111–121` —
the body baseline references `var(--color-linear-bg)` + `var(--color-linear-text)`,
never the underlying hex.

### `TOKEN-002` — BLOCK — Banned color values (Round-1 mockup regression class)

**Trigger.** Any in-scope file references one of the explicitly-retired
mockup values:

| Banned value | Why banned | Production replacement |
|---|---|---|
| `#9eb5a0` (or `rgb(158, 181, 160)` / matching rgba triplets) | Round-1 mockup sage; off by 36/15/-20 in RGB from production sage | `var(--color-linear-sage)` = `#7AA68C` = `rgb(122, 166, 140)` |
| `#050607` (or matching rgb) | Round-1 mockup background; differs from production canvas | `var(--color-linear-bg)` = `#08090a` |

The match is hex-exact (case-insensitive) on the value, AND on the
matching rgb/rgba triplets — `(158, 181, 160, X)` is the alpha-variant
of `#9eb5a0`; `(5, 6, 7, X)` is the alpha-variant of `#050607`. Both
forms emit BLOCK.

**Why a separate rule (not a TOKEN-001 footnote).** TOKEN-001 catches
*drift* — hardcoded production values where a token would be cleaner.
TOKEN-002 catches *regression* — values that were explicitly retired
in Phase 5 Linear V1 because they paint visibly-wrong sage/canvas. The
operator action is different: TOKEN-001 invites a refactor; TOKEN-002
blocks merge until reverted. Keeping them as one dual-tier rule
obscures that.

**Provenance of the banned list.** See
`_design-references/quillmd-design-tokens.md` "BANNED-VALUE LEAK CHECK"
section. Both values originated in Round-1 mockup attempts that used
different palettes than production; the post-merge audit caught and
documented them. Future banned values (if any are retired in a Phase
6+ palette migration) get appended here in the same shape.

**Violation:**
```css
/* anywhere under apps/transcribe-md/** or apps/marketing/** */
.foo { color: var(--color-linear-sage, #9eb5a0); }       /* fallback wrong sage */
.bar { background: rgba(158, 181, 160, 0.08); }          /* alpha-variant of #9eb5a0 */
```

**Correct:**
```css
.foo { color: var(--color-linear-sage, #7AA68C); }       /* fallback matches the var */
.bar { background: rgba(122, 166, 140, 0.08); }          /* production sage rgba */
/* or, preferred — drop the alpha-form for the named token */
.bar { background: var(--color-linear-sage-tint); }       /* declared at globals.css:74 */
```

**Real regression caught by this rule.** PR #176's first version landed
four `#9eb5a0` / `rgb(158, 181, 160)` hits in the new
`<style jsx>` block of `rx-warnings-rail.tsx` (lines 300, 311, 312, 313).
The auditor's first review pass surfaced them as BLOCK; the
amendment commit corrected them before merge. See
`samples/pr-176-sample-run.md`.

### `TOKEN-003` — WARN — Hardcoded font-family

**Trigger.** A literal `'Inter'`, `'JetBrains Mono'`, `'Source Serif'`,
`'Lora'`, etc. appears inside an in-scope file. `var(--font-sans)` and
`var(--font-mono)` are the only allowed expressions.

**Anti-pattern (real regression we shipped to mockups):** Loading Lora
serif in production app code. Production has been *Inter + JetBrains Mono
only* since Phase 5 Linear V1; serif fonts are explicitly retired
(`globals.css:14–19`).

**Violation:**
```css
.foo { font-family: 'Lora', Georgia, serif; }
```

**Correct.** Reference the token:
```css
.foo { font-family: var(--font-sans); }   /* Inter via next/font */
.bar { font-family: var(--font-mono); }   /* JetBrains Mono via next/font */
```

**Canonical example.** `apps/transcribe-md/src/app/layout.tsx:14–30` —
font wiring via `next/font/google`, exported as the `--font-sans` / `--font-mono`
CSS vars.

### `TOKEN-004` — NIT — Hardcoded spacing where Tailwind utility exists

**Trigger.** `padding: 14px 16px` or similar hardcoded spacing inside JSX
inline styles when a Tailwind utility (`px-4 py-3.5` etc.) covers the same
value. NIT-tier because production already does this in many places where
the surrounding context warrants explicit values (see
`globals.css:3372`, `qm-lin-soap-section-v6` padding) — judgement call.

**Note.** Inline pixel literals inside `.qm-lin-*` CSS classes in
`globals.css` are intentional (Linear V1 baseline). Don't flag those.

---

## 2 · React component patterns

Canonical references:
- **`apps/transcribe-md/src/app/visits/[id]/soap/SoapSection.tsx`** — display-only client component, status-pill class map pattern.
- **`apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx`** — severity-grouped client component with click-bubble guards + lifted modal state.
- **`apps/transcribe-md/src/app/visits/[id]/rx-tab.tsx`** — list + rail composition with `initialOverriddenIds` prop + local `Set<string>` state.

### `COMP-001` — BLOCK — Server-only import in a `'use client'` file

**Trigger.** A file with `'use client'` directive imports a module that's
provably server-only. The auditor recognises:
- `prisma` from `@meddoc/db` (Prisma client → DB connection → Node-only)
- anything from `@/lib/audit` (writes audit rows)
- anything from `@/lib/queue` (BullMQ → IORedis → Node-only)
- anything from `@/lib/minio` (server-side MinIO client)
- `next/headers`, `next/cache` (server-only Next APIs)
- `node:*` builtins (`fs`, `crypto`, `path` …)
- env reads matching `process.env.<X>` where `<X>` is NOT prefixed
  `NEXT_PUBLIC_` (see `BOUND-001` below)

**Why BLOCK.** Bundling these into the client breaks the build at best
(Next will warn) and leaks server secrets at worst.

**Violation:**
```tsx
'use client';
import prisma from '@meddoc/db';   // ⊗ server-only — breaks the client bundle
```

**Correct.** Move the data load into the server component (`page.tsx`) and
pass it as a prop, or wrap the access behind a server action (`'use server'`).
Reference: `apps/transcribe-md/src/app/visits/[id]/page.tsx` runs the
`prisma.rxWarningOverride.findMany` query and threads
`rxOverriddenWarningIds` to `<VisitReadyView>` — exactly this pattern.

### `COMP-002` — BLOCK — Server action without `'use server'`

**Trigger.** A function exported from `apps/transcribe-md/src/actions/**`
or `apps/transcribe-md/src/server-actions/**` that is invoked as a Next
server action (called from a client component, mutates Prisma) without
`'use server'` at the top of the file (or at the function head for
single-action exports).

**Why BLOCK.** Without the directive, Next bundles the function into the
client; it stops being a server action and starts being a client function
that fails on Prisma.

**Violation:**
```ts
// apps/transcribe-md/src/actions/visits.ts
import prisma from '@meddoc/db';
export async function deleteVisit(id: string) { … }   // ⊗ no directive
```

**Correct:**
```ts
'use server';
import prisma from '@meddoc/db';
export async function deleteVisit(id: string) { … }
```

**Canonical example.** Every file under `apps/transcribe-md/src/actions/`
opens with `'use server'`. Spot-check
`apps/transcribe-md/src/actions/visits.ts:1`,
`apps/transcribe-md/src/actions/soap.ts:1`,
`apps/transcribe-md/src/actions/auth.ts:1`.

### `COMP-003` — WARN — Status-pill class map pattern

**Canonical reference.** `apps/transcribe-md/src/app/visits/[id]/soap/SoapSection.tsx:65–69`:

```ts
const STATUS_PILL_CLASS: Record<SoapSectionStatus, string> = {
  drafted: 'qm-lin-pill--draft',
  reviewed: 'qm-lin-pill--sage',
  signed: 'qm-lin-pill--signed',
};
```

**Trigger.** A new component renders a status-shaped enum (`'drafted' | 'reviewed' | …`)
via inline `if/else` or `switch` on the JSX class string, instead of declaring
a `Record<EnumType, string>` map at the module top.

**Why WARN.** The map pattern is exhaustive (TS errors when enum grows)
and keeps the JSX clean. Inline switches drift over time.

**Violation:**
```tsx
<span className={`qm-lin-pill ${
  status === 'drafted' ? 'qm-lin-pill--draft' :
  status === 'reviewed' ? 'qm-lin-pill--sage' :
  status === 'signed' ? 'qm-lin-pill--signed' : ''
}`}>
```

**Correct.** Extract the map to module scope; index it in the JSX:
```tsx
<span className={cn('qm-lin-pill', STATUS_PILL_CLASS[status])}>
```

### `COMP-004` — WARN — Custom CSS where a `qm-lin-*` utility applies

**Trigger.** A `<style jsx>` block, a CSS module, or a Tailwind arbitrary
value (`bg-[#0d0e10]`, `border-[1px_solid_rgba(255,255,255,0.05)]`)
re-implements a primitive that already exists in `globals.css` as a
`qm-lin-*` utility. The auditor's lookup is the set of class names declared
in `globals.css`.

**Why WARN.** Custom styles drift from production tokens; the centralised
utility evolves with the design system, the inline override does not.

**Allowlist.** `RxWarningsRail.tsx:273–316` ships a `<style jsx>` block for
two classes (`.qm-warn-action`, `.qm-warn-override-btn`,
`.qm-warn-overridden`) that are *intentionally* component-scoped — the
production decision is documented in the file's header comment. Treat
matches against those three classes as ALLOW.

### `COMP-005` — NIT — Click-bubble guard on nested actionable elements

**Canonical reference.** `apps/transcribe-md/src/app/visits/[id]/rx-tab.tsx:349`
(and parallel sites at
`apps/transcribe-md/src/app/admin/threats/_components/ResolveModal.client.tsx:71`,
`apps/transcribe-md/src/app/admin/hipaa/_components/AdminHipaa.client.tsx:457`):

```tsx
<button … onClick={(e) => e.stopPropagation()}>
```

**Trigger.** A `<button>` or actionable child element nested inside a
parent that *also* carries `onClick` (typically a row that focuses
something on click) without an explicit `e.stopPropagation()` on the inner
handler.

**Why NIT.** Without the guard, the override-button click would also focus
the Rx row — intent-collision bug. Production code has the pattern; new
code should follow.

### `COMP-006` — WARN — Heavy comment header missing on new component

**Canonical reference.** `apps/transcribe-md/src/app/visits/[id]/soap/SoapSection.tsx:1–19`,
`apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx:1–30`. Both
open with a 10–25 line `// ============================` comment block that
states (a) what the component is, (b) which Phase / mockup it implements,
(c) any non-obvious wire-up notes.

**Trigger.** A *new* `*.tsx` or `*.ts` file ≥80 lines under
`apps/transcribe-md/src/**` or `apps/marketing/src/**` whose first line is
not a comment block ≥6 lines OR doesn't reference its mockup / spec / PR
number.

**Why WARN.** QuillMD's velocity depends on multi-Claude-session
hand-off; the comment-block convention is how prior decisions survive.
This is a hygiene rule, not a correctness rule, so WARN — but new files
that skip it consistently bleed institutional memory.

---

## 3 · Prisma / schema rules

Canonical reference: **`packages/db/prisma/schema.prisma`** (2114 lines as
of `cefb2be`).

### `SCHEMA-001` — BLOCK — Model mutating PHI without audit row at call site

**Definition of "PHI mutation".** Any `prisma.<model>.{create,update,delete,upsert}`
call where `<model>` is one of:
`Patient`, `Document`, `TranscribeMdPatient`, `TranscribeVisit`,
`Allergy`, `Medication`, `Appointment`, `VisitDelivery`,
`RxWarningOverride`, `User` (when the mutated field set includes anything
in the PHI-adjacent allowlist below).

**Trigger.** A diff that introduces a new call from the above set without
an accompanying `logAudit({ action, … })` from `@/lib/audit` either
in the same function body or in a transactional wrapper.

**Why BLOCK.** §164.312(b) requires audit-log mechanisms for activity in
PHI systems; Round-3 PR-D + the QA-agent v3.2 deep walks closed three
real audit-row gaps that had this exact shape. We've paid this tuition
already.

**Boundary with HIPAA Compliance Auditor.** This rule checks **pattern
presence** — was an audit call written in the same code path? The HIPAA
Auditor (when active) checks **runtime correctness** — does the call
actually emit a row, does it populate the right columns, is the action
in the enum? Both fire on the same gap; this one fires at PR time, that
one fires at audit time. Don't merge them.

**Violation:**
```ts
// apps/transcribe-md/src/actions/patients.ts
export async function softDeletePatient(id: string) {
  await prisma.patient.update({ where: { id }, data: { deletedAt: new Date() } });
  // ⊗ no logAudit call — soft-delete is a PHI-touching action
}
```

**Correct:**
```ts
import { logAudit } from '@/lib/audit';
export async function softDeletePatient(id: string) {
  const updated = await prisma.patient.update({ where: { id }, data: { deletedAt: new Date() } });
  await logAudit({
    action: 'PATIENT_SOFT_DELETED',
    targetType: 'Patient',
    targetId: id,
    metadata: { changedFields: ['deletedAt'] },   // field NAMES, not values
  });
  return updated;
}
```

**Canonical example.** `apps/transcribe-md/src/lib/rx-warning-audit.ts`
(the override path) — see how `logAudit` is invoked alongside the
Prisma mutation.

### `SCHEMA-002` — BLOCK — New model missing required infrastructure fields

**Trigger.** A diff to `packages/db/prisma/schema.prisma` introduces a new
`model X { … }` and the model lacks any of:
- `id String @id @default(cuid())` (or equivalent primary key)
- `createdAt DateTime @default(now())` UNLESS the model is purely
  derivative (e.g. a join table OR an analytics aggregate).
- `practiceId String` + `practice Practice @relation(…)` for
  multi-tenant data (every PHI-bearing model must carry tenant; spot-check
  `Patient`, `Document`, `AuditLog` for the pattern).

**Why BLOCK.** Multi-tenancy + audit timing depend on these. Patterns are
established across all 21 production models; new ones diverging is a
real bug we've shipped before.

**Allowlist.** Pure-relation join tables (`@@unique([a, b]) @@id([a, b])`)
without their own identity may skip `id` + `createdAt`. The auditor
recognises a join table by zero non-FK scalar fields plus a composite
primary key.

**Canonical example.** `schema.prisma:922–970` (`AuditLog`) — every required
field present, indexes for query patterns, `practiceId` mandatory with FK,
`@@map("audit_logs")` mapping to the SQL table name.

### `SCHEMA-003` — WARN — Model field naming convention

**Trigger.** New model field uses `snake_case` instead of `camelCase`,
OR the explicit `@@map` mapping to the underlying SQL column is missing
when the column name should be `snake_case` (production convention is
`camelCase` in TS / `snake_case` in SQL where readable; see how
`audit_logs`, `transcribe_visits`, `rx_warning_overrides` map).

**Why WARN.** Inconsistency leaks into raw SQL queries + audit reports.

### `SCHEMA-004` — NIT — Index hint on common query field

**Trigger.** A new field that's plausibly a query target (foreign key, status
enum, timestamp used for filtering) has no `@@index([field])`. NIT because
Prisma + Postgres autocreate indexes for FKs already; manual indexes are
for composite + filter columns.

**Canonical example.** `schema.prisma:968` — `@@index([userId, targetId, timestamp])`
composite for the "show me everything user X did to patient Y" query.

---

## 4 · BullMQ / pipeline patterns

Canonical references:
- **`apps/transcribe-md/src/lib/queue.ts`** — queue handles + idempotency.
- **`apps/transcribe-md/src/worker.ts`** — Worker entrypoint.
- **`apps/transcribe-md/src/worker/layers/01-transcribe.ts`** — primary-fallback transcription path (Deepgram → Whisper).

### `QUEUE-001` — BLOCK — New `Queue` without DLQ wiring

**Trigger.** A diff that introduces a new `new Queue(...)` (or
`getXQueue` factory) under `apps/transcribe-md/src/lib/**` without a
parallel DLQ queue or without subscribing the worker side to the
`failed` event with `enqueueDlq`-shaped behaviour.

**Why BLOCK.** PR-L (clinical-resilience) explicitly added DLQ wiring to
every queue + a worker healthcheck on the DLQ depth (`POST_MERGE_TODO §24.L`).
Adding a queue without DLQ regresses that closure.

**Canonical example.** `apps/transcribe-md/src/lib/queue.ts:45–66` — main
queue + `dlqQueue` declared in the same module; `worker.ts` failure handler
calls `enqueueDlq(payload, err)`.

### `QUEUE-002` — BLOCK — Job enqueue without idempotency key

**Trigger.** A `queue.add(jobName, payload)` call without an explicit
`{ jobId }` option, OR with a `jobId` that includes `Date.now()` /
millisecond precision (which defeats BullMQ's dedupe).

**Why BLOCK.** T-M16.4 fix: triple-clicking upload was enqueueing three
identical jobs because `jobId: visit-${id}-${Date.now()}` gave a unique
ID per millisecond. Production now uses per-minute-bucket suffix —
`apps/transcribe-md/src/lib/queue.ts:103–110` (the `enqueueProcessVisit`
helper bakes the per-minute floor and routes both initial + retry
through it).

**Violation:**
```ts
await queue.add('process_visit', payload, { jobId: `visit-${id}-${Date.now()}` });
```

**Correct.** Reuse `enqueueProcessVisit(visitId, userId)` (which bakes in
the per-minute idempotency); for a new queue, mirror the pattern:
```ts
const minute = Math.floor(Date.now() / 60_000);
const jobId = `mything-${id}-${minute}`;
```

### `QUEUE-003` — WARN — Layer with no skip-state handling

**Trigger.** A new layer file added under
`apps/transcribe-md/src/worker/layers/**` without referencing
`layer-skip.ts`'s `isLayerComplete` / `logSkippedLayer` helpers, OR
without a check on the `LayerSkipState` parameter.

**Why WARN.** Pipeline retries shouldn't redo expensive layers (Deepgram,
Anthropic) that already wrote their output. Production layers all skip
when their database fingerprint exists; new layers that skip this pattern
double API costs on retry.

**Canonical example.** `apps/transcribe-md/src/worker.ts:54–61` imports
the helpers; layers like `04-generate-soap.ts` use them at the top.

---

## 5 · Server / client boundary

### `BOUND-001` — BLOCK — Bare `process.env.<NON_PUBLIC>` in a `'use client'` file

**Trigger.** A `'use client'` file references `process.env.SOMETHING` where
`SOMETHING` is NOT prefixed `NEXT_PUBLIC_`.

**Why BLOCK.** Next inlines `NEXT_PUBLIC_*` into the client bundle; bare
secrets get inlined too, leaking them to the browser. We've shipped this
shape historically; PR-J's input-validation hardening flagged it as a
class to monitor.

**Allowlist.** Reading `process.env.NODE_ENV` is fine (the bundler
substitutes it pre-bundle).

**Canonical example.** `apps/transcribe-md/src/lib/email-enabled.ts` ships
the `isEmailDeliveryEnabled()` helper for client-callable env shape; client
components read the boolean, not the env directly.

### `BOUND-002` — WARN — `'use server'` action doing CPU-heavy work without queue

**Trigger.** A `'use server'` action that calls a known-heavy module
(Anthropic SDK, Deepgram SDK, the worker layers) directly inline.

**Why WARN.** Server actions hit the web container's request thread; long
work belongs in the worker. `actions/visits.ts:retryVisit` enqueues a
BullMQ job rather than running the pipeline inline — that's the model.

### `BOUND-003` — NIT — Missing `server-only` import

**Trigger.** A file in `apps/transcribe-md/src/lib/**` that exports a
function calling `prisma` (or another server-only resource) without
`import 'server-only';` at the top. NIT because the runtime path almost
always catches the boundary anyway via `'use client'`/`'use server'` chain
analysis; the explicit import is defense-in-depth.

---

## 6 · Folder layout / co-location

### `LAYOUT-001` — BLOCK — Cross-app import into `apps/meddoc-pro/**`

**Trigger.** Any diff line under `apps/transcribe-md/**` or
`apps/marketing/**` that `import`s from `apps/meddoc-pro/**` or from a
package known to be meddoc-pro-specific.

**Why BLOCK.** `meddoc-pro` is decommissioned (POST_MERGE_TODO §21);
new transcribe-md / marketing code must not depend on it. This rule
also fires at SCOPE-001 if the auditor sees any direct edit to
`apps/meddoc-pro/**` (the entire app should be eligible for delete).

### `LAYOUT-002` — WARN — Test file not co-located OR not in `__tests__/`

**Trigger.** A new `*.test.ts` / `*.test.tsx` file lives in a path that
matches neither convention production uses:

| Pattern | Where used |
|---|---|
| `foo.test.ts` next to `foo.ts` | `worker/error-categorize.test.ts`, `worker/retry-decision.test.ts`, `lib/email-auto-confirm.test.ts`, `lib/deepgram-vocabulary.test.ts` |
| `__tests__/foo.test.ts` (subdir) | `lib/__tests__/dose-range.test.ts`, `lib/em-coding/__tests__/score.test.ts`, `lib/em-coding/__tests__/corpus.test.ts` |

**Why WARN.** Both patterns are alive in production; pick one per dir.
Tests in `apps/transcribe-md/tests/` (top-level) are E2E only — that's a
different signal.

### `LAYOUT-003` — NIT — Component file not in conventional location

**Trigger.** A new client component lives outside the established folders:

| Folder | Convention |
|---|---|
| `app/**/page.tsx`, `layout.tsx`, `loading.tsx`, `not-found.tsx`, `error.tsx` | Next.js conventional file names |
| `app/**/<feature>-tab.tsx` | Tab-shaped subpanels (codes-tab, rx-tab, transcript-tab, extras-tab) |
| `app/**/<verb>-<noun>.tsx` | Action panels (sign-and-send-modal, edit-draft-dialog, copy-section-button) |
| `components/<domain>/**` | Cross-page reusables (`components/visits/CodingRail.tsx`, `components/rx/override-confirm-modal.tsx`) |
| `components/ui/**` | Visual primitives (`app-frame`, `icon`, `avatar`, `top-nav`, `quill-logo`, `spec-chip`) |

**Why NIT.** Production has hairline drift here already (PascalCase vs
kebab-case file names appear inconsistently — `CodingRail.tsx` lives next
to `BumpModal.tsx` but `rx-tab.tsx` is kebab). Don't BLOCK on file-name
casing; flag location category mismatches only.

---

## 7 · Scope guards

### `SCOPE-001` — BLOCK — Diff modifies `apps/meddoc-pro/**`

**Trigger.** Any line of the diff is under `apps/meddoc-pro/**`.

**Why BLOCK.** Per memory + POST_MERGE_TODO §21: meddoc-pro is
legacy-pending-deletion. New code must not extend it; deletions to it are
welcome but should land as a separate dedicated PR (so the auditor itself
doesn't get bypassed on the deletion PR).

### `SCOPE-002` — BLOCK — Cross-app symbol import

**Trigger.** An import from `apps/transcribe-md/**` to `apps/marketing/**`
or vice versa. Shared code lives in `packages/**` (e.g. `@meddoc/db`,
`@meddoc/ai`, `@meddoc/shared`).

**Why BLOCK.** Apps are independently deployable; cross-imports defeat
that. Move the shared symbol to a `packages/*` workspace.

---

## 8 · Documentation hygiene (NIT-tier only)

These are advisory; the auditor reports them but never blocks merge.

### `DOC-001` — NIT — TODO/FIXME without ticket reference

**Trigger.** A new `TODO`, `FIXME`, or `XXX` comment in a *.ts/*.tsx file
that doesn't reference an issue / PR / `POST_MERGE_TODO §X`. Production
convention: every TODO points somewhere actionable.

### `DOC-002` — NIT — Ambient comment claiming "// removed"

**Trigger.** A comment that says "// removed", "// deprecated — keep for
back-compat", or similar without a delete-by date or ticket. These rot.

---

## 9 · Accessibility (axe-core-aligned)

> **Added v1.1 (2026-05-10).** Each rule is keyed to a specific
> `axe-core` rule ID so failures translate 1:1 to the CI a11y job's
> `aria-*-name` / `*-attr` checks that QuillMD already runs on every
> PR. Pre-commit catch lets the auditor block the diff at PR-open
> time instead of waiting for the 3-minute Playwright a11y sweep.

Canonical references:
- **`apps/transcribe-md/src/app/visits/[id]/processing-typewriter.tsx:425–432`** —
  `role="progressbar"` with proper `aria-label` / valuemin / valuemax /
  valuenow / valuetext (the post-PR-#180 baseline).
- **`apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx:142–152`** —
  warning rows carry `role="alert"` + a `data-rxid` chip + an
  inner heading; the click-to-focus handler propagates Rx ID to
  parent state.
- **`apps/transcribe-md/src/components/visits/CodingRail.tsx`** — bump
  CTA + override controls; reference for accessible-name patterns
  on action buttons.

### `A11Y-001` — BLOCK — `aria-progressbar-name` (axe-core 4.10)

**Trigger.** A `*.tsx` file under `apps/transcribe-md/**` or
`apps/marketing/**` adds OR modifies an element with
`role="progressbar"` (or the native `<progress>` element) **without
any of:**
- `aria-label="..."` (non-empty literal)
- `aria-labelledby="<id>"` pointing to a non-empty element in the same render
- `title="..."` (non-empty literal)

**Why BLOCK.** This is the exact regression that PR #180 closed —
the SOAP processing screen shipped (PRs #172–#175) with a fully-named
*value* (`aria-valuemin`/`aria-valuemax`/`aria-valuenow`/`aria-valuetext`)
but no *name*. Axe flagged it serious; CI a11y job blocked every
downstream PR for ~4 days until #180 added the missing aria-label.
At PR-open time the auditor would have caught this in <1 second
instead of waiting for the 3-minute Playwright sweep.

**Violation:**
```tsx
<div
  className="qm-tw-segments"
  role="progressbar"
  aria-valuemin={0}
  aria-valuemax={6}
  aria-valuenow={4}
  aria-valuetext="Phase 4 of 6: Drafting"
>
```

**Correct.** Per `processing-typewriter.tsx:425–432`:
```tsx
<div
  className="qm-tw-segments"
  role="progressbar"
  aria-label="SOAP processing progress"   // ← required name source
  aria-valuemin={0}
  aria-valuemax={6}
  aria-valuenow={4}
  aria-valuetext="Phase 4 of 6: Drafting"
>
```

Allowed name sources are exactly the three documented at
https://dequeuniversity.com/rules/axe/4.10/aria-progressbar-name —
`aria-label`, `aria-labelledby` (non-empty target), or `title`.

### `A11Y-002` — BLOCK — `button-name` (axe-core 4.10)

**Trigger.** A `*.tsx` file adds OR modifies a `<button>` element (or
an element with `role="button"`) that has **no accessible name**.
The auditor checks for any of:
- Non-empty text-node child (e.g. `<button>Save</button>`)
- Non-empty `aria-label`
- `aria-labelledby` pointing to a non-empty element
- `title="..."` (non-empty literal)
- Single child `<img>` with non-empty `alt`
- Single child SVG with `<title>` element

**Why BLOCK.** A button with no accessible name is unannouncable —
screen readers read "button" with no further context. Common
regression in icon-only buttons where the developer dropped the
text but forgot the `aria-label`.

**Violation:**
```tsx
<button onClick={handleClose}>
  <Ic.x width={14} height={14} />
</button>
```

**Correct (any of):**
```tsx
<button onClick={handleClose} aria-label="Close">
  <Ic.x width={14} height={14} aria-hidden />
</button>

// or if the icon library supports semantic titles:
<button onClick={handleClose}>
  <Ic.x width={14} height={14} title="Close" />
</button>
```

**Canonical example.** `apps/transcribe-md/src/app/visits/[id]/rx-tab.tsx:349`
— icon-only override button uses `aria-label`. Same pattern in
`CodingRail.tsx`'s bump CTA.

### `A11Y-003` — WARN — `aria-label-on-interactive` (best-practice)

**Trigger.** A `*.tsx` file adds OR modifies an element that's NOT a
`<button>` / `<a>` / `<input>` but carries an interactive role
(`role="button"`, `role="link"`, `role="tab"`, `role="menuitem"`,
`role="checkbox"`, `role="switch"`, `role="option"`) AND has neither
`aria-label` nor a non-empty visible text child.

**Why WARN.** The element is technically findable by axe-core's
button-name rule when role="button" is the case, but A11Y-002 covers
the BLOCK-tier subset; this WARN catches the wider best-practice
cases (tabs, menu items, switches) where missing names are usually
silent — axe permits them in some configurations. WARN tier because
production code has occasional well-justified omissions (when the
parent label is announced via aria-labelledby or aria-describedby).

**Allowlist.** Element with `aria-labelledby` set to an element id
that is non-empty in the same render — already named through the
labelledby chain.

### `A11Y-004` — WARN — `aria-required-attr` (axe-core 4.10)

**Trigger.** A `*.tsx` file adds OR modifies an element with a
`role="..."` attribute and the role's WAI-ARIA spec **requires**
attributes that are missing. The auditor's required-attr table is
keyed off the axe-core rule of the same name; the table currently
covers the roles QuillMD actively uses:

| Role | Required attributes (per ARIA 1.2) |
|---|---|
| `progressbar` | `aria-valuenow` (or implicit-now via `aria-valuetext`) |
| `slider` | `aria-valuenow` |
| `combobox` | `aria-expanded` |
| `scrollbar` | `aria-controls`, `aria-valuenow` |
| `option` | (no required attrs at the role level — listbox parent enforces) |
| `radio` | `aria-checked` |
| `checkbox` | `aria-checked` |
| `switch` | `aria-checked` |

**Why WARN.** A missing required attribute usually still renders;
axe flags it serious-tier in some cases and moderate in others
depending on context. Treating as WARN keeps the auditor's BLOCK
list focused on regressions that *break* a11y at runtime
(A11Y-001/002), while still calling out the spec compliance gap
for the author to address.

**Violation:**
```tsx
<div role="progressbar" aria-label="Loading">  {/* no aria-valuenow */}
```

**Correct:**
```tsx
<div role="progressbar" aria-label="Loading" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
```

---

## Rule taxonomy summary

| Category | BLOCK | WARN | NIT | Total |
|---|---|---|---|---|
| Design tokens | 1 | 2 | 1 | 4 |
| React component patterns | 2 | 3 | 1 | 6 |
| Prisma / schema | 2 | 1 | 1 | 4 |
| BullMQ / pipeline | 2 | 1 | 0 | 3 |
| Server / client boundary | 1 | 1 | 1 | 3 |
| Folder layout | 1 | 1 | 1 | 3 |
| Scope guards | 2 | 0 | 0 | 2 |
| Documentation hygiene | 0 | 0 | 2 | 2 |
| Accessibility (v1.1) | 2 | 2 | 0 | 4 |
| **Totals** | **13** | **11** | **7** | **31 rules** |

## Stale-rule guard

Each rule's `canonical_ref` line is dereferenced at agent run-start. If
the file or line range named has moved (file deleted, line range no
longer matches the documented anchor), the rule emits one
`RULE_STALE` BLOCK against the *auditor itself* (not against the diff
under review) before any other rule runs. The fix is always: re-anchor
the rule by editing this file. Never silently drop a rule.

The intent is that this rule library lives forever in step with the
canonical references — a refactor that moves `SoapSection.tsx`
forces this file to be updated in the same PR, which the auditor will
self-flag if forgotten.
