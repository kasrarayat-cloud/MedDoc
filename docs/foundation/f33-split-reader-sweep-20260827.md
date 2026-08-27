# The ledger split has downstream readers, and CI found one of them

**2026-08-27, supervised session. Branch `docs/ledger-split-and-rotation` (PR #877).**

## THE VERDICT: #877 IS NOT MERGEABLE AS COMMITTED, AND THE LOOP MUST NOT RELIGHT ONTO IT

Not because the split is wrong — **the split is content-preserving and I
re-proved it by a second, independent route** (below). Because a split is not
only a fact about two files; it is a change to **what every reader of those
paths can see**, and the census that ratified it cannot see that class at all.

> **A content-preservation census proves nothing was LOST. It cannot prove
> anything is still REACHABLE.** Those are different questions, and only the
> first was asked.

## WHAT RATIFICATION ACTUALLY COVERED

The census (0 lines lost both directions, 33,386 == 33,386) is TRUE. I confirmed
it by a route that does not share its failure mode: extracting each archive's
body at its `<!-- VERBATIM-BODY-BEGINS -->` sentinel and testing verbatim
containment in the pre-split blob at the split commit's own parent `c1d641f7`.

- **23 of 25 archives are byte-verbatim slices.** Spans contiguous, **no gaps,
  no overlaps**, covering pre-split lines 31–33,386.
- The **2 exceptions** (`2026-08-04-part1.md`, `-part2.md`) differ ONLY by the
  `## Rules` and `## Invariants re-checked every item` blocks, which were
  **promoted into the live head** — both verified verbatim there (`Invariants`
  byte-identical, 554 == 554; `Rules` 1,813 chars contained).
- Positive controls pass in both directions (a corrupted body is NOT found).

⚠️ **My own first two attempts at this measurement were wrong** — an off-by-one
line extraction, then a `re.S` regex that ate the file and reported `0/25`. Both
were my instrument, not the split. Recorded because a "0/25 MISMATCH" screenshot
would have been a very convincing false finding.

## THE CONFIRMED DEFECTS

Every row below was found by one lens, then **adversarially refuted by an
independent agent told to default to "this is wrong"**, and the ones here are
those that survived AND were shown NOT to hold on `main` (i.e. split-caused).
I personally re-measured rows 1, 2 and 3.

### 1 · `check-retirement-conditions.sh` — BROKEN. *(FIXED in this commit.)*

The only defect CI could see, and it is the reason `unit tests` is red.

| | main | split |
|---|---|---|
| `ledger closure-vocabulary present=` | **1** | **0** |
| partition | due **4** · not-due **1** · cannot-tell **0** | due **2** · not-due **0** · cannot-tell **3** |
| `⛔ NOT DUE` section | present | **absent entirely** |
| exit | 1 | **2** (fail-closed) |

The script greps `docs/foundation/RELAY.md` for `#+ (✅|🟢) <ID> —` closure
headings. A closure heading is BY DEFINITION in a closed arc, and the split moved
every closed arc out. All **31** headings are still on disk, in
`docs/foundation/relay/*.md` — the content was preserved and the **watched set
narrowed**.

It reddens `gate-f30-retirement-conditions.test.ts:136` — **a file this PR does
not touch** — at the arm written to catch exactly this: *"CONTROL — a
demonstrably UNMET condition lands in NOT-DUE and never in DUE."*

⚠️ **The loud half is the red CI. The quiet half is that DUE went 4 → 2:** F10's
and F23's MET retirement conditions stopped being reported, so two expired INBOX
entries would go on being printed into every session's launch — the precise harm
this sweep exists to price. It does fail-closed rather than lie (cannot-tell 3,
exit 2), which is the script working as designed.

⚠️ **And the irony is load-bearing, not decorative:** the same PR finally SHIPS
this script's grant (`Bash(bash scripts/check-retirement-conditions.sh:*)` in
`.claude/settings.json`), closing the F30 residual the script's own header said
it could not close from its side — **and narrows its watched set until it
refuses, in the same commit.**

**FIX (in this commit):** the watched set becomes the live head PLUS the
archives, degrading to exactly `$LEDGER` where `docs/foundation/relay/` does not
exist — so it is byte-identical on any pre-split tree. Proof in the commit body.

### 2 · `rotate-ledger.sh` — BROKEN, TWICE. The PR's central promise is inert.

