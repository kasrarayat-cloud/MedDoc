# F8 — the ICD-10 Coding tab: design input

**This document is the build's contract.** It supersedes any palette asserted in
conversation.

⚠️ **EVERY COLOUR HERE IS A TOKEN REFERENCE, NEVER A DICTATED HEX.** The war room
asserted hex values from the redesign spec and they were wrong. The values below
were MEASURED from the files the build imports, then CONFIRMED against a running
page — see "Provenance". **The tab matches the LIVE Rounds system, whatever its
values are. If the redesign ships later, the tab inherits the new tokens with
everything else** — because it references tokens, not numbers.

---

## Provenance — how these were obtained

`app/layout.tsx:10-11` imports `globals.css` and `rounds-tokens.css`. Those are
the files the build reads.

Measured 2026-08-16: `globals.css` declares **40** distinct custom properties
(41 lines); `rounds-tokens.css` declares **76** distinct (85 lines — 9 are
redeclared under skin selectors, which is the whole point of the file).

⚠️ **AN EARLIER DRAFT OF THIS PARAGRAPH SAID "45" AND "54". BOTH WERE WRONG** —
they match no measure of either file (declaration lines, distinct names, or
`var()` references). They were carried from a note rather than measured, in the
one document whose entire thesis is that numbers are measured. Corrected before
merge, and left on the record here because **the failure mode this doc exists to
prevent showed up inside the doc itself.**

**Verified twice, independently:**

1. **From source** — declarations read out of `rounds-tokens.css`.
2. **From a running page** — `getComputedStyle(document.documentElement)` on the
   QA stack (same tokens as production), which also reported
   **`data-skin="rounds"`**, confirming the skin is live rather than assumed.

Both agree exactly. That agreement is the evidence; either alone is a claim.

## The screenshot — what it is, and what it is not

`docs/foundation/f8-live-rounds-palette.png` — the **QA stack's sign-in page**,
captured live.

⚠️ **IT IS NOT A VISIT PAGE, AND IT IS NAMED THAT WAY ON PURPOSE.** The
`qa-auditor` account's password is operator-held (`QA_AUDITOR_PASSWORD`), and I
declined both alternatives: hunting an operator credential, and signing up a
fresh user who would have no visits to photograph anyway. **A capture labelled
as something it is not is worse than no capture.**

**What it does evidence, in real pixels:** the stage background, a
`--rounds-surface-1` card on `--rounds-line-1` at `--rounds-radius-lg`, the
`--rounds-accent` button, the three text tiers, and the mono-uppercase **kicker** label
treatment the tab reuses (*WELCOME BACK · EMAIL · PASSWORD*). Those are exactly the primitives the coding tab is built from.

**What it cannot evidence:** the visit-page tab bar and the two-column split.
Those come from the spec below, not from a photograph.

**The doc's authority rests on the tokens, verified two independent ways — not
on this image.** Adjudicated before committing: no patient data, no
credentials, both fields empty.

## The measured palette

| role | variable | value |
|---|---|---|
| app background | `--rounds-stage-bg-2` | `#171d27` |
| stage, deeper / lighter | `--rounds-stage-bg-3` / `-1` | `#12161e` / `#232b3a` |
| panel surface | `--rounds-surface-1` | `#161b24` |
| raised surface | `--rounds-surface-2` / `-3` | `#1e2530` / `#252d3a` |
| border, default | `--rounds-line-1` | `#2c3442` |
| border, emphasis | `--rounds-line-2` | `#3a4353` |
| primary accent | `--rounds-accent` | `#5b5bd6` |
| accent, on dark text | `--rounds-accent-text` | `#a5a5f0` |
| accent hover / on-accent | `--rounds-accent-hover` / `--rounds-on-accent` | `#4a49c4` / `#fff` |
| accent tints | `--rounds-accent-tint-10` / `-16` | `rgba(91,91,214,.1)` / `.16` |
| text primary / secondary / tertiary | `--rounds-text-1` / `-2` / `-3` | `#e7ebf1` / `#98a2b1` / `#7c8694` |
| **success** | `--rounds-ready` / `--rounds-ready-text` | `#187a4e` / `#6ee7a8` |
| **warn** | `--rounds-em` / `--rounds-em-fill` / `--rounds-em-text` | `#c4841c` / `#e29a34` / `#e8b168` |
| **error / critical** | `--rounds-critical` / `--rounds-critical-on-dark` | `#c93a2e` / `#ff8d7e` |
| info / processing | `--rounds-processing` / `-text` | `#3b6fd4` / `#7ab0f5` |
| neutral / signed | `--rounds-signed` / `-text` | `#6b7480` / `#9aa4b2` |
| paper (the note itself) | `--rounds-paper-1` / ink | `#fcfcfa` / `#191e26` |
| ink muted | `--rounds-ink-muted` | `#525a66` |
| radius | `--rounds-radius-sm` / `-md` / `-lg` | `9px` / `12px` / `18px` |

### ⚠️ THERE ARE **TWO** KICKER CLASSES, AND THE TAB WANTS THE DARK ONE

This is the one place a careless read of this document ships a contrast defect,
so it is stated as a rule rather than a note:

| class | colour | for |
|---|---|---|
| `.rounds-kicker` | `--rounds-ink-muted` `#525a66` | **PAPER only** — the note surface |
| **`.qm-rounds-kicker`** | `--rounds-text-3` `#7c8694` | **DARK surfaces — use this one** |

