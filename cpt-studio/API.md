# CPT Studio JSON API — the frontend contract

Session-authenticated; every POST sends `X-CSRFToken` (read from the
`cptstudio_csrf` cookie). Errors: `{"error": "<message>", "details": {...}}`
with 400 (invalid input), 404 (not found or not in your workspace), 409
(state conflict, e.g. reviewed report not ready), 403 (role cannot review).
Text the database cannot store exactly (NUL, a lone surrogate) in pasted text,
an addendum, a note or an acknowledgement answers 400; it is never altered.
Titles and file names drop those characters.
Timestamps are ISO-8601 UTC. Text offsets are Python code-point offsets into
`revision.text`.

## GET /api/session

```json
{
  "user": {"id": "uuid", "username": "agent", "label": "CPT Studio review agent (automated agent)",
           "actor_kind": "agent", "initials": "RA"},
  "workspace": {"id": "uuid", "name": "Gastroenterology", "subtitle": "Synthetic demonstration workspace",
                "category": {"slug": "gastroenterology", "name": "Gastroenterology", "profiles_version": "gi-profiles@2"}},
  "role": "reviewer", "can_review": true,
  "acknowledgement": "I am an automated agent. I read the whole source document, ...",
  "counts": {"documents": 7, "queue": 2},
  "synthetic_only": true, "provider_mode": "live", "release": "<git sha>"
}
```

## GET /api/encounters

```json
{"encounters": [{
  "id": "uuid", "title": "Colonoscopy report", "state": "ready_for_review", "state_label": "Ready for review",
  "service_date": "2026-10-21", "service_date_conflict": false,
  "families": ["Colonoscopy", "Upper GI endoscopy (EGD, esophagoscopy, enteroscopy)"],
  "source_kind": "pdf", "open_clarifications": 0, "created_at": "..."
}]}
```

`service_date` is the documented or member-entered date, else null; `service_date_conflict` is true when the date is
a conflict (within the document, or a member's date against the document's), so the list shows it as one, never as
not documented.

Encounter `state` ∈ `processing`, `stopped`, `extraction_failed`,
`processing_failed`, `provider_not_run`, `provider_failed`, `provider_unknown`,
`needs_clarification`, `ready_for_review`, `reviewed`, `no_codes`.
`counts.queue` in the session counts the encounters the review queue lists: those whose `queue_reasons` is not
empty (GI round 2; until then it counted `needs_clarification`, `ready_for_review` and `provider_unknown` only). Each
list row carries `queue_reasons` - what the encounter waits on a workspace member for, in this order: `question` (an
open clarification), `decision` (a code needing a reviewer's decision, or an exclusion to confirm or reinstate),
`reconciliation` (an unknown provider outcome not reconciled), `incomplete` (the coding completeness reads
incomplete), `second_review` (the bounded second review can be asked for now, by the predicate POST second-review
accepts an ask by), and `state` (a state that always waited on a member, when nothing above is found); empty while
processing - plus `coding_state` (the encounter view's coding completeness: `incomplete`, `pending_review`,
`reviewed`, `not_established`) and `service_date_evidence` (the documented text the reader kept as evidence of a
service date it could not use, quoted by the list instead of "not documented"; '' otherwise).
`state_label` is the human label (design vocabulary). A response refused whole
(the primary's, or the bounded second review's) is never `no_codes`: with nothing
left to decide the state is `provider_failed`, its `state_run` the refused run,
labelled "Provider response not used". A `no_codes` state is labelled from its
rows: beside a second review made for the answer the assessment reads that the
assessment did not read, that review's outcome ("Second review outcome unknown",
"Second review failed", "Second review not sent", "Second review not read yet");
otherwise, when the provider's codes are listed and none can be decided (excluded
with no reinstatement, or offered only as alternatives), "No code selected for
approval"; only an assessment that lists no code is "No CPT codes proposed"
(refutation p2, reports2:2 and reports2:3). The readiness blocker reads the same
rows: "No code is selected for approval: the provider proposed only codes that
were excluded or offered as alternatives", or "No CPT code was proposed".

## POST /api/encounters (multipart/form-data)

Fields: `file` (PDF/DOCX/TXT) **or** `text` (pasted note); `title` (optional);
`service_date` (optional `YYYY-MM-DD`, recorded as user-supplied metadata);
`synthetic_attestation=yes` (required). → `201 {"id": "uuid"}`.

