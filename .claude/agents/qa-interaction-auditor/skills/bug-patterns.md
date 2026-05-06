# Bug patterns — taxonomy with real examples

This file is the agent's bug-pattern reference. Every pattern below
was a real production bug in the QuillMD codebase. The verbatim
code excerpts are the EXACT lines that were buggy — included so
future runs can pattern-match against the same shapes elsewhere.

## Pattern A — Orphan event dispatcher

**What it looks like:** a button's `onClick` calls
`window.dispatchEvent(new CustomEvent('qm:something', ...))`. No
component anywhere in the codebase calls
`window.addEventListener('qm:something', ...)`. The event vanishes
into the void; the user sees nothing happen.

### Real example (PR #132 / commit `42357d6`)

The "Confirm 99213 · sign" button on the visit-detail page. Pre-fix
verbatim from `apps/transcribe-md/src/components/visits/CodingRail.tsx`:

```tsx
<button
  type="button"
  className="qm-lin-coding-confirm"
  onClick={() => {
    // Confirm-and-sign is owned by the existing Sign & Send flow; we
    // emit a custom event for the page to wire up to the existing
    // SignAndSendModal trigger. UNTOUCHED behaviour preserved.
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('qm:request-sign', { detail: { visitId } })
      );
    }
  }}
>
  <span>Confirm {displayedCode} · sign</span>
</button>
```

`grep -rn "qm:request-sign" apps/transcribe-md/src/` returned ONE
match — the dispatcher itself. **No listener existed.** The button
had been "working" in code review for weeks because the failure was
silent.

### Detection grep

Two greps; diff produces orphans.

```bash
# 1. Bare-string events
grep -rEhn "new CustomEvent\(['\"](qm:[a-z-]+)" apps/*/src/ \
  | grep -oE "qm:[a-z-]+" | sort -u > /tmp/dispatched-bare.txt

grep -rEhn "addEventListener\(['\"](qm:[a-z-]+)" apps/*/src/ \
  | grep -oE "qm:[a-z-]+" | sort -u > /tmp/listened-bare.txt

# 2. Constant-named events (the codebase has both styles)
grep -rEhn "_EVENT = '(qm:[a-z-]+)'" apps/*/src/ packages/ \
  > /tmp/event-constants.txt
# Then resolve dispatchEvent(CONSTANT_NAME) and
# addEventListener(CONSTANT_NAME) for each declared constant.

# 3. Diff
comm -23 /tmp/dispatched-bare.txt /tmp/listened-bare.txt
# Anything that prints is an orphan.
```

### Known event constants (as of commit `42357d6`)

`packages/...` exports — agent must resolve symbol → string before
diffing:

- `SOAP_EDITED_EVENT = 'qm:soap-edited'`
  (`apps/transcribe-md/src/lib/em-coding-ui/types.ts:152`)
- `SOAP_HIGHLIGHT_CRITERIA_EVENT = 'qm:soap-highlight-criteria'`
  (`apps/transcribe-md/src/lib/em-coding-ui/types.ts:160`)
- `EM_OVERRIDE_EVENT = 'qm:em-override'`
  (`apps/transcribe-md/src/lib/em-coding-ui/types.ts:169`)
- `SOAP_JUMP_EVENT = 'qm:soap-jump'`
  (`apps/transcribe-md/src/lib/em-coding-ui/types.ts:177`)

**Active orphans as of this build (caught by the agent's smoke
test — bonus findings, NOT yet fixed):**

- `EM_OVERRIDE_EVENT` is dispatched at `CodingRail.tsx:226` — no
  listener. (Same pattern as the original Bug A.)
- `SOAP_HIGHLIGHT_CRITERIA_EVENT` is dispatched at
  `BumpCtaButton.tsx:61` — no listener.
- `qm:em-boost-hints` is listened at `soap-editor.tsx:117` — no
  documented dispatcher in the agent's grep window. Worth a deeper
  read.

