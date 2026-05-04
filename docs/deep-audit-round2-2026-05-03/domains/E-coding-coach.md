# Domain E — Coding Coach (Phase 5.2)

**Run:** 2026-05-03 20:55 UTC
**Visit:** `cmoq6q5s4000p01qqhdngm77n` (cardiology — Round 1)

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| E1 | Coding Coach loads on visit detail | ✓ | rail visible with chips |
| E2 | "+ add 1 element" button click | ✓ — clicks but **0 XHRs fired** | INFO: client-side state only |
| E3 | "Confirm 99214 · sign" button click | ✓ — clicks but **0 XHRs fired** | INFO: client-side state until Sign & Send |
| E4 | Re-test prior P3-001 (Codes tab → Cmd-K) | resolved | **TEST RIG ARTIFACT** in Round 1 — selector matched Cmd-K search bar (which contains "codes" in placeholder) instead of the Codes tab. Codes tab itself works fine. |

## Findings

### E-001 — Coding Coach updates are client-side until Sign & Send (POSITIVE)

The `+ add 1 element` and `Confirm 99214 · sign` buttons fire **0
backend XHRs**. The coding rail's E/M score, accepted codes, and
overrides are all staged in React component state. Only when the
doctor clicks Sign & Send does the final state ship to the server
(via `/api/visits/[id]/sign` per the source code).

This is **good architecture**:
- Doctor can flip codes around without each click being a server
  round-trip (low latency, no rate-limit risk)
- A network drop during code editing doesn't lose work (state is
  in client memory; user can keep editing)
- Sign-time commit is atomic — either the whole signed bundle
  lands or none does

**Trade-off:** if doctor closes the tab without signing, the
coding-rail edits are lost. The same is true for SOAP-body edits
in the inline editor (read in source: edits go to a textarea, save
fires a server action only when user clicks Save). Worth verifying
with Kasra whether unsaved changes warn the user before tab-close
(`beforeunload` handler).

### E-002 — P3-001 from Round 1 sweep was a test-rig artifact (RESOLVED)

The prior QA sweep finding (`docs/qa-sweep-authenticated-2026-05-03/
bugs/P3-001-tab-click-may-trigger-cmdk.md`) said clicking the
"Codes" tab produced a body containing the Cmd-K command palette
overlay. Round 2 re-test confirmed the button inventory contains:

```
"Search patients, visits, codes…⌘K"   ← THE CMD-K SEARCH BAR (contains "codes")
"Codes"                                 ← THE CODES TAB
```

Playwright's `:has-text("Codes")` selector matched **the Cmd-K
search-bar button first** (DOM order). Clicking that button opens
the palette — exactly the behavior observed in Round 1. The Codes
tab itself is unaffected.

**Recommended action:** mark Round 1 P3-001 as RESOLVED — false
positive. No code change needed.

## Test methodology

The deep test of "click each E/M rubric chip — does score update?"
requires identifying the chip elements specifically. Round 2's
selector (`[data-em-chip], [role="checkbox"], [data-element-status]`)
returned `chipCount: 0` — the chips don't carry these attributes
on the visit-detail page. They're styled buttons or divs without
explicit `data-em-chip`. Recommend adding `data-em-chip` /
`data-element-status` test attributes to make E/M coding-rail
elements reliably testable.

## What was NOT covered

- Rejecting all suggested codes (E5)
- Accepting all suggested codes — score reaches max (E6)
- Visit with no codes yet (empty state — E4 sub)
- Visit with conflicting codes (99214 + 99215)
- Visit with mismatched codes (E11.9 with no diabetes in SOAP)

These would require carefully-crafted visits + DOM-level
inspection of chip state. Recommend a focused human session.
