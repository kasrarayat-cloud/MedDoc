# Template Twin clinical-quality technical report

Evaluation timestamp: 2026-07-19T07:42:03Z

Evaluated branch: `release/template-twin-ga-20260719`
Evaluated technical head: `a351fa7309a59d114a9bdee736c8d9b3b32b5d01`

## Verdict

**FAIL — LIVE PROVIDER QUALITY NOT YET MEASURED. CLINICAL SAFETY IS HUMAN PENDING.**

The deterministic Template Twin clinical contract cohort passes 176/176 tests across ten selected files. That cohort verifies fail-closed resolution, exact options, evidence anchors, modality equivalence, laterality, polarity, units, dates, and supported custom scalar behavior on synthetic fixtures. It does not estimate live-provider clinical accuracy.

The release-head live-provider Template Twin cohort is `n=0`. No claim about critical-field accuracy, unsupported-field recall, hallucination rate, accent performance, or specialty generalization can be made from it. Historical real-provider evidence for the ordinary SOAP pipeline is retained only as risk context: it did not exercise Template Twin field placement and was recorded at a different exact head.

No real PHI was used. No production provider call, database write, feature change, or signing action was performed for this report.

## Decision summary

| Question                                                                                                                         | Evidence                                                                                     | Status        |
| -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------- |
| Do deterministic field and evidence contracts behave as specified?                                                               | Ten-file synthetic cohort, 176/176 tests                                                     | PASS          |
| Does typed input resolve identically to equivalent voice evidence?                                                               | Synthetic modality-equivalence and voice-to-DOCX tests                                       | PASS          |
| Are exact options, units, dates, laterality, polarity, and anchors independently revalidated?                                    | Resolver, validation, certification-coverage, and evidence-verification tests                | PASS          |
| Is release-head live-provider clinical accuracy measured?                                                                        | No release-head scored provider cohort                                                       | FAIL          |
| Are multiple specialties, accents, tables, missing data, and ambiguity scored end to end on the released provider configuration? | Required scored corpus not yet executed                                                      | FAIL          |
| Are provider agreements sufficient for PHI?                                                                                      | Existing audit records no countersigned BAAs on file; current human verification is required | FAIL          |
| Has Clinical Safety approved thresholds and the observed results?                                                                | No signed decision                                                                           | HUMAN PENDING |

## Evidence cohorts

### Cohort A — deterministic Template Twin contracts

Command:

```text
npm run test:unit --workspace apps/transcribe-md -- \
  src/lib/template-twin/__tests__/voice-text-docx.e2e.test.ts \
  src/lib/template-twin/__tests__/fill-engine-equivalence.test.ts \
  src/lib/template-twin/__tests__/encounter-evidence-verification.test.ts \
  src/lib/template-twin/resolver/__tests__/resolver.test.ts \
  src/lib/template-twin/validation/__tests__/validation.test.ts \
  src/lib/template-twin/__tests__/certification-coverage.test.ts \
  src/lib/template-twin/custom-concepts/__tests__/custom-concept-extraction.test.ts \
  src/lib/template-twin/custom-concepts/__tests__/custom-concept-runtime-integration.test.ts \
  src/lib/template-twin/__tests__/supported-concepts.test.ts \
  src/lib/template-twin/__tests__/synthetic-evidence-gate.test.ts
```

Result: **10/10 files and 176/176 tests PASS** at the evaluated technical head.

This is a contract census, not a statistical clinical evaluation. Model calls are mocked or deterministically supplied where applicable. A passing test means the named invariant held for its synthetic fixture; it does not mean a provider will extract the fact correctly from arbitrary language.

### Cohort B — historical ordinary-pipeline provider context

The most recent committed full-chain real-provider report, `docs/eval-runs/primock57-fullchain-fabrication-20260706T205036Z.md`, was introduced at `d2a7a87e1568a4b313d5a54382cbc586a2505636`. It covers four audio cases in the ordinary Deepgram-to-SOAP pipeline, not Template Twin.

Recorded results:

