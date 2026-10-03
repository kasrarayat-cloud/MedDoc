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

### Fifth clinical refutation and prepared served authorization

The fifth scope SHA `169f2144383d66a1a8818c731db6b03d8ca837cbb0ac35b9c0c46ea570946f5d` was frozen and copied
before16 bounded whole-validator/current-governance probes, exit0. Generation77e123 and context3b925 were unchanged.
The fourth definite-article failure is held; its three negated-exclusive unnecessary holds now preserve the original
patient claim. Two fresh unnecessary holds remain: after `Takes warfarin 5 mg daily`, `Her father is the only person
without warfarin` and `Only her father used to take warfarin` both conflict the patient's current claim. Explicit
negative possession and explicitly historical other-person use do not contradict it. A `my daily medication`
variant remains supported, but no definite unsafe assertion is made because its explicit speaker may fall outside
the patient-default grant. Exact output and source witness remain failed fifth-source evidence.

The proposed sixth whole-governance probe was refused before copying sources or running cases: scopebb72 and
generation77e123 matched, but the transcript context had changed from declared3b925 todf959 during the nominal repair.
The setup refusal1 and accidental launch of the absent probe2 are retained. Neither is a clinical test result. The
writer acknowledged the mixed-source refusal and will announce the completed full source freeze.

`rebuild/ops/verify_qa_authorization.py` is a prepared bounded actual-served harness. No new demo was executed by this
writer yet. The harness requires lead-confirmed process IDs, exact archive/extracted source, release and synthetic
fixture database on55731; it targets only9160/9161. It seeds separately named synthetic authorization accounts, a payer
and two departments, six held and two simulated settled jobs, and direct synthetic finalized files for real export
authorization positive controls. These direct fixtures do not qualify generation or clinical finalization. Existing
accounts, wallets, grants and services stay untouched; all read-window financial fingerprints must remain equal.
Actual owner/dual-owner/manager scopes, list totals and metadata, detail GET/HEAD/valid-CSRFPOST, API/export, membership
revocation with personal-history preservation, password-only admin refusal, actual MFA, and host/path404 without
redirect are measured. Only these seeded accounts are retired with session-version increments; clinical/financial
fixture evidence is retained. No welcome grant or provider request is performed.

The lead's independent prepared-source pass found a wrong health literal before execution: the harness expected
`synthetic`, while the actual endpoint returns `synthetic-only`. The finding and repaired exact literal are preserved;
syntax, prepare-only and diff checks pass. These checks prove preparation only. Actual served results await the lead's
confirmed idle new-demo window. The harness bounds150HTTP requests/180seconds with6second request deadlines and
3second lock/8second statement limits; source preparation and financial snapshots have their own finite work rather
than being advertised as covered by the HTTP clock. Raw HTTP credentials/tokens remain unrecorded.

### Finished fixture-only refutation

A read-only pass over root `5a06295a6bcfa7aca82f024e761c0a53f2b92ab5` found no demonstrated counterexample in the
fixture-only change's scoped claims. Four source hashes were copied before the probes.13 bounded scenarios used
the actual `g.generate` fixture path, existing validator and current stored-answer governance with database
connections and sockets denied. Exact labelled positive values and exact printed `No` are supported; unlabelled
notes, unknown context/labels, repeated labels, contradictory values, inherited family scope and ambiguous options
remain held/missing. Both a typed signature and a text field whose printed label is a signing area stay empty. The
signature-only catalogue refuses compilation with no eligible asked field; no signing text is adopted. A labelled
medication followed by a labelled stop plan holds that medication and retains the exact plan positive.

Every emitted context partition names all source units once. A deliberately truncated fixture source list is
refused by the real validator. A text-only multipart response keeps the complete source context without introducing
option IDs from another part. Each returned fixture settlement has cost0, empty quantities/rates and request ID,
explicit synthetic provider identity and `simulated=True`. The live `v3_field_relations.generate` AST, after excluding
only the changed nonlive branch, equals the prior888 parent exactly, including request transport and settlement.
The inspected batch diff changes only its fixture-response builder. These controls do not qualify live clinical
accuracy or replace the lead's actual101-field workflow evidence.

The first instrument failed before probing because it imported a transcript module not yet integrated in root. Its
exit1 remains retained. A distinct instrument removed that irrelevant import and completed exit0; no measured tree
was changed. `fixture5a-refutation-evidence.json` binds the exact outcomes, source witness and first failure. The
full clinical context freeze and actual new-demo served authorization execution remain pending lead coordination.

### Actual served authorization: preserved failures and repaired dashboard

