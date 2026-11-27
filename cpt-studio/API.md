# CPT Studio customer API

Client contract `customer-2026-11-26` (`studio/client_contract.py`; the fix passes' line identity, the id of each
decision shown, which an undo names, and the round an export names). Handlers:
`studio/api.py`; every payload is built by `studio/customer.py` from stored rows on each request.
`ops/verification/customer-contract.json` lists the keys and `ops/verification/customer-denylist.json` what a customer
response may never carry; the browser walk (`ops/walk.cjs`) holds the deployed site to both.

Release 2 (RELEASE-2-SPEC R2-15 to R2-21 and R2-24) pages the lists (`GET /api/encounters`), adds the search
(`POST /api/encounters/search`), a validator for the in-page view of a PDF (`ETag`, answered `304` when the page holds
it), `opens_pdf` on each list row, and the session carried by the page shell. A page of release 1 left open is told to
reload by the client header (below) before any of these is read, so it never reads a page as the whole list.

## Conventions

- **Session authentication** (`/login/`). A call without a session answers `401 {"error": "Sign in to continue."}`.
- **The client header.** The page sends `X-CPT-Studio-Client: customer-2026-11-26` on every API call. A call without it,
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
  or anything under `/ops/` (the platform-operator console, which answers a customer 404). An `ETag` on an `/api/`
  answer (release 2: only the in-page view of a PDF carries one) is a quoted UUID, never a hash; `ops/scan_customer.py`
  and the walk refuse any other.
- **Every read of a document is recorded** (release 1, C1): a page of a list or of a search, a document, its in-page
  view, its download and a report's download each write an access record - who, which practice and documents, when, from
  which address, sign-in and request - before the answer leaves. When that record cannot be written the answer is
  `503 {"error": "This could not be recorded, so nothing was shown."}` and nothing else. A document or report of another
  practice answers the same `404` as a missing one, and the attempt is recorded as refused. The page's poll of a
  document being coded (`X-CPT-Poll: 1`) is recorded at most once a minute per sign-in. `HEAD` is answered `405` by
  these reads. Release 2 (R2-21): a list's record names the documents of the page it served, in the order shown, with
  its list and cursor (never search words); the same page read again within a minute by the same sign-in, showing the
  same documents in the same order, is counted on that record. A re-open of the in-page view answered `304` is recorded
  too, as shown from the page's memory (R2-15).
- **A database that cannot be reached** (integrated refutation round 1, avail-0): a connection the database ended while
  the request ran, or one it refuses (a restart), answers `503` with `Retry-After: 5` and nothing of the request -
  under `/api/` `{"error": "This could not be recorded, so nothing was shown.", "details": {}}`, elsewhere a plain
  error page (`studio/db_unavailable.py`). A recorded limit (I1-20): a connection lost at the session's own save after
  the view, in Django's write of the session's row, is Django's own `400` (`SessionInterrupted`: an HTML page, no
  `Retry-After`), not this `503`; the view's answer is not sent then either, and a read's record, already written,
  says it was served. It is rare: a request writes its session only when it changed it, and under `/api/` that is only
  its activity time, written at most once a minute (`SESSION_ACTIVITY_WRITE_SECONDS`). Any other server error is
  `500`, as before. A connection the database ended between requests is replaced at the next request's first query
  and answers as usual (R2-7).
- **Limits** (release 1, C5): 10 reports made per member in 10 minutes and 60 per practice in an hour, 30 uploads per
  member in 10 minutes. Only a report actually made counts. The stored copy answered again (200) counts toward no limit
  and is never refused by one, and neither is a refused request. Over a limit, any of these calls answers
  `429 {"error": "rate_limited", "retry_after": <seconds>}`, with the same number in `Retry-After`; the page words it
  itself. Release 2 (R2-21): 120 later list pages and searches per member a minute (a first page and the Overview are
  not counted); over it the same `429`, with nothing read or recorded.
- **A destroyed document** (release 1, D1) is in no list or count, and its routes answer `404`.

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
 "role": "owner|reviewer|viewer", "can_review": true, "can_manage_team": false,
 "acknowledgement": "<the exact text an approval must send back>",
 "counts": {"documents": 3, "queue": 1}}
```

`can_manage_team` is true for an owner with access (release 1, C4; owner decision D15): the page then offers the Team
panel (`/api/members`).

`counts.queue` is the documents waiting on a member (questions to answer, codes to review or approve): the same rule
as the Review queue's list, so the two agree. An agent's acknowledgement says it is an automated agent.

Release 2 (R2-17): the page shell (`GET /`) carries this same payload, from the same function, in
`<body data-session-json="...">` (HTML-escaped JSON), so a page load needs no session request; the page asks for it
again at most once a minute on document opens, and after its own acts.

### `GET /api/encounters[?list=documents|queue|recent][&before=<cursor>]`

One page of a list (release 2, R2-19), newest first (`created_at`, then `id`):

```json
{"encounters": [{"id": "...", "title": "...", "state": "ready", "state_label": "Ready for approval",
                 "service_date": "2026-11-02", "insurance": "medicare", "created_at": "2026-11-20T08:00:00Z",
                 "kind": "upload|paste", "opens_pdf": true}],
 "next": "20261120T075959.123456Z~f5000000-0000-4000-8000-000000000001", "total": 117,
 "workspace": "fa000000-0000-4000-8000-000000000002"}
