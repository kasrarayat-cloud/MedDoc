# Template Twin Office compatibility QA boundary

This runbook separates the immutable delivery proof used for clinical signing
from synthetic compatibility evidence produced after an Office application
opens and saves a copy. The two results are intentionally not interchangeable.

## Immutable pre-delivery verification

The DOCX stored by QuillMD before signing remains governed by
`template-docx-readback/2.0.0`. Signing and download authorization require the
exact stored bytes and all existing proof gates, including:

- certified OOXML part, canonical structural path, binding type, ordinal, and
  native identity;
- output-derived value and occurrence evidence;
- certified binding fingerprint and static-region invariance;
- stored byte count and SHA-256;
- current SOAP version/hash and rollout-generation admission.

A moved, duplicated, substituted, missing, or altered binding fails this
contract. Office compatibility evidence must never replace, repair, or waive a
failed immutable-delivery proof.

## QA-only post-Office verification

Desktop Word and LibreOffice may rewrite ZIP ordering, part names, namespace
prefixes, paths, run structure, generated identifiers, and other serialization
details when they save a copy. A saved copy is therefore assessed only by the
synthetic QA contracts in:

- `office-docx-byte-readback.ts`;
- `office-schema-evidence.ts`; and
- `office-roundtrip-qa.ts`.

Those modules are not exported by the production DOCX index. Application
linting and architecture tests prohibit production signing, certification,
worker, correction, import, export, and download code from importing them.
Every result is branded QA-only and ineligible for a production state
transition.

The QA harness must derive field values, control state, logical occurrences,
and package security evidence from the completed Office-saved DOCX bytes. It
must cross-bind source, immutable renderer output, Office-saved DOCX, validator
logs, visible-static manifests, and PDF/page-image evidence by SHA-256. Empty,
partial, malformed, tool/version-mismatched, or hash-inconsistent evidence
fails.

Schema-validator logs and PDF/page-image measurements are **external
attestations**, not cryptographically authenticated statements. The contract
pins their tool/version and reconciles stages, targets, artifacts, counts,
matrix rows, and hashes, but a self-hash alone cannot prove that an external
tool ran. Every actual gate run must therefore preserve the raw validator
logs, PDFs, page images, exact container image digests, commands, exit codes,
and replayable hashes outside the repository for independent reproduction.
This external evidence is QA-only and has no signing or production authority.

Post-Office compatibility checks require:

1. successful open, separate save, and PDF export with no repair/corruption
   diagnostic;
2. byte-derived survival of every expected visible field value, dropdown or
   checkbox state, and occurrence count;
3. no unexpected or ambiguous field occurrence;
4. normalized clinically meaningful static text, headers, and footers;
5. unchanged page count and major page/table geometry, with any field-region
   pixel delta explicitly classified;
6. a fresh production package-security inspection with no macro, active
   content, embedded object, or external relationship; and
7. individually classified Open XML schema evidence.

For `TAB_ONLY_BLANK_TABLE_CELL_V1`, QA field readback deliberately excludes
paragraph-property tab stops (`w:pPr/w:tabs/w:tab`) from the clinical value.
Content-level `w:tab` remains visible and changes the value. This normalization
exists only in the QA-only reader after an Office save; immutable pre-delivery
output must still pass exact path, profile, fingerprint, occurrence, and static
invariance checks under production readback v2.

`ORDINARY_PLACEHOLDER_TOKEN_V1` requires a separate final-SHA corpus run. Its
pre-delivery output must pass strict binding/readback v2 at the exact certified
token span and surrounding-static-context hashes. After an Office save, the
QA-only contract may compare normalized visible replacement and surrounding
static text while recording run/path normalization, but it may not authorize
signing or reimport. The earlier tab-only LibreOffice result is not evidence
that ordinary placeholders passed; that profile remains Office-QA pending
until its synthetic corpus is opened, saved, exported, security-inspected, and
visually compared. Desktop Microsoft Word remains pending independently.

