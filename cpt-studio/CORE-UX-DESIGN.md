# CPT Studio customer interface - design contract

First written for the core repair and customer interface build (session a12d8fb3, 2026-11-03); revised 2026-11-20 for
the Fable coding build (DECISIONS D351-D352; the build specification's sections 6-9). Code and tests cite it by section,
so the numbering is kept; sections that described the removed pipeline say so in one line. The JSON is
[`API.md`](API.md)'s; this file is the page's copy and DOM contract and the access model around it.

## 0. Rules for the customer surface

1. Synthetic data only: every upload carries the synthetic attestation; banners say so; exports say SYNTHETIC at both
   ends.
2. Plain English for a physician's office.
3. One page build at a time: the page names its build on every API call (client contract `customer-2026-11-22`) and
   asks the member to reload when the server is newer.
4. No inline script, handler or style attribute from server text; one same-origin script tag (for a document viewed as a
   PDF the page also loads the pinned PDF library, same-origin modules named on `<body>`; section 8); server text is
   escaped (`escapeHtml`) before it reaches the DOM, and a PDF's own text reaches it as text only.
5. Keyboard and screen-reader use: every control is a button, link or labelled field; focus is kept across the page's
   redraws; status messages are announced (`role="status"`).
6. Customer-facing text never names a vendor or model (Corti, Astra, Fable, OpenAI, Anthropic, Claude, Gemini, Google,
   model ids), tokens, credits, costs, sha256, request ids, "provider", "participant", "peer review", "trace" or a rule
   id. It says "the coding review", "the second check" and "the coding service". The shared list is
   `ops/verification/customer-denylist.json`; text the coding review wrote passes the server's display filter
   (`customer.shown`), which replaces such names with "the system".
7. Never invent a human reviewer or a certification: an agent's approval is labelled agent-executed everywhere.

## 1. What the page does

Upload or paste a document with its date of service and insurance -> watch the coding review read and check it ->
answer its questions (a new round) -> approve or reject each code -> download the draft or the approved report as a PDF
(the only report; TXT and CSV files made before 2026-11-21 stay listed under Earlier downloads).

## 2. Where it lives

`studio/templates/studio/index.html` (the shell and its dialogs), `studio/static/studio/app.js` (the page),
`studio/static/studio/styles.css` (the owner-approved stylesheet: its first 32,785 bytes are pinned and stay
byte-identical; additions define no new tokens), `studio/static/studio/lib/pdfjs-6.5.438/` (the PDF library the viewer
draws a PDF with: the legacy build of pdfjs-dist 6.5.438, which carries core-js 3.51.0 stand-ins for the newest built-ins
it calls; only the files its `MANIFEST.json` lists with their npm path and sha256, the licences of pdf.js, its decoders
and fonts, and core-js beside them). `tests/test_frontend.py` and `tests/frontend/app.test.cjs` hold them to this contract; `ops/walk.cjs` checks it on
the deployed site.

## 3. Readers

Removed with the earlier pipeline (D351-D352): the coding service reads the original document itself.

## 4. Review overlay

Removed with the earlier pipeline: a decision is a `CodeDecision` row on one code line of one round
(`studio/decisions.py`).
The earlier tables, the reviewer's chosen modifier among them, stay as legacy records.

## 5. Access, the operator console and exports

- A workspace member reads the customer surface only. The complete record - runs, models, usage, costs, hashes, the
  coding review's whole answers - is a platform operator's, under `/ops/` (`studio/operator.py`).
- An operator is a user holding an `OperatorGrant` that no `OperatorRevocation` ended, recorded only by the
  `grant_operator` command from a reason file; no workspace role confers it. Everyone else gets exactly an unknown URL's
  404 under `/ops/`. An operator with no membership signs in on the usual page and lands on `/ops/`; one who is also a
  member signs in as the member.
- The console's own address is admin.quillmd.com (owner direction 2026-11-23, D396): its sign-in admits operators only
  (anyone else is refused exactly like a wrong password, with a pointer to the doctors' sign-in) and lands on `/ops/`,
  an operator who is also a member included; a signed-out visitor to a console page there is sent to the sign-in and
  back, never to an unexplained 404. That host serves no doctor app and no API. cpt.quillmd.com/ops/ keeps answering
  operators while both addresses serve.
- The operator console also runs CPT Studio (owner direction 2026-11-22, D395; `studio/console.py`): people and roles
  (add, reset a password shown once, change a role, access off and on; operator accounts and grants are never changed
  there), workspaces for an existing specialty, spending from the recorded usage, and the activity log. The doctor
  app's page, payloads and DOM contract are unchanged by it.
- Exports (`cpt-studio-customer-export@3`): a draft (every code with status, units, modifiers, reason, the second check
  and quotes with pages) or the approved codes (each with who approved it, their kind and when). The PDF (owner
  directive 2026-11-21; `studio/physician_report.py`, `studio/physician_pdf.py`) is the report for the doctor and the
  dialog's only download (owner direction 2026-11-21: no more TXT or CSV). A download names the round the page shows
  (`{kind, fmt, round}`, `fmt` pdf; any other format is refused, 400) and is refused as changed when that is not the
  latest; a PDF that cannot be made is refused (503, nothing stored). A download serves the stored bytes; an export from
  an earlier round, or made before a decision recorded after it on the same round, is marked earlier (`current: false`;
  the page says "made before a later decision or coding review").

## 6. Flow

- Upload: a file (PDF, DOCX, TXT) or pasted text, an optional title, the date of service, the insurance (`#insurance`:
  Medicare / Medicaid / Commercial or other / Not sure) and the synthetic attestation. A repeated submit of one attempt
  opens the document it already made.
- Processing: the page polls the encounter; the member may leave and come back. Stop, Resume and Retry appear only when
  the server offers them (`progress.can_stop`, `can_resume`, `can_retry`).
- Questions: answering sends every answer at once and starts a new round, which reads the document again with every
  answer so far.
- Decisions: Approve opens the review dialog with the attestation; Reject asks for an optional note; Undo revokes. A
  decision is made on a line and names the round the page shows (`{round, line, code, action, acknowledgement,
  note}`); an Undo also names the decision it undoes (`decision`: the id the page shows for it), and a row whose
  decision has no id offers no Undo. What a dialog's act names - the document, the round, the line, its code - is fixed
  when the dialog opens, and leaving the document closes it. When the server answers 409 (the coding review or the
  decision changed), the dialog closes, the page says nothing was recorded and reads the document again - nothing is
  sent twice. A download refused the same way (409 with no blockers) closes the export dialog and reads the document
  again; a refusal with blockers stays in the dialog. The export dialog opened again while that read runs says "This
  coding review has changed. The page is loading the latest; the downloads are offered again once it has." and offers
  nothing; once the read has ended it is drawn as opened on the read the page then has, so its download names the latest
  round. The refused download's own guard is released first, so no other choice waits on that read.
- Downloads: while the server makes the file, every option of the export dialog waits (disabled), the chosen one says
  so ("Preparing PDF…" on a PDF button, with `aria-busy`) and `#exportStatus` says the file is being prepared. Only the
  server's 201 makes the page say the file is ready ("Your PDF is ready. Downloading <filename>.") and start the
  download; the options then come back, and once the page has read the document again the dialog lists the new file
  under "Earlier downloads". A refusal with blockers, or a PDF that could not be made (503, "The PDF could not be made.
  Nothing was saved. Try again."), shows the server's sentence in `#exportError` and gives the options back for a
  retry (a notice instead when the dialog was closed meanwhile); nothing is said to be ready and nothing is downloaded.
  The dialog opened again while a file is being made says so and its options wait until it is made.
- One gesture makes one file: the second click of a double click (`event.detail` > 1) is not a choice, and once a file
  is made its option waits (disabled) for at least a second and until the dialog has been drawn from the document read
  again; then it is offered again, with the focus back on it when nothing else holds the focus.
- An open export dialog follows every read of its document (the poll, the read after an act or a download) while the
  read is of the round it was opened on: an approval recorded or the round finishing changes its options and its status
  at once. A read that lands while a file is being made leaves the dialog as it is until the file is made; a status that
  says a file was just made keeps saying it; a read that changes nothing in the dialog writes nothing to it. Reads are
  applied in the order the page asked for them: one that answers after a later read was shown changes nothing, and its
  failure says nothing.

## 7. The customer encounter contract

[`API.md`](API.md), `GET /api/encounters/<id>`: every key listed there, nothing else; `ops/verification/customer-contract.json`
is the machine-readable copy.

## 8. DOM contract (the walk depends on these exact hooks)

The encounter view has two columns.

Left, the document:
- `#documentViewer[data-view-url]` - the viewer of `document.view_url`, which keeps that address in `data-view-url`. For a
  PDF (or a Word document's converted PDF) it is a scrolling region (`div.pdf-viewer[role=region]`) the page draws the
  PDF's pages in with the pinned PDF library: every page as `.pdf-page[data-page]`, fitted to the region's width at the
  zoom chosen, drawn only near the visible area (the others are placeholders of their size) and redrawn when the width,
  the zoom or the screen's pixel ratio changes, each with its canvas and a transparent, selectable text layer
  (`.pdf-text`; an overprint copy's span is `span[data-overprint="1"]`). The toolbar holds `#viewerPage` ("Page N of M")
  and, once the pages are drawn, the zoom `#viewerZoom` (`button[data-zoom=out|in|fit]`, "Zoom out", "Zoom in", "Fit
  width", and the level `#zoomLevel`, "100%"), then the file name (`.viewer-name`, its full text also its `title`): at
  least 12 characters wide (all of it where it is shorter), and where the toolbar cannot hold it beside the page and the
  zoom it takes a row of its own. Where the library cannot run or cannot draw the document, the browser's own viewer is
  framed in the region instead (`[data-mode=frame]`, `data-fallback` saying why). For a text it is an
  iframe of the text. Under it, `#viewerMark` (`role=status`, polite) says what choosing a quote marked; under that, the
  note that a PDF is a Word document's converted PDF; then `#downloadOriginal` ("Download original") for an upload.
- `#quotesPanel` ("Quoted passages") - every quote of every line as `button.quote[data-code][data-line][data-page]`;
  choosing one (or a row's own quote) opens its page and marks its words there (below). The chosen button stays
  selected (`.selected`, `aria-current`) until another is chosen.

Right, top to bottom:
- `section.progress-panel[data-phase]` - the steps `.progress-step[data-step=reading|checking|finished][data-state]`
  (Reading, Checking, Finished; states done, active, waiting, failed, stopped) and the Stop, Resume and Retry buttons
  when offered. Phase titles: Waiting to start, Reading your document, Checking the codes a second time, Coding review
  finished, The coding review could not finish, The coding review was stopped.
- `section#questionsPanel` ("Questions for you") - one `.question-row[data-question]` per question with a labelled
  `<textarea>`, and `#sendAnswers`.
- `ol#codesList > li.code-row[data-line][data-code][data-status]` (id `code-<line>`; one row per line, so two lines of
  one code are two rows) - `.code-number`, `.code-units` ("1 unit", "2 units", "0 units" as the coding review wrote it,
  or "Units not given" when it gave none), `.code-modifiers` ("No modifier" for none, "Modifier XS", "Modifiers 25, 59",
  or "Modifiers not given"), the status badge `.status`, `.code-reason`, `.code-check` (the second check's verdict and
  reason), `.code-quotes`, and only the buttons `allowed_actions` names, as
  `button[data-decision][data-code][data-line]` (id `act-<line>-<action>`; Approve, Reject, Undo). A row the page cannot
  name by its line is shown but offers no decision.
- `section#notesPanel` ("Documentation notes": the coding review's notes about the documentation, then each comment of
  the second check that could not be tied to one line) and the export button, `button[data-action=export]` ("Download"),
  offered whenever a draft or the approved codes can be made or an earlier download exists.

Status badges: Ready for approval (green), Needs your answer (amber), Needs your review (amber outline), Not supported
(gray); once decided, Approved (green) or Rejected (gray).

The review dialog: `#reviewDialog` with `#reviewLine` (the line's units and modifiers), `#reviewAcknowledgement` (the
label holding the checkbox `#reviewAckBox` and the session's `acknowledgement`, which the member confirms by ticking
it), `#reviewNote` and `#saveReview` (enabled once the box is ticked). The upload dialog: `#uploadDialog` with
`#uploadFile`, `#pasteText`, `#serviceDate`, `#insurance`, `#syntheticAttestation` and `#startReview`. The export
dialog: `#exportDialog`, its copy presenting the PDF as the report for the doctor;
`#exportStatus` (`role=status`: what can be downloaded, then the file being prepared and made); `#exportOptions` with
one `.export-group` per kind - "Draft report" and "Approved report" - each holding its PDF,
`button.button.primary.export-pdf[data-export-kind][data-export-fmt=pdf]` ("Download PDF", full width; "Preparing
PDF…" with `aria-busy` while it is made; named "Download PDF (draft report)" or "Download PDF (approved report)" by
`aria-label`, the words shown first, so the two are told apart by name), described by the `p.export-pdf-note` under it
(draft: every code with its status, any saved decision, the evidence and what still needs a decision; approved: only
approved codes, with who approved them and when);
for the approved group, why it waits (`.export-blockers`). A group's PDF is enabled by the readiness
(`readiness.draft`, `readiness.approved`); each `.export-group` is a `role=group` named by its label
(`aria-labelledby`). The draft's line says what it holds, saved decisions included (a draft holds the decisions saved so
far, approvals among them). Downloads made earlier are listed under "Earlier downloads"
(`.report-list .report-item`: the file's link, then its kind, format - PDF, or the CSV or TXT of earlier releases - and
time); `#exportError` (`role=alert`) holds the server's sentence when a download is refused.

### Marking a quoted passage (the owner's direction of 2026-11-20, DECISIONS D368)

The one statement of the rule; the code is `locateQuote` and `pageText` (PDF) and `findPassages` (text) in
`studio/static/studio/app.js`, and the docs elsewhere point here. The walk's own judge (section 9) states the same rule
apart from the page script.

- **A page's text** is its text items as the PDF library reads them, joined in order, with three steps: an item drawn
  again over an earlier one to look bold is an overprint copy and is left out (R1: its string, after NFKC, holds a
  character that is not white space and is the string of an earlier item of the page - any earlier item; the two items'
  font heights, `hypot(transform[2], transform[3])`, agree within 1%; and its origin lies within max(1, 0.2 x its font
  height) PDF units of that item's origin, in a straight line); a line break follows every item the library ends a line
  with (`hasEOL`); and Unicode format characters (`\p{Cf}`) are dropped, as the library already drops them. An overprint
  copy is never marked, and its span in the text layer says so (`data-overprint="1"`). Finding the copies costs time in
  proportion to the page's items (a page of 20,000 items is prepared in about 0.2 seconds).
- **A quote is located by its own characters only** in that text: white space is ignored entirely, format characters are
  dropped and Unicode NFKC applies, on both sides, and a match is exact-case first, case-blind only where there is no
  exact-case occurrence, and always of whole characters (`Intl.Segmenter` grapheme clusters, joined again wherever NFKC
  combines two of them, so that NFKC of the page's text is exactly its characters' NFKC). No fuzzy or nearest match, no
  word list.
- **Word edges.** At each end of a match a word edge is asked for, in this order, read in the page's text above (copies
  left out, line breaks in) as the page writes it, not after NFKC:
  1. *Separate drawings* (R2b). Where the match's end lies between the last character of one item and the first
     character of the next item that gives a character, with nothing between them, that end is an edge - unless the next
     item visibly continues the first: both have a finite transform and a width above 0, their font heights agree within
     5%, and the next one's origin lies at the first one's end (along the first one's text direction within 0.25 x its
     font height of its width, across it within 0.1 x its height; the library gives the width as the advance along the
     text, rotated or not). So a footnote marker raised or smaller and glued to a word, the jump back of fake bold and an
     overstrike glued after a line's end are edges, while a word drawn in two fonts ("pain" then a bold "less") stays one
     word. An item with no such geometry meets an edge on each side.
  2. *Letters and digits* (R2, R2c). Otherwise, where the quote's character at that end is a letter or a digit
     (`\p{L}`, `\p{N}`), the page's code point beside the match must not be a letter, a digit or a combining mark
     (`\p{L}`, `\p{N}`, `\p{M}`); the start and the end of a page are edges. A Han ideograph (`\p{Ideographic}`) or a
     hiragana character is a word of its own, as Unicode's default word boundaries (UAX #29) have it: it never joins a
     word on the page and never asks for an edge in the quote; katakana stays a word part. So "pain" is not counted inside
     "painless", nor "polyp" inside "polypectomy", while "糖尿病" is found in running Chinese text.
  3. *Numbers* (R2a). Then a number's own separator keeps its digits in one word (UAX #29 WB11, WB12): the 21 code points
     Unicode 16.0 calls MidNum, MidNumLet or Single_Quote (U+0027 U+002C U+002E U+003B U+037E U+0589 U+060C U+060D U+066C
     U+07F8 U+2018 U+2019 U+2024 U+2044 U+FE50 U+FE52 U+FE54 U+FF07 U+FF0C U+FF0E U+FF1B) between two digits (`\p{Nd}`). A
     match is turned away where the quote begins with a digit and the page has a separator and a digit before it, where
     the quote begins with a separator and a digit and the page has a digit before it, and the same at the end. So "1 cm"
     is not counted inside "2.1 cm", "500 mL" inside "1,500 mL", "Hemoglobin 12" inside "12.5", nor "2." inside "2.5 mg",
     while the list number "1." is found and "1990" in "1990's". The quote's characters are asked as folded (NFKC), the
     page's as written; reading stops at an edge of step 1.
  White space inside the quote stays ignored, so a quote whose words the page runs together into one whole word ("not
  able" for "notable") is still found. A place turned away is passed over by one character only, so a word right after
  it is still found.
- **Pages.** It is looked for on the quote's page. Only where it is not there, on that page and the next joined, keeping
  only a passage that starts on the quote's page and runs onto the next (the marked part on each page is shown; the edges
  are read on each page). Nothing is ever marked on another page; a quote found only on another page is not marked. A
  quote with no page is looked for on every page, and its pages are named. Each page's prepared text is made once per
  document and reused; a quote with no page reads and prepares the pages in slices, so the page never stops answering
  for long.
- **What the matcher marks is whole characters of the text as the library reads it**, which is not always the text as
  drawn: two letters a PDF declares for one drawn ligature are two characters (only the word-edge rule keeps a mark from
  beginning or ending between them), and a spacing accent drawn over a letter is a character of its own (the letter can
  be marked without it). A letter keeps a combining accent the PDF draws as an item of its own.
- **Marks and notes.** Every occurrence found is marked (`mark.pdf-mark[data-occurrence]`, role mark, around exactly the
  matched characters of the text layer, in the page's lime beneath the drawing) and counted in the note: "Marked on page
  2.", "These words appear 2 times on page 1. Each is marked.", "Marked on page 1, continuing onto page 2." Where nothing
  is found, nothing is marked and the page still opens: "The exact words were not found in the searchable text of page
  N, so nothing is marked. Page N is shown." (with no page: "... of this document, so nothing is marked."); where the
  quote's page has no searchable text at all (no character after folding, copies left out, whatever the next page
  holds): "Page N has no text the viewer can search (it may be a scanned image), so nothing is marked. Page N is shown."
  (with no page, where the whole document has none: "This document has no text the viewer can search (it may be a
  scanned image), so nothing is marked."). Never a partial match.
- The mark stays until another quote is chosen or the document changes (a newer coding review clears it with the
  passage chosen); it is painted again whenever its page is drawn again (a new width or zoom, scrolled back into view),
  and a read of the document that only changes the codes never reloads the viewer. When another quote is chosen, what was
  shown of the one before goes at once, before anything is waited on - its marks on every drawn page, the viewer's mark
  state and the note - and nothing of it is painted on a page drawn while the new quote's pages are read; a quote whose
  pages are already read is shown in the same moment. Scrolling to it respects `prefers-reduced-motion`; where the pages
  are wider than the viewer (a zoom above fit width), the first mark is brought into view across too (by the least
  distance that shows all of it with a 12 px gap, or with its start 12 px from the viewer's start where it is wider than
  the viewer). A zoom, a new width or a new pixel ratio while the view is still moving to a quote, or before its page is
  drawn, keeps the quote: the view is sent to it again. The member's own scrolling (a wheel, a touch, a scroll key, a
  pointer on the viewer) ends that, so nothing moves the view later unasked.
- **Zoom.** "Zoom out", "Zoom in" and "Fit width" step through 75%, 100% (the page fitted to the viewer's width), 125%,
  150%, 200% and 300%; a page wider than the viewer scrolls across inside it, the page at the top of the view stays at
  the top, and the text layer and the marks follow at every step. A new width keeps the zoom (relative to the new fitted
  width); a step that can go no further is `aria-disabled`, so the focus stays on it.
- **The browser's own viewer.** Where the PDF is not drawn in the page, the browser's own viewer is framed instead and a
  quote opens its page there: a quote on another page than the frame was opened at gets a new frame at `#page=N` (the
  browser's viewer opens the page only as its frame loads); the same page, or no page, keeps the frame. Nothing is
  marked, and the note says why, then the quote's page, never what the frame shows: "Marking needs a newer browser. The
  quote is on page N." where this browser lacks what marking needs (`pdfCapable`); "The marking tool did not work here,
  so nothing is marked. The quote is on page N." where the library or its worker does not load or start, or has not
  within 20 seconds, or its worker fails once started, or, once the document has opened, the library has not answered
  for 20 seconds while the viewer waits on it; "This document cannot be drawn here, so nothing is marked. The quote is on
  page N." where the library refuses the document, finds no page in it, or fails on a page's drawing or text; "The
  document took too long to load here, so nothing is marked. The quote is on page N." where the download stops moving
  for 20 seconds before the document opens (that timer stops once it has opened); "The document could not be downloaded
  for marking, so nothing is marked. The quote is on page N." where the download fails (an answer that is not 2xx, a
  fetch that fails, a body that breaks off). With no page, the reason sentence alone. The viewer keeps the reason on
  `#documentViewer` (`data-fallback`: `browser`, `library`, `document`, `slow` or `download`), and the note names the
  page of the quote being chosen. The time limits count only the time the page is visible (a hidden tab draws nothing),
  except the stalled download's 20 seconds, which run from the last data received whether the page is visible or not.
  A library that failed or timed out, or whose worker failed, is tried again for the next document opened, at fresh
  addresses (`?attempt=2`, `3`, ..., for the module and its worker: the browser remembers a module that failed to load, by
  its address, for the life of the page); the document that failed stays framed.
- **The viewer's own worker, download and watchdog.** The viewer starts the library's worker itself (a module worker at
  the worker's address), waits for the worker to say it is ready, and only then hands it to the library as its port, so
  the library never starts a worker of its own or its stand-in on the page's thread; closing the document ends the
  worker. The viewer downloads the view address itself (same origin, the browser's default credentials), chunk by chunk,
  and gives the library the bytes. Once the document has opened, one watchdog per viewer watches every wait on the
  library (the pages fetched, a page drawn, a page's text read, a text layer rendered): a wait is given up only when the
  library has not answered for 20 seconds of visible time, counted from the later of its last answer and the start of the
  wait, where an answer is any message from the viewer's worker or any of these waits settling. So a scan whose pages
  take long to decode (JPEG 2000 above all), with the worker busy on other pages, is waited for and marked, while a
  worker that has stopped still gives the library's note about 20 seconds later. A page released from the view is no
  longer waited on.
- **Browsers that mark** (measured in Chromium only, with each candidate built-in deleted in the page and in the
  library's worker; Firefox and Safari were not run, and their versions are MDN's browser-compat-data for what the
  measurement found needed): Chrome and Edge 119+, Firefox 125+ (so ESR 128 and 140, not 115), Safari 17.4+ on macOS, iOS
  and iPadOS, Samsung Internet 25+. The floor is set by what the legacy library calls with no stand-in
  (`Promise.withResolvers`, `ArrayBuffer.prototype.transferToFixedLength`, `Array.prototype.at`; `structuredClone` and
  `Object.hasOwn` on paths the test documents did not take) and by the matcher's `Intl.Segmenter` (Firefox 125). The
  legacy build puts back itself, when missing, what else it calls (seen present again once it had run): Map and WeakMap
  `getOrInsert` and `getOrInsertComputed`, `Math.sumPrecise`, `Promise.try`, Uint8Array `fromBase64`, `toBase64`,
  `toHex`, `setFromBase64` and `setFromHex`, `Iterator` with its `map`, `filter`, `toArray`, `flatMap`, `forEach`,
  `some`, `every` and `find`, the seven new Set methods, `URL.parse`, and Response and Blob `bytes()`; it does not put
  back `Uint8Array.fromHex`, `Iterator.from`, `Iterator.prototype.reduce`, `Array.prototype.findLast` and
  `findLastIndex` or `Float16Array`, which the documents never needed (the library does not call them on the viewer's
  paths, or tests for them first). Older browsers get the browser's own viewer and the newer-browser note, without
  downloading the library.
- **Drawing.** The pages near the view are drawn one at a time, the page a quote waits to be shown on first, and none is
  started while the view scrolls: the library's worker decodes one page's images at a time and answers as each page is
  done, a page only passed by a continuous scroll is never decoded, and a page asked for at a new size while it is
  drawn finishes and is then drawn again from what was decoded. Pages away from the view are released and the library lets go of what
  it decoded to draw them (a 40-page 300 dpi scan scrolled to the end and back stays near 300 MB, against 1.5 GB before); a change of the screen's
  pixel ratio with no change of size redraws the canvases at the new ratio; in forced colours (Windows contrast themes)
  the drawn page keeps its own white ground, so it stays legible and the mark visible, while the note and the page label
  keep the forced colours; in the desktop layout the quoted passages keep their approved share of the column (at most
  36%), however long the document.
- A text document keeps its own rule (`findPassages`, as `findPassage`: runs of white space count as one space, exact
  case before case-blind, no word edges): every occurrence is marked inside the text's frame (marked, not selected: the
  marks stay while a selection would not) and the note says how many, or that the exact words could not be found. The
  frame is searched only when it holds the document (`frameHolds`): its current document must have had its own load,
  be readable, answered 200 where the browser tells the answer, and of the document's exact size (`document.size`)
  where the browser tells a positive body size. Each load of the frame paints the chosen quote again, so the marks and
  the note follow what the frame holds (a reload from the frame's own menu included), and a quote chosen while the
  frame loads clears the earlier note until that load. Otherwise - the edge's own "temporarily unavailable" page while
  the app restarts, which the frame shows, or an answer the frame refuses to show - nothing is searched,
  `data-mark-status` is `unavailable` with `data-fallback="download"`, and the note is the 'download' sentence ("The
  document could not be downloaded for marking, so nothing is marked."). The walk fails such a reading.
- It reads no meaning, adds no word list or code rule, and never holds or changes a code (owner condition D358). The
  viewer keeps what it marked on `#documentViewer` (`data-marked`, `data-mark-status`, `data-mark-pages`,
  `data-mark-count`) for the walk.
- The library runs with no eval, no WebAssembly (so the policy needs neither `'unsafe-eval'` nor `'wasm-unsafe-eval'`:
  JPEG 2000 and JBIG2 images use its plain-JavaScript decoders, colour profiles fall back to the device colour spaces),
  no document scripting, no XFA and no layer of links or form fields (form fields' appearances are drawn on the page); it
  is given only the bytes the viewer downloaded from the same-origin view address, and parses them in the viewer's own
  worker. The one place each legacy file could build a function from a string is
  core-js's lookup of the global object, `Function("return this")`, reached only where `globalThis`, `window`, `self`
  and `global` are all missing (never in a browser), and the policy would refuse it anyway; `tests/test_frontend.py`
  allows that occurrence by its exact bytes.
- The text layer is placed by the page's own CSS: `position:absolute; inset:0` over the page, and each span's font size
  and transform computed (`calc()`, `var()`) from the custom properties and percentage offsets the library writes inline.
  The library's CSS `round()` sizes for the layer, which Chrome and Edge before 125 ignore, are not needed (measured: the
  marks do not move without them). What a browser at the floor may lack only changes looks, never a mark:
  `scrollbar-gutter` (Safari before 18.2), `overscroll-behavior`, `color-mix()` in the selection colour,
  `forced-color-adjust`.

**Known limits** (recorded, not defects):
- Only pages near the visible area are drawn, so only their text is in the page: a screen reader reads the text of the
  pages near the view, not of the whole document at once (the marked words are role mark on the drawn page), and the
  browser's find in page (Ctrl+F) sees only the drawn pages' text, so its "no match" says nothing of the other pages;
  "Download original" opens the whole document where its own viewer searches every page.
- A copy the library joins to the text beside it is no item of its own, so it is not found as an overprint copy: fake
  bold drawn inside a line in the line's own font, or a line-printer overstrike where only the bold part is drawn again.
  Those words then read twice: a quote of just those words is counted at two places in one spot, and a passage that runs
  across them is not found. The same holds for a copy the library splits into items otherwise than its original. A
  browser's print of text with a CSS text shadow (even an invisible one) draws the shadow as such a copy.
- Thai, Lao, Khmer and Myanmar are written without spaces between words, and their letters are word parts, so a run of
  them reads as one word and a quote inside such a run is not found. Katakana is a word part too, so it joins Latin
  letters and digits written against it (CTスキャン, 5ミリ): a quote that starts or ends where they meet is not found.
- A single page whose images take more than 20 seconds to decode, with no other answer from the library meanwhile, is
  taken as the marking tool not working.
- On a dark fill the highlight is faint: the drawing is multiplied over the mark like a highlighter, so a dark band
  darkens the lime with it (white text on a dark band shows the mark mainly as a tint of the glyphs).
- Words the page shows as an image (a scanned page) or drawn by a form field's appearance are not in the searchable
  text: a page with no searchable text says so; a page with some text says the exact words were not found in its
  searchable text.
- A quote with no page on a very long PDF reads and prepares every page once (in slices: no main-thread task above about
  60 ms measured at 100, 300 and 600 pages); the coding review's PDF limit of 600 pages bounds it.
- Text documents: the case-blind fallback lowers one UTF-16 unit at a time, so case that depends on context (a Greek
  final sigma) or astral letters (Deseret) is not matched case-blind; quotes are cited from the document, so the
  exact-case match normally comes first.

Recorded in round 6 under the stop rule (D381: a wrong mark or a false message that a normal document and a cited
sentence can bring about is repaired; the rest is recorded here):
- A page printed by a web browser (Chrome or Edge "Save as PDF") is searched in the order the browser drew it, which is
  not always reading order: floated labels are drawn before the rest of the page, and text the page moves or makes
  translucent (superscripts and subscripts as the common web style sheets set them, `position: relative` badges,
  translucent or transformed spans) after it. A quote that runs across such text is not found (the note says the words
  are not in the page's searchable text; the browser's own find does not find them there either), and a count can leave
  out an occurrence that runs across it.
- A superscript or subscript digit written as a character (¹ ² ³ ₂), not drawn raised or smaller, is a word part like
  any digit: a quote that ends or starts right at one (a footnote marker typed after a word) is not found, and an
  occurrence glued to one is not counted. A quote that includes it is found.
- In letter-spaced text (a gap of about a tenth of the font size or more between letters, as some web styles space out
  capitals) the library writes a space between every two letters, so R2 and R2a see no word or number edge inside it: a
  quote that starts or ends inside such a word or number is marked inside it ("2.5 mg" inside a spaced "12.5 MG") and
  counted at each spaced copy. Whole words and sentences are not affected.
- Where a browser slants a font that has no italic face, R2b measures across the slanted letters, so an italic run
  that ends inside a word ("<i>polyp</i>ectomy") is an edge there and "polyp" is counted inside "polypectomy";
  italic set from inside a word ("polyp<i>ectomy</i>") is read with a line break before the italic run, so each part
  is found alone. Whole italic words are not affected.
- The word edges are R2's, not Unicode's word boundaries: the Arabic decimal separator (٫) is not a number separator, an
  underscore is an edge (Unicode joins words across it), and a letter drawn at another size (a drop cap) is an edge. A
  quote that begins with a number separator, a space and a digit right after a digit on the page (", 4.0") is turned
  away; no cited sentence has that shape.
- R1's grid takes one cell size for a page, from its largest item, so a page of many identical small items with one
  very large item prepares slowly (8 s measured for 20,000 items around one item 10,000 units high).
- The note says what was marked as soon as the quote is found; its page is drawn after it (about a second on ordinary
  documents, several seconds on JPEG 2000 scans), so the page can be blank under the note for that time. A not-found
  quote's page is drawn in its turn among the pages near the view. Where that one page takes more than 20 seconds, the
  note becomes the marking tool's sentence (the 20-second limit above).
- When the member scrolls with pauses over 150 ms, the page drawn at each pause is the oldest still near the view, often
  the one above it, and a page let go before it is drawn has still been decoded by the worker (it does not stop a decode
  it has begun): on heavy JPEG 2000 scans a quote chosen right after such a scroll waits for that backlog (up to half a
  minute measured). While the view keeps scrolling, nothing is drawn.
- A quote whose words take a while to find (no page on a long PDF, or a page of a heavy scan still decoding) moves the
  view to its words when they are found, even if the member scrolled meanwhile. After a quote's scroll the page label
  names the page at the middle of the view, which for a quote in a page's last lines (a footer; the last lines on a
  phone) can be the next page.
- Zoom in and back out within 150 ms can leave a drawn page's canvas at the earlier size, stretched (blurred, the marks
  in place), until its next drawing. A viewer closed while its worker is starting can set the library aside 20 seconds
  later, so the next document downloads it again. A worker that says it is ready and then stops before the document
  opens is named as a stalled download ('slow') rather than the marking tool ('library').
- In the browser's own viewer the quoted passages' lead still says choosing marks the words; the note after each choice
  says why nothing is marked. An overprint copy stays in the drawn page's text for assistive technology, so a screen
  reader reads fake-bold words twice (once marked).
- Text documents: a text whose accented letters are stored decomposed (a letter then a combining accent, as some copies
  out of PDFs give it) is searched as stored, while the coding review read it composed, so a quote with such a letter is
  not found and the note says the exact words could not be found, though the frame shows them.
- Text documents (round 7, D382): a frame load the browser stops (Esc, the Stop button) or whose body breaks off never
  brings its load, so the viewer waits: it marks nothing and says nothing until the page is opened again, and the
  frame shows what arrived. After the member reloads only the frame (its own menu), an earlier choice's note stays
  until that reload's load comes (a moment, normally), and stays on, over the unmarked text, if it never comes, until
  the next choice (round 8). A body of size 0 is read as a size the browser did not tell (no view the app serves is
  empty).

## 9. Install and verify

`ops/install.py` installs a revision (`ops/INSTALL.md`). `ops/walk.cjs` then drives the real page with a synthetic
document at desktop width and at 390 px (no horizontal scroll): upload, poll to done, the DOM contract above and the JSON
contract, every quote chosen and judged by the walk's own search, an answer when one is asked, one approval through the
dialog (the History naming the line with its code), both reports downloaded as PDFs, read by the walk's own PDF reading
(every page marked synthetic with its status, every code named) and fetched twice to equal bytes (each request naming
the round shown), the approval undone through the row's Undo (naming the decision shown), the denylist scan over every
JSON body and the DOM (the PDF reports' wording is scanned by `ops/scan_customer.py`, which reads a phrase a line
break cuts as one and sets aside only the printed quotations of the document), and every `/ops/` path refused to the customer.

The walk never takes the viewer's word for a quote (DECISIONS D368, rounds 3 and 5). It reads every PDF it judges
itself, in Node, with the pinned library the page draws with (`studio/static/studio/lib/pdfjs-6.5.438`, its legacy build,
with the page's options: no eval, no XFA, no WebAssembly; in Node the library always runs its worker as its stand-in in
the walk's own process): the bytes it uploaded, or - for a Word file, whose view is the PDF it was converted to, and for
an encounter it did not upload - the view address, fetched in the page with its own signed-in session (a GET of the same
origin). From that reading (the page count, each page's box, rotation and user unit, and each page's text items exactly
as `getTextContent()` gives them to the page; equal, item for item, to what the library reads in the page, on every
fixture) it makes its own text of every page - R1's overprint copies left out, format characters dropped, a line break
after every item marked `hasEOL` - and runs the rule of section 8 itself, R2 with R2a, R2b and R2c. Nothing of its text
comes from the viewer's text layer.

It then holds the viewer to its own reading:
- the viewer's pages (`.pdf-page`) are the document's page count;
- each drawn page's text layer is the document's text: its spans, in order, are the items the library's text layer puts
  in the page (one span per item whose string is not '', a `<br>` after each item marked `hasEOL`), so a layer read from
  another page, or with a span dropped or changed, fails;
- the overprint flags (`data-overprint="1"`) are exactly the walk's own R1 copies, both ways: a flag on a span that is not
  a copy (which would hide its words) and a copy without its flag (whose words would count twice) both fail;
- the marks are exactly its own occurrences (count, place and case, so a case-blind match beside an exact one, a dropped
  occurrence or a "not found" over words that are there all fail), its count and pages agree, and the note is the rule's
  sentence, character for character; nothing is marked on another page or inside a character;
- every marked span lies where its item is drawn: computed from the item's transform at the viewer's scale (the page
  box's CSS width over the page's width at scale 1) with the page's rotation, box and user unit from the walk's own
  reading, its centre lies along the item's run (within 0.5 of the font's height of its origin and its origin plus its
  width) and within 0.25 of the height of where the library's text layer puts it across the run (the origin less the
  font's ascent, measured as the text layer measures it, plus half the span's height). Measured in Chromium on every
  fixture of round 5 (upright, turned 90, 180 and 270, turned text at 90 and 45 degrees, slanted and mirrored text, a
  CropBox with its own origin, /UserUnit 2, Times and Courier, four pages, faint scans): 0 outside the run, -0.09 to +0.06
  of the height across; the text layer moved 8 pt or 22 px down, a line up or scaled 6% larger lies 0.26 to 2.3 heights
  away.

Every page a quote requires drawn (a page with a mark or one of the walk's occurrences, or the page shown for a quote not
found) must be painted (its canvas opaque), and is checked as the member sees it (B5). The viewer draws only the pages
near what it shows and lets the others go, so each such page is brought back into view and read again, drawn, right
before it is looked at; that reading is the one judged. Screenshots of the page's box (the viewer scrolled over it as
needed, its scroll put back) are compared with its canvas pixels, both reduced to 4 x 4 CSS px
blocks, outside the marks. Over the blocks where the canvas draws no ink the screen may differ by at most 2 luminance
levels on average (measured 0 on drawn vector pages and 0.03 on scans; a page shown through an ancestor at opacity 0.03,
or a scan whose paper the screen turns white, 0.8 to 16.7); over the blocks where it draws ink (8 levels darker than its
paper or more), where there are four or more, the screen must show at least 0.6 of that ink (measured 1.000 to 1.001; the
canvas at opacity 0.04 or 0.02, screened, lightened, filtered to opacity 0, under an opaque text layer or an ancestor at
opacity 0.03 shows 0 to 0.36). A page whose own reading has text must show ink - at least 0.0002 of its canvas's pixels
(a white canvas shows none) - and a marked page ink under its marks, at least 0.05 of the pixels there (B6: measured 0.26
to 0.47 on every fixture and on faint scans, ink 190 on paper 240 at 150, 200 and 300 dpi, serif and sans; a mark over
blank paper shows 0). A pixel is ink when its luminance is at most the paper's (the canvas's most common luminance) less
max(8, 0.35 x (the paper less the page's 2nd-percentile luminance)): darker than the paper by a share of the page's own
contrast, so faint scanned ink counts and a clean scan's noise does not.

After every quote is chosen, the last one the walk judged marked is chosen again where another is now marked, and judged
again on its page drawn again at the new scale after Zoom in (`#viewerZoom [data-zoom="in"]`) and after Fit width
(`[data-zoom="fit"]`): marks, alignment, drawn and seen, as above. In the browser's own viewer it requires the reason
sentence the viewer gives - 'browser', 'library', 'document', 'slow' or 'download' ("The document could not be downloaded
for marking, so nothing is marked.") - and " The quote is on page N.", and a new frame whenever the quote's page differs
from the frame's. A text document is judged by the walk's own copy of its rule (`findPassages`). Counted; and where the
PDF viewer drew the document or the text viewer showed it, at least one of its quotes must be marked, since the walk's
documents quote their own words (so a text viewer that marks none of them fails, whatever its frame holds).

A caller with the document's bytes passes them: `chooseQuotes(page, enc, { bytes })`; without them the walk fetches the
view address in the page. `judgeQuote(quote, reading)` and `quoteMarkChecks(chosen)` need nothing more than what
`chooseQuotes` returns (each reading carries the walk's own reading of the document, `reading.document`, and the redraws
ride on the array as `chosen.redraws`).

Known limits of the walk: a page whose only ink lies under its marks is seen through its paper only; a page whose text is
all invisible (drawn in render mode 3 over nothing) has text and no ink, and is failed (on the safe side); a span of a
vertical font is not placed, and is counted out of the alignment check; the screenshot comparison covers the parts of
the page the viewer can scroll into view. Recorded in round 6: the walk checks where the marks are, not how they look
(a style that cancels the mark's colour passes); on a dense page the ink under the marks (B6) is met by any drawing of
text, so a canvas drawn a line off, slightly larger or from a page with the same layout passes, while the text layer,
the marks and their places are held to the walk's own reading; the walk and the suites run at a device pixel ratio of 1
only (the viewer was measured at 1, 1.25, 1.5 and 2); a faint scan with a dark edge or band over about 2% of the page
(black scanner backing, a dark border) sets the ink threshold so low that the ink under the marks is not seen, and a
correct page fails (on the safe side); in Node the library cannot load its standard fonts, so for a PDF using Symbol or
ZapfDingbats without embedding them the walk's reading names those fonts otherwise than the page's (the text and its
places are equal); and an item whose text direction has zero length is a continuation for the walk and an edge for the
viewer, which the library never gives (it gives such an item no width). The suite's text scan of the library for code
built from strings and its stylesheet token pin read the spellings a minifier and a person write, not escaped or
commented forms; the page's policy refuses code built from strings whatever its spelling. Recorded in round 8: for a
text document the walk judges each quote against what the frame holds when the viewer has answered, so a viewer that
answers before its frame holds the document is judged against that frame (the rule that at least one quote is marked
still fails a run where none is); and that rule can fail a correct viewer on a round whose every quote is a
model-written evidence quote not found word for word (the coding service cites the walk's documents, so their quotes
are found).

## 10. Read-bind rules; 11. Read-hold registers

Removed with the earlier pipeline (D351-D352).
