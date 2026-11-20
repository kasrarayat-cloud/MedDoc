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
answer its questions (a new round) -> approve or reject each code -> download a draft or the approved codes.

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
- Exports (`cpt-studio-customer-export@3`): a draft (every code with status, units, modifiers, reason, the second check
  and quotes with pages) or the approved codes (each with who approved it, their kind and when), as TXT or CSV, with the
  SYNTHETIC banner at both ends. A download names the round the page shows (`{kind, fmt, round}`) and is refused as
  changed when that is not the latest. A download serves the stored bytes; an export from an earlier round is marked
  earlier.

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
  again; a refusal with blockers stays in the dialog.

## 7. The customer encounter contract

[`API.md`](API.md), `GET /api/encounters/<id>`: every key listed there, nothing else; `ops/verification/customer-contract.json`
is the machine-readable copy.

## 8. DOM contract (the walk depends on these exact hooks)

The encounter view has two columns.

Left, the document:
- `#documentViewer[data-view-url]` - the viewer of `document.view_url`, which keeps that address in `data-view-url`. For a
  PDF (or a Word document's converted PDF) it is a scrolling region (`div.pdf-viewer[role=region]`) the page draws the
  PDF's pages in with the pinned PDF library: every page as `.pdf-page[data-page]`, fitted to the region's width, drawn
  only near the visible area (the others are placeholders of their size) and redrawn when the width changes, each with
  its canvas and a transparent, selectable text layer (`.pdf-text`); `#viewerPage` in the toolbar says "Page N of M".
  Where the library cannot run (it does not load, the browser lacks what it needs, the document is refused), the
  browser's own viewer is framed in the region instead (`[data-mode=frame]`, as before). For a text it is an iframe of
  the text. Under it, `#viewerMark` (`role=status`, polite) says what choosing a quote marked; under that, the note that
  a PDF is a Word document's converted PDF; then `#downloadOriginal` ("Download original") for an upload.
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
dialog: `#exportDialog`.

### Marking a quoted passage (the owner's direction of 2026-11-20, DECISIONS D368)

The one statement of the rule; the code is `locateQuote` (PDF) and `findPassages` (text) in `studio/static/studio/app.js`,
and the docs elsewhere point here.

- A PDF quote is located by its own characters only, in the text of its page as the PDF library reads it (the page's text
  items, joined in order): white space is ignored entirely, Unicode NFKC applies to both sides, and a match is exact-case
  first, case-blind only where there is no exact-case occurrence, and always of whole characters. No fuzzy or nearest
  match, no word list.
- The characters are cut from the page's whole text, across its items: the characters a person sees (Unicode extended
  grapheme clusters, `Intl.Segmenter`), joined again wherever NFKC combines two of them, so that NFKC of the page's text
  is exactly its characters' NFKC, in order (`pageCharacters`). So a letter is never marked without its accent, even
  where the PDF draws the accent as a text item of its own (the library starts a new item where the font changes), and
  no half of a ligature, of a Hangul syllable written as jamo or of an emoji sequence is ever a match. White space is
  dropped after the cut (an accent that follows a space stands on its own), and a character never spans two pages.
- It is looked for on the quote's page. Only where it is not there, on that page and the next joined, keeping only a
  passage that starts on the quote's page and runs onto the next (the marked part on each page is shown). Nothing is
  ever marked on another page; a quote found only on another page is not marked. A quote with no page is looked for on
  every page, and its pages are named.
