# A PROOF-CLASSIFICATION COMMENT DESCRIBES HOW A STATE IS **PROVED**, NOT WHAT THE RENDERER **DOES**

**Ratified by the owner, 2026-09-05, from an error of mine that reached him as a
statement of fact.**

> **Hypothesize from reading. Report only after running.**

A renderer in this codebase carries two vocabularies that look like one. There
are **proof kinds** — `blank`, `filled`, `kept_default`, `emptied` — which say
how a field's outcome is ATTESTED to a certificate. And there is the **write
path** — patch, bounded clear, leave alone — which says what happens to the
doctor's bytes. The comments that explain the first are the easiest thing to
find when you go looking for the second, and they are dense, careful and
confident. **They are also answering a different question.**

⚠️ **REFERENCE CASE, AND THE COST WAS A FALSE STATEMENT TO THE OWNER.** Asked
whether wrapping a paragraph in a content control could cause its text to
disappear from a note, I read the proof-classification comments around
`blank` / `blankEligible`, concluded that an unfilled control is merely *not
credited*, and told him wrapping would not omit anything. **The renderer does
bounded-clear nulls.** The real hazard was the exact inverse of what I
reported: sixteen controls whose pre-printed clinical prose was meant to STAY
would have been erased. I self-corrected within the hour, but the correction
was mine to make only because I later ran the thing instead of reading it.

⚠️ **AND IT RECURRED THE SAME DAY, ONE LAYER SHALLOWER, WHICH IS WHY IT IS
CANON AND NOT AN ANECDOTE.** Checking which files knew a new status, I grepped
the `template-twin` directory, got three hits, and stated that *the renderer
has never heard of it*. The renderer lives in `note-template-docx`. It handles
the status explicitly, in a branch with a twenty-line comment about it. **A
`NOT FOUND` measured my pattern before it was a fact about the code** — the
already-recorded shape — and the conclusion I drew from it was the strongest
available: not "I did not find it" but "it does not exist".

**The two errors share one mechanic.** Both times I answered a question about
BEHAVIOUR by reading PROSE, and both times the prose was accurate about its own
subject. Nothing was wrong with the comments. The defect was routing a
behavioural question to a documentary source and then reporting the answer with
the confidence appropriate to a measurement.

**THE PRACTICE:**

- A question of the form *what does this do to the doctor's document* is
  answered by rendering a document, or by reading the CONTROL FLOW that
  produces the bytes — never by the commentary alongside it.
- When a comment and a code path both appear to answer, the code path is the
  authority and the comment is a hypothesis about it.
- State provenance in the sentence itself. *"Reading the renderer, I believe X"*
  and *"I rendered one and X"* are different claims, and only the second should
  be allowed to end an enquiry.
- ⚠️ **The trap is that the comment is usually RIGHT.** These comments were
  right. A wrong comment gets caught; a right comment answering the wrong
  question is believed, quoted, and passed upward.

**Related:** the `NOT FOUND` measures your pattern entry; *record a hypothesis
because it was refuted*; and the mirror of this one — a documented-unreliable
instrument is not a permanently-wrong one.
