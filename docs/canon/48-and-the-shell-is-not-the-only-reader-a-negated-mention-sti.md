> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **104 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ PROSE IS NEVER A SHELL ARGUMENT**.
> Why the split: `docs/canon/README.md`.

### ⚠️ AND THE SHELL IS NOT THE ONLY READER — A NEGATED MENTION STILL CLOSES THE ISSUE

**Standing 2026-08-25. Same disease, different interpreter, and this one has no
`-F` to hide behind — the file IS the payload.**

`--body-file` defeats the SHELL. It does nothing about **GitHub**, which parses
the same prose for `<keyword> #<number>` and closes the issue on merge.

> **GITHUB'S LINKED-ISSUE PARSER HAS NO CONCEPT OF NEGATION.** *"It does not fix
> #603"* contains `fix #603`, and that is the entire input it sees. **The
> sentence written to disclaim a fix is the sentence that closes the issue.**

⚠️ **REFERENCE CASE, AND THE DISPOSITION DEFEATED ITSELF.** A
**documentation-only** PR — one file, `RELAY.md`, no helper, no test, no
application code — closed a live issue on merge:

    closed     at=2026-08-25T21:58:53Z
    referenced at=2026-08-25T21:58:53Z commit=43ac4cd9…

Source located exactly: **the PR BODY, line 59**. The commit message carried no
keyword — checked with the same pattern, so the two were distinguishable.

**The blast radius is what makes it a rule rather than a tidy-up.** That same
change closed **#745** as a duplicate **of #603**, on the stated reasoning that
an alarm must survive in a live parent rather than be discarded. The accidental
close produced:

| | |
|---|---|
| #745 | closed, pointing at #603 |
| #603 | closed, pointing at **nothing** |
| the security-shaped half — a session cookie alive 10s after sign-out | **no open home at all** |

**Precisely the outcome the disposition existed to prevent, produced by the
disposition itself**, and invisible from either issue: both read as tidy.

⚠️ **IT WAS CAUGHT BY ARITHMETIC, NOT BY REVIEW** — open issues read **8** at
STEP 0 and **6** at close-out, and only **one** had been closed deliberately.
*Arithmetic that does not reconcile is a finding*, one unnamed bucket wide.

**THE CHECK IS ONE GREP OVER THE BODY FILE BEFORE `gh pr create`:**

    grep -niE '(close[sd]?|fix(e[sd])?|resolve[sd]?)[[:space:]:]+#[0-9]+' <body-file>

Run against the offending body it returns exactly line 59 — **it discriminates,
and it costs nothing.** Any hit is read as *"this WILL close that issue"*, and
the sentence is rewritten or the reference backticked. Safe forms: *"does not
resolve the defect in #603"*, *"#603 is untouched"*.

⚠️ **AND IT REDDENED AGAINST ITS OWN AUTHOR ON FIRST EXECUTION, WHICH IS THE
BEST EVIDENCE IN THIS ENTRY.** Run against the commit message *landing this
rule*, it returned a hit: line 15, `closed #745` — a keyword directly before a
reference, in the sentence describing the accident. Rewritten before the push.

> **The author who had just diagnosed the defect, was writing the rule against
> it, and knew the exact pattern, committed it again one paragraph later.** That
> is not carelessness; it is the reason the check has to be MECHANICAL rather
> than remembered — the same argument the shell-argument rule above makes, and
> the same failure it records (*"it was written by a session that had used `-F`
> correctly all day"*).

⚠️ **AND THE HABIT GENERALISES PAST GITHUB.** Anything you hand a machine is
parsed by that machine's grammar, not by yours: prose reaching a shell, an
issue tracker, a templating engine, a model's tool schema. **`-F` bought safety
from ONE reader.** Ask, every time, *which parsers see this text* — the answer
is rarely one.


---

## ⚠️ AND THE GUARD RAN POST-HOC TWICE, SO IT BECAME A DOOR

**Appended 2026-09-06.**

This entry's own remedy — *scan the body file for a closing keyword
next to an issue number before `gh pr create`* — was followed twice by one session and **prevented
nothing both times**, because the grep was piped in the same breath as the
create. It reported on a PR that was already open.

| when | the body said | outcome |
|---|---|---|
| PR #967 | a body naming PR #951 after the verb *closed* | already closed; harmless by luck |
| PR #1005 | the same verb, narrating what GitHub itself had done to PR #951 | narrative; no link created, confirmed by GraphQL |

**Neither did harm and neither was prevented.** The check was performed
correctly, reported accurately, and could not have stopped anything — it ran
second. That is canon 93's shape: *a rule that depends on remembering has a
failure rate; when it fails twice, stop restating it and start counting.*

> **`bash scripts/create-pr.sh` is the door.** The scan runs BEFORE the create
> and a match is a REFUSAL, not a warning printed next to a URL.

⚠️ **AND IT CARRIES A POSITIVE CONTROL ON ITS OWN REGEX**, because a guard whose
pattern silently stopped matching would report every body clean forever. It
refuses to run unless its pattern still matches a known offender.

⚠️ **THE CONTROLS MATTER AS MUCH AS THE ARMS.** A bare issue URL and a body that
merely names `#946` and `#951` must NOT trip it — a guard that fires on every
`#N` gets disabled within a day, and a disabled guard is worse than none.

The legitimate override is a DECLARATION, never a flag:
`DECLARE_INTENTIONAL_CLOSE="…"`, refused as a bare token or under 20 characters.
