# Code Quality Audit — PR #180 (retro-run, v1.1 a11y rules)

**Run:** retroactive demonstration of `A11Y-001` firing on the
**pre-fix state** of `apps/transcribe-md/src/app/visits/[id]/processing-typewriter.tsx`.

**Input:** Reconstructed pre-#180 line range (the fix added a single
line: `+ aria-label="SOAP processing progress"` between the existing
`role="progressbar"` and `aria-valuemin={0}` at L425–L432).

**Rule library:** `.claude/agents/code-quality-auditor/rules.md` @ v1.1
(this PR adds the 4 A11Y rules; this sample documents A11Y-001's
expected firing on a real historical regression).

**Findings:** 1 BLOCK · 0 WARN · 0 NIT.

> **Why this sample matters.** PR #180's bug shipped in PRs
> **#172–#175** — the typewriter-SOAP processing screen had a
> `role="progressbar"` with full *value* annotation (`aria-valuemin`,
> `aria-valuemax`, `aria-valuenow`, `aria-valuetext`) but **no name**.
> Axe-core's `aria-progressbar-name` rule flagged it `serious`,
> blocking every downstream PR's CI a11y job for ~4 days until #180
> added `aria-label="SOAP processing progress"`. With v1.1 the
> auditor would have caught this in <1 second at PR-open time
> instead of waiting for the 3-minute Playwright sweep.

---

## BLOCK · 1 finding

### accessibility · `A11Y-001` · 1 finding

- **`apps/transcribe-md/src/app/visits/[id]/processing-typewriter.tsx:425–432`**
  (pre-PR-#180 state) — `role="progressbar"` element with no accessible name.
  - Snippet (pre-fix):
    ```tsx
    <div
      className="qm-tw-segments"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={VISIT_PHASES.length}
      aria-valuenow={Math.max(0, phaseIndex(displayPhase) + 1)}
      aria-valuetext={`Phase ${...} of ${...}: ${VISIT_PHASES[...].label}`}
    >
    ```
  - Canonical: `apps/transcribe-md/src/app/visits/[id]/processing-typewriter.tsx:425–432`
    (post-#180 baseline includes `aria-label="SOAP processing progress"`).
  - Why BLOCK: per `axe-core` 4.10
    [`aria-progressbar-name`](https://dequeuniversity.com/rules/axe/4.10/aria-progressbar-name),
    a `role="progressbar"` element MUST carry an accessible name via
    one of `aria-label` / `aria-labelledby` / `title`. The element had
    full *value* annotation but no *name*; screen readers announced
    "Phase 4 of 6: Drafting" with no preceding context (no "SOAP
    processing progress, ...").
  - Fix (the actual PR #180 fix):
    ```tsx
    <div
      className="qm-tw-segments"
      role="progressbar"
      aria-label="SOAP processing progress"   // ← required name source
      aria-valuemin={0}
      ...
    >
    ```
  - Diff scope of fix: 1 line added, 0 removed.

---

## WARN · 0 findings

(Under v1.1 rules, the post-fix state passes A11Y-002 / A11Y-003 /
A11Y-004 cleanly: the only `<button>` near this block is in a
sibling component with text content, and the progressbar's required
attrs — `aria-valuenow` — are present.)

---

## NIT · 0 findings

---

## Summary

```
Summary: 1 BLOCK · 0 WARN · 0 NIT against 1 file (pre-fix state of PR #180).
Rule library: rules.md @ v1.1 (31 rules; 13 BLOCK / 11 WARN / 7 NIT).
```

## Verification of A11Y-001's pattern-presence detection

- **Trigger evaluated against pre-fix snippet:** matches.
  - Element has `role="progressbar"` (literal string match on the
    role attribute).
  - Element lacks all three accepted name sources: no `aria-label`,
    no `aria-labelledby`, no `title`.
- **Trigger evaluated against post-fix snippet:** does not match.
  - `aria-label="SOAP processing progress"` is present and
    non-empty.
- **Allowlist coverage:** none — the rule has no allowlist (every
  progressbar needs a name; there's no "but this one is special"
  exception in production yet).

## Why this auditor catch is more valuable than the CI catch

The CI a11y job runs `npx playwright test --project=a11y` against a
fresh ephemeral Next.js server with a clean test DB and seeded
fixtures. End-to-end run time: ~3 minutes. The job has to bring up
infra, navigate to the route, capture the rendered DOM, and run
axe-core against it — for *every* PR.

The auditor catches the same regression by reading the diff statically
in <1 second. Pre-merge feedback shifts left from "CI failure 3
minutes after PR open" to "BLOCK shown in the PR review template at
draft time."

That ~3-minute saving compounds: PRs #172–#175 each waited on a
failing a11y run, plus PRs #176/#178/#179/#181 inherited the failure
through main. The total CI wall-clock cost across 8 affected PRs was
~24 minutes; auditor v1.1 collapses that to a handful of seconds at
each draft-PR time.
