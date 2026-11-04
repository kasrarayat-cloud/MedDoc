# CPT Studio core repair and customer interface — build design (session a12d8fb3, 2026-11-03)

This is the contract every builder works against. Owner directive (verbatim): `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`,
section "Owner directive, 2026-11-03 (second message)", and `/home/claude/cpt-studio-ux-20261103/directive-verbatim.md`.
Read-only maps of the code at `main` (cite them, do not redo them): `/home/claude/cpt-studio-ux-20261103/understand/R1..R9*.md`
and `critic.md` when present. Base commit for every package: **`c9f20a148a1f21aa2aaa53e477da0a26c07e268f`** (main after #1463).

## 0. Rules for every package (a breach is a failed package)

1. Work only in your own worktree and branch (given in your brief). Commit there with `git commit -F <file>` (prose is never
   a shell argument). Never push, never open a PR, never touch `/opt/meddoc-pro` (the shared tree) or another worktree.
2. Synthetic data only. Never connect to the live database (port **55451**), the live site, or any provider. Provider mode stays
   `disabled`. Python: `/home/claude/cpt-studio-gi4-20261031/venv-cpt-6212/bin/python` with `PYTHONDONTWRITEBYTECODE=1`.
3. Database-backed tests ONLY against the throwaway server `gi4-cpt-test-pg` at **127.0.0.1:55461** with CI's public values:
   `CPT_STUDIO_DB_NAME=cptstudio_ci CPT_STUDIO_DB_USER=cptstudio_ci CPT_STUDIO_DB_PASSWORD=synthetic-cpt-ci-database-only
   CPT_STUDIO_DB_HOST=127.0.0.1 CPT_STUDIO_DB_PORT=55461 CPT_STUDIO_SECRET_KEY=synthetic-cpt-ci-only-key-with-no-external-access-20261023
   CPT_STUDIO_PROVIDER_MODE=disabled`, a UNIQUE `CPT_STUDIO_TEST_DB_SUFFIX` (given in your brief) and
   `CPT_STUDIO_STATE_DIR=<your scratch dir>/state` (absolute). Never run two test runs with the same suffix. DB-free modules can
   run with `CPT_STUDIO_DB_PORT=9` (the gi4 `unit:` convention).
4. Never edit a file another package owns (section 2's table) except the shared files named for you, and then only the hunks
   your contract names. If you believe you must, stop and say so in your report instead.
5. Write every probe and scratch file under your scratch dir (given in your brief), never in the repository.
6. Customer-facing text: plain English, no provider or model names (Corti, Astra, Fable, OpenAI, Anthropic, Claude, gpt-, claude-),
   no "participant", "peer review", "provider", "vendor", "token", "credit", "sha256", "trace", "rule id", "request id". Say
   "document review", "independent checks", "coding validation", "the coding service". Never invent human reviewers or certifications.
7. Truth rules of `cpt-studio/ARCHITECTURE.md` section 2 stand: never fabricate; exact evidence or nothing; status before code;
   agreement is not verification; agent review labelled as agent review; synthetic only.
8. Your final report (your last message) lists: commits (sha + subject), files changed, tests added and their results (exact
   counts), anything you could not do, and every deviation from this design with the reason.

## 1. What is being built (directive section -> package)

| directive | package | worktree / branch (wip/cux-<k>-20261103) |
|---|---|---|
| 1 shared reading: binding, negation scope, E/M absence (Mara's four defects) | **P1 READ-BIND** | `.worktrees/cux-bind` |
| 1 previously reported false READYs D1-D13, D15 (hold-only) | **P2 READ-HOLD** | `.worktrees/cux-hold` |
| 1 recompute after selection/restoration/reload/export (D14), modifier review, approved-export truth | **P3 REVIEW** | `.worktrees/cux-review` |
| 2 customer API allowlist, operator diagnostics and grant, customer reports, error wording | **P4 CUSTOMER-API** | `.worktrees/cux-api` |
| 4 + 5 backend: details flow (answers, member context), progress fold, upload idempotency, Mara reassessment command | **P5 FLOW** | `.worktrees/cux-flow` |
| 3 + 4 + 5 frontend: codes-first list, Why this code?, details panel, progress panel, upload ack, mobile | **P6 UI** | `.worktrees/cux-ui` |
| 6 install without interruption (blue/green web, worker handover, availability record, switch-back), operator accounts phase, reassess phase | **P7 INSTALL** | `.worktrees/cux-install` |
| 6 verification tooling: walk tool for the new UI, negative scans, operator checks, download comparison | **P8 VERIFY** | `.worktrees/cux-verify` |

Integration (lead): merge order P2, P1, P3, P4, P5, P6, P7, P8 onto `feat/cpt-studio-core-ux-20261103`; migrations renumbered into
one linear chain; gi4 pins regenerated in one commit; full CI-like suite; bounded refutation; repairs; PR.

## 2. File ownership

| path | owner | others may touch |
|---|---|---|
| `studio/gi/services.py` | P1 (parts/titles/page headers/service headings/lesion labels/attributive participles/E/M denial vocabulary/`_on_procedure_line`/`Label:` parts/attached prior report titles/`_conflicts` sides) | P2: `read_clause` failure and negation vocabulary, `_time_kind`, `HISTORY_WORDS` only |
| `studio/gi/detect.py` | P1 (`_em_base_reading` and the E/M negation) | P2: C4 not-in-person fold and in-person regex (D12), upper-extent contradiction (D13) |
| `studio/gi/cues.py` | P1 (shared E/M denial pattern) | P2: new failure/negation patterns, added as NEW names only |
| `studio/gi/sections.py`, `studio/gi/context.py` | nobody (H2 request-side freeze). P5 may ADD a function to context.py that returns the pre-merge document date fact; no constant edits |
| `studio/validation/engine.py` | P2 (`_second_opinion` and its helpers, base-inclusion D15, narrow evidence hold) | P1: `_service_questions` E/M gating only; P3: `_service_considerations` (structured), extracting the base rule into a callable used by both engine and overlay |
| `studio/validation/reconcile.py` | P1 (`documentation_clarifications` gating, lesion-aware `match` conflict lookup) | — |
| `studio/validation/checks.py` | P2 | P3 (modifier consideration helpers only) |
| `studio/validation/review_view.py` (new) | P3 | — |
| `studio/review.py` | P3 | P5: member-answer effects (one clearly marked function + its call sites) |
| `studio/models.py`, `studio/migrations/` | P3 `0009_cux_review` (decision modifiers), P4 `0009_cux_operator` (grants, report audience), P5 `0009_cux_flow` (member answers, upload key, document-date field) — each depends on 0008 and is ADDITIVE ONLY (installer `migration_verdict` rules, R7 section 4); lead renumbers | — |
| `studio/customer_api.py` (new), `studio/operator.py` (new), `studio/serializers.py`, `studio/views.py`, `studio/access.py`, `studio/reports.py`, `studio/audit.py`, `cptstudio/urls.py`, `studio/templates/studio/ops.html` (new), `studio/operator/ops.js` (new: today's app.js moved), `tests/operator/` (new) | P4 | P5: `api.py`/`urls.py` hunks for its endpoints; P3: `reports.py` modifier lines in the operator report |
| `studio/api.py` | P4 | P3: decisions endpoint (modifiers field); P5: details, upload idempotency, progress |
| `studio/progress.py`, `studio/answers.py` (new), `studio/intake.py`, `studio/management/commands/reassess_retained.py` (new) | P5 | — |
| `studio/jobs.py` | P5 (read-only helpers for progress; upload key; reassess) | — |
| `studio/static/studio/app.js`, `styles.css` (APPEND only after byte 32,785), `templates/studio/index.html`, `login.html`, `tests/frontend/`, `ops/dev_preview_server.cjs`, `tests/fixtures/customer/` (new) | P6 | — |
| `ops/install.py`, `ops/INSTALL.md`, `ops/test_install*.py` | P7 | — |
| `ops/verify_browser.cjs`, `ops/verify_downloads.py`, `ops/verify_login.py`, `ops/verification/`, `ops/test_verify_*.py`, `ops/test_*verify_downloads.py`, `ops/scan_customer.py` (new) | P8 | — |
| `tests/fixtures/gi4/declarations/` | P1 `cux-bind.json`, P2 `cux-hold.json`, P3 `cux-review.json` (each written and committed BEFORE code) | — |
| `tests/fixtures/gi4/pins/`, parity digests in `tests/test_harness_engine_parity.py` | lead only (regenerated at integration) | — |
| `API.md`, `ARCHITECTURE.md`, `HARNESS.md`, `README.md` | each package appends ONE new section `## Core repair and customer interface (2026-11-03): <package>`; no rewrites | — |

## 3. Reader packages (P1, P2): the release standard and the measurement

- The round-4 standard governs (ruling 2026-11-03 (g); R8 section 4): a releasing rule must keep every must-stay-held input
  held; closed lists may only add holds; structure beats vocabulary (R8 3.3); do not widen shared lists such as `HEDGE_WORDS`.
- **Declaration first.** Your first commit is `tests/fixtures/gi4/declarations/<pkg>.json` (`declared_before_code: true`, base
  `c9f20a148`), naming every expected movement: H4 battery rows (machine-read `battery`), H1 replay movements (prose per document
  and state), H2 classes (`movements`, NEW-SEND = NEW-TAKE = 0 always), the register rows (R8 D-ids) you move and their direction,
  the Mara outcome, and the tests whose pins you expect to move. Amendments are appended, dated, and say before/after code.
- **Measure both directions on the same inputs** (R8 1.4): the false-READY register (R8 `probes/R8-history-defects/r8_cases.py`,
  run with `defects_probe.py` against your tree) AND the false-hold inputs (Mara, `tests/fixtures/cux/mara/`, and your new class
  documents). Tools: `python -m ops.gi4.replay --fixtures --base c9f20a148 --head <your HEAD>`, `ops.gi4.battery`, `ops.gi4.freeze
  --quick`, `ops.gi4.corpus judge` (H3: no MUST cell that passes on base may fail on head), `ops.gi4.cost` for any changed reader.
  Use `--scratch <your scratch>`.
- **Add the register rows as permanent battery rows with truths** (R8 1.5) where your package changes them, declared as movements.
- New synthetic class documents go to `tests/fixtures/cux/reader/` (P1) or `tests/fixtures/cux/holds/` (P2): each a positive case
  AND at least one must-stay-held twin in different wording. Every file starts `SYNTHETIC TEST DOCUMENT - FICTIONAL`.
- Mara's retained text and Corti response are copied (read-only source) to `tests/fixtures/cux/mara/` by the lead before the
  builders start: `rev1.txt` (the revision text) and `corti-response.json` (the raw response bytes, decoded) plus `request.json`.

## 4. P3 REVIEW: the effective review overlay, modifiers, approved-export truth

Adopt R3 section 7 (`/home/claude/cpt-studio-ux-20261103/understand/R3-validation-review.md`):
- New pure module `studio/validation/review_view.py`: `review_view(stored, decisions, *, services, retrieval, reference_sources,
  service_date, answers) -> {key: View}` over the stored proposals and the current decisions (and P5's member answers, passed in
  as data). The base rule and the PFS endoscopic-family check are ONE implementation shared with the engine (extract them from
  `engine._encounter`/`_proposal`; the engine calls the extracted function; byte-identical engine output, proven by replay EQUAL).
- Positive control: with no decisions and no answers the overlay reproduces every stored status and check byte for byte (test it
  over every battery row and the regression fixtures).
- Hook it everywhere a status or an action is read: `review._actions`/`_allowed`/`record_decision`, `readiness`/`_assessment_blockers`,
  `coding_completeness`, `refresh_state`/`_state_and_run`, `serializers._proposal_json` (operator view), the customer API (P4 calls
  `review.effective_view(assessment)`; signature fixed here: `def effective_view(assessment) -> dict[str, View]` in review.py), and
  the report snapshot. D14: reinstating 45385 beside a selected 45378 holds 45378 (approve withheld by `services.base_included`,
  question "Is 45378 reported separately from 45385 for this examination?"), and an APPROVE already on 45378 becomes a readiness
  blocker until revoked; rejecting the therapeutic releases only per the engine's own rule (no new release semantics).
- **Modifier review (directive 4 last paragraph).** Structured consideration on each proposal (keep the old string list for the
  operator report; add `modifier_review` to the overlay view): `{kind: 'distinct_lesion', codes, lesions, options: ['59', 'XS'],
  text, sources: [{title, release, section}]}` recomputed over the effective set (dropped when the other code leaves it). Wording
  cites the dated CMS source CPT Studio holds: Pub. 100-04 chapter 12 (claims manual) item 13 example (45380 with 45385 for
  lesions in different parts of the colon), and says NCCI procedure-to-procedure edits and payer modifier policy are not checked.
  The reviewer may choose ONE modifier per approval: none, `59` or `XS` (never both, never prefilled, never a free list), stored on
  the decision. Migration `0009_cux_review`: `Decision.modifiers = JSONField(default=list, db_default=[] via RunSQL SET DEFAULT
  pattern of 0007)` (additive). `record_decision(..., modifiers=())` validates against the view's options; approve without a
  needed modifier is allowed (the reviewer may judge none applies). The decision endpoint accepts `"modifiers": ["XS"]`.
- **Approved-export truth.** A report snapshot reads the overlay. P4 renders the customer approved export from
  `review.approved_items(assessment) -> list[Item]` (P3 provides: code, units, modifiers, approver label, approver kind, decided_at,
  note, exact evidence spans, one-sentence summary) — approved items only; unresolved and unapproved items never appear in it.
- Answers effect (P5 data, P3 rule): a proposal-scoped question answered `not_documented` or `cannot_confirm` makes the view's status
  `excluded` with reason `detail_unavailable` (not reinstatable, no decision required, never approvable) until the answer is
  revoked; readiness treats it as resolved. Service-scoped answers close the question only.
- Declare in `cux-review.json`: the overlay moves no engine output; the structured modifier consideration and the base-rule
  extraction must leave replay EQUAL and battery 0 (if anything moves, declare it).

## 5. P4 CUSTOMER-API: the customer contract (allowlist), operator diagnostics, reports

Adopt R4 section 6 (`R4-api-leak-surface.md`), with these fixed choices:
- Operator grant: append-only `OperatorGrant(ImmutableModel)` and `OperatorRevocation(ImmutableModel)` (R4 6.2), granted only by
  management commands `grant_operator --username U --reason-file F` and `revoke_operator ...`; `studio/operator.py:is_operator(user)`
  reads no Membership; every operator URL answers 404 to non-operators (never 403). Operators may sign in without a membership; an
  operator with no membership lands on `/ops/`. Login stays the same page.
- Operator URLs under `/ops/` (R4 6.4): `/ops/` shell (`templates/studio/ops.html`, one script `/ops/assets/ops.js` served by a gated
  view from `studio/operator/ops.js`, never under `static/`), `/ops/api/encounters`, `/ops/api/encounters/<id>` (today's full
  `serializers.encounter_detail`), `/ops/api/encounters/<id>/trace`, `/ops/api/encounters/<id>/reports`,
  `/ops/api/reports/<id>/download` (any artifact, stored bytes, `X-Content-SHA256`), `POST /ops/api/encounters/<id>/reports`
  (operator full report), `POST /ops/api/encounters/<id>/reconcile` (reconcile becomes operator work). Operator page access is
  audited as `operator.viewed` (never shown to customers). `/api/encounters/<id>/trace` is removed from the customer URLconf.
- The operator bundle is today's `app.js` moved to `studio/operator/ops.js` with its API base switched to `/ops/api/`; its node tests
  move to `tests/operator/ops.test.cjs`. P4 does not edit `studio/static/studio/app.js` (P6 owns it).
- `ReportArtifact.audience` (`CharField(max_length=10)`, DB default `'operator'` so every existing row reads operator); customer
  reports are `audience='customer'`; the customer download answers 404 for any non-customer artifact, carries no `X-Content-SHA256`,
  and answers 409 "This export no longer matches the saved decisions; create a new one." when an approved customer artifact's
  snapshot digest no longer matches the persisted decisions. Existing artifacts are never modified.
- Customer reports, format `cpt-studio-customer-report@1` (TXT and CSV): SYNTHETIC banner at both ends; encounter title, date of
  service, generated at, generated by; **draft** = the numbered suggested codes with status label, units, modifiers (decided only),
  one-sentence explanation, quotes (exact, with page) and the concise limitations, headed "Suggested codes — not approved";
  **approved** = approved items only (P3 `approved_items`): code, units, modifiers, approver label, "Agent-executed synthetic
  review — not clinical approval" when the approver is an agent, decided at, quote(s) with page and character offsets; then the
  limitations. No participant, model, usage, hash, rule id, run id, engine/profile version, check id or source key appears. CSV
  columns (approved): `report_format, encounter_title, date_of_service, number, code, units, modifiers, status, approved_by,
  approver_kind, approved_at, summary, evidence_text, evidence_page, evidence_start, evidence_end`; the draft CSV the same with
  `status` and empty approval cells. Formula-leading cells neutralised as today.
- Customer API: `studio/customer_api.py` builds every payload by allowlist (no stored free text passed through: re-derive from
  structured fields, R4 6.1(1)). Contract below (section 7). Customer error bodies use a fixed vocabulary; `ValidationError` text
  from deeper layers is never passed through (map known refusals to plain sentences; else "This action is not available right now.").
- Tests: `tests/test_customer_surface.py` per R4 6.6 (value-based denylist from the DB + regex net, every customer endpoint/role/
  download/error body/`GET /`/collected static bundle; schema allowlist; authorization matrix for every `/ops/` URL and the removed
  trace URL; legacy artifacts 404 to customers and byte-identical to operators; mutation proofs printed with sha256).
- A generator test writes `tests/fixtures/customer/*.json` from the real customer serializer when `CPT_STUDIO_WRITE_FIXTURES=1`, and
  otherwise asserts the committed customer fixtures have exactly the serializer's key shape (the harness2 fixture pattern).

## 6. P5 FLOW: details, member context, progress, upload idempotency, reassessment

- **Progress** (`studio/progress.py`, pure over rows): `encounter_progress(encounter, now) -> dict` folding the current revision's jobs
  (R6 3.2): extract -> `reading` "Reading your document"; analyze -> `identifying` "Identifying procedures"; predict + astra + fable +
  first assess when peers follow + astra_peer + fable_peer + review2 -> `checking` "Checking suggested codes" (active detail "Document
  review" for predict, "Independent checks" for participants and peers); the final assess -> `preparing` "Preparing your results"
  ("Coding validation"). Each step `{key, label, state: done|active|waiting|not_started|failed|stopped|skipped, started_at,
  finished_at}` from Job.created_at/started_at/finished_at. Phase: `queued` (busy, active job queued), `processing`, `action_needed`
  (the member-date hold: ProviderRun `scope.held == 'member_date_conflict'` on the current context), `awaiting_detail` (not busy,
  open details), `completed`, `partial` (final assessment present AND a participant/peer outcome failed/refused/unknown/not_sent/
  blocked, or reference validation failed/not verified, or extraction partial), `failed` (extraction_failed, processing_failed,
  provider_failed, provider_not_run), `stopped`, `being_confirmed` (provider_unknown: "We are confirming whether an earlier check
  completed. Nothing will be sent again until that is settled."). `slow` only from the job deadlines (`settings` stage bounds): a step
  running longer than its bound's 60% says what it is waiting for in plain words. Never a percentage or ETA. `can_leave` true.
  Customer messages per phase are a fixed table (no Job.error text).
- **Details** (`studio/answers.py`): `details_needed(encounter, assessment, view) -> list[dict]` — one row per OPEN material question,
  de-duplicated by (fact, family, code), each with its control: `date` (service_date: document value + quote and entered value side
  by side, action "Use document date" only when the pre-merge document fact is a single documented value; never prefilled with an
  unsupported date), `choice` (setting, patient_status, billing_context: the listed values + "Not documented"), `confirm` (clinical
  facts: conflict:<act>, performed_status, em_basis, extent, target, cannulation, base_included, units...: ONLY "Not documented" or
  "Cannot confirm" — a member never supplies a clinical fact — plus the existing physician addendum path offered as "Add to the
  documentation (physician)"). Each row lists the codes it affects (`affects`) and its saved answer.
- `POST /api/encounters/<id>/details` `{"answers": [{"id", "fact", "value"}]}` in ONE request (one save for all rows): context facts
  go through ONE `jobs.change_context` call (existing path; re-assessment as today); `not_documented`/`cannot_confirm` answers are
  stored as `MemberAnswer` rows (append-only: encounter, revision, fact, family, code, value, answered_by, answered_at, revoked_by/at via
  a revocation row) and applied by P3's overlay at read time (no new assessment, no send). Answers bind to (code, family, fact), never
  to a positional key (lesson EV-1). Each saved answer is audited `detail.answered` (customer-allowlisted summary "A detail was
  answered"). `POST /api/encounters/<id>/details/<answer id>/revoke` undoes one. 409 while busy (as context today).
- **Use document date**: the details endpoint with `{"fact": "service_date", "value": "use_document"}` = clear the member value (the
  existing clear path, `change_context` with `service_date: ''`).
- **Document date stored with the context**: add a function `context.document_service_date_fact(text)` (no constant edits) and store
  its JSON in a new nullable field `EncounterContext.document_date` (migration `0009_cux_flow`), filled at context creation; the
  customer API reads it to show the document date beside the entered one (R2 4.4, Q-6).
- **Upload idempotency**: `POST /api/encounters` accepts an optional `client_key` (UUID the page generates per upload attempt); a
  repeated key from the same user within 24 h returns the first encounter's id (201 with the same id) and creates nothing. New
  nullable field `Encounter.client_key` + a unique index on (created_by, client_key) for non-null keys (CreateIndex is gate-safe; the
  constraint must be an index, not AddConstraint on an existing table).
- **Reassessment from retained responses** (R6 6.4): management command `reassess_retained --encounter <uuid> --tag <release>` that
  enqueues the AGAIN-mode assess (`:c:` key with the tag digest) under the guards R6 lists, writes audit `assessment.refreshed`
  (customer summary "Results were refreshed with updated software"), and never sends. A `--dry-run` prints what it would do.
- Customer progress, details and service-date blocks are built by these modules and called by P4's `customer_api.py` with the
  signatures above.

## 7. The customer encounter contract (`GET /api/encounters/<id>`; every key listed; nothing else)

```jsonc
{
  "id": "uuid", "title": "str", "created_at": "iso", "updated_at": "iso",
  "state": "processing|action_needed|awaiting_detail|ready|reviewed|no_codes|stopped|failed|being_confirmed",
  "state_label": "Processing|Action needed|A few details needed|Ready for review|Reviewed|No codes suggested|Stopped|Could not finish|Being confirmed",
  "permissions": {"can_review": true},
  "document": {"kind": "upload|paste|addendum", "name": "str", "media_type": "str", "size": 123, "page_count": 3, "revision": 1,
               "text": "canonical text", "pages": [/* page spans as today's revision.pages */],
               "reading": {"status": "pending|ok|partial|failed", "label": "plain", "messages": ["plain"]},
               "original_url": "/api/encounters/<id>/original" | null},
  "service_date": {"value": "YYYY-MM-DD"|null, "source": "document|member|conflict|missing", "document_value": "YYYY-MM-DD"|null,
                   "document_quote": {"text": "", "start": 0, "end": 0}|null, "entered_value": "YYYY-MM-DD"|null,
                   "conflict": false, "can_use_document_date": false},
  "progress": {"phase": "...", "busy": false, "steps": [{"key": "reading", "label": "Reading your document", "state": "done",
               "started_at": "iso", "finished_at": "iso"}], "active_detail": "", "started_at": "iso", "finished_at": "iso",
               "server_time": "iso", "slow": false, "message": "plain", "can_stop": false, "can_resume": false, "can_leave": true,
               "error": {"text": "plain", "action": "resume|new_document|none"}|null},
  "checks": [{"key": "document_review", "label": "Document review", "state": "done|running|waiting|unavailable|not_run"},
             {"key": "independent_checks", "label": "Independent checks", "state": "..."},
             {"key": "coding_validation", "label": "Coding validation", "state": "..."}],
  "codes": [{"id": "proposal uuid", "number": 1, "code": "45385", "units": 1, "modifiers": [],
             "modifier_review": {"options": ["59", "XS"], "text": "plain", "sources": ["CMS claims manual Pub. 100-04 ch. 12 (Rev. 13753, 2026-05-07)"]}|null,
             "status": "ready|needs_detail|approved|excluded", "status_label": "Ready for review|Needs a detail|Approved|Excluded",
             "sub_label": "plain or ''", "summary": "one sentence from CPT Studio's own reading",
             "why": {"quotes": [{"text": "", "start": 0, "end": 0, "page": 1, "exact": true}], "qualifications": ["plain"]},
             "detail_ids": ["..."], "allowed_actions": ["approve", "reject"],
             "decision": {"action": "approve|reject|reinstate|confirm", "by": "label", "by_kind": "human|agent", "at": "iso",
                          "note": "str", "modifiers": []}|null}],
  "other_codes": [{"code": "99204", "reason": "plain"}],
  "not_separately_coded": [{"label": "plain", "reason": "plain"}],
  "details_needed": [{"id": "", "fact": "", "family_label": "plain", "prompt": "plain", "control": "date|choice|confirm",
                      "choices": [{"value": "", "label": ""}], "allow": ["not_documented", "cannot_confirm"],
                      "document_value": null, "entered_value": null, "quote": null, "affects": ["45385"],
                      "saved": {"value": "", "label": "", "by": "label", "at": "iso", "answer_id": ""}|null,
                      "addendum_allowed": false}],
  "unresolved": ["plain"], "limitations": ["plain"],
  "readiness": {"draft": true, "approved": false, "blockers": ["plain"]},
  "reports": [{"id": "", "kind": "draft|approved", "fmt": "txt|csv", "filename": "", "generated_at": "iso", "generated_by": "label",
               "download_url": "/api/reports/<id>/download", "current": true}],
  "activity": [{"event": "allowlisted key", "summary": "plain", "actor": "label", "actor_kind": "human|agent", "at": "iso"}]
}
```

Codes order: selected and reinstated codes by stored position, then excluded-but-decidable codes; alternatives go to `other_codes`
only. Status mapping: approved decision -> approved; reject decision -> excluded (sub_label "Rejected in review"); confirmed exclusion
or engine exclusion -> excluded; needs_clarification -> needs_detail; ready (incl. reinstated, undecided) -> ready. Agent approvals:
sub_label "Agent-executed synthetic review — not clinical approval". `summary` from `support.detail`/`support.acts[].label`
re-worded without engine jargon; `why.quotes` are CPT Studio's own located passages for the matched act (support.source / act
evidence) first, then the provider's exact passages only when they support (support.supporting); never a passage that does not
support. Session (`GET /api/session`): `user {id, label, initials, actor_kind}, workspace {id, name}, role, can_review,
acknowledgement, counts, synthetic_only` (no provider_mode, no release). List rows: `id, title, state, state_label, service_date,
date_conflict, open_details, created_at, kind`.

**Amended 2026-11-04 (integration; session decisions (n) and (o), `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`).**
The contract gains two keys, and nothing else changes: `"recheck": {"available": bool, "can_request": bool}` after
`unresolved` - the bounded second review the installed page offered, kept as "Check what is still open again" (R4's open
question 1 answered by keeping the installed capability) - and `in_queue` (boolean) on each list row, the predicate the
session's `counts.queue` counts, so the queue lists exactly what its badge counts. `progress.phase` also takes `paused` (decision (j)):
busy while the worker's heartbeat is older than 120 s, drawn without animation.

**Amended 2026-11-04 (refutation round 2).** Status mapping: a reinstated code whose approval waits on a question (the
overlay's needs_clarification) maps to needs_detail, with the row that asks it; a reinstated code with nothing to wait
on stays ready. Section 5's customer report: the TXT starts with the SYNTHETIC line, then the headline; the CSV gains a
last column `review_label`, the agent-executed synthetic review label on each row of an agent's approval (the approver
alone decides it). `why.quotes` and the approved export's evidence are one rule (`review.evidence_spans`): nothing
unless the support reading records the act as shown ('pass' or 'warn').

## 8. P6 UI: DOM contract (P8's walk tool depends on these exact hooks)

- Result list: `ol.result-list` > `li.result-row[data-proposal=<id>][data-code=<code>][data-status=<status>]` with `.result-number`,
  `.result-code`, `.result-units`, `.result-modifiers`, `.status[data-status=<status>]` (text = status_label), `.result-sub`,
  `.result-summary`; `details.why-code` > `summary` "Why this code?", `.why-quote[data-start][data-end][data-page]`, `.why-qualification`;
  actions `button[data-decision=<action>][data-proposal=<id>]` (only `allowed_actions`).
- Details panel: `section.details-panel` (heading "A few details needed") > `.detail-row[data-detail=<id>][data-fact=<fact>]`;
  date control `input[type=date][data-detail-input]`; choices `input[type=radio][name="detail-<id>"]`; buttons
  `button[data-detail-choice="not_documented"]`, `button[data-detail-choice="cannot_confirm"]`, `button[data-action="use-document-date"]`;
  `.detail-document-date`, `.detail-entered-date`; save `button[data-action="save-details"]`; saved state `.detail-saved`.
- Progress: `section.progress-panel[data-phase=<phase>]` > `.progress-step[data-step=<key>][data-state=<state>]`, `[data-elapsed]`,
  `.progress-message`, `.leave-note`, `button[data-action="stop"]`, `button[data-action="resume"]`. While busy the panel also carries
  the class `progress-card` (the old walk waits for its absence). No animation class on any step when the phase is failed/stopped.
- Upload acknowledgement: `.upload-ack` shown from the POST 201 before the first GET ("Uploaded. Reading your document…").
- Checks: `ul.checks-panel` > `li.check-step[data-check=<key>][data-state=<state>]`.
- Review dialog `#reviewDialog`: `#reviewAcknowledgement`, `#reviewNote`, `#saveReview`, and `select#reviewModifier` (options "", "59",
  "XS") shown only when the code has a `modifier_review`. Export dialog `#exportDialog` > `button.export-option[data-export-kind=
  draft|approved][data-export-fmt=txt|csv]`; the approved option disabled with the blockers listed when `readiness.approved` is false.
- One script on the customer page; CSS appended only after the pinned 32,785-byte prefix; no `:root`/tokens; no `url(`; touch targets
  >= 44 px; no horizontal scroll at 390 px; reduced motion respected.

## 9. P7 INSTALL and P8 VERIFY

- P7 adopts R7 section 7 (`R7-install-ops.md`): blue/green web on 9150/9151, worker drained before the switch and started after it,
  `publish_vhost` switch with exact restore, drain of the old web, availability recorder in the receipt, failure matrix, a
  `switch-back` phase for post-success rollback without interruption, `operators` phase (creates `ops-agent` [agent, no
  membership, grant; password file `/home/claude/.cpt-studio/ops-agent-credentials.json` 0600, top-level `username`/`password`] and
  `platform-operator` [human, no membership, grant; root-only `/etc/cpt-studio/operator-credentials.json` 0600]), and a `reassess`
  phase (runs `manage reassess_retained` for named encounters in a one-shot, receipt with the job ids). Offline tests per R7 section 8.
- P8 adopts R9 section 3.6 (`R9-tests-tooling.md`): the walk tool reads the new DOM contract (section 8), adds negative scans (API JSON,
  DOM text and attributes, downloads, toasts, the served bundle) and an operator session (`--operator-credentials FILE`) for the
  positive provenance checks and the no-duplicate-send proofs; `verify_downloads.py` parses `cpt-studio-customer-report@1`, checks
  approved-only content, units, modifiers and exact evidence against an independent source (`--api-dir` fed from the operator API).

## 10. P1 READ-BIND: the rules (R1 section 9, R2 section 1.4, R3 7.5.3) — in this order

Adopt `R1-services-binding.md` section 9 rules with their stated risks and test obligations:
1. **Rule 2** attributive participle compounds ("snare-treated", "biopsy-proven", "clip-closed", "band-ligated", "APC-treated",
   "snare-resected") are never act statements (`_acts_in`, `has_act_verb`, `read_clause`'s performed test). Hold-only.
2. **Rule 1** lesion labels and specimen labels: a lesion introduced under a label (line or sentence start, label + separator +
   anatomy or a lesion noun in the same clause; exact case-sensitive tokens; unique labels only) keeps it (`Lesion.label`, new
   field with a default); a later word-bounded mention in an act's clause, or a specimen reference equal to the lesion's
   specimen, binds the act to that lesion, its service and its region BEFORE `_family_for_act`; an unresolved or ambiguous label
   reads exactly as today. Bind act and lesion together (never an act of one service at another service's lesion).
3. **Rule 4** a report title naming two or more services binds no single family (`parts()`); each named service still gets
   its title reading; a site-less, label-less prose denial in such a part is set beside EVERY service that documents the act
   done (the `unplaced` extension), never dropped. Must land with or after rule 1 (R1 probes 3(A), 8c).
4. **Rule 3** copular negation "S was/were/is/are not a/an/the N (of|for) O" negates only N at O; never an act in S; never an
   act inside O's modifiers; "not a second/another/repeat <service>" denies another occurrence and is never performance evidence.
   Verbal negation unchanged (`test_controls_a_negation_of_the_act_itself_still_denies_it` must pass).
5. **Rule 5 (minimal)** a per-procedure section heading is NOT ended by: a field-label line whose value follows on the next line,
   a table header or cell line, or page furniture (a line repeated at page edges, page-number lines, the repeated title). Every
   other heading still ends it, and the other-tract site override still wins. Pass the revision's pages into `parts()`. This is
   the A1 class (`pi.json` PI-A1-HEADING-LAPSE-REBINDS): add those shapes as must-stay tests.
6. **Rule 8 + routing E/M**: one shared pattern in `cues.py` for an explicit statement that no separate E/M service / office
   visit / office-visit time is documented, performed, provided, billed, reported or occurred, read by BOTH
   `services.EM_ROUTINE`'s branch (with a distinct cue wording: "an explicit statement that no separate office E/M service is
   documented") and `detect._em_base_reading` (R2 1.4's rule: negator governs the visit mention when only visit qualifiers stand
   between, or the mention sits inside "no <NP> is/was documented|provided|...", or "... was/is not (separately) provided|
   documented|..."). Keep: an affirmative E/M statement elsewhere outranks it (contradictory notes still ask); "not billed
   separately" / "not separately billable" keep today's reading (an owner question, R2 Q-1).
7. **Validation E/M gating** (`engine._service_questions`, R3 7.5.3): skip `gi.office_em` documentation questions when the
   office E/M service is not established (routing/inventory `uncertain` with the procedure-day `EM_WITHOUT_BASIS` reading) and no
   decidable E/M proposal exists; keep them when an E/M code is proposed or the visit is documented performed/incomplete. The
   unresolved-service count stays (the customer sees "An office visit is mentioned but is not documented as a separate service").
8. **Rule 6 (optional, last)** tract binding when every site of a sentence lies in one tract. Attempt only after 1-7 are green;
   DROP it (and record it as a limit) if any must-stay-held input or pinned test moves in the wrong direction.

Rule 7 is the invariant: `_same_subject` unchanged; a site-less, lesion-less denial inside one service's own part still pairs with
every act of its kind (the "No biopsies were taken." held case); the tests R1 lists under rule 7 must keep passing.

Acceptance for P1 (measured, in the report): Mara replayed offline through `jobs._assess_child` with the retained Corti response
(`tests/fixtures/cux/mara/`) gives 43239, 45380 and 45385 all `ready`, 0 proposal questions, 0 E/M questions, the clip bundled
under the colonoscopy, and the 45380/45385 distinct-lesion consideration present; every must-stay-held twin stays held; the R8
register rows are unchanged or move only toward held; H1/H2/H3/H4 measured and every movement declared; the new tests pass; the
DB-free reader modules (R9 5.3) pass.

## 11. P2 READ-HOLD: the register repairs (hold-only), R8 section 1.2 and 1.3

For each of D1-D10, D12, D13, D15 (D14 is P3's): reproduce on base with R8's probe inputs, apply the verifier sketch of R8 1.3
WITH its recorded trap avoided, prove the row moves to held/excluded, and prove the controls R8 names stay as they are (notably
`tests/test_services_reconcile.py` `test_control_a_passage_naming_an_act_the_reader_does_not_read_still_stands`, "Cecal biopsies
x2." must stay READY). Specifically: D1 failure vocabulary gate on the own-passage release (candidate_rb); D2 `FAILED_ACT` in
`read_clause` (never widen `HEDGE_WORDS`); D3 routing negated/cancelled reading as a status signal in `_about`/`_status_signal`
and the `read_clause` negation forms "none was", "at no point was", "whether ... were not obtained", plus the box row tie; D4
release only when `_family_for_act` places the act in the matched family alone (fail-closed); D5 no release inside a
non-physician role part; D6 title branch only for physician role parts; D7 `Label: <service>` heading naming exactly one family
opens a part (coordinate: this one line is in `parts()`; P1 owns `parts()` — implement D7 as a separate helper P1's `parts()`
calls, and say so in your report; the lead wires it at integration if P1 did not); D8 indication inside a titled report; D9 the
third hold arm on any cue + the base companion (a code the readers do not read as performed never covers an act or makes a base
included); D10 attached prior report title read as another occasion; D12 C4 on a folded copy (no-break/zero-width/soft hyphens)
and the `in person today` regex that matches inside "not seen in person today"; D13 a named EGD whose extent a later statement
contradicts is held [extent]; D15 a base code inside an including service (EUS includes EGD) is held. Also R3 7.5.1 (narrow
evidence hold): hold when EVERY provider passage lies in another documented service's scope or reads as another time or a denial
(hold-only; Mara's 45385 must stay ready — its passages are in the colonoscopy scope).

Add every register input as a permanent battery row with its truth (declared movements). Measure both directions (R8 3.3 lesson 4):
the register rows move to held, and Mara/the class documents of P1 (when merged) do not move. Record each false-hold cost.
