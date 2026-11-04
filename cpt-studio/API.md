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
       "unlisted_codes": 0, "unverified_quotes": 0, "usage": {"creditsConsumed": 0.0281}, "usage_basis": "provider_reported_credits_not_usd",
       "estimated_cost_usd": null, "returned_model": ""},
      {"name": "astra", "label": "Astra", "vendor": "OpenAI", "model": "gpt-6-astra", "state": "refused",
       "detail": "Answered; the reading was not used: the response was cut off at the output limit.", "run_id": "uuid",
       "reused": false, "codes": [], "unverified_quotes": 0, "usage": {"input_tokens": 1200, "output_tokens": 16000},
       "usage_basis": "...", "estimated_cost_usd": "0.8120", "returned_model": "gpt-6-astra"},
      {"name": "fable", "label": "Fable", "vendor": "Anthropic", "model": "claude-fable-5-1", "state": "not_configured",
       "detail": "Not configured on this installation.", "run_id": null, "reused": false, "codes": [],
       "unverified_quotes": 0, "usage": {}, "usage_basis": "", "estimated_cost_usd": null, "returned_model": ""}],
    "reference_validation": {"state": "done", "detail": "", "codes_checked": 2, "passages": 3,
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
      "proposed_by": ["corti", "astra"], "listed_by": [],
      "participant_positions": {"astra": {"position": "proposed", "detail": "Astra proposed this code, quoting the document verbatim.", "quote": "..."},
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
(Corti's: its selected codes), each once - a participant's only when the engine lists it (1 to 10 characters): a longer
"code" may carry wording, a CPT descriptor say, so it is never served (superseded, round 5, shapes-3: 1 to 10
characters is the rule of Corti's row alone, `engine._listable`, I1; a participant's code is listed only in a CPT or
HCPCS code's shape, `engine.participant_listable`, and only with a quote found verbatim in the document,
`review.listed_codes` - one in no code's shape may carry wording, so it is never served and is counted below, and one
in a code's shape none of whose quotes was found is neither listed nor counted: participants.summary says it was listed
with no quote found verbatim in the document, so not proposed), and the row's `detail` ends with the engine's own
sentence ("It returned 1 code that cannot be listed: ... It is not shown and never truncated."); `unlisted_codes`
counts those (0 wherever none was returned) - a participant's as the engine counts them, every entry of its frozen
reading that the engine does not read, re-read when serving (the number its participants.summary states), and `null`,
with no count sentence, where that reading cannot be read again as recorded (refutation round 5, the session's D13: it
counted the assessment's record of the reading, one entry per value, so '45385-59' given twice was 1 beside the
summary's 2) - so the page says the reading proposed no code "that can be listed", never
that it proposed none (refutation round 2, truth-11). Corti's row counts the codes its answers returned that the engine
cannot list - every code of an answer, whatever its role (selected, a candidate, an alternative), read again as the
engine read it: its primary answer as the engine's `provider.unlisted` check counts it, and a bounded second review as
its `provider.second_review` check counts it, only where the engine read that review - so `unlisted_codes` is their
total, and its `detail` then says that only its codes that can be listed were checked, that it proposed no code that
can be listed (beside a code it listed apart, as its Alternatives list shows), or that none of its codes can be listed,
so none was checked, before each answer's own count sentence: "It returned 2 codes that cannot be listed: ..." and
"Its second review returned 1 code that cannot be listed: ...", the numbers those checks say. The reports' REVIEW
PARTICIPANTS says the same (refutation round 3, truth-3: "Answered; its codes were checked." and "It proposed no code."
beside a code it selected that cannot be listed; round 4, truth-4: it counted the selected codes alone, "It returned 1
code" beside the engine's "The provider returned 2 codes" for a candidate it returned too);
`usage` is as the vendor reported it, with its `usage_basis`; `estimated_cost_usd` is a string estimated from published
rates, not reconciled to an invoice, to four decimals (`"0.0270"`, rounded half up), and null for Corti (credits, not
USD), for a run that reported no usage (a reuse), and where the installed pricing module cannot price the usage. A tool
loop is priced exchange by exchange (Astra's long-context rate is a property of one request), and has no estimate when
its recorded exchanges do not add up to its usage, or when an exchange that may have been billed - any not recorded
not sent - reported no usage: an estimate of the others is no estimate of the run (refutation round 2, truth-12: a
loop whose second exchange's read timed out showed exchange 1's price as the run's). The reports' REVIEW PARTICIPANTS
and the trace say which exchange ("not estimated: exchange 2 (outcome unknown) reported no usage and may have been
billed, so the cost of this run cannot be estimated from published rates"); an exchange recorded not sent cost
nothing. `reused` is true when a retained answer to the identical request was reused and nothing was sent.

`harness.reference_validation.state` is `waiting` while processing, `failed` when the current assessment's retrieval
failed, `done` when retrieval ran for it, its traces cover every code a reviewer can decide (selected, or excluded and
reinstatable) and an installed
CMS reference file applied to its service date, `not_verified` when the traces cover those codes but no installed CMS
reference file applied (no service date is established - none documented, or a member's date in conflict with the
document - or none covers it, as `reference_sources[].applies` records), so no code was checked against one, and
`not_run` otherwise (no assessment, one recorded before the harness, or no trace at all - never `done` over zero
codes); `not_connected` is always listed. Only the trace of a code a reviewer can decide is read, the rule the assess
stage traces by, so the state is never `done` with no such code (refutation round 8, retrieval-2: a second review's code
CPT Studio did not add read "Done 1 code checked" where no proposal could be decided on; round 9, retrieval-1: so did a
code excluded with no reinstatement, whose own reference check says none ran). `codes_checked` counts the traced codes only when a CMS
reference file applied (0 for `not_verified`), and `not_verified`'s `detail` says why, in CPT Studio's own sentence: "No code was
checked against the CMS reference files: no service date is established for this encounter, so no dated CMS
reference file applies." or "... no installed CMS reference file applies to the service date, 2025-03-02."
(refutation round 2, truth-3: this was `done`, its codes counted as checked). A retrieval that fails never stops the
assessment, which stands as made (HARNESS.md 5): its retrieval is recorded as one entry `{"code": "", "failed": true,
"notes": ["Reference validation failed: ..."]}` (no fact, no passage), and the state is then `failed` - never
`not_run` or `done` - with that entry's note, CPT Studio's own sentence, as `detail`. It says which step failed: that
CPT Studio could not load the stored CMS reference passages, so the retrieval for the codes did not run (a stored
passage changed after import fails its sha256 check), or that its retrieval for the codes failed; either way no CMS
reference fact or passage is listed (refutation round 4, truth-5: a failed load read "could not record which CMS
reference facts and passages it retrieved", when nothing was retrieved). Then what that leaves of the codes' checks,
by the engine's record of the lookup (`reference_sources[].applies`): where an installed CMS reference file applied to
the service date, that each code's checks, which read the CMS facts before that, stand as shown (refutation round 2,
truth-4: it said no proposal was checked); where none applied, that no code was checked against the CMS reference
files, with `not_verified`'s own reason ("... no service date is established for this encounter, so no dated CMS
reference file applies." or "... no installed CMS reference file applies to the service date, 2025-03-02."; refutation
round 3, truth-1: it said the checks read the CMS facts beside checks that all read "not verified"). A failed entry
that carries no note is served with a sentence that claims neither. `detail` is `""` in every other state, and a failed
entry is counted in neither `codes_checked` nor `passages`. The code cards then say that reference validation failed
for the assessment and that each code's CMS reference checks stand as its status line shows them, and the reports'
REFERENCE RETRIEVAL section prints the entry as one line, "Reference validation failed: ...".
`harness.clarification.open` is how many questions are open on the assessment of the current revision, and `null`
while that revision has none: none was made, or the current assessment - the one `assessment`, `clarifications` and
`open_clarifications` serve - is an earlier revision's, as after an addendum until its revision is first assessed
(refutation round 6, row-1: it was `0` there, and the page's Clarification row said "None open" beside those
questions; the page reads `null` as no assessment of this revision).
`harness.final` is the encounter's state and its label.

Each proposal keeps three statuses apart (I4): `proposed_by` (who proposed it: `corti` for Corti's own proposals and
alternatives, and the participants the engine recorded - for a participant's alternative only those with an entry that
quotes the document verbatim; one that gave its code with no quote found verbatim listed it and did not propose it,
and is served apart in `listed_by`, `[]` on every other proposal, as `support.listed_by` records it: refutation round
5, the session's D12), `reference_check` (`passed`, `attention` or `not_verified`,
from its CMS checks `pfs.presence`, `mue.units` and `pfs.endoscopic_base`; its detail always says that NCCI PTP edits
are not connected) and `decision_state` (a member's). `participant_positions` gives each configured participant's
position on the code in its first reading (the only reading harness@1 makes; harness@2's frozen phase-1 reading) -
`proposed`, `not_proposed`, `advised_not_to_code` (with its reason) or `not_run` (with why) - and the first quote of it
that was found verbatim in the document ('' when none was); it is `{}` when no participant was configured. A
participant that first proposed the code after peer review (its `phases` entry is `peer_review`) keeps its first
reading's position, and its `detail` says both: "Fable did not propose this code in its first reading. It proposed it
after peer review." (refutation round 2, truth-2), in the encounter view and in the trace's reconciliation rows alike.
A first reading that listed the code with no quote found in the document proposed nothing (the engine counts no such
entry), so that participant's position is `not_proposed`, whether or not it then proposed the code after peer review:
"Astra listed this code in its first reading, but none of its quotes was found in the document, so that reading did
not propose it.", and only where it did, "It proposed it after peer review." after it (refutation round 3, truth-2: it
said Astra proposed it in its first reading and "again" after peer review, beside `phases` and the peer row's "never
independent"; round 4, truth-2: where peer review did not propose it, the same frozen reading was `proposed`, "Astra
proposed this code; none of its quotes was found in the document.", beside `proposed_by`).
A position never decides a status, and agreement never approves anything. `retrieval` lists the CMS facts
the checks read for the code and the verbatim CMS passages retrieved for it, with source key, release, page and
section ([] for a proposal no reviewer can decide, which is never traced: an alternative, whoever gave it - a
participant, the provider as a candidate, or the provider's second review, a code it selected that CPT Studio did not
add - and a code excluded with no reinstatement; and never another proposal's trace of the same code: refutation round
8, retrieval-1 to retrieval-3; round 9, retrieval-1).

`pipeline.stages` includes the participants' stages (`kind` `astra`, `fable`), between `predict` and `assess`. Their
requests carry the revision alone (no date), so a context change that leaves Corti's request as it is re-assesses with
the participants' answers as they are, and one that re-predicts reuses them; a configured participant with no recorded
outcome for the revision (its stage was stopped, expired or swept before it recorded one, or it was configured since)
gets its turn at such a context change, its stage running before the assess. While a member date conflict is held
nothing is sent, the participants' requests included (their rows say so), and settling the date gives them their turn.
`provider_runs` lists the participants' runs too (`purpose` `independent`); a participant run replayed from a
recording reads `mode` `replay`. Each provider run also carries `requested_model` and `returned_model` (`""` for Corti,
whose API takes no model identifier), which the Activity tab names. The Activity tab names a participant's attempts:
"Astra request started", "Astra response recorded", "Fable request failed (HTTP 529)", "Retained Astra result reused
(no new request)", "Unknown Astra outcome reconciled"; Corti's read as before.

### harness@2: phases, peer reviews, references, candidates and confirmations (HARNESS.md 11-12)

```json
{
  "permissions": {"can_review": true, "is_owner": false, "can_confirm": false},
  "harness": {"phase": 2, "participants": [{"name": "astra", "...": "the harness@1 row as above",
      "peer": {"state": "done", "detail": "Answered in peer review, after its first reading was frozen; the review was used.",
               "run_id": "uuid", "codes_added": ["45381"], "unverified_quotes": 0},
      "references": {"retrieved": [{"ref": "fact:cms-pfs-rvu26d:45385:mult_proc", "kind": "fact",
                                    "source_key": "cms-pfs-rvu26d", "release": "RVU26D", "effective_start": "2026-10-01",
                                    "effective_end": "2026-12-31", "tool": "cms_code_facts"}],
                     "used": [{"ref": "fact:cms-pfs-rvu26d:45385:mult_proc", "use": "...", "retrieved": true},
                              {"ref": "a value of 17 characters (not shown)", "use": "...", "retrieved": false}]},
      "peer_references": {"retrieved": [], "used": []}}]},
  "clarifications": [{"id": "uuid", "scope": "proposal", "fact": "extent", "...": "as above",
      "candidates": [{"id": "16 hex", "clarification_id": "uuid", "fact": "extent", "value": "cecum",
                      "located_by": ["astra", "fable"], "phase": "independent",
                      "phases": {"astra": "independent", "fable": "peer_review"}, "runs": ["uuid", "uuid"],
                      "spans": [{"start": 207, "end": 249, "text": "The colonoscope was advanced to the cecum.", "page": 1}],
                      "sentences": [{"start": 196, "end": 249,
                                     "text": "Technique: The colonoscope was advanced to the cecum."}],
                      "verified": false,
                      "why": "CPT Studio does not check what a participant's passage states, and this release offers no confirmation.",
                      "attestation": ""}],
      "confirmation": null}],
  "confirmations": [{"id": "uuid", "clarification_id": "uuid", "scope": "proposal", "fact": "extent",
                     "family": "gi.colonoscopy", "proposal_key": "sel:0", "value": "cecum", "spans": [...],
                     "located_by": ["astra", "fable"], "runs": ["uuid"], "confirmed_by": "label",
                     "confirmed_by_kind": "human", "attestation": "I read this passage ...", "created_at": "...",
                     "revision_number": 1, "current_effect": {"state": "read", "detail": "read by this assessment"}}],
  "assessment": {"proposals": [{"...": "as above", "phases": {"fable": "peer_review"}, "confirmed": ["uuid"],
                                "corti_relation": "none"}]}
}
```

`harness.phase` is `0` when no model participant (Astra, Fable) was configured for the current assessment (its
record is harness@1's "not configured", I1), `2` once an assessment records their peer reviews (assess #2 and its
re-assessments) and `1` before that; with no assessment yet it is `1` when a participant is configured. Each Astra and
Fable row gains `peer`: `{}` before phase 2 (and on Corti's row and a row not configured); `waiting`, `running` or
`stopped` while the current chain has not finished that participant's peer stage (`astra_peer`, then `fable_peer`);
once assess #2 is recorded, its `state` in the row vocabulary (`done`, `refused`, `failed`, `unknown`, `not_sent`,
`blocked`, `not_configured`) with a `detail` sentence, its `run_id`, the codes the review proposed after peer review
(`codes_added`, never independent) and its unverified quotes. `codes_added` lists only the additional codes the
participant first proposed in its peer review - the phase the engine records on the assessment's proposals of the code
(`phases`), or, for a code no proposal records it on, "whether its frozen first reading listed the code" (superseded,
round 5, the session's D12: read only from its entries that located a quote, as the engine's `phases` are - its first
reading's located quote, else its peer review's - so a code no entry of either phase located is neither added nor
repeated: it was listed in peer review) (`serializers.peer_code_phases`); an additional code its first reading
proposed is named in the `detail` instead ("It
listed 45385 again in peer review; it first proposed it in its independent reading."), never as proposed after peer
review (refutation round 2, truth-8). A final assessment of phase 1 - one that owes no peer
stage because a member date conflict holds it, or because the participant is not configured now - serves, for each
participant whose first reading it read, `not_sent` with why it read none ("Peer review: none is read by this
assessment: the service date entered as encounter metadata conflicts with the document, and no peer review is sent
while that question is open." or "Peer review: none follows this assessment: Astra is not configured on this
installation now."), `run_id` null, whatever peer-review runs the revision holds from an earlier chain (refutation round
2, truth-9); an assess #1 whose peer stages are owed still serves `{}`, and the page then says only that this assessment
read no peer review. The three kinds of references are never merged (11.2):
`references` are those of the row's first-reading run and `peer_references` those of its peer-review run - in each,
`retrieved` lists every ref that run's own tool calls returned (a `fact:<source>:<code>:<field>` ref or a passage key,
with the source, release and effective window its tool result stated - read by the CMS tool executor's own reader of a
stored result - '' where it stated none, and the tool; a run that reused a retained answer has the tool calls of the
run it reused, which answered for it, and says so: its block alone carries `reused_from`, that retained run's id, and
the page and the reports say these references were retrieved by the retained run's tool calls, never by its own
(refutation round 2, truth-13); a tool call whose result the participant was never sent - the loop ended after
CPT Studio answered it, its next exchange not sent or never made (a member's Stop, a follow-up it could not build, the
deadline) - is not listed: refutation round 2, sends-r2-3; the trace's `exchanges` keep every tool call CPT Studio
answered), and `used` every reference the run's answer says it relied on, with `retrieved`
CPT Studio's check against that same run's tool results, as the reader recorded it (`retrieved: false` is a reference
cited but never retrieved, never shown as retrieved; one participant's or phase's retrieval never counts for
another's). A used `ref` is served as given only when `retrieved` is true (CPT Studio's own identifier); any other is
the participant's own text, served only as a short id of letters and digits (at most 8 characters) or by its length,
`"a value of 17 characters (not shown)"` (`serializers.shown_used`, `participants.peer.shown_reference`; refutation
round 4, shapes-3: a ref written as a hyphenated CPT descriptor was served as written).
`harness.reference_validation` stays the reconciliation's retrieval only. The phase, each run's reading and
peer review and these references are read by the pipeline's own functions (studio/jobs.py), so the page states exactly
what the assessments read.

Each clarification gains `candidates` and `confirmation`. Only an OPEN question of the final assessment has candidates
(an assess #1 whose peer stages follow has none, and neither has a Corti-only encounter, nor any encounter while no
model participant is configured, when no assessment would read a confirmation), and only while that assessment was
made on the encounter's current revision and context (refutation round 2, truth-10: after a member's context change
no re-assessment would read a confirmation of it, so none is offered). The final assessment is the pipeline's
own: assess #2 and its re-assessments, or an assess #1 that owes no peer stage - no participant's first reading was
read, or a member date conflict holds the encounter, while which nothing is sent: the answers the frozen
phase-1 readings and the peer answers of the runs that assessment read offer for it (HARNESS.md 12.5) - the service
date, a proposal's performed status, the extent, the structure examined, the cannulation outcome, the E/M basis; never
another fact. `value` is in CPT Studio's own words (a `YYYY-MM-DD` date; `performed`, `not performed`, `cancelled`,
`planned`, `historical`; routing's landmark or EUS structure label; `successful` or `failed`; `time`, `mdm`,
`time+mdm`), never the participant's wording, and `''` when the participant's value cannot be stated so. `spans` are
exact slices of `revision.text` (offsets as everywhere) with their page. A candidate is `verified` only when its quote
was located verbatim, at most 8 spans, none across a page break and none in a history, plan or indication section,
and the fact's consistency check passes (refutation round 2, HARNESS.md 12.5): the passage states that date, never as
a date of birth; names that landmark or structure, which CPT Studio's readers read neither as not reached or not seen
nor as qualified by a negation, an attempt or a doubt; states that cannulation outcome; states a total time in minutes
or an MDM level; for a status, CPT Studio's readers - the documented-service inventory the assessment recorded - read
the passage's whole sentence as stating exactly that status for the act the proposal's code accounts for (or, for a
base code, an E/M or another family's profile, its service). Otherwise `why` says which check failed ("The passage
does not name the snare removal.", "The passage leaves the forceps biopsy in doubt."). `sentences` gives, for each span
in its order, `{start, end, text}` of the readers' whole sentence it lies in, so the page shows a span that is a slice
of a longer sentence with that sentence.
Agreement never verifies: identical (value, spans) from several participants merge into one candidate naming all of
them (`located_by`, `runs`), and `phase` is `independent` when any located it in its frozen first reading,
`peer_review` only when all did so after peer review (`phases` names each). `id` is stable for the same rows.
`attestation` is the exact sentence a confirmation of a verified candidate must carry (`''` when unverified): the
page sends it as served, as it sends a decision's acknowledgement from `GET /api/session`.
`confirmation` is the question's FindingConfirmation, or null. `confirmations` lists every confirmation of the current
revision, oldest first, also after its question has gone (a re-assessment that read it raises it no more).
`permissions.can_confirm` is `can_review`.

**This release offers no reviewer confirmation (refutation round 3, D7; HARNESS.md 12.10).** Candidates are served as
above - each participant's passage located for the question, exact slices of `revision.text` with their `sentences`
and pages, `located_by`, `phase`, `phases` and `runs` - but unchecked: no check that decides `verified` runs for the
response, so every candidate is `verified` false, with the one `why` "CPT Studio does not check what a participant's
passage states, and this release offers no confirmation." and `attestation` `''`; a source that cites no passage, or
whose passage is not located as exact slices of the text, is not served. `permissions.can_confirm` is false for every
member. No confirmation can be recorded, so `confirmation` is null and `confirmations` lists none; a row that exists
anyway is listed as recorded, and no assessment reads it (`current_effect` `not_read`). What this section says above of
`verified`, `why`, `attestation`, the checks and `can_confirm` describes the dormant confirmation path behind the
code-level setting `STUDIO_OFFER_CONFIRMATIONS` (off; no environment variable or installer file changes it), kept as
written.

**Amended after refutation round 4 (the session's D8; HARNESS.md 12.10): no candidate is served.** The paragraph above
is kept so the change can be seen. A served candidate's `value` was never a participant's answer to the question: it is
CPT Studio's own inference from a reading - a service's status or extent paired with every quote of that service, an
E/M basis CPT Studio's own reader read in the passage (which also chose the passages served) - and the page drew it as
the participant's answer. Now every clarification's `candidates` is `[]` for every member while confirmations are not
offered, and on the dormant path candidates are served only to a member who may confirm one (`permissions.can_confirm`
true); no `why` "CPT Studio does not check what a participant's passage states, ..." is served any more. A
participant's own answers to the open questions stay in its peer review: the owner's trace shows each in its own words,
and the reports' PEER REVIEW lists each "with its value in CPT Studio's words" (superseded, round 5: the session's D10 -
that value was CPT Studio's own reading of the participant's words, which printed 'Cannulation of the bile duct was not
successful.' as "successful"; each answer is now listed only by whether it is read as settling the question, with the
passages it located, and no value is printed).

Each confirmation's `current_effect` is what the current assessment made of it, in the words the reports' CONFIRMED
FINDINGS print as "Effect:" - one reading, `review.confirmation_effect` (refutation round 2, truth-5: the page said
every confirmation of a fact other than the date was read): `{"state": "read" | "not_read", "detail": "..."}`. A
service date is `read` when the assessment's context carries it ("entered as the member's service date through the
encounter context; this assessment's context carries it"; otherwise "... does not carry it (made before it, or with
another member date)"). Any other fact is `read` ("read by this assessment") when the assessment's record lists it
among those it read (`assessment.completeness.confirmations.applied`) or a proposal's checks read it (`confirmed`),
and otherwise `not_read`, with why: "not read by this assessment: <the reason it recorded>" (`ignored`), "not read by
this assessment, which was made before it", or "not read by this assessment, which records no reading of it"; with no
assessment of its revision current, "not read: no assessment of its revision is current". The confirm endpoint's
response carries it too: the assessment it was made on was made before it.

`assessment.completeness.confirmations`, on an assessment that read the revision's confirmations (a model participant
configured, and any confirmation recorded), is the engine's own record of them: `applied` - each answer it read, `{ids,
scope, family, proposal_key, code, fact, value, spans}` - and `ignored` - each confirmation it did not read, `{id,
why}`, why in CPT Studio's own words: it does not name the proposal it was made for (its code and the identity of its
reading: unbound); the proposal it was made for is not in this assessment (moved) or is in it more than once; its
passage is shorter than any quote CPT Studio locates (fewer than 8 non-space characters); CPT Studio cannot place its
value on its readers' own scale (an extent's landmark, a cannulation's outcome); it answers no question this assessment
asks; confirmations of the same question disagree; or it is malformed (its passage no exact slice of this revision's
text, no value, no locating participant, no reviewer). The encounter checks say the same: `confirmations.applied`
(`info`) lists what was read, and `confirmations.ignored` (`warn`) what was not, with why. A proposal's question is
bound to the proposal it was made for through `support.identity`: recorded on every decidable proposal while a model
participant is configured (with none, the record is harness@1's), it is the sha256 of the proposal's own reading - its
code, family, profile version, cited passages, units and the context values its decision depends on: its fingerprint
without its checks and status, which the other proposals and the confirmations move (HARNESS.md 12.5, refutation round
1, EV-1). The engine reads a confirmation only for the one proposal with that code and identity, wherever its key now
is, and the confirm endpoint refuses (409) a question whose proposal records none.

Each proposal gains `phases` (from its support record: the phase each participant first proposed the code in; a code
first proposed in peer review is `peer_review`, never independent) and `confirmed` (the ids of the confirmations its
checks read). Its `rationale` and `proposed_by` keep the origin (11.4: "Proposed by Fable; Corti did not propose this
code.") (superseded, refutation round 6: the session's D14 - a code only the participants proposed is never a proposal
now; it is served as an alternative of `support.origin` `participant`, `allowed_actions` `[]`, whose
`exclusion_reason` names who proposed it and why it is not added: its scope or evidence reason where one applies,
otherwise CPT Studio's own, "... but not added as a proposal: a quote found verbatim in the document does not by itself
show that the coded act was done at this encounter, and in this release a participant's code is never added as a
proposal of its own. Alternatives cannot be approved."). Every proposal carries
`corti_relation` (refutation round 2, truth-6), how Corti stands to its code, read from
the assessment's own proposals of that code (Corti's are those of origin primary or second_review): `proposer` (Corti
is among `proposed_by`); `selected_without_exact_passage` (Corti's response selected the code and that selection is
excluded because none of its passages matches the document text exactly: listed apart, carrying no proposal);
`selected_apart` (Corti selected it and that selection is another entry, excluded for another reason: out of scope,
beside a participant's own entry of the code, which is then an alternative); `candidate` (Corti's response listed it
without selecting it: a candidate, or an alternative to a code it selected - the token names no role); `second_review`
(only Corti's bounded second review listed it, without adding it as a proposal: a code it selected and did not add, or
a candidate or an alternative of it); `none` (Corti has no entry for the code). The page says "Corti did not propose
this code." only for `none`, words the others as the engine's rationale does ("Corti also selected this code, with no
exact passage; it is listed apart, excluded."; "Corti listed this code as a candidate or an alternative, not selected;
see Alternatives."; "Corti's second review also listed this code without adding it as a proposal; see Alternatives.":
the engine is told which codes Corti listed, not the role, so neither names one, and the code's Alternatives row says
which - refutation round 3, truth-5: an alternative to another code was said to be listed "only as a candidate"), and
says nothing of Corti for a proposal served without the field. A candidate, a confirmation and a
peer position never decide a status or approve anything: `decision_state`
stays a member's decision (I2-I4). `pipeline.stages` includes the peer stages (`astra_peer`, `fable_peer`); a
replayed peer-review run reads `mode` `replay`. The Activity tab reads "Finding confirmed from a participant's located
passage (not a decision)" for a confirmation, with its `fact` and `effect`.

## POST /api/encounters/{id}/clarifications/{clarification_id}/confirm

**In this release every request is refused (refutation round 3, D7; HARNESS.md 12.10).** After the session (401) and the
encounter's workspace scoping (404 outside the caller's workspaces), before the body, the member's role, the question or
the candidate is read: `409 {"error": "This release offers no reviewer confirmation of a candidate answer, so nothing
was recorded; a question is answered with an addendum, or a date of service in the encounter context.", "details": {}}`.
Nothing is recorded: no confirmation, audit event, context, job or provider request. What follows describes the dormant
path behind `STUDIO_OFFER_CONFIRMATIONS`, kept as written. **Amended after refutation round 4 (d7-3; HARNESS.md
12.10):** the error is `"This release offers no reviewer confirmation, so nothing was recorded."` - it says only what
happened. The sentence above named an addendum or the encounter context as the way a question is answered, which is
false for a documented conflict or an included base code (an addendum leaves them open) and for a member's setting
(only the context corrects it); it is kept so the change can be seen.

`{"candidate_id": "16 hex", "attestation": "I read this passage in the source document; it documents <value> for this
encounter."}` → `201 {confirmation, "effect": "context" | "reassessment"}` (the confirmation as in `confirmations`).
A reviewer's confirmation of one verified candidate answer to an open question (HARNESS.md 11.3, 12.5): an owner or
reviewer only (403); a question of another document or workspace is 404; a `candidate_id` that is not 16 lowercase
hex, or an attestation that is not a JSON string, is 400; under the encounter's row lock the question must be open on
the current revision's final assessment and not confirmed yet, nothing may be queued or running, and the candidate
must be one of that question's VERIFIED candidates, recomputed by the server (409 with why: an earlier assessment's
question, an assessment of an earlier context - "The encounter context changed after this assessment; resume
processing and confirm on its new assessment." -, peer reviews not finished, not open, confirmed already, processing,
not one of its candidates, not verified);
the attestation must be exactly the sentence above with the candidate's `value` (400 otherwise, naming the sentence).
The immutable confirmation (the question, the revision, scope, fact, family, proposal key, value, the exact spans, the
participants that located it, their runs, the reviewer and the attestation) and an audit event `finding.confirmed`
(ids and names, never the value) are recorded. A service date then enters as the member's date through the context
path (`effect` `context`, exactly as `POST context` with that `service_date`: every date safeguard applies, the
context's own audit row is recorded, and a context change's 409s apply); every other fact is read by one re-assessment
(`effect` `reassessment`), which labels it "confirmed from <participant>'s located passage by <reviewer>". Either
refusing leaves nothing recorded. Nothing is approved; a new revision's assessments never read a confirmation.

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
                      "proposed_by": ["corti", "astra"], "listed_by": [], "positions": {...}, "reference_check": {...},
                      "approved": false}]
}
```

harness@2 adds to each run `exchanges` - each HTTP exchange of a participant's tool loop (`turn`, `state`,
`http_status`, `latency_ms`, `usage`, `request_sha256`, `response_sha256`, `provider_request_id`, `response_id`,
`error`) with its `tool_calls` (`call_id`, `tool`, `arguments`, `refs`, `result_sha256`, `executed_at`; [] for Corti's
runs). `tool` and `arguments` are what the participant wrote, served only in the tools' own shapes (refutation
round 4, shapes-4: `participants.peer.shown_tool`, `shown_arguments`): `tool` as given only when it is one of CPT
Studio's tools (`cms_code_facts`, `cms_policy_passages`), and `arguments` as an object of the tools' fields with each
of `codes` in a CPT or HCPCS code's shape, `date_of_service` as YYYY-MM-DD or `""` and `topic` one of the policy
topics; any other value, field or argument text is named by its length (`"a value of 33 characters (not shown)"`).
`arguments` is `null` when they were missing or null (refutation round 2, sends-r2-1), and each exchange is recorded
as it ends, so a run still sending, or swept to unknown, can list exchanges
(sends-r2-4). Then `review`, a peer-review run's PeerReview as JSON (its answers, positions, additional codes, references
used checked against its own tool calls, the frozen inputs it was shown and its problems; null for every other run, whose
`reading` it is instead). Each of its `additional_codes` carries `phase`, the phase its participant first proposed the
code in (`independent` or `peer_review`), where the current assessment read that review, and "`''` otherwise" (truth-8;
superseded, round 6: where that review was read, an entry none of whose quotes was located is never `peer_review` -
each entry is worded by its own quotes, account-4 - so `''` is said of such an entry where the participant first
proposed the code in its peer review, as it is of a code no entry of either phase located, D12, and of a code in no
code's shape, while `independent` stays on every entry of a code its frozen first reading proposed; where the current
assessment did not read that review, every additional code carries `null`, account-5, which the page words "not read by
the current assessment", never "listed in peer review"). `reading.references_used` checks each reference against that run's own tool results; for a
run that reused a retained answer (`reused_from`), against the retained run's, and each of its references used then
carries `reused_from` too (refutation round 2, truth-13). The
trace also lists `assessments`: each assessment of the current revision, oldest first, with `current`, its `phase`,
whether it is its chain's `final` assessment, and the `frozen` list it recorded (`[[input name, sha256], ...]`: Corti's
response, each model participant's reading, the revision text; [] before harness@2).

`participants` lists Corti, Astra and Fable, each with its runs of the current revision (Corti's second reviews
included). `response_bytes` is the size of the raw response kept. `reading` is a participant run's full normalized
reading, read again from the stored bytes as the adapter version that recorded it - each quote with the spans it was
found at, or with the reason it was not (an unverified quote, never evidence) - and null for Corti's runs and for a run
with no answer; a stored answer that no longer matches its sha256 reads `{"refused": true, "problems": ["..."], ...}`.
A code, modifier or service id a participant wrote (a reading's codes, not-coded items, services and questions, a peer
review's additional codes and positions) is served as given only in its strict shape (HARNESS.md 12.4: a code in a CPT
or HCPCS code's shape, a modifier as two capital letters or digits, a service id as letters and digits of at most 8
characters); any other is named by its length, as the reader's own problems name it: `"a value of 106 characters (not
shown)"` (I9: such a field may carry a CPT descriptor), and a service id so withheld under a name of CPT Studio's own,
`"id 2: a value of 7 characters (not shown)"`, which is the same for all of the participant's runs in the trace - its
reading's and its peer review's (refutation round 4, shapes-2, truth-3). Each reference a run used
(`reading.references_used`, `review.references_used`) is served as `harness.participants[].references.used` serves it
(shapes-3). Free text (a basis, a question, a description) is served for the page, which withholds what reads like a
descriptor.
`retrieval` is the current assessment's retrieval traces as recorded; a retrieval that failed is its one entry marked
`"failed": true`, with no code, which the page shows as "Reference validation failed" with its note, never as a code
with nothing found. `reconciliation` keeps proposed (`proposed_by`, with `listed_by` apart: refutation round 5, D12,
`positions`), reference-checked (`reference_check`) and approved (`approved`: the member's current decision is an
approval) apart.

## POST /api/encounters/{id}/decisions

`{"proposal_id": "uuid", "action": "approve|reject|reinstate|confirm|revoke", "note": "", "acknowledgement": "..."}`
Approve requires the acknowledgement to be exactly the current attestation
for the reviewer's actor kind (`acknowledgement` in `GET /api/session`;
surrounding whitespace is ignored); any other text, or none, answers 400, so a page
loaded before the attestation changed is told to reload. → `201 {decision}`; 400 when the
action is not one of the five (any other text, none, or not a string); 409 when the
action is not allowed for that proposal now. harness@2 (HARNESS.md 12.1): a decision
is recorded on its chain's final assessment only - while the current assessment is an
assess #1 whose peer stages are owed, every proposal's `allowed_actions` is `[]`, a
decision answers 409 "The peer reviews of this document have not finished: a decision
is recorded on its final assessment.", and `readiness.blockers` lists "The peer reviews
have not finished: decisions are recorded on the final assessment". Decisions carry
between final assessments only: persisting such an assess #1 neither carries nor
invalidates one, and the next final assessment carries (or invalidates, with its reason)
each current decision of the assessment that holds them; a new revision invalidates them
there. A documentation check's exclusion
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