- Every occurrence found is marked (`span.pdf-mark[data-occurrence]` around exactly the matched characters of the text
  layer, in the page's lime beneath the drawing) and counted in the note: "Marked on page 2.", "These words appear 2
  times on page 1. Each is marked.", "Marked on page 1, continuing onto page 2." Where nothing is found, nothing is
  marked, the page still opens and the note says "The exact words could not be found on page N, so nothing is marked.
  Page N is shown." Never a partial match.
- The mark stays until another quote is chosen or the document changes (a newer coding review clears it with the
  passage chosen); it is painted again whenever its page is drawn again (a new width, scrolled back into view), and a
  read of the document that only changes the codes never reloads the viewer. Scrolling to it respects
  `prefers-reduced-motion`.
- Where the PDF is not drawn in the page, the browser's own viewer is framed instead: a quote opens its page (`#page=N`)
  and the note says why, plainly. "Marking needs a newer browser. Page N is shown." where this browser lacks what
  marking needs (`pdfCapable`) or the library or its worker does not load in it; "This document cannot be drawn here, so
  nothing is marked. Page N is shown." where the library runs but refuses the document, or a page or its text fails;
  "The document took too long to load here, so nothing is marked. Page N is shown." where the download stops moving for
  20 seconds. The viewer keeps the reason on `#documentViewer` (`data-fallback`: `browser`, `document` or `slow`).
- Browsers that mark (measured in Chromium with each candidate built-in deleted in the page and in the library's worker,
  versions from MDN's browser-compat-data): Chrome and Edge 119+, Firefox 125+ (so ESR 128 and 140, not 115), Safari
  17.4+ on macOS, iOS and iPadOS, Samsung Internet 25+. The floor is set by what the legacy library calls with no stand-in
  (`Promise.withResolvers`, `ArrayBuffer.prototype.transferToFixedLength`, `Array.prototype.at`; `structuredClone` and
  `Object.hasOwn` on paths the test documents did not take) and by the matcher's `Intl.Segmenter` (Firefox 125); it brings
  its own stand-ins for the rest (the modern build would have needed Chrome and Edge 147, Firefox 144, Safari 26.2).
  Older browsers get the browser's own viewer and the newer-browser note, without downloading the library.
- A text document keeps its own rule (`findPassages`, as `findPassage`: runs of white space count as one space, exact
  case before case-blind): every occurrence is marked inside the text's frame and the note says how many, or that the
  exact words could not be found.
- It reads no meaning, adds no word list or code rule, and never holds or changes a code (owner condition D358). The
  viewer keeps what it marked on `#documentViewer` (`data-marked`, `data-mark-status`, `data-mark-pages`,
  `data-mark-count`) for the walk.
- The library runs with no eval, no WebAssembly (so the policy needs neither `'unsafe-eval'` nor `'wasm-unsafe-eval'`:
  JPEG 2000 and JBIG2 images use its plain-JavaScript decoders, colour profiles fall back to the device colour spaces),
  no document scripting, no XFA and no layer of links or form fields (form fields' appearances are drawn on the page); it
  reads only the same-origin view address. The one place each legacy file could build a function from a string is
  core-js's lookup of the global object, `Function("return this")`, reached only where `globalThis`, `window`, `self`
  and `global` are all missing (never in a browser), and the policy would refuse it anyway; `tests/test_frontend.py`
  allows that occurrence by its exact bytes and nothing else.
- The text layer is placed by the page's own CSS: `position:absolute; inset:0` over the page, and each span's font size
  and transform computed (`calc()`, `var()`) from the custom properties and percentage offsets the library writes inline.
  The library's CSS `round()` sizes for the layer, which Chrome and Edge before 125 ignore, are not needed (measured: the
  marks do not move without them). What a browser at the floor may lack only changes looks, never a mark:
  `scrollbar-gutter` (Safari before 18.2), `overscroll-behavior`, `color-mix()` in the selection colour,
  `forced-color-adjust`.

## 9. Install and verify

`ops/install.py` installs a revision (`ops/INSTALL.md`). `ops/walk.cjs` then drives the real page with a synthetic
document at desktop width and at 390 px (no horizontal scroll): upload, poll to done, the DOM contract above and the JSON
contract, every quote chosen and its marks read back (its words on its page, or the note saying they could not be
found, nothing marked on another page, and no occurrence beginning or ending inside a character of the page's text,
which the walk reads apart from the page script; counted), an answer when one is asked, one approval through the dialog (the History naming the line with its code), both
exports downloaded twice to equal bytes (each request naming the round shown), the approval undone through the row's
Undo (naming the decision shown), the denylist scan over every JSON body, the DOM and the downloads, and every `/ops/`
path refused to the customer.

## 10. Read-bind rules; 11. Read-hold registers

Removed with the earlier pipeline (D351-D352).
