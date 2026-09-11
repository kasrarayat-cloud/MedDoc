# DECLARATION — BACKFILL `soleParagraphControl` INTO THE RE-ISSUED DRAFT'S IR

**Written and committed BEFORE the act, under ruling #313 (O5: "a ruled,
declared, in-place write to that DRAFT's compiled IR"). A TRACKED, UNMODIFIED
and COMMITTED file whose commit time provably precedes the row it changes.**

## PRECONDITION

**The composed deploy carrying #313 is live and judged.** The act must follow
the deploy. The pre-#313 strict schema rejects the new key, so a backfilled IR
under old code would not parse.

## THE ACT

```
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260911-backfill-sole-paragraph-control.md \
  --in transcribe-md-worker \
  -- npx tsx scripts/backfill-sole-paragraph-control.ts \
       --compiled-version d2120cdd-74ae-43a3-85a3-1f185401e202 \
       --expect-fields 53 --expect-groups 7 --expect-members 24 --commit
```

A DRY RUN (the same invocation without `--commit`) runs first. Its guard table
must be all ✓, and it must print exactly the seven groups below.

## PRE-GUARDS — any failure writes nothing

- The version is not CERTIFIED, has no certification record, and belongs to a
  template whose status is `draft`.
- **No fill manifest** is stored against the version.
- The stored source bytes' sha equals the artifact's sha, **`5367fd07…`**.
- A recompile with the deployed compiler gives the **same** `compilerVersion`,
  `structureSha256` (**`2b7384fa…`**, the stored IR and the column), and
  `staticContentSha256` (**`542a938a…`**). Its fieldIds match, **in order**,
  and the IR is identical to the stored one in every property except the added
  key.
- The field counts are **53** in the stored IR and **53** persisted rows.
- `bulletGroups` over the new IR and the current mappings gives **7 groups /
  24 members**.

## DECLARED DELTA

**MUST change, on `d2120cdd` only:**

| row | before | after |
|---|---|---|
| `compiledDocumentIr` | no `soleParagraphControl` anywhere | **`soleParagraphControl: true` on exactly 27 fields**: the 26 bullet controls (HPI ×4, PMH ×3, PSH ×3, Allergies ×2, Medications ×2, Family History ×3, Impression ×4, Plan ×5) plus the lone Telehealth-consent control |
| bullet groups under the current mappings | 0 | **7 / 24**: HPI ×4, PMH ×3, PSH ×3, Medications ×2, Family History ×3, Impression ×4, Plan ×5. **Allergies ×2 is refused**, because its two mappings differ (G7), and it is filed |
| `audit_logs` | N | **+1** `TEMPLATE_TWIN_COMPILED`, naming ruling #313 and this declaration |

**MUST NOT change:**

- the version's `structureSha256`, `staticContentSha256`, `compilerVersion`
  and every other IR property; every fieldId, and its order;
- every mapping on `d2120cdd` (the set sha is unchanged); every field-definition row;
- the certified, ACTIVE `18a7ae19`: **not one byte**. The five other compiled
  versions keep an IR with no such property;
- `template_twin_fill_manifests` 5 · certifications 4 · note templates 17 ·
  active template `939aa9ea`;
- ⚠️ **the clinical counts: visits 58 · patients 46 · signatures 40.**

## ⚠️ THE ROLLBACK FLOOR — THIS ACT CROSSES IT FOR THE OWNER'S PRACTICE

Per #313's round-one amendment, the floor arms **at deploy**: the first compile
of ANY form with a control alone in its paragraph (any practice's upload)
already writes the property. So the floor may be crossed before this act. The
judgement records the read-only count before and after:

    SELECT count(*) FROM template_twin_compiled_versions
     WHERE "compiledDocumentIr"::text LIKE '%soleParagraphControl%';

It must rise by **exactly 1** here (`d2120cdd`), from whatever the pre-act read
shows. Once this row is written, **code below #313 cannot parse `d2120cdd`'s
IR**. While the template is a draft, a rollback costs only the draft. After
activation, it would break the owner's active form. From this act onward,
**#313's deploy is the rollback floor for the owner's practice**, and a rollback
below it first needs a declared mutation stripping the key.

## WHY THE ANSWER CANNOT BE TUNED AFTERWARDS

Every quantity above is fixed in a committed file before the act. **A
difference this declaration does not name is THE FINDING.**
