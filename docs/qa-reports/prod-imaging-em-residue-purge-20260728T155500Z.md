# Prod imaging E/M residue — purge record

**When:** 2026-07-28T15:55Z
**Database:** prod `meddoc` (`meddoc-pro-postgres-1`)
**Scope:** ONE column (`emScoredCode`), UNSIGNED imaging visits only. Nothing else.
**Containers touched:** none. No deploy, no restart. Co-tenants unaffected.

## Why

An imaging report has no office-visit E/M level. Until 2026-07-28 the app passed
`specialtyLabel(visit.specialty)` — `'Ultrasound'` — into `isImagingReportSpecialty`,
which compares against the id `'ultrasound'`. Always false. So `emNotApplicable`
was always false on the one specialty it exists for, and **every ultrasound visit
computed an office E/M level and persisted it to `emScoredCode`**.

The fix shipped in PR #419 (`specialtyId` as a separate prop). It stopped new
artifacts — **0 imaging visits created after the fix carry E/M state**, which is
the independent confirmation that it works. It did not clean up behind itself.

These are unsigned pre-fix test visits. `emScoredCode` is the baseline a re-score
measures movement against; no export path reads it.

## Guard

The transaction aborted unless the target set was **exactly** the five known ids,
with a separate assertion that no signed row could enter the set:

```
NOTICE:  guard passed: exactly the 5 expected unsigned imaging rows
```

Predicate: `specialty='ultrasound' AND "signedAt" IS NULL AND "emScoredCode" IS NOT NULL`.
Signed imaging rows carrying `emScoredCode` before the run: **0** — so the
predicate excluded nothing that existed, and would have aborted if it had.

## BEFORE

| id | emScoredCode | status | signedAt |
|---|---|---|---|
| `cms1fjiz6000i01ntfxd9sy0c` | 99212 | READY | null |
| `cms2e4k6w000m01od9f7nj5vv` | 99212 | READY | null |
| `cms2qfn4g000i01uri6javo2t` | 99212 | READY | null |
| `cms3k19d2001801mkyarrlq57` | 99212 | READY | null |
| `cms40jr2i002v01mzn9z5r8w1` | 99214 | READY | null |

## AFTER

`UPDATE 5`, `INSERT 0 5` (audit), re-count → **0**.

```
remaining_unsigned_imaging_with_em
                                 0
```

### Blast radius — nothing else moved

| id | status | soapVersion | emStale | signedAt | soapFinal len |
|---|---|---|---|---|---|
| `cms1fjiz6000i01ntfxd9sy0c` | READY | 1 | false | null | 3628 |
| `cms2e4k6w000m01od9f7nj5vv` | READY | 13 | true | null | 5380 |
| `cms2qfn4g000i01uri6javo2t` | READY | 1 | false | null | 3188 |
| `cms3k19d2001801mkyarrlq57` | READY | 1 | false | null | 3499 |
| `cms40jr2i002v01mzn9z5r8w1` | READY | 1 | false | null | 5538 |

(`cms2e4k6w`'s `soapVersion=13` / `emStale=true` are its own pre-existing state,
not an effect of this run.)

## Audit trail

Five rows, one per visit, `id = aud_emrem_<visitId>`:

```
targetId                   action            metadata
cms1fjiz6000i01ntfxd9sy0c  EM_LEVEL_CHANGED  from=99212 to=NULL cause=operator_remediation
cms2e4k6w000m01od9f7nj5vv  EM_LEVEL_CHANGED  from=99212 to=NULL cause=operator_remediation
cms2qfn4g000i01uri6javo2t  EM_LEVEL_CHANGED  from=99212 to=NULL cause=operator_remediation
cms3k19d2001801mkyarrlq57  EM_LEVEL_CHANGED  from=99212 to=NULL cause=operator_remediation
cms40jr2i002v01mzn9z5r8w1  EM_LEVEL_CHANGED  from=99214 to=NULL cause=operator_remediation
```

`metadata.reason` records the provenance in full. `userId` is **NULL** because
this was not the doctor's action — an existing convention in this table (54 prior
rows). `EM_LEVEL_CHANGED` was chosen because it is the only truthful action in the
enum for "the E/M level baseline changed", and it had **zero writers and zero
readers**, so recording an operator remediation under it misleads no parser. Its
documented contract names `cause ∈ {suggestion_adopted, suggestion_dismissed}`;
`operator_remediation` is a third value, used here deliberately and recorded so.

## ⚠️ NOT purged — a different finding, deliberately left

`cms3k19d2001801mkyarrlq57` also carries:

```json
cptCodes = {"em": {"override": {"code": "99212", "overriddenAt": "2026-07-27T20:48:15.183Z"}}}
```

That is a **doctor-set override**, not a computed baseline — someone chose 99212
through the UI on 2026-07-27, while the label bug still made the level surface
reachable on imaging visits. Clearing it would delete a recorded clinical
judgement, which is a separate decision from clearing a computed artifact, and it
is outside the authorised predicate (`emScoredCode` only).

**It is not inert.** `loadVisitExportData` projects `cptCodes.em` with no imaging
guard (`src/lib/visit-export-server.ts:129`), and both renderers print
`data.em.code` whenever it is truthy (`src/lib/pdf-generator.ts:452`,
`src/lib/ehr-formatters.ts:183`). Verified by calling the real projection with
that row's exact blob:

```
projectDisplayedEmCode(em, isSigned=false) = "99212"
projectEmForDisplay = {"override":{...},"code":"99212"}
ehr line would read:  "  99212 — undefined"
```

So this unsigned ultrasound visit would export an office E/M code today. Two
separate follow-ups, neither authorised in this pass:

1. **Data:** decide what to do with that one doctor-set override.
2. **Code:** the export path has no imaging guard of its own. The invariant is
   enforced at compute/store but not at export, so any imaging visit that ever
   acquires an `em` blob will print an office code. That is the durable fix.

## Standing check

`./scripts/check-imaging-em-artifacts.sh` — READ-ONLY, added this session and
wired into the close-out checklist in `AGENTS.md`. Exit 0 clean / 1 found / 2
off-host; classifies `emScoredCode` vs `cptCodes.em.override` vs `signedCode`
rather than treating them as one sweep. Verified on all three paths.

Current prod result: **1 of 13** — the doctor-set override above, as expected.
