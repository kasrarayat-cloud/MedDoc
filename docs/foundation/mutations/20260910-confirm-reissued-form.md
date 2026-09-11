# DECLARATION — THE CONFIRM OF THE RE-ISSUED 53-CONTROL CONSULT FORM

**Written and committed BEFORE the act, under ruling #311(d) with the decisions
of #312 (as amended before landing).** `run-ruled-mutation.sh` requires this file
to be TRACKED, UNMODIFIED and COMMITTED, so its commit timestamp provably precedes
the rows it describes.

## THE ACT

Confirm the ten re-proposed rows on compiled version
`d2120cdd-74ae-43a3-85a3-1f185401e202` (template
`3877d5cf-ad03-4412-a322-6be0c7dcb3ff`, DRAFT), exactly as #312 decides. Nothing
is certified or activated here; certification is the next, separate act.

```
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260910-confirm-reissued-form.md \
  --in transcribe-md-worker \
  -- npx tsx scripts/confirm-reissued-form.ts \
       --compiled-version d2120cdd-74ae-43a3-85a3-1f185401e202 \
       --expect-fields 53 --expect-certified 43 --expect-confirm 10 --commit
```

A DRY RUN (the same invocation without `--commit`) runs first through the same
door, and its guard table must be all ✓ before the commit run.

**There is no recovery door.** If the end state reports a missing audit row,
the act exits 1 and that is THE FINDING of the judgement. Any recovery is its
own declared act, written after reading what happened. (Round two deleted a
`--reissue-audit` path that could attest a confirmation the act never
performed.)

## PRE-GUARDS — checked BEFORE any row is written

| # | guard | expected |
|---|---|---|
| 1 | the template is a DRAFT | `draft` |
| 2 | the version awaits confirmation | `NEEDS_CONFIRMATION`, no certification row |
| 3 | fields / mappings | **53 / 53**, no unmapped field |
| 4 | already CERTIFIED | **43**, exactly the fields #312 does NOT name |
| 5 | the ten decided rows | still carry the WHOLE proposal that was judged — every attribute, compared as one object, plus label and display order |
| 6 | every confirmed concept | registered in **this runtime's** registry (**7** concepts; the three `manual` rows have none) |
| 7 | the whole 53-row mapping set | sha **`dd4dc3784b5c4baa3581983d03001a2311758cd8953e94429488418b03da05ad`**, as judged |
| 8 | audit rows already naming this act for this version | **0** |

Any mismatch **aborts and writes nothing.** A re-run after success refuses on
guards 4 and 5, so the act cannot apply twice.

## DECLARED DELTA

**MUST change, all on `d2120cdd`:**

| row | before | after |
|---|---|---|
| mappings `CERTIFIED` | 43 | **53** |
| mappings RECOGNIZED / NEEDS_CONFIRMATION | 9 / 1 | **0 / 0** |
| sourceType `manual` | 0 | **3**: Telehealth consent (56), Total minutes spent with patient (70) and Total time minutes (71). Each has concept NULL and `unmentionedPolicy` NULL. **#312 amendment 3**: total time goes to human fill |
| sourceType `visit_metadata` | 2 | **2** (Patient, Age), now CERTIFIED |
| sourceType `extraction` | 51 | **48** |
| `approvedById` = the owning doctor | **0** | **53** |
| `approvedAt` set | **0** | **53**, all at the act's time |
| ⚠️ the stamp on the **43 transferred rows** | none | the owning doctor and the act's time. The writer stamps every row of the set it certifies; this is the approval of the mapping SET. It is named here so it is not read as a finding. |
| `audit_logs` | 12518 at 2026-09-11T02:22:58Z (r230's +6, then +14 logins and visit-list views, 0 template-twin); re-read immediately before the act | **+12**: 1 `TEMPLATE_TWIN_MAPPING_UPDATED` from the writer (target: the note template) + **10** `TEMPLATE_TWIN_MAPPING_UPDATED` from the door (target: each confirmed mapping) + **1** from the door (target: the compiled version: `approvedAsASet 53`, `confirmedFieldIds` ×10, `carriedOverFromTransfer 43`). All 11 door rows carry `confirmingActor = 'ruling #311(d)'`; the aggregate row also carries the resulting `mappingsSha256` and `certifiedMappingCount 53`, and the writer's own row carries the same sha — both are read back by the door. Other lanes' audit rows in the same window are expected, and are excluded by filtering on the action and target. |
| the version's synthetic-test columns | NULL | **NULL** (the writer clears them on any mapping change; they were already NULL) |

**MUST NOT change:**

- every other attribute of the ten (`expectedDataType`, `polarityBehavior`,
  `temporality`, `laterality`, `unitPolicy`, `approvedSynonyms`, `required`,
  `blankPolicy`, `unknownPolicy`, `practiceDefault`, `conceptScope`,
  `unmentionedPolicy`).
- the 43 transferred rows' `sourceType`, `clinicalConcept` and every other column
  **except** the approval stamp above.
- `d2120cdd.certificationStatus` stays **`NEEDS_CONFIRMATION`**; certifications
  stay **4**.
- the certified, ACTIVE version `18a7ae19`: **not one row**. The ACTIVE template
  stays **`939aa9ea`**; `3877d5cf` stays **`draft`**.
- `template_twin_fill_manifests` **5**, source artifacts **8**, compiled versions
  **6**, note templates **17**.
- ⚠️ **the clinical counts: visits 58 · patients 46 · signatures 40.** This act
  touches no visit and no note.
- `ai_calls` 1686 and `api_usage_events` 1867: **no model is called.**

## WHY THE ANSWER CANNOT BE TUNED AFTERWARDS

Every quantity above is fixed here, in a committed file, before the act. The
runner prints this file's commit time and the act's start time, and the two
bracket the rows. **A difference this declaration does not name is THE
FINDING**, whatever its explanation sounds like afterwards.
