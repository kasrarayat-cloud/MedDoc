# A MATRIX COPIED FROM A COMMIT MESSAGE IS A CLAIM, NOT A MEASUREMENT

**2026-09-06. Owner canon, from a PR body that presented another session's
numbers as measurement and was believed — including by the session that wrote
it.**

## WHAT HAPPENED

ADMIN-5's PR body carried a results table under the words *"Measured against the
real QA Postgres"*:

    unguarded, same timing   UPDATE 1 / UPDATE 1  -> 0 owners
    demote || demote         UPDATE 1 / UPDATE 0  -> 1 owner

The session that wrote that body **did not run the harness**. It lifted the
table from the author's commit message, reformatted it, and attached the phrase
that turns a claim into evidence.

**The harness cannot produce those numbers.** Its `race()` builds a heredoc
whose terminator line carries the redirect and the `&`, so bash swallows the
second script into the first heredoc's body; the two "racing" statements execute
**sequentially in one session, outside a transaction**, and the capture files are
never written. Verified three ways — CI's empty strings, a bash reproduction
emitting *"here-document delimited by end-of-file"*, and a psql reproduction
showing both UPDATEs run in one backend.

## ⚠️ THE RELAY IS WHAT MAKES IT DANGEROUS

A number in a commit message is the author's claim, and the author is entitled
to make it. **What laundered it was the copy.** Restated in a PR body by a
second session, under "measured", it acquired a corroboration that never
happened — two artifacts agreeing because one was transcribed from the other.

> **Two documents saying the same thing are one source until you can name the
> two measurements.**

This programme has the shape on record twice already: a ledger row pre-written
in the past tense corroborating a session prompt about a reboot that never
happened, and a brief asserting *"the rulings are all there, grep it"* when four
were not. **The relay is the failure, not the original claim.**

## THE RULE

**A results table in a PR body is the HARNESS'S OWN OUTPUT, pasted from a run,
or it is labelled as somebody else's claim and attributed.** There is no third
form. *"Measured"* is a word about who ran what, and using it for a number you
did not produce is not shorthand — it is the only part a reader cannot check.

⚠️ **AND THE CHECK IS CHEAP, WHICH IS THE UNCOMFORTABLE PART.** Running the
harness once would have shown the empty capture strings immediately. The cost of
the error was not difficulty; it was that a table already formatted as evidence
does not look like a question.
