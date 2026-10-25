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
   auto-dropped. **Routing's status reading is advisory:** it reads declared
   wording, layouts and boxes, and it can miss wording it does not recognise
   (four refutation rounds found new phrasings every time). So nothing it decides
   is final without a reviewer: a status exclusion is a recommendation the
   reviewer confirms or reverses (5.7), and an approval is the reviewer's
   statement that the whole document, not only the cited passages, supports the
   code. The UI and reports never claim that unrecognised wording is caught.
   Wording outside every declared list is recorded, not chased, in
   `ACCURACY-RESIDUALS.md` for the adjudicated accuracy evaluation.
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
    bounded.py          pure stage work in a forked child under a wall clock and memory limit
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
  box glyph, or as the unread mark `[?]` where its state is not plainly what
  the page or the document shows (routing holds it; never a guessed state). The
  box spellings themselves are defined once, in `studio/ingest/symbols.py`, and
  every reader (extraction's printed boxes, routing, sections' option rows)
  derives its pattern from them. DOCX: symbol-font boxes (Wingdings, Wingdings 2, Webdings, Zapf
  Dingbats; the tables in `studio/ingest/symbols.py` are shared with PDF and
  include every box shape Unicode maps those fonts to), a `w14:checkbox`
  content control by its structure whatever symbols it is set to (from
  `w14:checked`), a list paragraph whose numbering bullet is a box, written ☐ /
  ☒ when its own list (a run of consecutive box-bulleted paragraphs; any other
  paragraph ends it) shows a checked box (a checklist) and otherwise as the
  unread mark `[?]` (a box-shaped bullet on its own may be a bullet), counted
  in a note, and a legacy
  FORMCHECKBOX, written in place of the field from `w:checked`, else
  `w:default`. A filled square ■ is kept as written (it is a bullet as often as
  a box). PDF: a displayed check-box or radio widget over a printed box (☐ / ☒,
  `[ ]`, `[x]`; the glyph's origin within the widget's width, or up to a
  quarter of its size, at most 4 pt, left of it) replaces that glyph with its
  own state, and a FreeText or stamp that shows only a mark (X, ✓) over one
  printed box makes it ☒. Where a printed box's state is not plainly what the
  page shows (a printed mark under a widget whose state is off; any other
  displayed annotation over it: an ink tick, a stamp drawn as paths, other
  typed text, a shape, a text or choice field that shows something (its value,
  or text its appearance draws); a printed box whose position cannot be read:
  inside a piece of text, inside a form XObject under a widget or a mark that
  checks, inside a rotated or unresolvable form under any mark; two candidates
  for one printed box; a widget or mark over several) extraction writes `[?]`,
  and the page is named and partial. Boxes a form XObject draws are placed
  through the form (its /Matrix and the transformation at its Do, through
  nesting), so a mark that is not a check reads them where they land. The page
  note names a form check box over a printed box only when a check box or radio
  button is involved; any other mark gets the unread-box note. Otherwise a
  widget writes its glyph and a space before the one upright piece of
  page-level text that starts just right of it on its baseline, replacing a
  printed box that starts that piece (`[?]` when the printed box shows a mark
  the widget's state denies), and writes nothing when two lines or boxes
  compete or another button on its row cannot be tied. An unchecked widget
  whose label may be the page text to its left on its row (not a list marker or
  a printed box), and whose own piece does not start with its option word,
  writes `[?]` instead of ☐ when that text may be its label: a widget after its
  label (no other widget is tied to that text), unless it is the first of a row
  of options read before their words (the piece it is tied to is another
  widget's left label, does not end with a colon, and the widget sits nearer
  that piece than the text on its left by `BOX_SLACK`); and the next widget of a
  row of options when it sits no nearer the piece on its right than the text on
  its left (measured from where each upright string's ink ends; where that
  cannot be measured, when a widget tied to its left piece may be its own
  label's). An unchecked widget before a line that runs on past a gap wider
  than 0.6 font sizes, before the next widget of its row, also writes `[?]`: it
  does not govern the next column. Text in a font that gives no widths is never
  measured. A label left of its box with no text after it, and a page drawn
  through a form XObject, get no glyph: routing's field-line rule reads them
  (5.3). A yes/no
  set (a check-box field with /Opt or several on-states) and a radio group write
  their chosen option in the form block (`<label>: <option>` or `<label>: no
  option selected`), with ☐/☒ before each option word they can be tied to. Either way the form block keeps
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
  and Redact marks, and the opaque fills of any displayed annotation's
  appearance laid over text (a Square or Circle, a FreeText white-out, a form
  field's background, and the /MK /BG background of a text or choice field the
  viewer draws itself: no appearance, or /NeedAppearances), are named and make
  the result partial: the text under them was read as written. A cover over a
  run of fill-in characters (spaces, underscores, and rules of three or more
  dots, hyphens or dashes) counts only where it hides the run's letters.
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
  and Word's library bullets are counted and dropped. Text formatted as struck
  through (w:strike or w:dstrike, on the run or through its character,
  paragraph or table style or the document defaults) and white text with
  nothing that may be painted behind it (no shading or highlight on the run,
  its styles, paragraph, table cell or table, no text box, no page colour) are
  read as written, named and make the result partial. A DOCX can be partial.

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
detected family (an intervention word written in a procedure, findings or
technique section belongs to one only when that family is named, by a service
name or its instrument, outside the history and plan sections: "EGD in 2020 was
normal." in the HPI never takes today's hemorrhoid banding), is an
examination, test, sedation, consent or person (a name that coordinates a
procedure with such a word, split only at the connectors routing defines,
gives that procedure as a held `gi.other` mention, never a performed one:
"Office visit and anoscopy were performed today." holds the E/M for a possible
same-day anoscopy), opens
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
  mention never contradicts today's service unless its clause says today; in
  a procedure family's aggregate a held performance statement (an uncertain
  reading with a `performed:` cue or the hedged-statement hold) outranks every
  mention of another encounter ("Assessment and plan: EGD was performed with
  biopsies. Repeat EGD in 3 months." reads uncertain, never planned). A
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
  today, and never on an E/M visit statement; a time whose nearest service is
  another family's than the passage's first ("Colonoscopy ... after a normal
  EGD performed last week") is unclear and holds, never dates it, unless,
  outside procedure, findings and technique sections, the two are one
  coordinated group joined only by and, or, a comma, a slash, &, then or as
  well as ("EGD and colonoscopy last month were unremarkable." dates both); and
  a visit statement that names another service never takes that service's
  status (it holds). A month of the service month qualified by early, mid,
  late, end of or beginning of, with no day, may not be the date of service and
  holds; May reads like the other months (after in, on, during, by, until,
  early, mid, late, end of or beginning of, with a space or a hyphen, with its
  day, and after last or past only when capitalised: the verb "may" is never a
  month); a time hold is a doubt, so it contradicts the family's other section
  evidence. History
  told by relative time or by another provider reads historical; an explicit
  performance cue under Indication reads uncertain unless its clause says
  today.
- In a plan section an explicit performance is held, and the plan default
  reads planned, except that a clause that says today holds (`PLAN_TODAY`):
  the plan default's own reading; a performance statement a hedge outranked
  ("Anoscopy was performed today and showed grade 2 hemorrhoids versus
  prolapse."); and a statement of the procedure's result (a reporting verb
  after the service name, with only names, "with", "and" or a today phrase
  between: "EGD today showed esophagitis versus reflux.", "EGD this morning
  revealed a Schatzki ring, likely the cause"), whatever hedge outranks it;
  also "Repeat colonoscopy today if bleeding recurs.", an accepted over-hold. A
  hedge, condition or discussion that states neither a performance nor a
  result keeps the visit approvable even when it says today ("Possible EGD
  today if symptoms persist.", "Discussed colonoscopy today; she will think
  about it.": the round 2 and 3 contract). A performance statement a hedge
  outranks with no today word in a plan section, in an indication or
  chief-complaint section, or in a history clause that says today, carries the
  stated-act hold (`_P2_HEDGED_STATEMENT`, read by validation as OTHER_STATED),
  so the E/M beside it is held as it is beside the unhedged statement. Round 3b's release of a past-tense
  performance that says today as performed was withdrawn in round 4: it fired
  on another thing's past tense ("the MRI that was done this morning"). A held
  plan passage that says today is a doubt about today's service, so another
  plan, history or negated mention of the family cannot outrank it. "As
  scheduled", "as planned" and "as arranged" keep a done service done; a
  request ("requested by the referring physician") reads uncertain, never
  historical.
- A status line or a later denial denies or holds the line above it: the next
  sentence ("Status: Cancelled.", "Not performed.", "Patient declined.",
  "Rescheduled."), a next line that names the same service and reschedules
  it, and a denying status line, a typed or boxed answer that the procedure
  was not done ("Procedure performed: No", "Procedure completed: ☐ Yes ☒ No")
  or a cancellation of the procedure up to six sentences further down or above
  (headings not counted; a sentence naming only the line's own family is read
  on, another family's service ends the reading) hold it. A status value with
  boxes is read option by option, never by its first word: any denying option
  whose own box is checked, disagrees, is unread or has no box holds. The
  status line's hold words (pending, incomplete, on hold, TBD, TBA, unknown,
  unclear, requested) are options too, but only beside their own mark (a hold
  word in a remark, "Completed ☒ (pathology pending)", is none); a boxed value
  with no option is read as text; when the yes/no word right before the first
  box is the option's own word ("Not done ☒") that box decides, and "Not
  performed" / "Not done" is one option word. A line listed under a label that
  denies performance ("Procedures not performed:", after any list marker the
  other readers strip, with parentheses in its words, or led by one box of any
  state: "1. Procedure(s) not performed:", "☐ Procedures not performed:"), or
  under a verbless denying heading ("Cancelled procedures:"), is held whatever
  it names (an intervention line too: "Cold snare polypectomy of the 6 mm
  sigmoid polyp." under "Procedures not performed:"), never newly negated; a
  colon-less denying line is no label. The lines
  that ask whether the procedure was done, cancelled or called off are read by
  one grammar shared by the typed reader, the form-field block, the status
  question and its answer: a lead (an indent, a list marker, "was/is/has/had",
  "the/this"), the noun, the participle (performed, completed, done,
  attempted, started), "today", a separator (':', '?', '=', '|', a dash, a tab
  or two spaces, also after the label's own '?' or ':') and a denial (No, None,
  N, Not done / performed / completed, N/A, NA, Not applicable). A status
  question answered with a denial and then nothing or a punctuated remark
  ("Procedure cancelled: No", "Procedure cancelled?: No - completed as
  planned.") holds and is never read as a cancellation, while "no" opening the
  reason stays one ("no driver available."); an answer running past
  `BOX_ANSWER_REACH` holds; a printed status question tied to a form field
  answered with a denial holds (`BOX_STATUS_ANSWER`). A short line denying
  another act or care step ("Sedation was not needed.", "Fluoroscopy was not
  used.") never denies the service. An option every denying option of which
  has its own unchecked box ("Procedure cancelled | ☐", "Completed ☒ Aborted ☐
  Cancelled ☐") states nothing, in every reader of the line (the status
  references, the called-off reader, the clause cues of every status an option
  carries, member negations and the section-silent stop alike: "Colonoscopy:
  ☒ Completed ☐ Cancelled" is not cancelled, and "☑ Cold snare polypectomy ☐
  Repeat in 3 years" does not plan the polypectomy); a status line's label is
  read by its options, never by the first box after it ("Colonoscopy: ☐
  Cancelled ☒ Completed" reads performed); an item the box reader gave another
  entry's box is held; and held rather than released are an unread or
  disagreeing option box, a passage across the option and other words, a line
  that selects nothing, a target item that is not itself checked, and option
  text with more than one run of option words (a remark: "☐ Cancelled - aborted
  at the splenic flexure"), each hold keeping the rank of the cue it replaces.
  A status row cited whole that names no item is held (`BOX_STATUS_UNSELECTED`),
  never read as a cancellation from its unchecked options' words; on a line
  naming no item, a selected "Not performed" / "Not done" option holds the
  service above it, and a passage that names no item but selects such an option
  is held; a line with no denying option is no such option.
- Hedges and hypotheticals hold: a hedge after the name ("Biopsies may have
  been taken", "were possibly obtained"), counterfactual and conditional
  wording ("Had there been a stricture, it would have been dilated", "If
  colonoscopy were done today, ..."), and bare "defer" / "postpone" in any
  section ("we decided to defer EUS" under Impression is a doubt, not
  silence).
- No fact is read from a clause about another procedure (a dated, planned,
  denied or doubtful one, or a prior exam named without a service name: "On a
  prior exam the cecum was reached"); a failed sub-act (terminal ileum,
  retroflexion) does not make a family that reached its expected extent
  incomplete; shorthand extents ("to cecum", "to TI", "to 30 cm", "to D2")
  and an extent label ("Extent: cecum", also an addendum's "Furthest extent
  reached: cecum.") are read, never one led by "Intended", "Expected" or
  "Target", and only when what follows the landmark is punctuation or a word of
  the closed list `cues.EXTENT_TAIL` (which holds the landmark table's own
  spellings: TI, neo-terminal, cecal, pole, base; "Extent: cecum (intended)."
  is unread); the value also ends at a next table cell, tab or column that opens
  one of a closed list of other report fields (preparation or its quality,
  BBPS, withdrawal or insertion time, sedation, complications, findings,
  retroflexion: "Extent: Cecum | Prep quality: Good"), and any other next cell
  stays in the tail. An extent label that names the expected depth (the
  cecum, terminal ileum or appendiceal orifice; the EGD's duodenal depth) but
  is unread for its tail never lets a shallower prose landmark read the
  procedure incomplete ("Extent: Cecum | Scope: Olympus" beside "inserted into
  the rectum"): the extent is withheld and asked, but only when the tail is
  neutral (a plain value, or a listed instrument, staff or room cell or field;
  any word no list reads, a negation word, an aim word such as intended, goal,
  attempted or hoped, or a cue other than a performance cue keeps the reading
  the prose gives) and the family's own text never denies reaching that
  landmark or a deeper one ("Cecum not reached." on the next line keeps the
  incomplete); a label short of the expected depth agrees the procedure was
  incomplete and keeps that reading. A label in an unrecognised section counts only in the
  product's addendum block and the PDF form-field and annotation blocks (never
  a preparation or complications line, which may be an outside report's: "Prior
  colonoscopy (outside facility, 2021):" + "Prep: adequate" + "Extent: cecum"
  says nothing of today's extent); a denied finding followed by the act it needed ("no polyps were
  found to remove") stays unresolved; a purpose clause may use "to further
  evaluate", "to eval", "to r/o"; intent is never read from a question or a
  presumed or unconfirmed statement.
- Sections open on a heading with or without a colon; discussion,
  counseling, education and "risks and benefits" headings are plan sections,
  as are "Pending procedures", "Orders", "Referrals" and "To do" when bare.
  With an answer of their own ("Referral: Dr. B. Synthetic", "Orders: CBC,
  INR") they plan only their own line and the lines its sentence runs on into;
  up to the next heading, a field naming no service or intervention ("Extent:
  cecum", "Withdrawal time: 8 minutes") reads in the section in force before
  the label, every other run of lines is held (`_SEC_AFTER_A_PLAN_LABEL`, never
  planned and never performed), and inside a plan or history section that
  section reads every line; a cited passage that starts in a procedure,
  findings or technique section and reaches into such a held line is held too.
  "Procedures performed today:" and its variants open a procedure section,
  except when answered none or N/A; below such a label opened while anything
  but a procedure, findings or technique section was in force (or nothing
  was), a line that only the label's section would read as performed is held,
  a line with its own performance cue included ("listed after '<the label
  line>', a performed-today label that may answer none"), and after a positive
  section the lines below are held when the label's answer carries a negation
  word; the label's own line and an item its checked box governs keep their
  reading. A numbered or bulleted plan label ("2. Upcoming procedures") opens a
  plan again, as before round 3b; a colon-less line that starts with
  Procedure(s) or Plan(s) plans only when every word after the noun is a plan
  word or a closed tail (going, moving, forward, from, here, onward(s), ahead:
  "Procedures planned", "Plan going forward"), otherwise the noun-last rule
  decides ("Plan for further management" plans) and, failing that, it is held
  like a phrase line ("Procedure completed as planned"). Inside a procedure,
  findings or technique section a colon-less line that reads as a phrase
  ("Changes of prior radiation therapy", "Surgical opinion for further
  management") or a numbered or bulleted item naming prior therapy ("2. Prior
  radiation therapy") opens an `other` section whose lines are held, a line
  with its own performance cue included (it may tell another time or a plan),
  never a history or plan one, and a second such line inside it is read as
  inside the section it stands in for; outside those sections such lines are
  held too, except inside a plan or history section, which reads them as
  before. A service line or a service field after a line cut on a plan,
  cancellation or denial verb ("Dr. Smith recommended") is held
  (`HELD_AFTER_A_CUT`), whatever list marker it carries (a table row is
  exempt); a line ending without closing punctuation in a kept booking ("...
  performed as planned") still cuts, an accepted over-hold. The product's addendum
  header is a section boundary of kind `other` that inherits nothing, and a
  heading on the line where a form block's section resumes wins. A prose line
  runs on into the next line after a word a sentence cannot end on, or after
  an auxiliary or subject with its verb (or "not to" / "to" with a listed
  verb) when the next line has no verb of its own; a line that answers a field
  ("Schatzki ring present: no"; also the last field of a line, or a column
  answer "Hiatal hernia      no"), marks an option ("☐ Yes ☒ No") or gives a
  spoken answer ("the patient said no") before a line with a clause of its own
  never runs on. A joined line reads exactly as the same text on one line,
  except that a negation reaching a service only across a line break after a
  line ending in an answer of its own (a field answered by a bare denial, a
  bare refusal "the patient declined") holds instead of negating: whose answer
  it is cannot be read. The line above is read whole, from its own start, and by
  sections' own answer readers (a dash, a column, a tab or the last field of the
  line; an option row; a field question of any length, its "?" included; a
  spoken answer after a comma or a colon), so the two never disagree. Cut prose
  ("Comment: because of time constraints, no") stays a wrapped sentence.
- The separately identifiable E/M statement counts only when it is about this
  encounter and nothing says it is not attested: no conditional or normative
  wording, no other encounter or setting unless it is this one ("this",
  "today's", "current", "same", "present", or "today" after it), no date or
  time expression for another encounter ("yesterday", "two days ago", "on
  10/14"), no box or mark on its line other than a checked box, no answer on
  the next line but a checked Yes, a lone checked box or a bare Yes (a
  statement ending with a colon needs one), no unchecked field line naming it,
  and no untied denying or answering field line on its page. The line under it
  is its answer unless its label answers for something else (it names an item,
  or is a field of the closed own-field list: complications, adverse events,
  blood loss, sedation, anesthesia, allergies, comments, notes, remarks,
  bleeding, interpreter, teaching physician, resident, disposition); an
  attestation word (attest, agree, confirm, acknowledge, separate, E/M,
  modifier, significant, identifiable) always makes it the answer; one mark
  with a short label of its own on that line ("☐ Attested", "Attested | ☐") is
  the statement's own box and attests only when checked, and a form field tied
  to that line that is not checked refuses it. A line under it that carries an
  attestation word, or a word negated in itself (unattested, disagree,
  unconfirmed), refuses it when that line carries a contrary word, or is a
  field or a marked line whose value does not affirm ("Notes: Not attested";
  also "Notes: Attested", an accepted over-hold).
- Check boxes (the contract with 5.1; pasted text is read the same way; the
  spellings are defined once in `studio/ingest/symbols.py`): unchecked ☐ □ ◻ ◽
  ❏ ❐ ❑ ❒, `[ ]` and `( )` with any inner whitespace, `[_]`; checked ☑ ☒ ✓ ✔
  ■ ⌧, `[x]` and `(x)` with optional inner whitespace, `[*]`, `[v]`. The "?"
  of the exact unread mark `[?]` that extraction writes is no question-mark
  hedge: the item it governs is held as unread, and so is a passage naming such
  an item besides itself, while the checked item beside it reads as checked
  (a typed "?", "(?)" or "[ ? ]" is a hedge as before). Other
  marks are unread and hold their item, never pass silently: another bracketed
  mark (`(•)`, `[?]`, `(o)`, `[/]`, `[-]`, `[+]`, `[N]`, `[Y]`), `{ }` and
  `< >` forms, the other white squares (U+25A2, U+2B1C, U+1F78E-U+1F793:
  typed, they are a bullet as often as a box), and on a line that marks
  options bare radio glyphs and answers in parentheses; boxes for one item that
  disagree, a yes/no pair with both options checked, a passage across items
  whose boxes differ ("☑ Cold snare polypectomy ☐ Biopsy" cited whole: the item
  it speaks for cannot be told from it, so it is never read by its first box
  and never negated), and a row whose boxes can
  be read as leading or trailing (the items the readings disagree on) hold too,
  as does an intervention joined by "with", "plus" or ";" to a later item
  whose own box is not checked (`BOX_LATER`). A box governs the item(s) on its own line or cell within
  `BOX_REACH`, before it (`☐ Biopsy`) or after it (`Biopsy | ☐`,
  `Biopsy: ☐`), and its option label is read on that line only, never from
  the line above ("Complications: none" then "☒ Cold snare polypectomy": the
  checked box is the polypectomy's own, never a "none" option); remarks after the last box do not change that, a label that
  names several items (`Biopsy/polypectomy | ☐`) is governed as a whole, a
  cell ending in a period stays one cell, and a yes/no pair is read by the
  option marked. An E/M visit statement a box governs is read by it too: held
  when its own box is unread, unchecked or disagreeing, or its form line is
  "not checked" ("[?] Established patient office visit.", "☐ Established
  patient office visit."), never negated; a checked box or no box reads as
  before, and visit-type option rows are read option by option. The `[PDF form fields on page N]` and `[PDF annotation text
  on page N]` blocks are section boundaries of kind `other` with no default
  (a field labelled with a procedure, findings or technique heading reads its
  value as that printed line would). `<label>: not checked`, `unchecked`, `no
  option selected` or a chosen denial option (`No`, `None`, `Not done`, `Not
  performed`) negates the printed item its label names on that page when the
  label is the item alone ("Biopsy", "Biopsy taken") or a widget's default name;
  a label naming the item among other words ("Flexible sigmoidoscopy in the last
  10 years: No") holds only its own passages, and a label of the closed list
  known to name no item (complications, adverse events, EBL, estimated blood
  loss, blood loss, sedation, anesthesia, allergies, comments, notes, remarks;
  also with "Any", "if any", a parenthesis or its own "?": "Complications:
  None") holds nothing, as does a status question the status-answer rule reads;
  any other label that names no known item fails closed: its selected denial
  holds its page's cue-less mentions (`BOX_FIELD_ANSWER_UNTIED`: "Polyps
  removed: No", "Cecum reached: No"). A short answer the reader cannot read
  ("N", "0", "N/A") holds a label naming an item. When the label matches no
  printed line, the page's service and intervention mentions without an
  explicit performance cue are held. A status field whose value is no
  completion, or a done-question answered no, holds its page's cue-less service
  mentions (`BOX_FIELD_STATUS`). `<label>: checked` and `<label>: Yes` are
  silent, so the rest of the document decides.
- Validation reads routing's cues by prefix (5.6): `uncertain: no performance
  evidence` (silent), `performed:`, `section: <kind>`, `PLAN_TODAY`,
  `OTHER_STATED` and the another-time prefix (`ANOTHER_TIME_PREFIX`). The box and
  field holds (`BOXES_DISAGREE`, `BOX_UNREAD`, `BOX_LATER`, `BOX_STATUS_OPTION`,
  `BOX_STATUS_ANSWER`, `BOX_STATUS_UNSELECTED`, `BOX_FIELD_HELD`,
  `BOX_FIELD_HELD_UNTIED`, `BOX_FIELD_ANSWER_UNTIED`, `BOX_FIELD_STATUS`) and
  the section holds (`_SEC_AFTER_A_PLAN_LABEL`, the performed-today label hold,
  `HELD_AFTER_A_CUT`) are uncertain cues like any other hold.
- Cost: each mention stores a bounded window of its sentence, not the whole
  sentence, and a member's pre-triggers are read once from its own bounded
  start, so a long coordinated list stays linear. Clause lookups take only the
  first or last few clauses they need (by bisection), and a line's done-question
  answer is read once per line. Every stage reads the
  document in ONE forked child under the stage's own wall clock
  (`JOB_DEADLINE_SECONDS`) and a memory allowance (`BOUNDED_MEMORY_BYTES`,
  `studio/bounded.py`): analyze extracts the context and routes in one child,
  and assess routes and runs the whole validation assessment (whose span
  readings reuse that routing's analysis) in one child, with the reference rows
  of the selected codes fetched in the worker first (`prefetched_lookup`; a code
  it was not given is an error, never an empty answer). An overrun fails the
  stage with a plain message instead of holding the worker; nothing a stage
  read stays cached in the worker (`jobs.release_routing_caches` after every
  stage is the backstop). A member's context change re-reads the document's
  facts in a child under `CONTEXT_REQUEST_SECONDS`, and is refused for a
  revision whose analysis never finished, so nothing is ever sent for a
  document the service could not read.

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
longer stands, so its one released attempt is made, and neither does a reserved
run the stale sweep settled as not sent (no started_at: it was never sent). Every member action that can queue a stage runs under the encounter
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
established, and one its documented status excluded (reinstatable) in a third
group with status `excluded`, never as performed and never left out —
otherwise `not_verified`,
since routing recognises only the profiled families), performed services with
no proposal
(`services.unproposed`, a possible missed code; each performed `gi.other`
procedure counts unless an exact evidence span of a selected, non-excluded
`gi.other` code speaks for it: the span overlaps that procedure's sentence and
no other done procedure's sentence, or its name and no other's, so a passage
across two procedures speaks for neither; a done mention that names again the
same single procedure as one such a code speaks for is covered too, when the
two names are equal as words or both lie in the code's one-procedure class
(46221 banding, 46600-46615 anoscopy; never a hemorrhoidectomy, and with no
other procedure word in the name: "Anoscopy with rubber band ligation" beside
46600 alone is still named); it is named when another `gi.other`
code is selected). Each check: `{id, label, status ∈ pass | warn | fail | not_verified |
not_applicable | info, detail, source}`. Engine `cpt-studio-validation@3`.

Same-day procedure, for the E/M hold (fail-closed): a performed non-E/M code
with a procedure profile or a global period other than XXX (no fee-schedule
row counts); a selected procedural code whose performance is uncertain; a
routed procedure family, or a routed `gi.other` service (global period
unknown, so it counts), read as performed — a coded test such as 91010
manometry counts too (round 4 removed round 3b's XXX discount); one read as
uncertain through a mention that can speak for the date of service — outside
plan, history and indication / chief-complaint sections any mention that hedges
or doubts (never a silent one; round 4 removed round 3b's release of hedges in
assessment, impression, examination and MDM sections, accepting round 3's
over-hold there); inside plan, history and indication / chief-complaint sections
an explicit performance statement that routing downgraded for its section, a
passage routing holds with PLAN_TODAY, and a mention routing holds as a stated
act or finding (OTHER_STATED) or at another time (ANOTHER_TIME); and an excluded procedural code whose own passage
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
interventions; a held coordinated `gi.other` mention is never such another
service) leaves the code ready with a warn
naming it, and a performance statement that only its section downgraded
supports the code; a hedge that names no service is the code's own for a
procedure code (fail-closed). Routing decides only when the
passage is silent (routing's default "no performance evidence" reading). An
E/M code's own passage that reads planned or historical only by its section
default (its HPI, its plan, its counseling) is silent too, so routing's E/M
reading decides; a cue that dates or plans the visit, or a visit statement
routing reads in that section ("Follow-up office visit." under Plan), keeps
its reading. An E/M code's negative reading decided by a cue, in a passage that
touches no routed E/M mention and names another service (a routed mention of
another family, a procedure or service name, or a test, imaging or laboratory
word), is about that service, not the visit: it holds the code, never excludes
it. A positive passage cannot establish a family that routing documents only as not
performed, nor a recognisable family the document never names or names only
as uncertain. A `gi.other` code's passage that reads performed by its section
alone, or only as the office visit's own documentation (no other `performed:`
cue), counts only where it names the code's OWN procedure done (by the
`gi.other` profile's number ranges, an internal list used only to hold):
- it states the code's own act today ("were banded today"; also "we" or "I"
  after an introductory phrase that names no other occasion, with the act's
  object after it: "Under anoscopic guidance we banded the right posterior
  column."), not in a relative clause (a relative pronoun up to three
  auxiliaries or adverbs before the act: "that had been banded"), and only when
  the act's clause tells no other time (routing's other-encounter time reader,
  or a date that is not the date of service: "Two columns were banded at her
  last visit and look healed today." holds);
- or routing corroborates it: a routed `gi.other` mention of that procedure read
  as done lies in it, it lies in the first sentence of a procedure section whose
  routed mention is done, or, read by its section alone, it opens with that
  procedure as the report's done procedure line names it ("Anoscopy revealed
  grade 2 internal hemorrhoids."); a routed stated-act mention whose clause
  tells another time never counts; and none of the three counts when any
  sentence of the document denies, cancels, cuts short or doubts that
  procedure (by name, as "the procedure", "the exam", "the study" or "it", or
  by its act verb; a plan or history mention is no such doubt), because
  routing's `gi.other` finding never reads such a denial ("Anoscopy was not
  performed; the patient declined." names no mention). A sentence's
  own-procedure words are read on their own for this too, since routing reads
  the clause after a `gi.other` name only for the name ("Anoscopy was
  incomplete because of pain." reads performed as a sentence and incomplete at
  "Anoscopy").
A passage that reads incomplete only through its detected family's
document-level judgement ("Procedure: Colonoscopy" when the colonoscopy stopped
at the splenic flexure) is judged by its own reading before that judgement
(`detect.own_status_for_span`): it states no procedure of a `gi.other` code.
Otherwise (`section_only`) the code is held, never excluded, with the reason
that the passage is not read as documenting that service as done on that date
(worded from what decided it: "reads as performed only by its section, and as
incomplete only through what the document says of the procedure it names").
Each of these questions is indexed once per code (the routed families' mention
spans for the other-service question, each sentence's leading name, the
own-procedure sentence readings), never rescanned per passage. An exclusion never presents the code's own passage as the
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
default like any other. It also reads routing's OTHER_STATED and ANOTHER_TIME
holds by their prefixes (the stated-act and another-time cues of 5.3; the
stated-act hold of a hedged performance statement, `_P2_HEDGED_STATEMENT`,
shares OTHER_STATED's prefix, and a test pins that). A passage
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
an acknowledgement that the reviewer read the whole document and it supports
the code: exactly the current attestation text for the reviewer's actor kind,
`review.ACKNOWLEDGEMENTS`, which `/api/session` serves to the page; any other
text is refused), `reject` (any selected proposal), `reinstate` (a reinstatable
excluded proposal → becomes reviewable, recorded), `confirm` (agree with a
reinstatable exclusion: it stays excluded, now with a named reviewer), `revoke`
(undo the reviewer's current decision). A reinstatable exclusion is a
documentation check's recommendation, so it needs `confirm` or `reinstate`
before a reviewed report exists ("<code> was excluded by a documentation
check: confirm the exclusion or reinstate it"); an exclusion for scope or
evidence (not reinstatable) needs nothing. Decisions are bound to assessment, revision,
proposal fingerprint and profile version. **New revision (source change):**
every current decision is invalidated (`DecisionInvalidation`, reason names
the new revision). **New assessment on the same revision (context change):**
a decision is carried (`carried_from`) only when a proposal with the same
fingerprint exists in the new assessment; otherwise invalidated with the
context field that changed. Readiness: a reviewed report is available only
when every selected proposal has a current approve/reject decision, every
reinstatable exclusion is confirmed or reinstated and decided; anything else
is draft-only, with the blocking items listed. While a
code marked `review.same_day_em` has a current reinstate or approve decision,
an E/M marked `em.same_day_if_reinstated` cannot be approved, and while that
E/M is still on its way to an approval (selected and undecided, reinstated, or
approved first) the reviewed report is blocked ("<E/M> needs a separately
identifiable E/M: <code> was reinstated as a same-day procedure"); rejecting
the E/M, confirming its exclusion, or rejecting or revoking the reinstatement
releases it.

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
