# pypdf 6.21.4 in the rebuild: what it changes, measured 2026-10-31

`rebuild/requirements.txt` moves pypdf from 6.21.2 to 6.21.4. Seven advisories
against 6.21.2 (CVE-2026-119203 to CVE-2026-119209) fail the required "Python
dependency audit" in `.github/workflows/test.yml`, which blocks every pull
request. All seven are denial of service from a crafted PDF: a long run, a large
allocation or an infinite loop. The document worker already parses each upload
under Landlock and seccomp with a 512 MiB address-space limit and 12 s of CPU
(`documents/sandbox.py`) and a 20 s subprocess timeout (`documents/service.py`),
so on either version such a file ends as a refused or timed-out document.

**Nothing live changes with this commit.** The running rebuild keeps the pypdf
its image was built with until its next install, and that install ships this
pin, so its declaration should name it. This change did not read the running
version: the local `rebuild/.venv` holds 6.21.1, and `main` pinned 6.21.2.

## Measured differences

An independent refutation ran `documents/engine.py` under both versions. It ran
in-process with pypdf chosen by path and its version printed on every row, and
through the real worker for F1, F3 and F4. A second agent then reproduced each
finding from its description, and the author reproduced F1, P1 and F3 a third
time. Every input is a hand-built PDF, and no real producer is known to write
any of them.

| | input | 6.21.2 | 6.21.4 | status since the compatibility repair (2026-11-01) |
|---|---|---|---|---|
| F1 | a /JavaScript name tree or an /OpenAction present only in a later revision whose cross-reference section 6.21.4 cannot read: a negative /Index count, more than 2,000,000 cross-reference stream entries in total, or an indirect /DecodeParms on a filter that ignores it | refused (`unsafe_upload`) | accepted and filled | **remaining** here: the P1 security repair is a separate change |
| F2 | an AcroForm /DR Helvetica whose /Differences uses a glyph name outside the Adobe Glyph List form, such as `/uni006d` (lower-case hex) or `/u41` | the answer is painted | the stored value is right and the fill reports success, but that letter is missing from the painted appearance | **repaired**: refused at inspection (`unsupported_font`) on 6.21.1, 6.21.2 and 6.21.4 |
| F3 | a /DR font whose /BaseEncoding is an array or a dictionary (the PDF format requires a name) | filled | every fill, even a blank one, fails with `TypeError` (`invalid_document`), after the upload was accepted | **repaired**: refused at inspection (`unsupported_font`) on all three |
| F4 | an outline item that is not a dictionary, or a null /Next | the export fails | the item is dropped and the export succeeds | **judged, accepted**: the pages, appearances, text and answers equal a well-formed copy's export; 6.21.4's behaviour is pinned by a test |
| N1 | valid /uniXXXX or /uXXXX names in that /Differences | a fallback font is added | /Helv is kept; the bytes differ and pdf.js paints the same answer | **corrected, then repaired**: the same answer only when the name sits at the letter's own code; refused with F2 |

Unchanged on both versions:

- 78 files from pdf-lib, pdfkit, ReportLab, pypdf's own writer and
  `colon_blank_answers.pdf`;
- 120 real-producer fills, byte-identical with PYTHONHASHSEED pinned (the name
  of the 6.21.2 fallback font follows the hash seed);
- `qualification.run()`, 18 of 18.

The refutation did not render pages in Acrobat, PDFium or Preview. F2's missing
letter is measured with pdf.js only.

## The compatibility repair, 2026-11-01

`pdf_inspect` (`documents/engine.py`) now judges every font a fill can paint a
field with, before anything is filled, and refuses with `unsupported_font` in
the existing "standard Helvetica font only" wording, so the upload page shows
its existing Helvetica hint. It reads the font's PDF objects directly and never
runs pypdf's font parsing, which is the part that differs, so the verdict is the
same on 6.21.1, 6.21.2 and 6.21.4. It runs after every other check, so a form refused
for another reason keeps that refusal and its hint.

A field font is refused when:

- its /Encoding is neither a name nor a plain dictionary, or its /BaseEncoding,
  when present, is not a name (F3). ReportLab writes a dictionary with no
  /BaseEncoding; that stays accepted;
- its /Differences holds anything but codes 0 to 255 and direct names;
- a /Differences name begins `uni` or `u` and pypdf 6.21.4 reads it, through
  `int(x, 16)`, as a printable ASCII character, which 6.21.1 and 6.21.2 never do
  (F2 and N1). No glyph-list name reads that way. A name read as any other
  character stays accepted: answers are printable ASCII only, so it never reaches
  the painted answer, and those fills measured the same on every version.

