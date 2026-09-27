# Legacy Word inspection — 2026-09-27

**Binary `.doc` remains explicitly refused. Safe conversion is plausible, but no qualified production converter or complete workflow exists. This is not automatic compatibility.** No unseen original/annotation was accessed, provider generation called, source modified or corpus denominator changed during this inspection.

## Existing evidence reused

Known development file D19 original SHA256: `46f4c7cffa95fa64e34e51a6ced30857084b4f5b3baf3626c0be9c8a6dd8d84d`.
Retained normalized DOCX: `394eaa6eb6fc4e33ab21eac78d635cb68c6d687baeb7827fef7d58ded5814219`.
Both match earlier evidence. The original annotation has 17 expected answer areas; historical first pass remains 2 correct, 12 missed and 3 wrong (with 3 extra mappings). It remains a failed development case, not a new release score.

On inspected release `c74ed7c1fc513853caf54ac71de6a967bc19ceaa`, the retained DOCX yields eight detected fields. Eight visible initials rectangles are not fully represented. The participant name/date/signature paragraph is assigned an initials instruction; the following empty separator is assigned the preceding signature-line label as a date. A consent initials destination is ordinary text. These are concrete downstream recognition defects: the normalized XML still contains eight anchored rectangles and both signature blocks' underlined runs. This does not prove generation would invent consent, nor does preserved XML establish full original fidelity.

An orphaned consent-role line appears on a second rendered page. Without original native Word comparison, its cause cannot be attributed to conversion or the original layout. No binary-original fidelity claim is made.

## Converter and required boundary

Existing image `gotenberg/gotenberg:8` is pinned locally at digest `sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b`, version 8.34.0. A networkless read-only version probe confirms LibreOffice 26.2.4.2. The generic parser sandbox forbids process execution; the WM CLR sandbox is a different qualified boundary. Neither authorizes simply launching LibreOffice inside it.

A distinct converter must enforce no network/secrets, a restricted filesystem/spool, resource/time/output limits, explicit macro nonexecution and no link updates. Headless mode alone is not that policy. Official load controls: [MacroExecMode.NEVER_EXECUTE](https://api.libreoffice.org/docs/idl/ref/namespacecom_1_1sun_1_1star_1_1document_1_1MacroExecMode.html) and [UpdateDocMode.NO_UPDATE](https://api.libreoffice.org/docs/idl/ref/namespacecom_1_1sun_1_1star_1_1document_1_1UpdateDocMode.html). Gotenberg HTTP safeguards cannot be attributed to direct `soffice` invocation without verification.

Before conversion, the binary structure needs validation and explicit refusal for encrypted/corrupt documents, macros, embedded objects and tracked revisions. Inspecting the normalized package alone cannot prove the converter did not remove or accept unsafe original content.

## Concrete integration requirements

1. Keep the uploaded original and original hash immutable. Add a separately immutable normalized DOCX identity, original linkage, converter/profile digest and conversion outcome. Current `Template.original_path/sha256` serves both upload identity and processing basis; overwriting it would lose that distinction.
2. Provide a qualified isolated conversion runner; never give the application the Docker socket. Reuse bounded upload/workspace/timeout/hash orchestration where valid.
3. Revalidate the normalized DOCX, bind mapping/generation/review/export to it, and retain original downloads, prior mappings, finalized exports and accounting identities. Include both artifacts in backup/restore inventory.
4. Repair demonstrated recognition errors and verify upload through faithful export, including missing/ordinary/long values, rendered original comparisons and native controls. Preserve consent/signature authority and existing states.

These remain engineering work before this format can be advertised. The explicit current exception is binary `.doc`; editable `.docx` breadth remains the V1 requirement and is not reduced by this exception.

## Qualification consequence

The independently frozen new cohort contains three binary `.doc` files. With all three refused, its maximum possible document success is 17/20 (85%), below the required 18/20, even if every other document succeeds. Retain those files and refusals in its denominator. Do not replace them, call a format refusal an automatic success, or present this cohort as passed. Original 60-file evidence is likewise unchanged.

Evidence locations and hashes: `integration-evidence-20260927/legacy-doc-inspection-manifest.json`. No paid or single-use operation was repeated.
