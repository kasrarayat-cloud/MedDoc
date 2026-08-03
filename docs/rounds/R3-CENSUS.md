# R3 item 0 — the legacy-island census

**Produced by `tests/e2e/scenarios/rounds-legacy-census.spec.ts`
(`--project=rounds-census`), on the flag-ON QA image, 2026-08-03.**

Two consecutive runs agree exactly — 9 states, 120 rows, 103 unhosted. A census
that varies by timing is a sample; this one is reproducible, which is what makes
it an inventory.

## Why this exists

R1 found the app split-brain. R2 found a footer two artifacts claimed was
already gone. R3's brief is eight more legacy islands. **Each round has been a
list of sightings, and a list of sightings cannot tell you when you are
finished.** This walks the live DOM on every authenticated state and enumerates
what actually renders legacy skin.

## Surface → family → item

| surface | unhosted legacy classes | dominant family | R3 item |
|---|---|---|---|
| `/visits/[id]` (the stage) | **38** | `qm-lin-rx-*` (30+), `qm-c3-rev2-root`, `qm-vdoc-format-on` | **4** (rx surface), **5** (Word preview) |
| `/visits/[id]/record` | **38** | same set — the stage renders beneath it | **4**, **5** |
| `/visits/new` | **10** | `qm-c3-nv-*` (card, kicker, h, p, picker, top, eyebrow), `qm-lin-btn` | **7** |
| `/patients/[id]` | **5** | `qm-lin-btn-primary` (legacy **sage**), pills | **2** |
| `/visits` | **5** | `qm-lin-btn-primary` (sage), `qm-lin-pill--sage`, `qm-lin-row`, `qm-lin-pill--ready` | **DISCOVERED SCOPE** — not in the brief's eight |
| `/board` | 0 | — | item **8** is a removal, not an island |
| `/patients` | 0 | — | **1** — see the limitation below |
| `/settings` | 0 | — | already bridged (`.qm-rounds-host`) |
| `/settings/note-format` | 0 | — | already bridged |

10 further rows sit INSIDE `.qm-rounds-host`, which redeclares the
`--color-linear-*` names on a scoped class — they are already re-skinned and are
reported separately rather than counted as islands.

## Discovered scope

**`/visits` is not in the brief's eight and carries 5 legacy classes**, including
the legacy sage `qm-lin-btn-primary` and `qm-lin-pill--sage`. It is an
authenticated Rounds route a doctor reaches from the nav, so it joins R3 as
discovered scope, declared here and in the ledger.

## STATED BOUNDARY — what this census does NOT establish

1. **It cannot see "correct tokens, wrong anatomy."** `/patients` reports **zero**
   legacy classes and is still a redesign target (item 1): the owner's verdict
   was *"a redesign, not a recolor"*, which no class or colour matcher detects.
   **A clean row here is not a claim that a surface is finished.**
2. **Two transient states are not walked**, and are named rather than reported
   clean: the "Writing the note…" processing card, and the post-creation
   error/retry surface. Both exist only during a live pipeline run.
3. An earlier draft of this boundary also named the prescription-safety rail as
   unreachable, on the reasoning that it needs `MOCK_RX_WARNINGS`. **That was
   wrong** — `seedReviewDocVisit` writes `rxDrafts`, so the rail renders on the
   ordinary fixture and the DOM arm enumerated it. Recorded because a boundary
   that over-claims what a check cannot see is the same defect as one that
   over-claims what it can.

## How it is kept honest

- **Per-route load assertion** — a route that 404s would otherwise read as clean.
- **Positive control on BOTH arms** — a probe node carrying a `qm-c3-*` class and
  a legacy sage colour is injected and the same predicates must find it. Without
  it, a zero census and a broken census are the same output.
- **Visibility check** (`offsetParent` + rect) so compiled-but-unrendered nodes
  do not inflate the count.
- **Bridge awareness** — hosted vs unhosted reported separately.
- **Settle before enumerating.** The first widened run reported the stage as
  **0** and the next as **38**, same build and fixture: the paper renders
  asynchronously. Enumerating on first paint counts whatever happened to be
  mounted.
