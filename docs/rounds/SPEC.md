# Rounds — the master spec

**This document is the contract.** It was written from the master prompt so that
no future session needs chat history. If this file and a component disagree,
this file is right and the component is a bug. Where it is silent,
`docs/design-tokens.md` is the authority for colour, type, radii and depth.

Rounds is **the merge of two design directions** — **Ward Board** and **Focus
Flow**. Neither shipped alone. The spec below was written from the full source of
both and amended after war-room review of their rendered screens.

> **No design bundle is attached, and none is coming.** This spec is the
> authority. Do not wait for images.

---

## Architecture invariants — the skin changes, these do not

These are not style preferences. Every phase re-checks them.

- **Read-only paper.** Zero edit affordances on the document, at any breakpoint.
- **The chat editor remains the only edit path.**
- **All four fail-closed gates keep their exact server semantics.** The UI is a
  skin over them; `POST /sign` stays the sole source of truth.
- **`emApplies` decides whether the E/M gate exists at all** — imaging: never.
  Not hidden, not disabled, not a styled-empty state. Absent.
- **PDF/Word parity and the 820px paper stay.**
- **Custom templates render untouched.** Rounds styles the **default QuillMD
  layout only**.
- **The old skin remains the default until the final flip.**

---

## Tokens

`docs/design-tokens.md` is the authority and already carries these. Summarised
here only so this document stands alone:

- **Stage bg** radial `#232B3A → #171D27 → #12161E`; surfaces `#161B24` /
  `#1E2530` / `#252D3A`; lines `#2C3442` / `#3A4353`; on-stage text `#E7EBF1` /
  `#98A2B1` / `#7C8694`.
- **Paper** `#FCFCFA` / `#F3F4EF` / `#ECEDE7`; ink `#191E26`; muted `#525A66`;
  paper lines `#E7E8E3` / `#D8DAD3`.
- **Accent** `#5B5BD6` (hover `#4A49C4`, tints .10/.16).
- **Status** critical `#C93A2E` · ready `#187A4E` · E/M amber `#C4841C` (fill
  `#E29A34` for E/M action buttons) · processing `#3B6FD4` · signed `#6B7480` on
  stage / green `#187A4E` for completed track runs.
- **Fonts** Bricolage Grotesque (display) · Figtree (UI) · Source Serif 4 (**ALL
  clinical prose incl. the default paper template**) · JetBrains Mono
  (labels/MRNs/codes/pair lines).
- **Radii** 9–18px; paper cards carry the deep two-layer Focus Flow shadow.
- **WCAG AA all text; reduced-motion honoured; visible keyboard focus
  everywhere.**

---

## Screen 1 — THE BOARD (dashboard)

Ward Board's **patient-lanes × stage-columns** matrix on the dark stage.

**Top bar:** Q mark + wordmark · nav (Board · Templates · Settings) · red-outline
critical tally badge · clinician identity · Focus Flow **day-progress meter**
(signed · to review · live + bar).

**Filter strip:** date + tally line · filters (Active / Signed / SOAP /
Ultrasound / Critical / Failed) · **the EXISTING whole-queue search restyled in**
· an "Open next review →" quick link.

> **Search and pagination survive. The designs' bans lose to shipped features.**

**Numbered stage column headers with counts**, mapped from real statuses.

### Track semantics — explicit

Each lane rides a hairline track.

| Lane | Track | Card |
|---|---|---|
| **Signed** | solid **green** line, the full run | muted Signed card, "signed 8:52 AM" |
| **Failed** | **red** line stopping at the failure stage | dashed red card + **RETRY** affordance in-lane |
| **Processing / Recording** | — | dashed border, **amber** kicker / **pulsing red REC** |
| **Ready** | — | solid white |
| **Critical** | tinted lane row | red-bordered, ⚠, one-line interaction warning |

**Marker legend footer** (ready / recording / processing / critical / signed).
Click a marker to open the visit.

**Empty state: an invitation to record, not a mood.**

**Data honesty:** every datum derives from the real queue source. Park visibly
anything with no real data. **Never fake.**

---

## Screen 2 — THE STAGE (visit review)

Focus Flow's spotlit layout, carrying Ward Board's position-awareness.

**Pipeline strip**, above the sheet: five nodes from real statuses; done nodes
solid with checks; **"NOW REVIEWING"** marker on the current node; the **Signed
node PADLOCKED** with **"N blockers before Signed"** where

> **N = this visit's applicable unresolved gates: critical Rx count + E/M where
> `emApplies` + attestation.**

The strip **ticks live as gates clear**.

**The elevated white sheet IS the existing paper preview component**, default
layout restyled: Source Serif 4 body **15–16.5px/1.7**; section headers with
**derived glyph markers** — S·O·A·P for SOAP, template-section-derived for
imaging; kickers in mono smallcaps; hairline rules. **Reserve the vitals-chip
slot in the layout but build it only when structured vitals exist — parked,
never faked.**

