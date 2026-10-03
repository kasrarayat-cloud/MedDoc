# Transcript custody and integration verification — 2026-10-02

Writer: `fix/v1-sol-security-20261002`; isolated `/opt/meddoc-pro/.worktrees/v1-sol-security`.
Dependencies copied for isolated testing: Word81297/6e165/355 and notes172a5a52. The latter remains explicitly
**unqualified for clinical context** after independent counterexamples below. This privacy work does not qualify
that clinical behavior, authorize a demonstration, infer a retention schedule or claim provider-billed reconciliation.

## Custody behavior

TranscriptReview contains independent immutable reviewed clinical text. The explicit disposition edge/column catalog
now covers every field and relationship; review plans retain row identities/digests only and identify the immutable
content blocker. Retention readiness includes protected `reviewed_transcripts` counts, permits no aging/deletion
window, and leaves the unresolved schedule/external-copy gates intact.

Redaction returns the precise `transcript_review_content` refusal. Additive0037 independently refuses a tombstone while
any immutable review exists, acquiring the encounter before the preservation lock. Deleting ordinary notes/provider
files while leaving that review would falsely claim redaction, so this change preserves the review and refuses the
operation. Unreviewed documents retain the existing explicit two-custodian route. No financial rows are deleted.

The leaf reversal refuses transcript evidence, retained import manifests and the prior mapping preservation gates
before removing new guards. Code rollback is the safe route while evidence exists. The fresh-database integrity
contract includes all Word0035, transcript0036 and privacy0037 definitions:111guards/28functions. Expected PostgreSQL
function bodies derive from reviewed migration SQL, not the inspected database.0036 file SHA is
`ea0a01cb6bc512759d3961638a5a6a1348d7c15d456d49a85ba7ebaddafbce97`; its function-body SHA is
`4e0d9b0e69eb9f678f0d5c95bd086cd4236442a3f1da8a4edf7e531f05f6dfcd`.0037 body SHA is
`f27d1b0038852f1f8e3cb207151455eeb780f0a4fc08ccb82cc91d13f75bef81`.

## Preserved affected verification

- Full recording/retention/redaction rerun on Word-integratedbf6c7dd8:189tests/84.829s,186pass/3fixture setup errors.
  The shared BatchFixture copied a real imported mapping into version2 while omitting its new immutable import
  manifest/backend. The SQL guard correctly refused. Original output retained.
- Fixture-only909fc9bd copies both original metadata values; the guard stays intact. All3 affected BatchStop
  cancellation/closeout/voice lock tests pass in the subsequent15-check slice.
- Privacy/integrity/BatchStop slice:15tests/27.737s,14pass/1new DDL-control harness error. A TestCase inserted a review
  with deferred FK events, so deliberate `ALTER TABLE ... DISABLE TRIGGER` refused before its intended assertion.
  The exact original error remains retained.
- The harness validates its deferred FKs before deliberate DDL. That one affected test passes0.159s; it proves disabled
  review enforcement or a same-name redaction-function replacement fails the release contract, then restores the
  exact contract by transaction rollback. The other14 source checks are unchanged.

The seven custody checks cover actual application refusal, a structurally valid direct SQL tombstone refusal, the
unreviewed positive, hash-only graph/protected counts, all five hold scopes preserving exact review rows, schema
reversal refusals, real PostgreSQL hold-versus-direct-review insertion without deadlock, and guard tampering. Source
was frozen during each measured run. No provider/database credentials were printed; no paid calls were made.

Evidence files/hashes: `security-transcript-privacy-20261002/`. Required final candidate CI, independent finished-diff
refutation and served demonstration remain lead-owned gates. Split runs above must not be described as a single
green189-test execution.

## Independent clinical refutation, retained as failures

Read-only probes against frozen notes172 preparation used the real v4 parser, signed field records and current
governance, with simulated worst-case model relations. Socket connections were forbidden and no DB/provider request
was made. Positive controls confirmed that the intended subjectless and positional-change routes really executed.

Two concrete paired controls fail in the unqualified patient-context configuration:

1. `Takes warfarin 5 mg daily. Only her father does.` into Medications, selecting the first sentence and marking the
   second independent, becomes `supported` patient medication text. Explicit family attribution must prevent that
   inferred patient claim.
