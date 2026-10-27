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
`counts.queue` in the session counts `needs_clarification`, `ready_for_review`
and `provider_unknown`.
`state_label` is the human label (design vocabulary).

## POST /api/encounters (multipart/form-data)

Fields: `file` (PDF/DOCX/TXT) **or** `text` (pasted note); `title` (optional);
`service_date` (optional `YYYY-MM-DD`, recorded as user-supplied metadata);
`synthetic_attestation=yes` (required). → `201 {"id": "uuid"}`.

## GET /api/encounters/{id}

```json
{
  "id": "uuid", "title": "...", "state": "ready_for_review", "state_label": "Ready for review",
  "created_at": "...", "created_by": "label",
  "permissions": {"can_review": true},
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
      "allowed_actions": ["approve", "reject"]
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
evidence (`reinstatable` false) offers nothing and needs no decision. A reinstated exclusion offers
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
member date conflict's hold. The
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
same reason the encounter view's `second_review.reason` shows). The encounter
view carries `"second_review": {"available": bool, "reason": "...", "items":
["<unresolved item>", ...], "can_request": bool, "run": "uuid" | null}`; `items` is empty when no
documented service is left without a supported proposal. `run` is the id (in
`provider_runs`) of the newest second review made for the answer the current
assessment reads, whatever its outcome, and null when none was: while its
response was not read (unknown, failed, not sent) or not used (refused whole),
the page states that outcome and never says that no CPT codes were proposed. An
assessment never queues a second review (owner decision 2026-10-27).

## POST /api/encounters/{id}/stop · /resume · /reconcile

Stop: records an encounter-level Stop; queued stages are cancelled, no further
stage starts and no provider request is sent while it stands. Resume (when
`pipeline.can_resume`): lifts the Stop and re-runs the stage it cancelled, with
the current context. A stage the system cancelled (it expired in the queue, or
a worker stopped mid-stage) is resumable the same way; `pipeline.stopped_by_member`
is false then, and the stage's `error` records what happened. A predict whose
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
Format `cpt-studio-report@3`: the CSV's `decided_at` is the reviewer's own
decision time; a carried decision also fills `decision_carried_from` and
`decision_carried_at`. A CSV with no proposals has one placeholder row
(`item_list` = `none`) carrying the report kind and SYNTHETIC. In both formats a
C0 control character other than tab and line breaks, DEL and a C1 control are
shown as `\xNN` (two lowercase hex digits), so no rendering of a file shows a line
or row the file does not contain; a TXT line break of any form continues the
value on an indented line (`@3`; `@2` escaped the TXT only).

## GET /api/encounters/{id}/original

The original upload's bytes, as an attachment (404 for pasted text).
