# Finding P1 — repaired 2026-10-31 (not yet installed): active content hidden from the PDF upload check

**What was wrong.** `pdf_inspect` refused scripts and actions by walking what
pypdf resolves from the trailer. pypdf drops a cross-reference section it cannot
read (even with `strict=True`), re-locates objects by regex taking the first
match, adopts another catalog when the trailer's /Root is not one, and never reads
stream data. On the base `4ebba7732`, 21 hand-built shapes carrying a harmless
script or attachment were accepted as supported templates on pypdf 6.21.1, 6.21.2
and 6.21.4, and `template_original` served such an original back byte for byte.
The reproduction and the triggers: [pypdf 6.21.4 in the rebuild](pypdf-6.21.4.md).

**What the check guarantees now.**

- **A raw scan of the exact bytes is the guarantee** (`documents/pdf_raw.py`). It
  runs on every PDF the worker reads (upload inspection, every fill, and the new
  download check) before pypdf reads the same bytes, and asks no PDF parser what
  the document is. It tokenizes the whole file and applies the policy to every
  dictionary in every revision, in unreferenced objects and trailers, before the
  header and after %%EOF; parses one object at every `obj` and `trailer` keyword
  the sequential pass did not read as syntax (in a comment, a string or another
  stream's data, glued header numbers included); decodes every object stream
  (Flate, LZW, ASCII85, ASCIIHex, RunLength, PNG/TIFF predictors, chains,
  indirect parameters from every definition in the file, pdf.js's /F and /DP
  aliases); and a byte-pattern pass refuses the long forbidden names in any
  spelling and the short ones wherever they are shaped like a key. The policy is
  the engine's (forbidden keys, /Type /EmbeddedFile, the active annotation
  subtypes) plus action types named by /S, and /Encrypt as a key anywhere. Where
  readers disagree, every reading is judged: every value of a duplicated key;
  every name in a malformed object (a value where a key belongs, a key without
  its value, a keyword or an `R` that no reader takes as a value, a broken number
  or string), at any depth, because a lenient reader re-pairs what follows the
  error; and every policy name standing outside every container, because a
  reader that skips junk up to the next whitespace runs a dictionary past its end.
- **What it cannot read completely is refused**, never passed: an object stream
  it cannot decode (unknown or crypt filter, corrupt data, parameters it cannot
  resolve, that are defined ambiguously or twice, or that come from a malformed
  dictionary); any stream object malformed anywhere, and any dictionary followed
  by `stream` that the scan did not read as a stream's start, because which
  entries a reader keeps there cannot be known (pdf.js and PDFium skip a `[`,
  `<<` or `(` where a key belongs, where the scan opens a container); and anything
  past its bounds (64 MiB decoded, one work budget, nesting, hidden objects,
  definitions). Code `unreadable_pdf`: "This PDF could not be read completely, so
  it cannot be checked for active content. Save it as a new PDF and upload it
  again."
- **A second, independent layer:** pypdf's walk (unchanged), a refusal when
  `reader.root_object` is not the trailer's /Root (pages, fields and
  `PdfWriter.append` read the former, the walk the latter), and a refusal when
  pypdf logs a recovery that drops or replaces structure: 27 templates read from
  the source of 6.21.1, 6.21.2 and 6.21.4. Eleven test fixtures without active
  content each make all three versions log their own template, 15 of the 27 in
  all; the other 12 are logged only with `strict=False`, just before a strict-mode
  exception, or inside a rebuild of object streams, and are kept so that a change
  of mode cannot open them. The worker used to discard that log.
