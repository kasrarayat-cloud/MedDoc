# The Gemini migration: the installed baseline and every place semantic interpretation decides (checklist item 1)

Evidence for the owner's migration checklist, item 1 (cpt-studio/HARNESS.md, "The Gemini interpretation migration").
- **How it was made.** Workflow `wf_99a21a16-63c`: eight read-only readers mapped the installed tree, and a synthesis agent
  re-read every site it kept. The tree is `c2e53f8e`; its `cpt-studio/` equals main's at `6e95b0de` / `7d4ac946`.
- **Spot-checked.** The integration owner re-read 11 of its highest-impact sites against the code on 2026-11-09 at about 08:18Z,
  and all 11 read as stated: review_view.py:258; engine.py:207, 219, 3069, 3075 and 3600; review.py:1384; jobs.py:481, 553,
  559, 1715 and 3195; structure.py:2081 and 2118; progress.py:308; reports.py:922; customer_api.py:999; reconcile.py:831.
- **Line numbers** are the installed tree's.

## Baseline

- **Installed release:** `c2e53f8e7d33732d5badd4ce9b681f274eb5c471` (PR #1489).
- **Image:** `cpt-studio:c2e53f8e7d33`, id `sha256:02a99d53026f303cfeae5c5b64a1d9f18dec7a78c8306025427117c806b769a4`, built
  2026-11-08T21:34Z. It serves cpt.quillmd.com (web and worker started 2026-11-08T22:53-22:54Z, 0 restarts).
- **Rollback image for this migration:** `cpt-studio:c2e53f8e7d33` (present). The pair the current install replaced,
  `cpt-studio:aeae34bebbe5` (`sha256:78fc009b900c...`), is also present.
- **Labels:** gi-context@5, gi-routing@12, gi-services@7, cpt-studio-validation@10, gi-profiles@3, gi-catalogue@2.
- **Schema:** leaf `0013_completion_answer_binding` (13 migrations).
- **Live counts, read-only,** at 2026-11-09T08:20:55Z (`default_transaction_read_only=on`; every row was made by the
  legacy reader and is to be preserved):
  - encounters: 86
  - revisions: 87
  - contexts: 103
  - routing_runs: 113
  - assessments: 180
  - proposals: 2477
  - clarifications: 340
  - decisions: 62
  - decision_invalidations: 2
  - studio_memberanswer: 29
  - reports: 203
  - provider_runs: 265
  - provider_runs_sent: 231
  - jobs: 619
  - jobs_active: 0
  - audit_events: 1337

## Active work at the change of direction (2026-11-09T07:10Z)

- **Stopped and preserved:** the U32 c4 workflow (`wf_797a9eb3-a98`), a stage-by-stage keyword-reader repair, at 07:12Z.
  - Its 6,413 files were hashed before the stop.
  - Its counterexample registry (1,374 entries) is kept as a regression corpus.
- **Parked on origin, unmerged, not deleted:**
  - `fix/cpt-studio-gi-binding-20261029` (76 commits) and `wip/7c8-p2dates` (9): keyword-reader era.
  - `fix/cpt-studio-pypdf-6.21.4-20261031` (16) and its `prep/` branch (1): the deferred pypdf move. Its advisories fail
    the non-required `cpt-studio` audit on every main merge, this one included.
- **Records PR #1492:** merged as `7d4ac946`; its branch is retired.
- **This branch:** `feat/cpt-studio-gemini-interpreter-20261109`.
- **Sealed sets:** the independent set g1 was sealed at 08:10:37Z (`cpt-studio/ops/verification/seals/g1-20261109.md`).
  The blind sets c6 and c7 are unread.

## Where semantic interpretation decides today, by concern

### routing (11 sites)

- `studio/jobs.py:528` _analyze_child -> `gi.detect.service_mention_count; gi.services.mention_count (531, local import 530)`: Mention gate over legacy vocabularies. Above settings.MAX_SERVICE_MENTIONS=1000 (cptstudio/settings.py:116) the analyze stage fails (jobs.py:786-787) and no context, routing or request is ever made. [assess, reassess, save]
- `studio/jobs.py:534` _analyze_child -> `gi.context.extract_context`: The revision's document facts. Merged with member values (535), they give the effective date that is routed (536), recorded as EncounterContext (789), sent to Corti (953) and tested for the member-date hold. [assess, reassess, save]
- `studio/jobs.py:536` _analyze_child -> `gi.detect.route`: RoutingResult for the effective date (families, statuses, mentions with cues, facts, missing facts, document_kind), stored as RoutingRun (792). The stage fails if the context's date differs from it (790-791). [assess, reassess, save]
- `studio/jobs.py:946` stage_predict -> `RoutingRun existence; _route_child -> gi.detect.route (950 -> 541)`: Nothing is built or sent for a (revision, date) that has no RoutingRun. A newly effective date is routed first in a bounded child and recorded (951). [assess, save, reassess]
- `studio/jobs.py:3177` change_context -> `models.RoutingRun existence or review.can_resume`: A context save is refused for a revision the legacy router never routed, unless its latest stage is resumable. [save, answer_recompute]
- `studio/jobs.py:553` _assess_child -> `gi.detect.route`: Every FIRST, FINAL and AGAIN assess re-routes the whole text. The result is the engine's routing input and is recorded (2318) as Assessment.routing, a NOT NULL FK (studio/models.py:291). [assess, reassess, answer_recompute, save, peer_request, install_or_ops]
- `studio/validation/engine.py:1594` _select -> `RoutingResult.finding(legacy) gated by gi.profiles.DETECTED_FAMILIES`: The routed FamilyFinding feeds three things: routing readings in resolve_status (1606), required facts (3264) and separate_em (3333), and the routing.family check (3285). [assess, reassess, answer_recompute]
- `studio/validation/engine.py:3005` _encounter -> `routing.findings via _same_day_family/_done_today/_possibly_today/_speaks_for_today (2849-2918)`: procedure_day and procedure labels, which drive the same-day E/M holds, the reinstatement gates and the reconciliation's office-visit suppression (called 236, 248, 254, 263-267). [assess, reassess, answer_recompute]
- `studio/validation/engine.py:319` assess -> `_unsupported(routing, selections) (3740-3763)`: services.unsupported: performed services outside the GI profiles, read from routing. [assess, reassess, answer_recompute]
- `studio/serializers.py:231` _routing_json -> `stored RoutingRun.result`: The operator detail (serializers.py:1173, /ops/ only) shows the legacy routing's families, statuses, cues, facts and missing facts. [reload]
- `studio/jobs.py:2711` run_job -> `release_routing_caches (577-585) over ROUTING_CACHE_MODULES named as strings (567-574)`: Clears the legacy reader's caches after every stage. This couples the worker to legacy module names that import scans cannot see. [assess, reassess, answer_recompute, peer_request]

### matching (13 sites)

- `studio/validation/engine.py:219` assess -> `gi.services.build (+ gi.services.validate 224)`: Builds the documented-service inventory (services, acts, lesions, conflicts, attributions) from the text, with routing as a second opinion. Every match, base or competing hold, reconciliation and service question reads it, and it is stored as Assessment.services (379). If validate reports problems, usable is None (225). [assess, reassess, answer_recompute, save]
- `studio/validation/engine.py:232` assess -> `_select per proposer: Corti 232, bounded second review 435, admitted participant 4358, participant-merged primary passages 4412`: Each code's status, bucket, matched service/act (Proposal.support) and passage support, for every proposer. [assess, reassess, answer_recompute]
- `studio/validation/checks.py:1303` span_status/evidence_readings -> `gi.detect.status_for_span`: Status and cues of each cited passage. These are the code's own readings in resolve_status (called from engine.py:1595). [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1606` _select -> `checks.resolve_status + checks.routing_readings (checks.py:243-482)`: Combines own-passage and routing readings into a StatusOutcome (performed / not_performed / uncertain ...). This decides an unmatched code and is the second opinion for a matched one (re-run at 1623). [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1599` _select -> `checks._V2_judged_away (detect.own_status_for_span checks.py:410); _unnamed_other (1600; checks _VAL_* over private detect names checks.py:316-410, 1414-2560); _undated_visit (1602); _other_service (1604; checks.names_intervention -> cues.INTERVENTIONS checks.py:2534)`: Holds versus exclusions for gi.other and E/M codes, plus which hedges are about another service. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1608` _select -> `reconcile.match (reconcile.py:205-322: NAME_ONLY_CUE 138-141, ROUTING_CONTRARY_CUE/ROUTING_DOUBT_CUE 221, technique_fits 244 -> dilation regexes over act evidence 166-198)`: Matches a code to a documented service and act through catalogue covers, giving a Match state and reason. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1620` _select -> `_set_aside_attempts -> gi.detect.closed_attempt_failure (1803)`: Sets aside a cited passage that describes the failure of a different attempt. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1627` _select -> `_second_opinion (1834-1955) and helpers 2379-2671 over services/cues/detect constants and services._acts_in/_anatomy_in/parts`: The final Match state: hold both readings, release on the code's own passage, act included, or keep agreement/exclusion. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1660` _select -> `_stated_not_done (766-881: services.passage_readings 727/872/877, cues.FAILED_ACT 916, services.ACT_VERB/BARE_PARTICIPLE 925-926)`: Excludes a code (reinstatable) whose act the document states was not done. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1690` _select (current/today/report_family closures) -> `gi.services.current_statement; gi.structure.clinical_layout (1674, 1769, with the hidden full reread structure.py:2062-2118); gi.services.report_family_at (1678)`: The evidence.support status from reconcile.support (1692, 1718). [assess, reassess, answer_recompute]
- `studio/validation/engine.py:997` _competition -> `gi.structure.clinical_layout + _claimed (488-572; services.LISTED_CUE/SILENT_READINGS 512)`: Act identity across codes, which gives the proposals.competing hold and its question (P-ADMIT2). [assess, reassess, answer_recompute]
- `studio/validation/engine.py:208` assess -> `gi.context.charge_question_day(text) (+ is_member_conflict 207)`: read_day, the date every reader reads the text against when no date is established. It re-runs context._context over the text (context.py:1926-1933). [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1716` _select -> `reconcile.elsewhere (reconcile.py:550-566: services.act_regions/FAMILY_REGIONS) + reconcile.placed_check (618-643; _done_through regex 597-616)`: For a code with no service of its own family: whether the act is documented in another family's service, and the service.act_elsewhere warning. [assess, reassess, answer_recompute]

### contradictions (9 sites)

- `studio/validation/engine.py:1616` _select -> `_held_unless_agreed / _second_reading (2002-2047: services.passage_readings 2014, services.done_today 2021)`: The two-reader rule: a not-performed reading excludes only when both legacy readers agree; otherwise the code is held with a question. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:1636` _select -> `_agreed_not_done (2253-2268); _pa_one_cause_hold (1647; 2129-2300, clinical_layout 2195); gi.services.doubted_by_routing_alone (1649)`: Whether an exclusion stands or becomes a one-cause hold. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:316` assess -> `_service_questions -> reconcile.conflict_clarification (reconcile.py:924-933) over inventory.conflicts; reconcile.conflicts_check (engine.py:326)`: Conflict questions (conflict:<act>) and the services.conflicts check. [assess, reassess, answer_recompute]
- `studio/jobs.py:487` _merged_facts -> `gi.context.merge_user_values`: Member metadata against document facts: taken, held as a member conflict (USER_CONFLICT_NOTE context.py:3406), or settling a documented conflict. Runs in the analyze child (535) and unbounded in the parent (_record_context 493). [assess, save, reassess]
- `studio/jobs.py:935` stage_predict -> `gi.context.is_member_conflict (same predicate gates jobs.py:142, 249, 338, 855, 1605, 3024, 3151-3152)`: Member-date hold: a NOT_SENT hold run is recorded, nothing is built or sent to Corti, Astra, Fable or the peers, and the assess follows. [assess, save, reassess, peer_request]
- `studio/jobs.py:142` _queue_predict -> `gi.context.is_member_conflict`: Every predict queue records the hold and queues only the ASSESS (reached from 798, 861, 871, 2986, 3029, 3224). [assess, save, reassess]
- `studio/validation/engine.py:1531` _member_conflict_questions -> `gi.context.is_member_conflict (+ _billing 3518)`: One encounter question for a member-metadata conflict, plus PC/TC billing wording. [assess, reassess, answer_recompute]
- `studio/validation/checks.py:1057` _date_problem -> `gi.context.is_member_conflict + charge_date_problem (1059); also checks.py:711-712, 749`: Wording of the context.service_date failure and the date question, and the conflict reasons in required facts. [assess, reassess, answer_recompute]
- `ops/install.py:2039` UNDO_HAZARDS.undo_hazards -> `gi.context.is_member_conflict (imported 1994)`: The 'conflict' undo hazard; any named hazard makes switch-back (4540, 4624) and rollback-app (5612, 5777) refuse. [install_or_ops]

### completeness (9 sites)

- `studio/validation/engine.py:298` assess -> `reconcile.reconcile (reconcile.py:793-921: HYPOTHETICAL_CUE 830, FAILED_ATTEMPT regex over evidence 831, listed_contradicted/listed_in_doubt 844-858, _read_under -> services.examined_regions ANATOMY regex 875/741-763, technique_fits 905)`: Unresolved, bundled and covered items, which feed services.unresolved, completeness, second-review items and participant admission. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:349` assess -> `reconcile.completeness (989-1023)`: Coding completeness state and reasons stored in Assessment.completeness (forced incomplete when inventory problems exist, 352-354). [assess, reassess, answer_recompute]
- `studio/validation/engine.py:313` assess -> `checks.unproposed_check(_missed(routing...), _accounted_elsewhere 3645-3686 -> services.SERVICES 3681)`: services.unproposed: routed families done today that have no selected proposal. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:3264` _proposal -> `checks.required_fact_states (checks.py:673-688: routing FamilyFinding.facts/missing; context facts)`: The facts.required check and fact questions (3315, 3331, 3353). EXTENT_NOT_FOUND and similar make a code needs_clarification. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:3333` _proposal -> `checks.separate_em_statement (checks.py:788-793; also engine.py:312, 3024, 3354)`: Whether a separate E/M is documented, which sets the same-day E/M holds and the unproposed wording. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:360` assess -> `_routing_agrees (1130-1157: detect.status_for_span 1149; _po_* 1200-1512 with sections/structure/cues)`: The second_review mark on each unresolved item. Only marked items can be offered for a paid Corti second review (jobs.py:2365-2366). [assess, reassess, answer_recompute, peer_request]
- `studio/validation/engine.py:4747` _Harness.missing/_read_as/_read_in -> ``located` mention records from gi.services.build (218-223)`: The participants.services warning, and an incomplete state when only a participant reads a service as performed. [assess, reassess, answer_recompute]
- `studio/validation/engine.py:3600` reviewed_completeness -> `from_jsonable(gi_services.ServiceInventory) (3594) + reconcile.reconcile/uncounted/completeness`: Read-time reconciliation whenever a code was reinstated. It re-applies the FAILED_ATTEMPT, technique and ANATOMY regexes to stored evidence text. [review_view, reload, export, peer_request]
- `studio/review.py:1384` reviewed_completeness -> `validation.engine.reviewed_completeness`: The single completeness view read by customer_api.py:1004, serializers.py:406, reports.py:746, review.py:1402 and jobs.py:2363. [review_view, reload, export, peer_request]

### clarification (8 sites)

- `studio/validation/engine.py:316` _service_questions -> `reconcile.documentation_clarifications (reconcile.py:936-968; is_member_conflict 949)`: Service-scope questions about extent, setting, status and basis. [assess, reassess, answer_recompute]
- `studio/validation/checks.py:740` fact_clarifications -> `routing facts via required_fact_states (+ required_facts_check 701-735)`: Proposal-scope questions for missing or conflicting required facts. [assess, reassess, answer_recompute]
- `studio/jobs.py:3290` member_answers_of -> `validation.questions.MemberAnswerInput`: Standing answers bound by MemberAnswer.question fingerprints (studio/models.py:459), which the engine applies (stage_assess 2312). [assess, answer_recompute, reassess]
- `studio/review.py:296` question_pairs -> `questions.question_passages / service_passages (303) over the legacy Assessment.services`: Passages that are hashed into each question's fingerprint (questions.instance/fingerprint, questions.py:236-247). [review_view, save, answer_recompute, reload]
- `studio/review.py:389` asked_fingerprints -> `review_view.review_view + questions.group`: The fingerprint stored on a new MemberAnswer (answers.py:757, 823-827). [answer_recompute]
- `studio/answers.py:535` _rows -> `gi.context.is_member_conflict (also 570, 629)`: While a member date conflicts, only the date row is asked; also controls the 'use document date' choices. [reload, answer_recompute, save, review_view]
- `studio/answers.py:250` service_date_block -> `gi.context.is_member_conflict; charge_date_problem (257)`: The date-of-service block: conflict flag, can_use_document_date, and the printed value. [reload, export, save]
- `studio/candidates.py:328` _date_value / _inconsistent / _qualified -> `gi.context.find_dates (328, 530), gi.context._is_birth (461), gi.services.clauses (509), reconcile.status_stated/held_section/whole_sentence (495, 452, 508), gi.cues tables`: DORMANT: verifies candidate answers. Reached only through review.assessment_candidates (review.py:2419), which returns {} while STUDIO_OFFER_CONFIRMATIONS is False (cptstudio/settings.py:166). [review_view]

### review (11 sites)

- `studio/review.py:423` effective_view -> `validation.review_view.review_view (review_view.py:505)`: Every reader's code status, open questions, approve gate (withheld_by), readiness blocker, modifier review and summary, recomputed at read time. [review_view, reload, save, export, answer_recompute]
- `studio/validation/review_view.py:176` _inventory -> `from_jsonable(engine.gi_services.ServiceInventory, Assessment.services)`: Rebuilds the legacy record type. It fails quiet to None for an unreadable record (170-178), after which base rules and summaries are no longer recomputed. [review_view, reload, save, export]
- `studio/validation/review_view.py:259` _bases -> `engine.base_included (+ base_within 258) -> gi.services.listed_in_doubt/listed_contradicted (engine.py:3069, 3075) + reconcile._bundled`: Re-derives base-code holds over the reviewer-adjusted set, giving the view status, withheld_by and readiness blockers. [review_view, reload, save, export]
- `studio/validation/review_view.py:654` review_view -> `engine.competing_hold; base_hold/base_within_hold (604); checks.reinstatement_check (619); checks.endoscopic_check (672); engine.distinct_lesions (409); reconcile wording for summary (460)`: Recomputed check rows, questions, modifier options and summary. [review_view, reload, save, export]
- `studio/review.py:337` answer_states -> `review_view.review_view(answers=()) + questions.bind/group (338)`: Which standing answers apply, are bound, or are earlier answers. [review_view, reload, answer_recompute, export]
- `studio/review.py:697` record_decision -> `effective_view (+ is_final 695 -> jobs.peer_review_held -> is_member_conflict)`: Whether approve/reject/reinstate/confirm is allowed now, and which modifier is accepted. [save]
- `studio/review.py:1229` _assessment_blockers -> `effective_view; is_final (1202); answers.date_confirmation_open (1204 -> _rows -> is_member_conflict)`: Readiness blockers, which gate the approved/reviewed export and the cached Encounter.state. [review_view, reload, save, export, assess]
- `studio/review.py:929` _fact_value -> `gi.context.charge_date_problem`: Wording of a DecisionInvalidation reason when a re-assessment does not carry a decision (_what_changed 944-970). [assess, reassess, answer_recompute]
- `studio/review.py:1043` _carry_decisions -> `Proposal.fingerprint (engine._fingerprint engine.py:3566-3570, computed at 3411)`: Decisions carry only to an equal fingerprint, and only onto final assessments (1113-1115). Anything else is invalidated with a reason. [assess, reassess, answer_recompute]
- `studio/review.py:548` approved_items -> `effective_view`: Leaves out any approval that the overlay now blocks, so it never reaches the approved export. [export, reload]
- `studio/review.py:2346` recorded_inventory -> `gi.services.ServiceInventory (2342) + gi.services.validate`: DORMANT: re-validates the stored inventory against the text, for candidates only. [review_view]

### saving (8 sites)

- `studio/jobs.py:3195` change_context -> `make_context -> _bounded(gi.context.extract_context, revision.text) (481)`: Re-reads the document's context facts inside the web request (CONTEXT_REQUEST_SECONDS=15, cptstudio/settings.py:206) under the encounter row lock (3169-3170). [save, answer_recompute]
- `studio/jobs.py:500` _record_context -> `gi.context.document_service_date_fact(text, facts=...) + merge_user_values (493 -> 487)`: EncounterContext.facts and document_date, written in the web process when a member saves. [save, assess, reassess]
- `studio/jobs.py:3151` _settles_member_conflict -> `gi.context.is_member_conflict (twice, 3151-3152)`: Whether a save settles a held date. If so, the deferred request is owed and a re-predict (a send) follows (3211-3212). [save]
- `studio/jobs.py:3212` change_context -> `_run_answers -> _request_for -> provider.build_request(revision.text, legacy context date) (3076)`: Whether the save re-checks with the run in use or re-predicts. [save, reassess]
- `studio/jobs.py:3213` change_context -> `_participants_owed (is_member_conflict 249) / _queue_predict (3224 -> 142)`: Whether the participant chain runs or only the assess is queued. [save]
- `studio/answers.py:835` save_details -> `jobs.change_context`: A details save that carries a date, setting or billing value goes through the legacy context reread. [save, answer_recompute]
- `studio/api.py:359` addenda -> `jobs.start_pipeline (after review.invalidate_for_new_revision 353)`: An addendum is read again in full by the legacy reader, and every current decision is invalidated. [save]
- `studio/review.py:724` record_decision -> `refresh_state (1636) -> overlay chain`: The cached Encounter.state after every write. [save]

### reload (8 sites)

- `studio/customer_api.py:999` encounter_json -> `views_of -> review.effective_view`: Customer statuses, quotes, summaries, actions and qualifications on every page load and poll. [reload]
- `studio/customer_api.py:1004` encounter_json -> `review.reviewed_completeness`: not_separately_coded and unresolved lists. When a code was reinstated, this re-runs the reconcile regexes. [reload]
- `studio/customer_api.py:924` customer_state -> `progress.date_held -> gi.context.is_member_conflict (progress.py:308)`: The 'action_needed' state. [reload]
- `studio/customer_api.py:989` recheck_block -> `jobs.second_review_status (2536-2554) -> _second_review_items (2358-2378) -> review.reviewed_completeness`: Whether 'check what is still open again' is offered, using marks made by engine._routing_agrees and legacy inventory spans. It also builds a Corti request on the excerpt (2517). [reload]
- `studio/customer_api.py:956` session_json / in_queue -> `serializers.queue_reasons (132-185: open_questions_of 165, _decisions_waiting 167, coding_completeness 171, second_review_status 176)`: Review-queue membership and the session's queue count, for every encounter in the workspace. [reload]
- `studio/customer_api.py:702` details_rows -> `answers.details_needed -> _rows (is_member_conflict 535/570/629; passages questions.* over Assessment.services 512-515)`: The 'A few details needed' rows. list_row also runs these with views_of for every encounter (974). [reload]
- `studio/serializers.py:334` _proposal_json -> `review.effective_view per proposal (+ reviewed_completeness 406, _context_facts predicates 110, second_review_status 1187, assessment_candidates 1161 dormant)`: The operator console detail. [reload]
- `studio/serializers.py:189` encounter_summary -> `review.coding_completeness`: The operator encounter list (operator.py:269); runs the overlay for every encounter. [reload]

### export (7 sites)

- `studio/reports.py:714` snapshot -> `review.readiness`: Whether a reviewed operator report may be built, and its blocker lines. [export]
- `studio/reports.py:720` snapshot -> `review.effective_view; open_questions_of (721); coding_completeness (743); reviewed_completeness (746)`: Operator report statuses, open questions, completeness and documented services. [export]
- `studio/reports.py:922` _context_section -> `gi.context.is_member_conflict; charge_date_problem (923)`: Wording of the exported context facts. [export]
- `studio/reports.py:556` _peer_reviews -> `review.peer_review_held (+ owed_peer_stages 555) -> jobs.peer_review_held -> is_member_conflict`: Whether the PEER REVIEW section says held, owed or unowned. [export]
- `studio/reports.py:1871` customer_snapshot -> `customer_api.readiness; views_of (1874); answers.service_date_block (1878); approved_export_items (1881) / code_rows (1890)`: Contents of the customer draft and approved export (taken under the row lock, 2024). [export]
- `studio/api.py:475` create_report -> `customer_api.readiness -> review.readiness + review.approved_items`: The 409 refusal, with blockers, before an approved export is built. [export]
- `studio/operator.py:326` encounter_reports -> `review.readiness`: The 409 refusal before an operator 'reviewed' report is built. [export]

### peer_request (7 sites)

- `studio/jobs.py:1605` stage_peer -> `gi.context.is_member_conflict`: The peer review is recorded not_run (PEER_HELD). [peer_request]
- `studio/jobs.py:1715` _peer_material -> `_peer_codes(_cpt_studio_reading(first)) (1819-1848)`: The 'CPT Studio rule-based reading' sent to Astra and Fable: assess #1's OPEN clarifications and its held/excluded proposals with their failed-check details, all made by the legacy engine. [peer_request]
- `studio/jobs.py:1835` _cpt_studio_reading / _question_ids -> `review.question_identity (also 1898, 1905)`: Stable question ids, so an identical peer request can be reused. [peer_request]
- `studio/jobs.py:1857` _peer_reasons / _peer_text -> `validation.checks.CONFIRMATION_SOURCE/CONFIRMED_HEADING (1857-1858), checks.MEMBER_ENTERED (1872), gi.context.USER_CONFLICT_NOTE prefix (1816, 1875)`: Redaction of member values and confirmed reasons from the peer text. [peer_request]
- `studio/jobs.py:1720` _peer_material -> `sha256_json(cpt_studio) into frozen; prompt.peer_document exact shape (studio/participants/prompt.py:389-411); peer.check_frozen (peer.py:258-280)`: The peer request bytes and hash. Any change to the reading means no reuse and a new paid send. [peer_request]
- `studio/jobs.py:2337` stage_assess -> `owed_peer_stages -> peer_review_held -> is_member_conflict (338)`: Whether assess #1 queues peer stages, which also decides whether an assessment is final (review.is_final review.py:2077-2084). [assess, peer_request, review_view, reload, export]
- `studio/jobs.py:2614` stage_review2 -> `_second_review_items (2601 -> 2363) + Corti build_request(revision.text[start:end], legacy date)`: The member-asked bounded Corti second review: what it asks about and the excerpt sent (api.py:454 -> jobs.request_second_review 2557). [peer_request]

### progress (6 sites)

- `studio/progress.py:160` _held -> `gi.context.is_member_conflict`: Steps read 'skipped' and functions 'not_run' while a member date hold stands (callers 168, 219, 423, 486). [reload]
- `studio/progress.py:308` date_held -> `gi.context.is_member_conflict`: The 'action_needed' phase (520) and customer_state (customer_api.py:924). [reload]
- `studio/progress.py:349` final_assessment -> `review.is_final -> jobs.owed_peer_stages -> peer_review_held; _checks_outcome -> review.peer_review_held (387)`: Which assessment the checks summary reads, and the 'not_run' value for independent checks. [reload]
- `studio/progress.py:529` encounter_progress -> `review._derive_state (overlay chain); _open_details -> answers.details_needed + effective_view (584); _document_states_a_date -> service_date_block (575)`: The phase: stopped, failed, being_confirmed, awaiting_detail, partial or completed. [reload]
- `studio/review.py:1636` refresh_state -> `_derive_state -> _review_state -> readiness/effective_view`: The cached Encounter.state after every job (jobs.py:2693, 2718) and every member action. [assess, reassess, answer_recompute, save]
- `ops/install.py:2225` RECOMPUTE_STATES -> `review.refresh_state for every encounter (phase_app 4468; undo 4708; put_back_states 2624)`: Each stored list state after an install. A changed state is a declared stop. [install_or_ops]

## The same, per execution path (ordered)

### assess

- studio/jobs.py:784 stage_analyze -> _bounded(_analyze_child) (60 s forked child)
- studio/jobs.py:528 -> gi.detect.service_mention_count; 531 -> gi.services.mention_count (mention gate)
- studio/jobs.py:534 -> gi.context.extract_context
- studio/jobs.py:535 -> _merged_facts -> gi.context.merge_user_values (487) to get the effective date
- studio/jobs.py:536 -> gi.detect.route. Inside it: detect._analysis, context.service_date_of, sections.layout, structure.clinical_layout. The clinical_layout twin guard re-runs detect.route and services.build (structure.py:2081, 2118).
- studio/jobs.py:789 _record_context (parent, unbounded) -> merge_user_values (493 -> 487) and document_service_date_fact(text, facts=...) (500); 790 refuses on a date mismatch; 792 _record_routing
- studio/jobs.py:798 -> _queue_predict -> gi.context.is_member_conflict (142) -> on a hold: NOT_SENT run + ASSESS
- studio/jobs.py:910 stage_predict -> _remade_context. Only for gi-context@1-@3: make_context -> extract_context (835 -> 481), is_member_conflict (855).
- studio/jobs.py:935 -> gi.context.is_member_conflict (hold)
- studio/jobs.py:946-951 -> RoutingRun gate; _route_child -> gi.detect.route (541) for a date never routed
- studio/jobs.py:914, 953 -> Corti build_request(revision.text, the gi.context-read date) -> send doors -> _send (1004)
- studio/jobs.py:1476-1551 stage_participant astra/fable: no legacy call; the chain runs only because no hold stood upstream
- studio/jobs.py:2274 stage_assess FIRST -> _remade_context (earlier versions only)
- studio/jobs.py:2312 -> member_answers_of -> questions.MemberAnswerInput (3290)
- studio/jobs.py:2313 -> _assess_child: gi.detect.route (553) -> validation.engine.assess (559)
- studio/validation/engine.py:207-208 -> is_member_conflict + charge_question_day(text) (re-reads the context)
- studio/validation/engine.py:219 -> gi.services.build; 224 -> gi.services.validate
- studio/validation/engine.py:232 _select per Corti code, which calls in turn: checks.evidence_readings -> detect.status_for_span (checks.py:1303); gi.other and E/M readers (1599-1604); resolve_status + routing_readings (1606); reconcile.match (1608); _held_unless_agreed (1616); _set_aside_attempts -> detect.closed_attempt_failure (1620/1803); _second_opinion (1627); _agreed_not_done / _pa_one_cause_hold / doubted_by_routing_alone (1636-1649); _stated_not_done (1660); _another_roles_hold (1664); clinical_layout / report_family_at / current_statement (1674-1690); reconcile.elsewhere / placed_check (1716-1719)
- studio/validation/engine.py:435 second-review _select; 4358/4412 participant admission _select; 997 _competition -> structure.clinical_layout
- studio/validation/engine.py:236/248/254 _encounter (routing findings); 290 -> _MemberAnswers.apply -> review_view.review_view (5376)
- studio/validation/engine.py:298 reconcile.reconcile (reconcile.py:830-831 cue + FAILED_ATTEMPT regex, 844-858 listed_*, 875 examined_regions, 905 technique regex)
- studio/validation/engine.py:313 unproposed (_missed, _accounted_elsewhere); 316 _service_questions -> reconcile.documentation_clarifications (is_member_conflict reconcile.py:949); 319 _unsupported; 337 _member_conflict_questions (1531)
- studio/validation/engine.py:360 _routing_agrees -> detect.status_for_span (1149) and _po_* section readers (1200-1512): second_review marks
- studio/validation/engine.py:3264 required_fact_states (routing facts); 3285 routing_check; 3333 separate_em_statement; 3411 _fingerprint
- studio/jobs.py:2318 _record_routing; 2326 review.persist_assessment. Inside it: _withdraw_superseded (questions.member_key, review.py:866/872); is_final (1113 -> jobs.peer_review_held -> is_member_conflict 338); _carry_decisions -> _what_changed -> gi.context.charge_date_problem (929).
- studio/jobs.py:2337 owed_peer_stages -> peer_review_held -> is_member_conflict (338) -> astra_peer / fable_peer (see peer_request)
- studio/jobs.py:2268 stage_assess FINAL (':q:') -> _reread (2064-2087) -> the same _assess_child chain (553, 559) -> persist_assessment with carry
- studio/jobs.py:2711 run_job -> release_routing_caches, after every stage
- studio/jobs.py:2718 run_job -> review.refresh_state. This reaches: is_final (review.py:1202); answers.date_confirmation_open -> _rows -> is_member_conflict (1204; answers.py:535/570/629); effective_view -> review_view -> engine.base_included -> services.listed_in_doubt / listed_contradicted (1229/1512; review_view.py:258-259; engine.py:3069/3075).

### reassess

- ops/install.py:5194 phase_reassess -> one-shot manage reassess_retained (studio/management/commands/reassess_retained.py:53) -> jobs.reassess_retained (3376)
- studio/jobs.py:3408 -> review.is_final -> jobs.owed_peer_stages -> peer_review_held -> is_member_conflict (338); 3415 -> peer_review_held -> is_member_conflict
- studio/jobs.py:3450 -> review.refresh_state (overlay chain as in assess)
- studio/jobs.py:2268 stage_assess AGAIN (':c:<12 hex of tag>') -> _remade_context (2274, earlier versions only) -> _reread (2064-2087) -> member_answers_of (2312) -> _assess_child: gi.detect.route (553) + validation.engine.assess (559) full chain -> _record_routing (2318) -> persist_assessment (carry; charge_date_problem review.py:929)
- studio/api.py:438 resume -> jobs.resume: review.can_resume (2967; overlay chain) -> _queue_predict (2986 -> 142, is_member_conflict) or the cancelled stage re-enqueued under ':resume:<uuid>' (2984). That stage then runs its legacy calls: analyze 528-536; predict 935/946-951/953; peer 1605/1715; review2 2601 -> 2363; assess 553/559.
- studio/operator.py:389 reconcile -> jobs.reconcile: is_member_conflict (3024); _run_answers -> _request_for, which builds Corti's request with the legacy date (3025 -> 3076); then _after_predict (3026) or _queue_predict (3029 -> 142)
- studio/jobs.py:2735 mark_stale -> re-queues a finished send's successor under the key its stage would have used (2779-2810) -> the stages above
- studio/jobs.py:826-872 _remade_context for gi-context@1-@3 (43 current contexts at the 2026-11-08 baseline) -> make_context -> gi.context.extract_context (835 -> 481) -> is_member_conflict (855) -> _run_answers (846) -> ASSESS or _queue_predict
- studio/jobs.py:3238 reassess_after_confirmation: refused first (3253-3254) while confirmations are not offered (dormant)

### answer_recompute

- studio/api.py:400 details -> answers.save_details (736) under the encounter row lock
- studio/answers.py:753 _states -> review.answer_states -> review_view.review_view(answers=()) (review.py:337) + questions.bind/group (338)
- studio/answers.py:754 _rows(effective_view) -> review.effective_view -> review_view -> engine.base_within / base_included -> services.listed_in_doubt / listed_contradicted (engine.py:3069/3075); _rows -> is_member_conflict (answers.py:535/570/629); _passages_of -> questions.question_passages / service_passages over Assessment.services (512-515)
- studio/answers.py:757 review.asked_fingerprints -> review_view.review_view + question_pairs (review.py:296/303, legacy inventory passages) -> MemberAnswer.question (823-827)
- studio/answers.py:835 only when a context value is saved: jobs.change_context -> extract_context in the web request (see save)
- studio/answers.py:850 jobs.recompute_after_answers -> review.is_final (jobs.py:3325 -> peer_review_held -> is_member_conflict 338) -> queues an AGAIN assess ':c:a<11 hex>'
- studio/answers.py:859 review.refresh_state (overlay chain)
- studio/answers.py:880 revoke_answer -> _siblings -> _rows(effective_view) (872) -> recompute_after_answers (900) -> refresh_state (904)
- studio/jobs.py:2268 worker stage_assess AGAIN -> member_answers_of (2312) -> _assess_child: gi.detect.route (553) + engine.assess with member_answers (559; engine._MemberAnswers.apply -> review_view, engine.py:5376) -> persist_assessment (_close_answered, _withdraw_superseded, _carry_decisions -> charge_date_problem review.py:929) -> run_job refresh_state (2718)

### review_view

- studio/review.py:411-423 effective_view -> _overlay_inputs (254-278: Assessment.services unless inventory_problems) -> _member_answers -> answer_states (337: review_view.review_view(answers=()), questions.bind/group 338; _closed_pairs passages 367/373)
- studio/validation/review_view.py:176 _inventory -> from_jsonable(engine.gi_services.ServiceInventory) (legacy record type; fails quiet to None)
- studio/validation/review_view.py:240 _service -> reconcile.service_for (for a reinstated code)
- studio/validation/review_view.py:258-259 _bases -> engine.base_within / base_included -> gi.services.listed_in_doubt / listed_contradicted (engine.py:3069/3075) + reconcile._bundled + catalogue
- studio/validation/review_view.py:604, 619, 654, 672 -> base_hold/base_within_hold, checks.reinstatement_check, engine.competing_hold, checks.endoscopic_check (engine.endoscopic_rows 572)
- studio/validation/review_view.py:409, 436-440, 460 -> engine.distinct_lesions, reconcile.describe_act / lesion_words / service_label (modifier review and summary)
- studio/review.py:1384 reviewed_completeness, only when a code is reinstated -> engine.reviewed_completeness: from_jsonable ServiceInventory (3594); reconcile.reconcile (3600) with the FAILED_ATTEMPT regex (reconcile.py:831), technique regexes (905) and the examined_regions ANATOMY regex (741-763) over stored evidence
- studio/review.py:695-697 record_decision gate -> is_final (-> peer_review_held -> is_member_conflict) + effective_view -> _allowed/_actions
- studio/review.py:1202-1229, 1512 readiness/_review_state -> is_final, answers.date_confirmation_open (is_member_conflict), effective_view
- studio/review.py:2419 assessment_candidates -> candidates.candidates, and recorded_inventory -> gi.services.validate (2346). DORMANT: {} while STUDIO_OFFER_CONFIRMATIONS is False (review.py:2406-2407; cptstudio/settings.py:166).

### save

- studio/api.py:254 decisions -> review.record_decision (681): is_final (695); effective_view (697; review_view chain with listed_in_doubt/listed_contradicted); Decision(proposal_fingerprint) (716-720); refresh_state (724: readiness -> is_final, date_confirmation_open -> is_member_conflict, effective_view)
- studio/api.py:382 context, and studio/answers.py:835 for a details value -> jobs.change_context (3155): RoutingRun-exists refusal or review.can_resume (3177)
- studio/jobs.py:3195 -> make_context -> _bounded(gi.context.extract_context, revision.text, CONTEXT_REQUEST_SECONDS=15) inside the web request (481)
- studio/jobs.py:493, 500 _record_context in the web process -> gi.context.merge_user_values (487), gi.context.document_service_date_fact
- studio/jobs.py:3211 _settles_member_conflict -> gi.context.is_member_conflict twice (3151-3152) + _attempt_owed
- studio/jobs.py:3212 _run_answers -> _request_for -> provider.build_request(revision.text, legacy context date) (3076)
- studio/jobs.py:3213 _participants_owed -> is_member_conflict (249) -> participant chain or ASSESS; otherwise 3224 _queue_predict -> is_member_conflict (142)
- studio/jobs.py:3225 refresh_state (overlay chain). Then in the worker: stage_predict (935; 946-951 _route_child -> gi.detect.route; 953) and stage_assess (553, 559).
- studio/api.py:308 addenda: answers.addendum_detail -> review.effective_view (answers.py:668); review.invalidate_for_new_revision (api.py:353; refresh_state); jobs.start_pipeline (api.py:359) -> the full assess path on the new revision
- studio/api.py:278 confirm -> 409 CONFIRMATIONS_NOT_OFFERED before anything is read. The dormant review.confirm_finding would call change_context or reassess_after_confirmation (review.py:2449-2510).

### reload

- studio/customer_api.py:924 customer_state -> progress.date_held -> gi.context.is_member_conflict (progress.py:308)
- studio/customer_api.py:999 views_of -> review.effective_view (review_view chain: legacy ServiceInventory record; base_included -> listed_in_doubt/listed_contradicted)
- studio/customer_api.py:702 details_rows -> answers.details_needed -> _rows (is_member_conflict 535/570/629; questions.question_passages/service_passages over Assessment.services 512-515)
- studio/customer_api.py:610 code_rows -> questions.answered_away; _quotes -> review.evidence_spans (stored legacy acts' evidence); code_summary -> View.summary
- studio/customer_api.py:1004 review.reviewed_completeness -> engine.reviewed_completeness -> reconcile.reconcile regexes over stored evidence (when a code is reinstated)
- studio/customer_api.py:1013 answers.service_date_block -> is_member_conflict (answers.py:250), charge_date_problem (257)
- studio/customer_api.py:713 progress.encounter_progress -> date_held (308), review._derive_state (529, overlay chain), _document_states_a_date (575), _open_details -> details_needed + effective_view (584)
- studio/customer_api.py:1015 progress.checks_summary -> _held (160); final_assessment -> review.is_final (349) -> peer_review_held; _checks_outcome -> review.peer_review_held (387)
- studio/customer_api.py:989 recheck_block -> jobs.second_review_status (2545) -> _second_review_items -> review.reviewed_completeness (2363) + unresolved_items[].second_review marks (engine._routing_agrees) + Assessment.services spans; _second_review_bounds builds a Corti request on the excerpt (2517)
- studio/customer_api.py:804-810 readiness -> review.readiness (overlay chain) + review.approved_items (effective_view, questions.acts_of, evidence_spans)
- studio/customer_api.py:956 session_json and 979 list_row -> in_queue -> serializers.queue_reasons for EVERY encounter (open_questions_of 165, _decisions_waiting 167, coding_completeness 171, second_review_status 176); list_row also runs views_of per encounter (974)
- studio/serializers.py:1148 operator encounter_detail -> _context_facts predicates (110), _proposal_json effective_view per proposal (334), reviewed_completeness (406), _routing_json from the stored RoutingRun (1173), second_review_status (1187), readiness (1195), coding_completeness (1196), assessment_candidates (1161, dormant); operator list -> encounter_summary -> coding_completeness (189)

### export

- studio/api.py:475 create_report (approved) -> customer_api.readiness -> review.readiness (overlay chain, is_final, date_confirmation_open) + review.approved_items
- studio/reports.py:2024 generate_customer (holds the encounter row lock) -> customer_snapshot: customer_api.readiness again (1871); views_of -> effective_view (1874); answers.service_date_block (1878; is_member_conflict/charge_date_problem; prints the gi.context-made date); limitations (1879)
- studio/reports.py:1881 approved_export_items -> review.approved_items (effective_view; leaves out approvals the overlay blocks, review.py:548-549; evidence_spans from stored legacy acts), or 1890 code_rows for a draft (overlay, questions.answered_away, _qualifications)
- studio/reports.py:2033 customer_marker_digest (assessment, context, decision and answer ids; no legacy call); studio/api.py:500 download -> customer_artifact_current (marker only)
- studio/operator.py:326 operator report -> review.readiness -> reports.generate (1793) -> snapshot: readiness 714, effective_view 720, open_questions_of 721, coding_completeness 743, reviewed_completeness 746 (reconcile regexes when a code is reinstated), _services from the stored inventory 271-320
- studio/reports.py:922-923 _context_section -> gi.context.is_member_conflict / charge_date_problem
- studio/reports.py:555-556 _peer_reviews -> review.owed_peer_stages / peer_review_held -> jobs.peer_review_held -> is_member_conflict (338)
- studio/reports.py:739-740 prints the legacy RoutingRun's routing_version and routing_sha256

### peer_request

- studio/jobs.py:2337 stage_assess FIRST -> owed_peer_stages -> peer_review_held -> gi.context.is_member_conflict (338) -> _queue_peers
- studio/jobs.py:1605 stage_peer -> gi.context.is_member_conflict (PEER_HELD not_run)
- studio/jobs.py:1715 _peer_material -> _peer_codes(_cpt_studio_reading(first)): assess #1's OPEN Clarification rows and NEEDS_CLARIFICATION/EXCLUDED Proposal rows, made by validation.engine (1819-1848)
- studio/jobs.py:1835, 1898, 1905 -> review.question_identity (question ids)
- studio/jobs.py:1857-1858 _peer_reasons -> checks.CONFIRMATION_SOURCE/CONFIRMED_HEADING; 1872 _peer_text -> checks.MEMBER_ENTERED; 1816/1875 gi.context.USER_CONFLICT_NOTE prefix
- studio/jobs.py:1719-1720 frozen += sha256(cpt_studio) -> participant.build_peer_request -> prompt.peer_document, which requires exactly {open_questions, held, excluded} (studio/participants/prompt.py:389-411); peer.check_frozen (peer.py:258-280)
- studio/jobs.py:2268 stage_assess FINAL -> the full _assess_child legacy chain (553, 559)
- Member-asked bounded Corti second review: studio/api.py:454 -> jobs.request_second_review (2557) -> _second_review_blocker/_second_review_bounds (EARLIER_CONTEXT_VERSIONS 2480; _second_review_items 2485 -> review.reviewed_completeness 2363 + engine._routing_agrees marks + Assessment.services spans 2369-2373) -> refresh_state (2580)
- studio/jobs.py:2601, 2614 stage_review2 -> _second_review_items -> Corti build_request(revision.text[start:end], legacy date) -> _send -> ASSESS ':review2:<run>' (engine second-review merge, _select engine.py:435)

### install_or_ops

- ops/install.py:4468 phase_app RECOMPUTE_STATES (2218-2229) -> review.refresh_state for every encounter (overlay chain on legacy records; last install: 79 encounters, 0 changed)
- ops/install.py:1994, 2039 UNDO_HAZARDS (switch-back 4540/4624, rollback-app 5612/5777, CLOSE_STAGES 2186) -> gi.context.is_member_conflict, review.can_resume (2029), review._refused_run/current_decisions/_reviewable (2056-2074), answers.standing_answers (1971)
- ops/install.py:2162, 2171 CLOSE_STAGES -> jobs.may_have_reached_vendor, review.refresh_state
- ops/install.py:5194 phase_reassess -> reassess_retained (see reassess)
- studio/management/commands/evaluate_cases.py:48-51 -> claim_next/run_job (the whole legacy pipeline) + serializers.encounter_detail
- studio/management/commands/provision.py:18, 55-57 -> gi.profiles CATEGORY_NAME/CATEGORY_SLUG/PROFILES_VERSION (reference constants only)
- ops/gi4/battery.py:1739-1745, cost.py:98-138, replay.py:113-157, completion.py:67-69, observe.py:74-98 -> jobs._analyze_child/_merged_facts/_assess_child, gi.context.extract_context, gi.detect.route, gi.services.build (offline harnesses behind 58 test modules)
- Outside the tree: /home/claude/cpt-studio-completion-20261106/install/cmp/cmp_ctx.py (extract_context, _merged_facts, document_service_date_fact) is the pre-app gate (pre_app_s.sh:20)

## Reference and control rules that stay

- studio/gi/catalogue.py (gi-catalogue@2) is the coding rule table: code_profile covers/base/technique, entry, SUPPORTED, COMMON_BUNDLED, READ_UNDER, UNSUPPORTED_ACTS, UNRECONCILED_REGIONS, family_codes_act, includes_examination. It is keyed by gi.services ACT_KINDS (services.py:282) and used at reconcile.py:34-891, engine.py:3045-3103, review_view.py:448 and customer_api.py:726. Keep the rules, move them out of studio/gi, and either map Gemini's act vocabulary onto these kinds or re-key the table.
- studio/gi/profiles.py (gi-profiles@3) holds PROFILES (labels, required_facts, procedure flag), family_for_code numeric ranges, FAMILY_ORDER and CATEGORY_*. DETECTED_FAMILIES (profiles.py:93) currently means 'families routing recognises' and gates resolve_status detectability (engine.py:1594-1607); its meaning must be restated without routing.
- Evidence integrity: checks.code_scope/scope_check (checks.py:62-86); checks.exact_evidence/evidence_checks (91-143); review._check_result, which refuses inexact selected or support spans (review.py:774-792); review.evidence_spans, which re-checks each quote against the revision text (486-525). Per the directive, add attribute-level support: a quote alone proves nothing.
- CMS reference rules: checks.pfs_check, mue_check, endoscopic_check and pctc_consideration (checks.py:891-976); NOT_CONNECTED_CHECKS (1006-1014); duplicate_check (1017); reference_source_entries (1281-1294); studio/reference/*, which imports nothing from studio.gi (store.prefetched_lookup raises LookupError for any code not prefetched, store.py:157-169; passages.retrieve 513; tools.executor 78; importers).
- Required-fact and question rules, kept as rules: profile required_facts, checks.required_facts_check, fact_clarifications, FACT_LABELS and FACT_QUESTIONS (checks.py:623-760); catalogue questions in reconcile.documentation_clarifications (936-968); conflict question wording (924-933); service-date state, check and question (checks.py:1026-1104); same-day E/M and reinstatement gates (checks.py:765-862). Only their inputs move to the inventory.
- Combination rules, shared between the engine and the read-time overlay: engine.base_included, base_within, base_hold, base_within_hold, competing_hold, endoscopic_rows and distinct_lesions (engine.py:3045-3170; review_view.py:248-260, 572-702). Keep the rules and replace their cue predicates (engine.py:3069, 3075) with structured inventory flags.
- Reconciliation algorithm (coverage, bundling, read-under, inclusion) and the encounter checks built on it: reconcile.reconcile, uncounted, completeness, includes_through and inclusion_asks_no_code (reconcile.py:766-1023), plus inventory, unresolved, conflicts and attribution checks (1026-1125). Feed them events instead of cue strings and evidence regexes.
- Proposal assembly: engine._proposal bucket/status derivation (3250-3412); _excluded_early and _alternative (3469-3508); _fingerprint (3566-3570); _MemberAnswers (5302-5400); participant admission gates P-ADMIT in _Harness.merge (4289-4374). The legacy _select they call is replaced underneath.
- Approval controls: review.record_decision (681-725) requires a reviewer role in the encounter's workspace, a final assessment, an action the overlay allows, the exact ACKNOWLEDGEMENTS text (58-66, 711-715) and at most one modifier (59 or XS). Decision is append-only with a DB sequence (studio/models.py:394-424). Also keep decision carry/invalidation (review.py:975-1058) and the rule that the approved export exists only after readiness (customer_api.py:797-819; reports.py:1871-1873; a stale export answers 409, api.py:500-501).
- Tenant isolation: access.active_membership and scoped_encounter return 404 outside an active membership (access.py:12-35); writes require Membership.can_review (api.py:120-122); /ops/ requires an OperatorGrant (operator.py:57-62, 139-159); provider reuse lookups are scoped by encounter__workspace (jobs.py:730, 966, 1424, 2521, 2624); the CMS tool executor is per workspace (jobs.py:1074, 1551).
- Send discipline and send doors, reused for Gemini: jobs._send (1009-1099), _live_gate (1316-1325), _failed_before (624-637), the encounter-wide unknown-outcome block (review.py:1147-1152), Stop, mark_stale (2735-2845) and reconcile (2995-3035).
- Customer leak guards: customer_api FORBIDDEN and plain (89-101); customer_error (225-237); the ACTIVITY allowlist (839-856); audience 404 for operator artifacts (api.py:498-499); the ops/verification/customer-denylist.json scans.
- Installer controls: the ruled-mutation door (ops/install.py:272-347); migration_verdict, which accepts additive migrations only (4031-4161); worker-only credential mounts (2435-2445); the UNRUNNABLE_STAGES refusal (2198-2211, 4446-4452); blue/green switch and receipts.

## Semantic machinery the new path must not run

- The first read of every revision, studio/jobs.py:522-536 _analyze_child: gi.context.extract_context (534) and gi.detect.route (536). The mention gate (528 detect.service_mention_count, 531 services.mention_count) uses legacy vocabularies and needs a non-semantic size bound in its place.
- Date-change routing and the routing gates: studio/jobs.py:539-541 _route_child (gi.detect.route, called at 950); the RoutingRun-exists send gate (946-951); the context-save refusal (3177); the date-consistency refusal (790-791).
- The re-read in every assess, studio/jobs.py:544-564 _assess_child: gi.detect.route (553) plus validation.engine.assess (559) in FIRST, FINAL and AGAIN modes. This covers assess #2, answer recompute (3307-3341), reassess_retained (3376-3451), resume, review2 follow-up and context-save re-checks.
- Context re-extraction on save and on remake, studio/jobs.py:478-483 make_context: gi.context.extract_context in the web request (change_context 3195) and in _remade_context (835).
- In studio/validation/engine.py:163-226 assess: read_day comes from gi.context.charge_question_day(text) (207-208), which re-reads the text; gi.services.build (219) builds the inventory; the READ_DOCUMENTED_SERVICES fallback switch (44) still exists.
- Per-code status machinery in engine._select (1572-1725): checks.evidence_readings -> detect.status_for_span (checks.py:1299-1313); checks.routing_readings and resolve_status (243-482); _V2_judged_away; _unnamed_other and _undated_visit (engine.py:2702-2835); _other_service (2775-2802). Behind these sit the _VAL_/_V2_ readers over 30 function-local imports of private detect and cue names (checks.py:316-410, 1414-2560).
- The two-reader agreement arms: _held_unless_agreed and _second_reading (1616, 2002-2047); _agreed_not_done (2253-2268); _pa_one_cause_hold and _pa_* (2129-2300); doubted_by_routing_alone (1649); _second_opinion and its helpers (1834-1955, 2379-2671); _set_aside_attempts -> detect.closed_attempt_failure (1775-1815); _stated_not_done, _not_done_match and _another_roles_hold (766-981); _passages_elsewhere (1728-1763); _undecided (2407-2431).
- Evidence-support closures over structure.clinical_layout, services.report_family_at and services.current_statement (engine.py:1666-1692, 1766-1772). Every clinical_layout call hides a full reread through the heading-twin guard (structure.py:2062-2118: detect.route at 2081, services.build at 2118). Callers: engine.py:997, 1476, 1674, 1769, 2195, 2231 and reconcile.py:443.
- Act identity by evidence overlap and layout: engine._claimed, _competition and _same_claim (488-572, 984-1045).
- Encounter-level readings of routing: _encounter (procedure_day; 3005-3037, 2849-2918); _missed and _accounted_elsewhere (services.unproposed; 3645-3737); _unsupported (3740-3763); checks.required_fact_states (673-688); checks.separate_em_statement (788-793).
- The second-review eligibility mark from engine._routing_agrees and _po_* (1130-1512, set at 360), read by jobs._second_review_items (2358-2378).
- Semantic inputs inside reconcile: in match, NAME_ONLY_CUE (reconcile.py:138-141), ROUTING_CONTRARY_CUE and ROUTING_DOUBT_CUE (221), and technique_fits with the dilation regexes (166-198, 244). In reconcile.reconcile, HYPOTHETICAL_CUE (830), the FAILED_ATTEMPT regex (40, 831), listed_in_doubt/listed_contradicted (844-858), _read_under -> services.examined_regions ANATOMY regex (741-763, 875) and technique_fits (905). Also elsewhere, _done_through and placed_check (550-643).
- Base-rule cue predicates services.listed_in_doubt/listed_contradicted (engine.py:3069, 3075; services.py:293-302). They run at assess AND at read time on every effective_view (review_view.py:258-259).
- Read-time regex re-reads of stored evidence: engine.reviewed_completeness (3575-3622) re-runs reconcile whenever a code is reinstated. Callers: review.py:1384, customer_api.py:1004, serializers.py:406, reports.py:746, jobs.py:2363.
- Harness mention coverage, engine._Harness.missing/_read_as/_read_in (4747-4860), built from `located` records produced by services.build (218-223).
- The source of the member-date hold. EncounterContext facts are made by extract_context and merge_user_values (jobs.py:481, 487, 534) and read by is_member_conflict at jobs.py:142, 249, 338, 855, 935, 1605, 3024, 3151-3152; progress.py:160, 308; answers.py:250, 535, 570, 629; serializers.py:80-110; reports.py:922-923; review.py:929; checks.py:711-712, 749, 1057-1059; engine.py:207, 1531, 3518; reconcile.py:949; ops/install.py:2039. The predicates are utilities; the facts they read are legacy-made.
- Legacy content in vendor requests: Corti's service date (jobs.py:914, 953; _request_for 3068-3080); the review2 excerpt and items (2358-2378, 2614); the peer request's 'rule-based reading' (_cpt_studio_reading 1819-1908, _peer_material 1715-1720).
- Read-time readers of the legacy record shape: review_view._inventory (review_view.py:170-178), engine.reviewed_completeness (3594), questions.acts_of/question_passages/service_passages (questions.py:125-233), reports._services (reports.py:271-320). Each needs a versioned reader that does not call the legacy reader.
- Dormant legacy users, to remove or keep behind the code-level STUDIO_OFFER_CONFIRMATIONS=False (cptstudio/settings.py:166): candidates.py (73-590); engine._Confirmations and _shortfall (5045+, 4917-4945); reconcile.status_stated, held_section and whole_sentence (438-547); review.recorded_inventory (2331-2350).
- Legacy-reader coupling outside the request paths: jobs.ROUTING_CACHE_MODULES and release_routing_caches (567-585); installer UNDO_HAZARDS importing gi.context (ops/install.py:1994, 2039); ops/gi4 harnesses (battery.py:1739-1745, cost.py:98-138, replay.py:113-157, completion.py:67-69, observe.py:74-98, freeze.py:85-110).

## Utilities that read no clinical meaning

- gi.context stored-fact predicates: is_member_conflict (context.py:3429-3438), charge_date_problem and charge_date_own (1903-1924), documented_values (3398-3403). They read only a fact's origin and note prefix (USER_CONFLICT_NOTE 3406-3410). Keep them, or replace them with explicit fields, but feed them facts the new path writes.
- gi.context.merge_user_values (3467-3542) is the member-vs-document policy. It depends on the span subclasses _ElsewhereSpan, _BirthSpan, _DoubtSideSpan and _QuotedSpan (3286-3330), which the legacy date reader produces and which lose their type once stored. A Gemini date reading must supply the same per-span roles.
- gi.context.find_dates, date_from_match and compare_to_service (268-336) do explicit date parsing.
- gi.services.validate (services.py:8242-8288) checks exact passages at offsets, vocabularies and references. It is the integrity pattern to port to the event inventory, keeping inventory_problems semantics (engine.py:224-225, 352-354, 378).
- gi.services record types (ServiceInventory, DocumentedService, Act, Lesion, Conflict; services.py:1059-1165) are needed read-only to read existing legacy Assessment.services (review_view.py:176, engine.py:3594, review.py:2342).
- Wording helpers: reconcile.act_label, kind_label, service_label, quote, lesion_words, describe_act and service_for (reconcile.py:69-140); checks.fact_label and _join.
- studio/validation/questions.py imports nothing from studio.gi: fingerprint, instance, member_key, bind, group, acts_of, question_passages, service_passages, answered_away, missing. Keep it, with stable passage keys taken from the inventory.
- studio/bounded.py run_bounded runs forked, DB-free, CPU-bound work under a wall clock and memory limit. Keep it for deterministic validation; it must never host a network call.
- Text utilities with no clinical reading: sections.normalize_label and head_lines_end (sections.py:373, 1236); cues.rx, page_number_line and heading_shaped_line (cues.py:30, 382, 388).
- Participant machinery reusable for a Gemini adapter: participants/http.py (Vendor 64, default_session 69, build_request 207, finished_request 242, check_shape 277, verify/expand_original 285-322, post 356-417, describe 419-430); loop.py (recording 167, run 189); credentials._load and _parse (credentials.py:80-128); providers/base.py (canonical_body 40, verified_body 58, read_regular_file 83); replay.py (113-125); pricing.py (44-85); participants/reading.py strict JSON, schema, bounds and the verbatim Locator (read 235-267, bounds 423-444, Locator 449-502).
- jobs record writers and helpers: _record_context and _record_routing (491-512), as writers of the NOT NULL stand-ins; _retrieval (2185-2251); member_answers_of and answers_digest (3284-3304); _participant_input, _reread and _frozen (1987-2109); context_service_date (441-453).
- Review overlay mechanics: review.current_decisions and _overlay_inputs (219-278); review_view stored_from, Decided and service_answers; the readiness and state derivation (review.py:1199-1644). They stay unchanged once their inputs come from the inventory.

## Records to preserve

- EncounterContext (studio/models.py:201; ImmutableModel): legacy facts {value, origin, evidence, note} merged with member values; user_values; version (gi-context@5, jobs.py:49); sha256; document_date (214). Written only by jobs._record_context (491-500), from stage_analyze 789 and make_context 483. Baseline 96 rows across @1..@5, 43 of them current @1-@3 contexts that any stage remakes.
- RoutingRun (models.py:217; immutable): gi.detect.route JSON (gi-routing@12), sha256 and service_date, one row per (revision, version, sha, date). Written by jobs._record_routing (503-512) from 792, 951 and 2318. Assessment.routing is a NOT NULL PROTECT FK to it (291). Baseline 102 rows (gi-routing@3..@11).
- Assessment (models.py:286; immutable): context and routing FKs (290-291, NOT NULL); provider_run and second_run; profiles_version and engine_version; services, the legacy ServiceInventory JSON (302); completeness (303), including unresolved_items[].second_review and member_answers.applied; encounter_checks, unsupported, summary, reference_sources; participants (308) and retrieval (309), both outside the sha256; sha256. Written by review.persist_assessment (review.py:1085-1092). Baseline 157 rows across cpt-studio-validation@3..@10.
- Proposal (models.py:317; immutable): bucket, status, checks, evidence, support (339: matched service id, acts, source spans, origin, proposed_by), fingerprint (engine.py:3566-3570). Written by bulk_create (review.py:1094-1103). 2,157 rows.
- Clarification (models.py:346): mutable state open/answered/withdrawn and an answer FK to MemberAnswer. 259 rows.
- Decision (models.py:394; append-only; DB sequence studio_decision_sequence from migration 0003) and DecisionInvalidation (426): reviewer, reviewer_kind, exact acknowledgement, modifiers, proposal_fingerprint, carried_from. Written by review.record_decision (716-720), _carry_decisions (1051-1056) and _invalidate (728-730). 60 decisions and 2 invalidations: these approvals must be preserved.
- MemberAnswer (models.py:435; the question fingerprint at 459, db_default '') and MemberAnswerRevocation (467). Written by answers.save_details (820-833) and revoke_answer (894-895). 18 answers, 15 standing.
- ProviderRun (models.py:229; mutable): provider (20 chars), adapter_version (40), purpose (16, at 269); request_body, request_sha256 and contexts; raw response_bytes and response_sha256; usage and usage_basis; run_identity; service_date; scope (held, mode, continues, stopped_after_turn, excerpt); endpoint, requested_model, returned_model, response_id (273-276); reconciliation fields; reused_from. There is no cost column (cost is computed at read time, review.py:1987-2016). 229 rows, 204 sent; Corti usage is creditsConsumed (credits_sum 4.06).
- ProviderExchange (models.py:606) and ToolCall (632): raw bytes, hashes and usage per exchange, plus each tool call. Their existence gates participant reuse (jobs.py:1414-1427) and may_have_reached_vendor (2722-2732). 204 exchanges and 140 tool calls.
- Job (models.py:478): kind (10 chars, 493; astra_peer already uses all 10); idempotency_key, unique, 200 chars (494); state; attempts; deadline_at; stop fields; result, whose assessment id is read by the recompute and reassess lookups. 545 rows.
- ReportArtifact (models.py:513; immutable): content bytes, sha256, and snapshot_sha256 (the operator snapshot digest, or the customer decision-marker digest, reports.py:1904-1931); audience (db_default 'operator'). An approved export goes stale when the marker changes (api.py:500-501). 189 rows.
- AuditEvent (models.py:559; append-only), 1,170 rows. Also SourceFile (135) with the original file store (storage.py:45-79, sha256 re-verified on read), and SourceRevision (147: a plain Model whose write-once extraction goes through record_extraction 189-198).
- Encounter (models.py:105): current_revision, current_context and current_assessment pointers; user_values (member metadata); stopped_at and stopped_by; the cached state (review.refresh_state 1636-1644).
- Installation-wide records: reference tables ReferenceSource/ReferenceCodeFact (models.py:573) and PassageSource/ReferencePassage (651); WorkerBeat (704); OperatorGrant and OperatorRevocation (536); LoginAttempt (693); Workspace, Membership, User and Category (provision.py:54-95).
- FindingConfirmation (models.py:370): dormant, 0 rows.
- Outside the database: installer receipts /home/claude/cpt-studio-install-20261023/*.json (0600; the app receipt's 'replaced' pair is the switch-back target) with command logs; the pre-app pg_dump kept 0600 in the same directory (pre_app_s.sh:12-14). Credential copies /etc/cpt-studio/{corti,openai,anthropic}-credentials.env (10150, mode 0400; ops/install.py:99-118, 771-898). The owner's Gemini source /etc/cpt-studio-provider-sources/gemini.env with GEMINI_API_KEY (rulings 2026-10-23-cpt-studio-gi.md:2889-2890, 2930) is not handled by the installer yet.

## Hazards

- Every re-assessment re-reads the document with the legacy reader. _assess_child calls gi.detect.route (studio/jobs.py:553) and validation.engine.assess (559) in FIRST, FINAL and AGAIN modes alike. So assess #2, an answer recompute (answers.py:850, 900), a context save that re-checks (jobs.py:3212-3221), a Resume (2984-2989), a review2 follow-up (2608-2611) and the installer's reassess_retained (ops/install.py:5194) all re-read the text. No stored interpretation is reused.
- A hidden reread runs inside a web request on every metadata save. change_context -> make_context -> bounded extract_context (jobs.py:3195 -> 481) runs under the encounter row lock (3169-3170), then merge_user_values and document_service_date_fact run unbounded in the web process (493, 500). Reached from api.py:382, answers.py:835 and the dormant review.py:2507. A Gemini call cannot take its place there: the web has no credential file (ops/install.py:2440-2441), the budget is 15 s (settings.py:206), Gemini latency was 9.9-65.4 s (HARNESS.md:4470), and the web runs only 2 sync gunicorn workers with a 120 s timeout (deploy/gunicorn.conf.py:5-7).
- A hidden reread runs inside engine.assess: charge_question_day(text) re-runs context._context over the whole text (engine.py:207-208; context.py:1926-1933, 3355-3367) whenever no date is established, even though stored facts are passed in.
- A hidden full reread hides in structure.clinical_layout. Its heading-twin guard (structure.py:2062-2118) runs detect.route (2081), detect._analysis, status_for_span, services.passage_readings and services.build (2118). So any surviving call (engine.py:997, 1476, 1674, 1769, 2195, 2231; reconcile.py:443) re-enters the whole legacy reader.
- Semantic re-reads run at read time on reload, review and export. Every effective_view applies the services.listed_in_doubt/listed_contradicted cue predicates (engine.py:3069, 3075 via review_view.py:258-259). Whenever a code is reinstated, engine.reviewed_completeness re-runs reconcile with FAILED_ATTEMPT (reconcile.py:831), the dilation technique regexes (166-198 via 905) and the services.examined_regions ANATOMY regexes (services.py:7365-7372 via reconcile.py:741-763) over stored evidence text. This is reached from customer_api.py:1004, serializers.py:406, reports.py:746, review.py:1402 and jobs.py:2363, and it contradicts ruling interpretation (e) that reload and export read the persisted assessment.
- Reading a changed record shape fails quietly. review_view._inventory returns None for any Assessment.services it cannot rebuild as the legacy ServiceInventory (review_view.py:170-178), and _overlay_inputs passes None on inventory_problems (review.py:274-275). Base holds and summaries then silently stop being recomputed instead of failing.
- The legacy reader vetoes sending. The member-date hold is decided from facts made by extract_context and merge_user_values, through is_member_conflict at jobs.py:142, 249, 338, 855, 935, 1605, 3024 and 3151-3152. That predicate is a note-prefix test (context.py:3429-3438), so a new context record worded differently silently drops the hold, and a request can be built for a conflicting date.
- stage_participant has no hold check of its own (jobs.py:1476-1552). stage_predict's provider-disabled branch (932-933) runs before its hold check (935) and starts the participant chain (_after_predict 196-202). Both rely on _queue_predict upstream, so a Gemini stage placed in the chain must check the hold itself.
- Legacy content reaches vendor requests. Corti's request carries the legacy-read date (jobs.py:914, 953). The review2 excerpt comes from legacy inventory spans and marks (2358-2378, 2614). Every peer request carries assess #1's legacy-engine reading, hashed into frozen (1715-1720; peer.py:258-280). Changing any of these changes request bytes: retained answers stop matching (965-968, 1414-1427) and new paid sends follow.
- The two-reader exclusion safety disappears. Today exclusion requires the routing-era and documented-service readers to agree (engine.py:1610-1657, 2253-2268, 2334-2354), and the routing-era reader can only hold (1834-1955). An adapter that feeds one Gemini reading into both seams makes that agreement vacuous with no error.
- Decisions are keyed on exact legacy cue strings (services.py:285-298, 7338-7339; checks.py:260-307; reconcile.py:138-141, 221, 830; engine.py:1127). An inventory that does not emit them silently changes holds and exclusions.
- Approvals may not survive. Decisions carry only to an equal Proposal.fingerprint and only onto final assessments (engine.py:3566-3570; review.py:1024-1058, 1113-1115). The fingerprint carries no interpretation version, so a Gemini re-assessment either invalidates approvals (DecisionInvalidation) or carries one across interpreters wherever every fingerprinted field matches. Every addendum invalidates all current decisions (api.py:353).
- Member answers may stop applying. MemberAnswer.question hashes question wording and legacy inventory passages (questions.py:236-247; review.py:281-307; answers.py:823-827). Re-worded questions turn standing answers into ASKED_DIFFERENTLY or NO_LONGER_ASKED (questions.py:271-294), and codes excluded by 'Not documented' return to review.
- Schema: Assessment.context and Assessment.routing are NOT NULL PROTECT FKs (models.py:290-291), and the gate refuses AlterField (ops/install.py:4144-4145). The new path must keep writing an EncounterContext and a RoutingRun per assessment, and persist_assessment refuses a routing run of another revision (review.py:767-768).
- Rollback to cpt-studio:c2e53f8e7d33 has four problems. (1) It treats any context version outside EARLIER_CONTEXT_VERSIONS as current (jobs.py:73, 833) and re-assesses with the legacy reader on a save, Resume or answer recompute. (2) It reads a Gemini-shaped Assessment.services through legacy types and fails quietly (review_view.py:170-178). (3) Its worker dies on an unknown Job.kind because STAGES[job.kind] runs outside the try (jobs.py:2695), unless the installer's UNRUNNABLE_STAGES/CLOSE_STAGES run (ops/install.py:2136-2211, 4446-4452). (4) No undo hazard covers Gemini-made assessments (1963-2123; SHOWN_HAZARDS 2577).
- Legacy modules cannot simply be removed. Installer undo checks import studio.gi.context in the newer image (ops/install.py:1994, 2039), and every in-image script imports studio.review or studio.jobs, which import gi at load (review.py:29-30; jobs.py:28-29; answers.py:50). Deleting or forbidding the legacy modules breaks switch-back and rollback-app. 'No legacy reader on any path' must therefore be proven by call-path tests and operator evidence, not by import absence.
- A Gemini send occupies the whole installation. There is one worker and one installation-wide advisory lock (jobs.py:77, 1037-1040); queued jobs expire after 30 minutes (78, 2680-2683); a running stage older than 600 s is swept as dead (settings.py:207; jobs.py:2737); and the worker stop timeout is 600 s (ops/install.py:68). The trial client's 600 s deadline (gemini-trial/client.py:27) would be swept mid-call.
- mark_stale settles successors only for kinds in SENDING_PURPOSES (jobs.py:2744-2761). A new sending kind left out of it becomes CANCELLED (2814) while its run is settled UNKNOWN. A run reserved without an endpoint and without exchanges reads 'never reached the vendor' (may_have_reached_vendor 2722-2732; _finish_loop 1258).
- The unknown-outcome block is encounter-wide and provider-agnostic (review.py:1147-1152), so a Gemini unknown outcome blocks Corti, Astra and Fable until reconciled. jobs.reconcile distinguishes only primary from participant purposes (3022-3030), so a reconciled Gemini run would queue a re-predict.
- One transient failure can block a document for good. A failed request is never re-sent within the encounter (jobs.py:624-637), and http.post classifies every non-200 as failed (http.py:404-413), so a single 429 or 5xx permanently blocks that revision's interpretation until an addendum. No installation-wide auth/quota stop exists, although the directive requires one.
- http.describe reads usage, model and id from the top level of the body (http.py:419-430). Gemini's usageMetadata, modelVersion and responseId would be recorded empty. pricing knows only Astra and Fable (pricing.py:28-32, 74-85), and review.estimated_cost returns None for any provider outside PARTICIPANTS (review.py:1997).
- Adding 'gemini' to participants.PARTICIPANTS would silently read FABLE_MODE (participants/__init__.py:78). It would also make Gemini a code-proposal participant in engine inputs, the peer chain, Assessment.participants, assess keys, reassess_retained --participants (reassess_retained.py:45-51) and the access-check choices (participant_access_check.py:52, 70).
- The credential mount plan conflicts with the installer. gemini-migration/PLAN.md:42 plans to mount the Gemini credential into web and worker, but service_problems refuses any web bind mount (ops/install.py:2440-2441), so the web must never send.
- Key-in-URL: ProviderRun.endpoint is stored verbatim (http.py:412; models.py:273) and shown in the operator trace. The key must travel in the x-goog-api-key header (trial client.py:94), never in the ?key= query form.
- The customer guards do not name Gemini (customer_api.py:89-93; ops/verification/customer-denylist.json:13-16), so 'gemini-4-argon' passes every pattern. A bare 'argon' pattern must not be added either: argon plasma coagulation is GI vocabulary (cues.py:1130; services.py:236), and verbatim document quotes are printed unguarded on customer pages and downloads (customer_api.py:401-411; reports.py:1855-1856).
- Column limits are fixed because widening is an AlterField: Job.kind 10 (models.py:493; astra_peer already uses 10), idempotency_key 200 (494), ProviderRun.provider 20 (236), adapter_version 40 (237), purpose 16 (269), endpoint 200, requested/returned model 100, response_id 140 (273-276). Keys must also budget Resume's 44-character suffix (jobs.py:2984).
- Reload costs scale with the workspace. GET /api/session runs in_queue -> queue_reasons for EVERY encounter (customer_api.py:956), each running the overlay, coding_completeness and second_review_status. The list endpoint runs views_of per encounter (974). One approved export recomputes the overlay about six times under select_for_update (reports.py:1810, 2024). Any network-bound reader added to these paths multiplies.
- A draft customer export pairs the CURRENT context's date with the live assessment's codes (answers.service_date_block uses current_context, answers.py:234-259). Drafts are not gated by readiness (api.py:472-477).
- ProviderUnavailable subclasses Exception, not ValidationError (providers/base.py:23), and api_view does not catch it (api.py:90-104). jobs.second_review_status reaches get_provider (2508), so a misconfigured provider makes GET /api/encounters/<id> answer 500. A Gemini registry that raises the same way would do the same.
- Static scans have blind spots: modules named as strings (jobs.py:567-574); code embedded in strings (ops/install.py:1963-2123); the engine.gi_services attribute reached from review_view.py:176; 30 function-local gi imports in checks.py and 6 in engine.py (1142, 1224, 1412, 1527, 3515, 4925). A missing name fails only when its branch runs.
- Process-global lru_caches keyed by text are safe today only because stages run in forked children and run_job clears the caches (jobs.py:2711). Any Gemini result cache or reuse must be scoped by workspace, as provider reuse is (jobs.py:730, 966, 1424, 2521, 2624).
- Persisted legacy readings stay visible. The operator detail shows stored routing cues (serializers.py:231-252, 1173), and the operator report prints routing_version, routing_sha256 (reports.py:739-740) and the legacy documented services. Mixed-version encounters (assessments @3..@10, contexts @1..@5 at baseline) need explicit version labels.
- Ruling interpretation (f) says rollback compatibility is 'tested before the install', but the tree has only the syntactic migration gate (ops/install.py:4149-4195; ops/test_install_harness.py:985-1058). Nothing runs the c2e53f8e image against a migrated database.

