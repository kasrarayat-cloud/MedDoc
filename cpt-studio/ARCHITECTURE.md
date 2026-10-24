# CPT Studio — architecture contract

Owner directive: `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`.
This file is the contract every module is built against. If code and this file
disagree, that is a defect in one of them — fix it, do not paper over it.

## 1. What it is

A standalone, login-protected, **synthetic-only** website at `cpt.quillmd.com`
that turns an original clinical document (PDF, DOCX or pasted text) into
**CPT-only** proposals with exact source evidence, separate reference/rule
checks, scoped clarifications, persisted reviewer decisions and downloadable
reports.

Specialty **categories** are separate optimisation units. **Gastroenterology**
is the first and only category in this release: one GI workspace, one upload
flow, one combined results screen. GI **service families** are internal,
versioned routing and validation profiles — never navigation the doctor sees.

Independent of the QuillMD rebuild: no imports from `rebuild/`, no shared
database, users, files, venv, units or environment. Patterns were copied, not
imported.

### Non-goals in this release

- Real patient data, claims submission, payer adjudication, public launch.
- Licensed CPT descriptors or CPT code-set validity (no CPT edition is licensed).
- NCCI PTP edits (CMS serves them only behind an AMA point-and-click agreement).
- Choosing the production coding engine. Corti is the *initial* adapter.
- Accuracy claims. Accuracy needs independently adjudicated, withheld cases.

## 2. Truth rules (apply everywhere)

1. **Never fabricate**: no descriptor text, confidence percentage, source
   version, rule, pass result or clinical fact that is not backed by data the
   system actually holds. Missing → say what is missing.
2. **Provider display text is untrusted.** It may be stored for diagnosis; it is
   never shown or exported as a descriptor.
3. **Only provider-selected codes can become proposals.** Candidates and nested
   alternatives are listed separately and can never be approved.
4. **Exact evidence or nothing.** A proposal needs ≥1 evidence span whose text
   equals `canonical_text[start:end]` of the revision it belongs to.
5. **Status before code.** A service that is planned, historical, cancelled,
   negated or uncertain must not silently become a performed service.
   Incomplete procedures are routed to review, never auto-completed or
   auto-dropped.
6. **Agreement is not verification.** Nothing upgrades a status because two
   sources agree.
7. **Agent review is labelled as agent review** everywhere it appears.
8. **Synthetic only.** `SYNTHETIC_ONLY = True` is a constant, not a setting.
   Every upload requires an explicit synthetic attestation, and every export
   says SYNTHETIC — NOT FOR BILLING.

## 3. Stack and layout

Python 3.12, Django 5.2 (pinned as the rebuild pins it), PostgreSQL 17,
gunicorn, whitenoise. Text extraction with `pypdf` and `python-docx`; OCR with
`tesseract` + `pdftoppm` (poppler) inside the container image. One DB-backed
worker process. Buildless frontend: the approved design's `index.html`,
`styles.css` and `app.js`, adapted to a JSON API.

```
cpt-studio/
  ARCHITECTURE.md  README.md  requirements.txt  manage.py  .gitignore
  cptstudio/            settings.py urls.py wsgi.py
  studio/
    models.py           all persistent state (section 4)
    migrations/
    api.py              JSON API (section 7)
    views.py            SPA shell, login/logout, health
    access.py           workspace scoping, membership checks
    storage.py          immutable original-file store
    jobs.py             queue, pipeline stages, worker loop, Stop, reconcile
    audit.py            append-only audit events
    ingest/             extraction (section 5.1)  — pure + subprocess sandbox
    gi/                 GI category: context.py detect.py profiles.py (5.2/5.3)
    providers/          base.py corti.py replay.py (5.4)
    reference/          store.py importers.py (5.5)
    validation/         engine.py checks.py (5.6) — pure functions
    review.py           decisions, carry/invalidate, readiness (5.7)
    reports.py          TXT/CSV builders + persistence (5.8)
    management/commands/  run_worker, provision, import_reference, evaluate_cases
    templates/studio/   index.html (design shell), login.html
    static/studio/      styles.css (design, unchanged tokens), app.js (live)
  tests/                Django tests + fixtures (synthetic only)
  deploy/               Dockerfile, gunicorn.conf.py, nginx templates
  ops/                  install.py (ruled-mutation installer), browser verifier
```

## 4. Data model (`studio/models.py`)

All primary keys are UUIDs. "Immutable" rows refuse `save()` on an existing
row and refuse `delete()`; corrections are new rows.