```

- `list`: `documents` (the default, with no `list`), `queue` (the documents waiting on a member: a state of
  `awaiting_answer`, `needs_review` or `ready`, and a coding round) or `recent` (the Overview's five).
- `documents` and `queue` hold 50 rows a page, `recent` 5. `next` is the cursor of the next page - a UTC time to the
  microsecond and an id, `<YYYYMMDDTHHMMSS.ffffffZ>~<id>`, a position only - or `null` when nothing follows (always
  for `recent`). Ask for the next page with `?before=<next>` (and the same `list`); there is no page size to choose.
- `total` is the list's exact number on a first page: the rows themselves when the whole list is on the page, else
  counted. It is `null` for `recent` and for a later page.
- `opens_pdf` (R2-16) is true when the document's first stored file is a PDF of at most 1 MiB, so the page may ask for
  its view at the click. A Word document's converted view is not hinted.
- `workspace` is the id of the practice the page was read in: the caller's active practice at that request (for a
  member active in two practices, the oldest active membership), as the page's read record names it. After the
  member's access changes, a later page or a search may be another practice's: the page keeps its first page's
  `workspace` and never draws a page or a search naming another, but reads the session and the list afresh
  (integrated refutation round 1, exact-0).
- An unknown `list`, a parameter given twice, or a cursor this API did not write (or any cursor on `recent`) answers
  `400 {"error": "That list is not available."}` or `400 {"error": "That part of the list could not be read. Open the
  list again."}`, with nothing read or recorded. Another practice's cursor shows only the caller's own documents.
- Each page is recorded before it leaves, naming its documents (above); a later page counts toward the member's limit.

### `POST /api/encounters/search` (any member)

`{"text": "<the words>", "before": "<cursor>"|null}` -> one page of the practice's documents whose row, as the page
draws it, holds the words (release 2, R2-20): the list's answer above (its `workspace` included), with `total`
`null`. The page uses it for a Documents list of more than 200 documents and searches a smaller list itself, with
release 1's rule.

- It is a POST, so the words never sit in an address, a query string or an access log; CSRF is required.
- The row's text is the page's: the title (or "Untitled document"), the kind, the insurance when it is shown, the
  state's label, and the service date as "6 Nov 2026" or "Not entered". The words match it as the page's own search
  does (lower-cased, trimmed), and nothing in them is a wildcard. Where a browser and the database lower-case a letter
  differently (a final sigma, a dotted capital I, 27 capitals new in Unicode 16.0 that PostgreSQL 17 does not
  lower-case: U+1C89, U+A7CB, U+A7CC, U+A7DA, U+A7DC and Garay's U+10D50-U+10D65, and 28 new in Unicode 17.0: U+A7CE,
  U+A7D2, U+A7D4 and Beria Erfe's U+16EA0-U+16EB8), the search finds those documents too: never fewer than the page,
  in a browser of Unicode 17.0 or earlier (a later one: see "Known limits" below).
- Text that is not text, or blank, answers `400 {"error": "Type the words to search for."}`; a text longer than 240
  characters, not counting the combining dot above (U+0307, which the page's lower-casing adds to a dotted capital I),
  or holding a character the database cannot store, an empty page; an unreadable `before` the list's `400`. A `GET`
  answers `405`.
- Every search counts toward the member's limit, and each page is recorded naming the documents found, with the list
  `search` and its cursor - never the words. It needs PostgreSQL 17 or newer.

### `POST /api/encounters` (multipart; owner or reviewer)

Fields: `file` (PDF, DOCX or TXT, at most 15 MiB) or `text` (a paste, at most 400,000 characters) - exactly one;
`title`; `service_date` (`YYYY-MM-DD`, optional); `insurance` (optional, `unknown` when left out);
`synthetic_attestation` (`yes`, required); `client_key` (a UUID per upload attempt: a repeat within 24 hours answers
with the encounter the first made). Answers `201 {"id": "..."}`; coding round 1 is queued in the same transaction.

### `GET /api/encounters/<id>`

```text
{id, title, created_at, updated_at, state, state_label,
 permissions: {can_review},
 document: {name, media_type, size, kind, original_url, view_url, view_media_type, converted, view_round},
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
- `progress.error.text` is a failed round's sentence. Release 2 (R2-31; lane D) adds two for a Word file refused before
  coding, each with `can_retry` true: "This Word file has another document inserted in it, which cannot be read here.
  Open it in Word, save it as a PDF and upload the PDF." and "This Word file has an embedded object that cannot be shown
  here. Open it in Word, save it as a PDF and upload the PDF."; any other refusal of a Word file keeps "The Word file
  could not be opened.".
- `document`: `original_url` is an upload's download (null for a paste); `view_url` is the in-page view (`?view=1`);
  for a Word document the view is the PDF the coding review read (`converted: true`, once a round has converted it).
  `size` is the upload's exact number of bytes, or for a paste the bytes of its text in UTF-8, so for a text it is the
  exact size of the view (the review page checks its frame of the view against it).
- `document.view_round` (integrated refutation round 1, viewer-0) is the number of the coding round whose conversion a
  Word document's view serves: the newest round that stored one, none once a later round refused the file - the file
  itself, or the round's own fresh conversion of it as too large to store or to send (I1-1, I1-18), when the document
  reads as one refused at its first round (`view_url` null, `converted` false). It is null for a PDF, a text, a paste
  and a Word document with no view. A later round that converts the Word file again (R2-28
  step 7, C8) serves another PDF at the same `view_url`, so the page redraws its viewer whole when `view_round` changes:
  its kept copy is asked for with its `ETag` (`304` the same bytes, `200` the new ones). So a round's codes are never
  drawn beside another round's conversion (only a finished round has codes, and it recorded its own view).
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
`201 {id, kind, fmt, filename, generated_at, download_url, current}`, or `200` with the same shape when a report of that
round, kind and format is still current (made from the latest round, no decision on it since): the stored copy is
returned, not made again, and an `export.reused` audit row records the request (release 1, C5). The stored copy
counts toward no limit. The PDF itself is recorded as a read when it is downloaded (`member.report_download`). The file
is named
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

Without `view`: the upload as an attachment, exactly as stored (`404` for a paste) - except a Word document, whose
download is the PDF its coding review read, the file the in-page view shows (release 1, C6). The Word file itself comes
only with `?format=original`, which the page asks for after warning that it can contain links and embedded content; a
Word document with no converted PDF yet answers the plain download `409` with `details.original_url`, and serves its
Word file only by that address. Each download is recorded with the format it served. With `view=1`: what the
in-page viewer shows (the PDF or text, the pasted text, or a Word document's converted PDF), `Content-Disposition:
inline`, `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'`. A stored file that no longer
matches its sha256 answers `409`. Release 2 (R2-15): a PDF view of a stored file carries `ETag: "<uuid>"`, derived with
the site's key from the sign-in, the document and the stored file's recorded hash - never a hash itself; a text or a
pasted view carries none. A request naming it in `If-None-Match` (the page sends it only for a copy it holds in its
memory; the weak form `W/"..."` matches, `*` never does) is recorded first, as shown from the page's memory, and answered
`304` with no body and no stored file read; another sign-in, another document, or a newer conversion of a Word document
gets the `200` with the bytes. Both answers stay `no-store`. The review page fetches a PDF view itself (same origin, the session's cookie) and
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

### `GET /api/members` (owners only)

Release 1, C4 (owner decision D15). `{"members": [member]}`, everyone with a membership in the owner's practice -
automated and operator-added accounts included - each:

```json
{"id": "...", "label": "Dr. Maya Rivera", "username": "mrivera", "role": "owner|reviewer|viewer", "active": true,
 "actor_kind": "human|agent", "last_sign_in": "2026-11-24T10:00:00Z", "password_change_required": false}
```

`active` is the person's access to this practice (the membership's: the switch an owner turns). `last_sign_in` is the
latest successful sign-in (null for none); `password_change_required` says a password staff set has not yet been
replaced. No password or hash is ever sent. A reviewer or viewer is answered `403`. `username` is a key the customer
denylist forbids in every other payload; a reader of this one exempts it.

### `POST /api/members/<id>/access` (owners only)

`{"active": false|true}` -> `200 {"member": member}`. It turns that person's access to this practice off or on
(the membership's, never the account's: a person in another practice keeps it). Refused: a body without a boolean
`active` (400), a reviewer or viewer (403), someone of another practice (404), the owner's own access or the practice's
last active owner (409). A person left with no active membership is signed out everywhere, and loses the practice at
their next request. Each change is an audit row naming the owner (`member.access_off`, `member.access_on`).

## Known limits

- **The search's letters** (release 2, R2-20; an accepted residual, D-R2-42). The search folds the letters a browser
  lower-cases and PostgreSQL 17 does not, up to Unicode 17.0 (`customer.SEARCH_NEWER`). A browser on a later Unicode
  release can lower-case a letter the server does not fold: its page's own rule then finds a document holding that
  letter in the other case, and the search does not, until `SEARCH_NEWER` is extended. It applies only above 200
  documents, where the page asks the server. `tests/test_lists.py` reads node and the Chromium builds of its host, and
  a committed table of Chromium 153's letters - never a member's browser - so a newer engine there fails the test and
  names its letters.
