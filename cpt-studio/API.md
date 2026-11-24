# CPT Studio customer API

Client contract `customer-2026-11-24` (`studio/client_contract.py`; the fix passes' line identity, the id of each
decision shown, which an undo names, and the round an export names). Handlers:
`studio/api.py`; every payload is built by `studio/customer.py` from stored rows on each request.
`ops/verification/customer-contract.json` lists the keys and `ops/verification/customer-denylist.json` what a customer
response may never carry; the browser walk (`ops/walk.cjs`) holds the deployed site to both.

## Conventions

- **Session authentication** (`/login/`). A call without a session answers `401 {"error": "Sign in to continue."}`.
- **The client header.** The page sends `X-CPT-Studio-Client: customer-2026-11-24` on every API call. A call without it,
  or naming another build (a tab left open across an install), answers `409 {"error": "CPT Studio was updated. Reload
  this page to continue.", "error_code": "client_outdated"}` before the view runs. Downloads and the in-page view of the
  original are browser navigations and are outside the contract.
- **CSRF** on every POST (`X-CSRFToken` from the `cptstudio_csrf` cookie). Request bodies are JSON
  (`Content-Type: application/json`) except the upload, which is multipart.
- **Tenancy.** Every record is scoped through the caller's active membership: another workspace's encounter or export
  answers `404 {"error": "Not found."}`.
- **Roles.** Owners and reviewers may change things (upload, answer, decide, stop, resume, retry); a viewer reads and
  exports. A viewer's change answers `403`.
- **Errors** are JSON `{"error": "<the member's sentence>"}`, with `details` where there are any: `400` invalid input,
  `404` not found, `409` not now (a job is running, the round is not done, nothing to resume). No exception or stored
  text is ever echoed.
- **Responses** are `Cache-Control: no-store`. Timestamps are UTC ISO 8601 with `Z`, to the second.
- **What a customer never sees**: a vendor or model name, tokens, costs, hashes, run or request ids, the word provider,
  or anything under `/ops/` (the platform-operator console, which answers a customer 404).

## Vocabularies

- Encounter `state` (with `state_label`): `processing` (Processing), `stopped` (Stopped), `failed` (Could not finish),
  `awaiting_answer` (Questions for you), `needs_review` (Needs your review), `ready` (Ready for approval), `reviewed`
  (Reviewed), `no_codes` (No codes found), and `earlier` (Earlier review: a record of the earlier system, with no
  coding round; Review again codes it).
- `progress.phase`: `queued`, `reading` (the coding review), `checking` (the second check), `done`, `failed`, `stopped`,
  `earlier`.
- Code `status` (with `status_label`): `ready` (Ready for approval), `needs_answer` (Needs your answer), `needs_review`
  (Needs your review), `not_supported` (Not supported).
- `insurance`: `medicare`, `medicaid`, `commercial` (commercial or other), `unknown` (not sure).
- Round `trigger`: `upload`, `answers`, `retry`.
- Code `line`: `L1`..`Ln` for the coding review's codes in the order it listed them, then `M1`..`Mk` for the codes the
  second check added. A line, not a code, is what is decided, quoted and exported: two lines may hold one code.

## Endpoints

### `GET /api/session`

```json
{"user": {"id": "...", "label": "...", "initials": "AB", "actor_kind": "human|agent"},
 "workspace": {"id": "...", "name": "...", "specialty": "Gastroenterology|Neurosurgery|Orthopedic Surgery"},
 "role": "owner|reviewer|viewer", "can_review": true,
 "acknowledgement": "<the exact text an approval must send back>",
 "counts": {"documents": 3, "queue": 1}}
```

`counts.queue` is the documents waiting on a member (questions to answer, codes to review or approve). An agent's
acknowledgement says it is an automated agent.

### `GET /api/encounters`

`{"encounters": [{id, title, state, state_label, service_date, insurance, created_at, kind: upload|paste}]}`, newest
first.

### `POST /api/encounters` (multipart; owner or reviewer)

Fields: `file` (PDF, DOCX or TXT, at most 15 MiB) or `text` (a paste, at most 400,000 characters) - exactly one;
`title`; `service_date` (`YYYY-MM-DD`, optional); `insurance` (optional, `unknown` when left out);
`synthetic_attestation` (`yes`, required); `client_key` (a UUID per upload attempt: a repeat within 24 hours answers
with the encounter the first made). Answers `201 {"id": "..."}`; coding round 1 is queued in the same transaction.

### `GET /api/encounters/<id>`

```text
{id, title, created_at, updated_at, state, state_label,
 permissions: {can_review},
 document: {name, media_type, size, kind, original_url, view_url, view_media_type, converted},
 context: {service_date, insurance},
 progress: {phase, busy, started_at, finished_at, server_time, message, can_stop, can_resume, can_retry,
            error: {text} | null},
 round: {number, trigger, finished_at} | null,
 codes: [{line, code, units | null, modifiers[] | null, status, status_label, reason,
          second_check: {agrees: true|false|null, reason},
          question | null, quotes: [{text, page}],
          decision: {id, action, by, at, note} | null, allowed_actions[]}],
 questions: [{id, text, codes[], lines[]}],
 answers: [{question, answer, by, at}],
 notes: [string],
 readiness: {draft, approved, blockers[]},
 reports: [{id, kind, fmt, filename, generated_at, download_url, current}],
 activity: [{at, text}]}
```