harness@2 (HARNESS.md 12.6) adds, still within `cpt-studio-report@4` and only when a model participant took part in
the assessment (a Corti-only report - its snapshot, digest, TXT and CSV - is harness@1's exactly): in the TXT, CONFIRMED
FINDINGS after OPEN CLARIFICATIONS (each reviewer-confirmed finding of the revision: the fact and value, its subject,
who confirmed it and when, the confirmation and question ids, its passage with offsets and page, the participants that
located it, the attestation, and what became of it - the service date through the encounter context, any other fact
read by the assessment or not, with why), and after REVIEW PARTICIPANTS a PEER REVIEW section (each participant's peer
review: its state and run, the frozen inputs it was shown, its answers to CPT Studio's questions "with the value in CPT
Studio's own words" (superseded, round 5, D10: each only by whether it is read as settling the question, "Astra says
the document settles it" or "Astra's answer is read as not settling it", with no value), its positions on codes and the
codes it proposed
"after peer review, never independent" (superseded, round 6, account-4: its additional codes, each worded by its phase
and its own quotes - "proposed after peer review, never independent" of an entry with a located passage of a code
the participant first proposed in its peer review, "repeated in peer review; first proposed in its independent
reading" of every entry of a code its frozen first reading proposed, and otherwise "listed in peer review"), each with
its located passages; a phase-1 report says whether peer reviews follow, by the pipeline's rule, and why none does:
no first reading was read, a member date conflict holds the encounter, or no participant that read is configured now)
and a PARTICIPANT REFERENCES section (by
participant and phase, what that run's own tool calls retrieved and what it says it used, "cited, not retrieved" where
its own run never returned it) - apart from REFERENCE RETRIEVAL, which stays the reconciliation's. REVIEW PARTICIPANTS
gives a tool loop's exchanges and tool calls - for a run that reused a retained answer, its own (none) and then those of
the retained run, named as that run's ("Exchanges: 0 · tool calls: 0 (this run reuses the retained answer of run
<id>, which made 2 exchanges and 1 tool call)"; refutation round 3, truth-4: the retained run's were printed as the
reuse's own) - and PROVIDER USAGE lists a peer-review run as a "peer review". No
participant's own wording is printed: questions are CPT Studio's, "values CPT Studio's words" (superseded, round 5, D10:
no peer answer's value is printed), passages the revision's
own slices, codes and references only in their shapes. The CSV keeps its columns and adds rows that are not proposals,
after the encounter rows: `confirmed_finding` (fact in `status`, value in `exclusion_reason`, passages in `evidence`,
the locating participants in `proposed_by`, the reviewer in `reviewer`/`reviewer_kind`/`decided_at`, the attestation
in `evidence_support`, `confirmation=<id>;clarification=<id>;scope=<scope>` in `checks`), `peer_answer` (`settled` or
`not_settled`, "the value" (superseded, round 5, D10: no value, so `exclusion_reason` stays empty), passages,
`question=<id>;fact=<fact>`), `peer_position` (code, position, passages),
`peer_additional_code` (code, units, "`proposed_after_peer_review`" (superseded, round 6, account-2: the status the
TXT's wording of the entry gives - `proposed_after_peer_review` where the entry located a passage of a code the
participant first proposed in its peer review, `repeated_in_peer_review` where its frozen first reading proposed the
code (round 2, truth-8), and otherwise `listed_in_peer_review`: the entry proposed nothing, because no entry of either
phase located the code (round 5, D12), because the entry itself located no passage (round 6, account-4), or because
the code is in no code's shape), passages) and `participant_reference` (`retrieved`,
`used` or `cited_not_retrieved`, the ref in `exclusion_reason`, the source in `documented_service`, kind, release and
window in `evidence_support`, `run=<id>` in `checks`, and `run=<id>;reused_from=<id>` for a run that reused a
retained answer, whose tool calls they are: PARTICIPANT REFERENCES says the same of that run, "reuses the retained
answer of run <id>, whose tool calls these are; this run made none", and of each reference it used, "retrieved by the
retained run it reuses"); each names its participant in `proposed_by` and its phase in `proposal_origin` - the row's
participant and phase, not a proposer: the entry a `listed_in_peer_review` row records proposed nothing, as its status
says, whoever it names (refutation round 6, account-2) - and none
carries a `decision`. **Amended after refutation round 4 (d7-4; HARNESS.md 12.10):** CONFIRMED FINDINGS and the
`confirmed_finding` rows are printed only while confirmations are offered; this release offers none, so neither appears
(the section's "None: no reviewer has confirmed a finding for this revision." implied a reviewer could).

## GET /api/encounters/{id}/original

The original upload's bytes, as an attachment (404 for pasted text).

## Core repair and customer interface (2026-11-03): P3 REVIEW

**`POST /api/encounters/{id}/decisions` takes `"modifiers"`**: `[]` (or absent, or `null`), `["59"]` or `["XS"]` - the
reviewer's ONE chosen modifier, on an `approve` only, where the proposal's separate-lesion modifier review offers it
(`review.effective_view`, below). 400 for any other shape or value (`["59", "XS"]`, `"XS"`, `["xs"]`, a modifier with
another action); 409 "No modifier review is offered for <code>: approve it with no modifier." where none is offered.
Approving with no modifier is always allowed. → `201 {decision, "modifiers": [...]}`. Nothing is prefilled.

**Statuses, checks and actions are the review overlay's** (`studio/validation/review_view.py`, ARCHITECTURE.md's section
of the same name): in `assessment.proposals[]`, `status`, `status_label`, `checks`, `allowed_actions` and
`approve_withheld_by` are what the current decisions (and member answers) leave. After a reinstatement of 45385 beside a
selected 45378, 45378 reads `needs_clarification`, its checks carry `services.base_included`, `allowed_actions` is
`["reject"]` and `approve_withheld_by` is `"services.base_included"`. With no decision they are exactly the stored ones;
the key set is unchanged. `readiness.blockers` can list "<base> was approved, but <code> was reinstated: its diagnostic
examination is normally included in that intervention; revoke one of the decisions" and "<code> was approved with
modifier XS, but the separate-lesion modifier review no longer applies to it; revoke the approval and decide it again".
Reports: an approval's chosen modifier is printed under its decision ("Modifier chosen by the reviewer: XS (not
validated against NCCI procedure-to-procedure edits or payer modifier policy)"), and CHECKS notes the checks recomputed
over the current review decisions. The structured modifier review, the chosen modifier and the approved items are served
to the customer by the customer API (package P4), from `review.effective_view(assessment)` and
`review.approved_items(assessment)`.

## Core repair and customer interface (2026-11-03): P4 CUSTOMER-API

**This section supersedes the customer-facing shapes above where they differ** (CORE-UX-DESIGN.md 5, 7). The sections
above describe the full serializer, which is now the **operator** serializer: served only under `/ops/api/` to platform
operators. A workspace member - owner, reviewer or viewer - is served the customer contract, built by allowlist in
`studio/customer_api.py`: every key is written out, nothing stored is passed through, and no provider or model name,
usage, credit, request id, run id, hash, rule id, source key, trace link or engine sentence appears.

**Customer endpoints (`/api/`).**

- `GET /api/session` → `{user: {id, label, initials, actor_kind}, workspace: {id, name}, role, can_review,
  acknowledgement, counts: {documents, queue}, synthetic_only}` (no `provider_mode`, no `release`).
- `GET /api/encounters` → `{encounters: [{id, title, state, state_label, service_date, date_conflict, open_details,
  created_at, kind}]}`.
- `GET /api/encounters/{id}` → exactly the contract of CORE-UX-DESIGN.md 7: `id, title, created_at, updated_at, state,
  state_label, permissions{can_review}, document{kind, name, media_type, size, page_count, revision, text, pages,
  reading{status, label, messages}, original_url}, service_date{value, source, document_value, document_quote,
  entered_value, conflict, can_use_document_date}, progress{phase, busy, steps[{key, label, state, started_at,
  finished_at}], active_detail, started_at, finished_at, server_time, slow, message, can_stop, can_resume, can_leave,
  error}, checks[{key, label, state}], codes[{id, number, code, units, modifiers, modifier_review, status,
  status_label, sub_label, summary, why{quotes[{text, start, end, page, exact}], qualifications}, detail_ids,
  allowed_actions, decision}], other_codes[{code, reason}], not_separately_coded[{label, reason}], details_needed[...],
  unresolved, limitations, readiness{draft, approved, blockers}, reports[{id, kind, fmt, filename, generated_at,
  generated_by, download_url, current}], activity[{event, summary, actor, actor_kind, at}]`. States: `processing,
  action_needed, awaiting_detail, ready, reviewed, no_codes, stopped, failed, being_confirmed`; code statuses `ready,
  needs_detail, approved, excluded`. `activity` lists only allowlisted events under customer keys (`document_added`,
  `decision_recorded`, `report_created`, ...); provider events, operator reads and operator reports never appear.
  Committed examples: `tests/fixtures/customer/*.json` (generated from the real serializer).
- `POST /api/encounters/{id}/decisions` → `201 {proposal_id, code, decision{action, by, by_kind, at, note,
  modifiers}}`.
- `POST /api/encounters/{id}/resume` → `201 {"resumed": true}` (never the stage's kind).
- `POST /api/encounters/{id}/reports` `{"kind": "draft"|"approved", "fmt": "txt"|"csv"}` ("reviewed" is read as
  "approved") → `201 {id, kind, fmt, filename, generated_at, generated_by, download_url, current}`; the approved
  export answers 409 with `details.blockers` (customer wording) until `readiness.approved`. Format
  `cpt-studio-customer-report@1`: the draft lists the numbered suggested codes ("Suggested codes — not approved") with
  status, units, decided modifiers, one sentence of CPT Studio's own reading and the exact quotations with their page;
  the approved export lists the approved items only, each with units, modifiers, approver, "Agent-executed synthetic
  review — not clinical approval" for an agent's approval, the decision time and its quotations with page and character
  offsets; then the limitations; a SYNTHETIC banner opens and closes the file. CSV columns: `report_format,
  encounter_title, date_of_service, number, code, units, modifiers, status, approved_by, approver_kind, approved_at,
  summary, evidence_text, evidence_page, evidence_start, evidence_end` (one row per quotation of a code; a banner row,
  `report_format` = the SYNTHETIC line, follows the header and ends the file; formula-leading cells neutralised).
- `GET /api/reports/{id}/download` → a customer artifact of the caller's workspace as stored, **without**
  `X-Content-SHA256`. Any other artifact (an operator report, or one recorded before the `audience` column existed:
  they name the review participants) answers 404; an approved export whose snapshot no longer matches the persisted
  decisions answers `409 {"error": "This export no longer matches the saved decisions; create a new one."}`. Stored
  artifacts are never modified.
- `GET /api/encounters/{id}/original` → the original as stored, without `X-Content-SHA256`.
- **Removed:** `GET /api/encounters/{id}/trace` and `POST /api/encounters/{id}/reconcile` answer 404 for everyone.
- **Errors** use a fixed customer vocabulary (`customer_api.customer_error`): a refusal raised below the API is passed
  through only when it is a known customer sentence, re-worded when it names the machinery, and otherwise answered
  "This action is not available right now." No stored or exception text reaches a member.

**Operator diagnostics (`/ops/`).** Every URL answers anyone without a platform-operator grant exactly what an unknown
URL answers (Django's 404) - signed out, any workspace role, any workspace's owner, a revoked operator. A grant is a
user-level row (`OperatorGrant`, ended by an `OperatorRevocation`) recorded only by `manage.py grant_operator
--username U --reason-file F` and `revoke_operator ...`; no role confers it and no URL records one. An operator with no
membership signs in on the same login page and lands on `/ops/`.

| method + path | serves |
|---|---|
| `GET /ops/` | the operator console (`templates/studio/ops.html`, one script `/ops/assets/ops.js`) |
| `GET /ops/assets/ops.js`, `/ops/assets/ops.css` | the console bundle (today's website, API base `/ops/api/`), from `studio/operator/`, never `static/` |
| `GET /ops/api/session` | the console's session (`serializers.session_json`'s shape; role `operator`) |
| `GET /ops/api/encounters[?workspace=<uuid>]` | every workspace's rows: `serializers.encounter_summary` + `workspace{id, name}` + `provider_runs` (count) |
| `GET /ops/api/encounters/{id}` | the full `serializers.encounter_detail` (the operator's own membership when they hold one, else read-only) |
| `GET /ops/api/encounters/{id}/trace` | `serializers.trace_json` |
| `GET` / `POST /ops/api/encounters/{id}/reports` | every artifact with `audience`, `sha256`, `snapshot_sha256`; POST makes the operator report (`cpt-studio-report@4`) |
| `GET /ops/api/reports/{id}/download` | any artifact, stored bytes, `X-Content-SHA256` |
| `GET /ops/api/encounters/{id}/original` | the original with `X-Content-SHA256` |
| `POST /ops/api/encounters/{id}/reconcile` | `{"provider_run_id", "note"}` as before (reconciliation is operator work) |

An operator's reads of an encounter are audited as `operator.viewed` (once per operator, encounter and view in ten
minutes); they are never part of an encounter's activity, the customer's or the operator's.

## Core repair and customer interface (2026-11-03): P5 FLOW

Endpoints and blocks the customer interface reads for directive sections 4 and 5. Every sentence below is from fixed
tables in `studio/answers.py` and `studio/progress.py`: no stored question, reason, note, job error or run error text
is passed through.

**`POST /api/encounters` - `client_key`** (optional multipart field): a UUID the page generates per upload attempt. A
repeated POST of the same attempt - the same member, within 24 hours, the same file (sha256) or pasted text - answers
201 with the first encounter's `id` and creates nothing. Another member's same key is their own new encounter. 409 for a
key used for another document, in another workspace or more than 24 hours ago ("This upload was already received. Open
it from your documents." / "This upload key was already used for a different document. Reload the page and upload
again."); 400 for a key that is not a UUID. Two concurrent POSTs of one attempt are settled by the database's unique
index on (member, key): the second answers with the first's id.

**`POST /api/encounters/{id}/details`** `{"answers": [{"id": "<detail id>", "fact": "<fact>", "value": "<value>"}]}` -
one save for every row of "A few details needed" (owner or reviewer; 403 otherwise; 404 outside the workspace):
- a `date` row takes `YYYY-MM-DD`, or `use_document` where offered (clears the member's date: the document's own date
  then stands); a `choice` row takes one of its listed values, `use_document` where offered, or `not_documented` where
  `allow` lists it; a `confirm` row (a clinical fact) takes only `not_documented` or `cannot_confirm`;
- context values go through ONE context change and its re-assessment (as `POST .../context` makes it); the other two
  values are stored as the member's answers (append-only, attributed, audited `detail.answered`), read by the review
  overlay with no re-assessment and nothing sent;
- 201 `{"saved": n, "unchanged": m, "answer_ids": [...], "reassessing": bool}` when something was saved; 200 with
  `saved` 0 when the save changed nothing (a repeated identical save makes nothing); 400 `{"error"}` for an answer the
  row does not allow ("Only "Not documented" or "Cannot confirm" can be recorded for this detail. A clinical detail is
  added to the documentation by the physician.", "Choose one of the answers offered for this detail.", ...); 409 while
  processing runs or for a detail no longer asked.

**`POST /api/encounters/{id}/details/{answer id}/revoke`** - withdraws one saved answer (the detail is asked again);
201 `{"revoked": "<answer id>"}`; 404 for another document's answer; 409 while processing runs or when already
withdrawn. A later answer to the same detail withdraws the earlier one itself.

**Blocks** (built by `answers.details_needed(encounter, assessment, view)`, `answers.service_date_block(encounter)`,
`progress.encounter_progress(encounter, now)` and `progress.checks_summary(encounter)` with DESIGN section 7's keys):
`details_needed` rows are one per open question, de-duplicated by (fact, family, code), with a stable `id` across
re-assessments; `service_date` shows the document's own date and quote only where the document gives one date of its
own, beside the member's entered date; `progress` folds the jobs into four plain steps and one phase (`queued`,
`processing`, `action_needed`, `awaiting_detail`, `completed`, `partial`, `failed`, `stopped`, `being_confirmed`), never
a percentage or an estimate, "taking longer than usual" only from the stage's own deadline; `checks` states Document
review, Independent checks and Coding validation. None of them writes anything.

**Operator command `manage.py reassess_retained --encounter <uuid> --tag <release> [--username U] [--dry-run]`**:
one re-assessment from the retained answers (the final assessment's runs re-read by id), nothing sent, one job per tag;
refused, with the reason, while busy or stopped or when the final assessment is not current. Audit
`assessment.refreshed` ("Results were refreshed with updated software").

## Core repair and customer interface (2026-11-03): P6 UI

What the customer page (`studio/static/studio/app.js`) sends and relies on. It reads only the customer encounter
contract (build design section 7) and the customer session and list; it reads no other endpoint and has no
diagnostics route. Fixtures: `tests/fixtures/customer/`.

**Every request** carries `X-CPT-Studio-Client: customer-2026-11-03`. A server that no longer serves this build of the
page answers HTTP 409 with `{"error": "<sentence>", "error_code": "client_outdated"}`; the page shows "CPT Studio was
updated — reload the page to continue." with a Reload button and stops polling. This is a client contract; the server
side belongs to the integration. A page loaded before this release sends no header and does not know `error_code`; it
shows the body's `error` sentence, so that sentence should itself say the page must be reloaded.

**Errors.** The page shows the body's `error` sentence when it is a non-empty string, else a fixed sentence per status
(400, 403, 404, 409, 413, 429, other), never a status code. A refused download appends `details.blockers` (plain
sentences).

**`POST /api/encounters`** (multipart): `file` or `text`, optional `service_date`, `synthetic_attestation=yes`, and
`client_key` — a version-4 UUID per upload attempt, kept when the same attempt is retried and replaced when its file,
text or date changes. On 201 `{"id"}` the page shows the upload acknowledgement before its first read of the document.

**`POST /api/encounters/{id}/details`**: `{"answers": [{"id": "<details_needed[].id>", "fact": "<details_needed[].fact>",
"value": "<value>"}]}` — one request for every row the member answered. `value` is one of the row's choice values,
`not_documented` or `cannot_confirm` (only where the row's `allow` lists it), `use_document` (a date row whose
`document_value` is set), or `YYYY-MM-DD` (a date row). **`POST /api/encounters/{id}/details/{answer_id}/revoke`** with
`{}` withdraws a saved answer (`details_needed[].saved.answer_id`).

**`POST /api/encounters/{id}/decisions`**: as before, plus `"modifiers": []`, `["59"]` or `["XS"]` on an approval of a code
with a `modifier_review` whose `options` offer it (one at most, never prefilled; not sent for any other action or code).

**`POST /api/encounters/{id}/reports`**: `{"kind": "draft" | "approved", "fmt": "txt" | "csv"}`; the page downloads the
answer's `download_url`, which must match `/api/reports/<uuid>/download`. The approved options are disabled, with
`readiness.blockers` listed, while `readiness.approved` is not `true`. A `reports[]` entry whose `current` is not `true`
is listed without a link ("No longer matches the saved decisions").

**`POST /api/encounters/{id}/addenda`**: `{"text", "clarification_id": "<details_needed[].id>", "synthetic_attestation":
"yes"}`, offered only on a row with `addendum_allowed: true` ("Add to the documentation (physician)"); the server
accepts a details row id there (2026-11-04): the open confirmation row of the live assessment it names, answering the
stored clarification that row shows (none for a question only the review overlay asks); any other row id answers 404
"That detail is not open on this document." A clarification's own id is read as before. **`/stop`** and **`/resume`**: `{}`, offered when `progress.can_stop` (while busy) or
`progress.can_resume`, and `permissions.can_review`.

**Polling.** `GET /api/encounters/{id}` while `progress.busy` is true or `progress.phase` is `queued`, `processing` or
`being_confirmed`: 2.5 s backing off to 15 s, and to 30 s after failed reads. A failed read shows "Reconnecting…";
coming back to the tab or back online reads at once. Elapsed time is `server_time` − `started_at`, advanced by the
browser's clock between reads; no percentage or forecast is shown. No step is animated unless the phase is `queued` or
`processing` and `busy` is true.

**Labels the page fixes itself** (a served label is used only for a value it does not know): the code statuses (Ready
for review, Needs a detail, Approved, Excluded), the states, the four stages and the three checks. An approved code whose
`decision.by_kind` is `agent` always reads "Agent-executed synthetic review — not clinical approval", whatever
`sub_label` says.

**DOM hooks beyond design section 8.** `li.result-row` also carries `data-units` and `data-modifiers` (space-separated);
`.result-foot` holds `details.why-code` and `.result-actions`; a `.why-quote` button's text is the exact quote (the
typographic quotes and "page N" are drawn by CSS from `data-page`), and a quote not found at its offsets is
`span.why-quote.unlocated` with no `data-evidence`; source marks are `.evidence-mark[data-keys]` with keys
`<code id>:q<n>` and `date:document`; `#reviewModifierField` is hidden unless approving a code with a modifier review;
`#updateNotice`, `#uploadStatus`; `section.progress-panel.progress-done[data-phase]` for `completed`, `partial` and
`awaiting_detail`; `[data-elapsed][data-since]` ticks while busy and carries `data-until` once finished. The edit-context
dialog is gone (`#contextDialog`, `#contextServiceDate`, `#contextSetting`, `#contextBilling`, `#saveContext`,
`button[data-action="edit-context"]`): context answers go through the details panel.

## Core repair and customer interface (2026-11-03): integration wiring

What changed when the packages' functions replaced P4's stand-ins (appended; the sections above stand as written,
corrected here where this changes them):

- **Every customer status, action and question reads the review overlay** (`review.effective_view`): a code's status,
  its questions, the approve gate, a decision the overlay no longer supports (its readiness blocker, worded for the
  member), the separate-lesion `modifier_review` (`sources`: the dated CMS source, title, release, effective date and
  page) and the one-sentence `summary` (CPT Studio's own reading: structured fields and act labels, never a support
  detail). A code whose needed detail a member answered `not_documented` or `cannot_confirm` is `excluded` ("A needed
  detail is not documented" / "could not be confirmed"), offers no action and needs no decision until the answer is
  withdrawn - in both APIs, readiness and the reports (`review._member_answers` reads `answers.saved_answers`).
- **`details_needed`, `service_date`, `progress` and `checks`** are P5's (`answers.details_needed` over the overlay,
  `answers.service_date_block`, `progress.encounter_progress`, `progress.checks_summary`); `can_stop`, `can_resume`,
  `progress.error.action` and a row's `addendum_allowed` are offered only to a member whose role may take them. While a
  member's date conflicts with the document, the date is the one detail asked; a save answering anything else is 409
  ("That detail is no longer needed. ..."). `state` reads `action_needed` as soon as the phase does.
- **`readiness.approved`** is `review.readiness` over the overlay (every suggested code approved, rejected, its exclusion
  confirmed, or its detail answered as unavailable; nothing processing; a settled result) with an approved code to list
  (session decision (f) of 2026-11-03: no partial approved export).
- **An approved export is stale (download 409; `reports[].current` false) exactly when its decision marker moves**:
  the live assessment, the current context, the current decisions (ids and sequence) and the standing member answers
  (ids). A customer artifact's `snapshot_sha256` holds that marker's digest (`reports.customer_marker`), not a digest of
  the report's content: a queued stage, a later run, an operator report or new wording never makes one stale. This
  replaces the P4 section's "whose snapshot no longer matches".
- **`counts.queue` in the customer session** keeps the review queue's rule above (`queue_reasons`), joined with the
  customer queue's states (`action_needed`, `awaiting_detail`, `ready`), so it never counts fewer than the page's queue
  lists. The page lists only those states (the list rows carry no queue reasons), so its badge can count more than its
  queue shows: an open item. **Closed 2026-11-04 (session decision (o))**: each list row carries `in_queue` (boolean,
  `customer_api.in_queue`: one of the three customer states, or what `queue_reasons` holds waiting), the page's queue
  lists exactly the rows marked `in_queue: true`, and `counts.queue` counts exactly those rows. The rule is unchanged;
  the page now lists what it counts.
- **`recheck`** (session decision (n), 2026-11-04): `{"available": bool, "can_request": bool}` beside `unresolved`. The
  installed page offered the bounded second review ("Ask the provider once more"); the customer page keeps it, worded by
  function: "Check what is still open again" under "Still open", shown only while `can_request` is `true`, posting
  `POST /api/encounters/{id}/second-review` `{}` (201 `{"second_review": "queued"}`; a refusal answers 409 in the
  customer error vocabulary). `available` is `jobs.second_review_status`'s (a documented service left without a supported
  code and no bound standing: the predicate the POST accepts an ask by); `can_request` is `available` for an owner or
  reviewer, never for a viewer. An assessment never queues one (owner decision 2026-10-27), and the offer sends
  nothing.
- **"Taking longer than usual"** (`progress.slow`) is past 60% of the bound each stage really has where it runs
  (`progress.stage_bound`: extract 240 s, analyze 60 s, document review and its second review 150 s, assess 120 s, an
  independent check's stage 580 s), a display threshold only; no sentence promises an automatic stop or start.
- **Customer fixtures** (`tests/fixtures/customer/*.json`) are all generated from the serializer
  (`CPT_STUDIO_WRITE_FIXTURES=1 manage.py test tests.test_customer_fixtures`), including Mara from Corti's retained
  response, read in process.
