# Remaining ordinary-note selections — finite engineering triage

Read-only classification of `evidence/known-results.json`, generation SHA256 `8835d98c6943a323a07207a627151c19a34e98bcb15d2c6f373575ac586396e0`. No new parser/model run or campaign. Exact inputs, original selections and outcomes remain unchanged: **22 supported + 55 held = 77**. The other five-note subset remains12/12. The subsequent value-evidence repairs do not supply a new measurement of these selections.

**B-G1 remains a demonstrated engineering blocker.** Even ideal simulated source selection leaves ordinary relevant content held. This cannot all be assigned to provider funding or live Sonnet5 qualification.

## Classification of every held selection

- **V —38:** The selected source explicitly states content relevant to the intended ordinary field. This identifies a source-context/role/option engineering task; it does not certify completeness, patient attribution or a future automatic pass. Chief/HPI sharing also needs a declared destination relationship; it cannot bypass duplicate-question safeguards.
- **J —7:** The proposed per-field meaning, selected wording or patient ownership needs author adjudication. Keep the hold until that evidence/contract exists.
- **I —10:** The original selection is not a valid single-field positive oracle. Keep it and its failure in77; do not replace or drop it to improve the score.

Every field, exact original selected quote and category is enumerated in [remaining-55-classification.json](evidence/remaining-55-classification.json). The table groups identical issues for readability.

| Retained case | Held fields and classification | Concrete source and currently applicable gate |
| --- | --- | --- |
| note1 | Chief complaint, HPI: **V2** | Full age/presentation sentence is stated, but it is a partial selection from the unowned patient/pronoun block and is selected into two history destinations. Complete-block and competing-destination guards apply. |
| note1 | PMH, Medications: **J2** | Both select `He has hypertension and takes lisinopril 10 mg daily.` as their whole answer. Establish exact per-field clause/wording and a supported source-span contract; do not simply place both topics in both fields. |
| note2 | Chief complaint, HPI, PMH: **V3** | Patient cough, subsequent symptom report and `She has asthma.` are divided across three selections from one source block. Current ownership rules cannot establish these topic-specific spans. |
| note3 | All nine selected fields: **I9** | The entire unpunctuated54-word mixed-topic note is selected into every field, including an assessment not explicitly stated. Passing those choices would be wrong. Reviewed voice punctuation/source selection remains required work; the invalid oracle is not grounds to declare ordinary dictation unsupported. |
| note4 | Chief complaint, HPI, Medications: **V3** | Explicit patient presentation and subsequent source statements are partial blocks/pronoun clauses. Retain every symptom denial and time qualifier. |
| note4 | Allergies, Smoker: **V2** | `No known drug allergies.` is a verbless unowned reference to Allergies. `She is a nonsmoker.` has no declared exact option conversion to No. Both are stated facts, not permission to drop negation or infer options from arbitrary prose. |
| note4 | Examination, Assessment, Plan: **V3** | `Neurological examination` is outside the narrowly recognized source-head syntax. Other fields inherit this unresolved context. Plan includes `to start...` and an unselected-or-selected pronoun follow-up; qualification/whole-block rules apply. Preserve the complete instructions. |
| note5 | Chief complaint, HPI, Examination: **V3** | Source uses Subjective/Objective labels that are not form destinations. A declared SOAP-to-field evidence relation is missing; Objective's clinical wording must remain intact. |
| note5 | Assessment: **V1** | Its directly labelled value is held by neighbouring nominal `Plan: naproxen 500 mg twice daily with food and physiotherapy.` The Plan itself currently succeeds. The complete named Plan is not recognized as a safe independent topic because it is neither a short plain value nor a finite-verb narrative. |
| note6 | Chief complaint: **V1** | Explicit patient visit-purpose sentence exists; surrounding procedural/consent source block prevents partial release. No consent or procedure may be invented from it. |
| note6 | Consent obtained, Plan: **J2** | The note explicitly records `Consent obtained: yes.`, but establish whether this field records that fact or attests authorization/signature. The selected Plan also includes procedure tolerance before the actual suture-removal plan; adjudicate the intended field scope without silently editing the frozen selection. |
| note6 | Examination: **I1** | The selected sentence describes excision and suturing, not an examination. A form author could define another field meaning, but the present generic Examination label supplies no such evidence. |
| note7 | Chief complaint, HPI, Medications: **V3** | Mother explicitly brings her four-year-old son; subsequent He and no-regular-medications statements require a safe caregiver/patient role contract. The negative medication object is an unresolved literal source reference today. Do not remove family guards. |
| note7 | Examination, Assessment, Plan: **V3** | Actual named source statements exist but inherit unresolved caregiver/negative-medication context. Preserve left-side findings and the complete drug/duration plan. |
| note8 | Chief complaint, Medications: **V2** | Visit-purpose fragment lacks a finite verb; the current amlodipine sentence has a pronoun and no established source owner. Current5mg and planned10mg must remain separate qualified facts. |
| note8 | HPI: **J1** | `Blood pressure today was 142/88.` is explicit but may belong in vitals/examination rather than HPI. A field-specific expected map is needed; source truth alone does not establish destination. |
| note8 | Allergies, Smoker, Examination, Assessment, Plan: **V5** | Exact answers inherit unresolved `Heart and lung examination` and qualified treatment context. Preserve `not at goal`, dose increase and follow-up; no shortening into an unqualified diagnosis/treatment. |
| note10 | Chief complaint, HPI: **V2** | The patient's exertional chest-tightness statement is explicit; it is not the father statement. Complete-block/competing-destination rules still hold it. |
| note10 | PMH, Medications: **J2** | `He has high cholesterol. He takes rosuvastatin.` follows `His father had a heart attack...`. The competing pronoun antecedent is real; do not assume the patient or override with a model guess. |
| note10 | Allergies, Smoker, Examination, Assessment, Plan: **V5** | Named source values are held amid unresolved role and qualified-topic context, including `possible stable angina`. Faithful wording and source scope are required; this is not authority to assert unqualified angina. |

