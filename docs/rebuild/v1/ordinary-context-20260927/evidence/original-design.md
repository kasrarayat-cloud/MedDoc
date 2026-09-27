# G1 retained ordinary-note diagnosis — 2026-09-27

Diagnosis only. Code remains clean at WM branch HEAD 185f1ae25978273267048365d2e30c69599e2cdf. No model request, broad campaign or source mutation. Eight existing synthetic cases were read through the unchanged source and validator, with actual units, parsed fields, neighbors and output retained in selected-known-cases.json. Generation SHA34558bca7356fabb04ceb16f2eeb74d94cf043b0fc36d0aab49b934e05e77721.

## Exact causes

The prior full five-note denominator remains 1/12 supported, 11/12 held. All eleven held cases become supported in the retained diagnostic ablation that disables both unconditional paragraph-neighbor rules. That ablation is evidence of cause, not a safe repair. The current eight-case inspection reproduces all five-note holds on the combined WM candidate.

Of the prior r1 72/77 held cases, 45 lift when those two neighbor rules are disabled. Eight belong to a single unpunctuated 54-word sentence that the fixture selects for almost every field; those selections cannot establish correct useful answers for medications/allergies/plan. Nine note2 values are held note-wide because `Return if symptoms worsen.` contains `if`. Remaining failures combine printed-option exactness, fragments without a listed verb, and the prior causes; the retained single-rule attribution is not a disjoint full causal model.

Two validators also read sentence context differently: `source_units` can isolate an embedded `Smoker: No.` sentence on a line starting with ordinary prose, while `LabelledLines` used for options reads larger line tails. A safe repair must share a source-context representation rather than blindly making option matching looser.

## Concrete before -> expected cases

1. Existing t-worker:
   `Referring physician: Dr Example\nPatient presents with right knee pain.\nSmoker: yes`
   Reason for visit currently holds the entire exact patient sentence solely because the plain physician answer precedes it. Expected: support the unchanged complete patient sentence in the unique general narrative destination, retain its exact offsets and source context. No pronoun-only subject or wrong-topic field exemption.

2. Existing t-prose:
   `Patient presents with right knee pain for three weeks. Allergies: penicillin. Plan is physiotherapy twice weekly and review in six weeks.`
   Plan currently holds `physiotherapy twice weekly and review in six weeks.` solely because `Allergies: penicillin.` precedes it. Expected: exact explicitly named Plan value, preserving all original words/order. The Plan is not a consent assertion. Chief complaint and Allergies also hold due to this following non-plain Plan sentence; those forward holds need a separate, stronger context design and are not waived by the proposed first repair.

3. Existing t-lines (same note, separate lines with `Smoker: No.` before Plan): Plan currently holds because the plain smoker answer precedes it. Expected: the same complete explicit Plan value. No change to smoker's following-context hold in this first bounded repair.

4. Existing r1-note2: one conditional return instruction holds every field. Desired full workflow keeps `Return if symptoms worsen.` as a conditional Plan instruction and does not reframe an already explicit, independent current finding. This requires source scopes linked to their governing units and a common reader at generation/page/save/finalization; it is outside the minimal preceding-context repair below. Never strip the conditional or accept a drug/finding below an unresolved `If ...` header.

5. Existing r1-note3: expected behavior remains a visible hold for wrong-topic whole-note selections. A useful future completion needs bounded sub-sentence extraction with exact source spans and context, or appropriately punctuated *reviewed transcription*, not automatic copying of the entire run-on into every field and not mandatory label rewriting.

## Smallest bounded repair proposed first

Replace only the unconditional *preceding-unit* hold for these two structurally established scopes:

- A complete explicit patient-subject sentence assigned to an existing unique general narrative destination, where preceding context consists of plain explicitly named unrelated form answers and all other governance/forward checks pass. Preserve the sentence and offsets without rewriting. A pronoun, relative/family subject, side-specific field, duplicate field, option/consent or unsupported topic is ineligible.
- An explicitly named natural form statement (`Plan is ...`) assigned to that exact unique field, immediately preceded by a plain explicitly labelled answer, where source-wide/shape/type/correction/consent and following-context checks all pass. Its explicit form subject names the destination; do not generalize this to a pronoun statement (`Diagnosis was ...`) under a family narrative.

Use a shared source-context result for generation and existing-draft review/save/finalize, preserving the qualifying source units as context rather than erasing them. Existing note-wide corrections, consent external-evidence checks, duplicate-label/option guards, wrong Lt-knee/allergy destinations, repeated instructions/order and exact export values remain required negatives. No new medical synonym or arbitrary semantic keyword expansion is proposed.

This first repair admits the three concrete ordinary positives above and provides a narrow useful path; it does not close G1 or promise a new subset percentage. A larger context graph is needed for independent topics in a continuous narrative and for conditional instructions. Keep all original 1/12 and 5/77 results as first-pass evidence; report repaired known cases separately, and keep live Sonnet quality distinct.

## Next safe action

Root reviews this bounded design. If proceeding, create a new isolated worktree from final WM or a supplied combined descendant, write failing exact-case and counterexample pins, implement the common source-context change, run only affected source/review/export checks, then obtain independent finished-diff refutation. Do not alter this already handed-off WM tree. No paid/model/corpus operation is justified by G1 diagnosis.