| model | key fields | notes |
|---|---|---|
| `User` (AbstractUser) | `actor_kind` ∈ {human, agent}, `display_name` | agent accounts are labelled everywhere |
| `Category` | `slug` (gastroenterology), `name`, `profiles_version` | |
| `Workspace` | `name`, `category`, `synthetic_only=True` | |
| `Membership` | `user`, `workspace`, `role` ∈ {owner, reviewer, viewer}, `active` | unique (user, workspace) |
| `Encounter` | `workspace`, `title`, `created_by`, `current_revision`, `current_context`, `current_assessment`, `state` | `state` is derived/cached for lists |
| `SourceFile` | `encounter`, `original_name`, `media_type`, `size`, `sha256`, `storage_name`, `uploaded_by` | **immutable**; bytes stored 0600, never overwritten |
| `SourceRevision` | `encounter`, `number`, `kind` ∈ {upload, paste, addendum}, `source_file`, `parent`, `addendum_text`, `answers_clarification`, `synthetic_attested_by/_at`, extraction fields (`extraction_status` ∈ {pending, ok, partial, failed}, `extraction_method`, `text`, `text_sha256`, `pages` JSON, `messages` JSON, `engine` JSON, `extracted_at`) | extraction fields are write-once (pending → final) |
| `EncounterContext` | `encounter`, `revision`, `facts` JSON (name → {value, origin, evidence, note}), `user_values` JSON, `sha256`, `created_by` | **immutable** snapshot; `current_context` points at the latest |
| `RoutingRun` | `revision`, `version`, `result` JSON, `sha256` | deterministic, recomputable |
| `ProviderRun` | `encounter`, `revision`, `provider`, `adapter_version`, `request_sha256`, `request_body` JSON, `contexts` JSON, `state` ∈ {reserved, sending, succeeded, failed, unknown, not_sent, cancelled}, `sent`, `http_status`, `provider_request_id`, `response_sha256`, `response_bytes` (raw bytes as received), `latency_ms`, `usage` JSON, `usage_basis`, `error`, `run_identity`, `authorization_ref`, `reused_from`, `reconciled_by/_at/_note`, `service_date` (the date the request was built with) | one row per send attempt; never resent automatically |
| `Assessment` | `encounter`, `revision`, `context`, `routing`, `provider_run`, `profiles_version`, `engine_version`, `reference_sources` JSON, `encounter_checks` JSON, `unsupported` JSON, `sha256` | **immutable** |
| `Proposal` | `assessment`, `key`, `bucket` ∈ {selected, alternative, excluded}, `code`, `code_kind`, `family`, `profile_version`, `status` ∈ {ready, needs_clarification, excluded, informational}, `exclusion_reason`, `reinstatable`, `provider_display`, `evidence` JSON, `rationale`, `checks` JSON, `modifier_considerations` JSON, `units`, `fingerprint` | **immutable** |
| `Clarification` | `encounter`, `assessment`, `proposal` (nullable), `scope` ∈ {encounter, service, proposal}, `fact`, `question`, `reason`, `state` ∈ {open, answered, withdrawn}, `answered_by_revision` | |
| `Decision` | `encounter`, `assessment`, `revision`, `proposal`, `action` ∈ {approve, reject, reinstate, revoke}, `note`, `reviewer`, `reviewer_kind`, `acknowledgement`, `profile_version`, `proposal_fingerprint`, `carried_from`, `sequence` | **append-only**; `carried_from` set when a decision is carried to a new assessment of the SAME revision; `sequence` (a database sequence, assigned under the encounter lock) orders decisions — never the clock |
| `DecisionInvalidation` | `decision`, `reason`, `by_revision`, `by_context`, `created_at` | append-only |
| `Job` | `encounter`, `revision`, `kind` ∈ {extract, analyze, predict, assess}, `idempotency_key` (unique), `state` ∈ {queued, running, succeeded, failed, unknown, cancelled}, `attempts`, `max_attempts`, `deadline_at`, `stop_requested_at/_by`, `error`, `result` JSON | |
| `ReportArtifact` | `encounter`, `assessment`, `kind` ∈ {draft, reviewed}, `fmt` ∈ {txt, csv}, `content` (bytes), `sha256`, `snapshot_sha256`, `generated_by` | **immutable** |
| `AuditEvent` | `workspace`, `encounter`, `actor`, `actor_kind`, `event`, `data` JSON | append-only |
| `ReferenceSource` | `key`, `kind`, `publisher`, `title`, `release`, `url`, `sha256`, `retrieved_at`, `effective_start`, `effective_end`, `license_note`, `scope_note`, `row_count` | |
| `ReferenceCodeFact` | `source`, `code`, `modifier`, `facts` JSON | descriptors are never imported |

## 5. Pipeline modules (pure where possible)

Stages run as jobs: `extract → analyze → predict → assess`. Each stage is
idempotent (unique `idempotency_key`), has a deadline, and records failures
explicitly. A source change makes a new revision and a new pipeline; a
context-only change runs `assess` (and `predict` only if the provider input
changed — section 5.4).

### 5.1 `studio/ingest` — extraction

`extract_document(data, filename, media_type, *, limits=None, ocr=DETECT) -> ExtractionResult`
(and `extract_paste(text, *, method, limits)` for pasted text and addenda) runs in a subprocess with CPU/memory/file-size rlimits and a wall-clock
timeout. Result: `status` (ok | partial | failed), `method` (txt | docx |
pdf-text | pdf-ocr | pdf-mixed | paste), canonical `text`, `pages`
(`[{page, start, end}]` over the canonical text), `messages` (explicit,
user-facing limitations/errors), `ocr_pages`, `engine` versions.