The PR's title offers *"rotation so it never needs doing by hand again."* It
refuses on its first use, and its `--apply` is worse than its `--check`.

**(a) The LIFT manifest names anchors that do not exist.** `rotatable()` declares
seven RELAY anchors; two are not headings:

- `## HOW THIS FILE IS ORGANISED — read this once` → is a **blockquote**
  (`> **HOW THIS FILE IS ORGANISED…`), not a `##` heading.
- `## THE ARCHIVE INDEX` → **0 occurrences in either file.** The index is emitted
  as an HTML-comment block (`<!-- ARCHIVE-INDEX-BEGIN -->`), never as a heading.
  The splitter itself never produces that heading.

Measured: `grep -nE '^#{1,2} ' docs/foundation/RELAY.md` returns exactly five
headings, and neither anchor is among them. `split-ledger.py` FATALs on any
unmatched LIFT anchor, so **every future rotation exits 2 having moved nothing**
— on both RELAY and RULINGS.

**(b) `--apply` never passes `WRITE_HEAD`, so it reports success while doing
nothing — and duplicates content.** `split-ledger.py:267` gates the head rewrite
on `os.environ.get("WRITE_HEAD")`; `rotate-ledger.sh:138,143` invokes the
splitter without it. Reproduced end-to-end on a grown copy (112,544 chars): the
run printed `🟡 rotate-ledger: rotation applied`, **`RELAY.md` md5 and char count
UNCHANGED**, and a new archive file was written holding a verbatim **copy** of
content still in the head.

⚠️ **That is the dangerous shape, not the annoying one:** a rotation that says it
rotated, left the head oversize, and put a second copy of live content on disk.
The next reader has two sources for one arc and no signal that they disagree.

### 3 · `RULINGS.md` — the standing rule that guards this programme from CONTRADICTION now returns zero

`AGENTS.md`: *"BEFORE DECIDING ANYTHING RULING-SHAPED, GREP
`docs/foundation/RULINGS.md`."* `MASTER.md:109` calls it **grep-only**.
`MASTER.md:768` orders the morning report's PROVISIONAL block reconstructed
**FROM DISK** out of that file.

Measured by me, both trees:

