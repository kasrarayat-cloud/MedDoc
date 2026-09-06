# 114 · A CONTROL WHOSE FIXTURE CANNOT REACH ITS OWN SUBJECT

**Filed 2026-09-06. SIX measured instances in ONE session, four of them mine,
two found by others in my work.** Not a new idea — this repository already has
[65](65-the-most-dangerous-wrong-number-is-the-one-expected.md),
[99](99-a-set-cannot-be-its-own-witness.md) and a standing memory on vacuous
controls. What is new is the **recurrence rate under pressure** and the fact
that every single instance was **green**, written by someone who had just
finished writing about this exact failure.

## THE SHAPE

> **A control can be perfectly correct about a universe its fixture cannot
> enter.** It does not fail, it does not warn, and it does not measure its
> subject. It measures the fixture.

The tell is never the assertion. It is always the *inputs*.

## THE SIX, ALL MEASURED IN ONE SESSION

| # | the control | what it could not reach |
|---|---|---|
| 1 | a biconditional asserting the offer predicate is *"the exact negation of `requiresClinicianInput`"* | its matrix varied only that predicate's five inputs — so it **PINNED the bug**, and the correct fix would have RED it |
| 2 | the same matrix, rebuilt | held `expectedDataType` constant, so it could not see `isMappingTypeCompatible` — **the first guard of the ladder** |
| 3 | the same matrix, widened again | held `bindingType` constant, so it could not see the fixed-grid `table_cell` route — **52 cells of the live customer form** |
| 4 | the same matrix, widened a third time | held `mapping.status` constant — caught by the arm written to close the class, **on its first run** |
| 5 | an arm asserting *"the confirm script lists every policy the writer persists"* | a whole-file `toContain`, satisfied by **one occurrence anywhere** — the script had TWO builders and only one was patched |
| 6 | an arm asserting *"the offer is withdrawn for an omit field"* | its mapping fixture was a **two-key stub**, so the predicate returned false for a *missing `expectedDataType`* — the arm passed while measuring a field that was never offerable |

And two more of the same family, on the instruments rather than the code:

- a boundary arm asserting a file **survived** a refusal, reaching for
  `/opt/meddoc-pro/README.md` — a path that **does not exist on the CI runner**.
  It could not tell *protected* from *never existed*.
- a positive control for *"is this field plumbed?"* that used
  `unmentionedPolicy` — **also absent on that branch**. Two zeroes, no
  discrimination, and it would have shipped a finding.

## ⚠️ WHY WIDENING THE MATRIX IS NOT THE FIX

Rows 1–4 are the same defect fixed three times by hand. **Each fix closed an
instance and left the class open**, and the fourth instance was waiting behind
the third.

> **THE FIX IS TO DERIVE THE CONTROL'S INPUTS FROM THE THING UNDER TEST.**

The arm that finally worked reads the guard ladder's own source, extracts every
`field.X` / `mapping.X` it consults, and asserts each appears as a varied
dimension:

```
expect(missing, `the mirror reads [${missing}] and the biconditional never
  varies them — so a guard keyed on those inputs is invisible to this matrix,
  which is exactly how the last three were missed.`).toEqual([])
```

**It found a fourth instance the moment it ran.** A hand-widened matrix is a
list of the inputs somebody remembered; a derived one is the inputs that exist.

## THE HABIT, AND IT IS ONE QUESTION

Before believing any green control, ask **not** *"is the assertion right?"* but:

> **Can this fixture reach the thing I am claiming to measure — and how would I
> know if it could not?**

Then answer it the only way that counts: **break the subject and watch the arm
go red.** A mutation that reds *nothing* is the same information as a mutation
that reds *the wrong arm* — both say the control is not about what you think.

⚠️ **AND CHECK THE CONTROL ITSELF DISCRIMINATES.** A positive control that scores
zero for the same reason as its subject proves nothing twice. Pick a control
that is *known present* on the tree you are measuring, not one you assume is.

## ⚠️ AND A CONTROL DRAWN FROM THE SUBJECT'S OWN CHANGE-WINDOW IS NOT A CONTROL

**Added the same day, from two instances — one mine, one a peer's, hours apart.**

Asking *"is `conceptScope` plumbed through?"* I used **`unmentionedPolicy`** as
the positive control. It scored **0 in `schema.prisma`** — the same zero as the
subject — because the branch under test **predates the migration that added it**.

> **The control shared the very property being measured.** That is the one thing
> a control may not do, and it produced two zeroes that looked like agreement.

The re-control is the shape to copy: three siblings from a **different era** —
`blankPolicy`, `practiceDefault`, `clinicalConcept` — scoring **1 / 4-7 / 3**
across schema, writer and reader while the subject scored **0 / 0 / 0**. The
discrimination is *visible in the table* rather than asserted in prose.

**The habit: pick the control from a DIFFERENT ERA than the subject.** A control
introduced by the same change, on the same branch, in the same week, is liable to
be absent, empty or unplumbed for exactly the reason the subject is.

⚠️ **THE PEER'S INSTANCE IS THE SAME FAMILY WITH A SHARPER EDGE, AND IT IS ABOUT
READING A COLOUR AS A VERDICT.** Their new gate's §2.5 row predicted the gate
would go **RED**. It went red — on `no merge base`, because `actions/checkout@v4`
defaults to depth 1 and the gate never ran at all. **Exit 2 is CANNOT-TELL, not
refusal.**

> **A row that predicts RED and gets RED is not thereby satisfied.**

They scored their own row a FINDING rather than letting the colour vindicate it.
The same asymmetry runs through this whole entry: a green that measures nothing
and a red that measures nothing are the *same* defect, and only the red gets
investigated.

**The instance, for the record:** `check-pr-rows-file.sh`, run `34052168551`,
exit 2 on `no merge base`. The fix is **two** changes, because depth was only
half of it — `fetch-depth: 0`, *and* a base of
`github.event.pull_request.base.sha` rather than `origin/${{ github.base_ref }}`.
**A branch ref moves**: if the base advances while a run is queued, `origin/main`
names a tree the PR was never diffed against and the file set changes underneath
the answer.

⚠️ **AND THIS INSTANCE IS NOT DISCHARGED, WHICH THIS ENTRY IS OBLIGED TO SAY.**
The corrected wiring is proved **locally** — exit 0 for the real PR, exit 1
naming the mismatch for a fabricated one — and has **not yet been observed green
in CI**. Its author flagged that rather than let me write it up as closed.

> **A correction believed before its own evidence lands is the same class as
> everything above it.**

An entry about controls that prove nothing does not get to assert its own
closure on a local run. When the CI run lands, this paragraph is the thing to
update — and if it never lands, that is the finding.

## THE UNCOMFORTABLE PART

Every one of these was written by somebody who had, in the same session, written
a paragraph warning about this exact failure — including the arm whose header
said *"a green arm over a table that never varies the deciding input is the
vacuity failure wearing a control's clothes"*, which then held the next input
constant.

**Naming a class is not enumerating it.** That sentence is already canon; this
entry is its sixth receipt.

⚠️ **AND THE HOUSE OFTEN ALREADY HAS THE ANSWER.** The peer's shallow-clone
failure was solved one file over — `e2e.yml:65` carries
`fetch-depth: 0  # the predicate diffs base...HEAD; a shallow clone would fail
CLOSED`, a comment naming their exact failure mode. They had written a second,
shallower spelling. **The fix was to read, not to invent** — the same
one-definition lesson that produced instance 6 above, where a bare `=== 'omit'`
test was added three lines below a header reading *"ONE DEFINITION, THREE
CALLERS"*.