On 2026-10-03 the lead authorized the provisional fixture-only demo at exact application commit
`5a06295a6bcfa7aca82f024e761c0a53f2b92ab5`, doctor9160 PID1160039, admin9161 PID1160043 and worker1160044.
Each run independently verified source archive and all629 extracted source files, process ownership/CWD/start
identity, release, fixture mode, protected QA connection and synthetic database `quillmd_qa_int_sol_5a06295a`.
Installed9130/9131 and the previous9140/9141 demo were not mutated. These are authorization fixtures, not clinical
workflow or model qualification. Four terminal runs remain failed; none has been rewritten or reclassified.

| Run | HTTP requests | Actual stopping condition | Fixture retirement / preservation |
| --- | ---: | --- | --- |
| `5a-first-20261003` | 2 | Mapping fixture lacked the existing source/tenant config binding; SQL guard refused it. | Seed transaction rolled back: zero own accounts/jobs; independently verified all nine financial hashes unchanged. |
| `5a-second-20261003` | 10 | Credential-route guard refused inherited own scratch parent mode775. | All six accounts inactive, session version1; all nine financial hashes unchanged from post-fixture baseline. |
| `5a-third-20261003` | 73 | Harness incorrectly expected authenticated404 from a doctor cookie ignored by the admin surface; actual empty302 went to login. | All six accounts inactive, session version1; all nine financial hashes unchanged. |
| `5a-fourth-20261003` | 89 | Actual MFA login succeeded, then the real admin dashboard returned500 for a legitimate held mapping job. | All six accounts inactive, session version1; all nine financial hashes unchanged. |

Across these174 actual HTTP requests there were zero provider requests. The first mapping refusal remains raw
evidence; a distinct fixture repair supplied the exact template hash, department and mapping-version identity.
The owned scratch directory was metadata-verified and protected700; the harness now checks both private parents
before any fixture account or money row. The cookie correction preserves the third failure and strengthens the
control: normal doctor cookies produce an exact empty login redirect, while the same real nonstaff session under
the destination cookie name must receive404. No product permission/host/financial guard changed for these repairs.

The fourth run measured four owner list/search/pagination requests with three scoped held requests and configured
cost$0.02/original charges$0.03; a dual-department owner positively saw six holds and$0.04/$0.06. A manager's list
contained no owner financial rows. Four owned detail requests and four authorized second-department owner details
returned200. All32 foreign GET/HEAD requests across four Host variants, four valid-CSRF foreign POSTs and four
manager detail requests returned404. Own API, encounter page and genuine original-hash DOCX export returned200;
all three foreign equivalents and the foreign job result returned404. Four surface cookie-isolation redirects
and four authenticated nonstaff admin-surface404 controls passed. Revoking the other author's membership retained
their personal billing/list/detail200 while their clinical API returned404. Password-only admin login failed and
console access redirected; actual TOTP login then succeeded302 to `/console/`, whose subsequent500 remains failed.
The later doctor-console/wrong-public-host/MFA CSV controls were not reached and are still pending a fresh archive.

Read-only reproduction against the exact served archive, with a database READ ONLY transaction and only audit
emission suppressed, found `VariableDoesNotExist: Failed lookup for key [created_by] in None`. At
`templates/admin_dashboard.html:27`, Django eagerly resolves `job.encounter.created_by.email` as the default-filter
argument even when the required `job.user.email` is populated. Mapping requests correctly have no encounter.
App repair `52f68707d1b07b2e622a45632d51a27187d907aa` renders the required bound requester directly. The real
mapping/held-reservation/MFA regression first reproduced the exception (one test, exit1,0.384s); the repaired
`ConsoleAccessControl` class passed five tests (exit0,1.121s), including existing role/MFA/CSRF controls and exact
preservation of all nine financial tables. This component result does not substitute for a served rerun. The lead
owns a new archive and restart; no running application source was edited. Finished clinical source refutation also
still awaits an announced complete freeze.

`served-auth-5a-first-through-fourth/manifest.json` hashes the11 retained raw results/diagnostics/RED/GREEN files
and binds each historical harness source commit. Original protected credentials, synthetic DOCX files, job/hold/
usage/ledger rows, audit events and all failed runs remain retained; credentials were not copied into this report
or repository. No financial history was deleted and no grant was fabricated. Evidence-backed retirement covered
all18 committed accounts from the second through fourth runs; the first committed none.

### Finished clinical6f0f647a refutation remains failed

The writer announced finished clinical commit `6f0f647a3d10227fc7ed9a30698c1877a7fff22f` with generation72a01ba6,
source scope653ffe19 and transcript contextd371aa54. All17 manifest files were verified against both working bytes
and committed bytes, then copied and hash-verified before probing. A distinct28-case instrument completed exit0
in8.690s with database connections and sockets denied. It uses actual field-relations validation, current stored
answer governance and finalization governance; every unselected model context unit is adversarially independent.
Five concrete unsafe releases and one unnecessary hold were demonstrated. This is supplemental adversarial evidence,
not a new campaign or a replacement for any frozen denominator. No provider request was made.