Canonical text: `\r\n`/`\r` → `\n`, NUL removed, Unicode NFC, nothing else.
PDF pages are joined with `\n\n`; page spans are recorded. A PDF page with no
usable text layer is OCRed (tesseract via pdftoppm images) when OCR is
available; when OCR is unavailable or fails, the page is reported, never
silently skipped. DOCX: body paragraphs and tables (cells ` | `-joined, rows as
lines) in document order; headers/footers are listed in `messages` as not
extracted. TXT: UTF-8 (BOM stripped) or explicit decode failure.
Encrypted/corrupt/oversized/too-many-pages files fail with a specific message.

Never silently partial (`cpt-studio-ingest@3`): content a viewer would show is
read or reported, and content it would not show is excluded with a message.
- Check boxes (a contract with routing, 5.3): every box extraction recognises
  is written as ☐ (U+2610, unchecked) or ☒ (U+2612, checked), never another
  box glyph. DOCX: symbol-font boxes (Wingdings, Wingdings 2, Webdings, Zapf
  Dingbats; the tables in `studio/ingest/symbols.py` are shared with PDF and
  include every box shape Unicode maps those fonts to), a `w14:checkbox`
  content control by its structure whatever symbols it is set to (from
  `w14:checked`), a list paragraph whose numbering bullet is a box, and a legacy
  FORMCHECKBOX, written in place of the field from `w:checked`, else
  `w:default`. A filled square ■ is kept as written (it is a bullet as often as
  a box). PDF: a displayed check-box widget over a printed box replaces that
  glyph with its own state, and a FreeText or stamp mark (X, ✓) over a printed
  box makes it ☒; otherwise a widget writes its glyph beside the line it can be
  tied to (at the start of the upright line to its right, or after the line
  that ends just left of it, also inside form XObjects), and writes nothing when
  two lines or boxes compete. A yes/no set (a check-box field with /Opt or
  several on-states) and a radio group write their chosen option in the form
  block (`<label>: <option>` or `<label>: no option selected`), with ☐/☒
  before each option word they can be tied to. Either way the form block keeps
  `<label>: checked` / `<label>: not checked`, one blank-free line per entry.
- PDF symbol fonts read as the glyphs they draw: a simple symbol font through a
  copy whose ToUnicode maps every code (widths, and so the layout, unchanged),
  with /Encoding /Differences names resolved through the ZapfDingbats and
  Symbol glyph names (and uniXXXX); a composite one character by character,
  its Latin echo of a symbol code read as that code. A composite font that
  writes glyph indices (Identity, no ToUnicode, no CIDToGIDMap stream) is
  dropped, and a malformed ToUnicode entry never fails the document.
  Private-use and control characters are dropped and counted per page; the
  status stays ok, and dropped characters are not readable text.
- PDF forms and annotations: filled form values (text, choice, checked / not
  checked, radio — the selected widget's /Opt entry, found by its place in
  /Kids) and FreeText / stamp text are read into a labelled block after the page
  text; the headers `[PDF form fields on page N]` and `[PDF annotation text on
  page N]` are fixed. A field whose stored value differs from what its
  appearance draws, or any XFA form, makes the result partial. The comparison
  first applies Acrobat's standard formats to the value (`AFNumber_Format`,
  `AFPercent_Format`, `AFDate_FormatEx`, `AFDate_Format`, `AFTime_Format`,
  `AFTime_FormatEx`, `AFSpecial_Format`, exactly one call with literal
  arguments, rendered as pdf.js renders them); any other script or an
  unparsable value keeps the difference. An appearance that exists but draws
  no text differs from a non-empty value; one that cannot be read is counted as
  unreadable; a FreeText whose own appearance layer is off is hidden. StrikeOut
  and Redact marks and opaque annotations laid over text are named and make the
  result partial: the text under them was read as written.
- PDF pages: a page at least half covered by images with under 200 characters
  of text is OCRed; without OCR it is named and the result is partial, keeping
  its text layer (a page with no text at all fails). Images a displayed
  annotation's appearance paints count as page images. Dense images covering a
  fifth of the page or more get the large-image note. Text is judged where it
  lands on the page, at every depth of forms: drawn wholly outside the visible
  page (the crop box within the media box) by more than one em, outside a
  form's box, or outside a clipping path (rectangles exactly, other paths as
  polygons), it is excluded and the page named; OCR renders the crop box.
  Text a viewer may not show is read, named, and makes the result partial:
  white text with nothing painted under it, text a later opaque fill or image
  covers, invisible text (render mode 3, or under 5% opacity) over nothing,
  zero-size text, a line drawn through text, and clips or pages too complex to
  follow within the work budgets. Optional content that is OFF by default is
  excluded and named.