## Pattern B — Prop-not-passed "pretend success" fallback

**What it looks like:** a component takes an optional callback prop
(typed `onSomething?: () => Promise<...>`). The component's internal
handler checks if the prop is provided, calls it if so, and returns
`{ ok: true }` if not. The render site **never passes the prop**, so
the fallback always runs. The user sees the modal close, the
"success" toast fires, the doctor moves on — but nothing persisted.

### Real example (PR #132 / commit `42357d6`)

The BumpModal's "Apply & save" button. Pre-fix verbatim from
`apps/transcribe-md/src/components/visits/CodingRail.tsx:233-249`:

```tsx
const handleApplyAdditions = useCallback(
  async (additions: Array<{ criterionId: string; text: string }>) => {
    if (onApplyAdditions) {
      const result = await onApplyAdditions(additions);
      if (result.ok && score.bump) {
        onBumpAccepted?.(score.bump.toCode);
      }
      return result;
    }
    // Standalone-build fallback — no backend wiring; pretend success so the
    // mockup state still flows. Subagent B's merge replaces this path.
    if (score.bump) onBumpAccepted?.(score.bump.toCode);
    return { ok: true };
  },
  [onApplyAdditions, onBumpAccepted, score.bump]
);
```

The render site at `soap-editor.tsx:200` was:

```tsx
<CodingRail
  emScore={initialScore}
  visitId={visitId}
  readonly={isReadonly}
/>
```

No `onApplyAdditions={...}`. Fallback always fired. Doctor's edits
NEVER hit the database. Re-opening the modal showed the original
suggestions because nothing had been persisted.

### Detection grep

Two-step. First find optional-callback shapes; then find render
sites that omit the prop.

```bash
# Step 1: optional async callbacks shaped like persistence hooks
grep -rEn "on[A-Z][a-zA-Z]+\?:.*Promise<\{.*ok:" apps/*/src/ \
  --include='*.tsx' --include='*.ts'
# Each match names the prop (e.g. `onApplyAdditions`).

# Step 2: for each prop name, find render sites that omit it
# Manual review — no clean grep. Use `<ComponentName ` and check
# the JSX block for the prop. Or use AST walk via tsx parser.
```

### Stub-comment markers (real strings from the original bugs)

The agent's grep should flag any of these — they're documented
deferrals that often outlive the deferral:

- `"UNTOUCHED behaviour preserved"`
- `"Subagent .* merge replaces"` (regex — `Subagent A`, `Subagent B`,
  etc.)
- `"Standalone-build fallback"`
- `"pretend success"`
- `"wire up to the existing"`
- `"When backend wiring is incomplete"`
- `"When unwired"`
- `"TODO.*wire"`, `"TODO.*hook"`, `"FIXME.*wire"`, `"XXX.*wire"`

Combined grep:

```bash
grep -rEn "UNTOUCHED behaviour preserved|Subagent .* merge replaces|Standalone-build fallback|pretend success|wire up to the existing|When backend wiring is incomplete|When unwired|TODO.*\bwire\b|TODO.*\bhook\b|FIXME.*\bwire\b|XXX.*\bwire\b" \
  apps/transcribe-md/src/ apps/marketing/src/ packages/ 2>/dev/null
```

### Known false-positive shape

