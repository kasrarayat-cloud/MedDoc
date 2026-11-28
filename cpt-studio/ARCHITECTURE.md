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

Specialties (owner direction 2026-11-22, DECISIONS D390): Gastroenterology, Neurosurgery and Orthopedic Surgery, each a
workspace category provisioned the same way (`manage provision --specialty`; ops/INSTALL.md, provision). A workspace's
specialty is a label: the page names it (the upload form's Specialty field and the review heading, rendered from the
member's workspace) and so does the PDF report's Specialty cell. Nothing on the coding path reads it - Fable codes every
specialty, with no engine, code list, routing or specialty rule (D358), so a Neurosurgery or Orthopedic Surgery document
runs exactly the GI path. "Subcategories" are what they are for GI: the coverage of the synthetic verification
documents, not a choice a member makes and not rules. One login serves one workspace until a workspace switcher exists:
provisioning never adds an account to a second workspace. A workspace is found by its name exactly as stored; a new
one needs a name that does not name another specialty (read by its letters and digits, case aside) and that no workspace
of another specialty has exactly (ops/INSTALL.md, provision).

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

Django 5.2 on PostgreSQL 17 (17 or newer since release 2: the search matches text in PostgreSQL 17's builtin
`pg_c_utf8` collation, `customer.search_page`), Python 3.12 in one image (`deploy/Dockerfile`, with LibreOffice Writer
for Word files), run as three long-running roles - web, worker and converter - and one-shot management commands
(`deploy/entrypoint.sh`); `ops/install.py` installs it.

- **The web** (`deploy/gunicorn.conf.py`; release 2, R2-5 to R2-8): gunicorn behind the host's nginx, four sync
  processes and no threads, each serving one request at a time (`timeout` 120 s, `graceful_timeout` 30 s, `keepalive`
  5 s). gunicorn's master loads the application once, before it forks a worker (`preload_app`): `cptstudio/wsgi.py`
  builds it and calls `cptstudio.warm.warm_up`, which loads both hosts' URLconfs with every view module they name,
  compiles every page template, reads the static manifest and loads the password hasher's library and the password
  rules - reading no database, starting no thread and needing no network. Before the first fork `when_ready` closes
  every database connection (a worker forked holding one would share it) and freezes the loaded objects out of the
  garbage collector (`gc.freeze`); `post_worker_init` opens each worker's own connection before its first request, and
  a database that does not answer yet stops no worker. A worker is recycled after 10,000 requests plus a jitter of up to
  1,000 (`max_requests`, `max_requests_jitter`); its replacement is a fork of the warmed master, so no request waits for
  the application to load. A web whose application cannot load writes one fixed line to stderr, never the error's text,
  and does not start: `CPT Studio web: the application could not be loaded.` The container has 1 GiB of memory and no
  swap (memory and memory + swap equal), 128 pids and a 256 MiB `/tmp` (`ops/install.py` `WEB_LIMITS`, `hardening`).
- **No AI library in the web** (R2-4): `studio.jobs` imports the coder's sender (`studio.fable.client`, and the
  Anthropic SDK with it) only inside the three functions a worker's send runs (`_live_gate`, `_code`, `_send`); the
  worker's command imports it at its start (`studio/management/commands/run_worker.py`), and the installer's image phase
  loads both (`import cptstudio.wsgi, studio.management.commands.run_worker`, `ops/install.py` `phase_image`), so a
  release whose web or worker cannot load stops there, never at a document.
- **Kept database connections** (`cptstudio/settings.py` `DATABASES`; R2-7): only the web's entry point,
  `cptstudio/wsgi.py`, sets `CPT_STUDIO_WEB=1`, before the settings are read; the installer gives it to no container.
  In the web each connection is kept for an hour (`CONN_MAX_AGE` 3600) and checked at the first query of each request
  (`CONN_HEALTH_CHECKS`), so a click after a pause opens no connection inside the request, and a connection the
  database ended between requests is replaced, never answered with an error; a new connection waits at most 5 s
  (`connect_timeout`). The worker and every management command keep 60 s and no check: a worker thread's connection
  holds its provider slot's session lock across a send (`studio.jobs._take_slot`). A connection lost while a request
  runs answers 503 (6).
- **The worker** (`run_worker`, 5.2): one process of `CPT_STUDIO_CONCURRENT_DOCUMENTS` threads, in 1,536 MiB
  (`WORKER_LIMITS`). In production it converts no Word file itself: it is given the converter's socket and told that
  the converter is required (`CPT_STUDIO_CONVERTER_SOCKET`, `CPT_STUDIO_CONVERTER_REQUIRED`; `ops/install.py`
  `service_args`).
- **The converter** (`studio/converter_server.py`; release 1, E3 and A7; 5.12): a container of its own,
  `cpt-studio-converter`, started by the installer's `converter` phase outside the blue/green switch
  (`phase_converter`, `converter_args`: no network, no environment file, no credential, its own uid, 1,536 MiB, two
  CPUs). No Django settings, secret or database in it: a Unix-socket server that converts one Word file at a time by
  the code the worker would run in-process (`docx_package.convert_in_child`). Since release 2 its refusal of a file
  whose content the PDF would not show carries that refusal's code and counts (R2-31, 5.12).
- **Static files** are collected into the image when it is built (`deploy/Dockerfile`) and served by WhiteNoise under
  content-hashed names (`CompressedManifestStaticFilesStorage`, `cptstudio/settings.py` `STORAGES`) with
  `max-age=315360000, public, immutable`; pages name them through Django's static tag. Since release 2 the console's
  four fonts are named so too (`templates/studio/ops_base.html`, R2-26; release 1 named them by plain addresses, which
  WhiteNoise serves for 60 s), so a console page needs the manifest, as every member page does; only the console's
  scripts keep their plain addresses.

