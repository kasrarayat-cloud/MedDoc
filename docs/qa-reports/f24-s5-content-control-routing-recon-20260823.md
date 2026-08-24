# F24-S5 RECON — where a content-control edit LANDS

**Run 2026-08-23 by FOUNDATION session 01 of 6 (`20260823-230455-b2`), against
`main` @ `922f18cd`.** Ruling **#142** opened F24-S5 and ordered *recon first*:

> *"Where the edit should LAND (manifest? pending-fill layer? the visit's own
> state?) is the slice's real design work and is measured before anything is
> built."*

**NOTHING WAS BUILT. No production write of any kind was made.** Every
production query in this report is read-only and returns counts or structural
metadata; no note text left the database.

---

## THE VERDICT, UP FRONT

| candidate route | verdict |
|---|---|
| **(a) the fill manifest** | ❌ **REFUTED BY MEASUREMENT.** Fatal in *both* configurations — see §3 |
| **(b) a resolution-overlay layer** consulted by the fill engine on every run | ✅ **THE ROUTE.** The mechanism already exists (`mergeFieldResolutions`); its **precedence is wrong** and that is the slice's real work — see §4 |
| **(c) the visit's own state** | ⚠️ **NOT DISTINCT FROM (b).** It is a question about where the overlay is *stored*, not about how it is *applied*. Answered in §5 |

**The one-sentence finding:** F24-S5 is not inventing a layer. **It is
completing one that was designed, shipped dormant, and never given a writer** —
and the single thing standing in its way is an overlay precedence rule that was
deliberately written to do the opposite of what a clinician correction needs.

---

## 1 · THE SUBSTRATE — measured on the real certified twin

Production holds exactly **one** compiled twin (the West Medical venous form).
Every number below is from `template_twin_compiled_versions.compiledDocumentIr`,
shape-checked before it was counted (`jsonb_typeof(... -> 'fields') = array`,
length **80**).

### 1.1 · The partition reconciles, and the two classes are perfectly disjoint

| bindingType | n | with a non-empty `allowedOptions` | without |
|---|---|---|---|
| `content_control` | **28** | **28** | 0 |
| `table_cell` | **52** | 0 | **52** |
| | **80** ✔ | | |

⚠️ **THIS IS THE CLEANEST RESULT IN THE RECON AND IT DECIDES CLAUSE 3.** The
ruling requires the edit to *"validate against that control's OWN compiled
option set"*. Measured: **there is no residue class.** Every one of the 28
unaddressable regions is a genuine closed-option control, so the validate-or-
refuse design applies universally — no second design is needed for
option-less controls, because there are none.

The complement is equally load-bearing: **no table cell carries options.** So
`allowedOptions.length > 0` is, on this form, an exact discriminator between
"dropdown" and "free cell" — the two F24 halves do not overlap at all.

### 1.2 · Option sets are small enough to NAME in a refusal

| options per control | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 11 |
|---|---|---|---|---|---|---|---|---|---|
| controls | 2 | 7 | 3 | 3 | 4 | 3 | 2 | 2 | 2 |

Sums to **28** ✔. Range **2–11**, no degenerate single-option control.

The ruling requires a refusal that **names the options**. At a maximum of 11
that is always tractable — this is a design fact, not an aspiration.

### 1.3 · Matching is unambiguous BY CONSTRUCTION

| | controls |
|---|---|
| all `displayText` distinct within their own option set | **28 of 28** |
| all `value` distinct within their own option set | **28 of 28** |

No tie-breaking rule is needed. A value that matches, matches exactly one
option.

### 1.4 · ⚠️ SEVEN OF THE 28 ARE LATERALITY CONTROLS

| criticality | unknownPolicy | n |
|---|---|---|
| `routine` | `blank` | 21 |
| **`laterality`** | `blank` | **7** |
| | | **28** ✔ |

**This is the highest-risk finding in the recon.** Laterality is the exact class
this arc has already paid for twice — F24-S1 wrote a diameter into the reflux
cell, F24-S1b wrote a RIGHT-leg correction into the LEFT leg. Both were caught
by the adversarial pass and not by their author.

