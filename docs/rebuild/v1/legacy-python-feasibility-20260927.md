# Legacy DOC converter decision — 2026-09-27

**Reject Aspose.Words FOSS for Python 26.7.0 for faithful template conversion.**
One known development DOC and one synthetic DOCX control demonstrate silent
loss of required content. No application integration is proposed for this engine.
Binary `.doc` remains an explicit format exception. Broad editable `.docx`
compatibility remains required for V1.

## Source and package gate

The current official [DOC reader documentation](https://docs.aspose.org/words/python/developer-guide/doc-reader/)
describes a Word 97–2003 OLE2 reader. The
[DOCX writer documentation](https://docs.aspose.org/words/python/developer-guide/docx-writer/)
describes conversion through a Light Document Model and a loss-warning mechanism.
These establish available interfaces, not fidelity for this form.

The inspected official source is commit
`2d2efee2787cb9e56d071d17f8d7b740dce8b784` of
[Aspose.Words-FOSS-for-Python](https://github.com/aspose-words-foss/Aspose.Words-FOSS-for-Python/tree/2d2efee2787cb9e56d071d17f8d7b740dce8b784).
Its current code implements anchored shapes and image-less rectangles, despite
older comments describing those paths as absent. That implementation made one
bounded probe plausible. Comments were not treated as proof of either support
or failure.

The free MIT package was installed only in a new private runtime venv. Exact
pin: `aspose-words-foss==26.7.0`; official PyPI wheel SHA-256:
`bca18c134f03e15d32c247d99ec6dee97c07e565e2c9d126a9c65f0e1b29b82f`.
The four installed DOC reader/DOCX writer files inspected match the pinned
upstream source exactly. Every dependency version, wheel hash and installation
receipt is retained. Application dependencies and environments were untouched.
No commercial package, trial license, purchase or provider call was used.

## Finite execution and containment

The copied existing parser Landlock/seccomp boundary was applied before opening
either input, with no fallback: 512 MiB address space, 12 CPU seconds, 30 MiB
file size, 64 file descriptors, no core dump and a 20-second parent timeout.
Each child directly demonstrated denied network socket creation, process
creation and reading an unrelated `/etc/hostname` file. The filesystem grant
covered only that case's private workspace and Python library trees. The parent
passed a minimal environment without application secrets.

An initial user/network namespace capability probe was unavailable; conversion
used the existing enforced Landlock/seccomp mechanism instead. No root session
or new executable was required. This experiment does not qualify a production
binary-DOC admission policy: encrypted/corrupt input, macros, embedded objects,
tracked revisions and external relationships still need explicit source checks.

Exactly two executions occurred: one synthetic DOCX read/write control, followed
by one conversion of the known blank development D19 DOC. Both exited zero,
completed in under 0.2 seconds and reported no warnings. No retry, new corpus
campaign, holdout/qualification access or rendering followed the detected losses.

## D19 result and the 17 expected areas

Original: `dev/originals/D19-46f4c7cffa95.doc`, 156,672 bytes, SHA-256
`46f4c7cffa95fa64e34e51a6ced30857084b4f5b3baf3626c0be9c8a6dd8d84d`.
Its first eight bytes are `d0cf11e0a1b11ae1`. A ZIP signature at offset 116,538
does not make this OLE2 document a DOCX.

The retained normalized DOCX remains
`394eaa6eb6fc4e33ab21eac78d635cb68c6d687baeb7827fef7d58ded5814219`.
The new rejected output is
`d0b2ef8528146cbcb3c7f292d1026d211f96817291bffb1665f6738771364a8b`.
Both corpus originals were rehashed unchanged after the probe.

| Required structure | Retained normalized DOCX | Rejected Python output |
|---|---:|---:|
| Anchored drawings | 10: eight initials rectangles, two header images | 0 |
| DrawingML rectangle shapes | 8 | 0 |
| Embedded media | 2 | 0 |
| Header part | present | absent |
| Underlined runs | 7 | 0 |
| Tables / rows / cells | 1 / 8 / 24 | 7 / 14 / 30 |

Body text is equivalent only after whitespace normalization. That narrow fact
does not preserve the form: a text-only check would miss the lost branding,
initials destinations, signing bands and changed table structure.

The existing independent 17-area annotation was reused. Areas A1–A3 retain
printed inline text/blanks, with no destination or visual acceptance claimed.
A4–A11 lose all eight required initials rectangles. A12–A17 retain captions but
lose the underlined signing bands above them. The original area manifest and
all historical first-pass results remain unchanged; no new compatibility score
or automatic success is claimed. The retained normalized D19 layout also remains
unqualified under its earlier clipping/refusal evidence.

## Synthetic control and warning failure

The single synthetic DOCX contains a two-row blank table, header/footer text,
underlined signing space and an existing checked legacy form checkbox. Its
words, table dimensions and header/footer text survive, but `w:ffData` and its
checked state both disappear (one to zero). Field markers remain without the
original control data. This is a direct preservation failure even though the
writer emits no warning.

The actual pinned
[writer hook](https://github.com/aspose-words-foss/Aspose.Words-FOSS-for-Python/blob/2d2efee2787cb9e56d071d17f8d7b740dce8b784/aspose/words_foss/docx_writer/writer.py#L65)
is a no-op. Therefore an empty `DocxWriterLossyWarning` list cannot establish
that a conversion preserved content. No loss was accepted as a clinical export.

## Smallest remaining implementation path

The existing pinned Gotenberg 8.34.0 / LibreOffice 26.2.4.2 route is available,
as recorded in `legacy-doc-readiness-20260927.md`; image digest
`sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b`.
This is an engineering qualification gap, not a missing binary or root-access
dependency. No further converter or render was run in this investigation.

The smallest plausible path reuses that engine behind a separate bounded
conversion worker: explicit macro/link-update suppression, original binary
admission checks, no network/secrets/application Docker socket, immutable
original and normalized identities, and fail-closed normalized-package checks.
Its orchestration and storage linkage must preserve existing mappings, exports
and backup inventory. It still needs direct conversion evidence, all original
areas/branding/controls compared, existing D19 layout defects repaired or
honestly refused, and complete missing/ordinary/long upload-to-export checks
with rendered and native Word acceptance. Existing valid evidence should be
reused. Merely adding an upload extension is insufficient.

No evidence here authorizes widening the corpus, replacing failed files,
weakening the automatic-success denominator or deferring editable DOCX breadth.
Root has ordered no further converters or renders now; the next independent
work is the custodian-supplied frozen development failure ledger.

## Evidence and next safe action

Private runtime:
`/opt/meddoc-pro/.worktrees/v1-host-readiness/rebuild/.runtime/legacy-python-feasibility-20260927/`.
It retains exact wheels, venv, hashed requirements, receipts, official source/docs
snapshots, input/output copies, sandbox controls, scripts, structural comparison,
per-area disposition and all failures. Compact decision/source/integrity
manifests are committed beside this report. No active process remains.

This is a local rejected-engine decision, not a deployed converter or launch
claim. Next safe action: retain the explicit DOC exception and review the
authorized development DOCX failure evidence before proposing a bounded shared
repair. Keep maintenance and synthetic-only enforcement unchanged.
