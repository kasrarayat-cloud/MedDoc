# THE MANDATORY ADVERSARIAL PASS OVER #191's FINISHED DIFF — 2026-09-05

**Five lenses, five isolated worktrees, each verified BY CONTENT before launch.**
Commit under review: `5fcdee5a` (`b56a2817..5fcdee5a`). Every lens was told to
REFUTE, to default to *this is broken*, and to report only what it could
demonstrate with a concrete input → wrong output. `NOTHING FOUND` was permitted.

**None returned `NOTHING FOUND`.**

## THE HEADLINE

> **The eleven arms were GREEN throughout, and every finding below was invisible
> to all of them — because all eleven drive the resolver with hand-built
> in-memory mappings and never cross the database, the counts, or the renderer.**

That is the argument for the pass in one sentence. The author's proofs were not
weak; they were *scoped to the author's universe*, which is exactly the property
an independent pass does not share.

## THE SETUP, AND ONE THING IT CAUGHT BEFORE ANY LENS RAN

Five worktrees at `5fcdee5a`, each given a local `node_modules` so `@meddoc/*`
resolves to its own tree, then asserted by content:

| lens | HEAD | emitter | exemption | gate |
|---|---|---|---|---|
| A/B/C/D/E | `5fcdee5a` | 2 | 1 | present |

⚠️ **A SIXTH TREE WAS AT THE WRONG COMMIT WITH THE CHANGE ABSENT.** Its
checkout had failed silently against uncommitted work from an earlier session.
A lens there would have reported `NOTHING FOUND` — the most reassuring sentence
available — about code that was not in its tree. Caught by the content check,
which is the entire reason that check exists. The tree was left untouched
rather than cleaned, and a fresh one built.

## FINDINGS, BY CONVERGENCE

Three lenses found the count regression independently. Two found the `omit`
gating. Two found the dead column. **Convergence from lenses that could not see
each other is the strongest signal this method produces.**

### 1 · THE COUNT REGRESSION — doctor-facing (lenses A, B, E)

`templateTwinCounts` was not widened, so `default_kept` matched no bucket. The
emitter fires on the ordinary *nothing was said about this* case, so **one
unrelated dictated sentence collapsed an entire form's blank count** — measured
11 → 0 on an 11-field template, **with the rendered document byte-identical**.
The doctor's *"N still blank — nothing dictated for those yet"* line vanished
and `notMentionedCount` persisted as 0.

Lens A proved it a **regression**, not a pre-existing defect, by running the
same arm against the parent commit.

⚠️ It is **#170's shape, reintroduced by the fix written to prevent it**, and
the comment fifteen lines above forbade it in that very file. **FIXED**, with a
bucket reconciliation so the next uncounted status fails in CI.

### 2 · THE COLUMN WAS DEAD IN BOTH DIRECTIONS (lenses B, D)

Zero of six projections carried `unmentionedPolicy`; neither writer set it. A
doctor choosing `omit` got `keep` silently, and nothing could choose it anyway.

⚠️ **And the naive fix is a production outage.** Projecting the column moves
the certified mappings sha and `fill-engine` throws
`TEMPLATE_PROVENANCE_MISMATCH`. **FIXED** by canonicalising `keep` to absent in
the attestation — which is what `.optional()` already means. Blast radius
measured against production first: **3 certifications, 2 inactive, 1 the active
form this batch re-certifies anyway.**

⚠️ The gate that should have caught it is titled *"THE TEST THAT WOULD HAVE
CAUGHT IT"* and watches **one column by name**. Now derived from the Prisma
model.

### 3 · THE `omit` REASON WAS UNGATED (lenses A, E)

The ternary tested the policy alone, so a temporality **deferral** had its named
reason overwritten — the manifest saying nothing supported a field the doctor
**did** dictate to. Lens E measured that **779 tests could not tell the
corrected code from the shipped code**. **FIXED**: both halves share one
predicate.

### 4 · ⚠️ OWNER-CLASS — `default_kept` CANNOT KEEP ANYTHING (lenses A, B)

`createFieldPatches` bounded-clears on `resolution.value === null` **before any
status is consulted**. A kept default carries a null value, so a control holding
prose is cleared, `patches` is non-empty, and the `default_kept` branch — inside
`if (patches.length === 0)` — is **unreachable for exactly the population the
ruling targets**. Measured: `kept_default` proofs landed only on controls that
were *already empty*, i.e. those with nothing to keep.

**ESCALATED, NOT FIXED.** Making `keep` real requires a renderer change, and
that makes a template's pre-printed sentence print on a note the doctor never
dictated to. The scoping meant to bound it — #191's SCAFFOLDED precondition —
**cannot be computed**: `TemplateFieldSchema` carries no compiled default
content, only an opaque sha (lens C).

### 5 · THE EXEMPTION'S INVARIANT IS FALSE (lens C)

The justifying comment asserts no cited fact *can* match the concept at the emit
site. `approved_practice_default` facts are excluded by the resolver's filter
and **not** by `factMatchesMapping`, so a practice default minted for field A is
cited by field B sharing its concept. The exemption also disables the
**temporality** clause, which is reachable by that route. **OPEN** — it is
downstream of the owner's decision on 4.

### 6 · TWO ARMS PROVED LESS THAN CLAIMED (lens E)

Arm 3 is **vacuous** — both statuses carry a null value, so it redded under none
of the six mutations. Arm 7 reds via a schema `ZodError`, not its own
assertions. **Both now labelled** rather than quietly kept: a vacuous arm nobody
has marked is worse than no arm, because it reads as coverage.

## WHAT THE LENSES COULD **NOT** BREAK — recorded so the negatives are not read as unexamined

- **The document does not move.** Byte-identical between the two statuses in
  every combination rendered, scaffolded controls included (A, B).
- **No dictated text is lost.** The emitter fires only where no fill was
  possible (A, C).
- **No `FieldResolution` reaches the validator unparsed**; no bridge overlays a
  value onto a kept default while preserving the status (C).
- **A denial never reaches the emit site** — a denial matches the concept (B).

⚠️ **One of those survives by accident:** `mergeFieldResolutions` short-circuits
on `value === null` **before** consulting its `UNFILLED` set, which does not
list `default_kept`. Anyone tightening that condition to the status set alone
silently breaks the bridge overlay.

## AN AUTHOR'S CORRECTION THAT WAS ITSELF WRONG

I told the owner *"the document does not move"*, then retracted it on reading a
lens summary. **The retraction was the error** — two lenses had rendered it and
measured byte-identity. The original claim stands; the false claim is the
different one, that `default_kept` *preserves* the scaffold.

> **A correction inherits the authority of being second without earning it.**

Twice in one session. Filed as canon.

## THE UNTESTED CLAIM, RECORDED LATE

The author's pre-registered "claim I have not tested" was written **after** the
lenses launched, which degrades it as a pre-registration and is recorded as
such. It named field-kind coverage — every arm builds `narrative_text`. Lens B
confirmed the concern: **all ten kind/binding combinations reach
`default_kept`**, three of which can never produce a `kept_default` proof.