2. `Takes warfarin 5 mg daily. Not today.` into Medications taken today, with the same adversarial relations, becomes
   `supported` despite the temporal denial.

Both remain supported through `as_currently_governed`, with no additional governance review requirement. Without
patient-context confirmation the same first selections remain conflict/empty. Notes accepted these findings,
withdrew qualification, preserved172a5a52 and is repairing the actual elliptical dependencies. These are simulated
adversarial failures; they neither alter the historical35-field live denominator nor erase its retained outcomes.

Exact probe and frozen source copies/hashes remain protected in
`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security/notes-refutation-source.json`,
`notes-refutation-source/`, `refute_notes_governance.py` and `refute-notes-governance.json`. The first standalone
probe's missing mandatory synthetic DB setting is retained separately; a new instrument used an unusable dummy
configuration and denied all connections. No real credential was acquired for these probes.
### Later refutation, rollback repair and CI fixture recovery

A read-only pass found a further leaf rollback omission: with no transcript reviews, import manifests or v3 mapping
evidence, 0037 permitted reversal even when a CodeSuggestion retained a release identity or re-review mark.0034's own
SQL would refuse later, after the executor had committed reversal of 0037/0036/0035. The leaf now checks those exact
protected coding columns before removing any newer guard. Neither the SQL bodies nor the 111-guard/28-function
release contract changed.

Three real multi-migration controls exercise a target of core 0033: release identity and a review mark alone each
refuse with the complete migration set, guard contract and coding rows unchanged; an unprotected legacy suggestion
allows reversal and forward migration while retaining its source and restoring the complete guard contract.

The initial core2 CI result on `313c2016` retains 48 fixture errors and two separate application failures. 31 fixture
errors share the BatchFixture repair in `909fc9bd`. The other 17 selected errors came from derived mapping fixtures that
omitted their uploaded import provenance or tests writing current ORM columns after deliberately reversing to0030.
Derived fixtures now carry the original engine and source evidence and rebind only their exact mapping hash. Wrong
signing labels, box destinations, overlap and stale fingerprints remain wrong and their original negative assertions
remain. Historical0030 writes now use that schema's actual historical model and foreign-key identities. No application
guard is relaxed. The two Word application failures remain the Word worker's separate responsibility.

One frozen, single-process suite passed28 checks in 183.403 seconds, exit 0, including the three new migration controls,
five historical rollback controls, signing and overlap regressions, four layout batch controls, three ordinary batch
workflows and four stale Word destination controls. It destroyed its synthetic test database. This is component
evidence; integration CI must still cite the final coordinated commit.

The clinical worker's intermediate `1144e47cf806f85eb698335e27fd1c7c5898c808` remains unqualified. A fresh read-only
whole-governance refutation verified the prior two failures were held, but retained two further unsafe supported
answers: `Takes warfarin 5 mg daily. Not since Monday.` for Current medications, and `Takes warfarin 5 mg daily. Only
her father takes warfarin.` for Medications. The adversarial model declared the later statement independent; both
validation and current stored-answer governance still released the first statement with no review decision. Complete
nonexclusive family clauses and the local cough dependency supplied positive controls. Source hashes were checked
before the probes and the exact committed failed source was copied and hash-verified afterwards. Original failed
outputs are retained; a later repair cannot turn them into first-pass successes.

The durable follow-up evidence directory contains the actual 28-check log, the 17 selected CI error frames, the leaf
counterexample, the 18-case clinical governance record, parser evidence and committed-source witness manifest.
`followup-evidence.json` binds each copied file to its protected raw source and SHA256. No paid request, installed
credential, financial ledger, public service or production database was touched by this follow-up.
### Core1 controls and further clinical refutation

The initial core1 CI result on `313c2016` remains failed: 1,644 checks in 1,352.213 seconds, seven failures and 34 errors. Its
exact protected raw log and the selected error/assertion frames are retained. The remaining historical 0030 writer in
`ARefusedRollbackKeepsTheConfirmationGate` now uses the actual historical model and foreign-key identities. Its
unchanged complete-applied-schema assertions were valid: original failures showed 0035 had been reversed before an
older refusal. The new 0037 leaf check closes that real partial-reversal defect; the tests were not changed to accept
it. The original unconfirmed finalization negative and confirmed positive remain intact.

