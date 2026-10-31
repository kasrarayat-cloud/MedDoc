# Document adapter contract

The application calls `from documents import inspect_template, fill_template,
DocumentError`. Both public operations launch an isolated, disposable Python
subprocess. The original is copied into a private temporary directory, read by
the child, and never edited. Callers authorize every original/export before
passing opaque server-generated paths. Never accept a filesystem path from a
browser.

```python
inspection = inspect_template(original_path)
# Persist inspection['fields'] as a new immutable mapping version and
# inspection['sha256'] alongside the immutable original.
summary = fill_template(original_path, inspection['fields'], answers, new_path)
```

`answers` is `{field_key: plain_text}`. Inspection returns `format`, `fields`,
`warnings`, `adapter`, `sandbox`, and `sha256`. Each field has `key`, `label`,
`kind: 'text'`, and an opaque `locator`; PDF fields additionally have `capacity`
and `max_length`. Keys are stable for a given original. Keep field dictionaries
unchanged: fill re-inspects and compares the entire snapshot, rejecting stale
or altered mappings. Editable clinical labels should be separate application
metadata. A new original requires a new inspection and mapping version.

Fill additionally returns `filled`, `missing`, and `output_sha256`. Unknown
answer keys are errors. Omitted/empty answers stay blank and are named in
`missing`. It is the application's responsibility to require explicit clinical
review of missing/conflicting information before finalization. The adapter never
generates an answer, judges evidence, bills, or authorizes a clinical action.

`DocumentError` exposes a safe message and `code`. Unsupported formats and
unsafe documents fail closed. No export is created for overflow. An existing
output is never replaced; original-path exports are prohibited. Export files
are created mode 0600 with exclusive creation. Symlink source files are refused.

## Supported real operations

* DOCX `{{Question name}}` placeholders in body paragraphs, tables, headers and
  footers, including placeholders split across multiple styled runs.
* DOCX two-column tables with a question in the first cell and a blank second
  cell. Nested/merged row boundaries are not inferred.
* DOCX labelled underlined answer tabs when no older placeholder/table mapping
  applies. A single-underlined tab-only run is an answer area; ordinary tabs,
  paragraph borders and underlined text are not. Inline pairs require separate
  labels and a separating tab. Blank continuation paragraphs require an adjacent
  real heading; numbered answers retain that section's context. Orphan/ambiguous
  areas and positioned paragraphs are refused, not partially mapped.
* PDF AcroForm text fields using an explicit Helvetica font size and printable
  ASCII. Text width and height are checked using ReportLab font metrics for
  every visible widget. Explicit newlines are supported in multiline fields.
  Automatic wrapping is deliberately not relied on: a too-wide line is rejected.

The adapters are established `python-docx` and `pypdf`; ReportLab provides PDF
font metrics and synthetic fixtures. They are real local integrations, not
mocked document generation. DOCX insertion retains other text, styles, layout
settings and questions. Text expansion can change pagination; visual review is
required. PDF fields retain questions/page content and receive regenerated
appearances, but remain form fields; no archival signature or PDF/A claim is made.

The underlined-tab v1 locator binds the complete original SHA256, package part,
paragraph, run and child positions. Logical questions retain their physical
answer anchors separately. Explicit answer lines occupy existing continuation
areas; surplus lines expand the last area, and unused areas remain blank. Long
paired answers separate at the existing separator into flowing lines. Exact line
spacing becomes minimum spacing and paragraph keeping is relaxed for pagination;
font, size, underlining, labels, tab stops and section setup stay intact. Answer
ink is black. Only changed story XML is serialized; other package-part bytes are
copied unchanged. Pagination may grow and is not fixed-layout Word parity.

The supplied blank colonoscopy fixture has 24 logical fields and 28 physical
answer tabs, with five excluded separators. Consent and procedure continuation
lines are grouped and flagged for mapping review. The mapping page surfaces these
review notes, and this adapter exposes manual answer entry before AI generation.
No clinical statement, date or signature is supplied by the adapter. Recognized
signer fields are never generated from notes; a nonblank value requires the
actual finalizer's identity and that clinician's own explicit field review.

## Explicit unsupported cases

Flat/scanned PDFs, OCR, automatic detection of arbitrary answer boxes, Word
content controls/legacy fields/text boxes/tracked changes, fixed-height Word
answer rows, PDF checkboxes/dropdowns/signatures/rich text, PDF Unicode/custom
fonts/automatic font sizes/rotated fields, document-to-PDF conversion, and exact
rendered pagination require an advanced SDK adapter and visual qualification.
They fail with a specific error rather than producing a partial claim of success.
Malformed placeholders also fail. Existing visible questions are treated as
untrusted data; application AI must never follow embedded instructions.

## Isolation and limits

Linux Landlock ABI >=3 is mandatory. Filesystem access is restricted to the
disposable job directory and read-only Python runtime/library directories.
`libseccomp.so.2` denies network sockets, process creation/exec, ptrace/process
inspection, signal delivery, namespaces/mounts, keyring and io_uring operations.
The worker inherits no provider credentials or application environment, receives
no DB connection, and has a 20-second wall timeout, 12 CPU seconds, 512 MiB
address-space ceiling, 30 MiB file ceiling, and 64 open file descriptors.

Input: 10 MiB maximum; DOCX: 1,000 package parts, 50 MiB total expanded size,
20 MiB per part and 250x compression ratio; PDF: 100 pages; all templates:
200 fields; answers: 100,000 characters each and 2 MiB request total. These are
explicit processing limits, never silent truncation.

DOCX validation rejects path traversal, duplicate ZIP entries, symlinks, encrypted
ZIP parts, excessive expansion, DTD/entities, macros, active/embedded content
and external relationships. PDF validation rejects encrypted documents,
actions/JavaScript, XFA, attachments, external resources and active annotations
in two independent layers: `pdf_raw.py` scans the file's exact bytes without any
PDF parser (every revision, every dictionary, hidden objects and every decoded
object stream; anything it cannot read completely is refused as `unreadable_pdf`),
then pypdf reads the same bytes and its walk, a single-catalog rule and its own
recovery reports form the second layer. Both run on upload, on every fill, and
before a stored PDF original is downloaded (`check_original`); see
`docs/rebuild/security-readiness.md` for what this does and does not guarantee.
The parser is not a substitute for future antivirus/CDR or an independent security
assessment. Synthetic tests prove actual kernel denials for file reads, network
sockets and process creation.

Run `rebuild/.venv/bin/python -m unittest documents.tests -v` from `rebuild/`
(use `.venv/bin/python` when already in that directory).