- Only the latest round is shown; while it is queued, running, failed or stopped it has no codes, questions or notes.
- `document`: `original_url` is an upload's download (null for a paste); `view_url` is the in-page view (`?view=1`);
  for a Word document the view is the PDF the coding review read (`converted: true`, once a round has converted it).
  `size` is the upload's exact number of bytes, or for a paste the bytes of its text in UTF-8, so for a text it is the
  exact size of the view (the review page checks its frame of the view against it).
- `codes[]` is one row per line: its `decision`, `quotes` and `allowed_actions` are that line's; `decision.id` is what
  an undo names. `units` is the whole number the coding review wrote (0 included: it writes 0 on a code it does not
  support), or null when it gave none; `modifiers` are its modifiers as written (a blank item, which carries nothing,
  is left out), or null when it gave none (the page shows "not given"; `modifiers: []` is the coding review saying
  there is none).
- `codes[].quotes` are the passages the coding service itself cited from the document under that line (pages for a
  PDF); only for a line with none, the quotes its answer gave. `second_check.agrees` is null, with CPT Studio's own
  sentence as the reason, for a code the second check added (the sentence says the status it gave the code), a code it
  did not review, or a line whose only reviews could not be tied to it (one names the line or its code but not both, or
  names no line at all); for a verdict that is neither exactly agree nor exactly disagree it is null too, and the
  reason opens with "The second check did not give a clear verdict." (never "disagrees") before the review's own. A
  review that names no line, or one that does not exist, sends every line carrying its code to `needs_review` - or
  every line of the round when no line carries it: the code never picks a line for it.
