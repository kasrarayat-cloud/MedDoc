# CPT Studio JSON API — the frontend contract

Session-authenticated; every POST sends `X-CSRFToken` (read from the
`cptstudio_csrf` cookie). Errors: `{"error": "<message>", "details": {...}}`
with 400 (invalid input), 404 (not found or not in your workspace), 409
(state conflict, e.g. reviewed report not ready), 403 (role cannot review).
Timestamps are ISO-8601 UTC. Text offsets are Python code-point offsets into
`revision.text`.

## GET /api/session

```json
{
  "user": {"id": "uuid", "username": "agent", "label": "CPT Studio review agent (automated agent)",
           "actor_kind": "agent", "initials": "RA"},
  "workspace": {"id": "uuid", "name": "Gastroenterology", "subtitle": "Synthetic demonstration workspace",
                "category": {"slug": "gastroenterology", "name": "Gastroenterology", "profiles_version": "gi-profiles@1"}},
  "role": "reviewer", "can_review": true,
  "counts": {"documents": 7, "queue": 2},
  "synthetic_only": true, "provider_mode": "live", "release": "<git sha>"
}
```

## GET /api/encounters

```json
{"encounters": [{
  "id": "uuid", "title": "Colonoscopy report", "state": "ready_for_review", "state_label": "Ready for review",
  "service_date": "2026-10-21", "families": ["Colonoscopy", "Upper GI endoscopy (EGD, esophagoscopy, enteroscopy)"],
  "source_kind": "pdf", "open_clarifications": 0, "created_at": "..."
}]}
```

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
      "service_date": {"value": "2026-10-21", "origin": "document", "evidence": [{"start": 10, "end": 37, "text": "Date of service: 2026-10-21"}], "note": ""},
      "setting": {"value": "office", "origin": "document", "evidence": [], "note": ""},
      "billing_context": {"value": "not_documented", "origin": "missing", "evidence": [], "note": "..."},
      "patient_status": {"value": "established", "origin": "document", "evidence": [], "note": ""}},
    "user_values": {}},
  "routing": {"version": "gi-routing@1", "document_kind": "procedure_report", "families": [
      {"family": "gi.colonoscopy", "label": "Colonoscopy", "supported": true, "status": "performed",
       "mentions": [{"status": "performed", "section": "procedure", "cues": ["..."], "span": {"start": 0, "end": 0, "text": ""}}],
       "facts": [{"name": "extent", "value": "cecum", "origin": "document", "evidence": [], "note": ""}],
       "missing": []}]},
  "pipeline": {"busy": false, "can_stop": false, "can_resume": false,
               "stages": [{"kind": "extract", "state": "succeeded", "error": "", "finished_at": "..."}]},
  "provider_runs": [{"id": "uuid", "provider": "corti", "mode": "live", "state": "succeeded", "http_status": 200,
                     "latency_ms": 6123.4, "usage": {"creditsConsumed": 0.0281}, "usage_basis": "provider_reported_credits_not_usd",
                     "request_sha256": "...", "response_sha256": "...", "reused_from": null, "error": "",
                     "reconciled": false, "created_at": "..."}],
  "assessment": {
    "id": "uuid", "profiles_version": "gi-profiles@1", "engine_version": "...", "created_at": "...",
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

Proposal `bucket` ∈ selected | alternative | excluded. `status` ∈ ready |
needs_clarification | excluded | informational (alternatives). `decision_state`
∈ undecided | approved | rejected | reinstated. `allowed_actions` is computed by
the server and is the only source of truth for which buttons are enabled.

## POST /api/encounters/{id}/decisions

`{"proposal_id": "uuid", "action": "approve|reject|reinstate|revoke", "note": "", "acknowledgement": "..."}`
Approve requires a non-empty acknowledgement. → `201 {decision}`; 409 when the
action is not allowed for that proposal now.

## POST /api/encounters/{id}/addenda

`{"text": "...", "clarification_id": "uuid|null", "synthetic_attestation": "yes"}` → `201 {"revision_id": "uuid"}`.
Creates a new revision (original text + labelled addendum), invalidates current
decisions, runs the pipeline.

## POST /api/encounters/{id}/context

`{"service_date": "YYYY-MM-DD|''", "setting": "office|hospital_outpatient|asc|inpatient|emergency|telehealth|''",
"billing_context": "professional|facility|''"}` → `201 {"context_id": "uuid"}`. Empty string clears a
user value. Re-assesses; re-predicts only when the provider input changes (service date).

## POST /api/encounters/{id}/stop · /resume · /reconcile

Stop: records an encounter-level Stop; queued stages are cancelled, no further
stage starts and no provider request is sent while it stands. Resume (when
`pipeline.can_resume`): lifts the Stop and re-runs the stage it cancelled, with
the current context. Reconcile: `{"provider_run_id": "uuid", "note": "..."}`
(note 12–2,000 characters) after an `unknown` outcome; allows exactly one new
attempt.

Notes and acknowledgements are at most 2,000 characters (400 beyond that,
never truncated). An addendum is at most 20,000 characters. `revision.addendum_offset`
is the offset where the latest addendum begins (null when the revision is not
an addendum). `proposal.decision` has the same shape as a `decisions.history` entry.

## POST /api/encounters/{id}/reports → GET /api/reports/{id}/download

`{"kind": "draft|reviewed", "fmt": "txt|csv"}` → `201 {"id", "filename", "sha256", "download_url"}`;
409 with `details.blockers` when a reviewed report is not ready. The download
streams the stored bytes as an attachment; its sha256 equals the response's.

## GET /api/encounters/{id}/original

The original upload's bytes, as an attachment (404 for pasted text).
