# T4 — Sign & deliver: the frames, exactly as the file has them

**Source of truth.** Figma file **`Zvgz37i6jVoNYy9BzAAtoQ`**, page `Page 1`
(`0:1`), read through the Figma REST API on 2026-09-04. Every value is out of the
node JSON, never a screenshot. Raw extract beside this file at
`t4-figma-raw-extract.txt`.

⚠️ **A SECOND FILE.** The Receipt (T2) lives in `vDPGIxwPmm08BTzBD99vfQ`; these
two frames live here. The earlier "no such frame exists" finding was correct
about the first file and stays correct — it simply was not the whole spec.

| frame | node | size |
|---|---|---|
| `sign-deliver-pre` | `18:5` | 1440 × 1024 |
| `sign-deliver-post` | `18:81` | 1440 × 1024 |

Both draw a mock EHR behind a scrim; **only the modal card is ours**. The
`ehr-container` behind it is scaffolding for the mock-up, not a surface to build.

---

## ✅ THESE FRAMES ARE ALREADY IN THE ROUNDS PALETTE

Unlike the Receipt frames, which use the legacy sage, **every accent here is
`#5b5bd6` — the Rounds indigo** — for checked checkboxes, the primary button and
the DOCUMENT SIGNED badge. The colour ruling (map by role) therefore costs almost
nothing on T4: the file already agrees with the shipped skin.

| role | frame value | Rounds token |
|---|---|---|
| scrim | `#09090c` @0.8 | — (overlay) |
| modal ground | `#1e1e24` | `--rounds-surface-2` `#1e2530` |
| modal border, dividers, row rules | `#ffffff` @0.08 | `--rounds-line-1` |
| title / row label | `#f7f8f8` | `--rounds-text-1` |
| supporting copy, attestation | `#f7f8f8` @0.75 | `--rounds-text-2` |
| section label, summary, footer | `#f7f8f8` @0.3 | `--rounds-text-3` |
| **accent** — checked box, primary button, badge | **`#5b5bd6`** | **`--rounds-accent`** |
| accent label on the button | `#ffffff` | `--rounds-on-accent` |

---

## `sign-deliver-pre` — `modal-card-pre`, 496 × 511

`#1e1e24` · 1px `#ffffff` @0.08 · radius 12 · `VERTICAL` gap 24 · pad 24

1. **Head** (gap 8) — `"Sign & deliver"` Inter 600 20/26 · `"Confirm destination
   settings and sign off this progress note."` Inter 400 13/18 @0.75
2. **`DELIVER TO`** Inter 600 12/15 @0.3 UPPERCASE, pad 8 top / 8 bottom
3. **Four destination rows**, each **448 × 44**, `HORIZONTAL` gap 12, pad 12
   left/right, `cross:CENTER`, **1px `#ffffff` @0.08 bottom rule — except the
   last, which has none**:

   | row | state in the frame |
   |---|---|
   | Copy note to clipboard | **unchecked** |
   | Download PDF | **checked** |
   | Download Word | **unchecked** |
   | Email to referring physician | **checked** |

   Checkbox **20 × 20**, radius 4 — unchecked: 1.5px `#f7f8f8` @0.3 stroke, no
   fill; checked: fill `#5b5bd6` with an 8 × 5 tick, 2px `#ffffff`.
   Label Inter 400 14/17 `#f7f8f8`.
4. **Divider** 1px `#ffffff` @0.08, then the **attestation** row (gap 12): a
   **checked** box + *"I have reviewed this note and attest that it accurately
   reflects the clinical encounter."* Inter 400 14/20 @0.75
5. **Delivery summary** — `"Delivery summary: PDF • to Dr. Ananya Nair"`
   Inter 400 12/15 @0.3
6. **Actions**, `main:MAX` (right), gap 12 —
   **Cancel** 79 × 37, 1px `#f7f8f8` @0.3, radius 6, pad 10/16, Inter 500 14/17 @0.75 ·
   **Sign & deliver** 129 × 37, fill `#5b5bd6`, radius 6, pad 10/18,
   Inter 600 14/17 `#ffffff`

### What the frame settles about behaviour

- **Destinations are CHECKBOXES and they accumulate** — two are checked at once,
  which is the "one-or-more destinations preserved" requirement drawn.
- **Clipboard is its own independent row.** In the frame it is *unchecked* while
  Download PDF is *checked* — so a clipboard-only choice is expressible, and it
  does not imply a PDF. That is the constraint stated as geometry.
- **The delivery summary line reflects the checked set** — `PDF • to Dr. …`
  mirrors exactly the two ticked rows.
- **Attestation is a checkbox inside the modal**, not a separate gate.

---

## `sign-deliver-post` — `modal-card-post`, 496 × 406

Same ground, border, radius, gap and padding. Four differences:

1. **A status badge replaces nothing above the title** (gap 8, `cross:CENTER`):
   a 16 × 16 `shield-check` vector, 2px `#5b5bd6`, then `"DOCUMENT SIGNED"`
   Inter 600 13/16 `#5b5bd6`.
2. **Title** `"Export signed note"` Inter 600 20/26; sub *"The progress note has
   been successfully locked. Deliver to required destinations."* Inter 400 13/18 @0.75
3. **The rows stop being checkboxes and become ACTIONS** — 448 × **42**, label
   left, an **18 × 18 trailing icon** (2px `#f7f8f8` @0.75) right, same 0.08 rules
   with none on the last:

   | row | icon |
   |---|---|
   | Copy note to clipboard | `clipboard-copy` |
   | Download PDF | `file-down` |
   | Download Word | `file-down` |
   | Send email to Dr. Nair | `send-horizontal` |

4. **Footer**, `SPACE_BETWEEN`, `cross:CENTER` — `"Signed by Dr. Priya Mehta •
   Sep 4, 2026 09:15"` Inter 400 12/15 @0.3, and **`"Export again"`**
   Inter 600 13/16 @0.75.

⚠️ **THE CHECKBOX → ACTION SHIFT IS THE DESIGN, NOT A DETAIL.** Before signing a
destination is a *choice you accumulate and then commit*; after signing it is a
*thing you do now, repeatedly*. There is no Cancel and no primary button in the
post state — every row is its own commit, and `Export again` reopens it.

---

## Still on the batched request list, for T4

1. **Row states.** No hover, focus-visible, disabled, pending or error state is
   drawn for either the checkboxes or the post-sign action rows. A post-sign row
   is a button that performs I/O — it needs at least a pending and a failed look.
2. **`Email to referring physician` with no referring physician on file.** The
   frame always names one (`Dr. Ananya Nair` / `Dr. Nair`). What does the row do
   when the visit has no recipient — hidden, disabled, or a picker?
3. **Zero destinations checked.** Is `Sign & deliver` disabled, or does signing
   proceed with no delivery?
4. **Attestation unchecked.** The frame only draws it checked.
5. **The mock EHR behind the scrim is not our surface** — confirmed as scaffolding.
6. **1440 is the only breakpoint drawn**, for a 496-wide modal.
