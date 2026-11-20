# CPT Studio - architecture

Owner directive: `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`. The coding design is the owner's ruling of
2026-11-20 (DECISIONS D351-D353): no line of the earlier deterministic coding code remains; Claude Fable 5.2 reads the
original document and decides the codes; one Fable reader and one independent Fable checker per document. If the code
and this file disagree, one of them is wrong - fix it.

## 1. What it is

A standalone, login-protected, **synthetic-only** website at `cpt.quillmd.com`. A member uploads an original clinical
document (PDF, DOCX or pasted text) with the practice's date of service and insurance; the coding step returns CPT codes
with units, modifiers, a status, a reason, the second check's verdict and the passages of the document it cited; the
member answers questions, approves or rejects codes, and exports a draft or the approved codes.

Independent of the QuillMD rebuild: no imports from `rebuild/`, no shared database, users, files, venv, units or
environment.

Non-goals: real patient data, claims submission, licensed CPT descriptors, NCCI procedure-to-procedure edits, accuracy
claims.

## 2. Truth rules

1. **Fable's decision is final apart from the human.** No code holds, drops, downgrades or upgrades a code the coding
   step returned. The only glue logic is the combination of the two reads (5.3) and display hygiene (5.10).
2. **No automatic resend of a paid request, ever.** The SDK client retries nothing (`max_retries=0`); a round reuses a
   read it already paid for; an outcome that may have reached the vendor is `unknown`, and no one may resume or retry
   its round until an operator has reconciled it (5.4).
3. **Never fabricate.** No descriptor text (none is licensed), confidence figure or source that the system does not
   hold. A field of the wrong shape is dropped from display, never corrected.
4. **Credentials are read from the file settings names, by path**, at send time; never printed, logged, stored in a row
   or put in an exception message.
5. **The customer never sees a vendor or model name**, tokens, costs, hashes, request ids or the word provider. Operators
   see them under `/ops/`.
6. **Agent review is labelled as agent review** wherever it appears.
7. **Synthetic only.** `SYNTHETIC_ONLY = True` is a constant; every upload needs an explicit synthetic attestation; every
   export says SYNTHETIC at both ends.