| path | what |
|---|---|
| `cptstudio/` | settings (every environment value is a `CPT_STUDIO_*` variable), URLs, WSGI, the web's warm-up (`warm.py`) |
| `deploy/` | the image, its container roles (`entrypoint.sh`), gunicorn's settings (`gunicorn.conf.py`), the nginx vhosts |
| `studio/models.py`, `studio/migrations/` | the data model (4); migrations 0001-0021 (release 2's 0019-0021 add indexes only, for the paged lists, a round's runs and the sweeps: R2-23) |
| `studio/intake.py`, `studio/storage.py` | creating an encounter from an upload or a paste; the immutable original store (5.1) |
| `studio/jobs.py`, `studio/management/commands/run_worker.py` | the job runner, the worker and the coding stage (5.2) |
| `studio/fable/` | the coding step: request, send, document block, prompts, parsing, combination, citations, pricing (5.3); the Word package and its conversion, `docx_package.py` (5.12) |
| `studio/converter_server.py` | the Word converter service, and the worker's side of it (5.12) |
| `studio/state.py` | the encounter's derived state (5.6) |
| `studio/decisions.py` | decisions, answers and retries (5.7) |
| `studio/exports.py` | the customer exports (5.8) |
| `studio/physician_report.py`, `studio/physician_pdf.py`, `studio/report_fonts/` | the physician PDF report (5.8): its words, its drawing, its fonts |
| `studio/customer.py`, `studio/api.py`, `studio/client_contract.py` | the customer JSON API ([`API.md`](API.md)) |
| `studio/paging.py` | pages read by position (keyset): the customer's lists and search, and the console's pages (release 2, R2-19) |
| `studio/db_unavailable.py` | a database that cannot be reached answers 503 (6) |
| `studio/operator.py`, `studio/console.py`, `templates/studio/ops_*.html`, `static/studio/fonts/` | the platform-operator console (5.9): its encounter pages, and its people, workspaces, spending and activity |
| `studio/views.py`, `studio/access.py`, `studio/audit.py` | health, sign-in, the page shell, tenancy, security headers, the audit trail |
| `studio/static/studio/`, `templates/studio/index.html` | the customer page ([`CORE-UX-DESIGN.md`](CORE-UX-DESIGN.md) 8); `session_news.js`, which the sign-in and account pages load (6) |
| `studio/reference/` | CMS reference sources and passages (5.5) |
| `studio/bounded.py` | work in a forked child under a wall clock and a memory allowance |
| `ops/` | installer, rollback check, sign-in verifier, customer scanner, browser walk, the browser speed gate (`test_viewer_speed.cjs`) and the bench (`bench/`) (9); none of it is in the image (`deploy/.dockerignore`) |

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
- `ExportArtifact` (immutable) - one export (`draft` or `approved`; `pdf`, `csv` or `txt`) stored as generated, with its
  sha256. `pdf` needed no migration: the field's declared choices (`txt`, `csv`) are no database constraint, and
  `exports.FORMATS` is what a request may name.

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
  `claude-fable-5-2`, `max_tokens` 96,000, `output_config.effort` from `CPT_STUDIO_CODING_EFFORT` (default `high` since release 2, R2-33; release 1's was `max`), the
  server-side fallbacks in their default form. Outcomes: a final message is `succeeded`, or `failed` for stop reason
  `refusal` (declined) or `max_tokens` (too long); an HTTP or stream error is `failed` with its status and type; a
  timeout or lost connection after the request started is `unknown`. A message served by a fallback is recorded as such
  (operators see it). Modes (`CPT_STUDIO_CODING_MODE`): `disabled` (default), `replay` (recorded messages by request
  sha256), `live`.
- `credentials.py` - the credentials file read strictly as data: a regular file, not a symlink, owner-only, at most
  32,000 bytes, `ANTHROPIC_API_KEY` required, `ANTHROPIC_WORKSPACE_ID` optional.
- `document.py` - the original as the API reads it: a PDF as a base64 document block with citations; a Word file
  converted to PDF (5.12: its package checked and edited, then LibreOffice in a bounded child of 70 s with a memory cap,
  a throwaway home and profile and no inherited environment, in the converter service in production), then sent as a
  PDF - or refused, with nothing sent (5.12); text and pastes as a text document block. No local PDF parsing.
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
  list; a code line's code (a reader code or a missed code) written with the CPT book's marks before it - `+` an add-on,
  `#` a resequenced code, at most one of each - is the code they mark (`+22614` is 22614: the code itself says what the
  mark says; owner direction 2026-11-22, D390, nothing may drop a code Fable writes), and so are a review's code, the
  checker's correction and a question's target, so a marked line and a marked review of it agree (refutation
  N2-1-1..4) - a review's code, a correction and a target in any other form are kept as written and matched as before
  (white space and case aside), never unreadable; a stored round is read again whenever a page shows it, so the release
  that installs this reading checks, before its switch, that no stored round holds a marked code (refutation N3-1-1;
  cpt.quillmd.com held none); a code line's code in any other shape is unreadable, never corrected or guessed. **Lines**: every code row has one -
  `L1`..`Ln`, the
  reader's codes in its order, then `M1`..`Mk`, the checker's additions - and the checker is given each line and names
  the line of every review. **Combination**, the only glue logic: a reader line keeps the reader's status only when the
  reviews naming that line and its code all say `agree` (at least one) and no other review names the line or its code;
  otherwise `needs_review`, both reasons kept. A review that names no line, an unknown line, or a line with another code
  is kept for the operator, shown to the customer as a note on the encounter with its reason, and sends every line it
  names, or whose code it carries, to `needs_review` - or every line of the round when it reaches none that way: the
  code never picks a line for it. A verdict that is neither exactly `agree` nor exactly `disagree` is no clear verdict,
  and the line needs review. Every code the checker found missing is a line of its own, `needs_review`. The round's
  questions come in this order: the reader's, the checker's, each line's own questions not yet asked (its question text,
  today's shape, and any question object written in its `question_ids`; the reader's lines in order, then the missed
  codes), the questions reviews define on themselves with an id, and last those of the fallback (below). Two questions
  are one only when their text is the same with case and spacing folded - nothing reads what a question means, so a
  question written again in other words is asked again, and a repeated id stays two questions. A question object
  (`{"id", "question"}`) a line or a missed code writes on itself is asked and shown on its row. One a review writes
  without an id is shown on its line's second check (when it is the review shown there) and asked only by the fallback,
  as the same text in the review's `question` field is today; with an id, it is asked as one of the checker's questions,
  naming the review's lines - a question added, never one lost. Any question object with an id also defines that id
  among its author's questions, and the id is one of those its item names. Each question names the lines it affects: its
  `affects`, the line it is written on, every line and missed code whose ids name it, and the lines of every review
  whose ids do (an id names every question carrying it, case-insensitively, among the questions its author was shown:
  the reader's for a reader line, the reader's and the checker's for the checker). An id that names no question carries
  no text and is listed on the operator console, as are the ids both answers defined (a checker reference to one reaches
  every question carrying it in either answer, which is one question where their texts are the same; the code never
  picks one); any shape of `question_ids` is read without failing the round. A string in `question_ids` is always an
  id, so question text written there as a plain string names no question and reaches only the operator console - a
  known limit (D378): it takes two departures from the instructions, since the question also belongs in `questions`,
  and telling such text from a malformed id such as `Q1, Q2` would mean guessing. A code row shows its own question
  text, then the text of the questions its own ids name, one per line; a question naming the line only by its `affects`
  is not repeated there. A question whose text is blank - nothing left once U+FEFF and white space are removed; every
  text the page's trim() empties is blank by this test, which also counts U+001C to U+001F and U+0085, characters the
  page keeps - is no question, and an id blank by the same test is no id. A `needs_answer` line no question names by
  its affects or its question text gets its agreeing reviews' own questions (as before; a question object in its
  `question_ids` names it without silencing them), or - when none, and nothing names it either - CPT Studio's own.
  Answers in the earlier shape (a question text on each line or review, questions without ids) read exactly as before,
  with one exception: a question whose whole text is U+FEFF and white space is now blank and carries nothing, and a
  `needs_answer` line then gets the fallback when nothing else names it. The merge costs in proportion to what it reads
  (sets of question numbers, each reference list resolved once). A known limit: because a reference reaches every
  question carrying its id and a row shows every question its ids name, an absurd answer with many distinct questions
  sharing one id and many lines naming it multiplies the size of the stored round. The problems are the reader's.
  **Citations**: a whole line `LINE L<n> <code>` (reader), `REVIEW L<n> <code>` or `MISSED M<k> <code>` (checker),
  the code with or without the book's marks, starts that line's section; a citation after it is filed under the line when
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
refused as changed, 409, before readiness is read). A draft lists every code with its status, units, modifiers, reason,
the second check and quotes with pages, then the questions and documentation notes; the approved report lists only the
lines whose current decision is an approval and whose status is ready or needs_review, with approver, kind and time.
Units or modifiers not given read "not given". Each export is stored once as an `ExportArtifact`; a download serves the
stored bytes; one made from an earlier round stays listed, marked earlier. The report is a PDF and nothing else (owner
directions 2026-11-21: the doctor-facing report, then the only one); the TXT and CSV exports made before that stay
stored, listed and downloadable as records, and none is made again (`exports.FORMATS`).

