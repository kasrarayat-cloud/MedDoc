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
   read it already paid for; an outcome that may have reached the vendor is `unknown` and needs an operator's reconcile
   or a member's retry.
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
- `CodeDecision` (immutable, append-only) - `approve`, `reject` or `revoke` on one code of one round, by a reviewer of a
  kind, with the attestation an approval carries; ordered by the shared `studio_decision_sequence`. The current decision
  for (round, code) is the latest row; `revoke` clears it.
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
slot locks without waiting (none free: the job is queued again after 2 s), checks a member's Stop, a standing hold and
the spending ceiling, and is reserved in the database before any network I/O. A round reuses a run it already paid for
after a crash between sends. A job that cannot start within 120 minutes expires (resumable). The stale sweep settles
what a dead thread left running: a send in flight becomes `unknown` and fails its round; anything else is cancelled for a
Resume. The worker beats every 30 s; a beat older than 120 s reads as processing paused on the page.

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
  travel in the user text, outside the document; the checker also gets the reader's code list.
- `result.py` - the final JSON is the last fenced json block (else the widest `{...}` span); anything unreadable fails
  the round (`unreadable`), never resent. **Combination**, the only glue logic: a reader code keeps the reader's status
  when the checker agrees, else `needs_review` with both reasons; every code the checker found missing is added as
  `needs_review`; the questions are the reader's then the checker's (an exact duplicate shown once); the problems are the
  reader's. **Citations**: a `CODE <code>` (reader) or `REVIEW <code>` (checker) line starts that code's section, and
  every citation after it is filed under the code.
- `pricing.py` - claude-fable-5-2's rates (input $8, cache write $10, cache read $0.20, output $40 per million tokens),
  a run's cost priced from its usage at read time, a send's worst case.

### 5.4 Spend, holds and unknown outcomes

Spend: before each send, the priced cost of every run already on the revision plus this send's worst case must stay
within `CPT_STUDIO_DOCUMENT_CEILING_USD` (default 25), or the round fails `ceiling` and is not offered again. Holds: an
authentication, permission, billing or quota refusal records an `InterpreterHold`; while one stands nothing is sent and
rounds fail fast (`hold`) until an operator releases it. A rate limit or overload fails the round `busy`, for a member's
retry. An `unknown` run fails its round and counts against the ceiling at its reserved worst case; an operator records
a reconcile (who looked, what they found), and a member may retry.

### 5.5 Reference sources (`studio/reference/`)

CMS reference data, installed by management command and never read by the coding path: `import_reference` reads the
PFS RVU and practitioner MUE files (sha256 checked before opening; code-keyed facts only, descriptors never imported) and
`store.py` answers date-applicable lookups (a source applies only inside its effective window; two covering one date are
ambiguous and neither is used); `import_passages` loads the bundled, sha256-pinned CMS policy passages
(`reference/data/`), which `passages.py` reads. `tools.py` is the executor the earlier pipeline's participants called;
nothing calls it now.

### 5.6 Encounter state (`studio/state.py`)

Written to `Encounter.state` after every job, decision and answer, from the latest round: `processing` (queued or
running), `stopped` (cancelled), `failed`, and once done `awaiting_answer` (a code needs an answer), `needs_review`,
`ready` (a ready code undecided), `reviewed` (every ready and needs_review code decided) or `no_codes`. An encounter with
no round (a record of the earlier system) reads as an earlier review; Review again codes it.

### 5.7 Decisions and answers (`studio/decisions.py`)

An owner or reviewer decides one code of the latest done round: a `ready` or `needs_review` code may be approved or
rejected, a `needs_answer` code is answered first, a `not_supported` code is never decided, a decided code may only be
revoked. An approval carries the review attestation for the reviewer's kind, exactly. Answers name the round's own
question ids (a page left open on an earlier round is refused), are stored as `CodingAnswer` rows, and start a new round
with every answer so far in its context. A failed round (not one stopped at the ceiling) may be retried as a new round.

### 5.8 Exports (`studio/exports.py`)

`cpt-studio-customer-export@3`, from the latest round. TXT opens and closes with the SYNTHETIC banner and states the
encounter, round, date of service, insurance and who made it when; a draft lists every code with its status, units,
modifiers, reason, the second check and quotes with pages, then the questions and documentation notes; the approved
export lists the approved codes with approver, kind and time. CSV (RFC 4180) has the columns kind, code, units,
modifiers, status, reason, quotes, decision, decided_by, decided_at, banner rows, and formula cells neutralised. Each
export is stored once as an `ExportArtifact`; a download serves the stored bytes; one made from an earlier round stays
listed, marked earlier.

### 5.9 The operator console (`studio/operator.py`)

Server-rendered pages under `/ops/` for users holding an operator grant (from `grant_operator` only; no workspace role
confers it). Everyone else - signed out, any member, a revoked operator - gets exactly an unknown URL's 404 before the
method, body, CSRF token or any record is read. Pages: every encounter across workspaces (state, rounds, latest cost),
and one encounter's rounds, runs (models, served by a fallback, tokens, cost, latency, state), the reader's and checker's
whole answers, codes, decisions, answers, audit events and the original with its sha256. Acts (POST, CSRF): reconcile an
unknown run (a note of at least 12 characters), retry a failed round, release the standing holds. Views are audited.

### 5.10 Display hygiene

Text the coding review wrote (reasons, questions, notes) is escaped and shown as written; a server-side filter
(`customer.shown`) replaces vendor and model names - the shared denylist's name rules,
`ops/verification/customer-denylist.json` - with "the system" and changes nothing else. Codes, statuses and quotes of
the document are never touched.

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
