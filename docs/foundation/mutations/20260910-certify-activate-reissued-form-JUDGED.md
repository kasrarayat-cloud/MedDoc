# RULED-ACT JUDGEMENT — certify + activate the re-issued 53-control form (`d2120cdd`): 🟢

**Judged against `docs/foundation/mutations/20260910-certify-activate-reissued-form.md`,
committed `a36d7c10` at 2026-09-11T02:25:18Z — every row.** The commit run
started 14:56:48Z; the certification landed at **14:58:18Z**, provably after the
declaration's commit. This is the re-run after the 04:44Z refusal, once the
generator fix (`1bc62c08`) was deployed.

## VERDICT — 🟢 the form is CERTIFIED and ACTIVE. The referrer fills with a ROLE, and the privacy gate passed.

The first attempt (`…-REFUSED-20260911.md`) was rejected because the generator
dictated a physician's NAME. The deployed fix dictates "their primary care
physician". The synthetic gate passed, and the Referring MD control filled.

### ⚠️ THE ACT COMPLETED, THOUGH THE WRAPPER WAS KILLED — board #13

`certify-active.ts` finished the DB work at 14:58:18Z and then hung on an open
handle (board filing #13, RULED-ACT-SCRIPTS-DO-NOT-EXIT). My 15-minute `timeout`
killed the host wrapper at ~15:12Z (exit 124), but the in-container node
survived because `docker exec`'s signal did not propagate. **The completion was
confirmed from the DB, not from the exit code**, and the idle in-container pid
was then SIGTERMed by name (cmdline verified to name this script). The kill was
~15 minutes after the work landed, so it removed only an idle process; the
post-kill snapshot is identical to the pre-kill one.

### MUST CHANGE — declared, observed

| row | declared | observed | |
|---|---|---|---|
| `d2120cdd.certificationStatus` | NEEDS_CONFIRMATION → **CERTIFIED** | CERTIFIED | 🟢 |
| its 53 field definitions' `detectionStatus` | → CERTIFIED ×53 | CERTIFIED ×53 | 🟢 |
| `template_twin_certifications` | 4 → **5**, the new row for `d2120cdd` with `approvedMappingsSha256` = the confirm's set | 5; new row `d2120cdd`, `approvedMappingsSha256 = 33ffb02b0206…` | 🟢 |
| `note_templates.status` | `3877d5cf` draft·`939aa9ea` active → **`3877d5cf` active·`939aa9ea` inactive**, count still 17 | `3877d5cf` active · `939aa9ea` inactive; count 17 | 🟢 |
| `d2120cdd` pinned-note + latest-test | NULL → **set**, round trip verified | pinned + proof set; `roundTripVerified = true`; `latestTestVerifiedAt 14:58:18` | 🟢 |
| `audit_logs` | +3 named (SYNTHETIC_TESTED, CERTIFIED, ACTIVATED), plus fixture rows recorded | 12531 → 12536 (+5); tested 9→10, certified 5→6, activated 5→6 (+1 each), +2 fixture-visit rows | 🟢 |
| `ai_calls` / `api_usage_events` | +k / +j ≥ 1 | 1699 → 1705 (+6) / 1880 → 1886 (+6) | 🟢 |
| MinIO output object | one new object, sha = `latestTestOutputSha256` | key `…/830b577a729f….docx`; `testOutputSha256 830b577a729f…`; fetched read-only and sha-verified equal | 🟢 |

⚠️ **The `ai_calls`/`api_usage_events` baseline moved from the declaration's
1686/1867 to 1699/1880 before the act.** That is my own L3 referrer rehearsal
(13 + 12 rows), recorded in the generator-fix account, not an unexplained
movement. The declaration bounds the act's OWN delta at "≥ 1", and the act added
6 / 6 on top of the re-read baseline.

### MUST NOT CHANGE — re-read after the act

| row | declared | observed | |
|---|---|---|---|
| clinical: visits · patients · signatures | 58 · 46 · 40 | 58 · 46 · 40 | 🟢 |
| the certified `18a7ae19` | not one row | mappings md5 `94bc1c1a…` and cert-row md5 `cb17dc67…`, both **unchanged** | 🟢 |
| fill manifests · source artifacts · compiled versions | 5 · 8 · 6 | 5 · 8 · 6 | 🟢 |
| `d2120cdd` mappings | 53 CERTIFIED, set sha unchanged | md5 `cd6ac2bd…`, 53 CERTIFIED, unchanged | 🟢 |

⚠️ **The synthetic certification writes NO `template_twin_fill_manifests` row**
(those are for real signed visits). Its manifest lives in
`latestSyntheticTestManifest` on the compiled version. So the "manifests = 5"
row held, correctly.

### TRANSIENT — net zero

The declaration says one `transcribe_md_patients` and one `transcribe_visits`
row are created and deleted inside the call, and a straggler of either is a
finding. **`recent_created_6h = 0 / 0`**: no straggler. The clinical counts are
unchanged, which is the same fact from the other side.

## THE FILL MAP — PREDICTED, THEN MEASURED

The synthetic manifest's counts equal the declaration's prediction **exactly**:

```
declared:  FILLED 26 · SLOTS UNUSED 11 · BLANK 16
manifest:  filled 26 · slotsUnused 11 · notMentioned 16 (13 fact_not_mentioned + 3 manual_source_not_filled)
           conflicts 0 · needsReview 0 · criticalUnresolved 0 · validation.valid = true, 0 issues
```

The Referring MD field resolved `supported`, value **"Primary care physician
(name not stated)"**, reason `direct_evidence_supported` — the predicted "filled:
the dictated referrer", now a role.

## THE ELEVEN-ROW ACCEPTANCE ON THE ROUND-TRIP EXPORT

The export was fetched read-only via the artifact store, which verified its sha,
and re-verified locally (`830b577a729f…` = `latestTestOutputSha256`). It carries
53 content controls; rendered filled/blank is 26 / 27, matching the manifest.
Bodies were counted, never printed (PHI-class posture, though synthetic).

| row | criterion | verdict |
|---|---|---|
| 1 | one per bullet; no repeated-concept control repeats another's item | 🟢 no duplicate filled item in any of the 8 repeated-tag groups |
| 2 | PSH carries procedures, PMH carries conditions, neither the other's | 🟢 PMH ×3 conditions / no procedures; PSH ×3 procedures / no conditions |
| 4 | ROS: each contradicted clause carries evidence | 🟢 6 / 6 ROS controls filled |
| 5 | exam: each system carries evidence | 🟢 10 / 10 exam controls filled |
| 6 | telehealth omitted when unsupported | 🟢 the consent control is blank |
| 9 | "married" on the marital control, not on occupation | 🟢 |
| 10 | family history all blank | 🟢 3 / 3 blank |
| 11 | recreational drugs blank | 🟢 |
| 7 (referrer half) | the referrer is filled | 🟢 "Primary care physician (name not stated)", no person-name pattern |
| 3, 7 (Patient/Age), 8 | placeholders / record-derived / manual total time | ⚠️ NOT checkable on a synthetic round trip — declared so; go to WHAT REMAINS |

**Every ✅ row holds → the lane's 🟢 for this act is reached.**

## WHAT REMAINS (unchanged from the declaration; #311 does not waive it)

- The **owner's own fresh visit** — the acceptance no gate substitutes for.
- Row 3's `{patient}`/`{age}` placeholder half (filed ROW3-PLACEHOLDERS).
- Row 7's Patient / Age (record-derived; only a real visit has a record).
- Row 8's total-minutes (manual under #312 amendment 3; a sentence rule cannot
  establish this visit's total, across three refutation rounds).

## WHY THE ANSWER COULD NOT BE TUNED

Every quantity was fixed in a committed file at 02:25:18Z, and the runner
printed that commit time and the 14:56:48Z start. The manifest counts, the set
sha, and the eleven rows all matched what was written before the evidence
existed.