- majority-vote class-(c) fabrications: 0 across four final notes;
- material omissions: mean 1.50 per case, maximum 4;
- deterministic content-line conservation: 74/90, or 82.2%;
- cases with silent line loss: 4/4;
- polished output retained: 2/4; the fabrication gate fell back to the pre-polish draft for the other two.

These results are **context only**. They are underpowered, do not cover Template Twin binding or field placement, and do not constitute a current release-head pass.

### Cohort C — release-head real-provider Template Twin evaluation

Status: **NOT RUN (`n=0`)**.

The repository contains a zero-PHI real-model lane and configured provider credentials exist outside the release clone. Before results can be admitted as evidence, the evaluation must use an immutable image from the eventual candidate head, the isolated `meddoc_qa_test` database, only committed synthetic fixtures, provider telemetry proving the configured models, and a pre-registered scoring protocol. Generated artifacts must remain outside Git and must be scanned for patient-like identifiers before retention.

## Proposed Clinical Safety thresholds

These thresholds are proposed for review; they are **not approved policy**. Clinical Safety may tighten them, change denominators, require larger cohorts, or reject the release despite a numeric pass.

| Metric                                     | Proposed release threshold                                                          | Required denominator and rule                                                                                                                                                                                           |
| ------------------------------------------ | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Critical-field accuracy                    | At least 99.5%, with zero catastrophic errors                                       | All expected critical fields in a pre-registered release-head cohort; report point estimate and 95% Wilson interval. Any wrong medication, allergy, negation, laterality, or critical measurement is a release blocker. |
| Unsupported-field recall                   | At least 99.0%, with zero missed critical unsupported fields                        | Every deliberately unsupported or ambiguous source region. A field is recalled only if it is visibly marked unsupported/uncertain and blocks activation or signing as required.                                         |
| Field-level clinical fabrication           | Zero critical fabrications and no more than 0.1% noncritical unsupported assertions | Every populated field plus generated narrative assertion; report both encounter-level and assertion-level rates with a 95% upper confidence bound.                                                                      |
| Evidence-anchor validity                   | 100%                                                                                | Every populated field must point to the exact canonical source span with matching mode, SHA-256, offsets, quote, polarity, and unique occurrence.                                                                       |
| Exact dropdown accuracy                    | 100%                                                                                | Every populated native dropdown must equal one certified option exactly. Nearest-option substitution is a failure.                                                                                                      |
| Critical negation and laterality accuracy  | 100%                                                                                | All critical polarity and laterality facts. Unknown or ambiguous evidence must remain unresolved.                                                                                                                       |
| All-field negation and laterality accuracy | At least 99.5%                                                                      | All scored polarity and laterality fields, with subgroup counts by specialty, modality, and accent.                                                                                                                     |
| Table-placement accuracy                   | 100% for the declared supported matrix                                              | Every populated cell, row, header/footer occurrence, and repeated-row binding must land at its certified structural identity with static regions unchanged.                                                             |
| Typed/voice canonical equivalence          | 100% on matched-pair facts                                                          | Equivalent typed and voice inputs must produce the same canonical facts and the same unresolved/unsupported dispositions; anchors remain mode-specific.                                                                 |
| Ambiguity containment                      | 100%                                                                                | Every pre-registered critical ambiguity, missing evidence, provider ambiguity, or incomplete automation case must block review/signing/download according to policy.                                                    |

### Proposed minimum evaluation design

- At least 300 fully synthetic encounters across at least six clinically distinct specialties.
- At least 50 matched typed/voice pairs.
- At least 30 cases per declared accent or speech-condition subgroup used in release claims.
- Deliberate traps for medication/dose, allergies, negation, laterality, measurements/units, dates, exact options, repeating rows, missing facts, conflicting facts, and unsupported structures.
- Independent double review of every critical discrepancy, with adjudication blinded to provider/model identity where practical.
- No rerolls. Every failed provider outcome, timeout, ambiguity, and fallback stays in the denominator.
- Results stratified by specialty, modality, document structure, accent/speech condition, and critical-field class; aggregate success may not conceal a failing subgroup.

Clinical Safety must approve the cohort and thresholds before token-spending execution so that results cannot influence the scoring rules.

## Required field-level scoring record

Each scored field must retain:

- synthetic case and template identifiers;
- expected canonical concept, value, unit, date precision, laterality, polarity, and option ordinal;
- actual field disposition and value;
- exact canonical source mode, source SHA-256, offsets, quote, and occurrence identity;
- structural target identity, including part, path, table/cell/repeating-row identity, and occurrence count;
- criticality, supported/unsupported class, ambiguity class, and failure taxonomy;
- provider/model identifiers and attempt/ownership outcome;
- reviewer decisions and adjudication without patient or physician identity.

## Blocking behavior required for release

The following outcomes must block review, correction acceptance, signing, and download until resolved:

- a critical value without valid evidence;
- conflicting or non-unique evidence for a clinically material field;
- missing required unit, polarity, laterality, date precision, or exact option;
- a provider outcome whose ownership or completion is ambiguous;
- unsupported or uncertain clinical meaning treated as supported;
- an invalid or changed structural target;
- incomplete automation, stale source identity, or stale template lineage;
- any critical discrepancy identified by Clinical Safety.

## Provider and privacy boundary

The committed BAA audit `docs/qa-reports/pre-pilot-baa-status-20260610T152350Z.md` records no countersigned Anthropic, Deepgram, OpenAI, Resend, or hosting BAA on file at the time of that audit. A current Privacy/Legal verification is mandatory before any real PHI. Until then:

- provider evaluation is synthetic only;
- production and PHI-bearing databases are out of scope;
- no physician or patient identity may appear in fixtures or retained artifacts;
- provider fallback and data-use configuration must be recorded per run;
- a synthetic pass cannot authorize PHI.

## Limitations and robustness

- The 176 deterministic tests are intentionally selected for Template Twin clinical contracts; they are not independent samples and cannot be converted into a provider accuracy percentage.
- The historical provider cohort is four cases, evaluates a different output surface, and contains material omission/conservation concerns.
- No release-head real-provider field scoring, accent subgroup analysis, repeating-row placement score, or Office-returned semantic score exists yet.
- Provider ownership remains incomplete for some sequential L1–L6 and custom-concept calls; ambiguous outcomes can replay unless that release blocker is closed.
- Completed-document candidate conversion is being implemented separately and is not covered by the current deterministic cohort.
- Desktop Microsoft Word evidence, production infrastructure readiness, Privacy/Legal approval, Clinical Safety approval, and Operations approval remain separate gates.

## Next actions

1. Freeze the technical candidate after remaining implementation blockers close.
2. Obtain Clinical Safety approval of the pre-registered cohort, thresholds, and adjudication protocol.
3. Build immutable candidate images and run the synthetic-only real-provider cohort in the isolated QA stack.
4. Produce a field-level, hash-manifested result set outside Git and a de-identified aggregate report inside Git.
5. Obtain independent technical validation of calculations and an explicit signed Clinical Safety decision.
6. Keep production rollout at 0% until every technical and human release gate passes.

## Evidence hashes

| Evidence                                                             | SHA-256                                                            |
| -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `docs/qa-reports/pre-pilot-baa-status-20260610T152350Z.md`           | `e71ee5da398491a964cf2ce962b46a72530cb20c6738f43999d956814fa41f82` |
| `docs/qa-reports/hallucination-reconciliation-20260611T072219Z.md`   | `db0df3693725dd2b828ff3850200a90258cd1b2f0ae502b32bb74bed4b2b2101` |
| `docs/eval-runs/primock57-fullchain-fabrication-20260706T205036Z.md` | `eef536cc55965ab780551331d0dc000ada37e130b532144dd4a7a0622f3d7646` |
| Ten-file deterministic cohort file hashes                            | Recorded in `clinical-quality-evidence-manifest.md`                |

## Human decision required

Clinical Safety must return one signed decision tied to the final exact SHA and evidence-manifest hash:

- `APPROVE` — thresholds, cohort, results, review language, limitations, incident criteria, and rollback criteria are accepted;
- `REJECT` — release remains blocked, with actionable findings; or
- `REVISE` — identify the exact additional cases, threshold changes, or controls required.

No Codex or implementation-agent signature is valid for this gate.
