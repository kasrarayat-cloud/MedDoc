# Code Quality Audit — PR #176

**Run:** 2026-05-09T21:35:00Z
**Input:** `gh pr diff 176 --repo kasrarayat-cloud/MedDoc` (560 lines, 5 files)
**Rule library:** `.claude/agents/code-quality-auditor/rules.md` @ `agent/code-quality-auditor-v1` head
**In-scope files:** 4 (1 dropped — `.claude/agents/qa-interaction-auditor/**` is out of scope for content rules)
**Findings:** 2 BLOCK · 1 WARN · 1 NIT

> **Note for reviewer:** PR #176 is the production-defect fix that wires the
> `RxWarningsRail` → `OverrideConfirmModal` bridge. Net pattern direction is
> *toward* convention (the PR closes a long-standing pattern gap). The two
> BLOCK findings are concentrated in the `<style jsx>` block at the tail of
> `rx-warnings-rail.tsx` and are the kind of regression this auditor is
> designed to catch — banned `#9eb5a0` color leaking into a fallback chain.

---

## BLOCK · 2 findings

### design-tokens · `TOKEN-001` · 2 findings

- **`apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx:518`** — Banned `#9eb5a0` color in CSS fallback chain.
  - Snippet: `outline: 2px solid var(--color-linear-sage, #9eb5a0);`
  - Canonical: `apps/transcribe-md/src/app/globals.css:70` declares `--color-linear-sage: #7AA68C;`
  - Why BLOCK: `#9eb5a0` is the **Round-1 mockup mistake** explicitly retired in
    Phase 5 Linear V1 — see `_design-references/quillmd-design-tokens.md`
    "BANNED-VALUE LEAK CHECK" section. Production sage is `#7AA68C`. If the
    CSS var ever fails to resolve (older browser, module load order quirk),
    the fallback paints the wrong sage.
  - Fix: replace fallback with `#7AA68C`:
    `outline: 2px solid var(--color-linear-sage, #7AA68C);`

- **`apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx:529–532`** — Banned `#9eb5a0` color + matching rgba derivatives in `.qm-warn-overridden` chip.
  - Snippet:
    ```css
    color: var(--color-linear-sage, #9eb5a0);
    background: rgba(158, 181, 160, 0.08);
    border: 1px solid rgba(158, 181, 160, 0.32);
    ```
  - Canonical: `apps/transcribe-md/src/app/globals.css:70` (`--color-linear-sage: #7AA68C` = `rgb(122, 166, 140)`).
  - Why BLOCK: triple violation — the var fallback is wrong sage, AND the rgba
    triplets `(158, 181, 160, …)` are derived from the wrong sage. The
    correct triplet is `(122, 166, 140, …)`. Production already uses
    `rgba(122, 166, 140, 0.13)` etc. across `globals.css` (e.g.
    `--color-linear-sage-tint`, `--color-linear-sage-glow`).
  - Fix: replace `#9eb5a0` with `#7AA68C`; replace `rgba(158, 181, 160, X)`
    with `rgba(122, 166, 140, X)`. Or — preferred — drop the inline rgba
    in favour of the existing `--color-linear-sage-tint` /
    `--color-linear-sage-glow` tokens:
    ```css
    color: var(--color-linear-sage-bright, #9bc4a8);
    background: var(--color-linear-sage-tint, rgba(122, 166, 140, 0.13));
    border: 1px solid rgba(122, 166, 140, 0.32);
    ```

---

## WARN · 1 finding

### React component patterns · `COMP-004` · 1 finding (sub-threshold; advisory)

- **`apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx:491–533`** — `<style jsx>` block introduces three new utility-shaped classes.
  - Snippet:
    ```tsx
    <style jsx>{`
      .qm-warn-action { … }
      .qm-warn-override-btn { … }
      .qm-warn-overridden { … }
    `}</style>
    ```
  - Canonical: `apps/transcribe-md/src/app/globals.css:575–608` (the `qm-warn-*` family).
  - Why WARN: production's `qm-warn-*` namespace lives entirely in `globals.css`.
    Adding three new `qm-warn-*` classes via `<style jsx>` makes them
    component-scoped, which means the theming system can't update them
    centrally if the danger / sage palettes ever shift. The PR header
    comment acknowledges this is a deliberate carve-out for this component;
    the auditor flags it as drift-warning (per `COMP-004` allowlist note),
    not BLOCK.
  - Fix path: file a follow-up to migrate these three classes into
    `globals.css` after PR #176 lands so the next round of `qm-warn-*`
    refactor catches them. Reasonable to ship as-is; capture as TODO in
    `POST_MERGE_TODO.md`.

---

## NIT · 1 finding

### Documentation hygiene · `DOC-001` · 1 finding

- **`apps/transcribe-md/src/app/visits/[id]/page.tsx:160–164`** — Comment mentions "Round 4" without a ticket / PR pointer.
  - Snippet:
    ```ts
    // Round 4 critical-Rx-override fix: pull existing override rows so
    // the rail can hydrate with ✓ Overridden chips on already-acknowledged
    // warnings. Visit-scoped + persisted, so reload + cross-tab don't
    // lose the doctor's progress through multiple critical warnings.
    ```
  - Why NIT: production convention is to reference `POST_MERGE_TODO.md §X`
    or a PR number when motivating non-obvious changes. "Round 4" is fine
    in conversation but ambiguous in code 6 months from now.
  - Fix hint: append `(PR #176)` to the comment header.

---

## Findings against the diff but no rule fired

- `apps/transcribe-md/src/app/visits/[id]/page.tsx:174–177` adds
  `prisma.rxWarningOverride.findMany` to the `Promise.all` batch. **Read,
  not mutation** → `SCHEMA-001` (audit-row presence) does NOT apply. PASS.
- `apps/transcribe-md/src/app/visits/[id]/rx-tab.tsx:235–260` lifts a
  `Set<string>` state via `useState` + `useCallback` for the merge
  handler. Mirrors the production state-management style. PASS.
- `apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx:212–215`
  adds the `e.stopPropagation()` click-bubble guard on the override-button
  container — `COMP-005` recognises this as the right pattern. PASS.
- The PR adds `rxLineNumber: number` as a proper field on `RailWarning`
  with comment explaining the choice (vs a parsing helper). Type-coupling
  cost is minimal; matches `COMP-003`-adjacent map-pattern intent. PASS.
- `apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx:1–30`
  comment header expanded to document the new override flow. `COMP-006`
  satisfied. PASS.
- The new modal mount block at `rx-warnings-rail.tsx:467–489` filters by
  `!readonly && !overriddenIds.has(w.id)` — defensive; doesn't render
  modals for warnings that don't need them. PASS.

---

## Summary

```
2 BLOCK · 1 WARN · 1 NIT against 4 in-scope files.
Rule library: 26 rules (10 BLOCK / 9 WARN / 7 NIT). Stale: 0.
```

**Merge gate.** Two BLOCK findings — both are the same `TOKEN-001`
violation (banned `#9eb5a0` Round-1 sage) in two locations of the same
file. **Fixing the two locations unblocks merge.** The WARN and NIT are
advisory.

**Reviewer sign-off note.** Once the `#9eb5a0` → `#7AA68C` fix lands, this
PR resolves a real production defect (doctor sees critical Rx warning →
hits Sign & Deliver → 422 toast → no UI path forward). The pattern net of
the PR is *toward* convention, not away — exactly the trajectory this
auditor wants to encourage.
