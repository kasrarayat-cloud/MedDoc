# Q1 fix-pack — carry-over items

A living list, unlike the dated triage reports it descends from
(`docs/qa-reports/q1-fixpack-triage-20260610T183416Z.md` and its ancestors).
Items land here when a run finds something real, decides **not** to fix it in
that run, and would otherwise lose it to a commit message.

Both entries below came out of the read-only-paper work (PR #419 and its
close-out). Neither blocks anything shipped.

---

## CPT-93970 — a spoken procedure code did not reach PROCEDURES

**Found:** 2026-07-28, prod smoke on the read-only-paper deploy.
**Status:** open. Logged, deliberately not fixed in that run.

A bilateral venous duplex was dictated with the CPT spoken aloud (93970) and the
note's **PROCEDURES section came back with 0 entries**. The code was in the
transcript; it did not reach the structured procedure list.

Not a regression from the review-page work — that change removed the *rendering*
of the codes table, and this is upstream of it, in L7b CPT coding. It is visible
now only because the codes panel used to make it look like something had been
captured.

Related, and probably the same neighbourhood:
`docs/qa-reports/specialty-deep-audit-20260512T182300Z.md` §G4 — L7b emits 93971
(limited) where 93970 (complete bilateral) is the accurate code for a
both-legs study. That one is a prompt-strengthening note; this one is a
zero-capture. Worth looking at together.

**Where to start:** `src/worker/layers/07b-cpt-coding.ts`, and whether a CPT
spoken as digits survives L3 extraction at all.

---

## Speaker-role reassignment — removed, and the case for bringing it back

**Decided:** 2026-07-28. `reassignSpeakerAction` deleted, not rehomed.
**Status:** closed as built; reopen only against the design note below.

`reassignSpeakerAction` lost its only caller when the input-transcript panel
came off the review page. The obvious rescue — surface it through the chat
editor — was considered and rejected on two grounds:

1. **It needs the surface that was deleted.** To reassign a speaker you must
   first see *which* speaker is wrong, which means reading utterances attributed
   to speakers. Putting that in the chat rebuilds the transcript panel inside
   the chat.
2. **Decisive: it changed nothing about the artifact being signed.** The action
   mutated `speakerMap` and never re-ran the pipeline — its own success toast
   read *"Re-running the SOAP pipeline will pick up the new roles."* On a
   pre-sign review page the note is already written. A control that appears to
   fix attribution while the document underneath it does not move is the
   pretend-success class, and actually realising it needs a regenerate, which
   would discard the doctor's edits.

The `SPEAKER_ROLE_REASSIGNED` audit action is **kept** in `lib/audit.ts`: rows
written before this date still reference it, and an audit enum that forgets its
own history makes its own records unreadable.

**If it comes back, it belongs before the pipeline runs, not after the note
exists** — a correction on the transcript, at a point where re-deriving the note
from it costs nothing, because nothing has been reviewed or edited yet. That is
a different feature in a different place, not this one re-hosted.
