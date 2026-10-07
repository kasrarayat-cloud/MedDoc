# Adjudication of the retained synthetic voice verification

adjudication_attempt: 5
adjudication_job: 27c1bcba-f2e6-49a5-8af8-1ab64aeda415
source_commit: dedac1625032e32c7a149e6771be22e26c307eb1
adjudication_original_guard_sha256: 42358895e8a68131b6ce7819ccfe915d958ce2affd9983829a802a41317f921d
adjudication_original_outcome_sha256: 6fc960685082170a35a1f54704415c44739d1f3d6c8bac813fc43aacb30e2b70
adjudication_original_stop_sha256: 184074990461413262e25c00223ce8ea00c5097f1a6314b89eecf0524a86a406
adjudication_request_sha256: ede5b10d514a409a10d96124dcf2453d3f709587bc78e2da28914b4148998e92
adjudication_response_record_sha256: 8d346a50d5cb97b6ed7516dcfed9f5f703ef62ba67bc5dba11ec21123e1a31ae
adjudication_response_body_sha256: eea3beb5b5dc3c7327dfdbbca9883515668f16eee0ad8332a81c9aa96513f35f
adjudication_source_inventory_sha256: 2e045a4efa7f6fc60e56231823cd2c5e86d8d0cd456422d0303fcf4fde93188d
adjudication_evidence_sha256: d8276750d8c7e71c1a4fc99dfc2884b6404deb541f256123d794e40cb984ffa2
remaining_generation_attempts: 1
additional_transcription_attempts: 0
decode_tolerance_seconds: 0.25
permitted_continuation_case: soap-voice-generation

The previous committed batch stopped correctly at its first operator verification
failure. That outcome and STOP remain byte-identical, and the old guard is retained
as `run_one_guard-original-42358895.py`. The lead independently verified the raw
response, receipt, frozen recording and unchanged application tolerance, corroborated
by the separate read-only diagnosis. This committed diagnosis admits only the
already-declared final SOAP generation after ordinary transcript review/save; the
original declaration must also pin the reviewed repaired guard before execution.
No provider resend, cost reconciliation change, record rewrite or model installation
is authorized by adjudication.

The actual unchanged-main transcription succeeded once: HTTP200, Deepgram
`nova-3-medical`, request `01a1129d-84ad-76e1-8f04-69cb48516198`, client timeout90,
automatic retries0. Captured submitted bytes and the provider's metadata hash both
match the frozen synthesized recording: SHA256
`8bb6b53f2832ae830fc422e6fac366a383226fcb911e59a814466cb90809b8d7`,1130602bytes.
Receipt and usage agree; configured provider cost0.001837264600USD,
charge0.002755896900USD exactly1.5times; all billing audit checks pass and no held
reservation/unresolved job remains.

The operator required exact equality between two different measurements of the same
submitted recording. The unchanged application records container duration25.636236
seconds and decoder duration25.636seconds. Their absolute difference0.000236seconds
is below the unchanged `core/media.py` `DECODE_TOLERANCE_SECONDS=0.25` documented at
lines259-267 and enforced at480. The repaired operator verifier uses that exact
constant, requires both finite positive measurements at most300seconds, retains
both measurements, and preserves hash/byte-count/cost checks. No clinical, prompt,
provider profile or application source has changed.

Protected `evidence/005/adjudication.json` is a new read-only adjudication with
original failed records/hashes and actual receipt/response checks; it does not
replace the original failure. `evidence/005/adjudication-billing.json` retains the
full read-only billing audit. The raw transcript lacks the spoken question labels
and says “ankle strain” where the frozen script says “ankle sprain”. These transcription
differences remain visible. The ordinary explicit transcript review must restore
the four exact labels and correct that term against the fictional source recording;
raw and corrected texts, their hashes and exact differences are retained by the
application audit and operator evidence. No unreviewed transcript is adopted.

Only the already-declared fifth Anthropic generation, `soap-voice-generation`, may
continue after that ordinary review/save. The guard requires the specific committed
diagnosis, exact original failed outcome/STOP/evidence hashes and verified read-only
adjudication; all other failed or unknown outcomes remain blocking. It verifies the
application's `transcription.applied` audit against the retained raw transcript and
the frozen corrected notes before any provider key is loaded. The original technical
five-generation/one-transcription bounds and1USD generation exposure remain intact.

This is synthetic engineering evidence. Uploaded synthesized audio does not qualify
human microphone capture or patient use; structural Word export verification does
not claim native Microsoft Word rendering.

Independent protected diagnosis: `voice005-independent-diagnosis.json`, SHA256 `848884045a35f4645240a1346fbbc3c56bef2b24c55bc6293976f97b5f884b53`. This is corroborating read-only evidence; the retained failed outcome and exact scoped adjudication remain authoritative bindings above.