## GET /api/encounters/{id}

```json
{
  "id": "uuid", "title": "...", "state": "ready_for_review", "state_label": "Ready for review",
  "created_at": "...", "created_by": "label",
  "permissions": {"can_review": true, "is_owner": false},
  "harness": {
    "participants": [
      {"name": "corti", "label": "Corti", "vendor": "Corti", "model": "", "state": "done",
       "detail": "Answered; its codes were checked.", "run_id": "uuid", "reused": false, "codes": ["45385"],
       "unverified_quotes": 0, "usage": {"creditsConsumed": 0.0281}, "usage_basis": "provider_reported_credits_not_usd",
       "estimated_cost_usd": null, "returned_model": ""},
      {"name": "astra", "label": "Astra", "vendor": "OpenAI", "model": "gpt-6-astra", "state": "refused",
       "detail": "Answered; the reading was not used: the response was cut off at the output limit.", "run_id": "uuid",
       "reused": false, "codes": [], "unverified_quotes": 0, "usage": {"input_tokens": 1200, "output_tokens": 16000},
       "usage_basis": "...", "estimated_cost_usd": "0.8120", "returned_model": "gpt-6-astra"},
      {"name": "fable", "label": "Fable", "vendor": "Anthropic", "model": "claude-fable-5-1", "state": "not_configured",
       "detail": "Not configured on this installation.", "run_id": null, "reused": false, "codes": [],
       "unverified_quotes": 0, "usage": {}, "usage_basis": "", "estimated_cost_usd": null, "returned_model": ""}],
    "reference_validation": {"state": "done", "codes_checked": 2, "passages": 3,
      "sources": [{"key": "...", "title": "...", "release": "...", "effective_start": "2026-01-01", "effective_end": "2026-12-31"}],
      "not_connected": ["NCCI procedure-to-procedure edits (AMA licence agreement not accepted)",
                        "AMA CPT descriptors and guidelines (no licence)", "Payer policies"]},
    "clarification": {"open": 0},
    "final": {"state": "ready_for_review", "label": "Ready for review"}
  },
  "revision": {
    "id": "uuid", "number": 1, "kind": "upload", "revisions_total": 1, "created_at": "...",
    "source_file": {"name": "note.pdf", "media_type": "application/pdf", "size": 12345, "sha256": "..."},
    "addendum_text": "", "addendum_offset": null,
    "extraction": {"status": "ok", "method": "pdf-text", "messages": [], "ocr_pages": [], "page_count": 2, "engine": {}},
    "text": "...", "text_sha256": "...", "pages": [{"page": 1, "start": 0, "end": 812}]
  },
  "context": {"facts": {
      "service_date": {"value": "2026-10-21", "origin": "document", "evidence": [{"start": 10, "end": 37, "text": "Date of service: 2026-10-21"}], "note": "", "member_conflict": false},
      "setting": {"value": "office", "origin": "document", "evidence": [], "note": "", "member_conflict": false},
      "billing_context": {"value": "not_documented", "origin": "missing", "evidence": [], "note": "...", "member_conflict": false},
      "patient_status": {"value": "established", "origin": "document", "evidence": [], "note": "", "member_conflict": false}},
    "user_values": {}},
  "routing": {"version": "gi-routing@4", "document_kind": "procedure_report", "families": [
      {"family": "gi.colonoscopy", "label": "Colonoscopy", "supported": true, "status": "performed",
       "mentions": [{"status": "performed", "section": "procedure", "cues": ["..."], "span": {"start": 0, "end": 0, "text": ""}}],
       "facts": [{"name": "extent", "value": "cecum", "origin": "document", "evidence": [], "note": ""}],
       "missing": []}]},
  "pipeline": {"busy": false, "can_stop": false, "can_resume": false, "stopped_by_member": false,
               "stages": [{"kind": "extract", "state": "succeeded", "error": "", "finished_at": "..."}]},
  "provider_runs": [{"id": "uuid", "provider": "corti", "mode": "live", "state": "succeeded", "http_status": 200,
                     "latency_ms": 6123.4, "usage": {"creditsConsumed": 0.0281}, "usage_basis": "provider_reported_credits_not_usd",
                     "request_sha256": "...", "response_sha256": "...", "reused_from": null, "error": "",
                     "reconciled": false, "created_at": "..."}],
  "state_run": null,
  "assessment": {
    "id": "uuid", "profiles_version": "gi-profiles@2", "engine_version": "...", "created_at": "...",
    "proposals": [{
      "id": "uuid", "key": "sel:0", "bucket": "selected", "code": "45385", "code_kind": "cpt1",
      "family": "gi.colonoscopy", "family_label": "Colonoscopy", "eyebrow": "COLONOSCOPY", "supported": true,
      "profile_version": "gi.colonoscopy@1",
      "status": "ready", "status_label": "Ready for review",
      "exclusion_reason": "", "reinstatable": false,
      "descriptor": {"status": "withheld", "label": "Description withheld — no licensed CPT descriptor is connected."},
      "evidence": [{"start": 120, "end": 180, "text": "...", "page": 1, "exact": true}],
      "rationale": "...", "units": 1,
      "checks": [{"id": "evidence.exact", "label": "Exact source evidence", "status": "pass", "detail": "...", "source": "..."}],
      "modifier_considerations": ["..."],
      "clarification_ids": [],
      "decision": null, "decision_state": "undecided",
      "allowed_actions": ["approve", "reject"],
      "proposed_by": ["corti", "astra"],
      "participant_positions": {"astra": {"position": "proposed", "detail": "Astra proposed this code with evidence located in the document.", "quote": "..."},
                                "fable": {"position": "advised_not_to_code", "detail": "Fable advised not to code it: not performed at this encounter.", "quote": "..."}},
      "reference_check": {"state": "passed", "detail": "Present in the CMS fee schedule file: passed; ... NCCI procedure-to-procedure edits are not connected, so bundling with other codes is not verified."},
      "retrieval": [{"kind": "fact", "source_key": "cms-pfs-rvu26d", "release": "RVU26D", "label": "status", "value": "A", "page": "", "section": "", "text": ""},
                    {"kind": "passage", "source_key": "...", "release": "...", "label": "pfs.mult_proc 3", "value": "", "page": "12", "section": "...", "text": "<verbatim CMS text>"}]
    }],
    "encounter_checks": [{"id": "...", "label": "...", "status": "pass", "detail": "...", "source": "..."}],
    "unsupported": [{"family": "gi.other", "label": "...", "status": "performed", "detail": "..."}],
    "reference_sources": [{"key": "cms-pfs-rvu26d", "title": "...", "release": "RVU26D", "effective_start": "2026-10-01",
                           "effective_end": "2026-12-31", "applies": true, "license_note": "...", "scope_note": "..."}],
    "summary": {"selected": 2, "alternatives": 5, "excluded": 3}
  },
  "clarifications": [{"id": "uuid", "scope": "proposal", "proposal_id": "uuid", "family": "gi.office_em", "fact": "setting",
                      "question": "...", "reason": "...", "state": "open"}],
  "decisions": {"history": [{"id": "uuid", "proposal_id": "uuid", "code": "45385", "action": "approve", "note": "",
                             "reviewer": "label", "reviewer_kind": "agent", "created_at": "...", "acknowledgement": "...",
                             "carried_from": null, "invalidated": null, "revision_number": 1}]},
  "readiness": {"draft": true, "reviewed": false, "blockers": ["45380 has no decision"]},
  "reports": [{"id": "uuid", "kind": "draft", "fmt": "txt", "filename": "...", "sha256": "...",
               "generated_at": "...", "generated_by": "label", "download_url": "/api/reports/<id>/download"}],
  "activity": [{"event": "decision.recorded", "summary": "...", "actor": "label", "actor_kind": "agent", "created_at": "..."}]
}
```

