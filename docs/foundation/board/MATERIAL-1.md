# MATERIAL-1 — `clinicallyMaterial` is DERIVED, and the constant has been doing real harm

**Filed 2026-09-08 by the custom-file session, under ruling #277. It runs AFTER
#275's sequence** — merges, then #274's ingest entry point, then the re-issue
act. This note is the record so that the work starts from measurement rather than
from the ruling's prose.

## THE ASK

> `clinicallyMaterial` is **derived from the concept's class**:
> **administrative** — identity, credentials, addresses, boilerplate, **#194(a)**
> — → **`false`**; **clinical** → **`true`**. The constant is retired at **all
> twelve** compiler emission sites.
>
> **THE ARM: the production census moves ONLY the administrative rows.**

## WHY IT IS A RULING AND NOT A TIDY-UP — measured, not argued

```
critical = field.criticality !== 'routine' || field.clinicallyMaterial
                                              ^^^^^^^^^^^^^^^^^^^^^^^^  always true
```

Read-only against production:

| query | result |
|---|---|
| `clinicallyMaterial = true` | **238 of 238** |
| `required = false` | **238 of 238** |
| `clinicallyMaterial: true` in `compiler.ts` | **12 sites** |
| `clinicallyMaterial: false` in `compiler.ts` | **0 sites** |

So `critical` is a **constant true**, and in

```
needsInputBlocks = !allowUncertifiedForSyntheticTest && (critical || field.required || mapping.required)
```

**every disjunct after `critical` is dead weight.** A field's own `required` flag
has never once decided anything on this deployment.

⚠️ **AND IT DID REAL HARM, WHICH IS WHY THIS IS NOT COSMETIC.** #272's
implementation is the case: a record-derived blank withheld the doctor's entire
document, and it did so **regardless of whether anybody had marked the control
required** — because the `required` half of the condition was never reached.
Reading the code, the behaviour looks scoped to required controls. It is not.

**#157(d) already named the class:** *"a qualifier that is always true is a
comment."* This is that comment.

## ⚠️ THE ARM IS THE HARD HALF, NOT THE DERIVATION

Writing the classifier is a morning's work. Proving it did not move a row it
should not have is the whole item, and it is asymmetric:

- an **administrative** row that stays `true` → a field keeps blocking that need
  not. Annoying, visible, and someone complains.
- a **clinical** row that flips to `false` → **a field that should block stops
  blocking**, silently, and nothing in the suite is shaped to notice. It surfaces
  as a document that shipped when it should have been withheld.

> **The census is taken BEFORE the change, from production, and the comparison
> has one correct answer fixed while the outcome was still unknown.**

That is §2.5's discipline applied to a code change rather than a deploy, and for
the same reason: *afterwards, every number has a story available to it.*

**The census to capture (before any edit):**

```sql
select fd."clinicalConcept", fd.criticality, fd."clinicallyMaterial", count(*)
from template_twin_field_definitions fd group by 1,2,3 order by 1;
```

…joined to the mapping's concept, since the classifier keys on the CONCEPT and
the census must be readable in the same terms the classifier decides in.

## WHAT "ADMINISTRATIVE" MEANS HERE, AND WHERE THE LIST LIVES

**#194(a)** is the anchor. The classes named in the ruling: **identity**
(patient name, DOB-derived age), **credentials** (referring physician, provider
identifiers), **addresses**, **boilerplate**.

⚠️ **THE CLASSIFIER MUST HAVE ONE READER.** The concept registry already decides
what a concept IS; a second table mapping concept → materiality would drift from
it the day either changed, which is the failure this programme has paid for
repeatedly (`fromPersistedMapping`, `narrativeSentence`, `#272`'s own refusal
vocabulary). Derive it from the registry, or put it in the registry.

## ORDER, AND WHY

**It runs after the sequence.** It touches the compiler at twelve sites and
changes a value that gates **document withholding**. Landing it beside the
re-issue act would put two clinical-surface changes into one deploy — and a
deploy discharges only the declaration whose author ran the comparison, so the
other goes unjudged. That is a named hazard, not a scheduling preference.

## ACCEPTANCE

- the census, captured **before** the change, is in the record
- after: **only administrative rows moved** — enumerated by concept, not counted
- a **clinical** row that moved is a **finding**, whatever its explanation sounds
  like afterwards
- `needsInputBlocks`'s `required` disjuncts become reachable, and there is an arm
  showing a `required` field now decides something that a non-required one does
  not — otherwise the constant was merely replaced with a different constant
