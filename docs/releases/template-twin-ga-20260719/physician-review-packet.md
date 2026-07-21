# Template Twin physician-review packet

Status: **HUMAN PENDING**

Release: `release/template-twin-ga-20260719`
Exact candidate SHA: **TO BE FROZEN AFTER TECHNICAL GATES**

## What the reviewer is deciding

Decide whether the declared Template Twin compatibility boundary, physician review language, clinical uncertainty behavior, and synthetic quality results are acceptable for controlled use by authorized QuillMD physicians. This is not approval of arbitrary DOCX files, completed patient reports as templates, or unattended clinical automation.

## Intended physician workflow

1. Upload a native blank/fillable DOCX or deliberately choose the separate Completed Document → Template Candidate mode.
2. The system quarantines, scans, inspects, and minimizes metadata before admission.
3. Mapping suggestions remain inactive until every proposed field, uncertainty, and unsupported region is visible to the physician.
4. The physician confirms or changes each binding; bulk confirmation is allowed only when every included suggestion remains visible and reversible.
5. A synthetic staging exercise proves the certified fields and structural occurrences.
6. During a visit, every populated field must have canonical evidence. Missing, conflicting, unsupported, or ambiguous evidence remains unresolved.
7. The physician reviews the rendered document and all blocking issues before signing.

## Safety language to approve or revise

> Template Twin fills only physician-certified fields supported by evidence from this encounter. It may leave fields blank or block signing when evidence is missing, conflicting, ambiguous, or unsupported. Review every populated field, every unresolved item, medications, allergies, measurements, units, dates, negation, and laterality before signing. The physician remains responsible for the final document.

## Declared supported boundary for review

Technical evidence currently covers native Word content controls, exact dropdown/combo options, checkbox polarity, dates, scalar and narrative text, bounded ordinary placeholders, tab-only blank table cells, standard table placement, headers/footers, exact occurrences, units, laterality, polarity, and specialty-specific custom scalar concepts where a stable binding can be certified.

The final supported-file matrix must narrow this statement to structures that pass exact-head corpus, Office-return, and clinical scoring. Anything outside the published matrix must fail closed with a useful explanation.

## Explicitly unsupported or not yet approved

- arbitrary DOCX files or unsupported auxiliary parts;
- macros, OLE, ActiveX, scripts, external relationships, unsafe fields, hidden text, unresolved revisions, comments, malformed XML, and decompression attacks;
- populated completed reports treated directly as blank templates;
- candidate regions inferred from ordinary narrative without physician approval;
- unsupported complex merges, drawings, floating text boxes, or unbounded repeating structures;
- nearest-option substitution for dropdowns;
- inferred unit, date precision, polarity, or laterality when evidence is absent;
- production PHI until Privacy/Legal verifies all processor agreements and data-use controls;
- unattended activation, signing, or download when a critical gate is unresolved.

## Required review exercises

Use only the supplied synthetic reviewer corpus and returned Word evidence package.

| Exercise                                                                               | Reviewer result |
| -------------------------------------------------------------------------------------- | --------------- |
| Confirm every candidate field is visible and understandable                            | PASS / FAIL     |
| Confirm uncertain and unsupported regions are concise and complete                     | PASS / FAIL     |
| Confirm exact dropdown choices and explicit denial behavior                            | PASS / FAIL     |
| Confirm medication, allergy, dose, unit, negation, and laterality traps                | PASS / FAIL     |
| Confirm table, header/footer, page, and repeated occurrence placement                  | PASS / FAIL     |
| Confirm missing information remains blank/unresolved and blocks where required         | PASS / FAIL     |
| Confirm side-by-side completed-document candidate review does not overwrite the source | PASS / FAIL     |
| Confirm review language is clinically adequate and not misleading                      | PASS / FAIL     |
| Confirm known specialty and document limitations are acceptable                        | PASS / FAIL     |

## Findings register

| Severity | Case/template | Finding | Required correction | Retest evidence |
| -------- | ------------- | ------- | ------------------- | --------------- |
|          |               |         |                     |                 |

Any critical medication, allergy, negation, laterality, measurement, evidence, structural placement, signing, or data-isolation error is a release blocker.

## Human decision

- Decision: `APPROVE` / `REJECT` / `REVISE`
- Final exact SHA reviewed: **UNFILLED — HUMAN REQUIRED**
- Evidence-manifest SHA-256: **UNFILLED — HUMAN REQUIRED**
- Name and role: **UNFILLED — HUMAN REQUIRED**
- Date/time and timezone: **UNFILLED — HUMAN REQUIRED**
- Signature or approved organizational record: **UNFILLED — HUMAN REQUIRED**

Codex and implementation agents may prepare this packet but may not sign it.