This assessment does not authorize a reimported or Office-edited clinical
document. Reimport would require a separate product and threat model.

### Narrow LibreOffice legacy-dropdown normalization

LibreOffice 25.8.7.3 may remove the cached `w:t` result of a legacy
`FORMDROPDOWN` while continuing to render the exact selected value from the
native form field. The QA reader recognizes this only as
`libreoffice_legacy_dropdown` when completed bytes prove all of the following:

- exactly one unambiguous certified legacy binding survives;
- `FORMDROPDOWN`, the complete ordered entries, selected ordinal, and selected
  value agree;
- there is no explicit conflicting result text;
- the empty result region has the exact known LibreOffice bookmark structure,
  with the expected normalized legacy name and consistent distinct IDs; and
- the pinned original/saved PDF page images are exact full-document pixel
  matches.

Metadata alone is insufficient. Deleting cached text without the exact native
presentation structure fails, and any nonidentical, tool/version-mismatched,
or hash-inconsistent visual evidence fails. This exception is QA-only: it does
not relax production readback v2, authorize signing/reimport, or constitute
Microsoft Word approval.

### Narrow LibreOffice date-control normalization

The pinned LibreOffice 25.8.7.3 round trip omits
`w:calendar="gregorian"`. WordprocessingML defines omitted `w:calendar` as
Gregorian, so the QA reader normalizes only that exact omission and records
`calendar_omitted_defaults_gregorian`. An explicit non-Gregorian value such as
`hijri` remains a behavior change and fails.

Normative behavior reference: Microsoft Open XML SDK documentation for
[`w:calendar`](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.calendar?view=openxml-3.0.1).

LibreOffice also omits `w:storeMappedDataAs="dateTime"`. That setting controls
storage only for a data-bound control. Safe-alpha rejects custom XML, and the
reader requires no `w:dataBinding`, so explicit or omitted storage format is
normalized to `not_applicable_unbound` and recorded as
`store_mapped_data_as_not_applicable_unbound`. Any bound control, custom XML
part, duplicate behavior element, or conflicting calendar still fails. These
normalizations are QA-only and do not relax strict production readback v2.

Behavior reference: Microsoft Word documents date storage as applying when a
date content control is
[`bound to the XML data store`](https://learn.microsoft.com/en-us/office/vba/api/word.contentcontrol.datestorageformat).

## Open XML schema policy

Every synthetic source and every immutable QuillMD renderer output must have
zero Open XML schema errors for each declared target. No allowlist can turn a
source or renderer error into a pass.

The independent stage matrix is
`docs/qa/template-twin-office-schema-error-matrix.json`. It records that the
current schema-valid corpus and renderer outputs have zero errors, while
LibreOffice 25.8.7.3 introduces 42 errors during save:

- 20 font-character-set extension values;
- 19 logical-alignment enumeration values; and
- 3 table-row on/off lexical values.

The QA schema contract recognizes only those exact reviewed LibreOffice-stage
patterns under its versioned registry. They remain
`external_tool_pending_word`: the files are not declared schema-valid, the
errors are never accepted for signing or reimport, and desktop Microsoft Word
evidence remains mandatory. An unknown diagnostic, tool/version, part,
element, attribute, value, target, or unreviewed classification fails closed.

## Isolated execution

Use only synthetic DOCX and clinical data. Office and PDF containers must run
with `--network none`, isolated user profiles, non-root file ownership where
supported, and separate source/output paths. Never overwrite an original
corpus document. Record exact image digests, application versions, commands,
exit codes, stdout/stderr, warnings, artifact hashes, sizes, and schema
validator versions.

The Windows Word package may automate local COM open/save/PDF operations, but
repair dialogs and visual/layout correctness still require a human observer.
LibreOffice evidence is not Microsoft Word evidence. Until returned desktop
Word results pass, Word status remains **PENDING** and no structure is
Word-approved or production-ready.
