# T9 RECON — the coding-confidence distribution, and the number that does not exist yet

**Run 2026-09-04 by the Data/Audit session. READ-ONLY against production.**
**For Design/Admin, who consume the threshold. No code changed by this item.**

**PHI posture, stated before the numbers.** Every statement below comes from
SELECT-only queries over **structured fields**: the numeric `confidence`, the
derived `confidenceLevel`, the `specialty` column, and row counts. This recon
did **not** read `evidence_quote`, `description`, `soapFinal`, any transcript, or
any patient identifier — the first two are model prose that `07a-icd-coding.ts`
already rules can carry patient context. Only aggregates are published: no
per-visit row, and no (patient, code) pair, appears anywhere in this document.

---

## ⚠️ THE HEADLINE IS A REFUSAL: THE THRESHOLD CANNOT BE DERIVED TODAY

The item asks for **the auto-accept threshold**. An auto-accept threshold answers
one question — *above what confidence is the model right often enough that a
doctor need not look?* — and answering it requires **ground truth**: cases where a
clinician accepted or rejected a proposal.

> **Measured: ZERO of 58 production visits carry any ICD decision.**

| probe | result |
|---|---|
| `icdDecisions` column exists | yes |
| visits with a non-null `icdDecisions` | **0** |
| distinct `icdDecisions` values in the table | **0** |
| decision actions in `audit_logs` | **none** — only `CODING_COACH_REJECTED_INVALID_ICD` (72) and `..._INVALID_CPT` (20), which are the MACHINE's allowlist refusals, not clinician acts |
| **control** — visits with a non-null `icdCodes` | **57** (so the query shape works; the zero is a fact about the data) |

This is consistent with the record: #148(b) and #149 both shipped the decision
substrate **with no caller**, and where the coding surface lives is parked under
#148. Nothing is broken. **There is simply no adjudication to learn from.**

**So no threshold is proposed here.** A number derived from a confidence
distribution alone would be a policy choice wearing a measurement's clothes: the
distribution says how *often* the model claims confidence, and nothing whatever
about how often it is *right*.

### ⚠️ ADDENDUM 2026-09-05 — RULING #185 SETTLED IT, AND IT AGREES WITH THIS REFUSAL

**#185 (T2) rules the threshold at `0.90`, labelled SPECIFICATION-DERIVED, and
refuses `0.80` BY NAME.** Read quickly, that looks like it overrides this
section. It does not — **it is this section's conclusion, acted on.**

The number does not come from the distribution below. It comes from the L7a
prompt's own clause, `≥0.9 = explicit diagnosis statement` — *a statement about
what the model was ASKED to mean, never a measurement of how often it is right.*
That is exactly the distinction this recon refused to blur, and #185 makes it
explicit in the ruling's own words rather than leaving a policy choice wearing a
measurement's clothes.

⚠️ **SO THE TITLE OF THIS DOCUMENT STAYS TRUE AND MUST BE READ PRECISELY.** The
number that does not exist is the **data-derived** one. A specification-derived
number exists, is ruled, and is being built to. Anyone citing this recon as
*"no threshold is ruled"* is citing it wrongly.

**#185 requires re-derivation after 50 real doctor decisions, and this recon is
the instrument for it** — the probe table above is the re-run, and its control
row (57 visits with non-null `icdCodes`) is what distinguishes *no decisions
yet* from *a broken query*. Today's count is **0 of 58**; the re-derivation
becomes possible, and owed, at 50.

**The operational consequence of 0.90, measured on today's corpus:** 150 of 212
proposals auto-accept, 62 remain reviewed — **70.8 %**. ⚠️ That is a POPULATION
FACT about proposals that exist now, not a property of the threshold; it moves
with the corpus and must be re-measured, not remembered.

---

## What IS measured, and it answers the design question underneath

**212 proposals across 56 visits**, 2026-06-15 .. 2026-09-04.

### Distribution

| band | n | | band | n |
|---|---|---|---|---|
| 0.30–0.34 | 3 | | 0.75–0.79 | 5 |
| 0.35–0.39 | 3 | | 0.80–0.84 | 13 |
| 0.40–0.44 | 1 | | 0.85–0.89 | 24 |
| 0.45–0.49 | 2 | | 0.90–0.94 | 40 |
| 0.55–0.74 | 11 | | **0.95–0.99** | **110** |

min **0.30** · median **0.95** · max **0.99** · 22 distinct values · 0 nulls.
The derived `confidenceLevel` partitions exactly on the documented 0.5/0.8
boundaries with no crossover, so that defensive re-derivation in `07a` agrees
with the numbers it is derived from.