Release 1 (C5): a request for a report that is still current (made from the latest round, no decision on that round
since; `customer.export_current`, the page's own rule) returns the stored copy - 200, one `export.reused` audit row -
instead of rendering another, and a new decision makes the next request render a fresh one. The lock is the document's
row alone (`select_for_update(of=('self',))`). Reports made are limited to 10 per member in 10 minutes and 60 per
practice in an hour, and uploads to 30 per member in 10 minutes (`studio.rate`; 429 `rate_limited` with `Retry-After`;
the first refusal of a window writes a `SecurityEvent`). Only a report actually made counts (lead ruling 2026-11-24).
`exports.create` answers a current stored copy from a read without a lock, before anything is counted. It calls the
API's `charge` only when it is about to render a new report, outside any transaction, so the counter is never held under
the document's lock. A refusal (409) is never counted. Encrypting `ExportArtifact.content` (F1's reports half) is release 1b
(D402): not built.

The physician PDF is made from the snapshot every customer export has been made from (`exports.snapshot`):
`studio/physician_report.py` chooses its words from that snapshot (a draft: every line with its status, decision and
evidence, then the questions, the lines with no saved decision and the notes; an approved report: only the lines with a
current approval, each with who approved it and when), and `studio/physician_pdf.py` draws them with ReportLab - a
searchable US Letter document after the owner-approved first-page design, continuation pages in the evidence-page
treatment, every dynamic string escaped before it reaches ReportLab's markup, no image and no remote resource. The fonts
are the files in `studio/report_fonts/`, embedded as subsets; their licences and `PROVENANCE.md` (source and sha256 of
each file) are beside them, and they are read from the code tree, not served as static files. The PDF is stored like
the other two - one `ExportArtifact`, fmt `pdf` - and served as stored. Making it reads saved rows only: it writes no
decision, round or state, calls no provider, and gives the same output for the same saved state, but for the Prepared
line (when, and by whom, it was made) and the PDF's own date. A PDF that cannot be made is refused (`exports.NotMade`,
503) before anything is stored.

How the PDF prints text (refutation rounds 1 and 2, 2026-11-21): control characters print as spaces; invisible format
characters, and whatever the report's own fonts draw as nothing (measured from the fonts when they load), are deleted
before the display filter reads the text, so the filter reads what the reader sees; a character none of the fonts draws
prints as U+FFFD - never as a look-alike or a compatibility form, which could change a number in a quotation or spell a
name the filter has already read - and the report's review scope says so; right-to-left text is printed in its stored
order, also said there. Every field the coding review wrote (reasons, second checks, questions, notes, its own
quotations, modifiers) passes `customer.shown`, the filter every customer surface uses. A model family's name (Opus,
Sonnet, Haiku) is replaced only where it continues a vendor's name ("Claude 3 Opus"); alone it is an ordinary or a
clinical word (the OPUS trial, a MED-EL SONNET 2 processor).

