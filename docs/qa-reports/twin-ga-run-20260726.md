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

## S2(b)-COMPLETE — the sourceType persistence round-trip ✅

The miss: `sourceType` was added to the Zod schema and the proposer but there was
no COLUMN, so every mapping round-tripped back as `extraction` and both manual
carve-outs in the gate were inert code. Two certification runs were burned before
the persistence path was checked. Fixed end-to-end, traced statically FIRST.

**1. Migration — additive.** `20260726010000_twin_mapping_source_type`:

```sql
ALTER TABLE "template_twin_semantic_mappings"
  ADD COLUMN "sourceType" TEXT NOT NULL DEFAULT 'extraction';
```

NOT NULL *with* a DEFAULT, so every existing row is valid without a backfill.
Proof on QA after apply — 2000 pre-existing rows, none invalidated, none touched:

```
 column_name | data_type | is_nullable |   column_default
 sourceType  | text      | NO          | 'extraction'::text

 sourceType | count
 extraction |  2000
```

Rollback: `ALTER TABLE "template_twin_semantic_mappings" DROP COLUMN "sourceType";`
Nothing reads it when it is absent except the code shipped alongside it.

**2/3. Write and read.** `updateTemplateTwinMappings` now sends
`sourceType: mapping.sourceType`; `fromPersistedMapping` takes `sourceType:
row.sourceType`; both the certification projection and the workspace projection
select it. App typecheck clean.

**4. Round-trip — both halves.**

Static, every link (`__tests__/source-type-roundtrip.test.ts`, 16/16): the column
exists in the model, the update payload writes it, the read projection selects and
parses it, the workspace projection carries it to the review surface, and both
gate checks honour the manual carve-out. A break anywhere makes the carve-outs
silently dead again — which looks exactly like a certification bug and is not one.

Live, against the QA database (`scripts/prod-smoke/source-type-roundtrip.ts`):

```
[rt] chose mapping cmrzutiha000e0wo3g4xh7ywc (sourceType=extraction)
[rt] read back sourceType=manual
[rt] parsed sourceType=manual
[rt] ROUNDTRIP PASS — wrote manual, read manual: true
[rt] restored sourceType=extraction
```

**Operational finding, recorded because it cost a cycle:** `db-migrate` in
`docker-compose.qa.yml` is `image:`-only (no `build:`), so `--build` is a silent
no-op and the image's baked migrations go stale (70 vs 72 on disk). It reports
"No pending migrations to apply" while the column is genuinely absent. Correct
invocation mounts the live directory:

```
docker compose -f docker-compose.qa.yml run --rm \
  -v /opt/meddoc-pro/packages/db/prisma:/app/packages/db/prisma db-migrate
```

## S4 — reaching CERTIFIED: seven defects, found by probe, not by guessing

The first three certification attempts each blocked on a *different* set of
fields. That is the tell: the run was not deterministic, so no fix could be
judged. Everything below was found by replaying a compiled version's fill from
its stored inputs (`scripts/prod-smoke/twin-fill-probe.ts`) — seconds, no
writes — instead of an eight-minute run that mutates state.

**Blocking issues, in order: 20 → 11 → 4 → 0.**

1. **The classification was never written at draft creation.** `sourceType` went
   into the schema, the proposer and the gate, but `create-draft.ts` did not
   include it, so every row was born `extraction` and both manual carve-outs
   were inert. The static round-trip test covered the update path and missed the
   create path — the one that was broken.

2. **Three of five mapping projections omitted `sourceType`.** Two of those are
   hashed and compared, so the mismatch surfaced as *"Mappings changed after the
   page loaded"* — which reads like a concurrency bug and is not one. A test now
   asserts, per module, that the count of mapping selects equals the count that
   carry `sourceType`.

3. **Certification depended on TWO sampling decisions.** The note was pinned;
   Layer 3 was not, and it re-extracted every attempt. Identical encounter text,
   different facts, different blockers. The extraction is now pinned beside the
   note under the same content hashes, so the synthetic proof is a pure function
   of (document, encounter text).

4. **The bridge walked 26 IR rows against a 13-row table with one cursor.** L4
   renders the grid as two tables with identical row labels, so the right-leg
   rows matched and consumed the LEFT table's rows first. Every such pairing was
   correctly refused on laterality — but the row was already spent, so no
   left-leg cell could fill. Pairing is now decided by evidence: a note row is
   consumed only when it fills something, so a refusal costs nothing.

5. **The resolver was guessing at rows it cannot see.** In a 26-row grid every
   reflux cell shares one concept, so it could not say which row a given 2.4
   seconds belonged to. It returned `needs_clinician_input` for 33 cells the
   encounter had said nothing about. Fixed-grid cells now defer to the bridge; a
   repeating-row prototype still resolves in the resolver, because it expands one
   row per fact and has no row to address.

6. **A measurement fact stated its value as a number.** The validator re-derives
   a text cell as `typeof fact.value === 'string' ? fact.value : null`, so all
   nine correctly-placed measurements — right number, right leg, right segment,
   real citation — came back `ASSERTION_NOT_SUPPORTED`. A fact's `value` is its
   stated form; `number` and `unit` are the structured attributes beside it.