Note what makes content controls *different* from the table cells those defects
lived in, and it cuts both ways:

- **Safer:** a content control has no row geometry, so there is no
  label-column offset and no row-ordinal to get wrong. The S1/S1b defect
  shapes are structurally absent here.
- **More dangerous:** `SIDE OF EXAM` is a single control whose whole content
  *is* the laterality. There is no neighbouring cell to be wrong about — the
  field itself is the thing. A mis-resolved control does not shift a value one
  column over; it states the wrong side of the body in the one place the form
  says it.

Also measured: **all 28 carry `unknownPolicy: blank`** — none is
`requires_input`. So no content control can block a fill by being unset, which
means the slice cannot break an existing fill by declining to set one. Refusing
is always safe here. **That is a measured licence to fail closed.**

---

## 2 · HOW A FIELD VALUE REACHES THE DOCTOR TODAY

Traced end to end, because the routing question is really a question about this
chain.

1. **`worker.ts:1331`** → `runTemplateTwinFillStep` — the **only** production
   caller of the fill in the pipeline.
2. **`fill-engine.ts`** builds `resolutions` (`FieldResolution[]`), renders the
   document, stores the artifact, and writes **one manifest per visit**
   (`findUnique({ where: { visitId } })` — the relation is 1:1).
3. **`native-export.ts:70`** serves the **stored rendered bytes**, gated on
   `status='VERIFIED' AND roundTripVerified AND outputObjectKey IS NOT NULL`
   **and** on freshness: `noteSha256 === sha256(visit.soapFinal)`.

⚠️ **RECON FACT — THE EXPORT SERVES STORED BYTES, NOT A LIVE RENDER.** This is
the fact that kills route (a). A write that changes manifest *metadata* without
re-rendering **never reaches the document the doctor downloads.** Any route must
cause a re-render, or it is decorative.

### 2.1 · There is a SECOND producer, and it changes the picture

`loadOrComputeNativeTemplateDocxForVisit` calls the loader first and, **when it
returns null for ANY reason — including stale freshness** — falls through to
`processTemplateTwinVisit` for an UNSIGNED, CERTIFIED-twin visit, then reloads.

> ⚠️ **A HYPOTHESIS I FORMED AND THEN REFUTED, RECORDED BECAUSE IT WAS
> REFUTED.** On reading the freshness gate I concluded that any chat edit to
> `soapFinal` would leave `noteSha256` stale and silently drop the doctor to the
> generic styled layout — a serious live defect in the *already-shipped* F24
> table-edit path. **That is wrong.** The recompute fallback fires on stale, not
> only on absent, so the edit self-heals at download time. The docstring says
> *"only fires when the manifest never materialised"*, which is what misled me;
> the **code** is broader than its own comment. Reading the docstring produced
> the wrong answer and reading the control flow produced the right one.

**The correction matters far beyond the false alarm:** this self-healing
recompute is precisely the mechanism that destroys route (a).

---

## 3 · WHY THE MANIFEST IS REFUTED — both configurations fail

The manifest carries a `fillManifest` jsonb (the resolutions) and a dormant
`reviewedAt` column. There are exactly two ways to use them, and **both are
fatal.**

### 3.1 · Write the override into the manifest WITHOUT `reviewedAt`

`fill-engine.ts` replaces the manifest wholesale whenever
`existing.manifestSha256 !== prepared.manifestSha256`. The recompute in §2.1 is
triggered **by the download itself**. So:

> the doctor corrects a dropdown → downloads → sees it correct → edits one word
> of the note → downloads again → **the dropdown has silently reverted.**

A correction that disappears with no error is the worst available outcome.

### 3.2 · Write the override AND set `reviewedAt` to protect it

`fill-engine.ts:510-513` refuses:

```
if (existing?.reviewedAt != null)
  throw new TemplateTwinFillError('MANIFEST_CONFLICT', …)
```