`.qm-rounds-kicker` is `10.5px` / `letter-spacing: .06em`; `.rounds-kicker` is
`11px` / `.08em`. **Both are already written — reuse, do not re-specify.**

### ⚠️ A TOKEN NAMING A STATE OR A FILL NEEDS ITS `-text` VARIANT BEFORE IT IS USED AS TEXT

**This is not my rule — `rounds-tokens.css` states it in its own comments, with
the measurements, and records FOUR instances of it being learned the hard way**
(`--rounds-em`/`-em-fill`, `--rounds-accent`/`-accent-text`,
`--rounds-signed`/`-signed-text`, `--rounds-ready`/`-ready-text`).

Measured there: `--rounds-ready` `#187a4e` is **3.392:1** on
`--rounds-stage-bg-3`, **3.233:1** on `--rounds-surface-1`, **2.661:1** at worst
— it **fails AA as text**. `--rounds-signed` lands near **3.7:1** and also fails.

**What that means for this tab, concretely:**

- confidence **bar fill** → `--rounds-ready` ✅ · the **"92%" text beside it** →
  `--rounds-ready-text`
- the ACCEPTED section **border** → `--rounds-ready` ✅ (a line, not text)
- REJECTED label text → `--rounds-signed-text`, never `--rounds-signed`
- an amber **button fill** → `--rounds-em-fill`, **never `--rounds-em`** (the
  file says so in as many words)

⚠️ **AND THE FILE CORRECTS A NUMBER IN ITS OWN HISTORY:** *"near 2.3:1" stood
there until 2026-08-01 and was wrong.* Do not carry 2.3 forward — the conclusion
survived, the measurement did not.

---

## The tab

**Visit page tab bar: `Note · Documents · Coding`.**

### Layout — desktop two columns, ~65 / 35

#### LEFT — the code list

**Header:** summary chip — *"N suggested · N accepted · N needs review"* — plus a
**search-add typeahead over the allowlist** (604 codes — see Constraints), so a doctor can add a
code the suggester missed without leaving the tab.

**Sections:**
- **SUGGESTED** — ranked by confidence, expanded
- **ACCEPTED** — collapsed, border `--rounds-ready`
- **REJECTED** — collapsed, muted `--rounds-signed-text`

**Each card carries:**
- **code** — mono, large (`--rounds-font-mono`) + official description
- **confidence** — bar + % · **≥90** `--rounds-ready` · **70–89** `--rounds-em` ·
  **<70** muted with a `low confidence` tag
- **the `evidence_quote`** — italic, quoted, truncated, with **"View in note"**
- **verification badge** — *"Billable — verified"* (`--rounds-ready`) /
  *"Not in verified set"* (`--rounds-em`)
- **[Accept]** primary (`--rounds-accent`) + **[Reject]** ghost.
  Accepted swaps to a check + **[Undo]**.

#### ⚠️ THE AMBER RULE — owner-decided: SHOW, never hide

A validation-rejected code renders as a **distinct warn-state card**
(`--rounds-em`, `--rounds-em-text` on dark) **naming the reason** —
*"K21.0 is a category header — not billable"* — with a one-tap
**"Use K21.00 instead"** chip when a billable child exists.

**Why this is a rule and not a preference:** 59 production rejections exist today
and the doctor has never seen one. **A suggester that silently loses candidates
teaches the doctor to distrust the list**, and a distrusted list is worse than no
list.

#### RIGHT — the evidence panel, bound to selection

- code + official description
- **2–3 note excerpts** with the supporting phrases highlighted
- metadata rows: **Source section · Specialty · Confidence**
- footer, verbatim: *"Suggestions are validated against the ICD-10-CM billable
  set. The physician makes the final coding decision."*

### States

| state | |
|---|---|
| default | suggested list + evidence panel |
| amber-header | one or more validation-rejected codes present |
| empty | no suggestions — **search-add is the path**, not a dead end |
| loading | skeleton cards, *"Analyzing note…"* |
| mobile 390 | evidence becomes a **bottom sheet** |
| **signed visit** | **read-only; decisions frozen** |

---

## Constraints

**(a) evidence** and **(b) allowlist validation** are **already satisfied by the
existing engine**, verified at source for this document:

| claim | verified where | reading |
|---|---|---|
| evidence is mandatory | `07a-icd-coding.ts:22` | `evidence_quote: z.string().min(1)` |
| codes are validated | `07a-icd-coding.ts:447` | `if (isValidIcd10(c.code))` |
| allowlist size | `packages/ai/src/data/icd10-allowlist.ts` | **604** — read as `ICD10_ALLOWLIST.size`, through the Set, never by counting lines |
| rejections in production | `audit_logs` | **59**, re-measured for this document rather than carried forward |

(`07a-icd-coding.ts` is `apps/transcribe-md/src/worker/layers/`.) **(c) accept/reject authority**,
**(d) an audit row per accept/reject**, and **(e) specialty-aware RANKING** (the
specialty reaches generation today, not ranking) are the new work. Full measured
delta and the population figures: **F8's row in `docs/foundation/RELAY.md`,
added by PR #682** (the recon). If that row is not there yet, #682 has not
merged — this doc landed first, and the two are read together.

**Build after F5** per the queue. **`frontend-design` SKILL.md + live tokens
only — never an invented value.** ⚠️ **The adversarial pass is MANDATORY:** a
code accepted here reaches a signed record.