- `questions[]`: the coding review is asked to write each question once, and its code lines refer to a question by its
  number. A question's number links code lines to every question that carries it among the questions the line's author
  was shown (a number on a line of the coding review reaches the coding review's questions only; one the second check
  gives reaches the coding review's and its own); only identical text (case and spacing aside) makes two questions one.
  A question written again in other words is therefore shown again. A question several codes refer to is one question
  naming all their lines, and one answer to it covers every line it affects. `lines` are the lines a question affects
  and `codes` those lines' codes; a `needs_answer` line always has at least one question. A question whose text is blank
  is never served: nothing is left of it once byte-order marks and white space are removed, white space as Python reads
  it (every character the page's trim() removes, and also U+001C to U+001F and U+0085, which the page would show).
- `codes[].question` is the line's own question text, then the text of the questions the line's own references name,
  one per line of text. A question that names the line only in `questions[].lines` is not repeated there.
- `allowed_actions`: `approve` and `reject` for a `ready` or `needs_review` code; none for `needs_answer` (answer first)
  or `not_supported`; `revoke` while a decision stands; none at all for a viewer.
- `notes` are the coding review's documentation notes, then one note for each review of the second check that could
  not be tied to one line: "The second check made a comment that could not be tied to one line: <its reason>".
- Reasons, questions and notes are the coding review's own words, with any vendor or model name replaced by "the
  system"; codes, modifiers, statuses and quotes are never changed.
- `readiness`: a draft once the latest round is done; the approved export once a code of it is approved; `blockers`
  say why not.
- `reports[].current` is false for an export made from an earlier round, or before a later decision.
- `activity` is a fixed set of sentences (uploaded, answered, finished, approved, stopped, ...), oldest first; a
  decision names its line with its code ("Reviewer approved L2 45380.").

### `POST /api/encounters/<id>/answers` (owner or reviewer)

`{"answers": [{"question_id": "...", "text": "..."}]}` - ids from the latest done round's `questions`, each answer 1 to
2,000 characters, at most 50 at once. Answers `201 {"round": {number, trigger: "answers", finished_at}}`: the answers
are stored and a new round is queued with every answer so far in its context. A question id of an earlier round is
refused (reload).

### `POST /api/encounters/<id>/decisions` (owner or reviewer)

`{"round": 2, "line": "L2", "code": "20610", "action": "approve|reject|revoke", "acknowledgement": "...",
"note": "...", "decision": "..."}` - `round` is the round number the page shows, `line` and `code` the row decided; an
undo (`revoke`) names in `decision` the `id` of the decision it undoes, as the page shows it. An approval needs
`acknowledgement` equal to the session's text exactly; a note is optional (at most 2,000 characters). Answers
`201 {id, line, code, action, by, at, note}`. Refused: no round, line or code named, or an undo naming no decision
(400); `round` is not the latest round's number, or the latest round is not done, or an undo names a decision that is
not the line's current one (409 "This coding review has changed. Reload to see the latest.", `details` empty); the line
is not in that round, or holds another code (409 "That code is not part of this coding review. Reload to see the
latest."); the line already has a decision (409: revoke it first); a `needs_answer` or `not_supported` line (409).

### `POST /api/encounters/<id>/stop` | `/resume` | `/retry` (owner or reviewer)

- `stop`: `200 {"stopped": <jobs>}` - queued work is cancelled; a step already sending finishes, nothing after it starts.
  `409` when nothing runs.
- `resume`: `201 {"resumed": true}` - the stopped round continues, reusing any read it already has. `409` when there is
  no stopped round.
- `retry`: `201 {"round": {...}}` - a new round (trigger `retry`) of a failed latest round, or of an earlier review.
  Not offered for a round that failed at its spending limit (the same document would meet it again).
- Neither is offered, and both answer `409 "Whether the last coding finished is not known yet. It can run again once
  it has been checked."`, while a request of the round may have reached the coding service with its outcome unknown
  and no platform operator has reconciled it.

### `POST /api/encounters/<id>/reports` (any member)

`{"kind": "draft|approved", "fmt": "pdf", "round": 2}` - `round` is the round number the page shows ->
`201 {id, kind, fmt, filename, generated_at, download_url, current}`, the file named
`CPT-Studio-<kind>-r<round>-<UTC time>.pdf`. The PDF is the only report made (owner direction 2026-11-21). Refused: a
kind that is not one, or any format but `pdf` (400 "Choose a draft or an approved PDF report."); no round named (400); `round` is not the latest round's number (409 "This coding
review has changed. Reload to see the latest.", `details` empty - checked before readiness, so a page left open never
downloads a round its member did not see); `409` with `details.blockers` when the export is not available yet; `503`
"The PDF could not be made. Nothing was saved. Try again." when a PDF cannot be made: nothing is stored and no audit
row is written, so the same request can be sent again.

The report is made from the saved rows - the latest round, each line with its own current decision - and is stored
once, as made: an immutable export and its `export.created` audit row. Making one reads saved rows only: it changes no
decision, round or state and sends nothing to the coding service. Format `cpt-studio-customer-export@3`:

- **PDF** (`application/pdf`; the doctor-facing report, owner directions 2026-11-21): a searchable US Letter document
  with its fonts embedded, whose every page shows its status (DRAFT · REVIEW REQUIRED, or APPROVED CODES), the
  document's title, its encounter reference and the coding review, and its page number of the total. A draft lists
  every line of the round in stored order with its status, units, modifiers and current decision (who made it and
  when), its evidence (the document's own quoted words with their pages; a line with no citation shows the coding
  review's own quotation, marked as such), its reason and the second check; then what still needs a decision (the
  round's questions and the lines with no saved decision) and the documentation notes. An approved PDF lists only the
  lines whose current decision is an approval, each with who approved it and when, says how many lines of the round it leaves
  out, and has no questions, second checks or notes. An approval by an automated agent says it is not clinical
  approval. A value the record does not hold reads "Not recorded" or "Not given", never a guess; no patient identifier
  is printed (the record has none). No vendor or model name, provider, run, usage or log field reaches it: text the
  coding review wrote passes the same filter as the page. Two PDFs of the same saved state read the same but for their
  Prepared line (when, and by whom, each was made) and the PDF's own date.
- TXT and CSV exports made before 2026-11-21's direction (no more TXT or CSV) are records: they stay listed, with
  their format, and download exactly as stored (`text/plain` or `text/csv`); none is made again.

The approved report lists only the lines whose current decision is an approval and whose status is `ready` or
`needs_review`, each with who approved it, their kind and when. Units or modifiers the coding review did not give read
"Not given" and "Modifiers: not given".

### `GET /api/encounters/<id>/original` and `?view=1`

Without `view`: the uploaded original as an attachment, exactly as stored (`404` for a paste). With `view=1`: what the
in-page viewer shows (the PDF or text, the pasted text, or a Word document's converted PDF), `Content-Disposition:
inline`, `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'`. A stored file that no longer
matches its sha256 answers `409`. The review page fetches a PDF view itself (same origin, the session's cookie) and
draws it with its pinned PDF library, marking a chosen quote's words on its page; where the browser cannot run that
library, the library does not work or answer in time, it cannot draw the document, or the download fails or stalls, the
page frames this address instead, a new frame at `#page=N` for a quote on another page, and says why. A text view is
shown in a frame of this address and its passages marked there; a frame that does not hold the view (an answer other
than `200`, a body whose positive size is not `document.size`, or an answer the frame refuses to show) is never
searched, and the page says the document could not be downloaded; a frame whose load never ends (stopped, or its body
broken off) is waited for, and nothing new is said (a note from an earlier choice stays until the next one). The rule is
[`CORE-UX-DESIGN.md`](CORE-UX-DESIGN.md) section 8, "Marking a quoted passage"; this endpoint and the contract are
unchanged by it.

### `GET /api/reports/<id>/download`

The stored export, byte for byte, as an attachment with its format's content type, `Cache-Control: no-store` and no
hash header; `404` outside the caller's workspaces. An export is never made again on download: one made from an earlier
round, or before a later decision, is served exactly as it was made and listed with `current: false`.