note9 is7/7 and has no row among the remaining55. Counts reconcile as **V38/J7/I10**, without changing any result.

## Code gates and finite repair order

Code references below use the exact retained [generation source](evidence/value-context/generation-before.py); multiple guards may apply to one selection. This is static diagnosis from retained outputs/code, not new branch-instrumentation evidence.

| Gate | Exact reader | Required next engineering work |
| --- | --- | --- |
| Complete block and destination | `v3_scope_selection`2493–2502; competing unowned selections2665–2673; before/after guards2712–2725 | Define exact per-field source spans and safe relationships between history destinations. Never accept an entire mixed paragraph into every question. |
| Independent labelled topic | `v3_preceding_reading`2432–2449; same neighbour guards | First bounded slice: nominal labelled Plan and independent qualified topics, keeping complete wording. Include root's separately reproduced prior-positive Indication regression with repeated Pain/Comments; repeated questions must stay held. No source edit before current value-evidence refutation closes. |
| Literal source subject/reference | `v3_field_subjects`2169–2220; `v3_related_source_blocks`2221; unresolved subject2694 | Later finite negative-Allergy/Medications and examination source-head cases. Retain all-source reference ambiguity and foreign/future ownership guards. Do not solve by widening arbitrary prefixes. |
| Patient/relative and SOAP roles | source-block construction2374–2384; ownership reader2169 | Explicit caregiver-to-child and declared SOAP relations require a shared generation/review/save/finalize contract with negative controls. Ambiguous He after father remains held. |
| Exact options/fragment shape | `runs_on`2014; finite-statement2698; `v3_option_answer`3146 | A bounded faithful natural-negative option relation and documented source fragment contract can be engineered. No guessing polarity, rewriting notes into mandatory labels or releasing the run-on whole-note oracle. |
| Consent | `judged_context`1712–1714 and independent consent checks | Preserve withdrawal, conditional and authority distinctions. Author field-meaning adjudication is separate from a recorded source fact. |

Each engineering slice needs its retained positive, targeted adverse inputs and a complete doctor workflow, followed by independent finished-diff refutation. Reuse unaffected proofs. Classification V does not preapprove a blanket release of38 fields; no semantics/destination inference can be smuggled through an independent-topic exemption.

After deterministic code gaps are closed, the exact served model still needs bounded source-selection and clinical-quality qualification. Native Word/dictation and author field-meaning evidence are separate prerequisites. Neither live-model spending nor a favourable source-selection result can repair missing deterministic scope logic.
