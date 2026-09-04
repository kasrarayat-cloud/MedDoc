> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **58 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A DETECTOR CAN BE BLIND TO THE THING IT MOST EXISTS TO WATCH

**Standing 2026-08-14.** `rounds-axe.ts` decided whether a modal was open with:

    d.offsetParent !== null || d.getAttribute('data-state') === 'open'

⚠️ **`offsetParent` IS ALWAYS NULL FOR `position: fixed`.** The Rounds gate flow
is `role="dialog" aria-modal="true"` on `position: fixed; inset: 0`, carrying
`data-step` but not `data-state` — so it satisfied **neither** arm, and the
focus-trap assertion had **never once been applied to the primary modal of the
surface.** The Rounds chat drawer was invisible for the same reason.

**Nothing said so, because the count was non-zero.** The override modal — which
IS also `position: fixed`, via an inline style, and was detected only because
Radix stamps `data-state` on `Dialog.Content` — supplied every `modalStates` the
walk ever counted. **It took DELETING the one dialog the detector could see for
the zero to appear**, and only then did the non-vacuity guard fire.

> **A detector that silently covers half of what its name implies is
> indistinguishable from one that works. The tell is never a red test — it is
> the count that never moves, and a count nobody expected to move looks
> healthy.**

**And the correction needed its own correction:** the first version of this note
said the override modal was NOT `position: fixed`. It is; the inline style is
just not in its class. Verified rather than assumed, on the second pass.

### ⚠️ TWO MORE OF THE SAME FAMILY, FROM ONE RECON — F8, 2026-08-16

Both produced a confident number about the wrong thing, and both were caught by a
control rather than by re-reading the query.

**THE RE-EXPORT TRAP.** Parsing the ICD-10 allowlist reported **`codes: 0`**. The
file grepped was `packages/ai/src/index.ts`, which RE-EXPORTS the symbol and
contains none of the data; the array lives in `data/icd10-allowlist.ts`. A zero
from the wrong file is indistinguishable from an empty allowlist — and an empty
allowlist would have been a spectacular finding, reported with total confidence.

> **A grep that resolves a SYMBOL has not found its DATA.** Barrel files exist to
> make imports tidy and measurements wrong.

**THE SHAPE ASSUMPTION.** Counting stored codes with `jsonb_array_length("icdCodes")`
errored: `cannot get array length of a non-array`. The column is an OBJECT with a
`codes` key — 43 objects, not 43 arrays. **The error is the lucky case**: had the
column been an array of something else, the query would have returned a number
and it would have been the wrong number.

> **Ask what SHAPE the data is before asking how much of it there is** —
> `jsonb_typeof` costs one query and turns an assumption into a measurement.

### ⚠️ TWO ZEROES WITH OPPOSITE MEANINGS IS **ONE BROKEN INSTRUMENT**, NOT TWO FINDINGS

**Contributed by the GI session, 2026-08-14, and it is the cheapest reading of a
broken probe there is.** Verifying R5 in production, it grepped the running APP
container for two source files and got:

    rx-tab.tsx            0   ← must be GONE      ✔ looks like a pass
    prescriptions-card.tsx 0   ← must EXIST        ✘ looks like a failure

Read as two results, that is "the deletion worked and the restore did not" — a
plausible, alarming, and entirely false conclusion. Read as one, it is obvious:
**a probe that answers 0 to a question whose true answer is 1 is not measuring.**
The app image ships a BUILT Next application, not a source tree, so neither path
ever resolved. Re-run against the worker with a traversal control (50 `.tsx`
files found), the real answers appeared: the deleted files 0, the restored card
1, `OVERRIDE_REQUIRED` 0 against a live control of 4.

> **When a sweep returns zeroes for things that MUST be absent AND zeroes for
> things that MUST be present, stop reading the results and check the
> instrument. The contradiction is the finding.**

#### ⚠️ AND THE FOURTH MEMBER: A PROBE THAT MATCHES ITSELF

**Standing 2026-08-16, found on its own author.** For roughly three hours a
supervised session reported the FOUNDATION loop as **LIVE** and shaped real
decisions on it — declining to touch the shared tree, and choosing a "declared
live landing" over the dark-window one the owner preferred. **The loop had been
DARK the whole time.**

