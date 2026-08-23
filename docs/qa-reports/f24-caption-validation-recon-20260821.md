# F24-CAPTION-VALIDATION — recon

**Measured 2026-08-21, production, STRICTLY READ-ONLY.** FOUNDATION loop, run
`20260821-224030-b1` session 01. Nothing built; this is the map.

> **The item, as filed:** *"deciding what a caption IS. Product-shaped; its own
> recon."* Blocks bilateral tables from being edited at all, and bilateral is
> the main ultrasound case.

---

## 0 · THE INSTRUMENT, AND WHY IT LOOKS THE WAY IT DOES

The whole census runs **inside Postgres**. Notes are split into lines, classified,
and only **category labels and counts** are emitted — **no note text ever left the
database**, and none appears in this report. That is F12-g's posture applied to a
different question.

**Traversal controls, taken before any number below was believed:**

| control | value |
|---|---|
| notes with a non-empty `soapFinal` | 49 |
| lines scanned | 2,329 |
| pipe rows | 531 |
| alignment rules | 45 |
| **table headers found** | **45** |

45 headers **reproduces the figure already in the ledger**, from an independently
written matcher. Rules == headers, as it must be.

**The section boundary was READ, not assumed.** `captionFor` runs over a SECTION
BODY, so my whole-note approximation is only valid if it splits where
`readNoteSection` splits. `splice-note-section.ts:68-75` — *"The section runs to
the next heading of any level"*, `HEADING_RE = /^\s{0,3}#{1,6}\s+(.+?)\s*$/`. It
splits on `###` as readily as on `##`. My approximation (nearest preceding
heading of any depth) is behaviourally the same boundary.

---

## 1 · THE PARTITION — every header lands in exactly one bucket

| tables in section | line directly above the header | count |
|---|---|---|
| **1** (ambiguity impossible) | heading | 16 |
| **1** | text | 1 |
| **2 — BILATERAL** | blank | **20** |
| **2 — BILATERAL** | text | **8** |
| | | **45** ✔ |

17 single-table + 28 bilateral = 45. Sections: 17 with one table, 14 with two.

### ⚠️ CORRECTION 1 — the denominator is 28, not 45

A caption is consulted **only** when `matches.length > 1`
(`note-table-edit.ts:211-237`). The headers in single-table sections mostly never
reach that branch: their row labels are unique in the section, so the edit
succeeds with no caption at all.

> **The blocked figure is 20 of 28 bilateral tables — 71% — not 20 of 45.**
> The item is worse than its own headline in the population that matters, and
> covers 17 fewer tables than the headline implies.

#### ⚠️ AND THIS CORRECTION NEEDED ITS OWN CORRECTION — CAUGHT BY MEASURING MY OWN CLAIM

The first draft of this section said *"the 17 headers in single-table sections
**never** reach that branch."* **That is too strong, and the check that found it
was asking what `matches.length > 1` actually depends on.** It depends on the ROW
LABEL repeating within the SECTION — which does not require two tables.

Measured: **2 of the 17 single-table sections carry a genuinely repeated row
label** (not an empty first cell and not a dash placeholder — those were
classified out explicitly; the bilateral sections carry 138 such groups, as
expected).

⚠️ **AND A CAPTION CAN NEVER FIX THOSE TWO, WHICH IS WHY THEY ARE A DIFFERENT
DEFECT.** Both matching rows sit in the **same table**, so they share the same
header *and the same caption*. The narrowing at `:211-217` compares captions;
with one table, `narrowed.length` is **2**, never 1. So:

- with a caption, the caller is offered **two identical choices**;
- with none — and **both of these sit under a heading**, measured, so
  `captionFor` returns null — it is **`caption_not_found`**.

That is the *"unanswerable question"* shape Slice 1b was written to kill,
**surviving in a form Slice 1b's fix cannot reach**: 1b made an empty `choices`
list honest, and this case produces either an empty list or a list of duplicates,
for a reason no caption strategy addresses. **Filed here, out of this item's
scope** — a caption addresses a TABLE, and this is two rows inside one.

**So the population that can reach the ambiguity branch is 30, not 28**, and the
count that reaches an unanswerable refusal is **22** — 20 bilateral-with-no-
caption plus these 2.

### ⚠️ CORRECTION 2 — "green on the 25 of 45 whose caption sits ADJACENT" is false as stated