### What each candidate threshold would actually do

| threshold | auto-accepted | still reviewed | share auto |
|---|---|---|---|
| 0.80 | 187 | 25 | **88.2 %** |
| 0.85 | 174 | 38 | 82.1 % |
| 0.90 | 150 | 62 | 70.8 % |
| 0.95 | 110 | 102 | 51.9 % |
| 0.99 | **2** | 210 | **0.9 %** |

⚠️ **0.99 is not a usable tier.** The model emitted it twice in 212 proposals, so
a design with a "≥0.99" band renders an empty state ~99 % of the time.

### The per-visit shape, which is what a Receipt view actually lays out

Median **2** proposals per visit. At a 0.95 threshold:

- **17 of 56 visits (30 %)** would be **fully** auto-accepted — the review list is empty
- **14 of 56 visits (25 %)** would have **nothing** auto-accepted — the accepted list is empty

At 0.80, 36 of 56 (64 %) are fully auto-accepted.

> **Both empty states are COMMON, not exceptional.** Whatever threshold is
> chosen, the Receipt view needs a designed empty state on both sides. That is
> the finding most directly useful to Design/Admin, and it does not depend on the
> threshold number at all.

### ⚠️ A third of the low-confidence tail is not "uncertain" — it is "nothing found"

9 proposals sit below 0.50. **Three of them are `Z76.89`**, and `Z76.89` never
appears above **0.35**. That is the L7a prompt's own escape hatch: it instructs
the model to emit a single low-confidence `Z76.89` when *no* diagnosis applies,
so the post-validation layer can flag the visit.

**So "low confidence" is two different things in one band** — *the model is unsure
about this diagnosis* and *the model found no diagnosis at all* — and a surface
that renders them identically will tell a doctor the wrong thing about six cases
and the wrong thing again about three.

### Is one global threshold even coherent?

| specialty | proposals | median | min | ≥0.80 | ≥0.95 |
|---|---|---|---|---|---|
| gastroenterology | 94 | 0.92 | 0.30 | 88.3 % | 44.7 % |
| bariatric-surgery | 72 | 0.95 | 0.35 | 91.7 % | 61.1 % |
| ultrasound | 36 | 0.92 | 0.35 | 77.8 % | 47.2 % |
| primary-care | 10 | 0.95 | 0.85 | **100 %** | 70.0 % |

At **0.80** the specialties agree within ~14 points (77.8–91.7, ignoring
primary-care's 10 proposals). At **0.95** they spread 44.7–70.0. So if a single
global threshold is wanted, the evidence for *stability* is better at 0.80 —
though stability is not correctness, and correctness is the thing not measured.

---

## ⚠️ The population, so nobody reads these as product-wide

**4 practices, 4 doctors, 4 specialties, 56 visits, 212 proposals.** GI and
bariatric surgery are **78 %** of all proposals; primary-care contributes 10.

This is a fact about four doctors over eleven weeks, not a property of the
product. AGENTS.md: *a measurement of today's corpus is a fact about the
population, not a property of the code.* **What re-arms it is the pilot roster** —
the same trigger the parked Q1 items wait on.

---

## What would produce the number, concretely

The substrate already exists and is already ruled:

1. The Coding tab surfaces proposals with accept/reject (Design/Admin, #148).
2. `applyIcdDecision` writes `{state, at, byUserId, reason?}` — a **closed**
   5-token rejection vocabulary, already built and already gated.
3. Once decisions exist, the threshold is a direct measurement: **accept rate per
   confidence band**, and the threshold is the lowest band whose accept rate
   clears whatever bar the owner sets.
4. ⚠️ **The bar itself is an owner decision, not a measurement.** "Right 95 % of
   the time" is a claim about acceptable billing error on a signed note, and no
   distribution can supply it.

**Sample size matters and is small today.** With ~2 proposals per visit, a pilot
producing 100 adjudicated visits yields ~200 decisions — enough to separate the
0.80 and 0.95 bands, not enough to split 0.95 from 0.97.

## Summary for Design/Admin

- **No threshold number yet, and the reason is structural, not a delay.**
- **Build for both empty states**; at any plausible threshold, a quarter to a
  third of visits land wholly on one side.
- **Drop any ≥0.99 tier** — 2 of 212.
- **Distinguish `Z76.89` from low confidence**; they are not the same message.
- **0.80 is the more defensible interim line if one is needed at all**, on
  stability across specialties — offered as a policy choice, explicitly not as a
  measured error rate.
