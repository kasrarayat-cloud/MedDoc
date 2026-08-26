> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **26 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## ERR TOWARD THE EDGE — THE EDGE HAS A FENCE

**Standing 2026-08-23. Found by the loop's adversarial pass over its own diff,
refuting its own first design.**

> **A BOUNDS CHECK CATCHES A READ THAT RUNS OFF THE END, NEVER A READ OF THE
> NEIGHBOUR. When an indexed clinical write can err, err toward the EDGE,
> because the edge has a fence.**

An off-by-one on a table-cell index has two directions and they are **not
symmetric in safety**:

| direction | what happens | what the doctor sees |
|---|---|---|
| **over-shoot** (offset 0 → 1) | `cellIndex >= cells.length` — the existing bound check fires | fails closed to a **blank**. Visibly missing |
| **under-shoot** (offset 1 → 0) | no guard exists; the index is valid | reads a **real neighbouring value**. Silently WRONG |

**An absent field is content the doctor did not see. A wrong field says the
opposite of the record being signed.** The language-level guard only ever
protects the first direction, so a design that can slip either way should be
biased toward the one the runtime already fences.

**Concretely, on this seam:** a label-column offset that guesses HIGH lands past
the row and blanks; one that guesses LOW writes the diameter into the reflux
cell. Both are wrong; only one is discoverable by the person reading the note.

### ⚠️ AND THE PASS THAT FOUND IT ALSO CAUGHT A CITATION OF THIS FILE OVER-REACHING

The design it refuted justified ignoring the header/row delta by **citing
canon's double-tap entry**. The entry forbids inferring WHICH END is short from
a `+1` delta; it does not license discarding the delta as evidence. Three lenses
produced two wrong-cell writes **introduced by the fix**, neither present in the
code it replaced.

> **CITING CANON IS A CLAIM, AND A CLAIM NEEDS EVIDENCE. Misapplied canon is
> inference wearing canon's clothes** — and it is more persuasive than ordinary
> inference precisely because the rule it names is real.

Check that the entry says what the argument needs it to say, on the axis the
argument is using. Both halves of that sentence matter: the entry was real, the
axis was not.