`45 − 20 = 25` is **arithmetic over the blank count**, not a classification.
Measured: only **9** headers have any adjacent non-blank text line. The other
**16 sit directly under a `##` or `###` HEADING**, and `captionFor` returns
`null` on a heading (`note-table-edit.ts:146`).

**Those 16 are editable because they are UNAMBIGUOUS, not because they have a
caption.** The number was right and the mechanism was not — and the mechanism is
what a fix gets built on. A fix keyed on *"the 25 that have captions"* would be
built for a set in which 16 members have no caption.

⚠️ This is **the third instance of the same shape in one slice**: a count over a
quantity (a blank, a delta, a subtraction) answering a question about a **kind**.
See `AGENTS.md` **"THE DOUBLE TAP"**.

---

## 2 · THE KIND CENSUS — what those lines actually ARE

The question the earlier census never asked. 25 text candidates
(9 adjacent + 16 one-blank-up), classified by shape alone:

| slot | sides named | sentence punctuation | words | n |
|---|---|---|---|---|
| ADJACENT | none | no | 2 | 1 |
| ADJACENT | left only | no | 2 | 4 |
| ADJACENT | right only | no | 2 | 4 |
| ONE_BLANK_UP | left only | no | 2 | 6 |
| ONE_BLANK_UP | right only | no | 2 | 6 |
| ONE_BLANK_UP | left only | no | 4 | 2 |
| ONE_BLANK_UP | right only | no | 4 | 2 |

**Every candidate in production is ≤ 4 words, names AT MOST ONE side, and
carries NO sentence punctuation.** Zero exceptions in 25.

The refuted counterexample — *"The right leg was normal; the left GSV is
dilated."* — violates **all three**: it is long, it names **both** sides, and it
carries sentence punctuation.

### The structural corroboration, and it needed no reading

For the 14 bilateral sections, the pair of candidate lines reads:

| pair | sections |
|---|---|
| **`right` + `left`** (in that order) | **12** |
| `nontext` + `nontext` | 2 |
| `BOTH` sides on one line | **0** |
| same side twice | **0** |
| no side named | **0** |

**A narrative paragraph does not systematically alternate right-then-left across
twelve independent notes.** That is content-free evidence that these lines are
captions — obtained without a single character of a note being read.

### ⚠️ WHAT THIS CENSUS CANNOT DO, STATED BEFORE IT IS CITED

**It cannot show the withdrawn widen was safe, and it must never be read that
way.** That widen was refuted by **running the function** and producing a
wrong-leg write. This census describes what 49 notes *happen to contain today*;
no result it could have produced would have refuted the reproduction.

What it does provide is **measured support for a VALIDATOR** — and a validator
whose failure mode is to **REFUSE** is a tightening: on an unrecognised line it
reproduces exactly today's behaviour, and it can never write to a table it could
not name.

---

## 3 · ROUTING — which fix reaches which tables

The 28 bilateral headers, by template binding and by the disambiguator available:

| disambiguator | CERTIFIED-TWIN tpl | no template | other tpl | **total** |
|---|---|---|---|---|
| ADJACENT — **works today** | 4 | 2 | 2 | **8** |
| ONE_BLANK_UP — blocked | 2 | 12 | 2 | **16** |
| **NO CAPTION ANYWHERE** — blocked | 0 | 4 | 0 | **4** |
| **total** | **6** | **18** | **4** | **28** ✔ |

### ⚠️ CORRECTION 3 — the twin route adds ZERO on today's blocked set

The item's noted direction is *"the editor asking the TWIN which table is
which… `rendererBinding.rowLaterality` is populated 80 of 80."*

**Measured on production's one compiled twin (`617d6de9…`, CERTIFIED):**

| `rowLaterality` | `bindingType` | fields |
|---|---|---|
| `right` | `table_cell` | 26 |
| `left` | `table_cell` | 26 |
| `unknown` | `content_control` | 28 |
| | | **80** ✔ |

Two things follow, and they point opposite ways:

- **The good half is better than the row claims.** The twin knows a real side for
  **52 of 52 table cells** — `0` table cells are `unknown`. The 28 `unknown` are
  content controls, which are not in tables and have nothing to disambiguate.
- ⚠️ **"populated 80 of 80" is vacuous as a claim.** `ir.ts:72` declares
  `rowLaterality: z.enum([...]).default('unknown')` — **every** field carries the
  key by construction. *Populated* was never the question; *knows a side* is, and
  the answer is 52, not 80. A count that cannot come out any other way is not
  evidence.

