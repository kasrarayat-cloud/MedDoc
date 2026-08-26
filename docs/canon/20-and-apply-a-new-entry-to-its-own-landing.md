> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **33 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## ⚠️ AND APPLY A NEW ENTRY TO ITS OWN LANDING

**Standing 2026-08-23. Cheap, and it is the only test an entry gets before it
becomes precedent.**

The `GATE ON THE OBJECT THE GATE READS` entry was written because a citation
taken from the workflow run disagreed with the check-run that actually gates a
merge. **Its own PR was then verified by reading the check-runs**, not the
workflow runs — and that is what confirmed its waiter's silence was a genuine
in-flight state rather than a stuck instrument.

> **An entry you cannot apply to the commit that lands it is an entry nobody
> will apply later.** Running it once, immediately, on your own work is the
> difference between a rule and a paragraph.

This is the same move as the instrument-grant rule, which grants the script its
own entry names in the same commit. Both exist because **writing a lesson down
is not obeying it** — this file has a recorded case of an author violating his
own merged commit message days later.
### ⚠️ THE COROLLARIES, EARNED IN THE SAME SESSION AS THE ENTRY ABOVE

**Standing 2026-08-24.** Four refinements, three of them from misses made
*after* the entry above was written and merged — which is the argument for them
being mechanical rather than remembered.

#### 1 · EVERY ZERO YOU PRODUCE IS YOUR INSTRUMENT UNTIL PROVEN OTHERWISE

The survivorship is the evidence, and it is one-sided:

| zeros that SURVIVED scrutiny | what saved them |
|---|---|
| `0` visits written since deploy start | a partition reconciling to the declared totals |
| `0 of 8` captions carrying both tokens | a positive control (8 of 8 carry one) |
| `0` occurrences of a control string | an explicit negative control run beside it |

| zeros that were WRONG | what produced them |
|---|---|
| `0 rows` for the manifest population | wrong JSON key — `resolutions`, it is `fields` |
| `0` for the landed acceptance clause | **case-sensitive grep against prose I had written myself** |

> ⚠️ **SELF-AUTHORED PROSE IS THE HIGHEST-RISK GREP TARGET, NOT THE LOWEST.**
> You remember the meaning and mistype the casing, the emphasis markers, the
> hyphenation. The text you wrote is the text you are least able to search
> literally — and a zero there reads as *"my change did not land"*, which is
> alarming, plausible, and false.

**A zero is a measurement only when it arrives with a control or a
reconciliation. Otherwise it is a token-match with an opinion.**

#### 2 · CHECK QUERIES PARTITION `status` FIRST, `conclusion` SECOND

`conclusion != "success"` counts a RUNNING check as a failure — its conclusion is
`null`. Measured live: `5 non-success` on a PR whose true state was
**4 running · 0 failed · 3 passed**, reconciling to 7.

    running = status != "completed"
    failed  = status == "completed" AND conclusion != "success"
    passed  = conclusion == "success"

Three named buckets that add to the total. **Two fields collapsed into one
predicate is this file's most-repeated defect; here it manufactures alarm rather
than false calm, which is the direction nobody guards.**

#### 3 · A WATCHER MATCHING ON CONTENT SEES ITS OWN AUTHOR

A monitor polling for PRs whose title matches an item fires on **your own** PRs
about that item. Benign — but read every event for **who filed it** before
treating it as somebody else's activity. Cousin of the `pgrep -f` self-match,
one layer out: not a probe that cannot return false, but one whose population
silently includes the observer.

#### 4 · A RATIFIED CHANGE OF SCOPE LANDS BEFORE THE BUILD FINISHES, NOT AFTER

**`RELAY.md` is the builder's INPUT. This conversation is not.** An acceptance
that is agreed in a transcript and not yet merged is invisible to the actor
doing the work — and arrives as a correction to finished work rather than as a
requirement.

**Reference case:** F24-S5's acceptance was sharpened while the loop was already
building the slice. Landing it immediately put the target *and* the known trap
where the builder reads them; holding it until the next report would have
produced a proof aimed at the wrong field class, correctly built.

> **If a decision changes what "done" means, it is not delivered until it is on
> `main`.**