F05's forged stored contract/backend now uses a distinct explicitly historical unbound template. It still uses the
same synthetic blank source and the same bad stored suggestion. This does not change the import engine of the real
uploaded template to create a negative test case. The original rejected-act assertions and legitimate legacy
acceptance positive remain. The other derived signing/overlap/box fixtures were already repaired in `6ee290af`.

A single frozen focused suite passed nine checks in 36.769 seconds, exit 0, including all six refusal/finalization
controls, F05 and two previously unmeasured signing/permutation controls. The synthetic database was destroyed.
`core1-followup-evidence.json` binds the actual log and the failed initial CI frames to their protected raw sources.

Further finished clinical diffs were measured only with simulated provider responses and blocked network connections,
using hashes verified and exact source copies retained before each run.31 whole-governance checks showed the earlier
exclusive family and dated-fragment defects were held, alongside wrong-subject, stopped, withheld and replaced
medication controls and both exact original voice controls with and without patient confirmation. Independent drug,
condition, side and nonexclusive family statements remained positive controls. Eight narrow frequency variants
isolated an ambiguous `No longer routine` residual; seven explicit frequency restrictions were held.

A third finished source repaired that residual but failed three fresh cases in a 10-case counterexample set: the full
daily claim survived `No longer a daily medication`, `Her father is the sole warfarin user`, and `Her father is the
only patient on warfarin`. Validation and current stored-answer governance both released the patient-default first
sentence with no review decision. Different-drug exclusive statements remained positive controls. This third source
is unqualified; the lead and clinical writer received the exact findings and withdrew readiness. These are retained
failed outcomes, not measured live accuracy or a replacement denominator. The governance JSON, parser witness and
source manifests are copied alongside the nine-check fixture log. There were zero provider or production calls.

### Fourth frozen clinical refutation

The fourth source (`source_scope.py` SHA256 `8b83a04c7e57778ca5896c51827fd4c2f5c304b6b60a39080a6dfc529878e3a8`,
`generation.py` SHA256 `77e123ba8407cb82a660c5769b483b55673f3ac16b650b7eb692ce7ea53bd1c1`) was hash-verified
and copied before read-only testing. Two bounded probe runs exited 0 with 16 fresh cases and five narrow controls;
a separate parser witness exited 0. The exact three previous failures are now conflict/empty. Different-drug nominal
roles and an independent family cough statement retain the selected patient medication positive. A locality control
with warfarin followed by metformin and a negated daily-medication fragment preserves warfarin.

One definite new unsafe release remains: `Takes warfarin 5 mg daily. No longer the daily medication.` for Current
medications releases the full daily patient-default claim through both validation and current stored-answer
governance, with no additional review decision. The omitted nominal clause has root `medication`, negative `No`,
and definite article `the`; the source-scope nominal predicate arm at lines111–113 accepts only `a`/`an`, and its
dependency graph is empty. This is the definite-article counterpart of the preceding repaired failure.

Three concrete unnecessary holds are also retained. After the same patient-default warfarin sentence, `Her father is
not the only warfarin user`, `Her father is the only person not taking warfarin`, and `Only her father is not taking
warfarin` each conflict/empty the selected patient claim. Those negative other-actor exclusives do not contradict
that patient claim. `exclusive_reattributions` at lines161–200 attaches each unit2 to unit1 without testing the
exclusive or nominal/action predicate's polarity. This witness establishes the actual validation result, not merely
a hypothetical parser edge.

The left-knee variant was already held without its family statement, so no new laterality defect is asserted. The
apixaban locality variant is held because the existing parser marks that preceding sentence dependent; it is not
asserted to be a new locality regression. These controls prevent attributing an existing conservative result to the
new repair. The 21 probes are a counterexample set, not an accuracy denominator. Failed original results remain
unchanged, and zero provider requests or database connections occurred. `fourth-refutation-evidence.json` binds
the raw outputs, probe source and pre-run source witness. Lead and clinical writer received the new findings before
any live qualification; actual served authorization/host verification awaits the final qualified demonstration.