**And the coverage answer is the decisive one** (canon: *ask which production
rows the proof covers, and count them*):

- **6 of 28** bilateral headers are on the certified-twin template.
- **2 of the 20 blocked** — and both are already in the ONE_BLANK_UP bucket, which
  a validated read serves. **Incremental reach of the twin route over a validated
  read, today: 0 headers.**
- **The 4 headers with NO caption anywhere — the only ones no caption strategy can
  ever serve — are ALL on no-template visits.** The twin cannot reach a single one.

⚠️ **This is not a refutation of the direction.** The twin route is
forward-looking by nature: once the pilot doctor works on the certified template
the mix shifts, and it is the only route that is *semantically* certain rather
than heuristic. What must not happen is adopting it **on the belief that it
covers the blocked population**, because measured, it does not.

⚠️ **And it is not free plumbing:** the recon already recorded **0 twin refs in
the edit path** across `chat-edit-visit.ts`, `note-table-edit.ts` and
`intent.ts`. The twin route is new wiring, for 0 incremental tables today.

---

## 4 · THE TWO CAPTION READERS DISAGREE — latently, not live

`note-table-edit.ts:147` returns the whole line. `claim-prose.ts:75` splits on
` — ` / ` – ` / ` - ` and keeps **the tail** (*"DIAMETER AND REFLUX TIME — Right
Leg"* → *"Right Leg"*).

| measurement | value |
|---|---|
| adjacent text candidates | 9 |
| …carrying an em-dash separator | **0** |
| **control**: any line in the corpus with that separator | **94** |
| **control**: lines containing any dash | **417** |

The matcher works (94 hits elsewhere), so the zero is real: **the two readers
return identical strings on every production caption today.** The divergence the
code comment warns about is real in code and **currently unexercised** — which is
exactly the condition under which it ships unnoticed the day a template starts
emitting titled captions.

---

## 5 · DIRECTION — noted, NOT ruled

This is recon. Nothing here is a decision.

1. **A caption VALIDATOR that reads one blank up and FAILS CLOSED.** Supported by
   §2: ≤ 4 words, at most one side named, no sentence punctuation. On anything
   else it refuses — byte-identical to today's behaviour, so it is a strict
   tightening that can only add capability. **Reaches 16 of the 20 blocked.**
2. **It must move BOTH readers**, or the codebase holds two definitions of
   "caption" and a disagreement between them is a wrong-table edit waiting to
   happen (`claim-prose.ts:71`).
3. **The 4 no-caption-anywhere headers are out of reach of any caption
   strategy.** They need the twin (0 reach today), a generator-emitted caption
   marker (forward-only, retroactively 0), or an explicit ask. **No single
   candidate covers the blocked population, and the one with the most reach is
   the one already refuted on safety** — which is precisely why the item is
   validation and not distance.
4. ⚠️ **The acceptance must be a REPRODUCTION on the real function, not a
   census.** Both of Slice 1's censuses were true, correct, and licensed a fix
   that wrote a measurement into the wrong place. A third census — including
   this one — cannot discharge that.

---

## 6 · HONEST LIMITS

- **49 notes, few templates.** A discriminator supported on this corpus is
  *supported*, not *proven*. Nothing here bounds what a future dictation writes.
- **No note text was read, deliberately.** "Is a caption" is inferred from
  structure (the right+left pairing, the shape statistics), never from reading.
  That is a real epistemic limit and it is the correct trade.
- **`noteTemplateId IS NULL` is read off the column** as "no template binding". I
  did not establish *why* those 18 rows are null.
- **Line numbers are `origin/main` at `e23247cf`.** PR #788 (F24 Slice 2) touches
  **both** caption readers; they will move.
- **The census is a snapshot.** It describes production on 2026-08-21 and nothing
  else.

---

## 7 · FOUND ON THE WAY PAST — A NUL BYTE MADE A SOURCE FILE INVISIBLE TO `grep`

Not what this recon went looking for. Found because a grep for
`readNoteSection` returned **nothing** on the file that defines it.

`apps/transcribe-md/src/lib/splice-note-section.ts:109` held a **NUL byte inside a
string literal** — `spliceNoteSection(markdown, label, '<NUL>probe')`. It was
committed on `main`; `git show origin/main:… | file -` said **`data`**.

**It was functionally INERT.** `readNoteSection` discards the spliced text and
returns `previousBody`, which is computed from the original lines — that byte
never reached a note, and no test could have seen it.

⚠️ **THE COST WAS EVERY SWEEP THIS PROGRAMME RUNS.** `file(1)` classified it as
binary, so GNU grep **suppressed its output entirely** — no matches, no
*"Binary file … matches"*, nothing:

    grep -rn spliceNoteSection --include=*.ts apps/transcribe-md/src
      -> note-table-edit.ts, the test file … and NOT THE DEFINITION SITE
    git grep -c spliceNoteSection
      -> apps/transcribe-md/src/lib/splice-note-section.ts:2

**Two instruments, opposite answers, on a live dependency of the note editor** —
this repository's own *"two zeroes with opposite meanings is one broken
instrument"* diagnostic, arriving in the tooling rather than in a query. Any
census written with plain `grep` over `apps/**/*.ts` carried a hole exactly the
size of this file and would have reported a confident zero.

**ENUMERATED, not assumed:** `git grep -lP "\x00"` over every tracked `.ts`,
`.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.json`, `.md`, `.sql`, `.sh`, `.yml`,
`.yaml`, `.css`, `.html` returns **exactly one file** — this one. The `-P`
matcher is positive-controlled (54 hits for `'` in a known file). **The class has
one member and it is now closed.**

**FIXED** — the byte is removed (scripted, with an occurrence assertion: expected
1, found 1, 0 after). **GUARDED** —
`gate-tracked-source-has-no-nul-bytes.test.ts`, with a non-vacuity floor
(≥ 900 files scanned; `git ls-files` reports 1,244) and a **named control** that
the offending file is in the scanned set, because *"the sweep found no NULs"* and
*"the sweep never opened this file"* are the identical output.

**Mutation-proved in both directions.** It read **1 before the fix and 0 after**,
so it MOVED when the fix landed. Injecting a NUL into a *different* file
(`table-header-shape.ts`) turns it **RED naming that file**; restored **from a
scratch backup, never `git checkout`**, verified byte-identical by sha256, and
green again.

---

## ⚠️ ADDENDUM — 2026-08-23, supervised re-measurement

**The 20 and the 8 were re-derived independently and BOTH reproduce. What
changes is what the 8 MEAN.**

### The two figures reconcile against the shipped predicate

A separately-written census (different author, different SQL, same read-only
posture) returns the identical partition:

| tables in section | line above header | count |
|---|---|---|
| 1 | heading | 16 |
| 1 | text | 1 |
| 2 — bilateral | blank | **20** |
| 2 — bilateral | text | **8** |
| | | **45** ✔ |

And it reconciles with the *other* session's corrected figure —
**9 of 45 headers supply a caption** — which was derived from the shipped
`captionFor` rather than from this partition. `captionFor` returns null on a
blank line, on a heading, and on a pipe row; only plain text survives. So
`1 + 8 = 9`, and `20 of 28` bilateral are refused. **Two numbers, two sessions,
two routes, one measurement.**

### ⚠️ WHAT THE PARTITION'S FRAMING HIDES, AND HOW THE MEASUREMENT ANSWERED IT

The table above reads as *"20 blocked, 8 working"*. That framing deserves a
challenge, because `captionFor` performs **no validation** — it returns whatever
prose sits above. Under the ratified error-direction asymmetry, an accepted
wrong caption is worse than a refusal, so the 8 could be the *higher*-risk
bucket rather than the working one.

**Hypothesis: some of the 8 are ordinary narrative that the substring narrowing
would mis-match, silently writing a correction into the wrong leg.**

**Measured — and REFUTED:**

| of the 8 accepted captions | count |
|---|---|
| contain a laterality token (`left`/`right`) | **8 of 8** |
| contain **BOTH** tokens — the shape that mis-narrows | **0 of 8** |

Every one is a genuine single-laterality caption. The wrong-leg reproduction in
`note-table-edit.ts:143-153` requires a line carrying **both** tokens; production
holds **zero** such lines directly above a bilateral table.

> **So the 8 are correct today — by the phrasing the notes happen to use, not by
> any validation. The defect is real and currently UNEXERCISED.** That is a
> materially different claim from "8 are working", and it is the one to carry
> forward: the fix is still caption VALIDATION, and its urgency comes from the
> 20 refusals, not from a live wrong-leg risk.

**Honest limit:** `0 of 8` is a fact about the population on 2026-08-23, not a
property of the code. One note whose narrative names both legs directly above a
table re-arms the path with no code change anywhere.

**Posture:** strictly read-only, counts only; no note text left the database and
none appears above.
