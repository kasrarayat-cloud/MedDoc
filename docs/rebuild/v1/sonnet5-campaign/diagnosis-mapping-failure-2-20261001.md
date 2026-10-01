# Diagnosis: mapping failure 2 (2026-10-01)

reopen_stage: mapping
failed_attempts: 24
repair_commit: f8adebd9a30d16872c763b9cc0f0ca9431609a60

**What stopped the stage.** After reopening 1 (diagnosis `diagnosis-mapping-failure-1-20261001.md`, runner
`f55a1561`, CI green), the remainder's first send, attempt 24 (`mapping:f2-leave-checkboxes`, served `claude-sonnet-5`,
`end_turn`, 8,843 input / 109 output tokens, $0.018776), returned a well-formed proposal: all three fields kept, no
change, and a verdict for 24 of the form's 35 printed slots. It left 11 slots unclassified (the five checkbox controls
and their printed options of the 'Types of leave taken' multi-choice question, and two empty cells). The envelope rule
"every field and slot ID exactly once" refused the WHOLE response ("Mapping slot IDs must form one complete, disjoint
request-bound set."); the job failed and the stage stopped as a contract failure before the other eight sends. Nothing
was adopted; no unsafe change reached a mapping. Reproduced offline on `f55a1561` from the retained response.

**Repair** (`f8adebd9`, hold direction only). A duplicated ID or an ID the request does not contain still refuses the
whole response. An OMITTED field is held `uncertain` (it keeps its deterministic mapping and is never a target); an
OMITTED slot is held `uncertain` and appears as an unresolved review item the clinician must map or dismiss before the
mapping can be confirmed. Nothing is adopted from an omission. The request and its instructions are unchanged: replaying
attempt 24 on the repaired code, the compiled request equals the retained body and the SDK bytes equal the sent ones
(20,659), so no amendment is needed. On the repaired code the retained response returns the fields unchanged, 0
changes, 0 rejected, and the omitted slots as unresolved review items. The repair diff was refuted before this
reopening; its two LOW side effects were repaired in `a9a22a93` (a response classifying nothing is refused again,
as the parent refused it; an omission marks the proposal incomplete).

**What the next remainder can show.** The remainder is the eight declared sends not yet made
(`mapping:f2b-leave-checkboxes-owner`, `mapping:f3-selection-instructions`, `mapping:f4-exam-grid`,
`mapping:f5-negative-controls`, `mapping:f6a-long-answer`, `mapping:f6b-admin-missing`, `generation:f6a-long-answer`,
`generation:f6b-admin-missing`). Attempts 2 and 24 remain recorded stops, so the stage cannot pass. Model-assisted
mapping stays OFF in every installed profile; the sends run on the QA worker only.

**Not reopened, and why.** The runner's reopening check (A2) requires the named repair commit to touch at least one of
the files every attempt records (`ops/sonnet5_qa.py` `WATCHED_FILES`). The mapping-assistance modules that ran and were
repaired (`core/mapping_wire.py`, `core/mapping_assistance.py`, `core/destination_roles.py`) are not on that list, so
`f8adebd9` cannot pass it. The only later commit that touches a watched file, `a9a22a93`, does so through an unrelated
review-page change in `core/views.py`; naming it would satisfy the letter of the check while defeating its purpose,
which is a weakened stop rule. The remainder (eight sends, worst case about $2.1) is therefore not run. Adding the mapping
modules to the watched list cannot apply retroactively (attempts 2 and 24 record no hash of them), so a further mapping
measurement needs an owner decision: an amended runner with the wider watched list for a new allowance, or acceptance
that model-assisted mapping stays unqualified and off.

