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
and external relationships. PDF object validation rejects encrypted documents,
actions/JavaScript, XFA, attachments, external resources and active annotations.
The parser is not a substitute for future antivirus/CDR or an independent security
assessment. Synthetic tests prove actual kernel denials for file reads, network
sockets and process creation.

Run `rebuild/.venv/bin/python -m unittest documents.tests -v` from `rebuild/`
(use `.venv/bin/python` when already in that directory).