A context fact's `member_conflict` is true when a workspace member's value differs from the document's single value
(both kept, neither used): the screen words it as that conflict, never as conflicting documentation or as not
documented.

Proposal `bucket` ∈ selected | alternative | excluded. `status` ∈ ready |
needs_clarification | excluded | informational (alternatives). `decision_state`
∈ undecided | approved | rejected | reinstated | exclusion_confirmed. `allowed_actions` is computed by
the server and is the only source of truth for which buttons are enabled. `approve_withheld_by` is the
same for every member: on a reinstated exclusion it names the check that withholds approve
(`review.reinstatement` or `em.same_day_if_reinstated`), and it is null otherwise.

`state_run` is the id of the provider run a `provider_failed` state reads (the failed stage's own request, else the
run the current assessment read), and null in every other state. The page explains the failure with that run's error,
never with a run picked by recency: a newer request stopped or settled before sending is not the run in use.

### The review participants (HARNESS.md; harness@1)

`permissions.is_owner` is true for the workspace's owner only; it opens the administrative trace below.

`harness.participants` always lists Corti, Astra and Fable, in that order. Each row's `state` ∈ `not_configured`,
`waiting`, `running`, `done`, `refused`, `failed`, `unknown`, `not_sent`, `blocked`, `stopped`, and its `detail` says it
in one plain sentence (why it was not used, not sent or not run, the HTTP status of a failure, how many of its quotes
were not found in the document). While the encounter is processing, a stage the current chain has not reached yet is
`waiting`, one in flight `running`, and after a Stop (or a stage the system cancelled) the stages not run are `stopped`.
Once processing ends, Astra's and Fable's rows read the current assessment's record of them (`done`: its reading was
used; `refused`: it answered and its reading was not used - the vendor refused, cut it off, or another model answered;
`blocked`: nothing was sent because a request had an unknown outcome; `not_sent` with why: nothing was sent, or no
request was made for this revision), and Corti's row reads the run the assessment read; a participant disabled on this
installation reads `not_configured` unless an assessment read its answer. A participant's failure is its row's state:
the encounter `state` is never `provider_failed` for it, and an unknown outcome of any participant - an adapter that
stopped with an unexpected error before it recorded an outcome included - makes the encounter `provider_unknown` until a
member reconciles it (`POST reconcile` takes any participant's run). `codes` are the codes that participant proposed
(Corti's: its selected codes);
`usage` is as the vendor reported it, with its `usage_basis`; `estimated_cost_usd` is a string estimated from published
rates, not reconciled to an invoice, and null for Corti (credits, not USD) and for a run that reported no usage (a
reuse). `reused` is true when a retained answer to the identical request was reused and nothing was sent.

`harness.reference_validation.state` is `waiting` while processing, `done` when retrieval ran for the current
assessment and its traces cover every code a proposal can be decided on, and `not_run` otherwise (no assessment, one
recorded before the harness, or no trace at all - never `done` over zero codes); `not_connected` is always listed.
`harness.final` is the encounter's state and its label.

Each proposal keeps three statuses apart (I4): `proposed_by` (who proposed it: `corti` for Corti's own proposals and
alternatives, and the participants the engine recorded), `reference_check` (`passed`, `attention` or `not_verified`,
from its CMS checks `pfs.presence`, `mue.units` and `pfs.endoscopic_base`; its detail always says that NCCI PTP edits
are not connected) and `decision_state` (a member's). `participant_positions` gives each configured participant's
position on the code - `proposed`, `not_proposed`, `advised_not_to_code` (with its reason) or `not_run` (with why) - and
the first quote of it that was found verbatim in the document ('' when none was); it is `{}` when no participant was
configured. A position never decides a status, and agreement never approves anything. `retrieval` lists the CMS facts
the checks read for the code and the verbatim CMS passages retrieved for it, with source key, release, page and
section ([] for a code that was not looked up: a provider's alternatives never are).

`pipeline.stages` includes the participants' stages (`kind` `astra`, `fable`), between `predict` and `assess`. Their
requests carry the revision alone (no date), so a context change that leaves Corti's request as it is re-assesses with
the participants' answers as they are, and one that re-predicts reuses them; a configured participant with no recorded
outcome for the revision (its stage was stopped, expired or swept before it recorded one, or it was configured since)
gets its turn at such a context change, its stage running before the assess. While a member date conflict is held
nothing is sent, the participants' requests included (their rows say so), and settling the date gives them their turn.
`provider_runs` lists the participants' runs too (`purpose` `independent`); a participant run replayed from a
recording reads `mode` `replay`. The Activity tab names a participant's attempts: "Astra request started", "Astra
response recorded", "Fable request failed (HTTP 529)", "Retained Astra result reused (no new request)", "Unknown Astra
outcome reconciled"; Corti's read as before.

## GET /api/encounters/{id}/trace

The administrative trace of the current revision, for a workspace **owner** only: 403 for a reviewer or a viewer, 404
outside the caller's workspaces.

```json
{
  "encounter": {"id": "uuid", "title": "..."},
  "revision": {"id": "uuid", "number": 1, "text_sha256": "..."},
  "participants": [{"name": "astra", "label": "Astra", "vendor": "OpenAI", "model": "gpt-6-astra", "runs": [{
      "id": "uuid", "state": "succeeded", "sent": true, "mode": "live", "purpose": "independent",
      "run_identity": "uuid (the client request id the vendor was given)", "authorization_ref": "...",
      "requested_by": "label", "adapter_version": "...",
      "endpoint": "https://api.openai.com/v1/responses", "requested_model": "gpt-6-astra", "returned_model": "gpt-6-astra",
      "request_id": "<vendor request id>", "response_id": "resp_...", "http_status": 200, "latency_ms": 6123.4,
      "usage": {"input_tokens": 1200, "output_tokens": 300}, "usage_basis": "...", "estimated_cost_usd": "0.0270",
      "request_sha256": "...", "response_sha256": "...", "response_bytes": 2048, "created_at": "...",
      "finished_at": "...", "error": "", "reused_from": null, "reconciled": false,
      "reading": {"refused": false, "problems": [], "unverified_quotes": 1,
                  "date_of_service": {"value": "2026-10-21", "evidence": [{"quote": "...", "spans": [...], "reason": ""}]},
                  "services": [...], "codes": [...], "not_coded": [...], "questions": [...], "extraction_issues": [...]}}]}],
  "retrieval": [{"code": "45385", "service_date": "2026-10-21", "facts": [...], "passages": [...], "lookups": [...], "notes": [...]}],
  "reconciliation": [{"code": "45385", "family": "gi.colonoscopy", "bucket": "selected", "status": "ready",
                      "proposed_by": ["corti", "astra"], "positions": {...}, "reference_check": {...}, "approved": false}]
}
```

`participants` lists Corti, Astra and Fable, each with its runs of the current revision (Corti's second reviews
included). `response_bytes` is the size of the raw response kept. `reading` is a participant run's full normalized
reading, read again from the stored bytes as the adapter version that recorded it - each quote with the spans it was
found at, or with the reason it was not (an unverified quote, never evidence) - and null for Corti's runs and for a run
with no answer; a stored answer that no longer matches its sha256 reads `{"refused": true, "problems": ["..."], ...}`.
`retrieval` is the current assessment's retrieval traces as recorded. `reconciliation` keeps proposed (`proposed_by`,
`positions`), reference-checked (`reference_check`) and approved (`approved`: the member's current decision is an
approval) apart.

## POST /api/encounters/{id}/decisions

`{"proposal_id": "uuid", "action": "approve|reject|reinstate|confirm|revoke", "note": "", "acknowledgement": "..."}`
Approve requires the acknowledgement to be exactly the current attestation
for the reviewer's actor kind (`acknowledgement` in `GET /api/session`;
surrounding whitespace is ignored); any other text, or none, answers 400, so a page
loaded before the attestation changed is told to reload. → `201 {decision}`; 400 when the
action is not one of the five (any other text, none, or not a string); 409 when the
action is not allowed for that proposal now. A documentation check's exclusion
(`bucket` excluded, `reinstatable` true) is a recommendation, not a final
outcome: it offers `confirm` (agree with the exclusion) and `reinstate`, and
`readiness.blockers` lists "<code> was excluded by a documentation check:
confirm the exclusion or reinstate it" until one of the two is recorded. A
confirmed exclusion stays in the excluded list of every report, with the
confirming reviewer named; `revoke` undoes it. An exclusion for scope or
evidence (`reinstatable` false) offers nothing and needs no decision. A reinstated exclusion that is
not rejected is decided like a selected code, so the encounter view's `assessment.completeness`, the
reports' documented services, `coding` and `second_review` count it as one: the reconciliation is read
again with it counted, `completeness.reinstated` names it, and the stored assessment is unchanged. A
reinstated exclusion offers
`approve` only while its `review.reinstatement` check passes (the gates a
selected code meets: required facts, the separately identifiable E/M on a
procedure day, a known service date); otherwise only `reject` and `revoke`.
The current decision is the one recorded last (by sequence, never by clock).
An E/M whose checks include `em.same_day_if_reinstated` offers no `approve`
while a code carrying `review.same_day_em` has a current `reinstate` or
`approve` decision, since that code is then a same-day procedure; while the
E/M is selected and undecided, reinstated, or was approved first,
`readiness.blockers` lists "<E/M> needs a separately identifiable E/M: <code>
was reinstated as a same-day procedure". Rejecting the E/M, confirming its
exclusion, or rejecting or revoking the reinstatement releases it.

## POST /api/encounters/{id}/addenda

`{"text": "...", "clarification_id": "uuid|null", "synthetic_attestation": "yes"}` → `201 {"revision_id": "uuid"}`.
Creates a new revision (original text + labelled addendum), invalidates current
decisions, runs the pipeline. 400 when the document plus the addendum would
exceed the length limit (nothing is created); 409 while a stage is queued or
running. The addendum revision carries the original's extraction limitations.

## POST /api/encounters/{id}/context

`{"service_date": "YYYY-MM-DD|''", "setting": "office|hospital_outpatient|asc|inpatient|emergency|telehealth|''",
"billing_context": "professional|facility|''"}` → `201 {"context_id": "uuid"}`. Each value is a JSON
string: a listed choice, or null or `''` to clear the user value; any other type (a number, a
boolean, a list, an object) answers 400. A service date is a string in `YYYY-MM-DD` form only
(also on upload). Re-assesses with the provider run in use only when that run answers
exactly the request the new context would send; otherwise re-predicts (an
identical retained result is reused at no cost; a request this document already
sent that failed is never sent again: the predict records a `not_sent` run that
carries that request and names the failure, and re-assesses with it). The run in
use is the current
revision's newest finished request, also when a Stop or an expired stage
cancelled the assess that would have used it; a reconciled unknown outcome is
not, so the attempt the reconciliation released is still made, and neither is a
reserved run the stale sweep settled as not sent (it was never sent), nor a
member date conflict's hold. A member service date that differs from the
document's is that conflict: nothing is built, reused or sent (a `not_sent` run
held for it, and the date question asked) until the metadata is corrected or
cleared or an addendum settles it. A date the document leaves in question (a
conflict within the document; dated text the service cannot read or place - a
date-of-service field stating a date after other words in its field, or where a
header's positions do not match; a
labelled date with a bracket or words after it in its field, or written in a
form the installed revision did not send - a day-first date, a label naming the
time, a table row; or dated text the service keeps only as evidence - a dated
title, a "Date:" line, a dated line naming the service - which is never the
date by itself) is no date: the request goes out without a date line, and a
member's answer makes a second, dated request. The answer must be one of the
dates the document states as some dated text's own value - the withheld
labelled date's where there is one - never a date of birth, another field's
date, or a date only a label or title read as another occurrence's or another
document's states ("Next procedure date: ...", "Surgical pathology report:
..."); where its dated text reads no calendar date (an empty or non-date
date-of-service field among it), any member date is a conflict until an
addendum dates the encounter (ARCHITECTURE 5.2). The
document's own facts are read again inside this request under a
`CONTEXT_REQUEST_SECONDS` wall clock; past it the change is refused (409) and
nothing is changed. 409 while a stage is queued or running, before the text
is extracted, or when the revision's analysis never finished (it overran its
limits, the document names procedures more often than the service reads, or it
failed): nothing is ever sent for a document that could not be read.