A passing comment that *describes* a fix can match the negative-
form ("no more pretend success", "we used to use this stub
fallback"). The agent should read 3 lines of surrounding context
before flagging. Comments inside a `// no more` / `// previously`
clause are not bugs.

Example as of commit `42357d6`: the post-fix CodingRail comment
documents the rule:

```tsx
// sees an error and stays open — no more silent "pretend success"
// fallback (that was the bug we shipped this PR to fix).
```

This should NOT flag. The `no more` qualifier indicates description,
not deferral.

## Pattern C — Parser/renderer mismatch

**What it looks like:** a backing column in the database has
content, but the renderer parses it with a regex that doesn't match
the content's structure. Result: section bodies render empty
("Subjective section is empty" × 4) while the actual content sits
unread in `soapDraft` / `soapFinal`.

### Real example (kasra smoke-test visit `cmorjcv0i...`)

Doctor uploaded a non-clinical recording (a solicitor's medico-legal
witness statement, not a doctor-patient encounter). The pipeline
correctly detected this:
- L4 produced a SOAP with `## Subjective / Objective / Assessment / Plan`
- L5 critique flagged: "This transcript is not a clinical encounter"
- L6 polish OBEYED the critique and rewrote `soapFinal` as a
  refusal banner + "Abstraction of Third-Party Medico-Legal /
  Witness Statement" structure with NO canonical S/O/A/P headings

The UI parser at `apps/transcribe-md/src/lib/parse-soap-sections.ts`:

```typescript
export function parseSoapSections(markdown: string): SoapSection[] {
  // ...
  const lines = markdown.split('\n');
  let current: SoapSectionKey | null = null;
  for (const raw of lines) {
    const m = /^\s{0,3}#{1,3}\s+(.+?)\s*$/.exec(raw);
    if (m) {
      const heading = m[1].toLowerCase().replace(/[^a-z]/g, '');
      const found = ORDER.find((o) => o.alts.includes(heading));
      // ORDER alts = [['subjective','s'], ['objective','o'], …]
      if (found) {
        current = found.key;
        continue;
      }
    }
    // ...
  }
  // returns 4 sections; bodies are '' when no canonical heading matched
}
```

`soapFinal` had `## Abstraction of Third-Party...` — strips to
`abstractionofthirdpartymedicolegalwitnessstatement`, no match in
ORDER → all 4 bodies returned empty → renderer emitted "section
is empty" four times. The actual refusal banner sat in the column
but was never displayed.

### Detection — content-vs-render diff

For each parser-backed surface (SOAP sections, Rx warnings, ICD
codes, audit log entries, patient-summary HTML), the agent runs:

```bash
# 1. Pull the column verbatim from the DB
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tA -c "
  SELECT \"soapFinal\" FROM transcribe_visits WHERE id = '<VISIT_ID>';
"

# 2. Render the page in headless Chromium, snapshot the DOM
node /path/to/scripts/sweep-visit-page.mjs --visit <VISIT_ID> --section soap

# 3. Diff: column has >100 chars + DOM shows "is empty" = mismatch
```

The Playwright walk in `scripts/sweep-visit-page.mjs` checks every
section block on every page. If a section's backing column is
non-empty AND the DOM shows the empty-state copy, that's a Pattern C
finding.

### Known empty-state copy strings

(So the agent recognises "this is the empty-state, not real content"):

- `"Subjective section is empty"` /
  `"Objective section is empty"` /
  `"Assessment section is empty"` /
  `"Plan section is empty"`
  (`apps/transcribe-md/src/app/visits/[id]/soap/SoapSection.tsx`)
- `"No Rx drafts"` (Rx tab)
- `"No referrals"` (Referrals tab)
- `"No ICD codes"` (Codes tab)

The agent's content-rendering check looks for these exact strings
in the rendered DOM. When the corresponding DB column is non-null
+ non-trivial, that's a Pattern C bug.

## Pattern detection priority

When scanning a new page, run patterns in this order:

1. **Stub-comment grep** (cheapest, catches Pattern A + B
   pre-emptively before the browser walk)
2. **Orphan dispatcher diff** (cheap — pure grep + set diff)
3. **Optional-callback / render-site walk** (more expensive —
   AST-aware grep)
4. **Browser walk + DB diff** (most expensive — full Playwright)
5. **Parser-content-vs-DOM diff** (only on parser-backed surfaces;
   the agent doesn't run this on every element)

## When NOT to flag

Skip the following — they look bug-shaped but aren't:

- Comments that say `// previously…` / `// no more…` /
  `// pre-fix…` describing FIXED behavior
- Optional callbacks where the missing prop genuinely means
  "off" (e.g., `onPresenter` for a feature that's only used in
  presentation mode)
- Window events that are deliberately fire-and-forget (analytics
  beacons, telemetry — these often dispatch with no listener
  expected). Look for `analytics`/`telemetry`/`metric` in the
  event name or payload.
- E2E test code (`tests/automated/e2e/**`, `*.spec.ts`,
  `*.test.tsx`) — fixtures and mocks legitimately stub things out.

## Pattern D — Fixture / seed-script bugs that gate the agent itself

**What it looks like:** the seed script for the QA test user creates
a row that *technically* exists but is missing fields the auth flow
checks. The agent reports "login failed" on its first PASS B run, the
operator reads the form-level error message, fixes the seed script
in a follow-up PR. This is the most "agent-eats-its-own-dogfood"
class of bug — the agent's job is to find UX bugs, but if its own
fixture is broken, it can't get past the front door.

### Real example (PR #135 / 2026-05-06 — F-07 + F-08)

Pre-fix verbatim from `apps/transcribe-md/scripts/seed-qa-user.ts`
(the user.upsert payload — both branches missed two fields):

```ts
const user = await prisma.user.upsert({
  where: { email: QA_EMAIL },
  update: {
    passwordHash,
    role: 'DOCTOR',
    isActive: true,
    lockedUntil: null,
    failedLoginCount: 0,
    practiceId: PRACTICE_ID,
    specialty: 'family-medicine',
    timeZone: 'America/Los_Angeles',
    // F-07: emailVerified missing; login refuses with
    //       "Please verify your email before signing in."
    // F-08: products missing; login refuses with
    //       "This account is for MedDoc Pro, not TranscribeMD."
  },
  create: { /* same omissions */ },
});
```

The transcribe-md auth flow gates on:
1. `users.emailVerified !== null` (`apps/transcribe-md/src/actions/
   auth.ts` — verify-before-sign-in block)
2. `users.products` includes `Product.TRANSCRIBE_MD` (same file,
   line 213 — cross-app-redirect block)

A user row that satisfies neither was the equivalent of a seed
script that creates an account but locks it. The agent's first
PASS B run produced two findings + the operator fixed both in a
single seed-script patch.

### Detection — what to grep for

Seed scripts that create User rows and miss required-for-login
fields. Two greps:

```bash
# 1. Find every User upsert / create in scripts/
grep -rEn "prisma\.user\.(upsert|create)" \
  apps/*/scripts/ apps/meddoc-pro/scripts/ 2>/dev/null

# 2. For each match, check the payload for ALL of:
#    emailVerified, products, role, isActive, lockedUntil
# A missing emailVerified or products entry is a candidate;
# verify by checking the auth route's gates.
```

The agent's preventive grep on a new seed script:

```bash
# All required-for-login fields (transcribe-md)
for FIELD in emailVerified products role isActive; do
  if ! grep -qF "$FIELD" path/to/seed-script.ts; then
    echo "FINDING: seed missing '$FIELD'"
  fi
done
```

### Why this matters past the immediate bug

Every seed script that creates a User row is a candidate for the
same gap. A new `seed-staff-user.ts`, `seed-admin.ts`, etc. should
be auto-checked against this pattern. The QA agent's role is to
catch this once + write the regression test
(`tests/scripts/seed-qa-user.test.ts` for the QA fixture; future
seed scripts should mirror its `buildUserUpsertPayload` shape +
guard tests).

### Severity rubric for fixture-gap findings

- **P1** — fixture gap that gates an agent capability (login,
  visit creation, etc.). One-line fix in the seed script
  unblocks the agent permanently.
- **P3** — fixture gap that only affects niche test paths
  (specific role permutations, edge-case roles). Same shape but
  smaller blast radius.

Never **P0** unless the fixture gap exposes a product bug
(e.g. seed creates a user with `isActive: false` and the agent
discovers the inactive-user gate is broken — the seed-side bug
is then secondary to the product-side finding).
