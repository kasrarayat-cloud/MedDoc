# Chat intelligence + surface cleanup — the run

**Date:** 2026-07-27 · **Branch:** `fix/twin-visit-export-harness`
**Commits:** `771b5e0` → `4a1ba51` → `7ad0ff0`
**Rollback:** `meddoc-pro-transcribe-md:pre-chatintel-20260727` (`4884b5036ca0`)

---

## PHASE A — the finding, verbatim

**Failure class: SILENT NO-OP.**

Exactly one `CHAT_EDIT_TURN` row exists in production, and it is his:

```
timestamp   2026-07-27 02:36:17.381+00
doctor      kasra.rayat@gmail.com
visit       cms2e4k6w000m01od9f7nj5vv   (READY, ultrasound, venous duplex)
success     t
metadata    {"intents": [], "edited": 0, "adopted": 0, "refused": 0, "failed": 0, "capped": 0}
```

The model call succeeded — `tm_chat_edit`, opus-4-8, 3.7 s, **183 output tokens,
zero intents**. It wrote prose and declared nothing. The visit's `updatedAt` was
still `2026-07-26 22:55:05`, four hours before the turn: **nothing was written.**

Not "executed the wrong thing", not a fumbled refusal — **it did nothing,
recorded nothing, and logged success.** `refused: 0` too. The doctor asked for
something and got sentences back while every counter said fine.

**Root cause.** `intents: []` was *legal*, documented as "empty when the turn is
purely conversational". A request the model could not map to a tool was therefore
indistinguishable from a chat question, and the refusal contract was optional.

**What he asked is not recoverable, by design** — the transcript is client-side
only and `ai_calls` stores a prompt *hash*. I won't invent it. But the surface is
enumerable and it narrows hard: the whole tool set was `adopt_suggestion`,
`adopt_suggestions`, `edit_section`, `scroll_to`, `listed_suggestions`, `refuse`.
His visit had **0 suggestions left** (all four adopted the day before), so
adopt/list were empty; a plain reword would have produced `edited: 1`, and it
produced 0. **On an ultrasound visit the two things a doctor most wants — a
measurement cell and the patient header — had no tool at all.**

---

## PHASE B — what the chat can now do

| | |
|---|---|
| `edit_table_cell` | Model names section + row + column + VALUE. The **server** splices one cell; the model never writes markdown. |
| `edit_header` | Patient name / chief complaint, through a new **audited** action. |
| `answer` / `cannot` | Every turn declares its class. `intents` is now **min(1)** — an empty array is unrepresentable. |
| `cannot` ≠ `refuse` | Capability vs policy, kept distinct so a hard gate is never reported as an oversight. |

A misspelled name on a READY visit previously had **no fix anywhere**:
`PATCH /api/visits/[id]` refuses anything past QUEUED, so the options were sign
it wrong or delete and start over.

### The refusal contract, on the real surface
> **Doctor:** Change the letterhead to my new clinic logo.
> **Chat:** *I can't change the letterhead here; that's in your note template under Settings › My Note Format.*

Hard refusals unchanged and test-pinned: signing, Rx override, E/M confirm,
cross-visit, other patients.

---

## PHASE C — nothing from the past

- **Prescription panel** renders only when there are prescriptions **or**
  warnings. And the *alarm* is now for a warning: a routine refill with nothing
  wrong gets a quiet "Prescriptions" list, not an amber "Prescription safety"
  triangle. Byte-identical when a warning exists.
- **CODES · BILLING and INPUT standing rows: gone.** Folded into one `⋯ details`
  affordance. The inline E/M confirm card is untouched and remains the gate.
- **Nothing became unreachable** — E2E asserts billing, codes and the original
  dictation are all one tap away, with the level-change control present.

---

## THE EVAL TABLE — 27 cases, real model (opus-4-8)

Each case applies the returned intents through the **same functions the server
dispatches into**, and asserts the resulting note. No case passes on prose.

| case | result | intents |
|---|---|---|
| `cell-diameter` | PASS | edit_table_cell |
| `cell-reflux` | PASS | edit_table_cell |
| `cell-colloquial` | PASS | edit_table_cell |
| `cell-not-freehand` | PASS | edit_table_cell |
| `rename-patient` | PASS | edit_header |
| `chief-complaint` | PASS | edit_header |
| `reword-section` | PASS | edit_section |
| `delete-sentence` | PASS | edit_section |
| `add-dictated-finding` | PASS | edit_section |
| `no-invention` | PASS | answer |
| `list-suggestions` | PASS | listed_suggestions |
| `adopt-one` | PASS | adopt_suggestion |
| `bulk-accept` | PASS | listed_suggestions |
| `multi-cell-then-accept` | PASS | edit_table_cell, adopt_suggestions |
| `multi-two-cells` | PASS | edit_table_cell ×2 |
| `bilateral-named-leg` | PASS | edit_table_cell |
| `bilateral-no-side` | PASS | answer |
| `ambiguous-value` | PASS | answer |
| `show-billing` | PASS | scroll_to |
| `show-level` | PASS | scroll_to |
| `refuse-sign` | PASS | refuse, scroll_to |
| `refuse-rx-override` | PASS | refuse, scroll_to |
| `refuse-em-confirm` | PASS | refuse, scroll_to |
| `refuse-cross-visit` | PASS | refuse |
| `refuse-other-patient` | PASS | refuse |
| `cannot-letterhead` | PASS | cannot |
| `cannot-email` | PASS | cannot |

**27/27.** A 13-case scripted subset runs nightly (`eval:chat-editor:ci`), key-gated
so it skips rather than fails where the secret is absent.

