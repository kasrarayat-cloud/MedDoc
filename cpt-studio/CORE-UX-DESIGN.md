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
4. No inline script, handler or style attribute from server text; one same-origin script; server text is escaped
   (`escapeHtml`) before it reaches the DOM.
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
byte-identical; additions define no new tokens). `tests/test_frontend.py` and `tests/frontend/app.test.cjs` hold them to
this contract; `ops/walk.cjs` checks it on the deployed site.

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
- `#documentViewer` - an iframe of `document.view_url` (the PDF, the text, or a Word document's converted PDF), and
  `#downloadOriginal` ("Download original") for an upload.
- `#quotesPanel` ("Quoted passages") - every quote of every line as `button.quote[data-code][data-line][data-page]`;
  choosing one moves the viewer to that page (`#page=N`).

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

## 9. Install and verify

`ops/install.py` installs a revision (`ops/INSTALL.md`). `ops/walk.cjs` then drives the real page with a synthetic
document at desktop width and at 390 px (no horizontal scroll): upload, poll to done, the DOM contract above and the JSON
contract, an answer when one is asked, one approval through the dialog (the History naming the line with its code), both
exports downloaded twice to equal bytes (each request naming the round shown), the approval undone through the row's
Undo (naming the decision shown), the denylist scan over every JSON body, the DOM and the downloads, and every `/ops/`
path refused to the customer.

## 10. Read-bind rules; 11. Read-hold registers

Removed with the earlier pipeline (D351-D352).