- **Download:** a PDF original is checked in the worker (raw scan, pypdf walk,
  single catalog, pypdf's recovery reports, annotation subtypes; no field or
  capacity rule) before it is served. A refusal sends no byte, answers 409 with
  the reason, and records `template.download_refused` with the code. A served original is typed from
  `Template.format` (`application/pdf` or the DOCX type, never guessed from the
  client's name), sent as an attachment with `X-Content-Type-Options: nosniff`,
  and a stored name whose suffix was cut off gets the format's suffix. DOCX
  originals are not re-inspected.
- **Fill:** the export is written by pypdf from the reader built on the scanned
  bytes (read once), and the single-catalog rule keeps `PdfWriter.append` on the
  catalog the walk checked. A test scans a real export with the raw scan.
- **Stored originals:** `manage.py check_pdf_originals --output <new file>`
  reports, read-only (a read-only transaction, no audit row), how many stored PDF
  originals the download gate would refuse, with template ids and codes only.

**What it does not guarantee.**

- It refuses the listed active content; it does not render, and it does not
  examine fonts, images or content streams for parser exploits.
- Ordinary stream data (content streams, fonts, images) is not read as syntax.
  An object hidden there is read from its own `obj` or `trailer` keyword; a reader
  that parsed objects there without that keyword is not covered, and the
  byte-pattern pass skips ordinary stream data (measured: no ordinary file has a
  forbidden name there, but the corpus has few uncompressed content streams).
- The byte-pattern pass treats short keys (/A /AA /JS /EF /URI /XFA /Encrypt)
  only where shaped like a key. A reader whose tokenizer departs from the PDF
  syntax so as to hide a short key from the scan's parse AND leave it unshaped is
  not covered. Differential fuzzing against lenient pypdf and against pdf.js
  (details below) found nine files that a reader read differently from the scan,
  each now covered; it is a sample, not a proof.
- Lenient pypdf skips an unreadable token up to the next whitespace, so junk glued
  to `>>` runs a dictionary past its end. The scan covers what fuzzing found that
  to reach (standalone names after it; a malformed stream object is refused
  outright), not the habit in general: when the next object's header is glued to
  its dictionary (`obj<<`), such a reader can shift that object's key/value
  pairing, and that is not covered. pdf.js and PDFium end a token at a delimiter
  and do not read this way.
- Encryption is refused, not decrypted.
- A template list only knows the pypdf versions it was read from; the raw scan is
  what covers an unknown recovery's content.
- Nothing live changes until an install, and no installer changes the live venv:
  production runs pypdf 6.21.1 from `/opt/meddoc-pro/rebuild/.venv` (see
  [pypdf 6.21.4](pypdf-6.21.4.md)). The repair is proved on 6.21.1, 6.21.2 and
  6.21.4; `pdf_raw` uses only the standard library.
- Stored originals are not rewritten (the database forbids it). An existing PDF
  template the new check refuses can no longer be downloaded or filled: finalizing
  an encounter that uses it fails with the refusal. How many live templates that
  affects is unknown until `check_pdf_originals` runs against the live database.

**Measured** (2026-10-31, code `2dcff8790` against base `4ebba7732`, through the
real sandboxed worker run with each version's interpreter; corpus of 133 files
from 13 producer families, built offline and kept outside the repository; every
verdict and download-check result is the same as on `095387ecd`):

| | pypdf 6.21.1 | 6.21.2 | 6.21.4 |
|---|---|---|---|
| ordinary corpus: verdict changes | 6 | 6 | 6 |
| supported files still filled, byte-identical old vs new | 34 of 34 | 34 of 34 | 34 of 34 |
| the four known P1 trigger files (accepted by the base) | refused | refused | refused |
| 21 hidden-content test shapes (all accepted by the base) | refused | refused | refused |
| 11 recovery shapes without active content | `unreadable_pdf` | `unreadable_pdf` | `unreadable_pdf` |

- **The six changed files, all refused as `unreadable_pdf` by the second layer
  while the raw scan finds nothing in them,** are pypdf's own incremental writer
  with two or three increments over a ReportLab form. Reading the older
  cross-reference stream, strict pypdf raises "Overwriting cache for 0 13" (both
  increments number their stream 13), logs "Previous trailer cannot be read",
  drops that section and the base table, and re-locates four objects by first
  match: it then reads the base revision's AcroForm, without the
  `/NeedAppearances false` the first increment added. So pypdf's view really
  differs from the file, but no active content is involved; the refusal protects
  what pypdf reads, not against a script. It is kept as designed and reported;
  accepting these files would mean exporting from pypdf's stale view.
- **Worst case** on 26 adversarial and large inputs of at most 10 MiB, three of
  them aimed at the checks added last, against the worker's 12 s of CPU and
  512 MiB: no single sample above 2.81 s and 179 MiB, measured while the host ran
  at load 7 to 15 (the base code took 3.20 s on one of the same files in the same
  run); 24 repeats of the four slowest inputs took 1.49 to 2.38 s. The raw scan
  alone peaks at about 1.6 s in-process on a quieter host; the ordinary corpus
  uses at most 3,519 of its 1,000,000 work units.
  *(⚠️ Corrected 2026-11-01: this bound was refuted. An independent cost
  refutation of the code at this point drove the raw scan past the 12 s worker
  CPU with ~10 KB–384 KB files — the work budget did not bound several C-level
  regex and allocation paths — and the fixed 1,000,000-unit budget refused a
  benign 5.9 MiB object graph. Both are repaired below as COST-1 and COST-2; the
  numbers in this paragraph describe the code before that repair.)*
- **Fuzzing.** A mutated corpus file that the raw scan passes goes to two
  oracles: lenient pypdf (6.21.1 and 6.21.4), which reads the most, and pdf.js
  4.10.38, a real viewer's parser; either finding a forbidden key, an action, an
  attachment or an active annotation is a miss. Across the repair they found nine
  files: three before `095387ecd`, and six that `095387ecd` passed, the last two
  of which `fb1f259a1` passed too. pdf.js confirmed three of the nine as
  real-viewer bypasses, all object streams whose dictionary held junk
  (`/Length 29 0 o`, a `[` before `/Length`, `29 0[ R`): pdf.js read a link with
  a URI action from data the scan had not decoded. The other six are lenient-pypdf
  re-pairings in which pdf.js showed nothing (it opened five of them); one of
  them, an `R` that ends no reference, PDFium's parser source reads the same way
  (PDFium was not run). All nine are refused and kept as minimal tests. On the final code, 100,000
  mutations ended only in verdicts; 500,000 mutations, 132,442 of them passing
  the raw scan, gave lenient pypdf no miss; and pdf.js found nothing in 63,797
  mutations passing the raw scan, nor in the 98 ordinary corpus files it passes.
- **Tests:** `documents.test_pdf_active_content` (on CI's explicit list) and
  `core.tests.test_template_original_safety` build every fixture in memory; both
  pass on 6.21.1, 6.21.2 and 6.21.4.

## Round 2 — 2026-11-01: cost repair (COST-1, COST-2), the download-path gates (DL-1, DL-2), two accepted limits (F1, F2)

An independent refutation of the round-1 code found four things. Two were cost
(denial-of-service and false-rejection; the scan already failed closed, so no
active content was ever let through), and two were missing gates on stored
artifacts. Two more were ordinary-file verdict edges that are **accepted, not
widened** (F1, F2). All are measured through the real sandboxed worker on pypdf
6.21.1, 6.21.2 and 6.21.4.

**COST-1 (repaired).** Several paths in `pdf_raw.py` were super-linear while the
work budget charged them one or two units, so crafted files of 10 KB–384 KB —
all accepted by the base in ~0.3 s — drove the scan past the worker's 12 s CPU
and were SIGKILLed to `parser_failed`. Each is now linear and charged by the
bytes it crosses: the number-token regex is possessive (`_NUMBER_BODY`); gap
crossing (`_gap_end`) memoizes the end of a comment line so it is found once, not
once per name; `_unread_streams` crosses the comment run after each `>>` once;
`_predict` sizes its rows and masks by the data, never by a declared `/Columns`
(so a 64 MiB row width for one byte of data costs nothing); `_scan_content`
parses each object-stream offset once; `_define` recognises an already-read
summary by identity; and `_object_streams`, `_anchors`, `_variants` and
`_decode` charge every pass by the work it does. Measured on the lens's inputs
and doubled copies up to ~10 MiB, through the real worker (6.21.4), all well
inside 12 s and never killed:

| input (≈size) | before (round-1) | after |
|---|---|---|
| `num_token` 64 KB … 9 MiB | 12 s → killed | supported, 0.00–0.43 s CPU |
| `array_junk` 32 KB … 9 MiB | 12 s → killed | `unreadable_pdf` (malformed stream), ≤0.5 s |
| `stream_start` 100 KB … 9.5 MiB | 12 s → killed | supported, 0.02–2.54 s |
| `predict_objstm` 10 KB … 0.4 MiB | 12 s → killed | supported, ≤0.45 s |
| `gap_comment` 124 KB … 8.6 MiB | 12 s → killed | pass ≤0.2 s; the 8.6 MiB (3 M names) refused `unreadable_pdf` at 5.3 s |
| `gap_anchors` 384 KB … 9 MiB | 12 s → killed | pass ≤0.15 s; the 9 MiB (250 k anchors) refused `unreadable_pdf` at 0.5 s |
| `objstm_index` 12 KB … 65 KB | 12 s → killed | pass ≤0.13 s; the 60 MiB-of-spaces variant refused at 1.2 s |

The work budget now **grows with the file** — `budget() = MAX_WORK (1,000,000) +
size/4` — so a 10 MiB file has ~3.6 M units (about 3.5 s of CPU on this host) and
a crafted file is still bounded and refused, never killed. Over the 133-file
ordinary corpus the most any file now uses is **3,649** units, and every one of
the 133 keeps the exact verdict it had before this repair (raw scan and worker).

**COST-2 (repaired).** The old fixed 1,000,000-unit budget refused a benign
large structured file before the policy ran: a 5.9 MiB graph of ~97,000 small
objects was `unreadable_pdf` (work ≈ 1,002,822). With the growing budget it now
passes the raw scan (work ≈ 1,148,000 of a ~2.5 M budget) and reaches the real
policy — the pypdf walk refuses it `upload_limit` for object-graph size, exactly
as the base does. A plain 9.3 MiB text PDF passes the raw scan at 0.86 s (work
607,362) and is refused only for its 9,000-page count, as before. So ordinary
large files up to the 10 MiB upload limit are no longer refused by the budget;
measured on text PDFs and object graphs from several producers.

**DL-1 (repaired, defence in depth).** A stored PDF **export** was served after a
`sha256` check only (`core/views.py` `export`). New exports are built from
originals the gate re-checks, but an export finalized **before** the P1 repair
could carry a script pypdf's root recovery copied out of an unsafe original into
a page-level form every viewer reads. The `export` view now runs the same
isolated-worker active-content check on the stored export bytes before serving a
PDF export; a refusal sends no byte, answers 409 with the reason, and audits
`encounter.export_refused` with the code. DOCX exports are not re-checked (same
as DOCX originals). **The live rebuild has no PDF templates today**, so no PDF
export exists to refuse; this closes the path for any PDF export written before
the repair. The only route that serves a stored PDF export is `export`; the
coding and coding-draft exports are DOCX-only and build a new document.
*(⚠️ Superseded 2026-11-01, round 3 — SI-1 and SI-2: scanning the export bytes
refused a clean form's export that was larger than the check's 10 MiB input limit,
or whose answer held the word "trailer" and a later "/Launch", after finalize, when
the document could no longer change. The gate now checks the export's template
original instead; see "Round 3" below. This paragraph describes the round-2 code.)*

**DL-2 (repaired).** A PDF template whose stored original the gate now refuses
was still selectable: a doctor could create an encounter on it and spend a paid
generation, learning only at finalize that it can never produce a document.
`core.template_source.assert_pdf_template_usable` runs the same check on the
stored original at the two earliest points — encounter creation
(`encounter_new`) and every provider enqueue (`jobs.enqueue`, the one choke point
for generation and transcription) — and refuses with a clear message before any
provider usage. DOCX originals are validated by `source_for_version` as before;
a missing or changed original is left to the step that reads it.
*(⚠️ Corrected 2026-11-01, round 3: "every provider enqueue" was not true — saving
the answers queued a coding run with no check (SI-3), now gated together with the
semantic recheck; and a worker failure of the check was reported as this permanent
refusal and deleted an uploaded recording (SI-4), now "try again" with the recording
kept. See "Round 3" below.)*
*(⚠️ Superseded again 2026-11-01, round 4: `jobs.enqueue` no longer runs the guard.
The generate request does, and the worker runs it immediately before every provider
call; see "Round 4" below.)*

**F1 (accepted limit, not widened).** The second layer refuses any file whose
read makes strict pypdf drop or replace structure. This is **wider than round 1
documented**: the affected set is not only "pypdf's own incremental writer with
two or three increments" — it includes a form saved once by pypdf's incremental
writer and **then by pdf.js** (the engine behind Firefox's built-in viewer).
pypdf's incremental writer numbers its xref stream `len(_objects)+1` and omits it
from its own `/Index`; pdf.js then reuses that number, so strict pypdf raises
`Overwriting cache for 0 <n>` on the older stream, logs `Previous trailer cannot
be read`, and drops a revision. The raw scan finds no active content, pdf.js and
MuPDF read the file without repair, and an export pypdf would build matches a
correct re-save — so the refusal prevents nothing, but the file is refused as
`unreadable_pdf` at inspect, fill and download on all three pypdf versions.
⚠️ **The MIRROR order is accepted:** the same two writers in the other order
(pdf.js then pypdf) gives the reused number to a new appearance stream, and strict
pypdf silently returns its own xref stream as the widget's `/AP /N` and accepts,
fills and serves the file. That is safe **because the raw scan judges every
definition of every object regardless of what pypdf resolves** — the
active-content guarantee does not depend on pypdf's view. The rule follows
pdf.js's allocation order, not whether pypdf's view is wrong; it is kept, because
accepting the first order would mean exporting from pypdf's stale view. Only
pdf.js 4.10.38 in node was exercised, not Firefox itself.

**F2 (accepted limit, not widened).** The byte-pattern pass refuses a long
forbidden name anywhere outside ordinary stream data, strings and comments
included. So a well-formed literal string that contains a long policy name right
after a slash — e.g. `/Keywords (intake, pre/Launch checklist)`, a `/Subject`
URL containing `/JavaScript`, or a field `/V (Enable JS via /JavaScript)` — is
refused `unsafe_upload`, although no reader takes a name from a well-formed
string. The same words pass when the producer escapes the next byte (ReportLab
writes `\)` after a name, and a backslash is a regular byte, so the match is
decided by an escape, not by meaning). This is by design — a reader that runs a
dictionary past its end can take such bytes for entries — and it is kept rather
than narrowed: for medical templates the eight long names are CamelCase PDF words
and only `Launch` and `JavaScript` are plausible in ordinary text. Measured: the
three string variants refused on 6.21.1 and 6.21.4; the comma control and an
escaped tooltip pass.
*(⚠️ Round 4, GR-4: since SI-1 and SI-2 a stored PDF export is judged by its form's
original, so the download of an export filled from a form this byte pass refuses is
refused as well, although the export itself carries no such name. See "Round 4"
below.)*

**Round-2 proof.** `documents.test_pdf_active_content` adds `ScanCost` (each
COST-1 shape scanned in a CPU-capped fork; a regression is killed by the cap and
fails) and budget-growth and linearity assertions; `core.tests.
test_template_original_safety` adds the DL-1 export gate and the DL-2
encounter/enqueue gates. One killing mutation per new cost guard was verified on
a throwaway copy (reverting each guard makes its shape blow the cap or regress to
a refusal, and the copy restores to a pristine sha). A short pdf.js-oracle fuzz
campaign on the final `pdf_raw.py` found no miss. All on 6.21.1, 6.21.2, 6.21.4.

## Round 3 — 2026-11-01: the export gate redesigned (SI-1, SI-2), every provider path gated (SI-3), a worker failure is not a verdict (SI-4), two raw-scan edges (DELTA-1, COV-RENDITION)

An independent audit of round 2 found four defects in the gates and two edges in
the raw scan. Each was reproduced first, on `43bf5bd4e`, through the real views and
the real sandboxed worker (or, for the scan, against the round-1 code), then
repaired. No active-content refusal was weakened: the export bytes are no longer
scanned, but the only input of an export the doctor did not write — its form's
original — gets exactly the check its own download gets.

**SI-1 and SI-2 (repaired; the DL-1 export gate redesigned).** Round 2 ran the
hostile-input raw scan over the stored export. An export holds the doctor's own
words, and finalize writes exports of up to 30 MiB while the check reads at most
10 MiB. Reproduced: a 10,534,558-byte export of a clean four-field form finalized
and was then refused `upload_limit`, and the answer "Seen with trailer hitch
injury; plan /Launch" (pypdf writes answers verbatim into uncompressed appearance
streams, where the word "trailer" opens a hidden range for the byte-pattern pass)
made a clean form's export refused `unsafe_upload` — both after finalize, when
nothing could change the document any more. The `export` view now runs
`check_original` on the export's **template original** (the same check the
original download runs) and refuses the export — 409, no byte, audited
`encounter.export_refused` with the code — when the original is refused. DL-1's
case, an export filled before the P1 repair from an original the repair refuses,
is refused as before; a PDF template has no prepared source (preparation is
Word-only), so the original is the file every PDF export was filled from, and an
answer cannot add an object or an action to the file pypdf writes. A missing or
changed original refuses the export (409, "cannot be checked"); a check that could
not run refuses it as 503 "try again". Finalize is unchanged; DOCX exports are
served as before.

**SI-3 (repaired).** "Every provider enqueue" was not true: saving the answers of
an encounter whose PDF form the gate refuses queued a coding run automatically, and
the coding worker called the provider once (reproduced, provider mocked as the
coding tests mock it), while generation on the same encounter said nothing was
sent. `coding_service.ensure_run` now runs `assert_pdf_template_usable` before it
queues a run (after a save, on request, after a context change), and so does the
semantic recheck's enqueue (Word-only today, so a no-op). Every path that can buy a
provider call for an encounter now goes through the guard. Not covered, and
recorded: a job or coding run queued **before** the deploy still runs (the workers
do not re-check), which only matters in the deploy window.
*(⚠️ Superseded 2026-11-01, round 4: `ensure_run` and the recheck's enqueue no
longer run the guard. The coding worker and the recheck's worker path run it
immediately before the provider call, which also covers a run queued before the
deploy. See "Round 4" below.)*

**SI-4 (repaired).** Every `DocumentError` of the check became the permanent "This
form can no longer be used … Upload a clean PDF as a new form", worker failures
included; reproduced with only the check timing out on a clean form, the voice
route deleted the doctor's uploaded recording. `core.template_source` now raises
`PdfTemplateRefused` for a verdict about the file (`unsafe_upload`,
`unreadable_pdf`, `invalid_document`, `upload_limit`, `unsupported_format`) and
`PdfTemplateCheckUnavailable` when the check could not run (`parser_timeout`,
`parser_failed`, `sandbox_unavailable`, or the stored file changing between two
reads). Both still send and serve nothing. A check that could not run says "QuillMD
could not check this form right now … try again" — 503 on both downloads and the
JSON generate request; on encounter creation (the form keeps everything entered)
and on the kept-recording page 409, like every refusal page the doctor continues
from, because Django saves no session on a 5xx and the session would not be
extended — and never discards input: on the voice and over-limit-approval routes
the uploaded recording is **kept** and a page offers to send the same recording
again or discard it (`voice_retry`). The offer is signed and bound to the user,
encounter, revision and recording sha; it ends 30 minutes after the first offer
even when a retry renews the page, so its signed quote is never older than an
over-limit approval's; the worker removes a kept recording nobody sends after the
window, exactly like an unapproved over-limit upload, and never while a newer offer
still holds it. A refused form still removes the upload and says "can no longer be
used".
*(⚠️ Superseded in part 2026-11-01, round 4: the kept-recording retry flow —
`voice_retry`, its page, the signed offers, the reaper's kept-recording rules — is
removed, and so is the refused form's removal of the upload. The voice upload and
the over-limit approval run no form check, as before P1; the worker fails the job
unsent instead and the recording stays that job's input. The verdict / "try again"
split and its answers on the other routes stand. See "Round 4" below.)*

**DELTA-1 (repaired).** Round 2's one-pass `_unread_streams` also tested each `>>`
inside the comments of a run that ends at a stream the scan had read, and refused
`<< … >>⏎% >> stream⏎stream` as "a stream whose dictionary could not be read".
Round 1's non-overlapping search never restarted inside a match, and accepted these.
That rule is kept exactly: a `>>` inside a run ending at a read stream is skipped,
and inside any other run it is still tested (a commented `>> stream` after a
dictionary that starts no read stream is refused, as in both earlier rounds). The
audit's 18 inputs go back to round 1's verdict — accepted by the raw scan, shipped
and with the budgets lifted, and through the real worker identical to the round-1
tree (16 `invalid_document`, 2 `unsupported_format`) on 6.21.1 and 6.21.4. A
differential check of the stream-start rule alone over 2.4 million random inputs
and stream-start sets found it identical to round 1's every time (round 2 differed
in 333, always by refusing more). The pass stays linear.