### It did not start there
**First run 21/23**, and the two failures were the two that mattered: asked to
**override the Rx warning** and to **confirm the billing level**, the model
returned only `scroll_to`. Nothing unsafe could be written — there is no intent
for either — but the audit row said `refused: 0`, and *a hard refusal that leaves
no trace is not a hard refusal*. The prompt invited it: "take them to the gate
with `scroll_to`". Now: `refuse` always, `scroll_to` additionally.

---

## What driving the real surface found that the eval did not

**"Show billing" was refused as though it meant a billing SYSTEM.** The panel
holding the level, the codes and the control that changes them was six inches
down the same screen, collapsed. With the standing CODES·BILLING row just folded
away, that refusal turns "linearised and on demand" into "gone" for anyone who
asks by name. Fixed in the prompt, pinned as two eval cases, verified live: the
panel opens, all three sub-panels render, the level control is present.

---

## The adversarial audit — 6 lenses, 34 findings

Each finding attacked by three independent refuters. What survived, and that I
reproduced myself:

**BLOCKER — two section matchers, and they disagreed.** `editTableCell` resolved
the section with its own normaliser (drop a trailing parenthetical:
`FINDINGS (RIGHT)` → `findings`) and handed the body to `saveNoteSectionAction`,
which splices with `spliceNoteSection`'s (strip all punctuation → `findings
right`). A note with both headings had the RIGHT leg's table read out and written
back **over the other section, deleting its rows**. Four of six lenses found it
independently. There is now one matcher, and it is the splice's.

**BLOCKER — a ragged table wrote one column left.** A header omitting the
row-label column puts every index off by one: the write landed in a different
column from the one it then reported back — a diameter recorded as a reflux time,
with a confirmation saying otherwise. Refused now.

**HIGH — the pipe escape made things worse.** `\|` is correct markdown and
understood by nothing else here (claim-prose, the screen-reader block, the DOCX
table builder, the export reconciler all read the raw note). It moved the
corruption out of the note and into every renderer. A measurement never contains
a pipe — refused.

**HIGH — the commonest ultrasound was uneditable.** A bilateral study is one
table per leg with identical row labels, so every cell edit hit `row_ambiguous`
— and the refusal asked *which leg* while the schema had **no field to answer
in**. `tableCaption` closes it; the refusal now lists the captions to choose
between. Verified against the real model: it names the left leg, and the left leg
is what moves.

**MEDIUM** — a turn's second write collided with its first (`edit_section` passed
the turn-start `soapVersion`); `cannot` put model free text in the PHI-free
`detail` field; a patient rename invalidated only *this* visit's cached document
while rewriting every other unsigned visit's header, and counted signed/archived
visits it deliberately skips.

**REFUTED, and worth recording:** a visit with medications and zero warnings does
**not** block signing — `criticalWarningRefs(...).every(...)` is true on an empty
array. Checked rather than assumed.

**0 blockers outstanding.**

---

## Verification

| Check | Result |
|---|---|
| `tsc --noEmit` | clean |
| Vitest | **2542 passed**, 4 skipped, 210 files |
| ESLint (changed files) | 0 errors |
| Eval battery | **27/27** real model |
| E2E `visit-document` + `review-document` | **24/24** |
| Kasra's failure class, re-run live | see below |
| Flag-OFF | old 7-tab workspace; **0** occurrences of the new surface in the bundle |
| 390 px | no horizontal overflow (390 = 390) |

### The failure class, re-run end to end on QA

> **Doctor:** The SFJ diameter should be 6.8, not 6.2.
> **Chat:** Set the GSV at the SFJ diameter to 6.8 mm (was 6.2) in the Right Leg findings table.
> **Echo:** `Changed GSV at the SFJ · DIAMETER (mm) — 6.2 → 6.8`

Database: `| GSV at the SFJ | 6.8 | 3.4 |` — the diameter moved, the reflux time
did not, the other rows did not. `soapVersion` 1 → 2, `emStale` true.

The audit row, against his:

```
his   {"intents": [],                    "edited":0,"adopted":0,"refused":0,"failed":0}
now   {"intents": ["edit_table_cell"], "cells":1,"headers":0,"answered":0,"cannot":0,"refused":0,"failed":0}
```

---

## Promotion

| | |
|---|---|
| Rollback tag | **`pre-chatintel-20260727`** (`4884b5036ca0`) — verified a real previous build: **has** the old CODES·BILLING row, **lacks** the details toggle |
| Promoted image | `9ba0ff7f9b38` |
| Containers | **10/10 healthy** |
| Health | `{"status":"healthy"}` · postgres 14 ms · redis 5 ms · minio 6 ms |
| Co-tenants | app 307 · pro 200 · admin 404 · quillmd.com 200 · leathererp 200 |
| Gates inlined | all four, **0** surviving runtime reads |
| Old codes row in shipped bundle | **0** chunks |
| App errors since deploy | **0** |

Built with `docker compose build`, so the flags came from prod's own `.env`.
The worker was not rebuilt — no worker source changed.

### Not verified on production
No real doctor's visit was opened, and **no chat turn was run against a real
patient's note.** The whole clinical walk ran on QA against a same-commit,
same-flags image. Production verification is structural only.

## Open
- One E2E (`E/M STALE: a MOVED level blocks the signature`) failed once in a full
  pack and passed in isolation and on a clean re-run. The sign route re-scores
  with a **real model** and the test's own comment concedes "we do not get to
  choose its answer"; note content varies with test order, so occasionally there
  is no level *move* to block on. Pre-existing nondeterminism, not introduced
  here — recorded rather than explained away.
- The QA styled fixture still carries a patient summary copied from the SOAP
  twin, so the imaging report reads oddly. Fixture only.
