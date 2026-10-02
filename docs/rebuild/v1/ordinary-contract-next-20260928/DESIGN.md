# Ordinary history: separate answer spans from governing context

## Recorded failures and scope

This design uses the retained original selections, not a new model run. The
ten-note denominator remains **26 supported / 77 selections**; the five-note
subset remains **12/12**. The remaining 51 are the previously classified
34 useful explicit selections, 7 requiring adjudication, and 10 invalid
single-field selections. None is removed or relabelled here.

[three-history-cases.json](three-history-cases.json) preserves the complete
original notes, fields, picks, answer objects, offsets and first-pass outcomes.
Its source file SHA256 is
`28bac03e50f3a8b7a6571f0be9f97da35fde744d60d67ba4d1c4e24f33aedb71`;
recorded generation SHA256 is
`a7bbe3d9efd0db5247dccebeba0cb97137786312b03f22994c394cdfb744a81b`.

| Original ordinary note | Exact useful original selection | Recorded result and governing neighbour |
| --- | --- | --- |
| note1: knee presentation, followed by mixed medical history/medication, named examination/assessment/plan | Both Chief complaint and HPI select `45-year-old man presents with right knee pain for three weeks after a fall.` | Both `conflict`, empty text; context `He has hypertension and takes lisinopril 10 mg daily.` Case total5/9. |
| note2: cough presentation, symptom report and asthma on separate lines, then named medications/examination/assessment/plan | Chief: `Patient presents with a cough for five days.` HPI also selects `She reports low-grade fevers and green sputum.` | Both `conflict`, empty text; Chief inherits the symptom report; HPI inherits its selected neighbours and `She has asthma.` Case total6/9. |
| note4: explicit patient presentation, headache timing, symptom denial and medication in one paragraph | Chief: `This is a 30-year-old female seen for headaches.` HPI: `The headaches started two months ago and are worse in the morning.` plus `She denies visual changes, nausea, or weakness.` | Both `conflict`, empty text; Chief inherits headache timing; HPI inherits the patient anchor and `She takes ibuprofen as needed.` Case total3/8. |

These selections contain useful documented history and must preserve their full
wording, timing, side and denial. They do not establish complete histories or
complete documents. Note1's mixed hypertension/medication sentence is **not** a
new single-field positive. Note4's medication, smoker and NKA holds remain
outside the first release rule, including the anaphylaxis/hypersensitivity
counterexamples. No mandatory note labels are introduced.

## Distinct causes

* **Syntax:** the new parser repairs previously unrecognized complete sentences
  such as the A35 activity statement. It cannot fix this source-context problem.
* **Source representation:** `v3_scope_selection` requires an entire source
  block to be selected as answer text. The competing-destination check also
  removes that allowance when Chief complaint and HPI share a source sentence.
  The existing prompt explicitly permits independently applicable cross-section
  reuse. The deterministic representation cannot express that promise safely.
* **Clinical context:** patient attribution does not prove that an Assessment
  cannot qualify or contradict a selected answer. The failed NKA actor shortcut
  remains a counterexample. Syntax, label identity, a complete partition or a
  model's boolean `conflict=false` is not proof of independence.
* **Question coverage:** A35's activity sentence supports activities only. Its
  disclosure/risk subquestions stay visible and require the existing clinician
  review. Source acceptance must not claim compound-question completeness.

## Authorized bounded implementation

New versioned contract, default off, for **at most two** distinct unique,
unscoped, text/long-text roles: exact Chief complaint and HPI/History of present
illness. Aliases for the same role are duplicates, not two independent targets.
No numbered, repeated, side/role/section-scoped, protected or signing field gets
this allowance. Sources above64 units retain the existing contract; no unit is
truncated and no100-fields-by-all-units response is requested.

The existing request receives the complete source. Its one structured response
keeps exact output unit IDs and adds a complete per-unit relation for each
eligible history field. The closed relations are `answer`, `context_only`,
`required_qualifier`, `contrary`, and `unresolved`. Each offered unit occurs
exactly once; duplicate, missing, foreign or malformed IDs refuse the response.
The answer IDs must agree with the selected exact source units. Required
qualifiers must be included in output; otherwise the answer is held. Contrary
or unresolved relations hold the answer. A field with no output remains missing.