## POST /api/encounters/{id}/second-review

Asks for the one bounded second review of the current assessment
(ARCHITECTURE 5.11); owners and reviewers only (403 otherwise). 201
`{"second_review": "queued"}`, or 409 with the reason a bound stands (the
same reason the encounter view's `second_review.reason` shows; one predicate answers the view, the queue and the ask,
so "A second review was already requested for this assessment." is both the view's reason and the 409 once an ask's
stage was queued, whether it later ran, failed or was stopped - Resume runs a stopped one). A second review recorded not
sent, or cancelled before sending, does not use up the bound: the reviewer may ask again (GI round 2, L1). The encounter
view carries `"second_review": {"available": bool, "reason": "...", "items":
["<unresolved item>", ...], "can_request": bool, "run": "uuid" | null}`; `items` is empty when no
documented service is left without a supported proposal. `run` is the id (in
`provider_runs`) of the newest second review made for the answer the current
assessment reads, whatever its outcome, and null when none was: while its
response was not read (unknown, failed, not sent) or not used (refused whole),
the page states that outcome and never says that no CPT codes were proposed.
The current assessment is the one `assessment` shows, and `run` is looked up on
that assessment's own revision: after an addendum, while the new revision is not
assessed yet (stopped, or its predict blocked by an unknown outcome), the page
still shows the earlier assessment and still states its second review's
outcome (refutation p2, reports2:1). An
assessment never queues a second review (owner decision 2026-10-27).

