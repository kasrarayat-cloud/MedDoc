# CPT Studio customer API

Client contract `customer-2026-11-21` (`studio/client_contract.py`; the fix pass's line identity). Handlers:
`studio/api.py`; every payload is built by `studio/customer.py` from stored rows on each request.
`ops/verification/customer-contract.json` lists the keys and `ops/verification/customer-denylist.json` what a customer
response may never carry; the browser walk (`ops/walk.cjs`) holds the deployed site to both.

## Conventions

- **Session authentication** (`/login/`). A call without a session answers `401 {"error": "Sign in to continue."}`.
- **The client header.** The page sends `X-CPT-Studio-Client: customer-2026-11-21` on every API call. A call without it,
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
 "workspace": {"id": "...", "name": "..."}, "role": "owner|reviewer|viewer", "can_review": true,
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
          decision: {action, by, at, note} | null, allowed_actions[]}],
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
- `codes[]` is one row per line: its `decision`, `quotes` and `allowed_actions` are that line's. `units` is null and
  `modifiers` null when the coding review gave none (the page shows "not given"; `modifiers: []` is the coding review
  saying there is none).
- `codes[].quotes` are the passages the coding service itself cited from the document under that line (pages for a
  PDF); only for a line with none, the quotes its answer gave. `second_check.agrees` is null for a code the second
  check added or did not review, or when a review of the second check names the line or its code but not both, with
  CPT Studio's own sentence as the reason.
- `questions[].lines` are the lines a question affects and `codes` those lines' codes; a `needs_answer` line always has
  at least one question.
- `allowed_actions`: `approve` and `reject` for a `ready` or `needs_review` code; none for `needs_answer` (answer first)
  or `not_supported`; `revoke` while a decision stands; none at all for a viewer.
- Reasons, questions and notes are the coding review's own words, with any vendor or model name replaced by "the
  system"; codes, statuses and quotes are never changed.
- `readiness`: a draft once the latest round is done; the approved export once a code of it is approved; `blockers`
  say why not.
- `reports[].current` is false for an export made from an earlier round, or before a later decision.
- `activity` is a fixed set of sentences (uploaded, answered, finished, approved, stopped, ...), oldest first.

### `POST /api/encounters/<id>/answers` (owner or reviewer)

`{"answers": [{"question_id": "...", "text": "..."}]}` - ids from the latest done round's `questions`, each answer 1 to
2,000 characters, at most 50 at once. Answers `201 {"round": {number, trigger: "answers", finished_at}}`: the answers
are stored and a new round is queued with every answer so far in its context. A question id of an earlier round is
refused (reload).

### `POST /api/encounters/<id>/decisions` (owner or reviewer)

`{"round": 2, "line": "L2", "code": "20610", "action": "approve|reject|revoke", "acknowledgement": "...",
"note": "..."}` - `round` is the round number the page shows, `line` and `code` the row decided. An approval needs
`acknowledgement` equal to the session's text exactly; a note is optional (at most 2,000 characters). Answers
`201 {line, code, action, by, at, note}`. Refused: no round, line or code named (400); `round` is not the latest round's
number, or the latest round is not done (409 "This coding review has changed. Reload to see the latest."); the line is
not in that round, or holds another code (409 "That code is not part of this coding review. Reload to see the
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

`{"kind": "draft|approved", "fmt": "txt|csv"}` -> `201 {id, kind, fmt, filename, generated_at, download_url, current}`.
`409` with `details.blockers` when the export is not available yet. Format `cpt-studio-customer-export@3`: TXT between
SYNTHETIC banners; CSV (RFC 4180) with the columns kind, code, units, modifiers, status, reason, quotes, decision,
decided_by, decided_at, banner rows, formula cells neutralised, control characters shown escaped. The approved export
lists only the lines whose current decision is an approval and whose status is `ready` or `needs_review`, each with who
approved it, their kind and when. Units or modifiers the coding review did not give read "not given".

### `GET /api/encounters/<id>/original` and `?view=1`

Without `view`: the uploaded original as an attachment, exactly as stored (`404` for a paste). With `view=1`: what the
in-page viewer shows (the PDF or text, the pasted text, or a Word document's converted PDF), `Content-Disposition:
inline`, `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'`. A stored file that no longer
matches its sha256 answers `409`.

### `GET /api/reports/<id>/download`

The stored export, byte for byte, as an attachment; `404` outside the caller's workspaces.
