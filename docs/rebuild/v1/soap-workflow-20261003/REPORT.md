# Built-in SOAP route — 2026-10-03

Prepared source, not installed or qualified for live SOAP generation. The workspace form library now links to **Use SOAP note**. An active owner or clinician chooses an authorized department, creates one reusable blank SOAP DOCX original, reviews its four physical answer destinations, confirms the mapping, then uses the existing patient/encounter notes or reviewed-transcript route. The existing worker, source evidence, clinician acceptance/edit/leave-blank decisions, finalization and Word download retain their normal authority and immutable-version checks.

`core/soap_document.py` is a pure deterministic original constructor, shared with prospective qualification without a second generator. Original SHA256: `d92f300248ced2b07f6da5f0e7c12beaf43b01c0264253fd1b40ef2cb78f03aa`. Labels: Subjective, Objective, Assessment, Plan. The original has four ordinary two-column rows, no fixed heights, signing locations or clinical text. The configured Word inspector supplies each physical destination and the original/engine/mapping import manifest. It does not automatically confirm the mapping. Reuse preserves clinician corrections and every historical version. A changed/missing original is refused, never reconstructed over existing data. Creation is serialized on the department row and uses a deterministic original identity.

The new route explicitly denies the administrator host, including an MFA administrator with clinic membership. Form choices and the creation helper require a verified active owner/clinician membership; foreign, revoked, employee and manager access cannot create private files or originals. Existing cross-department mapping, original, encounter and export routes retain their scoped permission checks. Audit detail contains identifiers/hashes only.

## Preserved test results

The first fixture-only HTTP run used the original TEST_SETTINGS default profile. It finished **exit1: 16 of17 passed, one failed,57.665 seconds**; the test database was destroyed. It covered12 new SOAP methods and5 existing document workflow methods. It is neither a live result nor qualification of the intended Sonnet profile. The original assertion logged all four answer statuses as conflict, but did not retain encounter/job payloads before database teardown; a later replay is not presented as that first wire.

Passed positive/negative controls include:

- `test_repeat_start_preserves_original_and_corrected_mapping_version`: one original, two immutable mapping versions, same original bytes/path, newest correction kept, one upload audit.
- `test_corrupt_existing_original_is_refused_without_replacement_or_new_version`: exact changed bytes retained, original/mapping counts unchanged.
- `test_cross_department_post_and_saved_original_mapping_and_encounter_are_denied`: actual created/confirmed authorized objects are the positive control; foreign POST produces no file/row and outsider receives404 for their mapping/original/encounter/export.
- `test_authenticated_mfa_admin_surface_has_no_soap_clinical_access`: real Services200 positive control; SOAP GET/POST404 with no clinical sentinel or saved original.
- Missing documented Assessment/Plan remain missing, then explicit “Leave blank — reviewed” finalizes blank cells.
- A separate clinician-edited40-line Plan survives actual finalization/download once, completely, while the original and neighboring labels remain intact. This is clinician correction/export recovery evidence, not first-pass automatic generation correctness or native Word inspection.

The failed unchanged note was:

```
Subjective: cough for two days.
Objective: lungs clear.
Assessment: clinician assessed a viral upper respiratory infection.
Plan: rest, hydration and review if symptoms worsen.
```

Two separately named offline diagnostics preserve actual inspector-generated mapping and all answer reasons. The intended-profile diagnostic uses `claude-sonnet-5-5`, between_tools/medium, list rates2/10/0.20,20,000 output tokens and ordinary-field-relations-v4. It still produces **0 useful adopted answers,4 conflicts**. Removing only the conditional suffix makes the diagnostic supported; that counterfactual isolates the cause and does not replace the failed source or count as acceptance. Clinical repair/refutation and an affected HTTP replay with stored request configuration/answer evidence remain required. Tests now explicitly use the intended fixture profile and retain synthetic original, notes, mapping, job config, answers and export before teardown when the existing Word artifact environment is set.

No provider request or charge occurred. No installed service, real account, live payment or production secret file was changed or read. Ordinary unlabelled SOAP semantic quality, real-provider typed/voice usefulness and native Microsoft Word/human microphone acceptance remain separate qualification requirements.

## Entry UI evidence

Refero research reused the existing library and upload/review patterns, with no new CSS/assets. Chromium rendered the actual SOAP/library templates with synthetic context at1280px and390px. Both fit without horizontal overflow; the labelled department select and submit control are readable, Tab reaches the button and the no-membership state exposes no submission. These are local rendered-template visual checks; persisted HTTP controls were exercised separately. Initial render fixture omitted the existing username fallback and initial browser instrument demanded a colon-free exact field label; both original instrument failures are retained. Corrected browser process exited0 and closed. Mobile and desktop images were inspected.

Protected originals, diagnostics and later retained workflow artifacts remain under `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/`. Filled DOCX files are not committed. Nonsecret logs/diagnostics/screenshots have committed hash manifests. Full exact-candidate CI, integrated gates and private served checks remain root-owned.
