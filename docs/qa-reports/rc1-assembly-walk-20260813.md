# RC-1 — the assembled note, walked on the live QA stack

**2026-08-13/14 · ruling #106(a)/(f)/(g) · SPEC §4.3a · branch `feat/rc1-template-fidelity`**

**Verdict: 🟢 16 of 16**, in the universe production actually uses.
Script: `scripts/qa/rc1-assembly-on-qa.ts`. Database `meddoc_qa_test` on the
`meddoc-qa` stack, `MOCK_AI_CALLS=true` with dummy vendor credentials — both
conditions, read from the live QA container rather than from a literal.

    stored template → MIGRATION → slot values → assembly → document → past the polisher

## ⚠️ THE FIRST VERSION OF THIS WALK WAS 15 OF 15 AND PROVED ALMOST NOTHING

It is recorded here rather than quietly replaced, because the way it was wrong
is the most useful thing in this document.

| it did | it should have |
|---|---|
| drove `specialty='primary-care'` | **`ultrasound`** — every production visit bound to a reclassified template is an imaging visit, and imaging goes through a DIFFERENT prompt builder that had not learned the contract |
| ran with `TRANSCRIBE_MD_EVIDENCE_ANCHORS` unset | **`true`** — the production value; on that path the stripped protocol block was put back into the note |
| read modes already in the database and called it "the migration moved them" | **seed pre-migration, apply the real migration file, measure the move** |

⚠️ **And its fixture was imaging-shaped** — `## EXAM`, `SIDE OF EXAM: —`, the
`500 milliseconds` tripwire — which is what made fifteen green arms *read* as an
imaging proof. A gate can be flawless over a universe that contains none of the
rows it was written for, and a well-chosen fixture will disguise that.

⚠️ **The report also claimed the script "re-created those rows on each run".**
It contained no write of any kind. That sentence was false when written.

## The arms

| arm | claim | result |
|---|---|---|
| 0a | PRE-CONDITION — the fixture starts where a real upload leaves it | all three `scaffold_confirm` |
| 0b | the **MIGRATION** moves the fixed blocks and leaves the scaffold alone | `technique` + `exam_metadata` → `always_include`; `findings` unchanged |
| 1 | the tripwire is in `soapDraft`, VERBATIM | `500 milliseconds` |
| 1 | the transcript-supported option was filled | `condition of the superficial venous systems` |
| 1 | the paraphrase is nowhere in the note | no `0.5 seconds` |
| 1 | the protocol block never reaches the note | no sentinel, no `"s0"` |
| 1 | an unsupported slot in an ASSEMBLED section fails closed, visibly | `SIDE OF EXAM: —` |
| 2 | polish RAN and was accepted | `polishRejected=false` |
| 2 | **the tripwire is in `soapFinal` — past the polisher** | `500 milliseconds` |
| 3 | the polish is REJECTED when it normalises the doctor's prose | `polishRejected=true` |
| 3 | `soapFinal` fell back to the draft and still carries the tripwire | draft served |
| 3 | the banner NAMES the section | `TECHNIQUE` · "your own form" |
| 3 | the per-template counter moved | 0 → 1 |
| 3 | the audit ROW exists, read back | `divergedSections=["technique"]` |
| 4 | an out-of-menu value never reaches the note | refused structurally |
| 4 | the refused slot renders the marker, prose intact | `condition of the — venous systems` |

Layer telemetry from the run:

    ARM 1  staticSections=2 replaced=0 inserted=2 unfilled=1 rejected=0 slotBlock=ok
    ARM 4  staticSections=2 replaced=0 inserted=2 unfilled=2 rejected=2 slotBlock=ok

`rejected` moving 0 → 2 is the discriminating number: a slot the transcript did
not support and a slot the model answered illegally both render `—`, and only
that counter tells them apart.

## The composed note (SANITIZED FIXTURE — no real clinic, physician or technologist)

```
## EXAM
SIDE OF EXAM: —
MACHINE: [not documented]
## TECHNIQUE
A duplex Doppler color flow ultrasound study was performed in the upright
position, documenting the condition of the superficial venous systems of the
extremity. This study documents reflux as lasting more than 500 milliseconds in
either the saphenous veins or the perforator veins.
## FINDINGS
[MOCK] FINDINGS recorded for this encounter.

## IMPRESSION
[MOCK] IMPRESSION recorded for this encounter.
```

## What this walk does NOT prove, stated rather than implied

- **It runs the WORKING TREE, not the QA image** — deliberately, to sidestep the
  stale-image class AGENTS.md records. It therefore does not establish that a
  built image carries this code; that is the deploy's own structural check.
- **The `worker.ts` wiring of RC-3 is not exercised.** No test imports
  `worker.ts` and this walk calls the layers directly. RC-3's decision function
  is unit-proven in both directions; its wiring is an attempt-proof still owed.
- **The full audio path, the export and the twin are untouched.** This is L4 and
  L6, which is where the defect lived.

## QA state left behind

`note_templates.qa_rc1_tpl` and `transcribe_visits.qa_rc1_visit` — synthetic,
re-created by the script on every run (verified: `seedPreMigration` deletes and
re-inserts both). The migration is applied by the script from the file; a later
`prisma migrate deploy` will apply it again by name and it is idempotent.