It **throws** — it does not merge. And `native-export.ts` catches every throw
from the recompute and returns `reason: 'fill_failed'` → styled fallback. So:

> the doctor corrects a dropdown → edits any note text → the manifest is now
> stale → the recompute throws → **the doctor's own form stops coming back,
> permanently, and falls to the generic layout with nothing on screen saying
> why.**

That is an **accepted-capability-loss** shape (owner class **b**) manufactured
by the fix itself. It is the same failure this repository already recorded once,
for pre-deploy signed visits — and repeating it *deliberately*, in a new
feature, would not be defensible.

⚠️ **HONEST LIMIT, AND IT IS THE LOAD-BEARING ONE IN THIS REPORT.** §3.2's chain
was established by **READING the shipped code, never by exercising it.**
Measured: **`reviewedAt` has ZERO writers** — ORM and raw SQL, swept by table
(`template_twin_fill_manifests`) and by model, each sweep positive-controlled
against sibling columns (`roundTripVerified` 17 hits, `signedDecisionAt` 6, vs
`reviewedAt` 4 — all four being the schema declaration, two reads, and one
`WHERE` guard). And **zero tests reference `reviewedAt` anywhere**, so the guard
at `:510` is entirely uncovered. Production agrees: **`reviewedAt` is NULL on
both of the 2 manifests that exist.**

**So the chain is a code-reading, and it is a reading of a path nothing has ever
executed.** It should be confirmed by an executed proof in the build slice
before any weight is put on it. It is strong enough to *rule out* route (a) —
you do not need certainty to decline a route with two known-bad configurations
and no known-good one — but it is not strong enough to be cited as behaviour.

---

## 4 · THE ROUTE — an overlay, and the precedence is the work

`bridge-fill.ts:660` already exposes exactly the mechanism this slice needs:

```
mergeFieldResolutions(ir, baseline, ...overlays)
```

And `FieldResolution` (`ir.ts:451`) already carries **both** of the fields a
structured content-control correction requires:

- **`selectedOptionOrdinal: number | null`** — the option-selection slot,
  addressing an option by its compiled ordinal rather than by text;
- **`clinicianReviewed: boolean`** — the per-field clinician flag.

⚠️ **BOTH ARE DORMANT. `clinicianReviewed` is set to `false` at ALL SIX
construction sites and to `true` nowhere.** Together with the manifest's
never-written `reviewedAt`, the twin carries **two independent
clinician-correction seams, designed and shipped without a writer.**

### 4.1 · ⚠️ THE BLOCKER — the existing precedence is exactly backwards

`mergeFieldResolutions` applies an overlay **only where the baseline is
unfilled**:

```
const currentUnfilled = current.value === null || UNFILLED.has(current.status);
if (currentUnfilled && r.value !== null) byId.set(r.fieldId, r);
```

Its own docstring says why, and the reason is good:

> *"an overlay replaces the baseline for a field ONLY when the baseline left it
> unfilled — so a value the evidence resolver genuinely supported/denied/
> conflicted always wins."*

**That is gap-filling, and a clinician correction is the opposite.** A doctor
correcting `SIDE OF EXAM` is correcting a control the resolver *already filled* —
which is precisely the case this rule refuses. **Passing a clinician override
through `mergeFieldResolutions` as it stands would silently do nothing**, and
"silently does nothing" is this programme's most expensive failure shape: it
looks identical to working.

> **This is the finding the ruling predicted — *"the wrong choice here is the
> kind that is discovered at export time"*. It would have been: the edit
> accepted, the manifest rewritten, the census green, and the doctor's document
> unchanged.**

**The slice must therefore introduce a clinician overlay with WIN precedence,
distinct from the gap-fill overlays — and must not weaken the existing rule**,
which protects the evidence resolver from the AI overlays and is correct as
written. Two precedences, named separately. Widening the existing one to "always
win" would let every bridge overlay overwrite resolver-supported values, which
is a clinical-safety regression well outside this slice.

---

## 5 · WHY (c) IS NOT A THIRD OPTION

