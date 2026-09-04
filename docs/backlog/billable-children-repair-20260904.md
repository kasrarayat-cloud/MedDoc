# `billableChildrenOf` — the repair ruling #149(f) named, now that its condition is met

**Filed 2026-09-04 by the Data/Audit session, as the T8 follow-up.**

> **STATUS UPDATED 2026-09-04 — THE DERIVATION IS BUILT; THE TWO OWNER-SHAPED
> CLAUSES ARE NOT.** `billableDescendantsOf` ships in
> `packages/ai/src/data/icd10-allowlist.ts` **with no caller**, gated by
> `gate-billable-descendants.test.ts` (17 assertions, 6 mutation arms proved).
> Ratified for build by the owner, scoped explicitly to *"the #149(f) repair"*.
>
> **What is still NOT decided and was NOT touched:** clause (a), the reason-token
> split in `icd-drops.ts`; and clause (b), whether the substitute chip ships at
> all, which is parked under #148 and belongs to the Coding tab surface. Both
> remain owner questions. Nothing in `icd-drops.ts`, `07a-icd-coding.ts` or the
> Coding tab was edited by this work.
>
> ⚠️ **AND AN EARLIER DRAFT OF THIS BLOCK SAID #149(b) *FORBIDS* THE RENAME.
> THAT IS FALSE ON BOTH HALVES, AND THE LABEL DECIDES THE ROUTING.** Measured
> against the shipped code: `ICD_DROP_REASONS` holds exactly four tokens, one
> per exit, and a header (`M54.5`) and a fabrication (`K58.3`) **already share
> `not_in_verified_allowlist`** because both leave through the same exit —
> `isValidIcd10` failing at `07a-icd-coding.ts:462`. A rename therefore merges
> nothing; the partition stays four exits, four tokens, byte-identical. And
> #149(b) is scoped to those FOUR EXITS, its cited precedent being five exits
> collapsing into one bucket — it says nothing about SUB-DIVIDING one exit.
> #149(e) explicitly *permits* the re-reading ("may be re-read as
> `not_billable`"), so the earlier draft cited a ruling as a prohibition
> against something a sibling clause allows.
>
> **The honest status is UNDECIDED — no ruled precedent covers the split.** That
> distinction is not cosmetic: under AGENTS.md's standing-authority table, *"a
> ruling forbids it"* closes an item, while *"no ruled precedent covers it"* is
> **class (a)** and must reach the owner. Mislabelling it would have routed an
> owner question into the wrong bucket, in the artifact the next session greps.

## Why this exists

Ruling #149(f) **deleted** `billableChildrenOf` rather than repairing it, and it
wrote down the single condition that would make a repair sound:

> **RE-ARMING CONDITION, so this is a lookup rather than a judgement:** the
> allowlist becoming the full CMS billable set (its own header's "PHASE 7 PATH")
> — at which point membership and billability coincide, `not_in_verified_allowlist`
> may be re-read as `not_billable`, and a sibling derivation becomes sound.

**T8 met that condition.** `ICD10_ALLOWLIST` is now the complete CMS FY2026
valid-for-submission set (74 719 codes), and `ICD10_HEADERS` carries the 23 467
category headers alongside it. This file is the lookup that ruling asked a
future reader to perform, with the numbers re-measured rather than assumed.

## What the ruling's own reference case does now

#149(f) refused the feature on one measurement — a prefix scan of the STARTER
set returned every child *we happened to carry*, so a singleton meant "only one
sibling made our list" while the UI rendered it as "there is only one answer":

    billableChildrenOf('E66.0')  ->  ['E66.01']          # E66.09 simply absent

`E66.0` is obesity due to excess calories; `E66.01` is **morbid (severe)**
obesity. The one-tap chip would have upcoded. Re-measured against the complete
set:

| parent | starter set returned | complete set returns |
|---|---|---|
| `E66.0` | `['E66.01']` — upcodes | `['E66.01', 'E66.09']` |
| `E11.6` | `['E11.65']` — hyper- where the note may say hypo- | 12 codes, incl. `.649` hypoglycaemia |
| `K21.0` | — | `['K21.00', 'K21.01']` |
| `M54.5` | — | `['M54.50', 'M54.51', 'M54.59']` |

**The upcoding vector is closed by the data, which is what the ruling predicted.**

## The population facts that decide whether a singleton is still dangerous

Measured over all 23 467 headers, prefix-scanning the complete billable set.
The distribution reconciles to 23 467 exactly, so there is no unnamed bucket:

- **0 headers have ZERO billable descendants.** Every header resolves to at
  least one submittable code, so *"this is a header — bill one of these"* is an
  answer that always exists. Nothing has to handle an empty case in production,
  though the code must still refuse to *assume* that (see the guard below).
- **45 headers (0.2 %) have EXACTLY ONE.** Inspected: they are genuine
  singletons — `H54.413 -> H54.413A`, `I1A -> I1A.0`, `S06.1X7 -> S06.1X7A` —
  a parent whose only specificity is a 7th-character extension. **A singleton
  now means what the surface renders it as**, which is the precise thing that
  was false before.
- The largest header expands to **3 096** descendants. That is a surface
  problem, not a data problem, and it belongs to whoever owns the Coding tab.

## What is sound now, and what is STILL NOT

**Sound:** deriving the substitute set by prefix scan; rendering a singleton as
the only answer; the claim *"these are the billable codes under this header."*

**Still not sound, and none of it is fixed by having complete data:**

1. **It returns DESCENDANTS, not immediate children, and the old name lied
   about that.** `I71.0` is a header whose child `I71.01` is *also* a header;
   the scan returns the grandchildren. For a substitute chip that is the right
   answer — every one is billable — but the function must be named for what it
   computes. `billableDescendantsOf` is the honest name.
2. **Billable is not appropriate.** Membership means *valid for submission*. It
   says nothing about coverage, medical necessity, or which descendant the chart
   supports. **The surface may PRESENT; it may never AUTO-APPLY.** That was true
   before and is not improved by a bigger list.
3. **"All of them, never one" is a UI contract the data can now honour and the
   UI still has to keep.** A scan that returns 3 096 codes and a surface that
   shows the first three has reintroduced #149(f)'s defect one layer up, with
   the data blameless.
4. **The empty case must fail closed anyway.** Zero-descendant headers do not
   exist *in FY2026*. That is a population fact about today's corpus, not a
   property of ICD-10-CM, and it re-arms on any future edition. `[].length === 0`
   must return "no substitute available", never a silent empty chip.

## The two owner-shaped clauses — NOT decided here

**(a) The reason-token split.** #149(e) says the token *"may be re-read as
`not_billable`"* once this condition is met. ⚠️ **A straight rename would be
wrong, and #149(b) is why.** There are now **two** distinguishable refusals:

  - a real ICD-10-CM entry that is a HEADER (`Z83.71`, `M54.5`) — actionable,
    the doctor should bill a descendant;
  - a string that is not a code in any form (`K58.3`, `Z99.999`) — a
    fabrication or a typo, and there is nothing to offer.

⚠️ **AND THE FIRST DRAFT OF THIS SECTION GOT THE RULING WRONG.** It claimed
#149(b) forbids the rename because renaming "merges exactly those two". Measured
against the shipped code, **they are already merged**: both refusals leave
through the SAME exit (`isValidIcd10` failing), so both already carry
`not_in_verified_allowlist`, and `ICD_DROP_REASONS` is four tokens for four
exits either way. A rename changes a label, not a partition.

#149(b) — *"FOUR EXITS, FOUR REASON TOKENS, NEVER ONE BUCKET"* — is about the
four EXITS, and its cited precedent is five exits collapsing into one bucket. It
does not speak to sub-dividing a single exit. **So the split is UNDECIDED, not
forbidden**, and #149(e) already *permits* the re-reading.

**What remains genuinely owner-shaped is the PRODUCT question**, and it is worth
stating plainly because it survives the correction: a header refusal is
*actionable* (bill a descendant — and one always exists), while a fabrication
refusal has nothing to offer. Those are different things to tell a doctor. Today
they are one token and one message. Whether to separate them, and what the
surface should say, is a decision about what the product claims — **class (a),
no ruled precedent** — and this file does not make it.

**(b) Whether the substitute chip ships at all.** #149(f) refused a product
surface. The condition it named is met, which makes the surface *possible*; it
does not make it *decided*. Where the coding surface lives is PARKED under #148
and is an owner question.

## What the built derivation actually guarantees, and what it does not

Measured against the complete FY2026 release, all four re-derived for the build:

| measurement | value | why it matters |
|---|---|---|
| headers with **zero** billable descendants | **0** | *"bill one of these"* is always answerable |
| headers with **exactly one** | **45 (0.19%)** | each is a COMPLETE set of one rather than a truncated one — the property that was false before. By shape: 43 gain a 7th-character extension, **2 gain a 4th character carrying a distinct concept** (`I1A` → `I1A.0`, other → **resistant** hypertension; `U09` → `U09.9`). An earlier draft called all 45 "only a 7th-character extension", inferred from the majority rather than measured. |
| billable codes with a billable descendant | **0** | billable codes are leaves, so a submittable code correctly offers no substitute |
| dotted vs undotted prefix agreement | **242,114 pairs, 0 disagreements**, both directions | scanning the stored dotted form is *sound*, not merely convenient |

⚠️ **THE FIRST ROW IS A POPULATION FACT ABOUT FY2026, NOT A PROPERTY OF
ICD-10-CM**, and it re-arms on every future edition. The implementation still
fails closed on the empty case and the gate asserts the fact explicitly, so an
edition that breaks it says so loudly instead of silently producing empty
substitute lists.

⚠️ **AND `S82.62X`-SHAPED INPUT IS WHY THE FUNCTION REFUSES WHAT IT CANNOT
CHARACTERISE.** 4,553 strings in FY2026 are a prefix of a billable code while
being neither billable nor a header — **6,257 once the codes are dotted, which
is the form the guard actually reads** (the extra 1,704 are `A00.`-shaped
trailing-dot prefixes that exist only after a dot is inserted; an earlier draft
quoted the undotted 4,553, a universe this module never sees). `S82.62X` alone
prefixes sixteen. Those
are exactly what you get by dropping a required 7th character, which is a
plausible model or dictation error. Answering one would present a confident
substitute list for a category that does not exist, so the function returns `[]`
for any input that is not itself a known code.

**Cost, measured rather than assumed:** +20 MB heap and ~0.3 ms for the first
call (a sorted array built once at module load); ~1.5 µs per lookup; all 23,467
headers resolve in 35 ms. The worker container sits ~220 MiB against a 1 GiB
limit.

## What T8 already shipped toward this

`isIcd10Header(code)` exists in `packages/ai/src/data/icd10-allowlist.ts` and
**ships with no caller**, the same way #148(b) and #149 did. It is the predicate
the split in (a) would key on. Nothing reads it, so nothing changes until
somebody rules that it should. `billableDescendantsOf` now sits beside it on the
same terms.

## ⚠️ SIX LIVE COMMENTS NOW ASSERT A FALSE PREMISE — and they are not this session's to edit

Found by the T8 adversarial pass. The epitaph's own thesis is that prose decays
silently; the commit that says so left downstream files present-tense-asserting
the fact it retired. Measured at commit `1376670c` with
`grep -rn "604-code" --include=*.ts --include=*.tsx apps/ packages/`:

| file | what it now says falsely |
|---|---|
| `apps/transcribe-md/src/lib/icd-drops.ts:31` | "`isValidIcd10` is `ICD10_ALLOWLIST.has(...)` over a **604-code STARTER SET**" |
| `apps/transcribe-md/src/lib/icd-drops.ts:147` | "absent from the 604-code verified allowlist" |
| `apps/transcribe-md/src/app/visits/[id]/icd-coding-view.tsx:86` | "membership of a **604-code STARTER SET**" |
| `apps/transcribe-md/src/app/visits/[id]/icd-coding-view.tsx` (2nd) | "604-code STARTER set offered" |
| `apps/transcribe-md/src/app/visits/[id]/__tests__/gate-f8-s2-coding-view.test.tsx:199` | "a 604-code STARTER set, and 51 of the 65…" |
| `apps/transcribe-md/src/lib/__tests__/gate-f8-icd-drop-record.test.ts:125` | "a 604-code STARTER set that its own header…" |

**⚠️ `icd-drops.ts:31` is not decorative — it is the load-bearing ARGUMENT for
the shipped reason token.** It reasons: *"a refusal means 'absent from our
verified list', which is a fact about OUR COVERAGE — not 'not a billable
ICD-10-CM code', which is a fact about the CODE."* That premise is now gone.
The conclusion may still be right, but **for a different reason and only
partly** — see the token-split analysis above, which is exactly why this is
owner-shaped and not a find-and-replace.

**WHY T8 DID NOT FIX THEM.** `icd-coding-view.tsx` and its test are the Coding
tab UI, owned by another session; `icd-drops.ts` and its gate carry ruled
reason-token reasoning (#149(b), (e)). Editing either would be a peer's file or
a ruled decision, and the correct move is to hand over the measurement rather
than act across the boundary. **The doctor-facing label is unaffected** — it
reads "Not in this build's verified set", which remains true.

## Cross-references

- `docs/foundation/rulings/2026-08-20--2026-08-26.md` — #149(b), (e), (f)
- `apps/transcribe-md/src/lib/icd-drops.ts` — the drop record and its tokens
  (⚠️ **ruled territory; T8 deliberately did not touch it**)
- `packages/ai/src/data/icd10-allowlist.ts` — the epitaph and the new API
- `scripts/data/build-icd10cm.mjs` — the generator and its pinned provenance