**COV-RENDITION (repaired, defence in depth).** `/Rendition`, `/Movie` and
`/Sound` are now action types: an unreferenced `<< /S /Rendition >>` was accepted
while MuPDF reports it as an action. It was not exploitable — every trigger that
could reach it is refused on its own — but this module refuses an action dictionary
wherever it is. `/GoTo`, `/SetOCGState`, `/Trans` and `/Transparency` stay
accepted.

**Measured** (through the real sandboxed worker, inspect and download check, on
pypdf 6.21.1, 6.21.2 and 6.21.4):

| | 6.21.1 | 6.21.2 | 6.21.4 |
|---|---|---|---|
| ordinary corpus (133): verdicts changed vs round 2 | 0 | 0 | 0 |
| ordinary corpus: changed vs base `4ebba7732` | the documented 6 | the documented 6 | the documented 6 |
| 18 independent bypass fixtures (of 39) | refused | refused | refused |
| the audit's coverage variants a viewer reaches (58 of 90) | refused | refused | refused |
| orphan `/S /Rendition`, `/Movie`, `/Sound` | refused (was supported) | refused | refused |

**Round-3 proof.** `documents.test_pdf_active_content` adds the orphan action
types (raw scan and real worker) and the commented-`>> stream` cases, with the two
refusals that must stay; `core.tests.test_template_original_safety` rewrites the
export-gate tests and adds the coding, recheck, worker-failure and kept-recording
tests (35 in all, the trailer answer through the real upload-to-export path). Every
new test fails on `43bf5bd4e` except its controls (a clean form's coding run is
queued; encounter creation and generation stay refused; a refused form still
removes the upload). One killing mutation per new guard — 15, each applied and
restored to a pristine sha on a throwaway clone of the final code — including
round 2's own shape for the export gate (scan the export again) and for
`_unread_streams` (test every commented `>>`), a widened skip (skip every commented
`>>`) which the tests refuse as reopening, and the kept-recording page answering
503 again. The first mutation run found one new test passing vacuously (it
iterated the code's own list of worker-failure codes, which the mutation emptied),
and running the new tests against `43bf5bd4e` found the recheck test accepting the
recheck's own later refusal; both now fail on their own. The documents list (211
tests) and the P1 core modules (271 tests, with the recording-limit, audio, coding
and semantic recheck modules) pass on 6.21.1, 6.21.2 and 6.21.4.