### What the measurements changed

- **The painter chooses the font, not the old check.** The check read the first
  `Tf` in /DA with a regex, in the AcroForm's /DR. pypdf paints with the last
  complete `Tf` its own parser reads, or /Helv when it reads none, from the /DR
  the widget inherits before the AcroForm's. A second `Tf`, a `Tf` after a `%`
  comment, an unparsable /DA tail and a widget-level /DR each passed an ordinary
  /Helv while 6.21.4 failed every fill on an F3 font. The check now covers every
  name either reading can take, in both /DR dictionaries, for every widget on
  every page. A /DR font that no field can select is not judged.
- **N1 holds only at the letter's own code.** With /uni006D at code 109 (`m`'s
  own) or /u0041 at 65, pdf.js 4.10.38 paints pixel-identical fields on all three
  versions. With /uni006D at 200, 6.21.4 encodes `m` at 200 and pdf.js draws it
  there with too narrow an advance, so the letters after every `m` overlap;
  6.21.1 and 6.21.2 paint it like the control. The rule is therefore per
  answer character, not per spelling, and refuses both.
- **Malformed /Differences entries mislead on every version**, measured with
  pdf.js: a string entry makes pdf.js paint none of the answer whenever the
  painter keeps that font (on every version for `(/A)` at an unused code, and on
  6.21.4 for `(/uni006d)`, which it reads as `m`); an indirect `/uni006d` is read
  as `m` by 6.21.4 and the `m` is missing; a negative code wraps inside pypdf's
  table, so `-56 /A` painted "Amy" as "Èmy" on all three versions.
- **F4.** When an outline's first item has a non-dictionary or null /Next, or the
  outline's /First is not a dictionary, 6.21.4's export equals the export of the
  same form with a well-formed outline in page count, page content, boxes,
  resources, annotations, widget appearances, extracted text, field values and
  AcroForm, and pdf.js paints identical page pixels. Only bookmarks reachable
  through the malformed link are gone, and pdf.js reading the original shows no
  more of them than the export keeps. With /First malformed, the export is
  byte-identical to the same form's export with no outline at all. 6.21.1 and
  6.21.2 refuse these exports (`invalid_document`).
- **PYTHONHASHSEED never reaches the worker.** `service.py` starts it with `-I`
  and a fresh environment, so the fallback font's name is random in every fill
  that needs one: one file filled six times on 6.21.4 got four different names.
  The 120 fills above are byte-identical only because none of them needs the
  fallback font. Where a fill does, pixels are compared instead of bytes.

### Measured after the repair

On pypdf 6.21.1, 6.21.2 and 6.21.4, on the repair's code (commit `328487ad5`),
through the real sandboxed worker unless stated:

- the 133-file ordinary corpus (123 files from MuPDF, ReportLab, pypdf,
  pdf-lib, pdfkit, pdf.js, PDFium, Chromium, fpdf2, Pillow, cairo, Skia and five
  existing blank forms, plus 10 ReportLab CID-font files) keeps every verdict,
  identical on every version and before and after the repair: 40 supported, 25
  `flat_pdf`, 35 `unsafe_upload`, 21 `unsupported_field`, 11 `unsupported_font`,
  1 `invalid_document`. Of the 132 files pypdf can read, 59 carry a /DR. Every
  font in those /DR dictionaries is Helvetica, with either a dictionary that has
  no /BaseEncoding (49, ReportLab's shape) or `/WinAnsiEncoding` (10). The rule
  flags none of them;
- the 40 supported files fill byte-identically, with every stored answer read
  back: 240 outputs, one sha256 per file across the three versions and before
  and after. Identical bytes leave nothing to compare in pixels, text,
  annotations or answers, and the 25 flat files keep the `flat_pdf` verdict that
  routes them to field detection and OCR;
- 42 synthetic shapes for F2, F3, F4, N1, the painter's font choice (including a
  /DR or /DA inherited from a parent field and a widget on a second page) and
  malformed /Differences entries, and 5 for the remaining items below, get the
  same inspection verdict on all three versions. Every accepted shape has the
  same fill outcome on all three, and where it fills, pdf.js paints the same
  field and page pixels on each. The exceptions are F4 (judged above) and the
  negative bfrange (6.21.1 only, listed below). A fill that needs pypdf's
  fallback font differs in bytes from run to run and is the same in pixels;