## POST /api/encounters/{id}/stop · /resume · /reconcile

Stop: records an encounter-level Stop; queued stages are cancelled, no further
stage starts and no provider request is sent while it stands. Resume (when
`pipeline.can_resume`): lifts the Stop and re-runs the stage it cancelled, with
the current context. A stage the system cancelled (it expired in the queue, or
a worker stopped mid-stage) is resumable the same way; `pipeline.stopped_by_member`
is false then, and the stage's `error` records what happened. So is the predict
an upgrade queues when it remakes a context the installed revision recorded at a
stage that never sends (an assess queued before the swap or resumed after it, or
the stale sweep's settlement of a predict): it runs as any predict but stops
where it would send, with the reason as its `error` ("Nothing was sent: after an
upgrade this document was read again under the current rules, and ... Resume to
send it."), and the Resume sends that request once (ARCHITECTURE 5.12). A predict whose
provider outcome was already recorded when its worker stopped is settled by that
outcome instead, so a Resume never re-sends a request that already failed. Reconcile: `{"provider_run_id": "uuid", "note": "..."}`
(note 12–2,000 characters) after an `unknown` outcome; allows exactly one new
attempt, for the current revision's current context (never a re-send of a
request this document already sent that failed). Context, resume and
reconcile each run under the encounter's row lock and answer 409 while any
stage is queued or running, so one member action yields at most one provider
attempt.

Notes and acknowledgements are at most 2,000 characters (400 beyond that,
never truncated). An addendum is at most 20,000 characters. A note,
acknowledgement or addendum sent as anything but a JSON string (a list, an
object, a number, a boolean) answers 400 and is never stored as a rendering of
that value; an identifier sent as anything but a string answers the endpoint's 404 (an addendum's
`clarification_id` means "no clarification" only when it is missing, null or empty; `0`, `false`, `[]`
and the like answer 404). `revision.addendum_offset`
is the offset where the latest addendum begins (null when the revision is not
an addendum). `proposal.decision` has the same shape as a `decisions.history` entry.
A decision's `created_at` is when its row was recorded; `decided_at` is when the
reviewer decided (the root of any carry) and `carried_at` is set only on a carried
decision. `proposal.reinstated_by` (`{reviewer, reviewer_kind, decided_at}` or null)
names who reinstated an excluded proposal that now carries a decision (null for a
confirmed exclusion, which was never reinstated).