**Not covered, and recorded.** A generation, transcription or coding run queued
before the deploy still runs: the workers do not re-check the form (deploy window
only). A refused or unavailable template use writes no audit row except where the
route already audits (downloads, the kept recording, the automatic coding enqueue's
`coding.enqueue_failed`). `check_pdf_originals` counts originals; an export is
refused exactly when its original is, so that count bounds the exports affected.
A 503 download refusal does not extend the session (Django saves no session on a
5xx); the pages a doctor acts from answer 409 for that reason.
*(⚠️ Round 4: the first sentence no longer holds — the workers check the form before
every provider call — and the kept recording and `coding.enqueue_failed` audit rows
for a refused form are gone with the paths that wrote them.)*

## Round 4 — 2026-11-01: provider usage gated in the worker, the retry flow removed, a check that cannot start (GR-1), the F2 export case recorded (GR-4)

A final review of round 3 — one lens on the new gates and the retry flow, one on the
raw scan, which found nothing — reported one major finding (GR-1) and three minor
ones (GR-2, GR-3, GR-4). GR-1 was reproduced first, on `8ab57b30c`, through the
lens's own probe. This round also carries the integrator's binding simplification,
which removes the surface three of the four findings were in.

**The simplification: the form guard moved to the workers, and the retry flow is
gone.** Round 3 checked a PDF form at enqueue. A check that could not run there met
the recording the doctor had just dictated, so round 3 kept it and offered it again:
a `voice_retry` route and page, signed retry offers, `recording_kept`, and reaper
rules for kept recordings — new surface for a case the live rebuild cannot reach
(it has no PDF templates), and where GR-1's voice arm, GR-2 and GR-3 were found. All
of it is removed: `voice`, `voice_approve`, the reaper and `urls.py` are
byte-identical to the base again, so the voice upload and the over-limit approval
run no form check, as before P1, and a dictated recording can no longer be lost to
the check. Instead `core.template_source.provider_refusal` runs in the worker,
immediately before every provider call for an encounter:

| provider path | where the guard runs | refused, or the check could not run |
|---|---|---|
| generation, transcription | `core.jobs.run_one`, the first statement of the provider path: before testing admission, the provider slot, a recording's payload preparation and the call | fails as not processed (`NoProviderRequest`): "Not processed: ‹sentence› No provider request was made; nothing was charged and the held funds were released." The hold is released in the same transaction; a recording stays the job's input |
| semantic generation stages | `core.jobs.run_semantic_job`, first statement, before definitions are read or a stage exists | fails unsent: "Not processed: ‹sentence›" |
| semantic recheck | `core.semantic_revalidation.run`, first statement, before the proposal is bound | fails with the recheck's own fixed error, hold released, `semantic.revalidation_failed` audited with `NoProviderRequest` |
| coding | `core.coding_service.run_one`, first statement after the claim | the run fails (`processing_failed`, cost 0, no request) and shows "‹sentence› Contact your administrator to review this retained attempt. No automatic retry will be sent." |
| template and definition preparation | none added: Word-only by construction | creation requires a `.docx` and makes a `docx` template, and the inventory refuses anything that is not a ZIP (`read_original`) before the first role call; definition preparation's `_validate_source` refuses a non-Word source inside its worker before the first stage |

The two sentences are fixed, because a job's error is shown to the doctor and kept in
billing evidence: refused — "The PDF form of this document can no longer be used: it
failed the active-content check. Upload a clean PDF as a new form."; could not run —
"The PDF form of this document could not be checked right now. This is a temporary
problem on our side, not a verdict about the form." The guard never raises into the
worker: anything else that goes wrong in it is the second sentence, so a guard
failure can never leave a job in reconciliation with its hold kept. It is the first
step of each provider path, not the line just above the request: nothing on the path
before the request is a provider call, and a guard placed lower would let a refused
job remux and record a transcription payload ("written before the request") and hold
a provider slot, for a request that is never made. A missing or
changed original is still left to the step that reads it (finalize), as round 2
decided. Because the guard runs when the job runs, a job queued before the deploy, or
by any other path, is covered.

