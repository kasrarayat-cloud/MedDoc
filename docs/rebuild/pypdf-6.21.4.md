# pypdf 6.21.4 in the rebuild: what it changes, measured 2026-10-31

`rebuild/requirements.txt` moves pypdf from 6.21.2 to 6.21.4. Seven advisories
against 6.21.2 (CVE-2026-119203 to CVE-2026-119209) fail the required "Python
dependency audit" in `.github/workflows/test.yml`, which blocks every pull
request. All seven are denial of service from a crafted PDF: a long run, a large
allocation or an infinite loop. The document worker already parses each upload
under Landlock and seccomp with a 512 MiB address-space limit and 12 s of CPU
(`documents/sandbox.py`) and a 20 s subprocess timeout (`documents/service.py`),
so on either version such a file ends as a refused or timed-out document.

**Nothing live changes with this commit, and no install will change it on its
own.** *(Corrected 2026-10-31. This paragraph first said the running rebuild
keeps the pypdf "its image was built with until its next install, and that
install ships this pin". That was false.)* There is no image and no per-release
venv: every rebuild service runs the permanent venv `/opt/meddoc-pro/rebuild/.venv`,
which holds pypdf 6.21.1 (installed 2026-10-22 by a private helper). No tracked
installer applies a change to `rebuild/requirements.txt`, and the tracked install
engines refuse a delta that contains it; a code-only install leaves the venv as it
is, and nothing at startup compares the installed versions with the pins. This pin
reaches production only through a separately declared dependency install. Until
then production runs 6.21.1, which is why the P1 repair below is proved on 6.21.1
as well as 6.21.2 and 6.21.4.

## Measured differences

An independent refutation ran `documents/engine.py` under both versions. It ran
in-process with pypdf chosen by path and its version printed on every row, and
through the real worker for F1, F3 and F4. A second agent then reproduced each
finding from its description, and the author reproduced F1, P1 and F3 a third
time. Every input is a hand-built PDF, and no real producer is known to write
any of them.

| | input | 6.21.2 | 6.21.4 |
|---|---|---|---|
| F1 | a /JavaScript name tree or an /OpenAction present only in a later revision whose cross-reference section 6.21.4 cannot read: a negative /Index count, more than 2,000,000 cross-reference stream entries in total, or an indirect /DecodeParms on a filter that ignores it | refused (`unsafe_upload`) | accepted and filled |
| F2 | an AcroForm /DR Helvetica whose /Differences uses a glyph name outside the Adobe Glyph List form, such as `/uni006d` (lower-case hex) or `/u41` | the answer is painted | the stored value is right and the fill reports success, but that letter is missing from the painted appearance |
| F3 | a /DR font whose /BaseEncoding is an array or a dictionary (the PDF format requires a name) | filled | every fill, even a blank one, fails with `TypeError` (`invalid_document`), after the upload was accepted |
| F4 | an outline item that is not a dictionary, or a null /Next | the export fails | the item is dropped and the export succeeds |
| N1 | valid /uniXXXX or /uXXXX names in that /Differences | a fallback font is added | /Helv is kept; the bytes differ and pdf.js paints the same answer |

Unchanged on both versions:

- 78 files from pdf-lib, pdfkit, ReportLab, pypdf's own writer and
  `colon_blank_answers.pdf`;
- 120 real-producer fills, byte-identical with PYTHONHASHSEED pinned (the name
  of the 6.21.2 fallback font follows the hash seed);
- `qualification.run()`, 18 of 18.

The refutation did not render pages in Acrobat, PDFium or Preview. F2's missing
letter is measured with pdf.js only.

## P1: repaired 2026-10-31 (code `1ae49392d`, `ecc5c20e6`, `095387ecd`, `fb1f259a1`, `2dcff8790`; not yet installed)

The upload check no longer depends on what pypdf reads. `documents/pdf_raw.py`
scans the exact bytes of every PDF the worker reads, on upload, on every fill and
before a stored PDF original is downloaded, and refuses what it cannot read
completely as `unreadable_pdf`. pypdf's walk stays as a second layer, now with a
single-catalog rule and pypdf's own recovery reports, which the worker used to
discard. What this guarantees, what it does not, and the measurements are in
[security readiness](security-readiness.md). The text below is the finding as it
was reported, kept as the record.

## P1 round 2 — 2026-11-01: cost repair and the download-path gates (not yet installed)

An independent refutation of the round-1 code found two cost defects and two
missing gates, all now repaired, and two ordinary-file edges that are accepted
rather than widened. Full account and measurements in
[security readiness](security-readiness.md) (section "Round 2"). In brief:

- **COST-1** — crafted 10 KB–384 KB files drove the raw scan past the worker's
  12 s CPU while the work budget charged them a unit or two (a backtracking
  number regex, a per-name gap look-ahead, a per-`>>` comment scan, full-row
  predictor allocation sized by `/Columns`, per-offset object-stream re-parsing).
  Every pass is now linear and charged by the bytes it crosses; the lens's inputs
  and ~10 MiB copies all finish well inside 12 s, refused or not, never killed.
- **COST-2** — the fixed 1,000,000-unit budget refused a benign 5.9 MiB object
  graph before the policy ran. The budget now grows with the file
  (`MAX_WORK + size/4`), so ordinary files up to the 10 MiB upload limit pass and
  crafted ones stay bounded.
- **DL-1** — a stored PDF *export* was served after a `sha256` check only; it is
  now run through the same active-content check as an original before serving.
  The live rebuild has **no PDF templates today**, so no PDF export exists to
  refuse; this closes any export written before the P1 repair.
- **DL-2** — a PDF template whose original the gate now refuses is turned away at
  encounter creation and at every provider enqueue, not only at finalize.
- **F1 (accepted)** — a form saved once by pypdf's incremental writer and then by
  pdf.js (Firefox's viewer) is refused `unreadable_pdf`, because pypdf's own
  reader drops a revision over an xref-stream number collision; the real set is
  wider than "pypdf's own writer with two or three increments". The mirror order
  (pdf.js then pypdf) is read by strict pypdf with a misnumbered object yet
  accepted — safe, because the raw scan judges every object regardless of pypdf's
  view. Not widened.
- **F2 (accepted)** — the byte pass refuses a well-formed string holding a long
  policy name right after a slash (e.g. `(intake, pre/Launch checklist)`). By
  design; kept, not narrowed.

## P1 round 3 — 2026-11-01: the gates corrected (not yet installed)

An independent audit of round 2 found four gate defects and two raw-scan edges,
each reproduced first and now repaired. Full account in
[security readiness](security-readiness.md) (section "Round 3"). In brief:

- **SI-1, SI-2** — the round-2 export gate scanned the export itself, and so
  refused, after finalize, a clean form's export larger than the check's 10 MiB
  input limit (exports may be 30 MiB) or one whose answer held "trailer" and a
  later "/Launch". It now checks the export's **form original** with the
  original-download check; an export of a refused original is refused (409).
  *(This replaces the DL-1 line above, which describes the round-2 code.)*
- **SI-3** — saving answers queued a coding run (a provider call) on a refused
  form; coding and the semantic recheck now run the same guard as generation.
  *(Superseded 2026-11-01, round 4: the guard runs in the workers now, below.)*
- **SI-4** — a worker failure of the check (timeout, crash, sandbox) was reported
  as "this form can no longer be used" and deleted an uploaded recording. It is now
  "try again", nothing is sent, and the recording is kept for a retry.
  *(Superseded in part 2026-11-01, round 4: the retry flow was removed and the
  voice upload no longer runs the check, below.)*
- **DELTA-1** — a commented `>> stream` just before a stream the scan had read was
  refused as unreadable by round 2's one-pass rewrite; round 1's rule is restored.
- **COV-RENDITION** — `/Rendition`, `/Movie` and `/Sound` are refused as action
  types wherever they are (an unreferenced one was accepted; not exploitable).

## P1 round 4 — 2026-11-01: provider usage gated in the worker (not yet installed)

A final review of round 3 found one major and three minor defects; the major one
(GR-1) was reproduced first. Full account in [security readiness](security-readiness.md)
(section "Round 4"). In brief:

- **The form guard moved to the workers.** Immediately before every provider call
  for an encounter (generation, transcription, the semantic stages and recheck,
  coding) the worker checks the PDF form's original; a refused form, or a check
  that could not run, fails that job with no provider call, through the job's
  existing failure. The enqueue-time guards are gone, and so is round 3's
  kept-recording retry flow: the voice upload and over-limit approval run no form
  check, exactly as before P1, so a dictated recording can no longer be lost to
  the check. Encounter creation, the generate request and both downloads keep
  their synchronous checks.
- **GR-1** — a check that could not even start (the worker cannot be spawned, its
  pipes or workspace cannot be created) raised an `OSError` past every gate: 500s,
  typed notes lost, unaudited refusals. It is now "the check could not run",
  everywhere.
- **GR-2, GR-3** — the retry window and the reaper's starvation came with the
  retry flow, and went with it.
- **GR-4 (recorded)** — an export whose form is refused only by F2's byte-pattern
  false positive is refused too.

## P1 as reported: the upload check can be passed today, on either version

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
change. *(2026-10-31: that guard now exists as the second layer; the first is the
raw scan, because a log can only report what one pypdf version says.)*