| `grep -c` on `RULINGS.md` | main | split | still in `rulings/` |
|---|---|---|---|
| `PROVISIONAL` | **47** | **1** | 48 |
| `OWNER RULING` | **23** | **0** | 23 |
| `96(b)` (cited by AGENTS.md) | 3 | **0** | — |
| `laterality` (ruling #127) | 3 | **0** | — |
| *positive control* `RULING` | 44 | 11 | — |

The control proves the file is greppable and the instrument sound. The content is
**all still on disk, in the archives** — and unreachable by the one access route
the rules mandate. Ruling titles in the live index are hard-truncated at 72
characters, which removes the operative clause from most rows.

**Consequences, concretely:** a session asking *"is this an OWNER RULING I may
not overturn?"* gets **0, exit 1**, which reads as *"there are none."* A session
building the morning report writes a PROVISIONAL block with **zero rows** while
48 rulings await war-room review.

### 4 · `MASTER.md` is stale in the dangerous direction, and never mentions the archives

`MASTER.md` is untouched by this PR except an 18-line THROUGHPUT insert. So after
the merge it still tells every session that `RULINGS.md` is 371,533 chars / 2.5×
the read limit / grep-only — when it is **39,238 chars and fits in one read**, and
grep has just stopped being complete access. **Both halves wrong, both in the
direction that costs.** `RULINGS.md`'s own banner says the same.

It also never names `docs/foundation/relay/`, so STEP 0.3's *"GREP for everything
else"* now searches a 20 KB stub: `grep -n rollback docs/foundation/RELAY.md`
returns **145 lines on main and 0 after the merge**, with all 146 hits sitting in
a directory the instructions do not mention.

Same class: `INBOX.md:58` — printed into **every** session log — points at a
`RELAY.md` section that no longer exists there, and it is the full record of a
real $10 promo liability.

### 5 · The archive index's "citations still resolve" claim is false for 2 of 25

The index's frozen-span column is sound in principle. But the two `2026-08-04`
archives are **shorter than their declared spans** (the promoted `## Rules` /
`## Invariants` blocks), so line offsets inside them no longer correspond.
Resolving `RELAY.md:6000` lands ~35 lines off; `RELAY.md:6758`, the declared last
line of that span, falls **past EOF**.

## F8 — THE THING I WAS ASKED ABOUT. MY OWN FLAG DOES NOT SURVIVE.

The flagged concern was that the new live head reads *"F8 LEADS THE QUEUE"* and
*"Gate is DISCHARGED, not blocked"* while **F8-S1 and F8-S1b are MERGED and
F8-S2 is PARKED — owner-class**, so a relit session 01 would take an
authorization it cannot act on, or build a coding surface without the owner's
layout call that ruling #148 reserves.

**REFUTED, and I am recording it refuted rather than softening it.** The
resolving fact is stated **three rows below, in the same table**: F8-S2's row
names the park, names it owner-class, and names its trigger (an owner decision in
`RULINGS.md` choosing a nav primitive, a separate route, or the V2 tab strip).
A session reading the queue table reads both. The table is coherent.

Confirmed while checking it, with controls:

- **F8-S2 is the only remaining F8 work.** `grep -rhoE "F8-S[0-9a-z]+" docs/`
  returns exactly three tokens — S1 (23), S1b (7), S2 (10). No S3. Zero
  controlled: the matcher fires for `F8-S1b` across 4 files.
- Rulings #147–#150 read in full **from the archive**, since the live index rows
  are pointers.

⚠️ **So the answer to "does it change what session 01 should read" is YES — but
not for the F8 reason.** F8 is fine. Rows 2, 3 and 4 are what change it, and they
change it a great deal more than a queue-head wording ever could.

## WHAT I DID NOT DO, AND WHY

I fixed **only** row 1, the defect CI caught. I deliberately did **not** push it.

> **Pushing that fix alone would have turned #877 GREEN** — the F30 gate was the
> single failure in 5,302 tests — **while rows 2–5 remained.** None of them is
> watched by any gate; that is finding 3 of the `gates` lens in as many words:
> the PR's own new gate asserts the census over the file pair, and **nothing
> asserts the live index stays greppable.**
>
> A green produced that way would be the most expensive artifact in this
> repository: a citation certifying a tree whose rotation refuses, whose rulings
> cannot be grepped, and whose standing prompt describes a file that no longer
> exists at that size.

Rows 2 and 5 are unambiguous defects in **new** code with obvious fixes. Row 3 is
a **design** question about what the live index must carry (markers and full
titles at minimum), and row 4 is a rewrite of the standing prompt's read
protocol. Those last two are edits to a ratified artifact's design, and they are
the Lead's call, not mine to make at 02:00 unattended.

## THE SWEEP'S OWN HONEST LIMITS

- **6 lenses, 36 agents, 30 candidate findings, 20 confirmed / 10 refuted.** Of
  the refutations, **6 were rejected specifically because the defect ALSO holds
  on `main`** — i.e. real, but not caused by this PR. They are not listed here;
  they are not this PR's debt.
- No lens drove the **Rounds** ledger; it is out of scope and untouched — and
  `docs/rounds/RELAY.md` (236,036 chars, 1.57×) remains the one oversize
  instruction-target the new rotation does not yet reach.
- `.github/workflows` has **no `paths:` filters at all** (`grep -c paths` → 0 in
  all five, positive-controlled against `branches` → present in all five), so the
  "a filter naming the old file won't fire for the new directory" class
  **cannot occur here**. Named because its absence was checked, not assumed.

## SEPARATELY — the zombie-run age-out, measured

Recorded because it was an open question and the data was in reach.

**Zombie CI runs do NOT age out.** Repo-wide `queued` runs carrying **zero jobs**:

| run | workflow | jobs | age when measured |
|---|---|---|---|
| `28586802025` | Dependabot | 0 | **1,334 h — 55.6 days** |
| `31118255417` / `31118255265` | e2e / secrets-scan on `main` | 0 | **489 h — 20.4 days** |
| `32985441052` / `32985194616` / `32984966259` | f32 branch | 0 | 10 h |

⚠️ **AND THE RECORDED SIGNATURE NEEDS A CORRECTION.** `created_at == updated_at`
is **not** a reliable zombie discriminator: #877's own `CI` and `secrets-scan`
runs both had `created_at == updated_at` while carrying **4 and 1 real jobs** and
running to completion. Two of the six genuine zombies had `created_at !=
updated_at`. **`jobs == 0` while `status == queued` is the discriminator;
timestamp equality produces false positives on live queued runs** — which is the
direction that makes a pre-push hook demand a declaration it should not.