**The synchronous checks that stay, where refusing loses nothing:** encounter creation
(409; the form is shown again with the typed notes; "can no longer be used" for a
refused form, "try again" when the check could not run), the generate request (JSON
409 refused, 503 try again; the HTML form redirects with the same message; moved from
`jobs.enqueue` to `generate_view`, so it runs before `enqueue` takes the encounter
lock), and both downloads (the original, and the export, which re-checks its template
original as round 3 does; 409 or 503, audited).

**Enqueue-time guards removed, none kept:** `jobs.enqueue` (round 2's DL-2 guard; its
transcription arm is what put the recording at risk, and generation's check is now the
generate request's), `coding_service.ensure_run` (round 3's SI-3 guard; a check
subprocess on the answer-save path, repeating the worker's), and
`semantic_revalidation.enqueue` (SI-3; it could never refuse, because semantic
definitions exist for Word forms only, and the worker covers the call). Each would
cost a synchronous check the worker repeats, and on the voice paths the recording, so
none qualified to stay.

**What the doctor sees instead, recorded as the trade.** A recording on a refused form
is now queued, and its job fails as soon as the worker reaches it, with the recording
kept as that job's input (round 3 removed it at upload, saying "can no longer be
used"). A coding run stopped because the check could not run is retained as failed
under its input digest, like any not-sent coding run, so the same answers are not
re-sent by a repeated save (changed answers queue a new run). A generation stopped
that way needs the notes saved again before another request, the existing rule for
an ended attempt. None of this reaches the live rebuild until it has a PDF template.

**GR-1 (major, repaired): a check that cannot start.** `check_original` turned only a
worker timeout or a non-zero exit into a `DocumentError`. A check that could not START
— fork/clone `EAGAIN` or `ENOMEM` at a pids or memory limit, `EMFILE` for its pipes,
`ENOSPC` or `EDQUOT` for its workspace — raised a plain `OSError`, and every gate let
it through. Reproduced on `8ab57b30c` with the lens's injection (only the check's
`subprocess.run` raising `BlockingIOError(EAGAIN)`; inspect and fill real): voice
upload 500, the WAV left on disk with no audit row and no job, untouched by the reaper
at +41 min, +1 day and +8 days; encounter creation 500 with the typed notes lost;
generate (JSON) 500; both downloads 500 with no refusal audited; the retry and
approval pages said the recording was gone while it was on disk. Now `check_original`
reports an `OSError` or `SubprocessError` from starting the check as
`sandbox_unavailable`; `check_pdf_original` treats anything else that escapes the
check as a check that could not run; and `assert_pdf_template_usable` treats an
original that exists but cannot be read as could-not-run instead of skipping the
check. The same probe on round 4: voice 302 with the job queued and the recording its
input, then the worker fails that job unsent with the "could not be checked" sentence
(provider never called, hold released); encounter creation 409 with the notes kept;
generate 503; both downloads 503, audited `sandbox_unavailable`; the over-limit
approval queues the recording and the worker fails it the same way; the retry route
is gone (404).