- 30,000 random /DA byte sequences, each read as a byte string and as a text
  string, in-process: on every version, the font pypdf's painter takes is always
  one the check judges. Where the check's reading raised, the painter's raised
  the same error: 908 assertion errors and 18 type errors. One example is a
  number before an inline-image operator, `/Helv 10 Tf 0 g 1 BI`. Such a form
  used to be accepted, and every fill then failed on every version. It is now
  refused at inspection (`invalid_document`) on all three;
- 400 random /DR encodings (names, base encodings of every type, /Differences
  mixing codes, glyph-list and character-code names, strings, reals, nulls and
  indirect names), judged and filled in-process by the engine without the
  sandbox: the same outcome on all three versions, 252 refused and 148 accepted,
  and all 444 accepted fills render in pdf.js pixel-identical to the plain
  form's field. Through the engine as it was before the repair the same 400 were
  all accepted; decoded with pdf.js's glyph-name rules, 27 fills on 6.21.4 read
  as something other than the answer and 53 failed with `TypeError`, and on
  6.21.2, 10 read wrong;
- `qualification.run()`, 18 of 18.

`documents/test_pypdf_compat.py`, now in `scripts/ci/verify-fresh.sh`'s explicit
list, builds its forms in the test, commits no PDF and passes on all three
versions. Six mutations of the rule (no final pass, no painter font names, no
widget /DR, the per-spelling first draft, any non-name entry, no /BaseEncoding
check) each fail it, and each was restored and verified by sha256. The suites
were run as `verify-fresh.sh` runs them, in a private clone of `328487ad5`, on
each of 6.21.1, 6.21.2 and 6.21.4:

- `check` and `makemigrations --check` are clean;
- the explicit documents list passes 178 of 178, 9 of them new;
- `core.tests` passes 3,798, with 10 skipped.

**Nothing live changes** until the next install, as above. From then on an
already-stored template of an F2, F3 or N1 shape is refused at export with
`unsupported_font`, where 6.21.4 alone would have exported it with a missing
letter or failed. No known producer writes these shapes and the corpus holds
none; the stored templates were not read.

### Remaining: found while repairing, not repaired here

None of these is a 6.21.4 regression:

- a /ToUnicode CMap on the field font with a negative bfrange: accepted on all
  three versions; every fill fails (`invalid_document`) on 6.21.1 only, and
  6.21.2 and 6.21.4 fill it. The 6.21.4 install removes it;
- an /Encoding or /BaseEncoding name that pypdf does not know but viewers do.
  With `/MacExpertEncoding`, pypdf encodes the answer through StandardEncoding
  and pdf.js paints expert glyphs that Helvetica lacks, so the answer is
  unreadable on all three versions. The F3 rule accepts any name, as directed;
- a /DA that is not a string, such as an array holding `(/Helv 10 Tf 0 g)`: the
  check's regex reads it, the upload is accepted, and every fill fails
  (`invalid_document`) on all three versions;
- the painter takes its font size from the last complete `Tf`, or 0 (automatic)
  when its parser cannot read the /DA, while the overflow check uses the first
  `Tf` the regex finds and Helvetica's widths. The repair checks the encoding of
  every font the painter can select, not that it is the standard Helvetica or
  that its size is the one checked;
- 6.21.4 also reads `uni` and `u` names in the built-in encoding of an embedded
  Type1 program differently (the same glyph-name function). Not measured: a
  viewer takes those names from the embedded program itself, so F2's mechanism
  does not obviously apply.

## P1: the upload check can be passed today, on either version

F1 is not a new hole. pypdf 6.21.2 recovers from an unreadable cross-reference
section in the same way, with `strict=True`. A cross-reference stream can be
dropped the same way if it has:

- `/Type /Xref`;
- no /Size;
- a short or over-wide /W;
- an /Index count above its /Size.

A file that hides its script behind such a section is accepted by `pdf_inspect`
under 6.21.2 and 6.21.4 alike, while pdf.js still reports the script.

Once inspection passes, the original is kept, and `template_original`
(`core/views.py`) returns it byte for byte to the department's members. The
upload form says active content is refused.

pypdf logs each drop ("Previous trailer cannot be read", "XRef object at N can
not be read, some object may be missing"). The worker discards that log, which
is where a guard could look. A guard is rebuild work and is not part of this
change.