8. **Old tables stay untouched.** Migrations are additive only (the installer's gate); the earlier pipeline's model
   classes stay as legacy records (5.11).

## 3. Stack and layout

Django 5.2 on PostgreSQL 17, gunicorn behind the host's nginx, one worker process. Python 3.12 in one image
(`deploy/Dockerfile`, with LibreOffice Writer for Word files); `ops/install.py` installs it.

| path | what |
|---|---|
| `cptstudio/` | settings (every environment value is a `CPT_STUDIO_*` variable), URLs, WSGI |
| `studio/models.py`, `studio/migrations/` | the data model (4); migrations 0001-0016 |
| `studio/intake.py`, `studio/storage.py` | creating an encounter from an upload or a paste; the immutable original store (5.1) |
| `studio/jobs.py`, `studio/management/commands/run_worker.py` | the job runner, the worker and the coding stage (5.2) |
| `studio/fable/` | the coding step: request, send, document block, prompts, parsing, combination, citations, pricing (5.3) |
| `studio/state.py` | the encounter's derived state (5.6) |
| `studio/decisions.py` | decisions, answers and retries (5.7) |
| `studio/exports.py` | the customer exports (5.8) |
| `studio/customer.py`, `studio/api.py`, `studio/client_contract.py` | the customer JSON API ([`API.md`](API.md)) |
| `studio/operator.py`, `templates/studio/ops_*.html` | the platform-operator console (5.9) |
| `studio/views.py`, `studio/access.py`, `studio/audit.py` | health, sign-in, the page shell, tenancy, security headers, the audit trail |
| `studio/static/studio/`, `templates/studio/index.html` | the customer page ([`CORE-UX-DESIGN.md`](CORE-UX-DESIGN.md) 8) |
| `studio/reference/` | CMS reference sources and passages (5.5) |
| `studio/bounded.py` | work in a forked child under a wall clock and a memory allowance |
| `ops/` | installer, rollback check, sign-in verifier, browser walk (not in the image) |

## 4. Data model (`studio/models.py`)

Tenancy and accounts: `Category`, `Workspace` (`synthetic_only`), `User` (`actor_kind` human or agent), `Membership`
(owner, reviewer or viewer; owners and reviewers may change things), `LoginAttempt` (the sign-in throttle),
`OperatorGrant` / `OperatorRevocation` (append-only; the only way into `/ops/`).

The document: `Encounter` (title, `user_values` holding the practice's `service_date` and `insurance`, the derived
`state`, the member's Stop, the upload's `client_key`), `SourceFile` (the original's name, media type, size, sha256 and
storage name) and `SourceRevision` (immutable: an upload or a paste, with the synthetic attestation).

The coding path (migration 0016, additive):

- `CodingRound` - one coding of a revision: `number` (unique per encounter), `trigger` (`upload`, `answers` or `retry`),
  the `context` it was coded with (`{service_date, insurance, answers: [{question, answer}]}`), `state` (`queued`,
  `running`, `done`, `failed`, `cancelled`), its `reader_run` and `checker_run`, their parsed results, the combined
  `codes`, `questions`, `problems` and `citations`, `failure_kind` and the customer's `error` sentence, and for a Word
  document the PDF it was converted to (`view_pdf_storage_name`, `view_pdf_sha256`).
- `CodingAnswer` (immutable) - a member's answer to a question a round asked (at most 2,000 characters).
- `CodeDecision` (immutable, append-only) - `approve`, `reject` or `revoke` on one code line of one round (its `line`,
  `L1`.. or `M1`.., and the `code` it holds), by a reviewer of a kind, with the attestation an approval carries; ordered
  by the shared `studio_decision_sequence`. The current decision for (round, line) is the latest row; `revoke` clears
  it. Two lines may hold one code and are decided apart.
- `ExportArtifact` (immutable) - one export (`draft` or `approved`, `txt` or `csv`) stored as generated, with its sha256.

The runner and its record: `Job` (kind `code`, keyed `code:<round>`; a Resume adds a fresh job for the same round),
`ProviderRun` (one per send: purpose `coding_reader` or `coding_checker`, provider `anthropic`, the request with the
document's base64 replaced by `{"$original_sha256", "$original_bytes"}`, the final message, usage, latency, state
`reserved` -> `sending` -> `succeeded` / `failed` / `unknown` / `not_sent` / `cancelled`, and any reconciliation),
`InterpreterHold` / `InterpreterHoldRelease` (an account refusal and the operator's release), `WorkerBeat` (the
worker's heartbeat), `AuditEvent` (immutable).

Immutable rows refuse updates and deletes through the ORM, bulk ones included; a correction is a new row.

## 5. Modules

### 5.1 Intake and the original store

`intake.create_encounter` is the one place an encounter is made: the attestation, the original stored once, the first
revision and coding round 1, in one transaction. A repeated POST of one upload attempt (`client_key`) within 24 hours
answers with the encounter the first made. A file is a PDF, a DOCX or plain text (its name and first bytes must agree),
at most 15 MiB; a paste at most 400,000 characters. `storage.store_original` writes each original once under `ORIGINALS_DIR/<workspace>/` (random name, 0600,
exclusive create) and verifies its sha256 on every read, so a changed file is refused rather than served.

### 5.2 Jobs and the worker

upload, answers or retry -> `jobs.start_round` (round n+1, queued, with the context as it is now) -> Job `code` ->
`stage_code`: prepare the document -> READER send -> CHECKER send -> combine -> round done -> encounter state.

The worker (`run_worker`) is one process running `CPT_STUDIO_CONCURRENT_DOCUMENTS` threads (default 4), each claiming
queued jobs with `SELECT ... FOR UPDATE SKIP LOCKED` on its own connection. One chain per encounter: every action that
queues a job holds the encounter row lock and refuses while one is queued or running. Each send takes one of N provider
slot locks without waiting (none free: the job is queued again after 2 s; the process also counts its own sends in
flight, so a send whose database session ended keeps the other threads out), checks a member's Stop, a standing hold
and the spending ceiling (5.4), and is reserved in the database before any network I/O. A round reuses a run it already
paid for after a crash between sends. A job that cannot start within 120 minutes expires (resumable). The stale sweep
settles what a dead thread left running as its stage would have settled it (`jobs.abandoned_outcome`): a send in
flight becomes `unknown` and fails its round, as does an earlier `unknown` no operator reconciled; a send that failed
fails the round with its own kind; only a round with nothing it sent unsettled is cancelled, for a Resume. The worker
beats every 30 s; a beat older than 120 s reads as processing paused on the page.

### 5.3 The coding step (`studio/fable/`)

- `client.py` - Anthropic's official SDK (`anthropic==2.11.0`, `max_retries=0`), one streamed send per request:
  `claude-fable-5-2`, `max_tokens` 96,000, `output_config.effort` from `CPT_STUDIO_CODING_EFFORT` (default `max`), the
  server-side fallbacks in their default form. Outcomes: a final message is `succeeded`, or `failed` for stop reason
  `refusal` (declined) or `max_tokens` (too long); an HTTP or stream error is `failed` with its status and type; a
  timeout or lost connection after the request started is `unknown`. A message served by a fallback is recorded as such
  (operators see it). Modes (`CPT_STUDIO_CODING_MODE`): `disabled` (default), `replay` (recorded messages by request
  sha256), `live`.
- `credentials.py` - the credentials file read strictly as data: a regular file, not a symlink, owner-only, at most
  32,000 bytes, `ANTHROPIC_API_KEY` required, `ANTHROPIC_WORKSPACE_ID` optional.
- `document.py` - the original as the API reads it: a PDF as a base64 document block with citations; a Word file
  converted to PDF by LibreOffice in a bounded child (60 s, a memory cap, a throwaway home and profile, no inherited
  environment), then sent as a PDF; text and pastes as a text document block. No local PDF parsing.
- `prompts.py` - the reader's and checker's instructions; the practice's date of service, insurance and earlier answers
  travel in the user text, outside the document; the checker also gets the reader's code list and the reader's
  questions with their ids. Each question is written once, in the answer's top-level `questions`, with an id (the
  reader's `Q1`, `Q2`..., the checker's new ones `C1`, `C2`...) and the lines it concerns in `affects`; a code, a review
  and a missed code name the questions they depend on in `question_ids` instead of writing a question of their own, and
  the checker refers to a question the reader already asked instead of writing it again (D370, D372).
- `result.py` - the final JSON is the LAST fenced block of the joined text, whatever its fence (three or more backticks
  or tildes, any info string or none, any case); when it does not parse as strict JSON, the widest `{...}` span, read
  only when it reaches that block (never an earlier block); text after the last block that holds a `{` is unreadable
  too, since the code cannot tell which answer is final. Strict JSON: a repeated key, NaN, Infinity, a number too large
  to be finite, a NUL character or a lone surrogate make it unparseable. Anything unreadable fails the round
  (`unreadable`), never resent. The shape only is checked and only lossless conversions are made: modifiers are a list
  of strings (an integer item read as its decimal string, a blank item - which carries nothing - removed) or not given;
  units a whole number as written (0 included; a string of digits read as its number) or not given; a reason list
  joined; a question list one question each; a line label the reader writes on its own items must be its place in the
  list; any other shape is unreadable, never corrected or guessed. **Lines**: every code row has one - `L1`..`Ln`, the
  reader's codes in its order, then `M1`..`Mk`, the checker's additions - and the checker is given each line and names
  the line of every review. **Combination**, the only glue logic: a reader line keeps the reader's status only when the
  reviews naming that line and its code all say `agree` (at least one) and no other review names the line or its code;
  otherwise `needs_review`, both reasons kept. A review that names no line, an unknown line, or a line with another code
  is kept for the operator, shown to the customer as a note on the encounter with its reason, and sends every line it
  names, or whose code it carries, to `needs_review` - or every line of the round when it reaches none that way: the
  code never picks a line for it. A verdict that is neither exactly `agree` nor exactly `disagree` is no clear verdict,
  and the line needs review. Every code the checker found missing is a line of its own, `needs_review`. The questions
  are the reader's, then the checker's, then each line's own question text not yet asked (today's shape); two
  questions are one only when their text is the same with case and spacing folded - nothing reads what a question
  means, and a repeated id stays two questions. Each question names the lines it affects: its `affects`, every line and
  missed code whose `question_ids` names its id, and the lines of every review whose `question_ids` does (an id names
  every question carrying it, case-insensitively, among the questions its author was shown: the reader's for a reader
  line, the reader's and the checker's for the checker). An id that names no question carries no text and is listed on
  the operator console; any shape of `question_ids` is read without failing the round. A code row shows the text of the
  questions it names, one per line. A `needs_answer` line no question names by its affects or its text gets its
  agreeing reviews' own questions (as before), or - when none, and no id names it either - CPT Studio's own. Answers in
  the earlier shape (a question text on each line or review, questions without ids) read exactly as before. The
  problems are the reader's. **Citations**: a whole line `LINE L<n> <code>` (reader), `REVIEW L<n>
  <code>` or `MISSED M<k> <code>` (checker) starts that line's section; a citation after it is filed under the line when
  the marker's code is that line's code, else under `_document`. A section also ends at a line holding exactly `END`
  (both answers are asked to end their last section with one), at the start of the final answer, at a heading, a
  thematic break, a code fence or a line that only looks like a marker; a cited block whose own text holds a section
  change is filed under `_document`. Without `END`, a plain paragraph after the last section stays in it: a known limit,
  since telling it apart would mean reading its meaning.
- `pricing.py` - claude-fable-5-2's rates (input $8, cache write $10, cache read $0.20, output $40 per million tokens),
  a run's cost priced from its usage at read time, and a send's worst case over every attempt it may make (two with the
  server-side fallbacks, the second also reading the first's partial answer; a fallback model never costs more).

### 5.4 Spend, holds and unknown outcomes

Spend: before each send, the priced cost of every run already on the revision (the checker's and billed failures
included) plus this send's worst case - from the API's own count of its input tokens - must stay within
`CPT_STUDIO_DOCUMENT_CEILING_USD` (default 25), or the round fails `ceiling` and is not offered again. When the count
fails nothing is sent and the round fails `busy`; there is no byte estimate. Holds: an authentication, permission,
billing or quota refusal records an `InterpreterHold`; while one stands nothing is sent and rounds fail fast (`hold`)
until an operator releases it. A rate limit or overload fails the round `busy`, for a member's retry. An `unknown` run
fails its round and counts against the ceiling at its reserved worst case; Resume and retry of its round wait for an
operator's reconcile (who looked, what they found): until it is recorded the page offers neither, the API refuses both
(`jobs.RECONCILE_FIRST`) and the console offers no retry.

### 5.5 Reference sources (`studio/reference/`)

CMS reference data, installed by management command and never read by the coding path: `import_reference` reads the
PFS RVU and practitioner MUE files (sha256 checked before opening; code-keyed facts only, descriptors never imported) and
`store.py` answers date-applicable lookups (a source applies only inside its effective window; two covering one date are
ambiguous and neither is used); `import_passages` loads the bundled, sha256-pinned CMS policy passages
(`reference/data/`), which `passages.py` reads and stores. The retrieval that read passages for a code, with its
dormant endoscopy code-family rule set, was deleted (FIX-SPEC-2 section 8): nothing reads a passage for a code, and no
code-family or code-range rule is kept anywhere (`tests/test_no_rule_engine.py`).

### 5.6 Encounter state (`studio/state.py`)

Written to `Encounter.state` after every job, decision and answer, from the latest round: `processing` (queued or
running), `stopped` (cancelled), `failed`, and once done `awaiting_answer` (a line needs an answer), `needs_review` (a
needs_review line undecided), `ready` (a ready line undecided), `reviewed` (every ready and needs_review line decided)
or `no_codes`. Decisions count per line. An encounter with
no round (a record of the earlier system) reads as an earlier review; Review again codes it.

### 5.7 Decisions and answers (`studio/decisions.py`)

An owner or reviewer decides one line of the latest done round, naming the round the page shows, the line and its code:
a round that is not the latest done one, or a line that round does not hold with that code, is refused (409; the page
reloads). A `ready` or `needs_review` line may be approved or rejected, a `needs_answer` line is answered first, a
`not_supported` line is never decided, a decided line may only be revoked - and an undo names the decision it undoes
(the id the page shows), refused as changed (409) when that is no longer the line's current decision. An approval
carries the review attestation for the reviewer's kind, exactly. Answers name the round's own question ids (a page left
open on an earlier round is refused), are stored as `CodingAnswer` rows, and start a new round with every answer so far
in its context. A failed round (not one stopped at the ceiling) may be retried as a new round once no send of it awaits
a reconcile (5.4).

### 5.8 Exports (`studio/exports.py`)

`cpt-studio-customer-export@3`, from the latest round, which the request names (the round the page shows; another is
refused as changed, 409, before readiness is read). TXT opens and closes with the SYNTHETIC banner and states the
encounter, round, date of service, insurance and who made it when; a draft lists every code with its status, units,
modifiers, reason, the second check and quotes with pages, then the questions and documentation notes; the approved
export lists only the lines whose current decision is an approval and whose status is ready or needs_review, with
approver, kind and time. Units or modifiers not given read "not given". CSV (RFC 4180) has the columns kind, code,
units, modifiers, status, reason, quotes, decision, decided_by, decided_at, banner rows, and formula cells neutralised;
in both formats control, bidirectional and line-separator characters are shown escaped. Each
export is stored once as an `ExportArtifact`; a download serves the stored bytes; one made from an earlier round stays
listed, marked earlier.

### 5.9 The operator console (`studio/operator.py`)

Server-rendered pages under `/ops/` for users holding an operator grant (from `grant_operator` only; no workspace role
confers it). Everyone else - signed out, any member, a revoked operator - gets exactly an unknown URL's 404 before the
method, body, CSRF token or any record is read. Pages: every encounter across workspaces (state, rounds, latest cost),
and one encounter's rounds, runs (models, served by a fallback, tokens, cost, latency, state), the reader's and checker's
whole answers, codes and decisions by line, the reviews tied to no line, the question ids that name no question (read
from the two stored answers, so every stored round shows them), answers, audit events and the original with its
sha256. Acts (POST, CSRF):
reconcile an unknown run (a note of at least 12 characters), retry a failed round (not offered while a send of it awaits
that reconcile), release the standing holds. Views are audited.

### 5.10 Display hygiene

Text the coding review wrote (reasons, questions, notes, and the evidence quotes its answer gave for a line the API
cited nothing for) is escaped and shown as written; a server-side filter (`customer.shown`) replaces vendor and model
names - the shared denylist's name rules, `ops/verification/customer-denylist.json` - with "the system" and changes
nothing else. Codes, modifiers, statuses and the document's own cited passages are never touched. A platform
operator's act reads as "CPT Studio" in the customer's activity.

### 5.11 Legacy records

The earlier pipeline's tables (contexts, routing runs, event inventories, assessments, proposals, clarifications,
decisions, member answers, report artifacts, provider holds, exchanges and tool calls) stay with their model classes,
marked in `models.py` as read by nothing in the coding path, so old rows survive and an older revision can still be
switched back to. Nothing writes them.

## 6. Security

Session authentication with Argon2 password hashes and a sign-in throttle (8 failures per username, 24 per client, in 15
minutes); CSRF on every POST; `Cache-Control: no-store` on everything but static files; a Content-Security-Policy with
`script-src 'self'` and no inline script (the page shell adds `frame-src 'self'` for the document viewer, and only the
in-page view of an original may be framed, by CPT Studio's own pages); `X-Frame-Options: DENY` elsewhere. Every customer
query is scoped through the caller's active membership, so another workspace's records answer 404. Text the database
cannot store (NUL, a lone surrogate) is refused with a 400 rather than altered; only a title or a file name has it
replaced.

## 7. JSON API

[`API.md`](API.md): session auth, the client contract header, every endpoint and payload.

## 8. The customer page

[`CORE-UX-DESIGN.md`](CORE-UX-DESIGN.md) section 8: the DOM and copy contract the browser walk checks.

## 9. Verification

- The Django suite (`manage.py test tests`): the coding step with fake SDK streams and a fake converter, the job runner
  (reuse after a crash, unknown outcomes, the ceiling, holds, Stop, threads and slots), the API contract and tenancy,
  decisions, answers, exports, the operator console, the page's templates and node tests, and the reference data.
  Synthetic text only; nothing is sent.
- CI (`scripts/ci/verify-cpt-studio.sh`): checks, migration drift, the Django suite, the ops unit suites, the browser
  walk's own tests (`ops/test_walk.cjs`) and a dependency audit.
- After an install, `ops/walk.cjs` drives the real page with a synthetic document: upload, poll, the DOM and JSON
  contract, an answer, an approval through the dialog, both exports re-downloaded byte for byte, the denylist scan, a
  390 px viewport, and every `/ops/` path refused to the customer.

## 10. What was removed

Lane E of the Fable coding build removed the earlier pipeline (DECISIONS D351-D352): text extraction and OCR, the GI
routing and context readers, the Corti adapter, the harness participants (Astra, Fable 5.1), the Gemini and Fable 5.2
interpreter with its event engine, validation, the review overlay, the earlier reports and customer API, their commands
and their tests. They remain in git history; their tables remain as legacy records (5.11).
