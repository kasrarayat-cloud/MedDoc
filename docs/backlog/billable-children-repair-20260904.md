# `billableChildrenOf` — the repair ruling #149(f) named, now that its condition is met

**Filed 2026-09-04 by the Data/Audit session, as the T8 follow-up.**
**Status: FILED, NOT BUILT. Two clauses inside it are owner-shaped.**

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

#149(b) ruled **"FOUR EXITS, FOUR REASON TOKENS, NEVER ONE BUCKET"**, citing the
`notMentionedCount` collapse where a REFUSAL and an ABSENCE became one number.
Renaming one token into `not_billable` merges exactly those two. **The honest
move is a SPLIT, not a rename** — and splitting a shipped token is a ruling, not
a refactor.

**(b) Whether the substitute chip ships at all.** #149(f) refused a product
surface. The condition it named is met, which makes the surface *possible*; it
does not make it *decided*. Where the coding surface lives is PARKED under #148
and is an owner question.

## What T8 already shipped toward this

`isIcd10Header(code)` exists in `packages/ai/src/data/icd10-allowlist.ts` and
**ships with no caller**, the same way #148(b) and #149 did. It is the predicate
the split in (a) would key on. Nothing reads it, so nothing changes until
somebody rules that it should.

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
