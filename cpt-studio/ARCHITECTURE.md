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
| `RoutingRun` | `revision`, `version`, `result` JSON, `sha256`, `service_date` (the effective date it was routed for; null on rows recorded before migration 0005) | deterministic, recomputable |
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
  derives its pattern from them.  DOCX: symbol-font boxes (Wingdings, Wingdings 2, Webdings, Zapf
  Dingbats; the tables in `studio/ingest/symbols.py` are shared with PDF and
  include every box shape Unicode maps those fonts to), a `w14:checkbox` content
  control by its structure whatever symbols it is set to (from `w14:checked`), a
  list paragraph whose numbering bullet is a box, written ☐ / ☒ when its own
  list (a run of consecutive box-bulleted paragraphs in one table cell, one text
  box or the body; any other paragraph ends it) shows a checked box (a
  checklist) and otherwise as the unread mark `[?]` (a box-shaped bullet on its
  own may be a bullet), counted in a note, and a legacy FORMCHECKBOX, written in
  place of the field from `w:checked`, else `w:default`. A list never runs
  across a table cell's boundary, entering or leaving the cell, nor across a
  text box's: a text box's paragraphs are lists of their own and the anchoring
  paragraph's list resumes after them, so a ☑ checklist in the next cell, or in
  a text box anchored in or after an ordinary ❑ list, leaves that list's items
  `[?]`. A paragraph whose mark is hidden (`w:vanish` on the mark, else through
  its character, paragraph or table style or the document defaults, as for a
  run) or is a tracked deletion or move (read as accepted) belongs to no list:
  it ends the list it interrupts and never makes one a checklist; with no text
  shown nothing is written for it, and where its text shows its box bullet is
  written `[?]` (round 6 extraction:1). A filled square ■ is kept as written (it is a bullet as often as
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
  nesting), so a mark that is not a check reads them where they land.
Every printed box is then placed where it is drawn (`_I2_Places`) and widgets
  and marks are read against those places, holding only (a box the readings
  above held stays held; nothing but `[?]` is written). A box that starts a
  piece an operator placed lies at that piece's first glyph that draws, past the
  whitespace its string opens with and the TJ numbers and strings of spaces
  before it, across its width (its characters' widths where its font gives each,
  as for a typed `[ ]`; else one em for a box glyph and 0.6 em per character of
  a typed box), give or take `BOX_SLACK`; a box inside a piece, one whose glyph
  is not found where its piece starts, and one starting a piece no operator
  placed (after a font change with no move, which pypdf reports where earlier
  text of its text object began) lie somewhere right of where each of the
  piece's operators draws, on that operator's baseline; a box no piece places
  keeps the readings above. A mark that is not a check over a box so placed, and
  a check box or a mark that checks over one whose printed state it denies or
  whose place is not read exactly, leave it unread, and a widget or mark that
  decided a box loses it when such a box lies under it too:
  `[  ] Cold snare polypectomy` with an X field between the brackets, or
  `[-2400 ([ ] Cold snare polypectomy)] TJ` under a tick over its brackets, is
  `[?]`; one that agrees keeps the box as printed (an unchecked check box inset
  in an empty `[  ]`). Each piece is indexed once per baseline it draws on; past
  32 baselines or 64 candidate boxes under one widget or mark (`_ING_MAX_ROWS`,
  `_ING_MAX_SCAN`) every printed box on the page is unread (round 6
  extraction:2, extraction:3; round 4d verification).
  The page note names a form check box over a printed box whose position
  could not be read (`OVERLAP`) only where a check box or radio button may lie
  over a printed box whose position was not read exactly (inside a piece of
  text, in a form XObject, or placed only as somewhere right of its piece's
  operators) or has too much under it to read; two check boxes over one printed
  box at a known place, one over several boxes at known places, and any other
  mark get the unread-box note (round 6 extraction:4). Otherwise a
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
  label's).  An unchecked widget before a line that runs on into text it does not
  govern, before the next widget of its row, also writes `[?]`
  (`_ING_Ink.runs_on`): past a gap wider than 0.6 font sizes between the glyphs
  drawn (padding spaces draw nothing, at a string's ends or inside it, the tied
  string's own included; a TJ number moves the glyphs after it; one whitespace
  glyph closing a string, opening the next or between two words of one is a word
  space at its own width, so word spacing wider than 0.6 font sizes is itself a
  gap: "MAC" and the next column 25 spaces apart in one string, or
  `(MAC) Tj [-3000 (Cold snare polypectomy ...)] TJ`); with text pypdf joined
  into its line after the tied piece (each later operator of that piece, and
  each later piece before the next piece a box is written before or that a
  printed box starts) that is drawn more than `BOX_SLACK` off the piece's
  baseline or left of it, cannot be placed or is not upright, or, for a later
  piece, starts where no measured text starts or is set in a font the page does
  not measure (no widths, a Type3 font, or no font the page holds)
  (`_I2_joins`); and past 64 strings or operators to read. A tied piece alone on
  its text line and drawn by one operator that shows one string (`Tj`, `'` or
  `"`) is one string of ink: only padding inside it is a gap, so an item whose
  detail pypdf puts on a line of its own keeps ☐ (round 6 extraction:0,
  extraction:5; round 4d verification). Text in a font that gives no widths is never
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
documented values → `conflict` (never pick one silently). A member-supplied
value (service date, setting, billing context) is encounter metadata, never a
clinical fact: it supplies a fact the document does not give, or gives only as
a conflict, and it may agree with the documented value (`origin=user`). **A
member value that differs from a single documented value is a conflict**
(`origin=conflict`, value none, the note names both): both sides are kept and
neither is used until they agree (2026-10-27: a member-entered service date 28
years before the documented one had been used for every dated check, for the
time readings and in the provider request). Dates read as ISO, US, "October 20,
2026" and day-month-year ("20 October 2026", "20 Oct 2026").

### 5.3 `studio/gi/profiles` + `studio/gi/detect` — routing

`PROFILES` (`gi-profiles@2`): versioned internal profiles. Supported:
`gi.office_em`, `gi.egd`, `gi.colonoscopy`, `gi.flex_sig`, `gi.eus`,
`gi.ercp`. Recognised without a profile (review required): `gi.sedation`,
`gi.em_other`, `gi.other`. Codes outside every GI range route to
`gi.unsupported`. Each has `version`, `label`, card `eyebrow`, numeric code
ranges used **only for routing**, `required_facts`, `procedure`, and
`supported` (bool).