- PDF integrity: every stream the text depends on must decode to the end its
  encoding declares (Flate; LZW to its end-of-data code; RunLength to its
  end-of-data byte). On OCR pages so must every image: Flate followed to its
  end within a budget of four times the declared size, JPEG, CCITT Group 4 to
  EOFB, Group 3 to RTC or one EOL per row, JBIG2 in whole segments, JPEG 2000
  to its end-of-codestream marker. An image that cannot be checked makes the
  result partial ("could not be checked for completeness"). A page count that
  disagrees with the page tree, or a file truncated inside an incremental
  update, fails; whitespace, NUL, 0x1A, comment lines and repeated end markers
  after the last `%%EOF` are padding, not an update.
- DOCX: text hidden through direct formatting or a character, paragraph or
  table style is excluded and counted; a content control is a placeholder only
  when its flag is on; comments or processing instructions inside a run never
  cut it; `mc:AlternateContent` reads the first Choice this reader understands,
  else the Fallback (partial when neither); symbol-font glyphs other than boxes
  and Word's library bullets are counted and dropped. A DOCX can be partial.

### 5.2 `studio/gi/context` — encounter context

`extract_context(text) -> dict[name, Fact]` for `service_date`, `setting`,
`billing_context` (professional | facility | not_documented),
`patient_status` (new | established). `Fact = {value, origin ∈ {document,
user, missing, conflict}, evidence: [{start,end,text}], note}`. Conflicting
documented values → `conflict` (never pick one silently). User-supplied values
(service date, setting, billing context) override with `origin=user` and are
recorded as encounter metadata, never as clinical facts.

### 5.3 `studio/gi/profiles` + `studio/gi/detect` — routing

`PROFILES` (`gi-profiles@2`): versioned internal profiles. Supported:
`gi.office_em`, `gi.egd`, `gi.colonoscopy`, `gi.flex_sig`, `gi.eus`,
`gi.ercp`. Recognised without a profile (review required): `gi.sedation`,
`gi.em_other`, `gi.other`. Codes outside every GI range route to
`gi.unsupported`. Each has `version`, `label`, card `eyebrow`, numeric code
ranges used **only for routing**, `required_facts`, `procedure`, and
`supported` (bool).

`route(text, service_date) -> RoutingResult` (`gi-routing@3`) detects
documented services per family with: mention span, containing sentence span,
section (procedure, findings, technique, impression, indication, history,
plan, assessment, other), status (performed | incomplete | planned |
historical | cancelled | negated | uncertain) with the cues that decided it,
and family facts with evidence (extent reached, interventions/technique,
anatomic location, intent screening/surveillance/diagnostic, prep quality,
E/M basis: total time / MDM, the separately identifiable E/M statement).
Status is **fail-closed**: "performed" needs positive evidence; anything
ambiguous is `uncertain`. Plan/recommendation sections and future dates
default to `planned`; history sections to `historical`.

