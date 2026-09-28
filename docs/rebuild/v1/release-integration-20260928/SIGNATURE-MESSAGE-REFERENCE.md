# Signature message correction

Brief: help a clinician understand how a protected custom Word signature area is completed. Existing product is the design target; direct build, one conditional rendering correction, no new layout or styling.

References inspected before editing: the actual D30 generated-review HTML, encounter_answer_v3.html’s signed-by-hand state, the legacy tab-form Signature UI and its positive control, and Refero’s bundled copywriting guide (orientation/status/action and factual next steps). The reference lock keeps the existing signed-by-hand instruction for protected Word fields; the account-name instruction belongs only to an input that actually supports that action. The user’s signature/consent preservation requirement supplies the behavioral boundary.

The D30 first rendered page showed both “Signed by hand ... never filled” and “type your account name” on the same protected field, which exposes no text control. The single template condition now suppresses the latter for v3_input=signed. Legacy typed signatures retain their existing account-name instruction. No signing or consent permission changed.

Validation: the corrected D30 authenticated missing workflow and existing v3 review-kind check pass. The first legacy test selection used an absent class name and is retained as a harness error; rerun uses the actual TabFormWorkflowTests class. No product test was disabled. Final legacy result is in the private signature-legacy-02 manifest.