`route(text, service_date) -> RoutingResult` (`gi-routing@4`) detects
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
any mention does, otherwise the usual aggregate.
An intervention stated as performed today (`_V2_stated_today`: its clause says
today within 120 characters of it, and an explicit performance cue stands within
60 characters of it with no other procedure word or service between them), in
any section, is a detected family's only when that family is named for today
(`_V2_named_for_today`: outside the history and plan sections, by a mention not
itself read planned, historical, cancelled or negated; at most 50 readings per
family, beyond which it counts as named) or, in a procedure, findings or
technique section, when its own report's procedure line names that family read
planned, cancelled or negated - booked, called off or denied, never another
encounter's (`_V2_booked_report_line`: the first sentence of the last procedure
section with a line of its own opening before it, or the last line labelled as a
procedure outside a history or plan section with a dash, "=", "|", "?:", a tab
or two spaces after the label, `_V2_LABEL_LINE`; at most 50 readings per text,
beyond which every line counts as booked) - unless the statement names a
procedure of its own (`_V2_names_another_procedure`: a name ending in "scopy",
"ectomy", "otomy", "ostomy", "plasty", "centesis", "pexy" or "rrhaphy", or
manometry, outside its interventions; never the bare word endoscopy or an act
noun such as sclerotherapy). So "Assessment: Anoscopy with rubber band ligation
of two internal hemorrhoids was performed today." beside "EGD and colonoscopy
last month were unremarkable." in the HPI, or beside "EGD 2020 normal" in the
chief complaint, is a `gi.other` procedure, while "Procedure: EGD (rescheduled
from last week)" over "Findings: Esophageal varices. Band ligation of three
columns was performed today." keeps the banding the EGD's; any other
intervention reads as before (round 4d validation:7, validation:11 and the
verifier (validation2) new problem 6).
  `gi.other` stays outside
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
  word in a remark, "Completed ☒ (pathology pending)", is none), and a passage
  opening in a status line's label, a service's or a visit statement's label
  included, is held when a hold-word option's own box is checked ("Colonoscopy:
  ☒ Incomplete ☐ Completed"; "Colonoscopy: Incomplete ☒ | Completed ☐" reads
  incomplete); a boxed value
  with no option is read as text; when the yes/no word right before the first
  box is the option's own word ("Not done ☒") that box decides, and "Not
  performed" / "Not done" is one option word. A line listed under a label that
  denies performance ("Procedures not performed:", after any list marker the
  other readers strip, with parentheses in its words, or led by one box of any
  state: "1. Procedure(s) not performed:", "☐ Procedures not performed:"), or
  under a verbless denying heading ("Cancelled procedures:"), is held whatever
  it names (an intervention line too: "Cold snare polypectomy of the 6 mm
  sigmoid polyp." under "Procedures not performed:"), never newly negated; a
  colon-less denying line is no label.
The box may also follow such a marker ("- [ ] Procedures not performed:"; round
  6 declared:6), and the label may carry any number of words before and after
  its denial ("The following procedures were not performed:"), bounded by its
  length alone, 80 characters, which every reader checks before matching
  (`_DENYING_LABEL`; round 6 declared:7); a label that denies one thing and
  affirms another ("Patient declined MAC and the following were performed:")
  holds what is listed under it too, an accepted over-hold.
  The lines
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
  used.") never denies the service.
  The status line's key is read in that grammar too (`_B3_STATUS_KEY`: the lead, "status" after an optional procedure,
  case, exam, examination, study, service or endoscopy, and the separator: "• Status: Cancelled - the patient had eaten
  breakfast.", "Status | Cancelled - ...", a tab, a Word cell's "Status: | Cancelled - ...", a form field's "Procedure
  status?: Cancelled"; round 6 declared:4), only ever to hold: a line round 5's key (`_STATUS_KEY`) reads is read on
  that key's value as round 5 read it (`_B3_status_value_denies`), and the grammar's value, where it starts later (after
  a second separator), only adds a hold ("Status: | Completed? No" holds; round 4d verifier, boxes3 new problem 1); a
  line only the grammar reads holds when its value denies and otherwise falls through to the tests it had before ("•
  Status | Completed, then cancelled." holds); the form-field block reads each key on its own value, and either holds
  the page. In the word bounds of a short denying or cancelling line a box of any spelling, with what is written
  straight after it, is one word (`_B3_words`: "[ x ] Cancelled - patient ate breakfast." holds; round 6 declared:5). A
  typed done-question whose noun names a service holds that service (`_B3_SERVICE_ANSWERED_NO`, round 6 declared:9: "Was
  the EUS performed today? No", "EUS performed? No (patient declined)"): the grammar's lead, a noun of at most 60
  characters that names a service, with no ':', '?', '=', '|', tab or ';' and no period before a space (round 4d
  verifier, boxes3 new problem 4), the participle, "today", the separator, and a denial that is the whole answer (the
  line ends, or punctuation, a dash or a parenthesis follows it); read once per line from its start, it holds the
  mention inside the noun with doubt wherever the boxes say nothing, so the family it names is held and no other. A noun
  opened by an earlier-time word (`_B3_EARLIER_NOUN`: prior, previous, last, earlier, past, preceding, former or old,
  also after any, the, a or a possessive) asks about another time and holds nothing ("Prior colonoscopy performed? No";
  round 4d verifier, boxes3 new problem 3), nor do a word after the denial ("EUS performed - no complications.") and an
  item's question ("Was the biopsy performed? No"). The label of a hold-word status row (box2:L) ends at any of the
  shared separators (`_B3_label_end`), and on a line of one box the hold word beside it reads that box ("Colonoscopy - ☒
  Incomplete" holds; a row of two or more marks after such a label is held by the strict rows, "Colonoscopy - ☒
  Completed ☐ Incomplete" too, an accepted over-hold; round 6 declared:2); its hold also takes a passage its own words
  and section leave uncertain with no doubt, a status row outside a positive section ("Colonoscopy: ☒ Pending ☐
  Completed" under "Indication:"; `_B3_label_hold_unread`, round 6 declared:9), and a row its section reads as history
  or plan keeps that reading.
  An option every denying option of which
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
  incomplete and keeps that reading. An extent label whose own sentence denies
  or doubts its landmark (read past ";" and ",", up to a full stop, the next
  field, a deeper landmark or a retroflexion, each of which owns its segment) is
  never read as reached ("Extent: cecum; not reached").  A shallower prose landmark then reads the procedure incomplete only
  when that sentence denies reaching the landmark itself (a closed list: not
  reached, visualized, intubated, achieved or advanced; could or did not reach;
  unable or failed to reach, advance, intubate or visualize; short of; "reached:
  no"; also after a reason, "due to poor prep not reached"), never through an
  onward word, which denies going past the landmark and not reaching it
  ("Extent: cecum; not advanced further due to looping"), and through "beyond"
  or "past" only before a landmark shallower than both the label's and the depth
  the procedure calls for ("further" or "farther than" reads as "beyond";
  "Extent: terminal ileum; not advanced beyond the cecum" is no reach denial)
  (round 6 sections:1, and its verifier's new problem 5). Any other denial,
  doubt or aim word ("Extent: cecum; no biopsies taken") refuses the label
  without denying the reach (`_S2_doubted_short`): a label at or beyond the
  depth the procedure calls for (the cecum; the duodenal bulb for an EGD, the
  third part of the duodenum for an enteroscopy; a flexible sigmoidoscopy calls
  for none) withholds the extent, which is asked, never read incomplete at a
  shallower landmark, and otherwise the deepest such label reads the procedure
  incomplete at its own landmark, reached and no further or not reached at all
  ("Extent: transverse colon; not advanced further due to looping" beside
  "inserted into the rectum": 'incomplete: transverse colon'; its verifier's new
  problem 2). A denial elsewhere in the family's text decides only
  for a landmark between the deepest one reached and the label's own, and no
  other value decides beside a refused depth label.
A label read only because a next report-field cell ends its value ("Extent:
  cecum | Prep quality: Good"; `_S2_read_by_the_cut`: its uncut value holds a
  word outside `cues.EXTENT_TAIL` and no other reach cue reads it) is judged
  against the family's own text (`_S2_cut_denied`, round 6 regression:3): a
  blocked or denied mention of a landmark deeper than the deepest one reached
  otherwise and no deeper than the label's is read in its own segment
  (`_S2_contradiction`; the separator after a landmark written as a field's
  label, "Cecum - not reached", is no break). A reach denial of the closed list
  above naming it ("Cecum not reached."), or its own negated, cancelled or
  incomplete reading with no act or lesion of the closed list `_S2_ACT_AT` in
  the segment ("No cecal intubation.", "Cecum: no."), drops the label and the
  prose decides; a bare "none" or "N/A" ("Cecum: none.") only doubts, unless the
  landmark's own name is the reach ("Cecal intubation: none."). A reach word
  beside an act ("The cecum was not reached or biopsied."), a reading that only
  doubts ("The cecum may not have been reached.") and, with no act, a view word,
  a hedge or a bare answer ("Cecum: not seen.") doubt it; an act or finding
  denied there ("The cecum was not biopsied.", "The cecum was not inflamed.")
  says nothing of the reach (its verifier's new problems 1 and 7). A doubt of
  the label's own landmark withholds the extent, which is asked, only for a
  label at or beyond the depth the procedure calls for (always for a flexible
  sigmoidoscopy); a shorter label keeps 'incomplete: <label>' ("Extent:
  transverse colon | Prep quality: Poor" beside "The transverse colon was not
  well seen due to stool."; its verifier's new problem 3). For a colonoscopy a
  denial of the terminal ileum, a sub-act, only doubts. A doubt of a shallower
  landmark ("The sigmoid colon could not be examined.": the scope passed it), a
  denial beyond the label's landmark ("TI not intubated." beside a cecum label)
  and a label read whole change nothing; each denial is judged at most once, and
  only when such a label exists.
  A label in an unrecognised section counts only in the
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
   With an answer of their own ("Referral: Dr. B. Synthetic", "Orders:
  CBC, INR") they plan only their own line and the lines its sentence runs on
  into; up to the next heading, a one-line field reads in the section in force
  before the label only when it names no service or intervention, and no
  procedure by its form (`_S2_PROCEDURE_WORD`, the endings and words of the
  `gi.other` reader), and is either one of the report's own fields of a closed
  list (`_S2_REPORT_FIELD`: an extent or depth label, withdrawal, insertion or
  cecal intubation time, preparation or its quality, BBPS or the Boston scale,
  sedation, complications, EBL, findings, retroflexion: "Extent: cecum") or a
  landmark named as its label whose value opens by stating it reached or seen
  (`_S2_landmark_field`: words of `cues.EXTENT_TAIL` or normal, unremarkable,
  examined, inspected, up to a statement such as reached, intubated, visualized,
  seen or normal: "Cecum: reached without difficulty") (round 6 sections:0, and
  its verifier's new problems 4 and 6); every other field ("Right hemicolectomy:
  Dr. B. Synthetic", "Cecum: 4 cm mass", "Extent: cecum, right hemicolectomy
  with Dr. B. Synthetic") and every other run of lines is held
  (`_SEC_AFTER_A_PLAN_LABEL`, never planned and never performed), and inside a
  plan or history section that section reads every line; a cited passage that
  starts in a procedure, findings or technique section and reaches into such a
  held line is held too.
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
  like a phrase line ("Procedure completed as planned").  Inside a procedure, findings or technique section a colon-less line
  that reads as a phrase ("Changes of prior radiation therapy", "Surgical
  opinion for further management") or that names history or prior therapy,
  numbered, bulleted or with no marker at all ("2. Prior radiation therapy", and
  the same item as extraction writes a Word "List Number" or "List Bullet"
  paragraph, bare: round 6 sections:5; an unknown history label such as "Earlier
  endoscopic work-up" is held there too, an accepted over-hold) opens an `other`
  section whose lines are held, a line with its own performance cue included (it
  may tell another time or a plan), never a history or plan one, and a second
  such line inside it is read as inside the section it stands in for. Outside
  those sections a numbered or bulleted such item is held too (an impression, an
  indication, the text before the first heading), a phrase line or a bare
  history line opens the plan or history section it always opened, and inside a
  plan or history section every such line reads as before. A service line or a service field after a line cut on a plan,
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
  it is cannot be read.
The service's own line keeps its own reading only when a negation word on it
  negates there by itself (`_S2_own_line_denies`): an anchored negation of a
  service or intervention named beside it ("Biopsy not done.") or a denial that
  names no service of the act its words describe ("No tissue was obtained."); a
  word a complication, qualifier or finding explains, a word that only doubts,
  or a clause cue leaves the hold ("Biopsies were taken from the gastric antrum
  without difficulty." under "Has the patient had a prior adverse reaction to
  sedation or anesthesia? No" is held) (round 6 sections:3). Each negation word is
  read in a clause window of its own, so a line with more than eight of them
  (`_S2_OWN_LINE_TOKENS`) is not read for them: the line above decides, and it can
  only hold (round 7 bounded:5).
  The line above is read whole, from its own start, and by
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
  The line above it (one blank line may stand between) is read too when it is about the attestation, only ever to refuse
  (`_B3_attestation_above_refuses`, round 6 declared:10): a line with a mark and one of the attestation's words
  (`_B3_ATTEST_ABOVE`: attest, agree, confirm or acknowledge, negated or not, separate, modifier) refuses it unless its
  marks affirm and box2:F does not refuse it ("☐ Attested", "Attested | [ ]", "☒ Not attested"); a line with no mark is
  asked only when it names the attestation itself (`_B3_ATTEST_NAME`: an attestation word, modifier 25, or separate(ly)
  with E/M, E&M, evaluation, identifiable, service, visit or encounter within its next four words; never a bare agree,
  confirm or acknowledge: "Allergies confirmed: none." and "Notes: Agree" leave it attesting; round 4d verifier, boxes3
  new problem 2), and then refuses it when it denies the attestation itself at any length (`_B3_ATTEST_DENIED`:
  "Attestation: I do not attest to a separate service today, see note."), when it is a field whose value of at most
  `B3_ABOVE_ANSWER_WORDS` (4) words box2:F refuses ("Separate E/M attested: No"; a longer value is prose), when it is a
  line of at most four words with a contrary word ("Not attested", "Modifier 25 not appended"), or when a form field
  tied to it is not checked.
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
  be read as leading or trailing (the items the readings disagree on; also an
  item that, with every word run between the boxes read as an entry, takes the
  other state: "Photos ☐ | Biopsy ☒ | Cold snare polypectomy ☐", where a first
  word that is no item must not turn the row) hold too,
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
  before, and visit-type option rows are read option by option.
  A row opened by an item's own name and its colon, with items after its boxes, is read both ways ("Biopsy: ☐ Cold snare
  polypectomy": the box trails the biopsy or leads the snare; a service's name still leads: "Colonoscopy: [ ] biopsy [x]
  cold snare"), and an item the two readings read differently is held; a checked box one reading gives the item and the
  other reading none still reads checked ("Biopsy: ☒ Cold snare polypectomy" reads both items done, and a two-column
  form's "Biopsy: ☒ <the next column's sentence>" stays ready), but it never lifts a hold that only the item's own box
  lifts: under "Procedures performed today:" both items are held (`_box_checked_in_every_reading`; round 6
  declared:8, round 4d verifier, boxes3 new problem 6). Among an item's own options (option boxes written one after another, with only
  spaces, '|', ',', ';' or '/' between an option's yes/no word and the next box, or a label of at most 40 characters
  with no colon in place of the word), a later denial option checked while the first denial is not makes its boxes
  disagree ("Cold snare polypectomy: ☐ Not done ☒ Not performed"), unless an unchecked Yes already denies the item ("☐
  Yes ☐ Not done ☒ Not performed" stays denied; `_B3_later_denial_checked`, round 6 declared:11). Strict rows
  (`_B3_row`, `_B3_hold`; round 6 regression:0, 1, 2, 4, 5, declared:0, 1, 3): one predicate decides, once per row,
  whether a row's marks can be read, and every box reader consults it first (the box, option, status-line,
  status-reference, called-off, label and visit-statement readers). The row is the passage's box segment on its line; a
  row of one mark that is not the unread mark is left to the readings above. Any other row is read only when its marks
  and its entries (the word runs between them, after the row's label: the text before the first mark up to its last ':',
  '|', '=', tab, spaced dash, "with", "w/", "including", or a comma right before the mark) alternate one to one, all
  leading or all trailing their entries (after a trailing row's last mark a run naming no option is a remark), and every
  reader of the row pairs them so wherever its reading could release or exclude. A label right before the first mark
  that may also be the row's first entry is an entry when every mark stands alone in its cell, else the row's label when
  it names a service or no item, and an item's name pairs both ways (held); with no separator, a row of yes/no answers
  answers the text before it ("Biopsy taken ☐ Yes ☒ No"). On any other row every passage that starts in the row within
  `BOX_REACH` of its marks, a status reference included, is held with doubt (`_B3_ROW_HOLD`: "uncertain: the check boxes
  on the line '<row>' cannot be paired with its entries in exactly one way, so what they say of it is held"), never
  ready and never newly negated or excluded ("Consent signed ☒ | Completed ☐ | Procedure cancelled ☒" holds the EUS;
  "Colonoscopy: ☐ None ☒ Cold snare polypectomy ☐ Biopsy" holds both items; "☒ ☒ Biopsy"). On a row that pairs, an
  unread mark also holds the label of a row of options and a passage across entries one of whose marks is unread
  ("Colonoscopy: ☒ Completed [?] Pending"); a label that names a service and no intervention, ended by its separator
  with the row's first entry after it, on a row with no option word, is no entry ("Colonoscopy: Biopsy ☐ Cold snare
  polypectomy ☒ clip placed" leaves the colonoscopy to its own reading). A row longer than `B3_ROW_CHARS` (1,000
  characters) is never paired and is held, unless its only mark is one plain box, which keeps its reading at any length
  (round 4d verifier, boxes3 new problem 7); so is a row of two or more marks, or of an unread mark, on a line carrying
  more than `B3_LINE_MARKS` (64) marks (round 6 bounded:0, bounded:2); their cue says the row was never paired
  (`_B3_ROW_UNPAIRED`, the same prefix). So is a row with a mark past the document's first `B3_DOCUMENT_MARKS` (1,000)
  marks, held with `_B3_DOCUMENT_UNPAIRED` (the same prefix; its cue names the document's count): where that mark is
  depends on the text alone, never on which rows were read first, and a row of one plain box keeps its reading there
  too (round 7 bounded:0, regression:0: 64-mark rows one per line overran the analyze stage's memory).
  The `[PDF form fields on page N]` and `[PDF annotation text
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
  So are the strict rows' holds (`_B3_ROW_HOLD`, and `_B3_ROW_UNPAIRED` and `_B3_DOCUMENT_UNPAIRED` for a row never
  paired, which share the prefix "uncertain: the check boxes on the line") and the service-named done-question's hold (`_B3_ASKED_NO`), each a doubt.
- Cost: each mention stores a bounded window of its sentence, not the whole
  sentence, and a member's pre-triggers are read once from its own bounded
  start, so a long coordinated list stays linear. Clause lookups take only the
  first or last few clauses they need (by bisection), and a line's done-question
  answer is read once per line.
  A box row is paired at most once (memoised per row) and a line's marks are counted once, up to `B3_LINE_MARKS`; a
  status line's boxes and option words are indexed once per line window (`_B3_line_index`), so the option readers find
  an option's text, and whether it holds a remark (`_B3_line_remark`, asked once per window), by bisection; and a hold's
  quoted line is read once per line, its bounds by bisection over the text's line breaks (`_B3_shown_line`; round 6
  bounded:0, bounded:2). Pairing reads each option in its own line window, so the rows paired are bounded per document
  as well as per line (`B3_DOCUMENT_MARKS`); the status-line label hold answers a line window with no mark without
  reading or memoising its items (round 7 bounded:3); and the EGD location reader reads each clause's locations once,
  however many of its interventions the clause lists (round 7 bounded:4).
  A span's family is found positionally — the
  services are sorted and never overlap, so only those starting within the
  longest service name before the span are tested — so a provider citing a long
  report span by span stays linear (round 6 bounded:1).
The extent readers make one span of a clause and share it among its landmark
  hits, so memory stays linear in a one-line note (round 6 bounded:3); plan:D
  reads an extent label's rest, its verdict and its reach denial once per label
  (memoised by the label's end, depth and table; round 6 bounded:6); and
  plan:D2's guard over the doubted labels is one sorted sweep, linear in the
  labels and the denials, never their product (with round 6 sections:1).
  A list member followed, after nothing but spaces and commas, by the next service name inside the window reads its
  tail as `LIST_TAIL` instead of masking it to the window's end once per member and mention (`_masked_post`): every
  reader of a member's tail - `NEGATED_POST`, `INCOMPLETE_POST`, `UNCERTAIN_POST`, `NEGATION_HEAD_AFTER` - is anchored
  at its start and fails on a tail that opens with spaces or commas and a service token, whatever follows, so the
  readings are exactly those of the whole tail (round 4d integration; a long comma list of service names costs about
  half what it did; a document naming procedures more than `MAX_SERVICE_MENTIONS` times is not read, below).
  Every stage reads the
  document in ONE forked child under the stage's own wall clock
  (`JOB_DEADLINE_SECONDS`) and a memory allowance (`BOUNDED_MEMORY_BYTES`,
  `studio/bounded.py`): analyze extracts the context and routes in one child,
  and assess routes and runs the whole validation assessment (whose span
  readings reuse that routing's analysis) in one child, with the reference rows
  of the selected codes fetched in the worker first (`prefetched_lookup`; a code
  it was not given is an error, never an empty answer). An overrun fails the
  stage with a plain message instead of holding the worker; nothing a stage
  read stays cached in the worker (`jobs.release_routing_caches` after every
  stage is the backstop). The assess stage routes the document again (its span
  readings read that routing's analysis) and then validates, so it has twice the
  analyze stage's deadline and the analyze stage's memory allowance plus 256 MiB
  (`ASSESS_MEMORY_BYTES`): a document the analyze stage read within its limits is
  never sent and then left unassessed for repeating that work (round 7
  bounded:1), and `from_jsonable` resolves each dataclass's field types once. A
  document naming procedures more than `MAX_SERVICE_MENTIONS` (1,000) times is not
  read: the analyze child counts the service mentions first, and the stage fails
  with a plain message naming the count; nothing is recorded or sent. Each mention
  is read in its list window, and a list of one service's name overran the stage
  from about 40,000 characters (round 7 declared:8, bounded:1, bounded:3). A child
  that runs out of memory answers with a reply built before its limit was set, so
  the stage names the memory limit rather than an unexpected failure (round 7
  bounded:6). A member's context change re-reads the document's
  facts in a child under `CONTEXT_REQUEST_SECONDS`, and is refused for a
  revision whose analysis overran or failed, so nothing is ever sent for a
  document the service could not read; a stopped, swept or expired analysis is
  resumable and is not refused (round 6 pipeline:1). Nothing is sent for a date
  the revision was never routed for: when it has no `RoutingRun` for the
  context's date, the predict stage routes that date first in one child under
  the analyze deadline, and an overrun fails the stage before any request is
  built, reused or sent (round 6 pipeline:0).

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
response ≤ 4 MiB. A response listing more than 64 selected codes
(`MAX_SELECTED`) or more than 256 candidate and alternative codes
(`MAX_INFORMATIONAL`, alternatives nested under candidates included), or
citing more than 1,024 evidence passages over all its codes, candidates and
alternatives (`MAX_EVIDENCE`; every passage is read in the assess stage, round 7
bounded:2), is not used, and says so by count; an assessment's proposals are
written in one INSERT (round 6 bounded:5). A response refused whole is never reported as one
that proposed nothing: the provider check fails ("The response from
<provider> was not used, so there are no CPT proposals"), the problems check
gives the reason, the readiness blocker reads "The provider response was not
used" instead of "No CPT code was proposed", and the code panel shows the
failed check's wording (round 7 bypass:1). Usage = `usageInfo.creditsConsumed`, basis
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
A selected, non-excluded `gi.other` code also speaks for the routed procedure
line its passage opens with (`_Evaluation.speaks_for`: a passage's own sentence
leads are read once (`_VAL_owned_leads`) and each lead is compared with the
routed openers once per code (`_VAL_lead_matches`, what `_VAL_opens_with`
asks), never the passage rescanned per opener (round 7 validation:1,
validation:2): 46600 citing "Anoscopy revealed grade 2 internal
hemorrhoids." covers the report's "Procedure: Anoscopy"), and so for that
procedure named again, whether the code is ready or held because the document
doubts the procedure; another procedure line it does not open with is still
named (round 4d validation:10). 46221's one-procedure class takes a name only
with a band word (band, bands, banded, banding, RBL), with no other ligation's
name (suture, artery or arterial, dearterialization, Doppler, HAL, THD,
varices or variceal, esophageal) and with every word one of a hemorrhoid
banding's own description (`_V2_CLASS_WORDS`: the band and its act, the
hemorrhoid, its column, bundle and position, counts and grades), so "Suture
ligation of the left lateral column", "Ligation of the left lateral column" or
"Band ligation of a rectal varix" beside a selected 46221 is named
(fail-closed: an unlisted word names it, "Banding of the prolapsing tissue" too;
round 4d validation:5).

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
A detected family not read as done is read mention by mention too: outside
plan, history and indication / chief-complaint sections an uncertain mention
that hedges or doubts is a possible same-day procedure whatever the family's
aggregate ranks first ("History of present illness: EGD and colonoscopy last
month were unremarkable." beside "Assessment: EGD was performed today and
showed esophagitis versus reflux." holds the E/M for the EGD); inside those
sections nothing new counts ("Assessment and plan: Possible EGD if symptoms
persist." keeps the visit approvable; round 4d validation:6).
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
  after an introductory phrase, with the act's object after it: "After
  informed consent, we banded the right posterior column today."), not in a
  relative clause (a relative pronoun up to three auxiliaries or adverbs before
  the act: "that had been banded"), and only when the act's clause tells no
  other time (routing's other-encounter time reader, or a date that is not the
  date of service: "Two columns were banded at her last visit and look healed
  today." holds). An introductory phrase (`_VAL_introduced`: "we" within 100
  characters of its clause's start) introduces the act only when it opens with
  a listed introductory word (after, under, using, with, following, during,
  upon, through, via, this, then, subsequently) or, ending in a comma, with
  "in"; is no clause of its own (no time or condition word anywhere: when,
  whenever, while, whilst, once, until, till, if, unless, since, as soon as, as
  long as; no subject pronoun or auxiliary); names no other occasion by its
  time or by its event (consultation, referral, presentation, hospitalization,
  stay); and holds only words of today's procedure's own conduct
  (`_V2_LEAD_WORDS`: its position, consent, instrument, guidance, anesthesia,
  technique, or today), so an unlisted word holds. Today must then be said in
  the phrase or in the act's own statement up to its first clause break
  (`_V2_today_of_the_act`); an act that says it only of another predicate is
  told of, never stated, and its routed mention corroborates nothing either
  (`_VAL_told_act`): "When she presented with bleeding, we banded two columns,
  and today they look healed.", "In the hospital, we banded two columns
  today." and "In the left lateral position, we banded two columns, and today
  they look healed." hold (round 4d validation:3);
- or routing corroborates it: a routed `gi.other` mention of that procedure read
  as done lies in it, it lies in the first sentence of a procedure section whose
  routed mention is done, or, read by its section alone, it opens with that
  procedure as the report's done procedure line names it ("Anoscopy revealed
  grade 2 internal hemorrhoids."); a routed stated-act mention whose clause
  tells another time never counts; and none of the three counts when the
  document denies, cancels, cuts short or doubts that procedure as the doubt
  guard below reads it (a plan or history line only by its own words: "Plan:
  Anoscopy was not performed due to pain; will reschedule." doubts it), because
  routing's `gi.other` finding never reads such a denial ("Anoscopy was not
  performed; the patient declined." names no mention). A sentence's
  own-procedure words are read on their own for this too, since routing reads
  the clause after a `gi.other` name only for the name ("Anoscopy was
  incomplete because of pain." reads performed as a sentence and incomplete at
  "Anoscopy").
The doubt guard (`_VAL_doubted`; round 4d validation:0, 1, 2, 8, 9, bounded:4
and the verifier (validation2) new problems 1, 2, 3 and 5) reads the document
once (`_V2_doubt_index`), then code by code. It reads a sentence only when it
holds something it could be about (a `gi.other` procedure word, "procedure",
"exam", "study" or "it", a status line, an act verb, a cut, an attempt or
failure, a step or instrument of the procedure) and wording that can doubt (a
negation, status, hedge, plan, history or time word, a digit, "?", a clause cue
that is no performance statement, a date, routing's own times, a box mark on its
line or a denying label above it; a status line needs none). It reads such a
sentence by the passage's own reading (`detect.own_status_for_span`): whole and,
when that is no doubt, at up to four own-procedure words and two subject
references; in a sentence of several clauses, each of its first three that holds
a cut; and by routing's next-line denial grammar (`detect._denies`) when it is a
status line, or holds a denial word and is at most six words long or opens with
a referring subject. Where a detected family carries a document-level judgement
it reads every such sentence whatever its wording, and a performed reading again
as routing reads the span (`status_for_span`: "During her stay, we banded two
columns." and an own banding sentence in an incomplete colonoscopy's findings
hold). The code's procedure is doubted by a line answering the done question no
outside plan and history sections ("Procedure performed: No", "Anoscopy
performed: No"); by routing's reference denial of "the procedure", "the exam" or
"the study" (`cues.PROCEDURE_CANCELLED`, `PROCEDURE_NOT_PERFORMED`,
`PROCEDURE_INCOMPLETE`; never the digital rectal or physical exam, never where
it reads planned or historical: "The exam was stopped early because of pain.");
by a sentence naming the code's own procedure that reads as a doubt (whole or at
an own word) or a denial ("Anoscopy was not performed; the patient declined.");
by a sentence with a reference, an act verb, a cut or a status line that reads
as a doubt or a denial, or holds a clause that does ("Status: Pending", "Not
performed.", "Complications: Aborted due to inadequate sedation."), unless every
doubting word of its clauses about a procedure is accounted for (a doubt no
doubting word explains - a box, a field, an extent, a date, a label, a hedge -
only when every such clause names another act or procedure and nothing that is
this one); in a procedure, findings, technique, impression or `other` section,
unless the sentence reads planned or historical, by a cut, or a negation,
attempt or failure written of the procedure itself (no phrase, a reference, a
pronoun or a person, its step or instrument, or its own word), not accounted for
("Stopped early because of pain.", "Insertion of the anoscope failed because of
a stricture."); and in a plan line, by a cut stated as done in a clause with no
modal, condition or plan word (`_V2_MODAL`), not accounted for ("Plan: The exam
was stopped early; repeat in two weeks.", never "Plan: Banding will be deferred
if the INR is high."). A plan or history section is asked no done-question
answer, and a plan or history line that does not say today no other structural
denial (a status line, a short-line or reference denial, a clause read on its
own), so only its own words doubt the procedure (a rescheduling of it counts). A
doubting word is accounted for by routing's declared exceptions
(`cues.COMPLICATION_NEGATION`, `QUALIFIER_NEGATION`, `OTHER_ACT_NEGATION`, and a
`FINDING_NEGATION` naming no procedure, reference or person), a no-repeat
statement, the exact form "No other procedure was done.", or the phrase it is
written about - its subject or what it governs, of at most eight words and no
auxiliary - when that names another act, a medication, bleeding, another
family's scope, a routed service or a procedure word, and holds no reference,
pronoun, person or session and no word of the code's own procedure ("No biopsies
were performed."; "Banding was deferred because she takes apixaban." for 46600,
never for 46221); a hedge or another time only by a clause wholly about another
act or procedure. So a mention elsewhere in the sentence accounts for nothing, a
qualifier never makes the exam another ("Today's follow-up exam was aborted
because of pain." holds), a pronoun's antecedent is never guessed ("After
biopsies were discussed, it was aborted because of pain." holds), and a
no-repeat statement clears only its own negation ("Plan: No further banding is
needed." is no doubt; "Banding was cancelled today because the hemorrhoids had
resolved, and no repeat banding is needed." holds 46221). Bounded: at most 2,000
reads, 4,000,000 units of work (reads x (1 + references + E/M mentions, + routed
services where a family is judged)) and 6,000 doubting words per text, beyond
which every code's procedure counts as doubted (held, never excluded); a clause
about a procedure with more than 12 doubting words doubts it; a phrase is read
within 160 characters before its word or 80 after it, and routing's exceptions
within 60 before it and 300 after. Whether a word lies inside another exam's
phrase, a no-other-procedure denial or a cut is a bisection over those spans
(`_V2_inside`), never a scan of them per word: one long sentence of "physical
exam" phrases ran outside every budget (round 7 validation:0).
A passage that reads incomplete only through its detected family's
document-level judgement ("Procedure: Colonoscopy" when the colonoscopy stopped
at the splenic flexure) is judged by its own reading before that judgement
(`detect.own_status_for_span`): it states no procedure of a `gi.other` code.
Otherwise (`section_only`) the code is held, never excluded, with the reason
that the passage is not read as documenting that service as done on that date
(worded from what decided it: "reads as performed only by its section, and as
incomplete only through what the document says of the procedure it names").
A passage that names no routed service is worded by the family routing
attributes it to instead (`Reading.judged_by`: the sentence's attributed
family, read positionally by two bisections): "... and as incomplete only
through what the document says of Colonoscopy, the procedure routing attributes
it to" for "Grade 2 internal hemorrhoids were seen on retroflexion." (round 4d
validation:4). Likewise a `gi.other` code's passage that reads cancelled only
through a detected family's document-level judgement, its own reading being
performed or incomplete, is held as uncertain, never excluded
(`_V2_judged_away`): "Assessment: Anoscopy with rubber band ligation of two
internal hemorrhoids was performed today." beside "Procedure: EGD was
cancelled." holds 46221 with "The linked passage reads as performed (...), and
as cancelled only through what the document says of Upper GI endoscopy (EGD,
esophagoscopy, enteroscopy), the procedure routing attributes it to; confirm
whether ... was performed on the date of service." ("only by its section" when
its own reading is the section's; "the procedure it names" when the passage
names a routed service), and the held code still speaks for the routed mention
it cites; a passage that itself says cancelled is still excluded ("Banding was
cancelled because the patient took apixaban."; round 4d verifier (validation2)
new problem 4).
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
The doubt guard is a contract with 5.3 as well: it asks routing's own readers
(`own_status_for_span`, `status_for_span`, `_denies`, `_PERFORMED_ANSWERED_NO`,
`_PERFORMED_QUESTION`, `_performed_answer_denies`, the `_BOX_Q_*` done-question
grammar, `_status_line`, `_denying_label_above`, `_RESCHEDULED`, `_reschedules`,
`_REFERRING_SUBJECT`, `_generic_reading`, `_box_own_option_off`,
`_first_clauses_in`) and reads its word lists (`cues.DOUBT_TOKEN`,
`OTHER_TIME`, `TODAY`, `PROCEDURE_CANCELLED`, `PROCEDURE_NOT_PERFORMED`,
`PROCEDURE_INCOMPLETE`, `COMPLICATION_NEGATION`, `QUALIFIER_NEGATION`,
`OTHER_ACT_NEGATION`, `FINDING_NEGATION`, `_OTHER_ACT`), so a change to any of
them changes what doubts a `gi.other` procedure (round 4d validation:0).

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
text, or none, is refused as invalid input — `AttestationRefused`, 400), `reject` (any selected proposal), `reinstate` (a reinstatable
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
context field that changed and the part of the fingerprint that differs, read
from the persisted rows as the fingerprint reads it (family, list, status,
profile version and units by value; the evidence passages' text; each check's
id and status, never its wording), or, when none differs under the same
engine, "the decision on <code> depends on a context value that changed" (the
service date; for an E/M the setting, patient status and billing context; for
a PC/TC code the billing context) — never "the evidence or checks changed"
when neither did (round 7 bypass:0). Readiness: a reviewed report is available only
when every selected proposal has a current approve/reject decision, every
reinstatable exclusion is confirmed or reinstated and decided; anything else
is draft-only, with the blocking items listed. While a
code marked `review.same_day_em` has a current reinstate or approve decision,
an E/M marked `em.same_day_if_reinstated` cannot be approved, and while that
E/M is still on its way to an approval (selected and undecided, reinstated, or
approved first) the reviewed report is blocked ("<E/M> needs a separately
identifiable E/M: <code> was reinstated as a same-day procedure"); rejecting
the E/M, confirming its exclusion, or rejecting or revoking the reinstatement
releases it. Every proposal carries `approve_withheld_by`, the same for every
member: on a reinstated exclusion, the check that withholds approve
(`review.reinstatement` while it does not pass, `em.same_day_if_reinstated`
while the same-day hold applies), else null — so the page never reads a code's
state from one member's action list (round 6 bypass:3).

### 5.8 `studio/reports` — exports

`generate(encounter, kind, fmt, user) -> ReportArtifact` renders from a snapshot
of persisted rows, stores bytes + sha256 + snapshot sha256, and downloads
stream the stored bytes. TXT is the coding report; CSV is one row per item
(approved, rejected, undecided, excluded, alternative) with formula
neutralisation (`=`, `+`, `-`, `@`, tab, CR prefixed with `'`). In both formats
a C0 control other than tab and line breaks, DEL and a C1 control print as
`\xNN`; in the TXT a line break of any form continues the value at seven
spaces or deeper, below every structural line. Format `cpt-studio-report@4`
adds CODING COMPLETENESS (the encounter's coding state, separate from the
review status), DOCUMENTED SERVICES (status, completion, acts, the codes that
account for them, bundled acts, other providers' services), UNRESOLVED
DOCUMENTED SERVICES and CONFLICTS IN THE RECORD to the TXT, per proposal its
evidence support, the source passages CPT Studio selected and a second-review
origin; the CSV adds `evidence_support`, `source_passages`,
`documented_service` and `proposal_origin` columns and one
`coding_completeness` row, one `unresolved_service` row per unresolved item and
one `conflict` row per conflict. Draft:
"DRAFT — NOT REVIEWED", no "approved selections" section; its list of
undecided and provisionally approved codes is titled "UNDECIDED — REVIEW NOT
COMPLETE", or "UNDECIDED OR PROVISIONAL — THE REVIEWED REPORT IS AVAILABLE"
once the review is complete (round 7 bypass:4; the download verifier finds
either by its "UNDECIDED" prefix). Reviewed: approved
selections only in the approved section; rejected listed as excluded from
approved results; reviewer identity, kind and time; agent review labelled
"agent-executed synthetic review — not clinical approval". Both: source file
name + sha256, revision number + text sha256, assessment id, profile and
engine versions, provider runs and usage, reference sources with releases,
every not-verified item, open clarifications, SYNTHETIC — NOT FOR BILLING.

### 5.9 `studio/gi/services` — documented services (engine @4)

`build(text, service_date, routing, context_facts) -> ServiceInventory`
(`gi-services@1`) is a source-based inventory of what the document says was
done, read independently of any provider's codes. Per service: family and kind,
status (performed | incomplete | planned | historical | cancelled | negated |
uncertain), completion (complete | incomplete | unknown) and extent, intent,
the date, clinician and setting the context gives, its evidence, the text span
that documents it (`scope_start/end`), its lesions (noun, size, morphology,
anatomy, specimen label, disposition removed | sampled | untreated | scheduled)
and its acts (`ACT_KINDS`: biopsy, hot_biopsy, snare, emr, esd, ablation,
bleeding_control, clip, tattoo, injection, band_ligation, dilation, stent,
foreign_body, sphincterotomy, stone_extraction, lithotripsy, cholangioscopy,
cannulation, peg, tube_replacement, tube_placement, myotomy, decompression,
fundoplication, capsule_study, manometry, ph_monitoring, rectal_sensation,
moderate_sedation, fna), each with its status, the role that documented it
(physician | nursing | anesthesia | pathology | radiology | facility), anatomy,
technique, lesion and exact passages. Also: conflicts (an act stated both as
done and as not done for the same service and site, with every side kept),
attributions (anesthesia, pathology, radiology or facility services the
document gives to another provider — never coded for the performing
physician) and problems.

Reading rules, each decided within the clause and the service it belongs to:
negation has a scope (a clause opening with "No / Neither / Without" covers
every act it lists up to its predicate; "X was not <done> with A, B or C"
denies A, B and C for X; a negated negative is positive — "was complete and
was not discontinued", "not terminated early or interrupted"); "No other /
further X" denies only acts beyond the documented ones; time belongs to the
clause (a date or year in it, history and plan words, a history or plan
section outside today's report; reviewing earlier records is today's work); an
unresected lesion never makes a completed examination incomplete (completion
is read only from extent and completion statements); a duct "dilated to 11 mm"
is a finding, a dilation needs its instrument or an agent; a check-box row is
read only when exactly one option is marked. Report parts: a report title
naming one service owns its subsections to the next title; a bare service
heading ("Colonoscopy") owns the lines to the next heading; nursing,
anesthesia, pathology and radiology headings open role parts; an instrument
("the colonoscope was passed to the cecum") names its service; an act whose
anatomy its part's service cannot reach goes to the present service whose
anatomy it is. The office E/M service is routing's E/M finding, or for a note
routing reads no E/M in, the note's own evaluation wording (a sparse note still
documents a visit, with its missing setting, status and basis); routine
preprocedure work on a procedure day is not a separate E/M.

Wider reading (2026-10-27, from an independently written 43-document
synthetic corpus and fresh paraphrase tests; `gi-routing@4`, `gi-context@2`):
- Service date: a labelled date (also a table row "Date of service | …"), in
  ISO, US, "14 Oct 2026", "14-Oct-2026" or "October 14, 2026" form; only when no
  labelled date exists, the note's own dated title ("GI visit - 10/20/2026") or
  bare "Date:" field in its first 12 non-empty lines, never in a plan or
  history section or beside a qualifier (prior, last, next …). A member's value
  that differs from the document's is a conflict with both kept (5.2).
- Structure: a numbered part ("PART 2 - PROCEDURE NOTE: EGD …") is read by the
  label after its number, so it never inherits the previous part's plan
  (routing too); "SMALL BOWEL CAPSULE ENDOSCOPY: INTERPRETATION AND REPORT" and
  "PROCEDURE NOTE: <service>" are report titles; a "Study:" line is a procedure
  line; a wrapped "Label: value" line stays one sentence.
- Completion has a per-family endpoint: the cecum for a colonoscopy or a
  capsule, beyond the pylorus for an EGD (or a PEG), deep cannulation for an
  ERCP, the full examination for an EUS. It is read from routing's extent, from
  the endpoint landmark stated reached, checked ("Extent reached: [X] Cecum")
  or described as seen, or from deep cannulation; an insertion statement ("the
  colonoscope was inserted into the rectum and advanced") is no extent (routing
  too). A service without an endpoint (esophagoscopy, POEM, enteroscopy,
  flexible sigmoidoscopy, physiology studies, a tube change) is incomplete only
  when its discontinuation is documented, never from how far it went.
- Routing disagreement: a performed service becomes uncertain only through a
  contrary statement in today's report (negated or cancelled outside history,
  indication and plan; planned or historical inside procedure, findings,
  technique or impression). A planned repeat or an earlier examination named
  elsewhere is another occurrence, never a doubt about today's acts.
- Families: a PEG placed during an upper endoscopy is that EGD's act; an EGD
  performed with an EUS is `included_in` the EUS (the EUS code includes the
  examination: no code of its own is asked, its acts are still reconciled);
  manometry, pH and capsule acts go to their own family whatever part names
  them; an unnamed endoscope in upper GI anatomy is an EGD; an act that more
  than one service could take goes to the one documented as performed.
- Attributions: anesthesia given by an anesthesia professional, specimens sent
  to a pathology or cytology service, a facility's charges or technical
  component, radiology's interpretation; a sentence that denies it attributes
  nothing.
- Conflicts: a specimen recorded as collected (a nursing or specimen row)
  beside the physician's denied biopsy, with no tissue-taking act documented,
  is a biopsy conflict; a limit on further acts ("No tissue was sampled beyond
  the containers listed") and an act noun named as a place ("not passed
  through the newly deployed stent") deny nothing.

It is advisory, like routing (5.3): it reads declared wording and cannot be
complete for open prose. It is bounded (sentences, acts, lesions and services
are capped; a cap reached is a recorded problem, never a silent truncation),
runs inside the assess child, and is validated (`validate`: every passage
exact, every value in its vocabulary, every reference resolvable). An
inventory with a validation problem decides nothing (the engine falls back to
the routing-era reading for every code) and the problem is reported.

### 5.10 `studio/gi/catalogue` + `studio/validation/reconcile` — coverage and reconciliation

The coverage catalogue (`gi-catalogue@1`, rendered to `COVERAGE.md`) states per
family its support level (supported | recognised | unsupported), required
documentation, reconciled acts, acts not separately reported under an
internal profile rule (a prophylactic clip, cannulation, a biopsy of a lesion
removed at the same session, a lift injection before a resection, routine
preprocedure work), unsupported acts (ESD), clarification questions,
verification evidence and the rule checks applied. `CODES` maps a code number
to the documented act it accounts for: an internal engineering profile for
reconciliation only, never a CPT reference, never shown as a descriptor; a code
missing from it is "coverage not established", never wrong.

Per provider-selected code (`reconcile.match`): the documented service of its
family decides its status — never a fragment of a provider passage read on its
own. A service documented as planned / historical / cancelled / negated →
excluded (reinstatable, the reviewer decides); uncertain → held; performed or
incomplete → the act the code accounts for must be documented as done in that
service: done → positive; denied → excluded (reinstatable); not documented →
held with the question; in conflict → held with both sides. A base or E/M code
needs the service itself. **Second opinion:** when the code's own passage is
about the very act or service matched (it overlaps that act's or service's
evidence) and the routing-era reading of that passage hedges or denies it, the
code is held with both readings; a doubt on a passage about something else (a
fragment of a findings sentence, an earlier visit) does not decide, nor does a
doubt that is only the routing-era reader's unresolved negation in a passage
the inventory reads, clause by clause, as this service's own positive
statement ("The examination was complete and was not discontinued"); a hedge,
a denial or a cancellation always holds. **Evidence
support** (`evidence.support`): a provider passage supports the code when it
overlaps the documented act's evidence (for an office visit, when it is a
statement of this visit, not of another time); when none does, CPT Studio
selects the source passages that show the act (`Proposal.support.source`,
exact, shown and exported beside the provider's passages, which are labelled
as not showing it). Exact quotation is necessary, never sufficient.

Encounter level (`reconcile.reconcile`): every performed act the catalogue
reconciles in a supported family, documented by the physician and not
bundled, is covered by a selected, non-excluded proposal whose profile covers
it, or listed as unresolved (`services.unresolved`, one per service and act
kind; a service with no proposal at all is unresolved as a whole, except an
office visit beside a same-day procedure and a service included in another,
and its unsupported acts are still named). No code is added for an unresolved
item and no alternative is promoted. Conflicts → `services.conflicts` and a
service-scoped question with both sides; missing documentation → every
materially necessary question for that service, asked together (a sparse visit
note: setting, patient status and E/M basis), never twice for the same family
and fact. `Assessment.completeness` records the unresolved, bundled and covered
items and the reasons; `review.coding_completeness` adds the review state:
`incomplete` (unresolved services, open conflicts or open questions — the
supported proposals stay available for review), `pending_review`, `reviewed`.
It is never "verified": CPT membership and NCCI edits are not connected. A
proposal being ready for review and the encounter's coding being complete are
separate statements everywhere (UI banner, both reports, CSV row).

Rules connected: CMS PFS RVU26D (presence and status for the date, global
period → same-day E/M, endoscopic base family → multiple-endoscopy payment,
PC/TC indicator → modifier 26 consideration in a facility setting) and the
CMS practitioner MUE table (units per day). Modifier considerations (never
assigned): separate lesions within one endoscopic family (59/XS — an NCCI PTP
question, not connected), incomplete examination (52/53 — payer rule, not
connected), screening that became therapeutic (PT/33 — payer rule, not
connected), separately identifiable E/M (25). A selected anesthesia,
pathology or radiology code for a service the document attributes to another
provider is flagged (`services.attribution`). Practitioner and facility rules
stay distinct: only practitioner sources are connected.

### 5.11 The bounded second review

When an assessment leaves a documented service (or act) of a supported family
without a supported proposal, the encounter offers ONE second review, and a
workspace owner or reviewer asks for it (`POST .../second-review`,
`jobs.request_second_review`; the encounter view's `second_review` says whether
it can be asked for and why not). An assessment never queues one: owner
decision 2026-10-27 (narrow, install-first), after refutation r1 found the
reader's misreadings each turning into an automatic paid request. The request
queues ONE `review2` job (idempotency key `review2:<revision>:<assessment>`)
under the bounds the automatic one kept (`jobs._second_review_blocker`): never
while a stage is queued or running, never for a revision and date that already
had one, whatever its outcome (a reconciled unknown one releases another), only
for the current assessment of a primary request that succeeded and was not
refused whole, only with a known, agreed service date, never while an outcome
is unknown, never when its request repeats one the provider already answered;
`stage_review2` checks them again when it runs. It sends the
provider the text that documents those services (the services' report parts,
≤ 20,000 characters) with the date line, under the same send discipline as
predict (`jobs._send`: single-flight advisory lock, the run written reserved
before any I/O, Stop observed, no automatic retry, unknown outcomes recorded
and blocking every further send until reconciled; an identical retained
second review is reused, not resent). `ProviderRun.purpose = second_review`,
`ProviderRun.scope` = the excerpt offsets, the primary run and the items.
The assessment that follows reads both runs (`Assessment.second_run`): the
second review's passages are moved from the excerpt to the revision text and
re-checked exactly; only a code it SELECTED that accounts for an unresolved
item becomes a proposal (`support.origin = second_review`, labelled on the
card and in both reports); every other code it lists is an alternative. The
primary run stays the run in use for context changes and reuse.

### 5.12 Repairs after the full-suite triage of WIP 3 (2026-10-27)

The suite on WIP 3 failed 291 records in 129 tests that pass on the installed revision. Each failure was classified
as an intended change of 5.9-5.11 (the test was updated, keeping what it pins) or a regression (repaired by a general
rule, never a sentence patch). The rules this added, by module:

- Reader (`studio/gi/services.py`):
  - **Soft line wraps** (`reflow`, session interpretation 20): the reader reads a same-length view in which a line
    break inside a sentence is a space - after a long line of prose that ends no sentence, label or answer, before a
    line that continues it in lower case or after a word that cannot end a line; never around a check-box, option,
    table, list or field row, nor inside an extraction block. Every passage is re-read from the text at its offsets,
    and routing's box reader is given the text itself.
  - **Sentence ends**: after a line that answers its own field (`_answered_line`, routing's own `_answered`,
    `_OPTION_ROW` and spoken-answer readers), and at each line of an extraction block.
  - **Time parts follow routing's section layout** (`_time_parts`): a history or plan section dates what it holds from
    where the layout opens it to where the layout opens the next section; a history part ends at today's procedure
    heading when today's report goes on under it; an extraction block interrupts a history or plan part; a
    performance stated in an indication paragraph, not said to be today's, is held.
  - **Clause reading**: a history or plan section dates a mention before a hedge is read; a service named as replaced
    ("rather than EUS", "instead of") is negated, and its instrument in that clause documents nothing; "without (any)
    complication(s)" ending its clause denies no act; a "not" inside a subordinate clause, or on a second predicate
    coordinated with the act's own participle, never denies the act, and a coordinated subject with its own negated
    predicate is its own clause (every other "not" still denies); a line listed under a label that denies
    performance is held (`detect.denying_label_over`, routing's plan:C reader); a checked form-field line documents
    its act only as the strict-box rules below allow; without a known service date a dated act statement is held,
    never read as today's.
  - **Modal predicates** (routing:18): an act or a service whose own predicate is under a modal - a perfect or a
    conditional modal ("it would have been dilated", "Biopsies could have been taken but were not needed", "EGD with
    biopsy would be done if ..."), a recommendation or a possibility ("EGD should be done.", "may be done") - or
    inside a condition that opens its clause ("If colonoscopy were done today, ...") reads uncertain with a non-silent
    cue (`HYPOTHETICAL`, `_hypothetical`), and no report, procedure line or form field promotes it; an act verb the
    clause states for itself still decides ("Biopsies were taken and would be sent ..."), a plan section or plan word
    still dates first, and a hypothetical reach completes no examination. A hypothetical act is therefore no
    unresolved act (no second review is paid for it) and no act a diagnostic code leaves unreported.
  - **Intent** is read like extent: a family routing reads takes routing's intent (`detect._intent`: today's
    indication and procedure text only, never a question, a hedge, a pending confirmation, a denial, a plan or a
    history; read for a colonoscopy, so another routed family states none, as the routing-era rationale did); a family
    routing does not read takes the reader's own intent words, read with routing's intent doubts and its clause's
    reading (`_intent_word`). A doubted intent raises no screening-became-therapeutic consideration.
  - **Check boxes and form fields** (triage round 2, WIP 7-8; the owner's strict-box decision of 2026-10-25 applied to
    this reader). A row's own reading decides it: an unselected option, an unread mark, boxes that disagree or a row
    that cannot be paired hold, and the line the row is on never promotes that hold. A checked own box documents its
    act only when the run of check-box lines it belongs to lies directly under a procedure list's label
    ("Interventions:", "Procedures performed:"), or that label opens its own line, and a title, a statement or an
    instrument already documents the service (`_in_a_procedure_list`, `_checked_in_a_procedure_list`): any other label
    ("Consent obtained for:", "Equipment:", "Discussed today:"), a blank line, a line of prose or a field with its own
    answer above the run, or the document's start, leaves it held - never ready, never excluded, and never a performed
    act or service that would be sent for a paid second review. Plain item lines ("Biopsy", "1. Biopsy") and labels
    naming an item ("Biopsy:") belong to the run. A checked or "Yes" PDF form field documents its act only through the
    printed item it names on its page (routing's tie, `detect.checked_field_ties`) when that item is in such a list
    (`_checked_field_in_a_procedure_list`); a field whose label alone names the act ("Biopsy: Yes" under a printed
    "Biopsy recommended at follow-up?") is a doubt for the reviewer. A field's answer - never a participle in its
    label - states its item: an answer with a denial or a doubt among other words, or with several printed options
    ("None obtained", "zero", "Yes ___ No ___", "Yes / No (circle one)"), holds it (`ANSWER_DOUBT`); details ("3 from
    the sigmoid colon") still state the act and a negated predicate ("not placed") still denies it. With no colon on
    its line, a spaced dash after the item separates a typed field's label from its answer ("Biopsy taken - No"), and
    the denial such a field gives only holds (`FIELD_DASH`). A bare object noun answered with nothing ("Stones: None",
    "Stent: None") reports a finding, not a denied act. A checked row that routing reads as done only by its section's
    default is held when its own label lists something else ("Risks discussed - \u2612 Biopsy", `_row_label`); a
    landmark row ("Furthest point reached: [X] Cecum") is unaffected. An extraction block's option line ("Biopsy taken: no: checked") is decided by its
    checked option.
  - **Consent** (`_consent_object`): what a consent, an authorization or an approval is for is named, never stated done
    ("Consent was obtained for biopsy and cold snare polypectomy", "Written consent for EGD with dilation was
    obtained", "Prior authorization was obtained for colonoscopy"): its predicate is the consent's, so the item reads
    uncertain - held, never excluded, never sent for a second review. So is an item after the predicate of a consent
    that is the clause's subject ("Informed consent was obtained after explaining the risks of colonoscopy with
    polypectomy"). An act with a predicate of its own in the clause ("... and biopsies were taken") is still done.
  - **Service headings**: a label line (ending in ":" or "?") that names one service opens a bare service heading only
    when it carries the service's name, its acts and heading words alone (`_bare_service_heading`): "Colonoscopy within
    10 years:", "Last colonoscopy:" and "Colonoscopy up to date:" are questions, not reports of a service done today. A
    title without a colon keeps its other words ("ERCP (UNSUCCESSFUL)").
- Routing (`studio/gi/detect.py`): an insertion statement is no extent only when no extent label speaks
  (`_insertion_only` beside the plan:B/B2/D/D2 label readings), which restores the incomplete readings it had lost.
- Engine (`studio/validation/engine.py`):
  - the routing-era reading is named, never dropped: a contrary or released passage of a ready code is named in its
    status check (warn); a hold or an agreed exclusion carries both readings;
  - a passage overlapping a routed office-visit mention is about the visit, so a hedge in the E/M's own time or
    decision-making line holds it;
  - a plan or history SECTION reading of the code's own act passage holds, never excludes;
  - the own-passage release applies only to a passage naming the code's act kind that the reader does not read;
  - a family carved out by gi-profiles@3 also counts for the family routing still reads it under, so uncovered "other
    GI" procedures beside a manometry, capsule, anorectal, pH or feeding-tube code are named again;
  - no office visit is pushed as unresolved on a procedure day the engine sees (and no second review is made for it);
  - a bare status line is the procedure's own (it holds) by a structural signal, not a word list alone: a status
    word, a hedge that is not on an observation ("were carried out?", "unclear if adequate"; never "A 5 mm lesion was
    seen?", interpretation 9), or a routing-era reading from a check-box or status-option row (`_status_signal`);
  - the routing-era reading of the code's own passage excludes the code only when that passage marks its item off
    itself - an unchecked box, a denying field answer - never by prose beside another row ("A 6 mm polyp was removed."
    beside a checked "Procedure cancelled" box is held, `_own_passage_decides`);
  - an office visit's evidence support honours the routing-era E/M time reading, and a study's own result sentence
    supports the study code;
  - a member's encounter metadata that conflicts with the document is asked once, at the encounter, when nothing else
    asks it.
- Reconciliation (`studio/validation/reconcile.py`): an act read as uncertain is quoted as in doubt, never reported as
  absent; a member conflict is worded as one in the visit's own questions.
- Context, refutation r1: a member value against a fact the document labels but this service cannot use (a labelled
  date that is no calendar date, a place-of-service code it does not recognise) is a member conflict with both sides
  kept - never a silent replacement that is sent or that makes a held visit ready.
- Context (`studio/gi/context.py`): only the first dated title line near the top can be the note's own date (a
  qualified first title gives none; another unqualified dated title with another date is a conflict); a member value
  settles a document-internal conflict only by choosing one of its values; a member conflict is described as one
  (`is_member_conflict`, one predicate for every reader).
- Second review gate (`engine._routing_agrees`, refutation r1): a second review is paid for only an unresolved item
  both readers read as done today - the routing-era reading of the item's own passage is performed (or its clause states
  it done and only routing's family summary doubts the service), or it is silent beside the strict check-box and
  form-field rule; a whole service needs routing's family reading performed. Each unresolved item records the answer
  (`second_review`), and `jobs._second_review_items` asks about marked items only. An item routing reads otherwise stays
  listed for the reviewer and is never sent. A second review whose request repeats a primary request already answered
  is never sent, and the primary reuse lookup matches a retained run of any purpose.
- Reader, refutation r1: a "can/could be" possibility governed by a time still to come ("once anticoagulation is
  held", "at a repeat colonoscopy") stays a possibility; a check-box run under a label that sits directly under an empty
  plan heading ("Plan:" / "Procedure:" / "[x] ...") lists what is planned.
- Cost, refutation r1 (cost lens): the sentence splitter reads the word before a stop from its last seven characters
  and a newline's previous line only (a numeric appendix had been quadratic and failed the assess stage); conflicts
  compare a pair of statements through a per-service index of performed acts (cubic before); the time parts look up
  sections, marks and timed sections by bisection (quadratic before); and the analyze stage's mention cap also counts
  this reader's own service and act vocabulary (`services.mention_count`), so a note naming "HRM" or "biopsy" thousands
  of times is refused before it is read. Pinned by `tests/test_services_cost_r1.py`.
- Upgrade, refutation r1 (migrate lens): a context the installed revision recorded (`gi-context@1`, which kept a
  member's value as plain metadata) is remade under the current rules - bounded, as a member's change does - before any
  stage sends or assesses with it (`jobs._remade_context`, audit `context.remade`); a second review never runs on it.
- Jobs (`studio/jobs.py`): nothing is built, reused or sent while the service date is a member-vs-document conflict
  (session interpretation 19; the not-sent run carries `scope.held`, and the encounter waits on the date question);
  no second review after a primary response refused whole, nor without a known service date.
- Reports (`cpt-studio-report@4`): UNRESOLVED and CONFLICTS print "none" only after a consistent reconciliation (the
  snapshot records `documented.reconciliation`: missing, inconsistent, partial or reconciled); every passage the new
  sections print is re-checked against the revision text; each provider run is "used by this assessment" only when
  its own provider check did not fail; `ops/verify_downloads.py` reads a wrapped source passage as one entry.

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
