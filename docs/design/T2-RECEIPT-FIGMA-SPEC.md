# T2 — the ICD "Receipt" view: the frames, exactly as the file has them

**Source of truth.** Figma file `vDPGIxwPmm08BTzBD99vfQ`, page **`ICD QUillMD`**
(`101:2`), read through the Figma REST API on 2026-09-04. Every number below is
read out of the file's own node JSON — **not** from a screenshot, per the
standing no-solo-design rule. The raw extract is beside this file at
`t2-figma-raw-extract.txt` so any value here can be checked against its source.

> ⚠️ **`node-id=101-2` is the PAGE, not a frame.** The two frames live inside it.

| frame | node | size |
|---|---|---|
| `claim-summary-ready` | `102:366` | 1440 × 1024 |
| `claim-summary-signed` | `102:419` | 1440 × 1024 |

---

## Tokens the frames actually use

| role | value | maps to |
|---|---|---|
| canvas | `#08090a` | `--color-linear-bg` — **exact match** |
| card ground | `#0d0e0f` | ≈ `--color-linear-surface-1` (`#0d0e10`) — **off by 1 in blue** |
| card + row hairline | `#ffffff` @ **0.04** | ≈ `--color-linear-hairline` (`rgba(255,255,255,.05)`) — **not identical** |
| header rule | `#ffffff` @ **0.06** | no existing token |
| accent (code, badge, CTA) | `#7aa68c` | `--color-linear-sage` — **exact match** |
| CTA label on accent | `#08090a` | `--color-linear-bg` |
| body sans | Inter | `--font-sans` |
| code / numerals | JetBrains Mono | `--font-mono` |

⚠️ **THE ACCENT IS THE LEGACY SAGE, NOT THE ROUNDS INDIGO.** `#7aa68c` is
`--color-linear-sage`; the Rounds skin's accent is `#5b5bd6`, and
`rounds-tokens.css` deliberately retints legacy sage to the Rounds accent
wherever it appears on the visit surface. **These frames were drawn in the legacy
palette.**

## ✅ RULED 2026-09-04 — BUILD IN ROUNDS TOKENS, MAP BY ROLE

Owner ruling: **the frames are the spec for structure, spacing, type, hierarchy
and copy; COLOURS map by ROLE.** Sage maps to the surface's accent token, because
`rounds-tokens.css` deliberately retired sage on this page and *a green panel on
an indigo visit page reads as a bug, not a design.* If sage is later ruled back
in for the Receipt, it is **one token change**.

⚠️ **AND THE T4 FRAMES INDEPENDENTLY CORROBORATE IT.** The Sign & deliver file
(`Zvgz37i6jVoNYy9BzAAtoQ`) uses **`#5b5bd6` — the Rounds indigo — natively**, for
every checked checkbox, the primary button and the DOCUMENT SIGNED badge. So the
two files disagree with each other about the accent, and the newer one already
agrees with the shipped skin. That is evidence, not preference.

### The mapping table

| role in the frame | frame value | Rounds token | measured |
|---|---|---|---|
| card ground | `#0d0e0f` | `--rounds-surface-1` `#161b24` | the ground the coding view already ships |
| card + row hairline | `#ffffff` @0.04 | `--rounds-line-1` `#2c3442` | — |
| primary heading | `#ffffff` @0.90 | `--rounds-text-1` `#e7ebf1` | **14.43:1** |
| row description | `#ffffff` @0.75 | `--rounds-text-2` `#98a2b1` | **6.69:1** |
| section header · confidence · caption · archive footer | `#ffffff` @0.20–0.30 | `--rounds-text-3` `#7c8694` | **4.68:1** |
| accent — code, badge stroke, CTA fill | `#7aa68c` | `--rounds-accent` `#5b5bd6` | 3.22:1 on card — **fill/stroke only, never body text** |
| accent as TEXT (badge label) | `#7aa68c` | `--rounds-accent-text` `#a5a5f0` | **7.60:1** |
| CTA label on accent | `#08090a` | `--rounds-on-accent` `#ffffff` | **5.37:1** on the accent |