| Selected original source | Other exact source declared independent by the simulated model | Actual validation/current governance |
| --- | --- | --- |
| `Examination mild swelling over the left lateral ankle.` | `The patient has a left ankle without swelling.` | Original supported text; no finalization governance decision. |
| Same examination source | `The patient has absent swelling over the left ankle.` | Original supported text; no finalization governance decision. |
| Same examination source | `The patient has a swelling-free left ankle.` | Original supported text; no finalization governance decision. |
| `The patient reports pain in the left knee.` | `The patient has a left knee without pain.` | Original supported text; no finalization governance decision. |
| Same pain source | `Only her father has left knee pain.` | Original supported text; no finalization governance decision. |
| Original examination source | `Her father has no swelling over the left ankle.` | Conflict/empty: an unnecessary hold from an explicitly different actor. |

Relevant finished locations are `core/generation.py:3866` through the opposed-topic read at3882 and
`core/source_scope.py:200` through the same-assertion/topic intersection at224. These identify the measured path;
the writer and lead must diagnose and independently verify each finding before accepting a repair. No patch was
made to the measured clinical tree. Earlier OnlyFatherDoes/NotToday/date/nominal/exclusive medication failures,
the two prior Without/Past false holds, wrong-subject/stopped-medication controls and different-drug/locality/side
positives passed within this instrument. This does not attribute every new finding to this diff; its pre-change
baseline was not measured. It refutes the finished candidate's asserted qualification.

The retained original first-pass voice response remains byte-identical: no patient context yields zero supported
answers; an exact reviewed context yields only `v3_7` (examination), with both original adversarial picks still
conflict/empty and no unresolved finalization decision for the emitted supported answer. This is deterministic
replay, not a live transcription/generation or a human microphone pass. `clinical-6f0f647a-refutation/manifest.json`
hashes the raw result, exact instrument, successful instrument log and complete source manifest. All17 original
source witnesses remain in protected scratch and the writer's preserved commit. Finished clinical qualification
is withdrawn pending repair and a fresh frozen independent pass.

### Fifth served authorization run passed on a distinct repaired archive

The lead prepared a new provisional fixture-only demo at `789c0372127d89b1750a2f790c561e68c19f1654`, database
`quillmd_qa_int_sol_789c0372`, doctor9160 PID1247536, admin9161 PID1247540 and worker1247541. Only the verified
old provisional5a processes were stopped by the lead; their source/archive/database/evidence remain retained.
The harness independently rechecked all three process identities, all629 archive/extracted source files, protected
QA profile and actual synthetic health. Distinct terminal run `789c-fifth-20261003` completed exit0:124 actual HTTP
requests in7.542s and zero provider requests. This is the first complete served security pass; four earlier failed
runs remain failed. It is still provisional and fixture-only, with no clinical/model or installed qualification.

All list/totals/metadata, owner/dual-owner/manager detail, foreign GET/HEAD/valid-CSRFPOST, genuine hash-bound
export/API, separate-cookie and authenticated nonstaff role controls described above passed again. Membership
revocation retained two own financial200 positives while denying clinical access404. Password-only admin access
failed; actual TOTP login, admin dashboard and admin usage CSV succeeded. Sixteen doctor-console requests returned
404 without redirect for signed-out, clinician, ordinary admin cookies and an actual admin session under the doctor
cookie name. Sixteen wrong-public-Host requests returned404 without redirect across both listeners and normalized
case/trailing-dot/port variants; both correct-public-host login positives returned200. The original admin dashboard
500 is closed on this exact served archive. Every one of the nine financial table fingerprints is identical across
post-fixture, post-requests and exit snapshots. All six own fixture accounts are inactive with session version1 and
their memberships retired; fixture financial/clinical/audit rows and protected credentials remain retained.

The lead's browser/job idle window was released only after the real exit0. Across five terminal authorization
runs,298 HTTP requests occurred;24 committed own accounts were retired and the initial rolled-back run committed
none. No paid API request or installed/previous-QA mutation occurred. `served-auth-789c-fifth/manifest.json` binds
the exact raw complete result and harness source. No provider-billed evidence or clinical qualification is inferred.

At the clinical writer's request, six bounded parser witnesses were also captured against unchanged6f0f647a after
all17 hashes were rechecked before and after. They preserve source tokens/dependencies, actors, resolved subjects,
claim/negated keys, dependency maps and actual relation causes for the five unsafe and one false-hold findings.
The explicitpatient Without/Absent/Free clauses produce no negated keys; the exclusive father clause parses `left`
as `leave` and supplies no exclusive dependency despite shared named knee/pain; the father denial is explicitly
`other_floor=True` yet still supplies a hold. No source was modified. `clinical-6f0f647a-parser-witness/manifest.json`
retains the exact witness/instrument/log; the lead independently confirmed all five unsafe outputs. Clinical repair
and a new complete finished-source refutation remain pending and do not erase this failed qualification.