The probe was `pgrep -f "foundation-loop.sh"`. **`-f` matches the FULL COMMAND
LINE**, and the session's own background waiter carried that literal string —
because the waiter's entire job was to poll for it:

    pgrep -f "foundation-loop.sh"
    → 1370001  /bin/bash -c … until { ! pgrep -f "foundation-loop.sh" …

> **A search whose PATTERN appears in the SEARCHER is a self-fulfilling probe.
> It cannot return false, and a check that cannot return false is not a check.**

⚠️ **NOTHING CONTRADICTED IT UNTIL THE LOG DID** — `pgrep` saying LIVE against a
log ending `LOOP HALTED`. That is this family's own diagnostic and it worked:
the contradiction was the finding. **The authority is
`tmux has-session -t foundation`**, which asks the thing that owns the session
rather than pattern-matching the process table.

**It generalises past `pgrep`.** Any check whose pattern is a string the
checking machinery itself carries — a grep for a filename run from a script of
that name, a log scan for a message the scanner emits, a process match from a
poller named after its target — is measuring its own reflection. **Ask the OWNER
of the state (tmux, the scheduler, the API), never the process table.**

⚠️ **AND THE COST WAS NOT NOTHING:** three hours of a dark loop nobody was
restarting, and two decisions made on a false premise. Both happened to land
well — **a wrong premise that produces a good outcome is the kind nobody
corrects.**

This is the positive-control rule with a free control already in hand: any sweep
that contains at least one must-exist row carries its own tripwire, and a
must-not-appear table without one cannot tell absence from blindness.


##### THE REMEDY, RATIFIED 2026-09-04 — BUILD THE PATTERN SO THE LITERAL NEVER EXISTS

**This entry named the disease and left the cure to improvisation, and the
improvisations fail.** Recorded after a session flip-flopped TWICE inside five
minutes on the question *"are the CI runners on this box?"* — while holding this
very entry in context.

| attempt | result | why |
|---|---|---|
| `pgrep -c -f 'Runner.Listener'` | **2** | matched its own command line |
| `pgrep -c -f 'Runner[.]Listener'` | **2** | ⚠️ the bracket was correct, and the SAME shell line also contained a literal `Runner.Listener` inside an `echo` — so the regex matched *that* |
| `ps` → file, then `grep` the file | **0** | the pattern was built by concatenation; the literal never appeared |

⚠️ **THE SECOND ROW IS THE FINDING.** `pgrep -f 'X[.]Y'` is the folk remedy, and
it is only as good as the *whole command line* it runs in. One unrelated `echo`
mentioning the thing you are looking for re-arms the defect — and it re-arms it
**silently**, because a self-match looks exactly like a hit.

**THE FORM THAT CANNOT SELF-MATCH:**

```bash
# Build the pattern from pieces. The literal is never present to be matched.
PAT="Runner"".""Listener"
ps -eo pid,etime,user,args > /tmp/snap.txt      # captured BEFORE any grep runs
grep -c "$PAT" /tmp/snap.txt
```

**AND CARRY A NONSENSE CONTROL, WHICH IS WHAT ACTUALLY CAUGHT IT.** In the run
above the control was decisive:

```
  zzqqNoSuchProcess : 1     ← must be 0. It is 1 because MY OWN command line
                              is in the snapshot, carrying every literal I typed.
  dockerd           : 2     ← the method does find real things
```

A nonsense pattern scoring **1** proves the snapshot is contaminated by the
searcher. Once that was visible, the two zeros — built by concatenation, so never
literal — could be read as **true zeros**, and `dockerd: 2` proved the method
was not simply blind. *Three probes disagreed; only the controls settled which
one was lying.*

⚠️ **AND THE COST OF NOT HAVING THIS WAS A WRONG REPORT TO THE OWNER.** The
session stated "the runners are not on this box", corrected itself to "they are",
then corrected back — publishing the middle claim. **A retraction is cheap; a
claim about where infrastructure lives, acted on, is not.** The first answer was
right, and the detour was entirely manufactured by the probe.

#### ⚠️ AND A FIFTH: **ONE SUCCESS IS NOT RECOVERY, AS ONE ZERO IS NOT ABSENCE**

**Standing 2026-08-17. Written by the author of the other four, hours after
fixing them, which is the entire argument for it being a rule.**

> **A DEGRADED service succeeds intermittently. A single successful probe
> during an outage is a BLIP, not a recovery — and a waiter with no debounce
> will report health at the first one.**

⚠️ **REFERENCE CASE.** During a GitHub incident (Actions, API, Webhooks, Issues
and Pull Requests all degraded), a waiter polling the runs API printed
**`API RECOVERED at 14:16:18Z`**. It had not. The independent check still
returned **HTTP 404**, the status page still read *Partially Degraded*, and
**six consecutive samples came back 0 ok / 6 failed.** The service had simply
answered once, at minute 19, and the waiter exited on it.

**The family, now five, and every member is the same defect wearing different
clothes — two distinguishable states collapsed into one observation:**

| # | the collapse |
|---|---|
| 1 | two zeroes, opposite meanings — one broken instrument |
| 2 | a tree that cannot resolve its own imports |
| 3 | a probe that matches its own searcher (`pgrep -f`) |
| 4 | `cited` returning 1 for PENDING and for FAILED |
| **5** | **one success read as recovery** |

**THE FIX IS A DEBOUNCE, AND IT REPORTS THE FLAP.** Require **N consecutive**
successes — three is enough — and **print when a streak BREAKS**, so
intermittency is visible as intermittency rather than being averaged into
"working". A waiter that only reports its final verdict cannot be audited.

⚠️ **AND THE CORRECT POSTURE DURING THE OUTAGE IS THE OTHER HALF OF THIS
ENTRY.** The pre-push hook refused every push — *"CANNOT TELL — the runs API
returned nothing"* — which is the fail-closed behaviour working exactly as
designed. **`DECLARE_CANCELLATION` is NOT the way past it:** that flag declares
a cancellation, it does not certify a blind instrument, and using it there is
the sanctioned-hatch-becomes-the-undisciplined-door failure the wrapper exists
to prevent. **The work stayed committed and unpushed, and the loop stayed dark
rather than burning sessions that could not push, cite or merge.**


#### ⚠️ A CONTROL AIMED WHERE THE ANSWER IS PREDETERMINED IS NOT A CONTROL

**Standing 2026-08-21. Two specimens, same day, same author — which is why it
is a line rather than an anecdote.**

The positive-control rule says: before believing a zero, run the same matcher
against something you KNOW is present. This is the failure INSIDE that rule.
A control only tells you the instrument works if the target could have gone
either way. Aim it somewhere the answer is fixed and it reports the target's
properties, not the instrument's.

> **BEFORE TRUSTING ANY CONTROL, STATE WHAT THE CORRECT MACHINERY WOULD DO AT
> THAT TARGET. If the answer is "fire" or "stay silent" REGARDLESS of the
> machinery's health, re-aim.**

| specimen | the control | why it was predetermined | what it nearly cost |
|---|---|---|---|
| a byte-identity harness over 49 production notes | mutate `flattenTables`'s **header-only** join and expect digests to move | **no production note is a header-only table**, so that path is never reached — it moves 0 of 49 whatever the harness does | recording a WORKING harness as blind, and with it the 49/49 identity it had just proven |
| a misfiled-declaration hint | run its glob against `docs/foundation/deploys/` and expect silence | that directory legitimately holds `20260812-b7s3c-backfill-declaration.md`, a RULED-MUTATION declaration — it matches `*declaration*.md` **by right** | recording a WORKING mechanism as a false-positive generator |

**Both were re-aimed and both then discriminated**: the first at the 2-column
collapse every production table takes (15 of 49 move; the DOCX twin moves 24 of
49), the second at `preflight-reports/` and `qa-reports/`, which hold no
declarations — silent there, firing on `deploy-reports/` where the misfiled
files actually were.

⚠️ **THE TELL IS THAT YOU CAN PREDICT THE CONTROL'S RESULT FROM THE TARGET
ALONE.** If you can say what it will do without knowing whether the code works,
it is measuring the target. A control has to be a question the instrument
answers — otherwise it is the emptiness test one level up, wearing the clothes
of the rule that exists to prevent it.

#### ⚠️ AND A SIXTH — **TWO WEAK DEFECTS COMPOSED INTO A CONFIDENT FALSE GREEN**

**Standing 2026-08-21. Written by the author of the other five, the same day,
about a waiter he had just "corrected".** That is the argument for it being a
rule rather than a lesson.

> **THE BAD KEY PRODUCED A ZERO; THE VACUOUS TEST CONVERTED IT INTO A
> CITATION.** Neither defect alone would have printed a green.

A citation waiter reported **`CITED — all 0 SUCCEEDED`** on a PR that was
provably 3 of 4 with `e2e` still running. Two independent faults, each
individually survivable:

| fault | on its own |
|---|---|
| queried the **abbreviated** sha (`8a7271a7`) | the known `gh` trap — returns `[]`, exit 0, no warning |
| success test was `OK == T` | **true when both are zero** — no non-vacuity floor |

**Reproduced side by side, live, on the same commit:**

    --commit SHORT (8a7271a7)  ->  0 runs
    --commit FULL   (40 chars) ->  4 runs
    --branch  (second view)    -> 10 runs

**WHAT GENERALISES, AND IT IS NOT "USE THE FULL SHA" — THAT RULE ALREADY
EXISTED AND IS ONE SECTION UP.** The new part is the COMPOSITION: this
programme's canon already names the short-sha trap AND already demands a
non-vacuity control, and **the author had just written a "corrected" waiter
that violated both**. A defect list is not a defence; the same session that
fixes one member of this family will introduce another.

**So a check that reports success MUST carry a FLOOR, not only a ratio.**
`OK == T` is a ratio and ratios are vacuous at zero. The shipped form asserts
`T >= expected` and reports **`CANNOT TELL`** below it — because *"there are no
runs"* and *"every run passed"* are the two states this family exists to keep
apart, arriving here for the sixth time in a new costume.

⚠️ **AND THE THIRD WAITER IN THE SAME SESSION HAD THE SAME SHAPE ONE STATE
OVER:** it exited on `status != completed` being empty, and **a CANCELLED run
is `completed`** — so it printed a partial count as a citation. Cancelled vs
succeeded; absent vs passing. One family, two costumes, one hour.

### ⚠️ AND A THIRD MEMBER: A TREE THAT CANNOT RESOLVE ITS OWN IMPORTS

**Contributed by the FOUNDATION loop's session 02, 2026-08-15.**

> **A number printed from a tree that cannot resolve its own imports is not a
> measurement, and saying which half you have is the whole discipline.**

Running the unit suite **from a git worktree** reports 15 failed files / 1 failed
test, every one `Failed to resolve import "react/jsx-dev-runtime"`. The session's
first reading blamed its own leftover bind-mount — a plausible, self-implicating
diagnosis.

⚠️ **THE CONTROL REFUTED IT.** A clean detached worktree at `origin/main`,
carrying **none** of the change, produces the identical 15/1. `vitest.config.ts`
aliases react to `../../node_modules/react`, and **a worktree checks out TRACKED
FILES ONLY**, so that path does not exist there. A pre-existing property of the
config, not a defect in anybody's branch.

⚠️ **AND WHAT IT DID NEXT IS THE PART TO COPY: IT REPORTED THE CONTROLLED
DELTA, NOT THE RAW NUMBER.** `origin/main` 308 files / 3741 passed, branch 309 /
3746 — **+1 file, +5 tests, exactly the new arms.** That confirms the exclusion
**empirically**, where reading the config would only have confirmed it by
argument.


---

### ⚠️ A FRESH SPECIMEN, 2026-08-31 — THE CONTROL WAS DRAWN FROM THE GUARD'S OWN LIST

**Ratified with ruling #157(c). It is the same defect, one layer inside the fix
for the defect it was written to catch, and it stayed green through both.**

Ruling #157(b)'s adversarial pass found that a heading-strip was deleting the
negation out of a denied clinical sentence — printing an anticoagulant list for
a patient the encounter said was **not taking them**. The repair refused the
strip whenever the removed prefix matched the exported `EXPLICIT_DENIAL`, which
is built from the repo's `DENIAL_VOCABULARY`. A gate arm was written to prove
the repair, with five KEEP fixtures:

    Negative for: · Patient denies: · Not taking: · No history of: · Without:

**All five are `DENIAL_VOCABULARY` tokens.** The guard is built from that list,
so the arm's result was fixed by its own target before a line of it ran. It
proved that the guard protects the words the guard is made of.

⚠️ **AND THE MEASUREMENT THAT EXPOSED IT IS THE ONE TO COPY: MUTATE THE GUARD
OUT AND DIFF THE WHOLE POPULATION, NOT THE FIXTURES.** With the guard removed,
**every denial shape outside the vocabulary was byte-identical** — only the five
protected rows moved. The arm went red, correctly, and the rule it stood for was
still broken for `Absent:`, `Ruled out:`, `Not currently taking:`, and for
stated-polarity denials carrying no negation token at all. **Gate: 34 of 34
green with the harm live.**

> **A VOCABULARY GUARD'S FIXTURES COME FROM OUTSIDE THE VOCABULARY.** If every
> case you test is a case the implementation enumerates, you have measured the
> enumeration. The cases that matter are the ones nobody wrote down — which is
> why the arm must also carry a REFUSE set, and why #157(c) requires `(1f)`'s
> fixtures to use out-of-vocabulary negations.

Its sibling half — that the arm's other assertion, a substring check, was
*satisfied by the inversion* — is
[canon 74](74-a-substring-check-cannot-prove-nothing-was-destroyed.md).
