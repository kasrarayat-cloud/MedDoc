> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **13 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## Shared components — diff the callers BEFORE you replace them

**A shared component must accept every context its predecessors carried.**
Before replacing per-caller code with one component, diff each call site's
props, params and query strings and check the new signature can express all of
them. Then the migration test asserts **both directions**: it carries the
context when given, and omits it when there is none.

Why this is written down: R4 spent a round on two defects that are the same
mistake in two shapes, both introduced by consolidations that were otherwise
right.

- **Context dropped.** R3.2 replaced `/patients/[id]`'s New-visit link — which
  carried `?patientId=…` — with the shared `RoundsNewVisitCta`, and that
  component hardcoded a bare `/visits/new`. On the one page where the patient is
  already known, the button dropped them into create-a-patient. ⚠️ **The
  empty-state link on the same page still worked**, so *"the patient page has a
  working New visit link"* was true and useless — a claim that survives a
  spot-check. **Fix (reference implementation): context as an optional prop**
  (`patientId`), swept across every entry point, with the test asserting the
  five surfaces that legitimately have no patient in scope still omit it. A
  component that appended a stale id everywhere would satisfy the positive
  assertion and be a worse bug.

- **Coverage assumed.** R3.4 wrapped ONE of `RxTab`'s **three** mount sites in
  the Rounds host and verified it there — correctly, and incompletely. The other
  two rendered the legacy cream panel on a Rounds route for two rounds.
  **Fix (reference implementation): the treatment lives ON the component**
  (`rx-tab.tsx`), not on its callers, so every present and future mount inherits
  it and the list cannot go stale.

The rule generalises: **a per-caller list is kept complete by hand, and hand-kept
lists are wrong eventually.** Put the behaviour where it cannot be forgotten —
on the component — and where that is impossible, make the missing case fail a
test rather than render quietly.

**Neither defect was visible to any sweep.** A class census finds classes; it
cannot see a missing query param or an unhosted third mount. If this shape
recurs, the answer is a contract test on the shared component — its accepted
context, and its mount count — not another sweep.