7. **A select was conflicting over sentences it could never contain.** Dropdowns
   inside sentences map to a coarse concept like `exam.vascular`; judging
   polarity across every vascular statement made a conflict out of four
   unrelated ones. Conflicts are now judged over facts that could actually fill
   the field. A near-match still reaches a clinician as
   `select_value_not_exact_option` — that path is untouched.

8. **An unapproved temporality cited the facts it had just rejected.** The
   resolution declared their temporality unapproved and attached them as the
   field's evidence; the validator flagged both. Absence is now absence, with the
   reason code preserved.

9. **The grid's two halves were mapped as different kinds of thing.** The reflux
   cell names itself; the diameter cell is labelled with the vein, so the model
   chose per field — `measurement.diameter` for the right leg,
   `test.vascular_ultrasound.result` for the left. Both registry-valid, so
   nothing rejected either, and every left diameter came back "no supporting
   fact". The structure decides now, the same way the bridge already reads it.

**Not one evidence rule was relaxed.** `factSatisfiesMapping`,
`matchMeasurementFact`, the validator and the roundtrip are byte-identical; the
gate's floors are unchanged. Every fix was upstream of them — a value written in
the wrong shape, a row addressed by the wrong component, a conflict judged over
the wrong facts.

## S4 — CERTIFIED, twice, identical ✅

Two consecutive runs of `twin-ga-proof.ts` against the doctor's own WM_IOV docx:

```
run A                                     run B
4/80 off-registry (the 4 manual fields)   4/80 (same four)
CONFIRM 80 mappings                       CONFIRM 80 mappings
pin REUSED  templateSha=37813a6031d4      pin REUSED  templateSha=37813a6031d4
            generatedAt=01:47:03.372Z                 generatedAt=01:47:03.372Z
SYNTHETIC test: OK                        SYNTHETIC test: OK
filled=13 conflicts=0 needsReview=19      filled=13 conflicts=0 needsReview=19
notMentioned=48 criticalUnresolved=7      notMentioned=48 criticalUnresolved=7
roundTrip.fields=80 (IR declares 80)      roundTrip.fields=80 (IR declares 80)
CERTIFY status=CERTIFIED                  CERTIFY status=CERTIFIED
                                          NATIVE DOCX written: 49368 bytes
```

Identical, from the same pinned note under the same content hashes. The four
`manual` fields are attested blank; the fill floors are met by real evidence
(13 ≥ 10 filled, measurement cells among them); 48 fields are proven blank.

## S5 — real-visit proof: HONEST, NOT YET COMPLETE ⚠️

The visit path now behaves correctly and does NOT yet produce the filled
document. Both halves matter, so both are stated.

**What it fixed, and how it was caught.** The first passing run reported
`nativeTemplateApplied=true` and wrote a 49 297-byte file. Unzipping it and
grepping for the dictated numbers found *none of them*: the export path re-fills
from the visit row, the harness had never persisted the extraction there, so the
fill resolved nothing, validated trivially — there is no populated value to
object to — and returned the doctor's blank form wearing a success flag. That is
precisely the silent-empty-document failure this whole chain exists to prevent,
and it reached the export seam. `VERIFIED` now requires at least one filled
field, and an empty fill says so in the log.

Also fixed: the four `manual` context fields resolved as
`clinical_concept_unmapped`, which is BLOCKING at visit time. They would have
refused the native document on every visit forever while the certificate
attested them blank — the two halves of one decision disagreeing. They are blank
by design and now say so.

**Where it stands.** With the extraction persisted and a full dictation:

```
MANIFEST status=NEEDS_REVIEW filledCount=13 notMentioned=53 needsReview=14
BLOCKING 14 FIELD_NEEDS_CLINICIAN_INPUT
EXPORT nativeTemplateApplied=false nativeTemplateReason=manifest_incomplete
```

Both legs' measurement cells fill with real citations (13). The remaining 14 are
enumerated dropdowns — SIDE OF EXAM, CLINICAL INDICATIONS (×6), the deep-system
sentences. The L4 note *does* choose them in the form's own wording
(`SIDE OF EXAM: Bilateral Detailed`, `CLINICAL INDICATIONS: Swelling,
Heaviness`), so the note is not the problem: the picks bridge reports
`no_supporting_fact` for each, i.e. it cannot tie the chosen option back to a
cited fact. At visit time a clinically material field left unanswered blocks the
native render — deliberately, and test-pinned — so the export refuses and the
styled export stands.

**This is the one open item, and GA waits behind it.** The export refusing is
correct behaviour, not a passing proof: the doctor does not yet get their own
form back for a real visit.

## S6 — GA: NOT STARTED

Prod is untouched and verified so:

```
9/9 containers healthy
NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX unset -> OFF
pending migrations NOT applied: twin_pinned_synthetic_note,
                                twin_mapping_source_type,
                                twin_pinned_entities
0 synthetic strays (prod and QA)
app 307 / pro 200 / quillmd.com 200 / admin 404 (co-tenants incl. LeatherERP)
working tree: only the expected `M Caddyfile`
```

One-shot rollback if anything had been deployed: `:pre-finish-20260725`. Nothing
was.
