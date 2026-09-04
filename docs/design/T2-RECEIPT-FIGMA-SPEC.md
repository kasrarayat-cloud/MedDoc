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
wherever it appears on the visit surface. **The frames were drawn in the legacy
palette.** Which one T2 should ship in is a question for the owner, not a choice
for this session — it is the first item on the request list below.

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

## ⚠️ BATCHED FIGMA REQUEST LIST — states no frame covers

Per the standing rule, **none of this is invented**. Each item is a state the
build needs and the file does not describe.

### Blocking T4 entirely

1. **`Sign & deliver` (pre-sign)** — **no such frame exists.**
2. **`Export signed note` (post-sign)** — **no such frame exists.**

Measured, not assumed: across all 8 pages and 521 nodes, **zero** node names
match `deliver|export|pre-sign|post-sign`. The only `sign`-matching names are the
four in this page plus two unrelated `signal` frames on another page. T4 cannot
start.

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
