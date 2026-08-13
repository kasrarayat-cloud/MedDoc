# RC-1 — the assembled note, walked on the live QA stack

**2026-08-13 · ruling #106(a)/(f)/(g) · SPEC §4.3a · branch `feat/rc1-template-fidelity`**

**Verdict: 🟢 15 of 15.** Script: `scripts/qa/rc1-assembly-on-qa.ts`.
Database: `meddoc_qa_test` on the `meddoc-qa` stack, `MOCK_AI_CALLS=true`,
dummy vendor credentials — both conditions, read from the live QA container
rather than from a literal.

## What was proved, end to end

    stored template → migration → slot values → assembly → document → past the polisher

| arm | claim | result |
|---|---|---|
| 0 | the migration moves the fixed blocks and leaves the scaffold alone | `technique` + `exam_metadata` → `always_include`; `findings` stays `scaffold_confirm` |
| 1 | the tripwire is in `soapDraft`, VERBATIM | `500 milliseconds` |
| 1 | the transcript-supported option was filled | `condition of the superficial venous systems` |
| 1 | the paraphrase is nowhere in the note | no `0.5 seconds` |
| 1 | the protocol block never reaches the note | no sentinel, no `"s0"` in clinical text |
| 1 | an unsupported slot in an ASSEMBLED section fails closed, visibly | `SIDE OF EXAM: —` |
| 2 | polish RAN and was accepted | `polishRejected=false` |
| 2 | **the tripwire is in `soapFinal` — past the polisher** | `500 milliseconds` |
| 3 | the polish is REJECTED when it normalises the doctor's prose | `polishRejected=true` |
| 3 | `soapFinal` fell back to the draft and still carries the tripwire | draft served |
| 3 | the banner NAMES the section | `TECHNIQUE` · "your own form" |
| 3 | the per-template counter moved | 0 → 1 |
| 3 | the audit ROW exists, read back | `divergedSections=["technique"]`, `noteTemplateId=qa_rc1_tpl` |
| 4 | an out-of-menu value never reaches the note | refused structurally |
| 4 | the refused slot renders the visible marker, prose intact | `condition of the — venous systems` + tripwire |

Layer telemetry, from the run itself:

    ARM 1  staticSections=2 replaced=0 inserted=2 unfilled=1 rejected=0 slotBlock=ok
    ARM 4  staticSections=2 replaced=0 inserted=2 unfilled=2 rejected=2 slotBlock=ok

`rejected` moving 0 → 2 between arms is the discriminating number: a slot the
transcript did not support and a slot the model answered illegally both render
`—`, and only that counter tells them apart.

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

## ⚠️ THE WALK FOUND A REAL DEFECT THE PRODUCTION DRY-RUN COULD NOT

The migration's guards were behind `CREATE TEMP TABLE … ON COMMIT DROP`. psql
commits each statement on its own, so the snapshot was destroyed the instant it
was created and the guard block failed with
`relation "_rc1_before" does not exist` — **after the UPDATE had already
committed.** A migration that half-ran and reported nothing.

**The prod dry-run was structurally incapable of catching it**, because that run
was wrapped in `BEGIN … ROLLBACK` specifically so it could never commit — which
is the one condition under which the old form works. *A rehearsal that supplies
what the real run does not is not a rehearsal of the real run.*

`prisma migrate deploy` wraps each migration in a transaction, so this would
have shipped working and stayed latent until someone applied the file by hand.
Fixed to `DROP TABLE IF EXISTS` + a plain temp table, and re-applied to QA with
**no** enclosing transaction: guards ran, second pass reported `0 flipped`
(idempotent), and the prod dry-run re-measured unchanged at **7 sections across
4 templates**.

## ⚠️ AND ONE OF THE WALK'S OWN CHECKS WAS MEASURING NOTHING

The first version asserted "an unsupported slot fails closed to a visible
marker" while the transcript named a side — so every assembled slot filled,
`unfilled` was 0, and the assertion was pointed at `FINDINGS`, which is
`scaffold_confirm` and therefore **not assembled at all**. It went red,
correctly. The fix was the transcript, not the assertion: it now names no side,
so one assembled section fills and another fails closed in the same run.

## What this walk does NOT prove, stated rather than implied

- **It runs the WORKING TREE, not the QA image.** That is deliberate — it
  sidesteps the stale-image class AGENTS.md records (a QA worker built before
  the code it was meant to exercise). What it therefore does not establish is
  that a built image carries this code; that is the deploy's own structural
  check, on a build from the same commit.
- **The `worker.ts` wiring of RC-3 is not exercised here.** No test imports
  `worker.ts` and this walk calls the layers directly. RC-3's decision function
  is unit-proven in both directions; its wiring is an attempt-proof still owed.
- **The full audio path, the export, and the twin are untouched.** This is L4
  and L6, which is where the defect lived.

## QA state left behind

`note_templates.qa_rc1_tpl` and `transcribe_visits.qa_rc1_visit` — synthetic,
named here so they are recognisable, and re-created by the script on each run.
The migration was applied to QA by hand; `prisma migrate deploy` will apply it
again by name and the file is idempotent.