⚠️ **EVERY RATIO IN THAT TABLE IS COMPUTED, NOT TRANSCRIBED.** The first draft of
it carried five numbers I had written from memory — 7.98, 5.28, 3.29, 8.06, 5.90
— against measured values of 6.69, 4.68, 3.22, 7.60 and 5.37. All five were
wrong, all five were wrong in the *flattering* direction, and one of them
(`--rounds-text-3` at a real **4.68:1**) sits close enough to the 4.5 floor that
the invented figure would have hidden how little headroom it has. The table is
now generated from the token values in `rounds-tokens.css`.

⚠️ **THE ACCENT SPLITS IN TWO, AND THAT IS THE WHOLE REASON THIS TABLE EXISTS.**
`--rounds-accent` measures **3.22:1** on the card — fine for a fill, a stroke or a
CTA ground, and **below the 4.5 floor for text**. The frame uses sage for both the
row's CODE (text) and the CTA (fill). Mapping one token to both would ship a
1-in-2 contrast failure on every row. `--rounds-accent-text` exists for exactly
this and measures **7.60:1**.

⚠️ **THE RECEIPT IS A DARK CARD ON WHITE PAPER, AND THAT IS ALREADY TRUE TODAY.**
`icd-coding-view.tsx:249` paints `--rounds-surface-1` with light
`--rounds-text-*` inside it, sitting inside the Rounds paper. Verified: ink on
that ground measures **14.43:1**, so the surface passes and canon's
paper-chrome bridge deliberately does not reach it. The frames' dark card is
therefore structurally what ships — no ground question to answer.

---

## `claim-summary-ready`

```
FRAME 1440×1024  fill #08090a  VERTICAL  pad 80/0/80/0  main:CENTER cross:CENTER
├─ TEXT   "Sarah Chen · Follow-up · Aug 27, 2026"   Inter 400 13/16   #ffffff @0.25
├─ FRAME  ledger-card-unsigned   720×559
│     fill #0d0e0f · stroke 1px #ffffff @0.04 · radius 12
│     VERTICAL gap 16 · pad 36 / 40 / 32 / 40
│  ├─ FRAME card-header            640 · VERTICAL gap 16
│  │  ├─ TEXT "Coding — ready to sign"   Inter 500 20/24   #ffffff @0.90
│  │  └─ LINE 640×0                       1px #ffffff @0.06
│  └─ FRAME ledger-content        640×435 · VERTICAL gap 12
│     ├─ FRAME section-header-Diagnoses            pad 12 top / 8 bottom
│     │  └─ TEXT "Diagnoses"      Inter 500 11/13  #ffffff @0.25  UPPERCASE
│     ├─ FRAME (6 × ledger-row)   640×222
│     ├─ FRAME section-header-History & Screening  pad 12 top / 8 bottom
│     │  └─ TEXT "History & Screening"  (same type)
│     └─ FRAME (3 × ledger-row)   640×111
├─ TEXT   "5 suggestions outside the verified set · 1 low-confidence code
│          included — tap any line to change"
│          Inter 400 12/15  #ffffff @0.20  CENTER   720 wide
└─ FRAME  button-sign-finalize   720×52
      fill #7aa68c · radius 26 · HORIZONTAL main:CENTER cross:CENTER
      └─ TEXT "Sign & finalize"   Inter 500 15/18   #08090a
```

### The row — the unit the whole view is made of

`ledger-row-<CODE>` · **640 × 37** · `HORIZONTAL` · pad 10 top / 10 bottom ·
`cross:CENTER` · **bottom hairline 1px `#ffffff` @0.04**

| column | width | type | ready | signed |
|---|---|---|---|---|
| code | **96** | JetBrains Mono 400 13/17, LEFT | **`#7aa68c`** | `#ffffff` @0.40 |
| description | **484** | Inter 400 14/17, LEFT | `#ffffff` @0.75 | `#ffffff` @0.50 |
| confidence | **60** | JetBrains Mono 400 12/16, **RIGHT** | `#ffffff` @0.30 | `#ffffff` @0.20 |