The server derives and binds the full source-unit set, exact notes and mapping
identity, selected field, output/evidence, and contract version. Model text never
supplies those identities. A server-created stored record carries the relation;
clients cannot create or replace it on save. Changed notes, mapping, answer,
evidence or contract invalidate it. Historical answers without this record keep
their original reader; no draft or finalized record is silently upgraded.

An eligible relation may discharge only generic adjacency and the specific
Chief/HPI evidence-sharing restriction. Existing source ownership, malformed
evidence, wrong labelled field, duplicated destination, side, correction,
inherited/conditional scope, syntax, shape, signing and consent guards remain
vetoes. Generation, page, unchanged save and finalization use the same reader.
The complete source remains available beside the answer through existing
evidence/review controls; context is not inserted into the export as new facts.

**Semantic limitation:** `context_only` remains an exact-model clinical
judgment, not a deterministic theorem. The partition makes omissions and stale
decisions detectable; it cannot prove the classification is correct. This slice
prepares the implementation and mocked workflows. The live flag stays off until
eligible Sonnet5 clinical/context qualification is completed. No additional
provider request or verification allowance is created.

## Concrete negative and qualification obligations

The unchanged three cases are the positives. The finite adverse set must include:

* A later correction changes right knee to left: existing correction/side veto,
  regardless of a model `context_only` classification.
* A history attributed to a father, patient advocate, quoted third party or
  unresolved pronoun: existing ownership/scope veto, not a name blacklist.
* A denial that removes the offered symptom: contrary relation holds; a source
  that already has an explicit denial must retain its complete negative wording.
* A later statement that headaches resolved and have not recurred: a required
  temporal qualifier cannot be omitted while presenting the source as current.
* A note4 Assessment mentioning daily smoking, ibuprofen cessation, penicillin
  anaphylaxis or hypersensitivity: no new Medications/Smoker/NKA allowance.
* A semantically contrary statement lacking an existing lexical warning: an
  intentionally false `context_only` model response is **not** claimed safe by
  schema validation. This is part of exact-model qualification, with original
  responses retained. The finite mock suite can prove contrary/qualifier
  handling, not a model's ability to identify every such relation.

For the three original notes, run the actual authenticated synthetic worker,
review, unchanged save, finalization and download. Chief/HPI must require no
answer edit. Remaining held fields require explicit clinician decisions and
remain assisted in reporting. Force historical supported states and invalid
bindings through page/save/finalization. Finish with independent refutation of
the frozen diff. Preserve first-pass results; report candidate outcomes
separately rather than replacing77 or claiming an automatic whole-note pass.

## Affected paths and remaining work

At frozen5961, the affected paths are `UnitSelections`/`unit_selections`,
`generate`/`validated`, `maximum_cost`, `v3_scope_selection`,
`validate_tab_selections`, `v3_preceding_warnings`, `judged_context` and the
stored supported-answer reader. Use a small separate contract module for the
schema, scope, partition/binding and validation. Reuse existing Sonnet request
and settlement helpers. Bound schema/payload/output costs without changing
historical prices, receipts or balances. Configuration snapshots must distinguish
the contract actually sent. Keep the default off and avoid changes to unrelated
Word mapping or WM narrative paths.

This is internal source-contract engineering, not a funding-only blocker. The
next groups remain SOAP roles, caregiver/encounter ownership, mixed-clause
evidence and cross-field semantic consistency, with their existing34V/7J/10I
classification. Exact-model clinical quality remains a separate qualification.

The base4caa retention-readiness document was read briefly. It describes policy
and legal-hold/disposition dependencies; the parent is now implementing a newer
retention stream elsewhere. That historical document is not current deployment
proof and does not block this offline clinical contract work. No legal duration,
production record access, purge or additional clinical-data route is introduced.