## POST /api/encounters/{id}/reports → GET /api/reports/{id}/download

`{"kind": "draft|reviewed", "fmt": "txt|csv"}` → `201 {"id", "filename", "sha256", "download_url"}`;
409 with `details.blockers` when a reviewed report is not ready. The download
streams the stored bytes as an attachment; its sha256 equals the response's.
Format `cpt-studio-report@4` (the documented-service sections and columns of
ARCHITECTURE 5.8 added to `@3`): the CSV's `decided_at` is the reviewer's own
decision time; a carried decision also fills `decision_carried_from` and
`decision_carried_at`. A CSV with no proposals has one placeholder row
(`item_list` = `none`) carrying the report kind and SYNTHETIC, before the
encounter rows (`coding_completeness`, and one per unresolved service and per
conflict). In both formats a
C0 control character other than tab and line breaks, DEL and a C1 control are
shown as `\xNN` (two lowercase hex digits), so no rendering of a file shows a line
or row the file does not contain; a TXT line break of any form continues the
value on an indented line (`@3`; `@2` escaped the TXT only).

The review participants (HARNESS.md 6-7) add, within `cpt-studio-report@4`: in the TXT, a REVIEW PARTICIPANTS section
(Corti, Astra and Fable as the assessment read them: vendor, state, run, endpoint, the models requested and returned,
the vendor's request id and response id, usage, the estimated cost, unverified quotes and the refusal or other reason)
and a REFERENCE RETRIEVAL section (per code: the facts the checks read and the verbatim CMS passages retrieved, with
source key, release, section and page, then what is not connected), and on every code a "Proposed by:" line and, on
the numbered items, a "Reference check:" line beside the decision lines, never merged with them; a participant run is
listed in PROVIDER USAGE as an "independent review". The CSV gains two trailing columns, `proposed_by` (names joined by
`;`) and `reference_check` (`passed`, `attention`, `not_verified`); the `decision` column alone carries a member's
decision.

## GET /api/encounters/{id}/original

The original upload's bytes, as an attachment (404 for pasted text).