"The visit's own state" and "a pending-fill layer" are the same answer at
different addresses: both mean *a durable store, outside the manifest, that the
fill engine consults on every run*. The manifest is disqualified as a **store**
(§3) because it is the thing that gets replaced; anywhere else works mechanically.

The real question that remains open is **keying**, and it is a genuine design
decision the build slice must make rather than inherit:

- an override addresses a `fieldId`, which is scoped to a **compiled version**;
- a template can be **re-certified**, minting a new compiled version with new
  `fieldId`s;
- so an override keyed on `(visitId, fieldId)` alone **silently stops applying**
  after re-certification — the dormant-seam failure again, one layer up.

**Recommendation for the slice, not a decision taken here:** key on
`(visitId, compiledVersionId, fieldId)` and **fail closed and loud** when the
compiled version moves — an override that cannot prove it addresses the current
form should refuse, and say so, rather than quietly not applying. Measured
today: **1 compiled version, 2 manifests**, so this costs nothing now and is
unfixable-in-place later.

---

## 6 · WHAT THE BUILD SLICE OWES

1. **A clinician overlay with WIN precedence**, named separately from the
   gap-fill overlays; the existing rule left byte-for-byte intact.
2. **A durable override store**, keyed to survive re-certification (§5), which
   the fill engine consults on **every** run — so the recompute in §2.1 re-applies
   it rather than destroying it. This is what makes the correction survive a
   note edit, which is the whole failure mode of route (a).
3. **Validation against `allowedOptions`**, refusing and naming the options
   (§1.2 proves this is always tractable). Address the option by **ordinal**
   via `selectedOptionOrdinal`, never by matching label text — the arc's own
   standing lesson.
4. **`clinicianReviewed: true` on the overlaid resolution**, so the manifest
   records that a human set the value. This is a dormant field being given its
   first writer; it should get a guard in the same commit.
5. ⚠️ **AN EXECUTED PROOF OF §3.2's CHAIN** — the `reviewedAt → MANIFEST_CONFLICT
   → fill_failed → styled` path is currently a reading of never-executed code.
   Either exercise it or stop citing it.
6. **UNSIGNED ONLY** — the sign-freeze is unchanged and untouched by any of the
   above. Nothing here goes near a signed record.
7. ⚠️ **THE ADVERSARIAL PASS IS MANDATORY** and **7 of the 28 controls are
   laterality** (§1.4). The untested-claim sentence should be written before it
   runs.

---

## 7 · HONEST LIMITS, AND WHAT RE-ARMS EVERY NUMBER HERE

⚠️ **EVERY FIGURE IN §1 IS A FACT ABOUT ONE FORM, NOT A PROPERTY OF THE
COMPILER.** Production holds **one** certified twin. The 28/52 split, the
28-of-28 option coverage, the 2–11 range, the 7 laterality controls and the
perfect display/value distinctness are all measurements of the West Medical
venous form.

**The re-arming condition, stated so it is a tripwire somebody can watch:** *a
second template certifying end-to-end.* One such template can, with **no code
change anywhere**, produce a content control with an **empty** `allowedOptions`
(re-opening §1.1's "no residue class"), **duplicate** display texts (re-opening
§1.3's unambiguous matching), or an `unknownPolicy: requires_input` control
(re-opening §1.4's licence to fail closed). RELAY **F5-i** already tracks the
multi-shape census; **this recon is downstream of it and its conclusions inherit
its limit.**

Two further limits, stated plainly:

- **§3 is a code-reading, not an execution.** Recorded in full at the end of §3.
- **The census figures (52 addressable / 28 `no_editor_intent` / 80 total) are
  not mine** — they are `gate-f24-s3-editor-addressable-census`, which I **ran**
  (7 arms, green, from `apps/transcribe-md`, `setup: 114ms` — i.e. the real
  config, not the wrong-cwd one that reports `setup: 0ms`). I re-derived the
  80-field total and the 28/52 binding split independently from production and
  **they reconcile with the gate.** That reconciliation, not the agreement, is
  the evidence.