**Critical band** across the card top when unresolved ("you'll clear it at
Gate 1").

**Identity header:** name · MRN·age·DOB · reason line · WB's bordered meta cells
(recorded · audio duration).

**Next-up encounters peek at stage edges**; "N of M to review" + dots; queue
drawer on demand.

**Chat editor:** summoned drawer over the stage (button + keyboard shortcut),
restyled to tokens — **the only edit path, one gesture away**.

**Moderate Rx advisories inline with ACKNOWLEDGE as today.**

**Action rail:** Review & sign primary (label carries gate count) · Skip
secondary · kbd hints.

---

## Screen 3 — THE GATES (sign flow)

Focus Flow **full-screen sequential gates over the EXISTING gate logic**, styled
with Ward Board's blocker language. **Only applicable gates exist.** Each cleared
gate ticks the pipeline strip.

- **Gate 1 — Critical Rx:** red-tinted blocker card; drug pair in mono;
  **`> OVERRIDE` prompt-style typed input per warning, as today**; accountability
  line on success.
- **Gate 2 — E/M (only when `emApplies`):** big code + complexity · minutes;
  confidence; rationale; **amber CONFIRM `<code>`** primary; **"Change code" = the
  existing adjust-level flow** (required reason, audit row); stale state renders
  here with re-check.
- **Gate 3 — Attestation:** cleared-gates summary rows; attestation checkbox
  naming patient and date; **Sign & lock**; footer *"Signing locks the note. Later
  changes require a dated addendum."*

Locked-until-clear affordance styled as WB's dashed 🔒 **"Complete blockers to
advance."**

> **Server refusals remain the sole source of truth — the gates are UI over
> them; existing sign-block E2Es pass with semantics unchanged.**

---

## Screen 4 — SIGNED & LOCKED

Pipeline strip fully green-checked. **Green lock banner** (signed by / timestamp
/ patient / E/M-if-applicable + attestation line). **Safety trail as bordered
check cards — only what applied** (override logged · E/M confirmed · attested).
Read-only paper below with **"corrections require a dated addendum"** footer.

**THE DECK ADVANCES:** the signed card recedes (small, grayed) with an arrow to
the next in-review encounter's card, and a **Continue** primary.

---

## Also restyle

Login / signup (invite field) / waitlist · settings + My Note Format · templates
· error/empty/loading states (stage treatments).

**Copy register:** plain verbs, sentence case, **actions keep their names
end-to-end**.

---

## Phases and gates

Built behind `NEXT_PUBLIC_SKIN_ROUNDS` on QA (tagged images, MOCK posture check
green). **The flag stays OFF until the final flip.**

**Phase A — tokens + shell + board.**
GATE A: axe zero serious/critical on the board · chromium E2E green ·
screenshots 1440 + 1024 · merge on green · tagged QA image kept.

**Phase B — stage + gates + signed.**
GATE B: axe zero serious/critical on stage + all gates + signed · chromium E2E
green **incl. sign-block semantics** · fixture matrix green **both specialty
classes** (imaging: no E/M gate, no strip blocker for it, anywhere) · PDF/Word
parity re-proven at 1440 · screenshots · merge on green.

**Phase C — auth/settings/templates + default-paper typography.**
GATE C: axe on every restyled screen **incl. waitlist** · full suite + typecheck
· E2E green · merge on green.

**Phase C also carries the report-template design deliverable:** default-paper
typography finalized, **exports must match preview 1:1**.

---

## Final — the flip

Only if **A + B + C gates are all green**.

1. Walker element map updated for Rounds; run on the QA stack (this build);
   `ok:true`.
2. MOCK posture check green.
3. **Tag `:pre-rounds-<date>` FIRST.**
4. Flip `NEXT_PUBLIC_SKIN_ROUNDS` on prod **via `scripts/deploy-prod.sh` only**.
5. **Retire the old skin code — delete, not hide — in a follow-up commit AFTER
   the flip verifies.**
6. Update the rollback-constraint docs against the new baseline.

**Prod smoke, both walks:**

- one **custom-template ultrasound** visit: no E/M anywhere · letter + export
  intact · `ANCHOR_FLAGS_RECORDED`
- one **primary-care** visit: chat edit → stale → gates → adjust level → confirm
  → sign · audit rows in order

Reset the smoke account, **keep audit rows**. Standing checks green. Prod +
co-tenants verified. **Host nginx for ingress, never Caddy.**

---

## Stop-condition

> If any phase's gate cannot go green after genuine fix attempts, **stop there,
> leave the flag OFF, report.** Never flip a partial skin.

## Resource pre-flight

At the start of each phase: `free -h`, `df -h`, `docker stats`. **Batch
sub-agents; never parallel-all under 2 GB free.**
