> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **79 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## AN EXEMPTION'S REASON IS PROSE, AND PROSE DECAYS SILENTLY

**A gate can keep an exemption PRESENT. It cannot keep it HONEST.**

An exclusion list — exempted files, allowlisted paths, "known acceptable"
findings — carries two things: an entry, and a REASON. A check can assert the
entry still exists and still matches the shape it was written for. It cannot
assert the reason is still true, because the reason is a sentence about code
somewhere else.

> **Re-read an exemption's justification BY HAND whenever the code it describes
> is touched.** Nothing else will.

⚠️ **REFERENCE CASE, 2026-08-10 — B4 vs the metering gate.**
`gate-mock-suite-stubs-the-db.test.ts` exempted `embed-mock.test.ts` with the
reason *"embed.ts:72 returns mockEmbed() under mock, ABOVE the logApiUsage calls
at :123/:162 — the meter is never reached."* True when written. **B4 moved that
mock boundary below the meter, and the sentence became false** — while the gate's
stale-exemption arm stayed green, because the file still existed and still named
the flag. Both of the things it checks remained true.

The removal was caught by the session doing B4, reading the exemption because it
was touching the code it describes — not by any check. This is the watched-set
rule (§"A gate's WATCHED SET is diffed against the spec's NAMED set") pointed at
an EXCLUSION list instead of an inclusion one, and it is the more dangerous
direction: an exclusion that goes stale removes coverage silently, and the gate
keeps reporting zero.

### ⚠️ SO WRITE THE EXEMPTION WITH ITS RETIREMENT CONDITION IN THE SAME SENTENCE

**Standing 2026-08-17. The constructive half of the entry above — that one says
how exemptions rot; this one says how to stop it.**

> **An exemption is written WITH the condition that retires it, in the same
> sentence. Then checking whether it still applies is a LOOKUP, not a
> judgement — and a lookup is something a tired session at 03:00 actually
> performs.**

The entry above prescribes *re-read the justification by hand whenever the code
it describes is touched.* True, and it depends on somebody noticing the code was
touched. **A named retirement condition does not:** it turns an open question
into a closed one anybody can answer without reconstructing the reasoning.

⚠️ **REFERENCE CASE — A CLEAN DEATH, WHICH IS WHY IT IS WORTH RECORDING.** A
§2.5 carry-forward exemption was written *"it may live in the shared tree
because it can only be named after a post-merge sha — **and it retires WITH
F10**"*. **F10 shipped under nine hours later** (`c0ee3994`); the gate began
resolving declarations by ancestry; the forcing condition vanished; and the
exemption was **deleted before it ever landed.** The rule that replaced it is
SHORTER than the exemption was.

⚠️ **THE COUNTERFACTUAL IS THE ARGUMENT.** That exemption was **RATIFIED,
correct when written, and one mechanical landing away.** A ratified staged file
reads as settled and nothing in the landing would have questioned it. Had the
retirement condition been a rationale PARAGRAPH instead of a CLAUSE, it would
have shipped and become permanent — not by anyone's error, but because **no step
exists whose job is to ask "is this exemption still true?"**

**Two habits follow, and the second is the cheaper one:**

1. **Name the retirement condition as a TESTABLE EVENT** — an item id, a flag, a
   migration, a shipped fix. *"Until we have time"* and *"for now"* are not
   conditions; they never become false.
2. **RE-READ YOUR OWN STAGED AND UNLANDED WORK AGAINST WHAT SHIPPED WHILE IT
   WAITED.** Anything held for a window is evidence about a tree that has since
   moved — *"evidence is only evidence on the tree it describes"*, applied to
   your own drafts. This one was caught by a routine status check reading a
   merge and asking what it invalidated.

