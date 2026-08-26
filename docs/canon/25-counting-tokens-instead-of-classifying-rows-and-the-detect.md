> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **43 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## COUNTING TOKENS INSTEAD OF CLASSIFYING ROWS — AND THE DETECTOR THAT CAUGHT ALL FIVE

**Standing 2026-08-23. One session, five instrument defects, ONE shape and ONE
detector.** Filed as a synthesis because the uniformity is the finding: these
did not look alike while they were happening.

> **Every miss was COUNTING TOKENS instead of CLASSIFYING ROWS.**
> **Every catch was an INCOHERENT VALUE left loud.**
> **Keep impossible values loud — tidying them is how all five would have
> shipped.**

| # | the token count | the incoherent value that caught it | the real answer |
|---|---|---|---|
| 1 | `grep -c 'axis=note-shape'` on a watcher's output | **16 note-shape AND 1 specialty**, against a partition printing 50 rows | it matched the script's own **legend lines**; 15 / 0 — unmoved |
| 2 | `ls \| grep -cE '^[0-9]{14}'` for migration dirs | **105 in repo, 106 applied** — more applied than exist | the pattern excluded `0000_init`; 106 / 106 |
| 3 | `comm` over `git ls-tree` paths vs bare names | **everything divergent in BOTH directions** | a `sed` that never fired; zero divergence |
| 4 | three tries at the highest ruling number | **`#100` as the max** with `#141` known to exist | lexical sort, then PR numbers 739–809 swept in |
| 5 | a poll loop with no exhausted/satisfied distinction | **`conclusion: null` on a "completed" check-run** | the loop fell through on TIMEOUT and printed a verdict |

⚠️ **NOT ONE WAS CAUGHT BY A TEST, A GATE, OR A REVIEW.** Each was caught
because a number could not be true. That is the whole mechanism, and it is
free — but only if the impossible value is allowed to reach a human instead of
being normalised on the way.

**#1 is the one that had teeth.** A MOVED count on that watcher IS a deploy
finding, and it was inside a post-deploy judgement. Reported as `16 / 1` it
would have manufactured a finding that did not exist, on a deploy that was
clean — and every later reader would have inherited it.

**WHY THE SHAPE REPEATS.** `grep -c`, `wc -l`, `sort`, `uniq -c` all answer
*"how many lines carry this string"*. Almost every question worth asking is
*"how many ROWS are of this kind"* — and a file's prose, legends, comments and
headers are exactly where the string appears without the kind. The tool is
always right; it is answering the other question.

**THE PRACTICE, and it is one line of shell:**

1. **Anchor on the row's SHAPE, not its content** — `^\s+c[a-z0-9]{24}\s` for a
   cuid row, `\*\*#[0-9]{1,3} —` for a ruling row. A legend cannot satisfy a
   row anchor.
2. **Carry a positive control that names a known member** — `#141` was known to
   exist; `#100` as the maximum refuted the matcher instantly.
3. **Make the partition reconcile against a total you did not compute the same
   way.** Four of the five above are visible purely as arithmetic.
4. ⚠️ **NEVER NORMALISE AN IMPOSSIBLE VALUE.** `?? 0`, `|| echo 0`, `// "-"`,
   a default, a coalesce — each converts *"this instrument is broken"* into a
   plausible number. **The null and the backwards count were the only reasons
   any of this was found.**

### ⚠️ THE THREE-LAYER ECHO — one lesson, three altitudes, one arc

**Recorded because the repetition is the finding.** F24's single lesson —
**ASK THE THING THAT KNOWS; DO NOT CLASSIFY WHAT RESEMBLES** — fired at every
layer of the same work:

| layer | what classified instead of asking | what it cost |
|---|---|---|
| **editor** | `captionFor` took whatever line sat above as a caption | a RIGHT-leg correction written into the LEFT leg |
| **predicate** | `isDataColumnHeader` judged a column by whether its text *looked* like a measurement | `Vein Size` misread as data — a diameter written into the reflux cell |
| **measurement** | a census predicate that *resembled* the shipped function | 670 for 441; 25 for 9 |

⚠️ **"THE TWIN KNOWS ITS COLUMNS" WAS THIS ENTRY'S OWN OPENING SENTENCE, AND IT
IS MEASURED FALSE.** *Previous wording, kept because the correction is the
point:* **"The twin knows its columns.** `captionFor` has a real definition. The
table has a real boundary. **In all three, something authoritative was available
and a resemblance was consulted instead."**

The other two clauses stand. The first is corrected by the entry below:
the twin knows its **geometry** and not its **columns**.

### ⚠️ AND THE AUTHORITY ANSWERS SOME OF YOUR QUESTIONS, NOT ALL OF THEM

**Standing 2026-08-23. The refinement the echo entry needed, measured on the
one certified twin in production.**

*Ask the thing that knows* is right, and it is not self-executing. **An
authority consulted about a question it cannot answer still RETURNS
SOMETHING** — and what it returns is a resemblance, arriving with an
authority's credibility attached. That is strictly worse than the heuristic you
replaced, because nobody audits an answer that came from the source of truth.

> **ENUMERATE WHICH QUESTIONS THE AUTHORITY CAN ANSWER, BEFORE ROUTING ANY
> QUESTION TO IT. "It is the authority" is a claim about the OBJECT; "it can
> answer this" is a claim about the FIELD.**

⚠️ **REFERENCE CASE — the compiled twin, asked two questions, and it knows
exactly one.** Ruling #140 orders the label column resolved *"from the twin's
compiled structure — it knows its columns"*. Measured:

| the question | can the twin answer it? |
|---|---|
| **is there a row-label column, and where?** | ✅ **YES, structurally, with no text at all** — 0 of 52 table-cell fields sit at column 0, across all 28 rows |
| **which column is the diameter?** | ❌ **NO** — and it answers anyway |

The second is the trap. `compiler.ts:803-819` labels an ambiguous table cell by
a **precedence in which the LEFT NEIGHBOUR beats the table header**:

    leftLabel ? {source:"left_cell"} : headerLabel ? {source:"table_header"} : …

On a measurement grid the first data column's left neighbour is the populated
**row label**, so it wins — all 26 of `cellIndex` 1's fields are labelled with a
**vein name** (11 distinct). Column 2's left neighbour is an *empty* form-field
cell, so it falls through to the real column header (1 distinct). **An index
route taking `cellIndex → role` from that twin resolves a COLUMN role out of a
ROW label** — the identical class the arc was fixing, re-entering through the
fix for it.

⚠️ **AND THE TELL WAS A FIELD NAME, NOT A NUMBER.** The counts (26 / 26) look
perfectly healthy. `labelSource` is what discriminates, and it is only
meaningful because the compiler was READ rather than the labels being eyeballed.
*Read to form a hypothesis; RUN something — or read the shipped function — to
name a mechanism.*

**AND THE BLOCKER WAS BEING READ WIDER THAN IT WAS WRITTEN.** *"The IR stores
only `staticTextSha256`"* is true and is about header **TEXT**; it had been
carried as though it blocked the twin route entirely. It does not touch the
structural route at all. **A recorded blocker is scoped to the sentence that
records it — re-read the sentence before inheriting the conclusion.**

