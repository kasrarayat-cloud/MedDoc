# LIFECYCLE — a compile-time rule needs a recompile-and-recertify path

**Filed 2026-09-02 by ruling #164 item 5.**

## The gap, stated precisely

`assertSourceMatchesIr` recompiles the source on every fill and compares
`structureSha256` against the STORED IR. That is what keeps an already-certified
twin fillable, and it is load-bearing: moving that hash makes every certified
twin in the database unfillable, with each recompute path degrading silently to
the styled export.

The consequence nobody had written down:

> **A new COMPILE-TIME protection cannot reach a template that was compiled
> before it.** The stored IR is validated, not the fresh compile — so a rule
> added today applies to uploads from today, and never to the twin already
> certified.

Measured during the #163 pass: a pre-#163 stored IR kept filling, and its
compile-time finding never fired, precisely because the hash was held stable on
purpose.

## Why nothing is due right now

**#164 ships no compile-time protection** — the hygiene detector was retired and
the blank rule is a counting change in certification, not in the compiler. So
there is nothing an existing twin is missing, and no recompile is owed today.

## What this item owes when it is due

Any future compile-time rule needs, in the same slice:

1. a way to **recompile** an existing compiled version without breaking
   `assertSourceMatchesIr` for the fills in flight;
2. a **recertify** decision — does a template that was certified under the old
   rules keep its certificate, or must a physician re-attest?
3. the **population** measured first: how many compiled versions, how many
   certified, how many would newly fail.

⚠️ **The second question is the owner's**, not a session's: it decides whether a
doctor's existing certificate survives a rule they never saw.
