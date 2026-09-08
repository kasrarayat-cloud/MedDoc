# DECLARATION — THE RE-ISSUE OF THE 53-CONTROL CONSULT FORM

**Written and committed BEFORE the act, under ruling #263 and the standing rule
that `run-ruled-mutation.sh` is the only door to an irreversible production act.
The declaration must be TRACKED, UNMODIFIED and COMMITTED, so its commit
timestamp provably precedes the rows it describes.**

## THE ACT

Re-ingest the owner's pinned 53-control consult form from its **stored
artifact**, carry the 43 certified dispositions across, re-propose the ten, and
leave a **draft** for the owner to confirm.

Run through the in-container door:

```
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260908-re-issue-53-control-form.md \
  --in transcribe-md-worker \
  -- <the ingest entry point>
```

⚠️ **The worker, not the app.** The app container's `node_modules/.bin` is empty
and cannot run a `.ts` file; the worker can. That was measured, not assumed.

## PRE-GUARDS — checked BEFORE any row is written

The compile is pure (`compiler.ts` holds no `prisma` and no `await`), which is
what makes all of these precede the write. It matters because the artifact store
is **put-once and deletion is intentionally unavailable**, so a post-write guard
leaves an orphan nothing can remove.

| # | guard | expected |
|---|---|---|
| 1 | artifact bytes sha256 | `5367fd075472cc2c6a1de768c5224e7522691ccad3d2c7aafc47071752920642` |
| 2 | compiled `fieldId`s **set-equal** to the certified version's | **53**, exactly, no missing and no unexpected |
| 3 | transfer count | **43** |

Any mismatch **aborts and writes nothing.**

## DECLARED DELTA — what MUST change, and what must NOT

**MUST change:**

| row | before | after |
|---|---|---|
| note templates for this practice | N | **N + 1** (one new DRAFT) |
| compiled versions | M | **M + 1** |
| the new version's field definitions | — | **53** |
| its mappings with `mappingStatus = CERTIFIED` | — | **43** |
| its mappings NOT certified (the re-proposed) | — | **10** |
| the new template's `status` | — | **`draft`** |

**MUST NOT change:**

- the existing certified version's rows — **not one**. The transfer READS it.
- `template_twin_fill_manifests` — **0 rows touched**. Frozen per-visit manifests
  keep pointing at whatever they were filled against; that is why the old
  template is demoted later and never deleted.
- ⚠️ **the clinical counts: visits, patients, signatures — ALL UNCHANGED.** A
  deploy or mutation that moves one of these has done something nobody asked
  for, and the only way to know is to have written the numbers down while they
  were still true.
- nothing is **activated** and nothing is **certified** by this act. The owner
  confirms first; activation is a separate atomic swap.

## ⚠️ A RECORDED MEASUREMENT, NOT A GATE

Owner-ruled: in the same act, **count the `w:tag` attributes on the pinned
artifact.**

This does not gate anything and must not abort the act. It settles a premise
that is currently **unverified and load-bearing for TAG-ON-INGEST**: the ruling
states the form is 53/53 tagged; what is verifiable from the repository is
**18 of 53** — the controls `regenerate-consult-form.ts` adds. The other 35 come
from the owner's blank source, whose bytes are not in the repository.

⚠️ The provenance record's P3 proof says *"`w:sdt` tags balanced"*, which is
**XML nesting, not `w:tag` attributes** — a near-homograph that reads like
confirmation and is not.

**Declared expectation, fixed before the evidence exists:** `tagged >= 18`. Any
value is recorded as the finding; **53 makes TAG-ON-INGEST narrower, 18 makes it
wider**, and either way the number becomes a fact rather than a claim.

## WHY THE ANSWER CANNOT BE TUNED AFTERWARDS

Every quantity above is fixed here, in a committed file, before the act runs.
The runner prints the declaration's commit time and the act's start time into
the transcript, so the two bracket the rows in the units the rows carry.

**A difference that is not in this declaration is THE FINDING**, whatever its
explanation sounds like afterwards.
