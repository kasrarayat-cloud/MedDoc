> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **17 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## ⚠️ AND TWO MECHANISMS FOR ONE SYMPTOM, BOTH WRONG, IN ONE NIGHT

Same night, same symptom, and the lesson is about ORDER rather than care:

| proposed | refuted by |
|---|---|
| "the signed view falls back to a different renderer" | `visit-ready-view.tsx:787` already guards that whole block with `!isSigned`; `:1116` routes signed visits to a surface that renders the document |
| "the uncertified twin's native-fill half-fills the PDF" | **0** twin compiled versions for that template, **0** in the entire database, **0** fill manifests |

Both were reached by READING code and were plausible. **One had a fix and a
paragraph of explanatory comment already written before verification killed it —
and the comment was the worse artifact**, because a wrong mechanism stated
confidently in a source file outlives the session that wrote it.

> **Read to form a hypothesis; RUN something to name a mechanism.** The
> reproduction that settled it took one command and produced a number
> (`NUMID-SEQUENCE`) that no amount of further reading would have produced.

**And the good half is worth copying:** the second wrong mechanism was caught by
the author verifying his own fix before shipping it, which is the cheapest
possible moment. Verify your own change against the code it claims to fix, not
against your memory of what you read.