The six supported families are `DETECTED_FAMILIES`. Routing also emits one
`gi.other` finding for procedures documented at this encounter that name none
of them. It is recognised by form, not by a list of names (-scopy, -ectomy and
similar endings, ligation, banding, biopsy...): the first sentence of a
procedure section and the items on its check-box lines; the subject of
"<procedure> was performed" (also with the act as a verb: "were banded today",
"we banded"); the object of "underwent" or "we performed"; and a label line
("Anoscopy: grade 2 ..."). A name is never `gi.other` if it belongs to a
detected family, is an examination, test, sedation, consent or person, opens
with a negation, condition or plan word, or is told as history (a history
qualifier before it, or a time or visit that is not today's). Each mention is
read on its own; the family reads performed, then incomplete, then uncertain if
any mention does, otherwise the usual aggregate. `gi.other` stays outside
`DETECTED_FAMILIES`: a `gi.other` code's own status comes from its own passage
(5.6).

New wording rules only hold (uncertain, with a non-silent cue): they never
newly exclude a service or release one. The rules below follow that, except
where a rule restores what an ordinary note read before round 3b.

- A family's status ranks what its mentions say of today's service
  (incomplete, cancelled, negated today, uncertain) before what they say of
  other encounters (never before, historical, planned); a plan or history
  mention never contradicts today's service unless its clause says today. A
  family's reading reaches its explicitly performed passages only as
  cancelled, incomplete or uncertain, never as planned, historical or negated.
- A service's whole clause is read for qualifiers (a later or outside date,
  outside provider, pending, TBD, last year, a refusal before its name or
  after its interventions); a time expression in its own clause that is not
  today's and no listed cue reads ("next Tuesday", "in 2 wks", "recently",
  "two weeks prior") holds it. A relative time or an outside place is the
  service's only when it dates the service's own act: never the time of a
  test, result or diagnosis named between them ("for a positive FIT last
  month", "to review a CT scan done last week"), never in a clause that says
  today, and never on an E/M visit statement. History told by relative time
  or by another provider reads historical; an explicit performance cue under
  Indication reads uncertain unless its clause says today.
- In a plan section an explicit performance is held, and the plan default
  reads planned, except: a past-tense performance with a same-clause today
  marker ("today", "this morning") and no condition, possibility, future,
  plan word or question in the passage reads performed; and a clause that
  says today with none of those holds (`PLAN_TODAY`), so a conditional plan
  line ("Repeat colonoscopy today if bleeding recurs.") still plans. "As
  scheduled", "as planned" and "as arranged" keep a done service done; a
  request ("requested by the referring physician") reads uncertain, never
  historical.
- A status line or a later denial denies or holds the line above it: the next
  sentence ("Status: Cancelled.", "Not performed.", "Patient declined.",
  "Rescheduled."), a next line that names the same service and reschedules
  it, and a denying status line or a cancellation of the procedure up to six
  sentences further down (headings not counted) hold it; a service listed
  under a label that denies performance ("Procedures not performed:") is held.
  A short line denying another act or care step ("Sedation was not needed.",
  "Fluoroscopy was not used.") never denies the service, and an option its own
  unchecked box leaves unselected ("Procedure cancelled | ☐") states nothing.
- Hedges and hypotheticals hold: a hedge after the name ("Biopsies may have
  been taken", "were possibly obtained"), counterfactual and conditional
  wording ("Had there been a stricture, it would have been dilated", "If
  colonoscopy were done today, ..."), and bare "defer" / "postpone" under a
  positive section.
- No fact is read from a clause about another procedure (a dated, planned,
  denied or doubtful one, or a prior exam named without a service name: "On a
  prior exam the cecum was reached"); a failed sub-act (terminal ileum,
  retroflexion) does not make a family that reached its expected extent
  incomplete; shorthand extents ("to cecum", "to TI", "to 30 cm", "to D2")
  and an extent label ("Extent: cecum", also an addendum's "Furthest extent
  reached: cecum.") are read, never one led by "Intended", "Expected" or
  "Target"; a denied finding followed by the act it needed ("no polyps were
  found to remove") stays unresolved; a purpose clause may use "to further
  evaluate", "to eval", "to r/o"; intent is never read from a question or a
  presumed or unconfirmed statement.
- Sections open on a heading with or without a colon; discussion,
  counseling, education and "risks and benefits" headings are plan sections,
  as are "Pending procedures", "Orders", "Referrals" and "To do";
  "Procedures performed today:" and its variants open a procedure section. A
  numbered or bulleted list item is never a colon-less heading, and a
  colon-less label must end with its section noun. The product's addendum
  header is a section boundary of kind `other` that inherits nothing, and a
  heading on the line where a form block's section resumes wins. A prose line
  runs on into the next line after a word a sentence cannot end on, or after
  an auxiliary or subject with its verb (or "not to" / "to" with a listed
  verb) when the next line has no verb of its own; a line that answers a field
  ("Schatzki ring present: no") or marks an option ("☐ Yes ☒ No") never runs
  on. A joined line reads exactly as the same text on one line.
- The separately identifiable E/M statement counts only when it is about this
  encounter: no conditional or normative wording, no other encounter, no date
  or time expression for another encounter ("yesterday", "two days ago", "on
  10/14"), and no box governing it that is unchecked, disagrees or cannot be
  read.
- Check boxes (the contract with 5.1; pasted text is read the same way):
  unchecked ☐ □ ◻ ◽ ❏ ❐ ❑ ❒, `[ ]` and `( )` with any inner whitespace,
  `[_]`; checked ☑ ☒ ✓ ✔ ■ ⌧, `[x]` and `(x)` with optional inner
  whitespace, `[*]`, `[v]`. Another bracketed mark (`(•)`, `[?]`, `(o)`,
  `[/]`) is unreadable and holds its item, as do boxes for one item that
  disagree. A box governs the item(s) on its own line or cell within
  `BOX_REACH`, before it (`☐ Biopsy`) or after it (`Biopsy | ☐`,
  `Biopsy: ☐`); remarks after the last box do not change that, a label that
  names several items (`Biopsy/polypectomy | ☐`) is governed as a whole, a
  cell ending in a period stays one cell, and a yes/no pair is read by the
  option marked. The `[PDF form fields on page N]` and `[PDF annotation text
  on page N]` blocks are section boundaries of kind `other` with no default
  (a field labelled with a procedure, findings or technique heading reads its
  value as that printed line would). `<label>: not checked`, `unchecked`, `no
  option selected` or a chosen denial option (`No`, `None`, `Not done`, `Not
  performed`) negates the printed item its label names on that page; when the
  label matches no printed line, the page's service and intervention mentions
  without an explicit performance cue are held. `<label>: checked` and
  `<label>: Yes` are silent, so the rest of the document decides.
- Validation reads routing's cues by prefix (5.6): `uncertain: no performance
  evidence` (silent), `performed:`, `section: <kind>`, and `PLAN_TODAY`.
- Cost: each mention stores a bounded window of its sentence, not the whole
  sentence, and a member's pre-triggers are read once from its own bounded
  start, so a long coordinated list stays linear.

### 5.4 `studio/providers` — proposal adapters

`get_provider()` reads the provider mode (the only settings reader);
`normalizer_for(provider)` re-reads a STORED run without credentials.
`ProposalProvider` protocol: `name`, `adapter_version`,
`build_request(text, service_date) -> ProviderRequest` (body, canonical
sha256, contexts as sent), `send(request, deadline_s) -> RawExchange`
(outcome succeeded | failed | unknown | not_sent, bytes, sha256, status,
latency, usage, provider request id, error), `normalize(request, bytes) ->
NormalizedResponse` (codes with role selected | candidate | alternative,
evidence spans checked for exactness, internal non-CPT codes kept as
internal context only, parse problems).

`CortiProvider` (live): OAuth2 client credentials at
`https://auth.{env}.corti.app/realms/{tenant}/protocol/openid-connect/token`,
`POST https://api.{env}.corti.app/v2/tools/coding/` with `Tenant-Name`.
Body `{"system": ["icd10cm-outpatient","cpt"], "context": [{"type":"text",
"text": <canonical text>}, {"type":"text","text":"Date of service:
YYYY-MM-DD"}?]}` — the proven contract. Credentials come from a protected
dotenv file named by `CPT_STUDIO_CORTI_CREDENTIALS_FILE`
(`CORTI_CLIENT_ID`, `CORTI_CLIENT_SECRET`, `CORTI_ENVIRONMENT`,
`CORTI_TENANT_NAME`), parsed as data, never logged. `requests.Session`
with `trust_env=False`, `max_retries=0`, `allow_redirects=False`, connect
10 s / read 120 s, request ≤ 512,000 bytes (refused, never truncated),
response ≤ 4 MiB. Usage = `usageInfo.creditsConsumed`, basis
`provider_reported_credits_not_usd`.

`ReplayProvider` (tests/dev only): returns recorded bytes for a known request
hash; its runs are stored with `provider='replay'` and labelled REPLAY — it
can never present as live output.

Send discipline (`jobs.py`): live mode requires `CPT_STUDIO_PROVIDER_MODE=live`,
a configured `CPT_STUDIO_AUTHORIZATION_REF`, an active owner/reviewer
membership, and a synthetic-attested revision. A `ProviderRun` is written
`reserved` before any network I/O; single-flight via a PostgreSQL advisory
lock; no automatic retry; `unknown` (sent, no response) blocks resubmission
until a member records a reconciliation note. **Reuse**: if a `succeeded`
run exists for the same provider + adapter version + request sha256, it is
reused (`reused_from`) and no paid call is made. Context-only changes that do
not change the request (setting, billing context) never re-predict; whether the
request changed is decided against the run in use, never the previous
context. The run in use is the revision's newest request that finished,
whether or not an assessment was made with it (a Stop during the send or a
swept or expired assess cancels that assess); a reconciled unknown outcome no
longer stands, so its one released attempt is made. Every member action that can queue a stage runs under the encounter
row lock and is refused while a stage is queued or running. The predict stage
sends only the current revision's text with that revision's current context;
each run records the service date it was built with, and assessment refuses
to pair a run with a context of another date. The worker re-runs its
stale-stage sweep every minute, so an orphaned send becomes `unknown` without
a restart.

### 5.5 `studio/reference` — reference sources

`ReferenceSource` rows describe what is actually installed (publisher,
release, URL, sha256, effective window, license/scope note). Importers load
only code-keyed facts and **drop descriptors**:

- `cms-pfs` (RVU26D, PPRRVU nonQPP CSV): status code, global days, multiple
  procedure indicator, endoscopic base code, PC/TC indicator.
- `cms-mue-practitioner` (2026-Q4 practitioner MUE table): MUE value,
  adjudication indicator, rationale.

`lookup(code, service_date) -> {pfs, mue, coverage}`; a source applies only
when `effective_start <= service_date <= effective_end`.

### 5.6 `studio/validation` — checks (pure)

`assess(text, pages, context, routing, normalized, reference) ->
AssessmentResult`. Per selected code: scope (CPT Category I/III kept; Category
II and HCPCS Level II excluded with reason — CPT-only results), exact
evidence, family routing, service status vs routing, required facts →
scoped clarifications, CMS PFS presence for the service date, MUE units,
endoscopic-family combinations, E/M + same-day procedure (global days) →
separately identifiable E/M not established, modifier *considerations*
(never assigned), CPT membership `not_verified`, descriptor `withheld`, NCCI
PTP `not_verified`. Encounter checks: extraction status, service date,
services outside the GI profiles (`services.unsupported`: warn when any is
selected or detected — a selected one held for clarification is listed as not
established, never as performed and never left out — otherwise `not_verified`,
since routing recognises only the profiled families), performed services with
no proposal
(`services.unproposed`, a possible missed code; each performed `gi.other`
procedure counts unless a selected `gi.other` code's exact evidence lies in its
sentence, and is named when another `gi.other` code is selected). Each check: `{id, label, status ∈ pass | warn | fail | not_verified |
not_applicable | info, detail, source}`. Engine `cpt-studio-validation@3`.

Same-day procedure, for the E/M hold (fail-closed): a performed non-E/M code
with a procedure profile or a global period other than XXX (no fee-schedule
row counts); a selected procedural code whose performance is uncertain; a
routed procedure family, or a routed `gi.other` service (global period
unknown, so it counts), read as performed — unless a selected, non-excluded
`gi.other` code whose fee-schedule row gives the global period XXX covers that
mention's name with its exact evidence and the name holds one procedure (a coded
test such as 91010 manometry); one read as uncertain through a
mention that can speak for the date of service — in procedure, findings,
technique, unheaded and other sections a mention that hedges or doubts (never a
silent one); in assessment, impression, examination, MDM and time sections,
which weigh a procedure as a plan does, one whose cues are not all routing's own
hedge words (pending, an abort, anything validation does not read as a hedge),
whose sentence says today near it, or that is a downgraded performance
statement;
inside plan, history and indication / chief-complaint sections only an explicit
performance statement that routing downgraded for its section; and an excluded procedural code whose own passage
states the act although only the family's document-level reading makes it
negative. A routed `gi.other` finding gathers different procedures, so it is
read mention by mention (one mention read as done is a same-day procedure,
whatever the family status ranks first) and never for a code's own status: a
code of a family routing does not detect is judged by its own passages alone.
On an E/M with no same-day procedure detected, `em.same_day_coverage`
(`not_verified`) says a procedure of another kind is not detected; if an
excluded, reinstatable procedural code exists and no separately identifiable
E/M is documented, the E/M carries `em.same_day_if_reinstated` and each such
code `review.same_day_em` (both warn), which review enforces (5.7).

Status resolution is fail-closed: a code's own linked passage decides first;
a passage that hedges holds the code — routing never overrides it, and neither
does another of the code's own passages that reads as performed (`contested`:
the clarification names both passages) when the hedge is about the code's own
service. Beside a performed passage, a hedge about another service (for an E/M
code one that touches no E/M documentation routing reads; for another code one
that names only another family's service and none of the code family's
interventions) leaves the code ready with a warn
naming it, and a performance statement that only its section downgraded
supports the code; a hedge that names no service is the code's own for a
procedure code (fail-closed). Routing decides only when the
passage is silent (routing's default "no performance evidence" reading). An
E/M code's own passage that reads planned or historical only by its section
default (its HPI, its plan, its counseling) is silent too, so routing's E/M
reading decides; a cue that dates or plans the visit, or a visit statement
routing reads in that section ("Follow-up office visit." under Plan), keeps
its reading. A positive passage cannot establish a family that routing documents only as not
performed, nor a recognisable family the document never names or names only
as uncertain. A `gi.other` code's passage that reads performed by its section
alone, or only as the office visit's own documentation (no other `performed:`
cue), counts only where it names a procedure — a
sentence of it opens with a procedure name by routing's `gi.other` form rule,
it states a procedure's act by its participle ("were banded"), or a routed
`gi.other` mention read as done lies in it; otherwise (`section_only`) the code
is held, never excluded. An exclusion never presents the code's own passage as the
service "documented as performed elsewhere". Routing and span status read
dated history against the encounter's effective service date (a member value
overrides the document's).

Validation reads routing's cues by prefix, a contract with 5.3:
`uncertain: no performance evidence` (silent), `performed:` (an explicit
performance statement), `section: <kind>` (a section downgrade),
`performed: office E/M documentation` (the visit's own documentation, never a
procedure's) and routing's PLAN_TODAY cue (`uncertain: its clause says today,
so its plan section does not make it planned`): such a plan mention can speak
for the date of service, and for an E/M code's own passage it is a section
default like any other. It reads a hedge only from routing's own hedge words
(5.3's uncertain cue lists), so any other uncertain cue is a doubt. A passage
that states the act but is held because of its section is reported as
"stated as performed under <section>; confirm it was performed on the date of
service", citing the section cue, never as "no documentation establishes".

Proposal status: `excluded` (scope, no exact evidence, planned / historical /
cancelled / negated status — reinstatable by a reviewer where the exclusion
is a documentation judgement; its `review.reinstatement` check records what
approval would wait for), `needs_clarification` (an open clarification
scoped to it), otherwise `ready`. Clarifications are scoped to the affected
service; an encounter-scoped clarification is used only when the missing fact
is essential to every service (service date). Fingerprint =
sha256(code, family, profile version, evidence texts, check statuses,
relevant context values).

### 5.7 `studio/review` — decisions

Actions: `approve` (only `ready` proposals on the current assessment, with
acknowledgement), `reject` (any selected proposal), `reinstate` (a reinstatable
excluded proposal → becomes reviewable, recorded), `revoke` (undo the
reviewer's current decision). Decisions are bound to assessment, revision,
proposal fingerprint and profile version. **New revision (source change):**
every current decision is invalidated (`DecisionInvalidation`, reason names
the new revision). **New assessment on the same revision (context change):**
a decision is carried (`carried_from`) only when a proposal with the same
fingerprint exists in the new assessment; otherwise invalidated with the
context field that changed. Readiness: a reviewed report is available only
when every selected, non-excluded proposal has a current approve/reject
decision; anything else is draft-only, with the blocking items listed. While a
code marked `review.same_day_em` has a current reinstate or approve decision,
an E/M marked `em.same_day_if_reinstated` cannot be approved, and if it was
approved first the reviewed report is blocked ("<E/M> needs a separately
identifiable E/M: <code> was reinstated as a same-day procedure"); rejecting
or revoking the reinstatement releases it.

### 5.8 `studio/reports` — exports

`generate(encounter, kind, fmt, user) -> ReportArtifact` renders from a snapshot
of persisted rows, stores bytes + sha256 + snapshot sha256, and downloads
stream the stored bytes. TXT is the coding report; CSV is one row per item
(approved, rejected, undecided, excluded, alternative) with formula
neutralisation (`=`, `+`, `-`, `@`, tab, CR prefixed with `'`). In both formats
a C0 control other than tab and line breaks, DEL and a C1 control print as
`\xNN`; in the TXT a line break of any form continues the value at seven
spaces or deeper, below every structural line. Draft:
"DRAFT — NOT REVIEWED", no "approved selections" section. Reviewed: approved
selections only in the approved section; rejected listed as excluded from
approved results; reviewer identity, kind and time; agent review labelled
"agent-executed synthetic review — not clinical approval". Both: source file
name + sha256, revision number + text sha256, assessment id, profile and
engine versions, provider runs and usage, reference sources with releases,
every not-verified item, open clarifications, SYNTHETIC — NOT FOR BILLING.

## 6. Security

Login required for everything except `/health/` and `/login/`. No public
sign-up; accounts are provisioned by command. Argon2 passwords, login
throttling, `SESSION_COOKIE_SECURE`, `HttpOnly`, `SameSite=Strict`, CSRF on
every mutation, CSP without inline script, `X-Frame-Options: DENY`, HSTS
(behind nginx), `X-Robots-Tag: noindex`. Every query is scoped to a workspace
the user is an active member of; cross-workspace access answers 404. Uploads:
≤ 15 MB, extension + magic-byte check, random storage names, 0600, outside
static roots. Provider credentials never reach the browser, logs or exports.

## 7. JSON API (all under `/api/`, session auth, CSRF header on POST)

| method | path | purpose |
|---|---|---|
| GET | `session` | user, actor kind, workspace, category, counts |
| GET | `encounters` | list with derived status, service date, families |
| POST | `encounters` | multipart: `file` or `text`, `title`, optional `service_date`, required `synthetic_attestation=yes` → encounter + revision + pipeline |
| GET | `encounters/<id>` | full state: revision text + pages + extraction, context facts, routing summary, assessment (proposals by list, checks, clarifications), current decisions + history, jobs, provider runs (no secrets), activity, readiness |
| POST | `encounters/<id>/decisions` | `{proposal_id, action, note, acknowledgement}` |
| POST | `encounters/<id>/addenda` | `{text, clarification_id?, synthetic_attestation}` → new revision |
| POST | `encounters/<id>/context` | `{service_date?, setting?, billing_context?}` → new context + assess |
| POST | `encounters/<id>/stop` | stop queued/running stages (before send) |
| POST | `encounters/<id>/reconcile` | `{provider_run_id, note}` → allow one new attempt after `unknown` |
| POST | `encounters/<id>/reports` | `{kind, fmt}` → artifact id + sha256 |
| GET | `reports/<id>/download` | stored bytes, attachment |
| GET | `encounters/<id>/original` | original upload bytes, attachment |

## 8. UI mapping (approved design, preserved)

Same shell, tokens, typography, breakpoints and components as the design
package. Live content replaces samples: workspace picker shows the GI
workspace; documents list and review queue come from `/api/encounters`; the
review screen shows the extracted original text with evidence marks at exact
offsets beside one combined list of code cards (family label as the card
eyebrow), with Suggestions / Checks / Activity tabs; alternatives and
excluded candidates are listed separately below the selected codes;
clarifications appear inside the affected card (and as one card for
encounter-scoped questions); export dialog offers the TXT report and CSV,
labelled draft or reviewed. Status labels: Ready for review, Needs
clarification, Not verified, Reviewed, Rejected, Excluded.

## 9. Verification

Unit tests for every pure module; Django tests for API, isolation, storage
immutability, decisions/invalidation, reports-vs-database, job dedupe/Stop/
unknown handling. Browser verification (Playwright) of the deployed site with
fresh synthetic documents. Evaluation (`evaluate_cases`) computes per-family
complete-case correctness, missed/extra codes, modifiers and review frequency
**only** against independently adjudicated cases supplied separately; none
are available in this release.