Known limits of the physician PDF (recorded, not defects; refutation rounds 1-5, 2026-11-21): text the coding review
wrote is filtered as on the page, so what the shared filter cannot read is printed as on the page - a vendor name in
look-alike letters (Cyrillic or Greek, enclosed letters a report font draws, Hebrew points or a ligature inside it), with
its version joined to it ("Claude3.5": the denylist bounds a name by digits too), a model family alone ("Opus 4.5"), in
parentheses or split by an invisible character after its vendor name, other model tiers ("Gemini 2.5 Flash"), another
company's product ("ChatGPT", "GPT4o"), and machinery words (a token count, a request id), which the customer scanner
flags except inside a line's own quotation (the page serves it as a quote, and the scanner reads every quote as the
document's words). A word the filter cannot tell from a vendor's name is replaced as on the page (the organ of Corti, a
doctor named Claude), and numbers of one or two digits right after it, joined by dots, dashes or underscores, are read as
its version ("Dr. Claude 2 polyps" reads "Dr. The system polyps", as on main; so does a small range after "organ of
Corti"); a longer number is left (a CPT code, a date). A model family split by an invisible character after its vendor
name, in any field (a modifier too), prints after "the system" (refutation rounds 4 and 5). The scanner
reads the latest round's quotations as the document's words, so an earlier round's PDF quoting a passage the latest
round no longer cites fails the scan (a false failure, for a person to read), and a token the layout cuts mid-word is
read as two. A value too tall for one row (dozens of long modifiers, twenty reviewers with long names) flows as
paragraphs, and its first heading can end a page apart from its first fact; a code's evidence note can leave its last
line at the top of the next page. A page of this release left open across a switch-back still offers the PDF and shows
the earlier server's refusal (that server also offers TXT and CSV again); a page of the earlier release left open across
the install still offers TXT and CSV, and the server refuses them with its sentence until the page is reloaded.

### 5.9 The operator console (`studio/operator.py`)

Server-rendered pages under `/ops/` for people holding an operator grant (from `grant_operator` only; no workspace role
confers it), on admin.quillmd.com after the second factor (release 1; see the end of this section). Everyone else - signed out, any member, a revoked operator - gets exactly an unknown URL's 404 before the
method, body, CSRF token or any record is read. The console has a second address, admin.quillmd.com (owner direction
2026-11-23, D396; `studio/hosts.py`, `cptstudio/urls_admin.py`): that host's urlconf holds the console's own routes
(taken from the full urlconf, so the two cannot drift), an operator-only sign-in (any other account gets the same
sentence as a wrong password, no session, and a failed attempt on the shared throttle), and `/` and `/ops` redirects -
no doctor app and no API. There any signed-out request to a console route goes to the sign-in (a GET or HEAD back to
the page, a form sent after the session ended to the console's front page, its body never read); every signed-in request
meets the same gate, so the host is a convenience and never the security boundary. The admin host trusts only its own
origin for an unsafe request (`studio.hosts.foreign_origin`, ahead of every view): Django's global CSRF_TRUSTED_ORIGINS,
which names cpt.quillmd.com, never applies there. The host is the Host header as Django reads it (no X-Forwarded-Host),
port and trailing dot set aside. Pages: every encounter across workspaces (state, rounds, latest cost),
and one encounter's rounds, runs (models, served by a fallback, tokens, cost, latency, state), the reader's and checker's
whole answers, codes and decisions by line, the reviews tied to no line, the question ids that name no question and
those both answers defined (read from the two stored answers, so every stored round shows them), answers, audit events
and the original with its sha256. Acts (POST, CSRF):
reconcile an unknown run (a note of at least 12 characters), retry a failed round (not offered while a send of it awaits
that reconcile), release the standing holds. Views are audited.

The console's controls (owner direction 2026-11-22, DECISIONS D395; `studio/console.py`), behind the same gate and in
the console's design (the design tokens of 2026-11-22; Manrope and IBM Plex Mono served from `static/studio/fonts/`,
byte-identical copies of the report's vendored fonts):
- People (`/ops/people`): every membership with its role, access and last sign-in; the operators (read-only); acts to add
  a person to one workspace (one login, one workspace), reset a password, change a membership's role and turn the
  account's access off or on (`is_active`: sign-in refused, open sessions end). A new or reset password is generated
  (`secrets`, the site's password validators), stored as its hash and shown once in the POST's own answer - never in a
  URL, a redirect, a log or an audit row. No act changes an operator's account or records or ends a grant; nothing is
  deleted.
- Workspaces (`/ops/workspaces`): each with its specialty, people and documents; a new one for an existing category,
  its name stored exactly as typed in Latin letters (the Western European ones: Latin-1's, with Œ, Š, Ž, Ÿ and Welsh Ŵ,
  Ŷ), digits, single spaces and a few marks, and compared with case, accents, modifier letters and punctuation aside
  (`console.name_reading`): it may read alike no other workspace and no other specialty. Names in other scripts are refused (provisioning can still make such a workspace), and
  letters a font draws alike (I, l and 1; O and 0) are compared as written. A workspace's page lists its people with
  the same acts.
- Spending (`/ops/spending`): sent coding runs priced by `jobs.run_cost` (the console's own figures) by UTC day,
  workspace and document; an unpriced run is counted apart with its reserved worst case, never as zero.
- Activity (`/ops/activity`): every audit event in plain words, newest first, filtered by workspace and kind; every
  sign-in attempt under Sign-ins.
Every act is audited in the workspace it concerns (`operator.member_added`, `operator.role_changed`,
`operator.password_reset`, `operator.access_off`, `operator.access_on`, `operator.workspace_created`); those rows name
no encounter, so the customer's activity never shows them.

**Release 1 (RELEASE-1-SPEC B3, C1-C3, C4 item 4, B1 step 8).**
- *The gate* (`operator.may_use_console`): the console answers only on admin.quillmd.com, to a session that passed the
  second factor at the admin door (`second_factor.satisfied`), of a person's account holding a grant. On
  cpt.quillmd.com every console route answers an unknown URL's 404 to everyone, a valid admin-door session included; a
  password-only session, a session from the cpt door or one from before release 1 gets the same 404 on the admin host.
- *Operators are people* (C3): `is_operator` refuses an automated account whatever grant row it has; `grant_operator`
  refuses one and requires `--authorization-ref`, `--review-by` (at most 12 months away) and `--by` (a person, never a
  role); `revoke_operator` requires `--by`, and a revocation ends every session of the account. An account whose access
  was ever revoked is granted again only with `--regrant` (`operator.grant(regrant=True)`); the installer passes it only
  when its committed declaration names the regrant, and the `operator.granted` event of a regrant says `regrant: true`.
  Each grant and revocation writes a `SecurityEvent` (`operator.granted`, `operator.revoked`). The Operators card shows
  each grant's approval and review date and flags the overdue ones. `provision` refuses an operator's account in every
  role (owner, agent, reviewer) before it writes anything. An operator's account is one named in the installer's
  `OPERATOR_ACCOUNTS_SPEC` (`operator.INSTALLER_OPERATOR_USERNAMES`; a test holds the two equal) or one holding a grant.
  So provisioning never makes an operator a member or sets an operator's password.
- *Every read is recorded first* (C1, `studio.read_audit`): the front page (`ops.list`), a document's page
  (`ops.detail`, every view), the opening of its content (`ops.content_open`), its original (`ops.original`), a
  practice's page (`ops.workspace`), spending (`ops.spending`), the activity (`ops.activity`) and the reads page
  (`ops.reads`) write their access record before the page or file is built; a read that cannot be recorded answers 503
  and nothing else. A refused act answers 303 back to its page with an error code, so no page with data is served
  unrecorded. `/ops/activity/reads` lists every recorded read - members' and operators', served and refused - by
  account, practice, kind and day.
- *Less by default* (C2): no list shows a title or a file name (a document is its short reference, the first 8
  characters of its id); a document's page opens on its metadata (state, times, failure kinds, run ids, costs, sizes,
  decision counts, holds; the tab says "Encounter <reference>"). "Open the content" asks for one of four reasons and a
  reference with a digit (a ticket or request number, never patient details) and opens that one document for
  `CONTENT_GRANT_SECONDS` in that session only; without it the original answers 403. The original downloads as
  `encounter-<reference>.<extension>`; a Word document's is its converted PDF, the Word file only with `format=original`
  (C6). Retry, reconcile and the holds work from the metadata.
- *Access acts*, Clear sign-in delay included, ask "Requested by" (the practice's contact or a ticket reference;
  stored on the act's audit row) and the
  key again within `SECOND_FACTOR_STEP_UP_SECONDS` (B2 step 5). The access switch is the membership's - this practice
  only - by default; "Turn off everywhere" (the account) stays apart. Add-person and reset set
  `password_change_required_at` (B4). Clear sign-in delay (`ops/people/<id>/unlock`) calls Lane 2's
  `throttle.clear_failures(username)` and writes `signin.delay_cleared`; sign-in rows are never deleted. The Sign-ins
  page names each attempt's door and outcome, states the rule (a slowdown, never a lock) and shows, for each account on
  it, the attempts the slowdown refused in the last hour (`throttle.refused_in(username)`).
- *Disposal* (D1, Lane 4): a destroyed document's tombstone is in no list and its routes answer 404; a closed practice
  drops out of the front page and the add form, and the Workspaces page lists it apart.

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

### 5.12 Word files (`studio/fable/docx_package.py`, `studio/converter_server.py`)

A Word file becomes the PDF that is coded and shown in one way only, `docx_package.convert_in_child`: a bounded child
(`studio.bounded.run_bounded`: `CONVERT_SECONDS`, 70 s - 10 for the package checks, 55 for LibreOffice, 5 of margin -
and `CONVERT_MEMORY_BYTES`, 2 GiB of address-space growth) runs `safe_package`, which checks the package and edits it,
then LibreOffice (`soffice_convert`: a throwaway home, profile and work folder, an environment built from nothing, its
process group killed whatever happens). In production the converter service runs it (section 3); the worker allows it
`converter_wait_seconds()` in all (300 s with four threads), and reads busy, an unreachable socket or a timeout as
BUSY (a member may retry) and a refusal, a failure or an answer in another form as CONVERT
(`studio/fable/document.py` `convert_docx`). Release 1's checks run first, with their reasons and the general sentence
("The Word file could not be opened."), among them: not a zip, a part encrypted or named twice, more than 10,000 parts,
a part past 32 MiB or the parts past 64 MiB once inflated, an OpenDocument package, no content types or package
relationships, a main part that is not a Word document's. Every External relationship is dropped, with the parts only it named, and the
instructions of fields LibreOffice could act on (INCLUDETEXT, INCLUDEPICTURE, INCLUDE, LINK, DDE, DDEAUTO, IMPORT,
DATABASE, and any field whose type its own text does not spell) and embedded content are removed by byte ranges,
keeping what the reader sees; a part with nothing to remove passes through byte for byte. The converter's log holds
sizes, durations and fixed words only.

Release 2 (RELEASE-2-SPEC Group F, R2-28 to R2-31; owner directions D421 and D422): the Word handling never takes
content out of a file while leaving nothing of it in the PDF. Where it would, the file is refused (`ContentNotShown`,
counting `documents`, `objects`, `controls` and `fields`), nothing of it is rebuilt or converted, and nothing is sent
(`docx_package._package`).
- *The canonical package gate* (D-R2-46; `_require_canonical_zip`, `_require_canonical_structure`): once release 1's
  checks pass, and before any part is edited, the package must be in the one form a Word package takes, where this
  module, LibreOffice and the doctor's Word read every structural reference alike: one zip archive from its first byte
  (a local header) to its last (its end record, with no comment), its parts stored or deflated, each local header
  agreeing with its directory record; entry names of `/`-separated segments of `[A-Za-z0-9._-]`, none `.` or `..`, or
  `[Content_Types].xml`; every relationships part named for a part present, an unprefixed `Relationships` holding only
  `Relationship` rows of exactly `Id`, `Type`, `Target` and at most `TargetMode` (`Internal` or `External`), each `Id`
  once in its part, a relationship a part has one of (its styles, footnotes, comments...) once, each Internal target
  naming a part present by its exact name; content types of `Default` and `Override` rows only, the main part with an
  `Override` of its own; and a preview in a `w:object` or `w:pict` naming one picture id at most. Any other form is
  refused whatever the file holds (`PackageNotCanonical`, told as an inserted document, counts `{"documents": 1}`); the
  converter's log names the form broken, in fixed words, never a part. So is a package with a zip entry that a Unicode
  Path field names otherwise than its stored name (D-R2-43, `_renamed_by_unicode_path`). A known limit: a file in any
  other form - a main part typed only by a `Default`, relationships parts copied without their parts (pandoc's
  `--reference-doc`, as the module records), an archive comment - is refused with the save-as-PDF sentence, never coded.
- *An inserted document is refused* (R2-28; `_PartReader`, `_relationship_ids`): a `w:altChunk` whose relationship
  names a part present and not empty, in any format, story or namespace form; one whose relationship is External, which
  the doctor's own Word could pull in; and every `w:subDoc`. An `altChunk` that holds nothing - no `r:id`, an `r:id`
  naming no relationship, or an empty part - is removed as release 1 removes it (counted as `chunks`); one whose
  relationship names a missing part is refused by the gate.
- *An object or a control keeps a picture in its place, or the file is refused* (R2-29; `_PartReader._end_object`,
  `_is_picture`): a preview counts only when its relationship names, as LibreOffice opens a picture, a part that is sent
  and whose bytes begin as a picture LibreOffice decodes (EMF, WMF, PNG, JPEG, GIF, TIFF, BMP, PDF, and EMZ or WMZ by
  what they inflate to; PICT and SVG stay refused). A `w:object` is refused when its pictures are fewer than its
  pointers, when it holds anything but VML, a drawing, pointers, a control or a movie, when it has both a drawing and a
  VML shape, or when it points at something with no drawing and not exactly one VML shape; a `w:pict` when its pictures
  are fewer than the pointers and controls it holds; a pointer or a control in neither. A known limit: only a preview
  part's first bytes are read, so a part that begins as a picture counts as one whatever follows.
- *A removed field inside another field's result keeps its words* (R2-30; `_PartReader._shell_field`,
  `_shell_simple_field`, `_Field.loses_its_result`): a removed field that lies in the result of a field that stays, and
  in no field's instruction, stays a field whose instruction is ` QUOTE `, a type LibreOffice shows by its stored
  result (an INCLUDEPICTURE whose stored result shows no text, symbol or mark is unwrapped as in release 1). The rule's
  fallback refuses the file (counted as `fields`) when a removed field other than INCLUDEPICTURE stood in the
  instruction of a kept field whose type is not HYPERLINK, TOC, QUOTE or STYLEREF and whose stored result shows
  something outside the fields in it - text, a symbol, a note's reference, a non-breaking hyphen, a picture, a drawing
  or an object - which LibreOffice 7.4 drops.
- *Everything else is release 1's package*: a file that needs no refusal and no QUOTE gives exactly the package release
  1 gave, but for one deviation in a part that is edited - a relationship id a kept attribute writes with a character
  reference keeps its relationship and its part, which release 1 dropped (`_still_named`).
- *The refusal's sentence and record* (R2-31; `ContentNotShown.code`, `studio/fable/document.py`
  `REFUSED_PACKAGE_TEXT` and `DocumentError.recorded`, `studio/jobs.py` `_code` and `_fail`): the code is
  `inserted_document` when an inserted document or a field is counted (the gate's refusals included), else
  `inserted_object`, and the member reads "This Word file has another document inserted in it, which cannot be read
  here. Open it in Word, save it as a PDF and upload the PDF." or "This Word file has an embedded object that cannot be
  shown here. Open it in Word, save it as a PDF and upload the PDF."; every other refusal keeps "The Word file could not
  be opened.". The round fails `convert` with that sentence before any send - no `ProviderRun`, nothing counted - and
  its `coding.round_failed` event adds the code and the four counts (`refused`, `inserted`), never a word of the file;
  the worker's log line names the code alone, a fixed word the installer's kept log keeps. A retry is still offered and
  meets the same refusal.
- *One bound on every count* (`docx_package.MAX_REFUSAL_COUNT`, 1,000,000): `ContentNotShown` carries each count at
  most at that bound. The converter adds `reason` and `counts` to a refusal only when it has a code
  (`converter_server._error`), and the worker believes them only in exactly that form - a code of `REFUSAL_CODES`,
  counts holding exactly the four kinds, each an integer, not a boolean, of 0 to `converter_server.MAX_COUNT` (which is
  that bound), not all 0, and the code agreeing with them (`converter_server._refusal`); anything else, a release-1
  converter's answer included, reads as the general refusal. So the converter's answer, the worker's own check (below)
  and a conversion in the worker give one file one sentence and one record.
- *A stored conversion is reused only for a clean original* (C8, R2-28 step 7; `studio/jobs.py` `_stored_conversion`,
  `studio/fable/document.py` `needs_fresh_conversion`, `docx_package.check_in_child`): a later round of a revision (an
  answers round, a retry) read back the PDF an earlier round stored, unchecked. The worker now first runs this
  release's package check on the stored original, in a bounded child under a conversion's limits, converting nothing
  and asking no converter. A file the check refuses ends the round as a fresh conversion of it would - the same
  sentence and record, nothing sent - a resumed round included. A file whose package this release changes (R2-30's
  QUOTE applies, or a relationship id release 1 dropped is kept) converts afresh at a later round; a round that
  recorded the stored conversion as its own view (resumed or requeued) reads it back, so its reads, its view and its
  quote pages stay on one PDF. Where the check cannot decide - it runs out of time, fails, or refuses the file for
  another reason once it opened as a zip - the converter decides, a round's own view included (an acceptance is
  remembered for that round in the worker process). A clean original's stored conversion is reused byte for byte, with
  no converter call, and so is one whose original is no zip at all (every release refused such a file, so none was
  stored). When a fresh conversion cannot be stored and an earlier round's view exists, the round fails before
  anything is sent (`_keep_view`: `storage`, or `document` past the store's 15 MiB limit), since the viewer would show
  that other conversion beside this round's codes. A release-1 worker (before the install's switch, or after a
  switch-back) reuses a stored conversion unchecked.
- *What the doctor is shown* (`studio/customer.py` `shown_view`, `view_conversion_of`): once a round ends failed on the
  Word file itself - `convert`, or `document` with no view of its own - the page shows no converted view of the
  document and its PDF download answers 409 (the Word file itself stays downloadable, with `format=original`), until a
  later round stores a view of its own; the operator console keeps serving the record's converted PDF
  (`download_content(recorded=True)`). A Word document's view names the stored conversion it serves
  (`document.view_conversion`, and `X-CPT-View-Conversion` on the view's answers): the page redraws its viewer when a
  later round converts the file again, keeps it - zoom and place included - when a round reads the same file back,
  draws held bytes only as the conversion its detail names, and keeps no copy of a document whose detail names no PDF
  view (`app.js` `dropRefused`).

## 6. Security

Session authentication with Argon2 password hashes and a sign-in throttle (release 1, B1: it slows a username down
instead of locking it out; Lane 2's `studio/throttle.py`); CSRF on every POST; every read of PHI recorded before it is
served, and nothing served when it cannot be (release 1, C1: `studio/read_audit.py`, the `AccessRecord` table); `Cache-Control: no-store` on everything but static files; a Content-Security-Policy with
`script-src 'self'` and no inline script (the page shell adds `frame-src 'self'` for the text viewer and for the
browser's own PDF viewer, framed where the page cannot draw a PDF itself, and only the in-page view of an original may
be framed, by CPT Studio's own pages); `X-Frame-Options: DENY` elsewhere. The PDF library the review page draws a PDF
with (the legacy build of pdfjs-dist 6.5.438, which bundles core-js 3.51.0 for the built-ins older browsers lack; the
files `studio/static/studio/lib/pdfjs-6.5.438/MANIFEST.json` lists with their npm path and sha256 and the npm integrity
of both tarballs, the licences beside them; nothing from a CDN) loads as same-origin modules and a same-origin module
worker under `script-src 'self'` (`worker-src` falls back to it), served as JavaScript by WhiteNoise under `nosniff`; the
viewer starts that worker itself and hands it to the library, so the library never parses a document on the page's own
thread (DECISIONS D368, round 5). Since release 2 one worker is made ready ahead, holding no document, and the next
document opened takes it as its own (R2-10; `app.js` `startStandby`, `takeWorker`): each document still has its own
worker, ended with its viewer, and none is made ahead on Save-Data or after two failures. It runs with no eval and no
WebAssembly - the policy has neither `'unsafe-eval'` nor `'wasm-unsafe-eval'`; core-js's one `Function("return this")`
lookup is never reached in a browser and would be refused - with no document scripting, no XFA and no layer of links or
form fields, is given only the bytes the viewer downloaded itself from the same-origin view address (or, on a re-open
the server answered 304, a copy of them the page kept: below), and puts a PDF's text in the page as text only (its
text layer). A browser that
lacks what it needs (Chrome and Edge before 119, Firefox before 125, Safari before 17.4; measured in Chromium only, the
other versions from MDN's browser-compat-data) is not given it: the browser's own viewer is framed and the note says
marking needs a newer browser; where the library itself fails, or has not answered for 20 seconds while the viewer waits
on it, the note says the marking tool did not work here, and where the download fails, that it could not be
downloaded. Every customer
query is scoped through the caller's active membership, so another workspace's records answer 404. Text the database
cannot store (NUL, a lone surrogate) is refused with a 400 rather than altered; only a title or a file name has it
replaced.

The site's security headers (`studio.access.SecurityHeadersMiddleware`) wrap WhiteNoise, so every static file carries
them too (DECISIONS D368, round 3): above all the PDF library's module worker, which parses the uploaded document and
takes its policy from its own script's response, not from the page that starts it. A static file's policy is the site's
with `base-uri 'none'` (`STATIC_CSP`: `default-src 'self'`, `script-src 'self'`, `connect-src 'self'`, `object-src
'none'`, no `'unsafe-eval'`, no `'wasm-unsafe-eval'`), so code built from a string and a fetch to another origin are
refused inside the worker too (measured in Chromium); its caching stays WhiteNoise's (immutable for the hashed names,
never `no-store`). The dev preview serves the library with exactly these headers, and `tests/test_frontend.py` holds the
two equal through the full middleware stack. The suite pins the library itself as well: one digest over every file's
sha256, the manifest included (`PDF_LIB_DIGEST`), so a changed vendored file fails until that line changes in the open.

**Release 2 (RELEASE-2-SPEC R2-9, R2-15 to R2-24 and R2-27; integrated refutation rounds 1 and 2).** The page's side is
in CORE-UX-DESIGN.md section 8 ("Release 2: the page's speed"), the answers in API.md.
- *List records name their documents* (R2-19, R2-21; `studio/api.py` `encounters` and `search_encounters`,
  `studio/read_audit.py` `_counted_list_repeat`): a list is read a page at a time - Documents and the Review queue 50
  rows, the Overview's recent 5 (`customer.list_page`) - by keyset (`studio/paging.py`: the cursor, a time and an id, is
  a position and never an authority, since every query is scoped through the caller's membership). Each page served
  writes its `member.list` record before it leaves, naming the documents it showed in order, their number, and the list
  and cursor asked (filters `list` - documents, queue, recent or search - and `before`); a page read again within 60 s
  by the same sign-in (`READ_AUDIT_LIST_REPEAT_SECONDS`) is counted on the earlier record only when it shows the same
  documents in the same order. A later page and every search first count toward the member's limit
  (`LIST_PAGES_LIMIT_PER_MEMBER`, 120 a minute, scope `list.member`): over it, 429 `rate_limited` with `Retry-After`,
  one `SecurityEvent` `list.rate_limited` at the window's first refusal, and nothing read or recorded. A first page and
  the Overview are not counted. A list or search answer names its practice (`workspace`), and the page draws no page of
  another practice than the one it shows (`app.js` `otherPractice`; I1-2).
- *Search words travel in a POST body alone* (R2-20, R2-27; `studio/api.py` `search_encounters`,
  `studio/customer.py` `search_page`): `POST /api/encounters/search` (CSRF enforced) carries the words in its JSON
  body, so they never sit in an address, a query string or an access log; the page sends it only for a Documents list
  of more than 200 documents and searches a smaller one itself (`app.js` `LOCAL_SEARCH_MAX`). Its record names the
  documents found with the filters `{"list": "search", "before": <cursor>}`, never the words, and no table, session,
  answer header or log line keeps them (the closed-world guard, 9). The words are a bound parameter of one statement
  (`strpos` over the row's text, both lower-cased in `pg_c_utf8`, so nothing in them is a wildcard): they are in the
  statement's text while it runs (`pg_stat_activity`), as any parameter is, and the database logs no statement text
  (`ops/install.py` `DB_LOG_SETTINGS`). nginx counts a search in its every-request zone alone, never in the write zone
  the decisions and answers need (`deploy/nginx/cpt-quillmd-https.conf`, `cpt_write_key`).
- *A re-open is recorded as shown from page memory* (R2-15; `studio/api.py` `original`, `view_tag`, `_held`;
  `studio/customer.py` `view_source`): a PDF view of a stored file carries `ETag: "<tag>"`, a UUID derived with the
  site's key (`salted_hmac`) from the sign-in reference, the document and the stored file's recorded sha256 - it names
  no hash, is bound to the sign-in and is made without reading the file; a text or a pasted text is never tagged, and no
  other `/api/` answer carries an ETag. A re-open naming the tag in `If-None-Match` (its weak form too, never `*`)
  writes its `member.inline` record first, with the filters `{"shown_from": "page_memory"}`, and is answered 304 with no
  body and no stored file read; a record that cannot be written answers 503 and nothing else, and the page draws
  nothing. Anything else - another tag, another sign-in, a stored file whose recorded hash changed - is a 200 with the
  bytes, recorded as before. Both answers stay `no-store`, and what answered 404 before (another practice's document,
  with its refused record, a destroyed one, a member whose access is off) still does, first. A Word document's view
  names, on its 200 and its 304, the stored conversion it serves (`X-CPT-View-Conversion`,
  `customer.view_conversion_of`: a UUID derived with the site's key from the document and the stored file's name,
  never from its bytes), and the page draws held bytes only as the conversion its detail names (I2-1; 5.12).
- *Page memory, kept and wiped* (R2-15 to R2-18; `studio/static/studio/app.js` `keepView`, `forgetMemory`): the page
  keeps the bytes of a PDF it opened, for a re-open, in its own memory alone - never a Blob, the Cache API, IndexedDB or
  Web Storage - only for a tagged view, at most six documents and 24 MiB (`KEPT_VIEWS`), the least recently viewed
  going first, and every copy that goes overwritten with zeros. At every end - the sign-out, the idle end and the cap,
  a 401 or a forced password change wherever the page meets it, another tab's sign-out, a document refused with 404,
  and `pagehide` (the back-forward cache included) - `forgetMemory` overwrites and drops every kept copy, with the view
  asked for at the click, the rows' PDF hints and the worker made ready ahead; the list itself lives in page memory only
  and goes with every route. The sign-in and account pages tell the app's tabs they were reached
  (`studio/static/studio/session_news.js`, on the tabs' own channel; I1-13), so a "Sign out everywhere" or another
  member's sign-in in the same browser is an end there too.
- *The page shell carries the session* (R2-17; `studio/views.py` `index`): `<body data-session-json>` holds, escaped,
  the payload `GET /api/session` answers (`customer.session_json`), so a page load asks for no session; it names no
  document, so nothing is recorded, and the shell stays `no-store`.
- *The client version* (R2-24; `studio/client_contract.py` `VERSION`, `studio/api.py` `api_view`): this release's page
  names the build `customer-2026-11-26` on every API call, and any other build - a tab left open across the install -
  is answered 409 `client_outdated` before the view runs, every list page and the search included, so a page of release
  1, which would read one page as the whole list, is told to reload instead. After a switch-back release 1's web has no
  search route, and the page reads its HTML 404 to the search as the same notice (`app.js` `api`; I1-3).
- *A database that cannot be reached answers 503, with `Retry-After`* (integrated refutation rounds 1 and 2;
  `studio/db_unavailable.py`: `DatabaseUnavailableMiddleware` for what a view raises, `server_error` - both URLconfs'
  `handler500` - for what another middleware raises): only a lost or unusable connection (`is_database_unavailable`:
  an `InterfaceError`, or an `OperationalError` with no SQLSTATE, of class `08` or `57P01` to `57P03`) is answered so:
  503 with `Retry-After: 5` and nothing of the request - under `/api/` JSON with no exception text, a read's sentence
  (a GET or HEAD, and the search) `read_audit.NOT_RECORDED` and a change's `CHANGE_UNKNOWN`, which says neither that it
  was kept nor that it was not; elsewhere Django's plain "Service Unavailable (503)" page. A read whose own record is
  lost as it is written answers the same (`raise_if_lost`). Every other error - a deadlock, a cancelled statement, a
  full disk - stays Django's 500, as before. A recorded limit (I1-20): a loss in Django's own write of the session's row
  after the view is Django's 400 (`SessionInterrupted`), not this 503.
- *The web's kept log* (R2-9; `ops/install.py` `ids_only_lines`, `KEPT_STREAM_FORMATS`): the installer's ids-only copy
  of the web's log keeps gunicorn's access lines from stdout alone and every other kept line - gunicorn's life cycle,
  which since release 2 includes a worker killed for memory, an exit code and a failed boot, django.request's lines,
  and the web's fixed load-failure line - from stderr alone, each stream cut at line feeds only: the access log writes a
  client's decoded path unescaped, and no request can then forge a line the copy keeps (integrated refutation round 1).

## 7. JSON API

[`API.md`](API.md): session auth, the client contract header, every endpoint and payload.

## 8. The customer page

[`CORE-UX-DESIGN.md`](CORE-UX-DESIGN.md) section 8: the DOM and copy contract the browser walk checks, and the one
statement of how a chosen quote's words are marked in the document viewer ("Marking a quoted passage", DECISIONS D368:
its own characters on its page, white space ignored, NFKC and format characters dropped on both sides, exact case first,
never inside a longer word or number as the text reads (within the known limits) - two drawings that do not visibly
continue each other meet at a word edge, a Han ideograph or a hiragana character is a word of its own, a number's own
decimal point or thousands separator keeps it one word -, an overprinted copy counted once, every occurrence counted, never another page; the notes, the zoom, the
viewer's own worker and download, its watchdog on the library and the fallback to the browser's own viewer with its
reasons; the known limits). It is display only: it reads Unicode character classes, NFKC and the text's geometry, reads
no meaning and never holds or changes a code.

## 9. Verification

- The Django suite (`manage.py test tests`): the coding step with fake SDK streams and a fake converter, the job runner
  (reuse after a crash, unknown outcomes, the ceiling, holds, Stop, threads and slots), the API contract and tenancy,
  decisions, answers, exports (the physician PDF read back with pypdf, and through `ops/scan_customer.py`'s own PDF
  reading against the shared denylist), the operator console, the page's templates and node tests, and the reference
  data. Release 2 adds: the web process, in fresh interpreters (no AI library, and nothing opened or started at import;
  the warm-up; gunicorn's settings) and as a real gunicorn with the release's own settings on the test database
  (`tests/test_web_process.py`); the paged lists and the search - its row text held to the shipped page's, the letters
  it folds, its query plans - and their limits (`tests/test_lists.py`), with the records naming each page's documents
  (`tests/test_read_audit.py`); the view's tag and the recorded 304 (`tests/test_r2_viewer.py`); the Word refusals and the stored conversions, compared with release 1's own
  `docx_package.py` and `converter_server.py`, vendored as fixtures checked against their git blob ids
  (`tests/test_r2_word.py`, `tests/fixtures/release-1/`); the 503 (`tests/test_db_unavailable.py`); and what the coder
  is sent, pinned to release 1's requests at effort "high" - what the SDK is given and what it puts on the wire - with
  the coding files' blob ids (`tests/test_request_identity.py`, R2-3). Synthetic text only; nothing is sent.
- CI (`scripts/ci/verify-cpt-studio.sh`): checks, migration drift, the Django suite, the ops unit suites (the bench's
  own tests, `ops/test_bench.py`, among them), the browser walk's own tests (`ops/test_walk.cjs`) and a dependency
  audit. Since release 2 the request identity pin also runs on its own, and each of its named tests must run and pass
  with none skipped (R2-3); the walk's tests must show at least 59 passing, none failed or todo, and every skip's reason
  must begin `no Playwright at` (R2-1). CI installs no Playwright, so it runs none of the
  browser tests: the walk's browser subtests (every quote of the dev preview's synthetic documents chosen in Chromium and
  judged, the fallback frame, the review dialog) report as skipped there, and the PDF drawing, the text layer and the
  library's worker are exercised in CI only through `tests/frontend/app.test.cjs`'s stand-ins; the walk's own reading of
  PDFs with the library in Node, and its judge over that reading, run in CI. The release proof runs the browser tests
  on the host, where Playwright is installed (`CPT_VERIFY_PLAYWRIGHT`, else `/opt/meddoc-pro/node_modules/playwright`),
  and records the counts: there `ops/test_walk.cjs` is the local browser gate (at least 104 tests, none failed, none
  skipped).
- After an install, `ops/walk.cjs` drives the real page with a synthetic document: upload, poll, the DOM and JSON
  contract, every quote chosen and judged by the walk's own search (below), an answer, an approval through the dialog,
  both reports re-downloaded byte for byte (the PDFs' wording scanned by `ops/scan_customer.py`, not by the walk), the denylist scan of the JSON, headers and page, a 390 px viewport, and every `/ops/` path refused to the
  customer. Since release 2 the walk holds a search's answer to the list's contract and every `/api/` answer's ETag to
  a quoted UUID (`contractFor`, `etagHits`), and `ops/scan_customer.py --all` follows the list's pages
  (`Scanner.every_page`) and fails when it listed fewer documents than `GET /api/session` counts (up to `--limit`);
  both send this release's client version.
- The walk judges the viewer instead of taking its word (DECISIONS D368, rounds 3 and 5). It reads every PDF it judges
  itself, in Node, with the pinned library the page draws with (its own upload's bytes, else the view address fetched in
  the page with its own session), and runs the matching rule on that reading (CORE-UX-DESIGN.md section 8: R1 overprint
  copies, R2 word edges with R2a numbers, R2b separate drawings and R2c Han and hiragana, R3 format characters, NFKC,
  white space dropped, whole characters, exact case first, the quote's page and the next, never another): it runs R1
  itself, so a viewer that flags no copy, or flags one the rule does not make, fails (the round-4 verifier's gap 2), and
  the same words at another size are no copy on either side (its gap 1). It holds the viewer to that reading: the page
  count, each drawn page's text layer span for span, the overprint flags both ways, the occurrences marked - count, place
  and case - each marked span where its item is drawn (from the item's transform and the page's viewport), the count,
  pages and note character for character, a "not found" only where its own search finds none, no mark on another page
  or inside a character; every page it requires drawn is painted and seen as drawn (brought back into view and read
  again first, as the viewer lets far pages go; screenshots of the page against its canvas, block by block outside the
  marks), shows ink where its reading has text and ink under its marks (a pixel darker
  than the paper by a share of the page's own contrast, so faint scanned ink counts); and the last quote marked is judged
  again after Zoom in and Fit width. The tolerances are measured and stated in CORE-UX-DESIGN.md section 9. The page's
  text stays out of the evidence, which keeps counts.
- **The browser speed gate** (`ops/test_viewer_speed.cjs`, release 2): eighteen tests in headless Chromium, through the
  shipped page against `ops/dev_preview_server.cjs`'s mock - what a page load and an opening ask the server for (no
  `/api/session` on load), the one fade, the worker made ready ahead, the re-open answered 304 with no body and drawn
  with the same pixels, the view asked for with the click, the wipes (another tab's sign-out, a session ended or a
  password to change met at either viewer's frame, `pagehide`) with nothing left in Web Storage, the Cache API or
  IndexedDB, a view whose read cannot be recorded never answered with PDF bytes, the lists above 200 documents, and a
  Word document's view across a later round's conversion. The first fourteen fail on release 1's page, their control.
  Every skip's reason begins `no Playwright at`. It is not in CI (`scripts/ci/verify-cpt-studio.sh` does not run it),
  and the installer neither runs nor checks it: it is a release gate, run on the host with the walk's browser tests
  before an install (RELEASE-2-SPEC 9.1).
- **The bench** (`ops/bench/`; release 2, R2-2 and R2-32) is never shipped: `deploy/.dockerignore` leaves `ops` out of
  the image, and `ops/test_bench.py` holds that and that no file of the folder is discovered as a test.
  `bench_run.py` measures one tree through that tree's own Django (`manage.py test <folder> --pattern bench_run.py`, a
  `TransactionTestCase`) and refuses, before a test database can be made, unless the database is the throwaway server
  (`127.0.0.1`, port 55461, never live's 55451), the test database's name starts `test_cptstudio_`, `CODING_MODE` is
  `disabled` and every server listens on loopback (`refusals`). The tree's gunicorn runs with its own
  `deploy/gunicorn.conf.py` (command-line overrides only) and its own settings, only the database, the static root and
  the originals folder pointed at throwaway copies (`bench_settings.py`); the walk's worker codes with a fake coder
  (`bench_worker.py`); `proxy.cjs` stands where nginx stands - a request id on every request, the server-side log of
  every answer, the blue/green flip - and `bench.cjs` drives headless Chromium, every host but 127.0.0.1 unresolvable,
  over deterministic synthetic data (`benchdata.py`: practices of 51 to 18,000 documents, each PDF with a 12-bit barcode
  of its number on page 1). Its parts (`PARTS`): cold, pause, server, queries, open, lists, office, load, records,
  left-behind, correct, walk, bluegreen, plans and requests; one output file per tree, round and part group, never
  overwritten, and a lock against two benches at once. `bench.cjs --rehearsal` runs the open, lists and office flows
  through nginx over TLS on a test instance at a private IPv4 address. **The judge** (`judge.py`: no Django, database
  or browser) answers PASS, FAIL or INVALID for B against A from those files and **the acceptance table**
  (`acceptance.json`: the specification's section 8 as 186 rows - the opening, the lists, the cold start and the web
  process, the front door, the records, correctness, nothing left behind, plans, blue/green, the coder and the walk -
  and three external rows the bench does not measure: the coder's blob ids, the Word corpus and the suites). INVALID
  means "run again": equal trees (but for a deliberate control), a tag's files from two trees or A not the release-1
  revision the table names, an unexpected status, a console error, a request off loopback, a load average above 8,
  release 1's own value off its recorded A by more than the larger of 20%, twice the row's A/A spread and one step of
  its instrument, too few samples, a missing or failed control, or a derived value the table does not carry. Otherwise
  a gated row is judged on its pooled median: an absolute limit as the number; a limit relative to A against A measured
  in the same session, a no-worse-than-A limit never tighter than A times (1 + twice the row's recorded A/A spread);
  and a gain counted only beyond twice that spread. The values derived from A - each row's recorded A, its spread, the
  floors - were written by `judge.py floors` from a valid A/A pair of release 1 measured on this host before any B (the
  table's `derived`: release 1 at 816045c72644, measured on 2026-11-26), never at run time.
- **The search's no-leak guards are closed-world** (integrated refutation round 2, I2-3): they compare everything a
  search leaves with what it may leave, instead of looking for forms of the words. In Django
  (`tests/test_lists.py` `SearchTests.test_a_marker_searched_for_is_in_no_record_event_log_or_header`, by
  `SearchCase.assert_a_search_leaves_only_ids_counts_and_fixed_words`) every row of every table - each model's base
  manager, Django's own tables included - is read before and after a served search and a refused one, and the
  difference must be exactly the served search's `AccessRecord`, the refused one's `SecurityEvent` `list.rate_limited`
  and the member's `list.member` rate window; the session must be unchanged, each answer's headers exactly the fixed set
  with no cookie, the log exactly the 429's one `django.request` line, and nothing printed. In node
  (`tests/frontend/app.test.cjs`, the R2-22 search test above 200 documents) every request the page makes while the box
  searches is compared whole with the search's own - one POST to the search address, no query string, exactly its four
  headers, the words in its body only - every other way a page can make a request (XMLHttpRequest, sendBeacon,
  EventSource, WebSocket, a worker, an image, a dynamic import, a navigation) must stay unused, and the markup drawn
  meanwhile may hold only the list's own elements and attributes. The checks for the words' forms stay as the second
  line.

## 10. What was removed

Lane E of the Fable coding build removed the earlier pipeline (DECISIONS D351-D352): text extraction and OCR, the GI
routing and context readers, the Corti adapter, the harness participants (Astra, Fable 5.1), the Gemini and Fable 5.2
interpreter with its event engine, validation, the review overlay, the earlier reports and customer API, their commands
and their tests. They remain in git history; their tables remain as legacy records (5.11).
