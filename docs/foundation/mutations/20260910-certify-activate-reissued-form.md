# DECLARATION — CERTIFY AND ACTIVATE THE RE-ISSUED 53-CONTROL CONSULT FORM

**Written and committed BEFORE the act, under ruling #311 (clause (d): "certify
and activate follow"). The ruling-order preconditions are #312 (the confirm,
with amendment 3) and #313 (one item per bullet). #314 (total-time grounding)
is **no longer a precondition**: amendment 3 moves both total-time controls to
`manual`, and #314 is deferred. A TRACKED, UNMODIFIED and COMMITTED file whose
commit time provably precedes the rows it describes.**

## PRECONDITIONS — each already JUDGED, or this act does not run

| # | precondition | evidence required |
|---|---|---|
| 1 | the composed deploy carrying #313 (and #1098 with #312 amendment 3) is live | the container revision equals, or is a zero-runtime-drift ancestor of, this tree's HEAD, and its judgement is committed |
| 2 | the IR backfill act (#313 O5) is judged | `d2120cdd`'s stored IR carries `soleParagraphControl`; `bulletGroups` = **7 groups / 24 members** — HPI ×4, PMH ×3, PSH ×3, Medications ×2, Family History ×3, Impression ×4, Plan ×5. **Allergies ×2 is refused** (G7, its two mappings differ) and stays filed. The confirm does not move this: of the ten rows #312 confirms, only the three PSH members (display order 22–24) are group members, and all three are written to the same `sourceType` and concept |
| 3 | the confirm act (#312) is judged | `d2120cdd`: **53 / 53 CERTIFIED**, and the resulting set sha is recorded in the confirm judgement |

## THE ACT

```
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260910-certify-activate-reissued-form.md \
  --in transcribe-md-worker \
  -- npx tsx scripts/certify-active.ts \
       --compiled-version d2120cdd-74ae-43a3-85a3-1f185401e202 --expect-fields 53 --commit
```

A REPORT-ONLY run (no `--commit`) goes first, through the same door. It prints
the derived encounter and writes nothing.

**One model generation** runs, the real chain (L3 extraction and L4 over a
short-lived fixture visit). Then certification runs, then activation.

## DECLARED DELTA

**MUST change:**

| row | before | after |
|---|---|---|
| `d2120cdd.certificationStatus` | `NEEDS_CONFIRMATION` | **`CERTIFIED`** |
| its 53 field definitions' `detectionStatus` | not certified | **`CERTIFIED`** ×53 |
| `template_twin_certifications` | 4 | **5**. The new row is for `d2120cdd`, and its `approvedMappingsSha256` equals the sha the confirm judgement recorded |
| `note_templates.status` | `3877d5cf` draft · `939aa9ea` active | **`3877d5cf` active · `939aa9ea` inactive**. Exactly two changes; the count stays **17** |
| `d2120cdd` pinned-note and latest-test columns | NULL | **set**, and the round trip is verified |
| `audit_logs` | N | **+3 named**: `TEMPLATE_TWIN_SYNTHETIC_TESTED`, `TEMPLATE_TWIN_CERTIFIED`, `TEMPLATE_TWIN_ACTIVATED`. Rows written by L3/L4 against the fixture visit are recorded, not predicted |
| `ai_calls` / `api_usage_events` | 1686 / 1867 at baseline (re-read at declaration) | **+k / +j, both ≥ 1, recorded**. The last certification left 9 `ai_calls` in its window |
| MinIO `transcribe-md-template-artifacts` | — | **one** new output object under the practice's `outputs/synthetic_d2120cdd…` prefix; its sha equals `latestTestOutputSha256` |

**TRANSIENT, and net zero:** one `transcribe_md_patients` row (the fixture
name) and one `transcribe_visits` row are created and deleted inside the call.
**A straggler of either is a finding** and a named clean-up item.

**MUST NOT change:**

- ⚠️ **the clinical counts after the act: visits 58 · patients 46 · signatures 40.**
- the certified version `18a7ae19`: **not one row**. It is immutable, and its
  certification row is untouched. Demoted is not deleted: the five frozen fill
  manifests still point at what they were filled against.
- `template_twin_fill_manifests` **5** · source artifacts **8** · compiled versions **6**.
- `d2120cdd`'s mappings: **53 CERTIFIED, set sha unchanged** from the confirm judgement.

## THE FILL MAP — PREDICTED HERE, BEFORE THE EVIDENCE

Derived from the verification encounter over the confirmed concepts (dictated
sentences for PMH, PSH, marital status, total time and the referrer; none for
patient name or age), with #313 deployed. #314 is deferred, and total time is
`manual` under #312 amendment 3. **Any difference is THE
FINDING**, adjudicated row by row. A different item count K from the model's
extraction is a finding about the extraction, not a failure of the act.

| controls | predicted |
|---|---|
| Referring MD | **filled**: the dictated referrer |
| Patient, Age | **blank**: record-derived, with no record at certification (#247 / #272: named, never withheld) |
| HPI intro ×4 | line 1 = the chief complaint; lines 2–4 **`list_item_slot_unused`** |
| ROS ×6 | **filled** from the contradicting evidence. ⚠️ Rendered as the bare finding (filed: ROS-AFFIRMED-RENDER) |
| PMH ×3 | "Hypertension" · "Type 2 diabetes mellitus" · **slot unused** |
| PSH ×3 | the cholecystectomy · the appendicectomy · **slot unused** |
| Allergies ×2, Medications ×2 | blank (bare family concepts match no fact, as on `18a7ae19`) |
| Tobacco, Alcohol, Recreational drugs, Occupation | blank (not dictated) |
| Marital status | **filled**: married |
| Family History ×3 | blank |
| Exam ×10 | **filled**: unremarkable per system |
| Telehealth consent | blank, cleared (`manual`) |
| Impression ×4 | line 1 = the assessment; lines 2–4 **slot unused** |
| Plan ×5 | the two plan items · 3 **slots unused** |
| Total minutes ×2 | **blank, cleared (`manual`)**. Under **#312 amendment 3** the total is entered by the clinician. The encounter still dictates "A total time of forty five minutes …"; no control maps that fact, so nothing prints |

**Totals: FILLED 26 · SLOTS UNUSED 11 · BLANK 16 = 53.** The floor is 10, so
this is met. Blank proof is at least 1.

## THE ELEVEN-ROW ACCEPTANCE ON THE ROUND-TRIP EXPORT — criteria fixed now

The export is fetched read-only (sha must equal `latestTestOutputSha256`) and
read control by control. **A row that cannot be checked on a synthetic round
trip is declared so HERE, and goes to what remains.**

| row | 🟢 when | checkable here? |
|---|---|---|
| 1 one per bullet | no repeated-concept control repeats another's item; every dictated item appears exactly once | ✅ |
| 2 PSH own concept | PSH controls carry procedures, PMH controls carry conditions, and neither carries the other's | ✅ |
| 3 HPI intro lines + {patient}/{age} | line 1 carries the complaint; lines 2–4 empty | ⚠️ the `{patient}`/`{age}` half is **not built** (filed: ROW3-PLACEHOLDERS), so not checkable |
| 4 ROS per clause | each contradicted clause carries evidence; no "denies X" is printed for a reported X | ✅ (rendering filed) |
| 5 exam | each system carries evidence | ✅ |
| 6 telehealth omitted when unsupported | the consent sentence is absent | ✅ (the *supported* half is filed: TELEHEALTH-CONSENT) |
| 7 Referring MD / Patient / Age | the referrer is filled | ⚠️ Patient/Age need a record, which only a real visit has, so they go to what remains |
| 8 total minutes 45 | both time controls read 45 | ⚠️ **not checkable here: moved to what remains.** Under #312 amendment 3 the two time controls are `manual`. Three refutation rounds showed a sentence rule cannot establish "this visit's total". The owner's ACTIVE form already has them manual, so nothing is lost |
| 9 marital status | "married" on the marital control, and not on occupation | ✅ |
| 10 family history blank | all three blank | ✅ |
| 11 recreational drugs blank | blank | ✅ |

**The lane's 🟢 = every ✅ row holds.** The ⚠️ halves and **the owner's own
fresh visit** are what remains; #311 does not waive the visit.

## WHY THE ANSWER CANNOT BE TUNED AFTERWARDS

Every quantity above is fixed in a committed file before the act. The runner
prints this file's commit time and the act's start time. **A difference this
declaration does not name is THE FINDING.**