**GR-2 and GR-3 (minor): gone with the retry flow.** GR-2: alternating the retry and
approval pages kept one signed quote sendable far past 30 minutes. GR-3: one
recording's repeated retries filled the reaper's window of the 500 oldest events. No
retry offer exists now, and an upload produces at most one over-limit quote; the
500-event, seven-day window itself predates P1 and is unchanged from the base.

**GR-4 (recorded, consistent with F2).** An export whose template original is refused
only by F2's byte-pattern false positive — e.g. `/Keywords (intake, pre/Launch
checklist)` — is refused as well (409, `encounter.export_refused`, "the PDF form it
was filled from is no longer accepted"), every time, although pypdf's fill drops the
Info dictionary, so the export carries no `/Launch`; round 2 served it, and so did the
base. This is F2's accepted false positive reaching the export gate: since SI-1 and
SI-2 the gate judges the form, never the export bytes, so it inherits F2 as it
stands, and F2 stays kept, not narrowed. Only PDF exports finalized from such a form
before the repair are affected, and the live rebuild has none. A doctor can upload a
fixed form for new documents, but a finalized document tied to the old form cannot be
downloaded through the app: an accepted-capability loss (class b) for the owner to
accept if it ever touches a real document.

**Round-4 proof.** `core.tests.test_template_original_safety` has 48 tests (round 3
had 35): the worker guard on every provider path — generation, transcription through
the real voice view, the semantic stages, the recheck, coding — each with a control in
which a clean form reaches the provider; the voice upload and over-limit approval as
before P1 (no check on upload; a refused form, a check timeout and a start failure each
fail the job unsent and keep the recording; the retry route is gone); and GR-1 through
encounter creation, the generate request, both downloads, the worker and
`check_pdf_originals`, for every start failure (spawn `EAGAIN` and `ENOMEM`, pipes
`EMFILE`, a child-setup error, workspace `ENOSPC` and `EDQUOT`). The expected sentences
are written in the tests, never read from the code. Run against `8ab57b30c`, 21 of the
48 fail; the other 27 are the 23 unchanged round 1–3 tests, the two controls, and
encounter creation and the generate request, whose refusals are kept. One killing
mutation per new or moved guard — 10, each applied and restored to a pristine sha on a
throwaway clone of the final code, all killed: each of the four worker guards removed,
the generate request's check removed, GR-1's documents-layer conversion removed, its
catch-all removed, the unreadable-original skip restored, the worker guard narrowed so
that it can raise into the worker, and coding's form sentence replaced by the generic
one. The documents list (211 tests) and the P1 core modules (284 tests, with the
recording-limit, audio, coding and semantic recheck modules) pass on pypdf 6.21.1,
6.21.2 and 6.21.4. `pdf_raw.py` and `engine.py` did not change in this round, so the
corpus, fixture and coverage measurements of rounds 1–3 stand and were not re-run.

The full gate (`scripts/ci/verify-fresh.sh python`, pypdf 6.21.1, in a private clone)
then failed four tests outside those modules, each through a fake or an injection that
now meets the worker guard first: two `test_clinical_validation_diagnostics` tests and
one `test_semantic_generation` test hand `run_semantic_job` a fake form with no format,
or a fake version with no form, which a real one always has (they are now Word forms,
as every form with semantic definitions is); and `test_refutation`'s receipt test made a
full disk by failing every `Path.open`, so the guard could not read the stored original
and stopped the job before the provider call the test measures. A full disk fails
writes, not reads, so that injection now fails writes only; the test also asserts that
the provider was called and that no result file was written, and a mutation that drops
the receipt still fails it. No assertion was removed. When no file can be opened at
all, the guard cannot tell a missing original from an unreadable one and fails the job
as could-not-run, the safe direction.

**Not covered, and recorded (round 4).** A missing or changed original is passed by
the worker guard and left to finalize. The export's "missing or changed … contact
your administrator" answer (409) also covers an original that exists but cannot be
opened inside the check (that open error is reported as `source_unavailable`); a
check that cannot start is 503 "try again". In the worker a refusal is audited by the
job's own failure row (`job.failed`, `semantic.revalidation_failed`; a coding run
keeps its error), not with the check's code. A job queued on a refused form holds its
funds until the worker reaches it, then releases them. Both downloads still read the
stored file itself before the check, as the base does; a failure of that read is not
the check, and it behaves as it does on the base.

# Current internal operations supplement — September20–21,2026

The [privileged operations supplement](privileged-operations-security-20260921.md)
records the reviewed helper/renewal boundaries, demonstrated timeout and inventory
admission repairs, actual-host versus fixture scope and remaining operator trust.
Use the latest protected checkpoint for exact installed revision and final proof.
The independent reviewer engagement remains outstanding and reviewer access is
inactive. Earlier entries below retain their historical dates; subsequent backup,
Stripe, email and recovery completion is recorded in owner-actions/checkpoint and
must not be reopened from this older table.

# Private beta security readiness — 2026-09-17

Statuses describe observed evidence and deliberately separate prepared changes
from live activation. The application remains synthetic-only.

| Control | Evidence/status | Remaining qualification |
| --- | --- | --- |
| Private access | Doctor/admin bind 127.0.0.1:9130/9131; public app/admin maintenance503 | Authenticated test access for independent reviewer; reviewed HTTPS deployment before public use |
| Database exposure | Dedicated fresh cluster, published only127.0.0.1:55438; actual wrong-password attempt refused | Transport/encryption requirements for eventual topology; do not expose PostgreSQL publicly |
| Database privilege | Dedicated runtime role active;17role assertions and restored trigger checks passed | Independent privilege/race testing and credential recovery rehearsal |
| Immutable financial/audit records | Eight restored custom triggers enabled; runtime mutation/trigger-disable attempts refused; live billing audit passes | Independent financial mutation and concurrency review |
| Secret handling | Dedicated UID996/GID988, no capabilities, same-PID9denials+3positive controls per service; environment0600 inaccessible | Credential rotation and owner recovery rehearsal |
| Backup/restore |Post-OS restore:33tables/75,248rows/22referencedfiles, all hashes/invariants verified; ciphertext authenticated | Independent failure domain, key escrow, retention/RPO/RTO, scheduling/alerting and promotion rehearsal |
| File protection | Original/export/receipt hashes checked through backup and restore; no public storage route | At-rest encryption/mount and retention/deletion policy for actual patient data |
| Upload/parser safety | Existing isolated parser and synthetic rejection tests; bounded Word SDK qualification in progress | Finished clinical/SDK refutation and deployed WM workflow; scanned forms deferred |
| Tenant permissions | Existing API/file/export/job isolation tests | Independent tests across every fresh route and background authorization race |
| Administrator MFA | Existing TOTP gate and internal tests | Recovery/enrollment/revocation procedures and independent bypass attempts |
| Billing controls | 1.5× multiplier capped at the binding limit held before the request, locking, idempotency tests | Real Stripe test-mode exercise when keys available; account invoice reconciliation |
| External services | Synthetic provider use only | Required patient-data agreements, processing regions/retention and provider controls |
| Penetration test | Internal scope/evidence exists; independent handoff prepared | Independent reviewer, approved access/window and resulting report + repaired-findings retest |

An internal test pass, a prepared unit file or a successfully restored local
database does not clear the patient-data gate. No subscription or cloud resource
was provisioned and no real patient data was used for these checks.

## Evidence scope after dedicated identity activation

Release68883747 is private and synthetic-only. Direct namespace entry failed
because Docker AppArmor denied the ptrace read. Actual service-PID file/socket
probes now establish the intended denial without changing host protections;
this specific coverage gap is closed. The local backup restore is not offsite
recovery and the operator-held key is not independently escrowed.

Cost audit:10usage rows,14wallets, all arithmetic/ledger checks pass; two early
missing receipts remain documented exceptions. Eight real synthetic jobs have
configured-rate costUSD0.012801775400 and chargeUSD0.019202663100. Captured
provider units do not establish account billed cost or invoice reconciliation.
Available Deepgram billing/report access was denied403; Anthropic ordinary
request access does not grant organization billing access.

Stripe sandbox delivery, real Resend invitation/recovery delivery, approved
remote backup restoration, CPT entitlement and independent testing remain
unverified external gates. Use `owner-actions.md` for exact secure handoff steps.
No broad cleanup, new cloud provisioning, purchase or real patient data is
part of these changes.
