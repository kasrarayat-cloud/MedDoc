# A DECISION MADE AT WRITE TIME MUST BE RE-DERIVED WHERE IT IS USED

**Recorded 2026-09-02, ruling #168, after the same defect appeared three times
in one arc at three different boundaries.**

## The shape

A writer decides something and encodes the decision in a LABEL. A later reader
consumes the label and acts on it. In between, the artifact is stored — and the
store cannot express *why* the label was chosen.

    render time:  this control is a dropdown, so it may not claim blank
                  -> writes kind: 'filled'
    read  time:   sees kind: 'emptied' in a database column
                  -> counts it

Nothing is corrupted. The reader is simply believing a conclusion it has no way
to check.

## Three instances, one arc

| the decision | where it was made | how it was defeated |
|---|---|---|
| the field was patched to empty, so `emptied` is earned | renderer | a stored `emptied` with no expectation certified |
| the encounter said nothing about this field, so it may claim blank | renderer | relabelling a FILLED entry to `blank` certified |
| this control is a selection, so it may never claim blank | renderer | relabelling a selection's entry to `emptied` certified |

Each was closed the same way and the pattern is the rule:

> **Re-derive the decision at the point of use — and when it cannot be
> re-derived, CARRY it and say which one you have.**

⚠️ **THE FIRST VERSION OF THIS ENTRY SAID "from a source the stored artifact
cannot rewrite", AND THAT WAS MEASURABLY FALSE.** The source the gate re-derives
from is `compiledDocumentIr`, a mutable JSON column on the SAME row as the proof
it adjudicates — a forger editing one can edit the other. It is caught today
only because two independent gates hash the manifest against the IR, which makes
it a MULTI-column forgery rather than an unforgeable derivation.

And re-derivation is not always available. A field's KIND is in the compiled IR,
so it can be re-derived. Whether the field's paragraph carries NUMBERING is not:
it lives in the source document's `w:pPr` and in `styles.xml`, neither of which
the certification path reads. That decision has to travel WITH the proof, and
the honest limit is stated where it is carried — a forger editing the stored
proof can flip it.

The certification gate already opens the compiled IR to resolve bindings, so the
field's KIND and its RESOLVED VALUE were in hand at no extra cost. Three checks,
zero new data.

## ⚠️ THE TELL, WHICH IS AVAILABLE BEFORE ANYTHING IS MEASURED

Ask of any label you are about to trust: **what would I do differently if this
were wrong, and can I tell?** If the answer to the second half is no, the label
is an assertion the reader is repeating, not a fact the reader has.

And ask it about the WRITER too: *"the renderer will not emit this kind unless
it actually performed the clearing"* is a true sentence about the renderer and
says nothing about a row in a database, which is where the reader is looking.
Three files stated that invariant in terms while the read path could not see it.

## The honest limit, which must be stated with the cure

Re-deriving from the IR proves the label is CONSISTENT with the compiled
template. It does not prove the artifact was rendered from it — that needs the
stored output re-scanned, which is filed separately. A cheap re-derivation is
worth having and is not the same as verification; saying which one you have is
the whole discipline.