96 + 484 + 60 = **640**. The row is a three-column grid, not a flex row with
gaps — there is no `itemSpacing`.

---

## `claim-summary-signed`

Same card, same rows, same section headers. Four differences, all of them
meaningful:

1. **The header gains a badge.** `header-top-row` becomes `HORIZONTAL`,
   `main:SPACE_BETWEEN`, `cross:CENTER`:
   - TEXT `"Coding — signed"` Inter 500 20/24 `#ffffff` @0.90
   - FRAME `signed-badge` 76 × 23 · stroke **1px `#7aa68c` @1.0** · radius 4 ·
     `HORIZONTAL` gap 6 · pad 4 / 10 · `cross:CENTER`
     - `check-circle` 10 × 10 containing a VECTOR 8 × 8, **stroke 2px `#7aa68c`**
     - TEXT `"Signed"` Inter 500 12/15 `#7aa68c`
2. **The accent leaves the rows.** Codes go from `#7aa68c` to `#ffffff` @0.40,
   descriptions from @0.75 to @0.50, confidence from @0.30 to @0.20. **The whole
   ledger recedes**: signing is what turns it from a working surface into a
   record.
3. **`archive-footer`** 640 × 37 · `HORIZONTAL` · pad 24 top · `main:MAX`
   (right-aligned) — TEXT `"Signed Aug 27, 2026 at 2:47 PM by Dr. Marcus Vance"`
   Inter 400 11/13 `#ffffff` @0.20.
4. **No CTA.** `button-sign-finalize` is gone; an empty 720 × 100 frame sits
   where it was. The caption line is gone too.

Card height 559 → **612** (the badge row and the archive footer).

---

## ✅ RULED 2026-09-05 — THE PROVENANCE WORD, ruling #187(2)

**An auto-accepted row is visibly distinct from a doctor-accepted one, AS TEXT.**
A word in the frames' own right-aligned meta column — `auto` / `you` — beside
the confidence. The frames' existing vocabulary and geometry; no new visual
element.

**Never a colour.** A tint does not survive a greyscale print, a PDF of the tab,
or a colour-vision-deficient physician — and this is the surface a doctor
attests from.

⚠️ **THE HIDDEN ACCESSIBILITY TEXT STAYS.** The two are not alternatives and the
obvious simplification — drop the hidden label now that a visible word exists —
re-opens half the defect. The hidden text carries the STATE, which the
provenance word does not, and it is what restores the parity the pre-conversion
section HEADINGS gave assistive technology. Both are pinned.

⚠️ **STACKED, NOT INLINE — GEOMETRY, NOT TASTE.** The frames fix this meta
column at **60px**, and `95%` + a separator + `auto` does not fit. Stacking the
word under the confidence keeps the frames' column width. Recorded here so the
next reader does not "fix" it back to one line.

**Its origin is a finding.** The T2 conversion moved the decision state out of
section headings onto the row, where it became `data-state` plus a CSS tint —
and `ICD_ROW_STATE_LABEL`, added in the same slice, was rendered nowhere.
Measured on a signed visit: an accepted row and a held row were **byte-identical
in text**, accessible name `null`.

## ⚠️ THE ONE DEPARTURE FROM THE FRAMES — ruling #187(3), APPROVED

**The section holding the suggester's FIRST code leads.** The frames draw
`Diagnoses` first and then `History & Screening`; the shipped ledger orders the
two sections by where the suggester's first code falls.

**Everything else follows the frames**, and within a section the order is the
suggester's own, untouched. This is the ONLY place the build knowingly differs.

### Why

`icd-ledger-sections.ts`'s own header already forbade the alternative, in bold:

> ORDER IS PRESERVED, NEVER SORTED. The suggester emits codes in an order that
> carries meaning — the primary diagnosis leads — and a display that re-sorts
> them would silently re-rank a claim.

A FIXED section order does exactly that, and the counterexample is this
product's commonest encounter:

| | |
|---|---|
| suggester emits | `Z12.11`, `D12.5`, `K64.8` |
| fixed section order renders | `D12.5`, `K64.8`, **`Z12.11`** |

For a screening colonoscopy `Z12.11` **is** the first-listed diagnosis and the
reason for the encounter; the polyp is secondary. The fixed order demotes it to
last, under a heading that reads like an aside.

### The standing of this departure

⚠️ **The frames do not RULE on it — they do not cover the case.** Neither frame
draws a Z-code primary, so a fixed order is what the frames happen to show
rather than a decision they record. That is why this is filed as a departure and
not as a defect in the frames.

Owner-approved in **ruling #187(3)**, on the precedent this arc already set with
the counts chip: *a tested clinical claim outranks a mockup.* Pinned by
`gate-icd-ledger-sections`, which asserts the suggester's first code is the
first code the doctor reads, whichever section leads.

## ⚠️ BATCHED FIGMA REQUEST LIST — states no frame covers

Per the standing rule, **none of this is invented**. Each item is a state the
build needs and the file does not describe.

### ✅ DISCHARGED 2026-09-04 — T4's frames arrived in a SECOND file

1. ~~`Sign & deliver` (pre-sign)~~ → **`sign-deliver-pre`** `18:5`, 1440×1024
2. ~~`Export signed note` (post-sign)~~ → **`sign-deliver-post`** `18:81`, 1440×1024

⚠️ **THEY ARE IN A DIFFERENT FIGMA FILE — `Zvgz37i6jVoNYy9BzAAtoQ`, not the file
that carries the Receipt.** The original search was not wrong: across all 8 pages
and 521 nodes of `vDPGIxwPmm08BTzBD99vfQ`, zero node names matched
`deliver|export|pre-sign|post-sign`, and that remains true. Two files, one spec —
worth stating so a later reader does not conclude the first search was faulty.

Full extraction: **`T4-SIGN-DELIVER-FIGMA-SPEC.md`**, beside this file.

### Blocking the ruled auto-accept behaviour in T2

3. **THE FRAME DOES NOT DISTINGUISH ACCEPTED FROM PENDING-REVIEW — and its own
   caption says it should.** Measured: all nine rows in `claim-summary-ready`
   render **identically** — code `#7aa68c`, description @0.75, confidence @0.30 —
   whether the confidence is **95%** or **55%**. Yet the caption reads *"5
   suggestions outside the verified set · **1 low-confidence code included** — tap
   any line to change"*.

   The ruled behaviour is that codes at or above a data-derived threshold **start
   pre-accepted** and low-confidence ones **stay for review**. That is a
   two-state list, and the frame draws one state. **What does a
   held-for-review row look like?**

4. **What does an ACCEPTED row look like after the doctor taps it?** "Tap any
   line to change" implies a flip; no frame shows the flipped state.
5. **What does a REJECTED / removed row look like** — struck through, greyed,
   moved to a section, gone?
6. **Which row is "outside the verified set"?** The caption counts five; nothing
   marks them.

### Ordinary states with no frame

7. Hover / focus-visible on a row (it is a keyboard target if it is tappable).
8. Empty state — a visit with no codes.
9. Error state — the decision write fails.
10. The reason picker, if rejection keeps one (the current UI has one).
11. Long descriptions — the widest in the frame is 54 characters at 484px. What
    wraps, what truncates?
12. Narrow viewports — both frames are 1440 only; the card is a fixed 720.

### Palette

13. **Legacy sage `#7aa68c` or Rounds indigo `#5b5bd6`?** The frames are drawn in
    the legacy palette, which `rounds-tokens.css` retints everywhere else on this
    surface. Shipping the frames literally would put the retired brand colour
    back on the visit page.

---

## Honest limits of this extract

- Values are the file's **absolute** geometry and its own fill/stroke records. No
  Figma **variables/styles** are bound in these frames — the colours are raw, so
  there is no design-token layer in the file to inherit.
- `1440 × 1024` is the only breakpoint drawn.
- I have not rendered the frames to PNG; every value here comes from node JSON,
  which is the stricter source and the one the rule asks for.
