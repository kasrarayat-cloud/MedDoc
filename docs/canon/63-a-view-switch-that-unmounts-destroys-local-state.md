# A VIEW SWITCH THAT UNMOUNTS DESTROYS LOCAL STATE — AND THE GATE IT WAS HOLDING

**Ratified 2026-08-27. The reference case for any two-view surface.**

> **The obvious implementation of "switch between two views" is a ternary. A
> ternary UNMOUNTS the view you switch away from — and anything that view was
> holding in local state goes with it.**

⚠️ **REFERENCE CASE — F8-S2, caught in recon, before a line was written.**
Ruling #153 put the coding surface on the visit page via a two-view switch. The
visit's paper carries a constraint stated in its own source: it *"is never keyed
and never conditionally mounted"*, because `ReviewDocumentView` holds the
**in-session E/M confirmation in local state**, and changing its React identity
*"would silently re-block Sign and read as a flaky gate."*

A ternary produces exactly that, and the walk is four steps with no error in it:

| # | what the doctor does | what happens |
|---|---|---|
| 1 | confirms the E/M level | the confirm is held in local state |
| 2 | switches to Coding | **the paper unmounts, the state is destroyed** |
| 3 | switches back to Note | the paper remounts, the confirm is **gone** |
| 4 | tries to sign | **Sign is blocked again — no explanation, nothing to click** |

**No error. No log line. No existing gate watching.** The doctor's only evidence
is that the button stopped working, and the only remedy they can guess at is the
one that already failed.

**THE FIX IS TO HIDE, AND IT IS TWO MECHANISMS, NOT ONE.** The `hidden`
attribute for the accessibility tree, **and** an inline `display:none` for the
mechanics — because `hidden` is implemented as a **UA-stylesheet**
`display:none`, which **any author rule with higher specificity defeats
silently**, leaving a panel *visible on screen* while telling assistive
technology it is absent. One mechanism is a coin flip against the next
stylesheet change.

## ⚠️ AND THE ASSERTION IS A MOUNT COUNT — "STILL IN THE DOM" IS SATISFIED BY A REMOUNT

This is the half that makes the entry worth having, because it is where the
obvious test is worthless.

> **The obvious assertion — *"the note panel is still in the DOM after the round
> trip"* — is TRUE of the broken implementation.** A ternary that unmounts and
> remounts leaves the node right there, looking correct, with the state gone.
> **The presence check passes on the exact defect it was written to catch.**

**So assert the MOUNT COUNT**, behaviourally: the component must mount **once**
across a full round trip through the other view. That is the property the local
state actually depends on, and it is the only one a remount fails.

**THE GENERAL SHAPE, and it is not about React:** when the thing you must
preserve is *identity over time* rather than *presence at a moment*, a
point-in-time check cannot see the defect. Count the transitions, not the
occupants.

⚠️ **HONEST LIMIT, ACCEPTED AND RECORDED:** these render arms **cannot execute
in a worktree at all**, so CI is their only home and a single CI run is the only
place the mount-count proof has ever executed. That is a known cost of the
worktree discipline, not a gap to be closed by weakening the proof.
