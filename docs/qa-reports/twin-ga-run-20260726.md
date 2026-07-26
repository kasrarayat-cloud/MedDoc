# Twin native-WORD — autonomous run 2026-07-26

Evidence appended per stage. Prod touched only at S6.

## S1 — empirical dumps ✅

Enriched encounter written in the options' OWN language, then dumped. All six
families emit:

```
[s1] facts=12
[s1] assessment                                n=1 numeric=0  "Chronic venous hypertension with other complic…"
[s1] exam.vascular_great_saphenous_vein        n=1 numeric=0  "Demonstrates reflux from the common femoral ve…"
[s1] exam.vascular_left_deep_venous_system     n=1 numeric=0  "No evidence of obstruction or insufficiency"
[s1] exam.vascular_right_deep_venous_system    n=1 numeric=0  "No evidence of obstruction or insufficiency"
[s1] hpi.context                               n=1 numeric=0  "Duplex Doppler color flow ultrasound of the de…"
[s1] measurement.diameter                      n=2 numeric=2  "7" / "8"
[s1] measurement.reflux_time                   n=2 numeric=2  "2.4" / "3.1"
[s1] past_medical_history                      n=1 numeric=0  "Previous vein treatment"
[s1] test.duplex_…_venous_system_b.result      n=1 numeric=0  "Right deep venous system: no obstruction or in…"
[s1] test.name                                 n=1 numeric=0  "Duplex Doppler color flow ultrasound of the de…"
```

**Registry additions: NONE NEEDED.** All ten are already registered — the exact
concepts by name, the rest via the existing patterns:

```
[reg] IN  assessment / measurement.diameter / measurement.reflux_time /
          past_medical_history / test.name
[reg] IN  exam.vascular_great_saphenous_vein        (pattern exam.<thing>)
[reg] IN  exam.vascular_left_deep_venous_system     (pattern)
[reg] IN  exam.vascular_right_deep_venous_system    (pattern)
[reg] IN  hpi.context                               (pattern hpi.<thing>)
[reg] IN  test.duplex_…_b.result                    (pattern test.<study>.result)
[reg] ALL EMITTED CONCEPTS REGISTERED: true
```

### Rulebook-decided question (R4 + R10)

The dump showed emitted concepts carrying anatomy (`exam.vascular_great_saphenous_vein`),
which R4 forbids in concepts. Resolved: R4's anatomy clause governs what WE
author; the extractor's own naming is empirical fact and is matched by pattern.
Our authored concepts stay anatomy-free — `measurement.diameter` serves all 26
rows. No registry growth, so R4's "empirical only" clause is satisfied trivially.

**The real defect was therefore NOT a narrow registry.** It was the proposer
INVENTING concepts and being rejected afterwards. Per R10 (one mechanism), the
registry is now in the proposer's prompt as a closed vocabulary — constrain at
generation, not by post-hoc rejection.

Result: **off-registry proposals 72/80 -> 4/80.**

## S2/S3 — PARKED (memo below); S4/S5/S6 depend on them

With the proposer constrained, certification still stops:

```
[template-twin:mappings] 4/80 proposals were off-registry or unconcepted
[ga] TemplateTwinLifecycleError: The approved mapping for field 1 is incomplete or incompatible.
```

Correct behaviour. Those 4 fields have no extraction concept because they are
not dictated — they are the context_default / manual classes. The gate requires
every field to carry a concept, and R7 forbids scoping that down. So they must
become ready by a DIFFERENT route: `sourceType`, which is precisely S2/S3 and is
not built.

### Decision memo — the unified defaults lane

**Question.** How do context_default / manual fields become gate-ready without
an extraction concept?

**Options.**
(a) Build S2 + S3 as specced: `sourceType` on mappings, one flagged-review lane
    serving context_default AND practice_default (R6, R10), provenance validated
    option-exact-or-blank, guard lifted for both in the same PR.
(b) Ship S2 only (`sourceType` + manual → attested-blank), park the lane; the 4
    fields render honestly blank (R8) and GA proceeds without deterministic fills.
(c) Do nothing; certification stays blocked.

**Recommendation: (b) then (a).** (b) unblocks certification, GA and the export
proof using only mechanisms that already exist (needs-input attestation), with
no new provenance type on the evidence path. (a) is then a self-contained
follow-up whose only job is the lane — and per R6/R10 it must land for
context_default and practice_default together, lifting the existing
practice-default guard in the same change. Splitting them would be the two
half-solutions R10 forbids.

**Why I did not just do (b) here:** it is real work on the mapping schema and
the certify review surface, and this run had already spent its budget reaching
the 4/80 result. Starting it thin at the end is how an evidence-path defect
ships.

## S7 — riders ✅

* Open PRs on the branch: **none** (all work is committed to
  `fix/twin-visit-export-harness`; nothing awaiting merge).
* Disk: **77% -> 72%** (81 G free). Removed six superseded twin build images and
  15.75 GB of build cache. **26 rollback tags intact; 14 co-tenant images
  untouched.** Target was <70% — 72% is short; the remainder is live volumes
  (33 G, prod data) and in-use images, which are not reclaimable without
  touching prod or co-tenants.

## S2(b) — sourceType: built, NOT persisted (the blocker)

Landed:
* `sourceType` on `SemanticMappingSchema` — `extraction | context_default |
  visit_metadata | manual`, defaulting to `extraction`.
* `classifyFieldSource()` — label-driven, enumerated. The four non-extraction
  families (referring physician, machine, location/address, technologist)
  classify **manual**. `context_default` is declared but deliberately
  UNIMPLEMENTED: a deterministic fill puts content into a signed note the
  clinician never dictated, and the review lane does not exist. Honest blank
  beats silent fill; the guard holds.
* The proposer classifies from the COMPILER's label, not the model's guess —
  same doctrine as `expectedDataType`.
* Manual carve-outs in BOTH gate checks (`fieldsReady`) and the mapping-update
  validation: a manual field is ready on classification + type compatibility,
  with no clinical concept, because it can never produce a value. No evidence
  rule is relaxed — nothing about a manual field can fill.

**The blocker: `sourceType` is not persisted.** It exists in the Zod schema and
the proposer, but `template_twin_semantic_mappings` has no such column, so every
mapping reads back from the database as `extraction` and both carve-outs are
dead code in practice:

```
[template-twin:mappings] 5/80 proposals were off-registry or unconcepted
[ga] TemplateTwinLifecycleError: The approved mapping for field 1 is incomplete or incompatible.
```

Remaining work, fully specified and small:
1. additive migration — `sourceType TEXT NOT NULL DEFAULT 'extraction'` on
   `template_twin_semantic_mappings`;
2. persist it in `updateTemplateTwinMappings`' update payload;
3. read it in `fromPersistedMapping` and the workspace projection;
4. re-run: 5/80 should go to 0 blocked and certification should proceed.

That is a schema round-trip, not a design question — nothing in the rulebook is
unresolved. S4/S5/S6 remain blocked behind it; S3 was not reached.

## S7 (carried) — riders

Disk **77% -> 72%** (81 G free), 26 rollback tags intact, 14 co-tenant images
untouched. No open PRs; all work committed to `fix/twin-visit-export-harness`.
