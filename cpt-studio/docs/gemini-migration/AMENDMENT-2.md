# FINAL-V2 amendment 2: the interpreter is Claude Fable 5.2 (design, revised after refutation)

Session 31dfc45d, 2026-11-15, design round wf_e13a4dc8-aec (designer). Synthetic and development material only; nothing
was sent to any provider, no credential was read, no docker was run, no tree or worktree was edited, nothing under
`acceptance-a1/` but `DEV-EXCLUSION.sha256` (read by the replay tool) and no sealed set was opened.

Revised by the refutation judge (same session, 2026-11-15): the 32 findings of the four lenses (connector, truth,
replay, cost) are decided in `AMEND2-REFUTATIONS.md` beside this file; every change below carries the tag of the finding
that made it, `[R:<lens>-<id>]`; the text as refuted is `AMENDMENT-2-pre-refutation.md`. The judge read F3all and
F3long after their freeze (19:18:05Z and 19:38:01Z) and cites them where they settle a figure.

## Governing texts and what this amendment leaves alone

Governing, in this order: the owner directive of 2026-11-15 and its session interpretation (rulings file
`docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, lines 3373-3425), DECISIONS D275, then FINAL-V2 (D178-D182) as
AMENDMENT-1 (D208) amends it, with every ruling D178-D275. Where this text and a ruling disagree, the ruling stands and
this text is a defect.

Unchanged by this amendment: LOCAL_SCHEMA_2 (`contract/extract_schema.py`), the pass-2 LOCAL schema
(`contract/appraise_schema.py`), the claim templates, CONTROLS, CLAIMED and RANK, the settle truth table except one new
row-4 reason (section 4), the engine except the FactSet's reading of an overfilled slot (section 4), the store except
that slot rule, read time, D5's exclusion safety, P1-P9 of FINAL-V2 1.1, the owner's "no keyword reinterpretation and no
semantic veto" (5.7 measure 4), the sentinel's deny set, member answers, Corti/Astra/Fable 5.1 participants, approval
and customer confidentiality. No new database migration (section 8.6).

Paths below are relative to `cpt-studio/` in the built tree
`/home/claude/cpt-studio-completion-20261106/gemini-migration/trees/step8-195e06e90/` (git archive of 195e06e90; code
identical to a9bbc242c). Batch paths are relative to `gemini-migration/`.

## Read first: the evidence, and the short-document check

### E.1 What the probes measured (every figure cited to its batch)

| measure | value | source |
|---|---|---|
| pass-1 request, Claude tokenizer | 44,740-45,155 input tokens on the 8 short notes; 52,150 and 52,175 on the two 19.4 KB notes; fit 44,467 + 0.493 x characters | `anthropic-project/batches/F2high/MANIFEST.json` pass1.usage |
| pass-1 answer, short notes (551-1,417 chars, 9-25 units) | 8 of 8 STOP; 10,663-21,002 output tokens, of which thinking 5,766-12,807 (54-61%); 87.7-181.5 s; $0.784512-$1.201320 | F2high MANIFEST; `probe.anthropic_usage.output_tokens_details.thinking_tokens` in each frozen body |
| pass-1 answer, long notes (A-note8 19,398 chars / 181 units; C-C2MEM-023 19,460 / 182) | MAX_TOKENS at 64,000 output tokens (thinking 29,109 and 40,743); 491.5 s and 523.6 s; $2.977200 and $2.977400 | F2high MANIFEST and bodies |
| pass 2 without a schema (Gemini-shaped request, JSON text) | 6 of 6 answered; every one refused at replay ("verdicts[0] has a field the schema does not allow ('id')") | F2high; PLAN.md 17:10Z entry |
| pass 2 with structured outputs over `appraise_schema.LOCAL_SCHEMA` | 6 of 6 answered and read; 6,239-7,737 input, 6,252-12,562 output (thinking 3,137-8,832), 49.3-108.7 s, $0.299992-$0.562784; fit input 4,024 + 37.1 x claims; output 84-155 tokens per claim (mean 109) over 68-106 claims | `anthropic-project/batches/F2high-p2/MANIFEST.json` |
| pass 1 with structured outputs over LOCAL_SCHEMA_2 | HTTP 400 `invalid_request_error`, "The compiled grammar is too large, which would cause performance issues..." | `anthropic-project/batches/F1schema/cases/A-v1_two_lesions_one_site/r1/pass1.error-body` |
| throughput, output tokens per second end to end | 115.6-131.6, median 121.5, over the 8 short and 2 long pass-1 sends and the 6 pass-2 sends | F2high, F2high-p2 (output_tokens / seconds) |
| answer text density | 2.23-2.31 characters per answer token (output minus thinking) | F2high bodies |
| answer composition (Fable, compact JSON, whitespace 1.0-1.6%) | key names 50-58% of characters, quoted values 35-40%, empty arrays 2-4% (brackets only) | F2high bodies, counted in this session (key names with their quotes and colon, string values, `[]`); the BRIEF's Gemini figures (keys 44-52%, empty arrays 10-12%, words 20-29%) used another count |
| model returned | `claude-fable-5-2` on every send; message ids `msg_...` | F2high/F2high-p2 bodies (`modelVersion`, `responseId`) |
| usage fields returned | `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `cache_creation{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}`, `output_tokens`, `output_tokens_details.thinking_tokens`, `service_tier`, `inference_geo`, `speed` | F2high bodies |
| appraisal health, 6 complete notes | established 38/39 to 52/56 (0.93-1.00, median 0.97); controls not rejected 0-2 of 28-49 pairs (max 4.1%); missing 0 | `devsets/replay-F2high-p2/*/r1/health.json` |
| costs | F2high $15.878128 (16 sends); F2high-p2 $2.435728 (6 billed sends); F1schema $0; Gemini D2low $1.718684, D2medium $4.2778 | the batches' SUMMARY.json |
| pass 1 at `max_tokens` 128,000 with a cached instruction (probe tree `probe-fable52-v2`: the probe plus two slot sentences) | long notes: A-note8 79,758 output tokens (thinking 35,841), 615.5 s; C-C2MEM-023 73,224 (31,604), 566.3 s; both STOP. Short notes: 9,716-22,135 output, 79.8-190.6 s; 0 overfilled slots in the 10 answers [R:truth-T4][R:replay-R1][R:cost-F-COST-1] | `anthropic-project/batches/F3all` (frozen 2026-11-15T19:18:05Z) MANIFEST and bodies |
| pass-2 claim sets | short notes 41-108 claims; A-note8 756 and C-C2MEM-023 711, both refused at door 0 under the 640 bound (`not_built`: "more than the 640 one request may carry") [R:truth-T4][R:replay-R1][R:cost-F-COST-1] | F3all MANIFEST |
| pass 2 of the long notes under a bound of 1,000 (probe tree `probe-fable52-v3`, `CLAIM_BOUND_SHA256` 3fe08a5c...) | 756 / 711 claims; input 38,113 / 37,844; output 77,483 / 70,263 (thinking 43,623 / 38,435): 102.5 / 98.8 tokens per claim, of which answer text about 45; 590.7 / 536.9 s; established 336/340 and 317/322; controls not rejected 0/303 and 2/288 [R:truth-T4][R:replay-R1][R:cost-F-COST-1] | `anthropic-project/batches/F3long` (frozen 2026-11-15T19:38:01Z) MANIFEST and bodies; `devsets/replay-F3long/*/r1/health.json` |
| caching as F3all measured it | a 1-hour TTL (`cache_creation.ephemeral_1h_input_tokens` 44,466 on the first write; `fable_record.py:112`), so its later reads are 1-hour reads; the pass-1 prefix read at exactly 44,466 tokens by 9 later sends [R:cost-F-COST-5] | F3all bodies |
| the probe's body encoding | `json.dumps(body)` in insertion order (the schema's declared property order); the built connector sends `providers.base.canonical_body` (sorted keys) [R:replay-R7] | `probes-fable/fable_record.py:128`; `studio/providers/base.py:40-42` |

The probe connector was `probes-fable/fable_record.py`: record_v2 unchanged, Gemini-format requests translated to
Anthropic (system = the Gemini systemInstruction text, one user string, `max_tokens` 64,000, `output_config.effort`
high, `stream` true, no sampling field, no fallback) and Anthropic's answer text returned inside a Gemini-format
envelope. Its recordings are therefore Fable's answers but not Anthropic's raw stream bytes.

### E.2 The short documents (the owner's mid-run request, relayed again for this round)

Eight of the ten probe documents are short. Read first-hand from F2high, F2high-p2, their replays and scores:

- Pass 1 answered 8 of 8 within 182 s; pass 2 (with its schema) answered and read 6 of 6 within 109 s. Per complete
  short note both passes cost $1.19-1.76 (mean $1.44) and took 157-290 s.
- Two of 8 were refused whole by the slot rule. Scanned first-hand (overfilled SLOT arrays, `extract_schema.ATTRIBUTES`):
  A-v2 `events[1]` (E2) `technique.device` = cold_snare supported, hot_snare negated, electrocautery negated; A-v6
  `anatomy[0]` (Y1) `organ` = cecum supported, ascending_colon supported. (The BRIEF's "v6 anatomy subtype" is Gemini
  low's slip, `anatomy[2].subtype`; Fable's v6 slip is Y1's organ.) Neither is a confusion of two acts: each is several
  values the document states of one object, which a single-valued slot cannot hold.
- Outcomes, 19 rows on the 6 complete notes: as scored, 14 correct, 4 unnecessary holds, 1 wrong READY
  (`devsets/score-F2high-p2/summary.json`). Two of those five are measurement artifacts, verified in this session:
  A-v5 45380's wrong READY (the BRIEF's first-hand finding; section 6) and B-fb10 45330's hold (section 5.3: the replay
  tool hands C-10 no R1 word runs, the pipeline does). Replayed with the pipeline's word runs
  (`build-v2/amend2/verify/replay-F2high-p2-wordruns`, score `.../score-F2high-p2-wordruns`, rows sha256
  `fa573459...`): 15 correct, 3 unnecessary holds, 1 wrong READY (A-v5); with section 6's scorer rule, 16 correct,
  3 unnecessary holds, 0 wrong READY, 0 wrong exclusion, 0 dropped question, READY recall 5 of 8.
- So short documents do have problems, none of them a wrong READY or a wrong exclusion: whole-answer slot refusals
  (2 of 8; section 4), three unnecessary holds (section 5), and cost and latency of about $1.4 and 3-5 minutes each
  (section 7).
- The refutation's short-document check (`AMEND2-REFUTATIONS.md`, "Short documents") found that this amendment, as
  first written, gave short notes new problems, each repaired below: an overfilled slot read through the attribute's
  whole domain could word a documented colonoscopy as not documented or a complete enteroscopy as incomplete, and could
  switch off K4 on an A-v6-shaped note (4.3) [R:truth-T2][R:truth-T5][R:truth-T3]; a declined request was re-sent,
  paid, by the first Resume after a release, and its member read "Nothing was sent" (1.5) [R:connector-CONN-1]
  [R:truth-T6]; a short note cut at the output limit was told it is too long (1.5) [R:truth-T7]; an error-first stream
  held the installation as a substituted model (1.6) [R:connector-CONN-4]; a failed Fable reading could never be
  retried (9) [R:connector-CONN-5]; a crashed short note stayed stuck for up to 24 minutes (1.12) [R:connector-CONN-7];
  production short notes cost 23-43% more than "with caching as measured" (7) [R:cost-F-COST-5]. F3all's 8 short notes,
  read with two slot sentences close to 2.1's items 1 and 2, finished both passes (pass 1 79.8-190.6 s, pass 2 24.4-94.8
  s, 41-108 claims, far inside every bound and deadline) with no overfilled slot; scored as F2high-p2 was, 22 correct,
  4 unnecessary holds (the same four as F2high-p2) and 1 wrong READY (the same A-v5 artifact); with the measurement
  fixes of 5.3 and 6, READY recall 7 of 10 (`devsets/score-F3all`; fb10 replayed by the judge with the pipeline's word
  runs, `build-v2/amend2/verify/replay-F3all-fb10-wordruns`: 45330 READY, 45331 EXCLUDED, as on F2high-p2).

### E.3 What was not read

`anthropic-project/batches/F3all` (started 2026-11-15T18:34:20Z, tree `probe-fable52-v2`: the probe plus two slot
sentences, `max_tokens` 128000, a cached instruction) was unfrozen while this was first written, and only its plan and
its tree's diff were read then (the freeze-before-reading rule, FINAL-V2 7.6). F3all froze at 19:18:05Z and F3long
(`probe-fable52-v3`: the same with pass 2's claim bound at 1,000) at 19:38:01Z; the refutation judge read both after
their freeze (E.1's added rows), and they are the evidence for sections 3, 7, 8.2 and 11.3 as revised. Both measured a
near neighbour of INSTRUCTIONS_3 (2.1), never this text: D2 measures this text [R:truth-T4][R:replay-R1]
[R:cost-F-COST-1].

---

## 1. The connector, for both passes

### 1.1 Where it lives and what it is called

A new kept module `studio/interpretation/fable_adapter.py` (step F1). It sits beside `adapter.py`, outside
`contract/` and `engine/`, because its SSE reader holds event-name constants that
`tests/test_guard_static.py:no_word_lists` refuses inside those packages; `interpretation/sentinel.py:KEPT` gains it.
It imports only `participants.http`, `participants.reading`, `participants.credentials`, `providers.base`, the
`contract` builders and readers, and `studio.types` (as `adapter.py` does: D17 holds). `adapter.py` (Gemini) stays in
the tree, dormant (sections 8 and 9).

New names are added beside the old ones, never in their place: `interpretation/__init__.py`'s rule ("v1's names and
values stay byte-identical, because the 17 retired v1 modules and their tests read them for good", FINAL-V2 5.0). About
25 test files read `interpretation.MODEL` and `interpretation.PROVIDER` as Gemini's (among them
`tests/test_interpretation_adapter.py`, `test_pipeline_interpret.py` and the retired module's
`test_interpretation_prompt.py`), so those two keep their values and `adapter.py` is not edited at all.

| name | value | beside |
|---|---|---|
| `interpretation.PROVIDER_V3` (ProviderRun.provider of new runs) | `'anthropic'` (9 of 20) | `PROVIDER = 'gemini'`, kept |
| `interpretation.MODEL_V3` | `'claude-fable-5-2'` | `MODEL = 'gemini-4-carbon'`, kept |
| `interpretation.ADAPTER_VERSION_V3` | `'anthropic-messages@cptstudio-interp-1'` (37 of 40) | `ADAPTER_VERSION_V2`, kept for stored runs |
| `interpretation.READ_PROVIDERS` | `('anthropic', 'gemini')`: every interpreter provider whose runs an installation may hold | - |
| `fable_adapter.NAME`, `fable_adapter.MODEL` | `interpretation.PROVIDER_V3`, `interpretation.MODEL_V3` | `adapter.NAME`, `adapter.MODEL` (unchanged) |
| `fable_adapter.ENDPOINT` | `https://api.anthropic.com/v1/messages` | `adapter.ENDPOINT` |
| `fable_adapter.API_VERSION` | `'2026-10-21'`, its own constant and part of what `ADAPTER_VERSION_V3` names: a test pins it to the value recorded beside `ADAPTER_VERSION_V3` in `interpretation/__init__.py`, never to the participant's, so a changed `anthropic-version` is a new adapter version (8.4); each run records the value it sent in `scope.api_version` [R:replay-R8] | - |
| `fable_adapter.EFFORT` | `'high'` (D275) | thinkingLevel |
| `fable_adapter.MAX_TOKENS` | `128000`, both passes (section 3) | maxOutputTokens 65536 |
| `fable_adapter.BODY_KEYS` | `{'model', 'max_tokens', 'stream', 'output_config', 'system', 'messages'}` | Gemini's three keys |
| `fable_adapter.VENDOR` | `http.Vendor(label='Anthropic', request_id_header='request-id', describe=describe, complete=complete)` | `adapter.VENDOR` |

### 1.2 The request

Both bodies are built purely from the revision (and, for pass 2, pass 1's stored bytes), as now:
`fable_adapter.build_extraction_request` keeps `adapter.build_extraction_request`'s steps (`adapter._document`,
`adapter._unframed`, the NotBuilt reasons) and `fable_adapter.build_appraisal_request` keeps
`adapter.build_appraisal_request`'s five steps, with the body builders below in place of `extract_prompt.request_parts`
and `appraise_prompt.request_parts`, and its own `_finished` (`adapter._finished`'s rules, with `http.finished_request`
given this module's NAME and `ADAPTER_VERSION_V3`, where adapter's names Gemini's). NotBuilt, AppraisalRequest,
`_same_request`, `_document`, `_unframed` and the NotBuilt effects are imported from `adapter.py` unchanged (one copy).

Pass 1, `contract/extract_prompt.py:request_parts_fable(framed_text)` (new; the Gemini `request_parts` stays for the
dormant adapter):

```
{"model": "claude-fable-5-2",
 "max_tokens": 128000,
 "stream": true,
 "output_config": {"effort": "high"},
 "system": [{"type": "text", "text": INSTRUCTIONS_3, "cache_control": {"type": "ephemeral"}}],
 "messages": [{"role": "user", "content": [{"type": "text", "text": FRAMED}]}]}
```

`INSTRUCTIONS_3` is section 2.1's instruction; `FRAMED` is `extract_prompt.framed(text, pages, kind)` exactly as today
(the user turn is the framed document alone, D1). The cache breakpoint is section 7.2's.

Pass 2, `contract/appraise_prompt.py:request_parts_fable(turn)` (new):

```
{"model": "claude-fable-5-2",
 "max_tokens": 128000,
 "stream": true,
 "output_config": {"effort": "high", "format": {"type": "json_schema", "schema": appraise_schema.LOCAL_SCHEMA}},
 "system": [{"type": "text", "text": appraise_prompt.INSTRUCTIONS}],
 "messages": [{"role": "user", "content": [{"type": "text", "text": TURN}]}]}
```

`TURN` is the user turn `appraise_prompt.build_request` writes today (framed document, cards, claims; FINAL-V2 2.4).
The schema is a deep copy of LOCAL_SCHEMA under `APPRAISAL_LOCAL_SCHEMA_SHA256` (F2high-p2 sent this object and
Anthropic accepted it, `''` enumeration member included; it sent it in its declared key order, while the connector sends
the canonical body, whose keys are sorted at every depth, so the shipped schema lists its properties in another order
than the measured one: 2.2) [R:replay-R7].

Headers, set at send time and never stored: `x-api-key` (from the credential, 1.11), `anthropic-version`
`API_VERSION`, `content-type: application/json`, and `anthropic-workspace-id` when the credential file names one
(`anthropic_fable.FableParticipant._post`'s rule). The `anthropic-version` value (never the key) is recorded on the run,
`scope.api_version` [R:replay-R8].

Never sent: `thinking` (Fable 5.2 thinks always; omitting it is adaptive), `temperature`, `top_p`, `top_k` (400 on
this API version), an assistant prefill, `tools`, `tool_choice`, `stop_sequences`, `metadata`, `fallbacks` and any
`anthropic-beta` header (D275: no fallback model), any member value, filename or participant output (D1), the PDF
original (D12).

`fable_adapter.body_kind(body)` replaces `adapter.body_kind`: a body is sent only when it equals
`request_parts_fable(turn)` of its own user turn for pass 1, or `appraise_prompt.request_parts_fable(turn)` for a turn
of 2.4's form (`adapter._card_ids` and `adapter._claim_lines` reused; the framed-document check that
`adapter._appraisal_document` makes through the Gemini `extract_prompt.request_parts` is made through
`extract_prompt._is_framed`, so no Gemini pin is read on the Fable path). `http.check_shape(body, MODEL,
BODY_KEYS)` runs first (the model field is now in the body, as for the participant). The request's sha256 is
`providers.base.request_sha256` of the stored body through `http.finished_request`, unchanged.

### 1.3 The send

One exchange per run, `fable_adapter.InterpreterF.send_loop` (the structure of `adapter.InterpreterV2.send_loop`,
kept): `participants.loop.run` with `max_exchanges=1`, no tool executor called (`_no_tool_calls`, `_no_follow_up`,
`_no_tools` reused), a member's Stop asked once right before the send (`adapter._halt`), a continuation refused
(`NOT_CONTINUED`). The live interpreter `FableInterpreter._exchange` re-verifies the body, reads the key at send time
with `participants/credentials.py:load_anthropic_credentials`, and makes one `participants/http.py:post` under its
unchanged discipline (no retry, no redirect, no proxies, watched socket, the deadline checked per 64 KiB chunk, capped
read). `post` already streams (`session.post(..., stream=True)` and `_read_capped`'s `iter_content`), so the SSE bytes
are read as they come and kept whole as the response bytes.

One additive change to `participants/http.py` (step F1; byte-identical behaviour for Corti, Astra and Fable 5.1, which
pass no hook): `Vendor` gains `complete: Optional[Callable[[bytes], bool]] = None`. When `vendor.complete` is set and
the response is a 200:
- after the body is read whole, `complete` False makes the exchange `outcome='unknown'`, `sent=True`,
  `http_status=200`, error `INCOMPLETE_STREAM` ("The request reached Anthropic, but its answer stream ended before its
  end event. The outcome is unknown; reconcile it before any new attempt.");
- a read that stops early for any reason - a connection reset or a broken chunk (requests' `ChunkedEncodingError` or
  `ConnectionError` raised inside `iter_content`, the common mid-stream cut: a chunked body cut without its terminating
  chunk raises before `post` sees an end), the deadline (`_Watch`, `DEADLINE_READING`) or the byte cap - is the same
  unknown exchange with its own error, and `_read_capped` hands back the chunks read before the stop instead of dropping
  them [R:connector-CONN-6][R:connector-CONN-2].
In both cases the bytes read so far are kept as `response_bytes` with their sha256 - the operator's evidence for the
reconcile; P-6 never reads an unknown exchange - and no usage is recorded: 1.4's `describe` gives a usage only for a
stream that reached `message_delta`, where Anthropic's usage is final, so a cut run is unpriced in the report and
counted at its bound by the harness, never priced at its `message_start` count [R:connector-CONN-3][R:cost-F-COST-3].
Without the hook (Gemini's vendor and the participants) every path is as today. `adapter.py`'s Gemini vendor passes no
`complete`.

### 1.4 Reading the stream into one answer

`fable_adapter.assemble(raw) -> (message, '', '') | (None, code, why)`, pure, used by `describe`, `complete`,
`answer_text`, `classify` and replay alike:

1. The bytes are strict UTF-8; lines end with `\n` (a `\r\n` is read as `\n`); events are separated by one empty line.
   A line opening with `:` is a comment and skipped. Each event has at most one `event:` line and exactly one `data:`
   line; any other field name, a second `data:` line, or a `data:` value that is not `participants.reading.strict_json`
   refuses the stream (code `json`). The event name, when given, must equal `data["type"]`.
2. `ping` events are skipped anywhere. An event type this reader does not know is skipped and counted
   (`unknown_events`, kept in the read record for the operator; Anthropic documents that new event types may appear).
3. The first counted event is `message_start` (exactly once) or an `error` event (rule 7); a stream whose first counted
   event is neither names no model (code `model`: P-5's "or none") [R:connector-CONN-4]. `message_start` carries
   `message.type` `message`, `message.role` `assistant`,
   `message.content` `[]`, `message.model`, `message.id` (kept when it is 1-140 visible ASCII characters), and
   `message.usage`.
4. `content_block_start` opens block `index` = the number of blocks opened so far; its `content_block.type` is `text`
   (with `text` `''`), `thinking` (with `thinking` and `signature` strings) or `redacted_thinking`. A `fallback` block
   is code `model`. Any other block type (`tool_use`, `server_tool_use`, a citations-bearing text block, ...) refuses
   (code `content`). `content_block_delta` must name the open block: `text_delta` only in a text block (its `text`
   appended), `thinking_delta` and `signature_delta` only in a thinking block (kept, never read); any other delta type
   refuses (code `content`). `content_block_stop` closes the open block; no block stays open at `message_delta`.
5. `message_delta` (exactly once, after every block closed): `delta.stop_reason`, `delta.stop_sequence`,
   `delta.stop_details` (a refusal's `category`, read only as `participants.reading.vendor_word`, never the
   explanation), and `usage`, merged over `message_start.usage` field by field (Anthropic's `message_delta` usage is
   cumulative).
6. `message_stop` ends the stream; any counted event after it refuses (code `content`).
7. An `error` event ends the stream wherever it comes, before or after `message_start`: `{"type": "error", "error":
   {"type", "message"}}`; the message is never kept in a record or a sentence; its `error.type` is the stream's outcome
   by 1.5's precedence [R:connector-CONN-4].

`complete(raw)` is True exactly when the bytes end, after rule 1's parse, with `message_stop` or an `error` event; any
other end (EOF mid-stream) is incomplete. `describe(raw)` returns `(usage, model, id)` from the assembled stream - the
usage only when a `message_delta` arrived (Anthropic's usage is final there); a stream cut, ended early or ended by an
`error` event records none, its `message_start` usage staying readable in its kept bytes - or from an error body
(`{"type": "error", ...}`, no usage) for a non-200; it never raises (`http.described`'s contract)
[R:connector-CONN-3][R:cost-F-COST-3].

The envelope, `fable_adapter.answer_text(request, raw, purpose)`, in this order, each refusal an
`extract_read.refuse('envelope', why)` in CPT Studio's words (no provider or model named, D22): the request is an
`ADAPTER_VERSION_V3` request of this provider; the stream assembles; `message.model` is exactly `fable_adapter.MODEL`
(= `interpretation.MODEL_V3`; checked first
of everything the answer says, D13); no fallback block and no `usage.iterations` entry whose type starts with
`fallback` (`anthropic_fable._fell_back`'s rule, copied by reference to its test vectors); `stop_reason` is `end_turn`;
at least one text block. The answer text is the text blocks joined in order. Pass 1 then takes
`participants/reading.py:sole_object` (one JSON object alone or alone in one ```json fence; JSON mode constrains
nothing, harness-3's rule) before `extract_read.read`; pass 2's text goes to `appraise_read.read` as it stands
(structured outputs constrain it). `fable_adapter.read_extraction` and `read_appraisal` keep `adapter.read_extraction`
and `adapter.read_appraisal`'s structure (version, kind, same-request checks), with this envelope.

### 1.5 Classification

`fable_adapter.classify(outcome, http_status, response_bytes)` keeps `adapter.classify`'s contract (None for an outcome
that is not definite; a `Classification` otherwise, the same dataclass) and its precedence (the body's named error
before the HTTP status), with Anthropic's vocabulary. The effect column is `interpretation/holds.py:EFFECTS`; the
second column is this round's vocabulary.

Precedence for a 200 stream, in this order, so no two rows of the table can claim one stream [R:connector-CONN-4]:
(1) a `message_start` naming another model or none, a fallback block, a `fallback*` usage iteration, or a stream whose
first counted event is neither `message_start` nor `error` (1.4 rule 3): HOLD `model`, whatever follows; (2) an `error`
event, wherever it comes: its `error.type` decides by the rows below, so an error before any `message_start` (an
overload as the stream opened, the case Anthropic documents error events for) is FAILED, retry later, never HOLD
`model`; (3) a stream that does not assemble (1.4 rules 1-6): FAILED; (4) `stop_reason`.

| what came back | effect | word | what follows |
|---|---|---|---|
| 200, a complete stream, model `claude-fable-5-2`, no fallback, `stop_reason` `end_turn`, text present | ANSWERED | answered | read; a reader refusal makes it FAILED (`holds.classify`'s `refused`) |
| `stop_reason` `max_tokens` | TOO_LONG | too long | never re-sent for a member (C5, `jobs._settle_outcome`); worded as a reading that reached its output limit, never as a document too long (below) [R:truth-T7] |
| `stop_reason` `refusal`, any category | HOLD, reason `declined` (new) | hold | the answer is never read and never re-asked of another model (D275); an operator releases the installation; the hold is request-bound (below): its identical request stays blocked for members after the release [R:connector-CONN-1] |
| `message.model` absent or another model; a fallback block; a `fallback*` usage iteration | HOLD, reason `model` | hold | P-5, unchanged |
| `stop_reason` `tool_use`, `pause_turn`, `stop_sequence`, none, or any other value | FAILED | refused | recorded retry door (FINAL 11.3) |
| a stream that does not assemble (1.4 rules 1-6) | FAILED | refused | retry door |
| `error` event or error body, `error.type` `authentication_error`; or HTTP 401 | HOLD `auth` | hold | operator |
| `billing_error`; or HTTP 402 | HOLD `quota` (payment sentence) | hold | operator |
| `permission_error`, `not_found_error`; or HTTP 403, 404 | HOLD `permission` | hold | operator |
| `invalid_request_error`; or HTTP 400 or any other 4xx but 413 and 429 | HOLD `refused` (new) | hold | operator |
| `rate_limit_error` (an error body with HTTP 429, or a stream error event) | FAILED | retry later | retry door; no automatic retry (D11) |
| HTTP 429 whose body does not name `rate_limit_error` | HOLD `quota` | hold | operator (D39's fail-closed reading) |
| `request_too_large`; or HTTP 413 | FAILED | refused | that request only (AMENDMENT-1 A16's I10 rule) |
| `overloaded_error`, `api_error`, `timeout_error`, any other type; or any 5xx; an unread redirect | FAILED | retry later | retry door |
| a stream that ended before `message_stop` without an error event; a read cut by a connection error, the deadline or the byte cap | UNKNOWN (transport, 1.3: its bytes kept, no usage) | unknown | reconcile (6.9) [R:connector-CONN-6][R:connector-CONN-2] |
| nothing left (never connected, Stop, gates) | NONE | - | nothing was sent |

Why each hold. A 400 on a body this adapter pins is a refusal of every request of this version or of the account, not of
one document: the measured 400 (F1schema) refused the request form itself; Fable refuses every request of an
organization below 30-day retention with a 400; AMENDMENT-1 7.3 (A20's classification, the A16 hold) records that
Anthropic has answered an exhausted credit balance with HTTP 400 `invalid_request_error`, and its participant rule
already holds on any 4xx but 413 - the same answer that would hold the installed site's Fable 5.1 participant if a
development or acceptance batch ran the shared account dry (7.5) [R:replay-R5]. A 404 here names the model or endpoint, the same for every request. A model's refusal is a hold because D275 says
so; while it stands it also stops a run of paid declines across uploads (a decline after output began is billed). Its
release ends the installation's pause, never the block on the declined request (below) [R:connector-CONN-1]. A 429 is a
rate limit only when Anthropic says so by its error type; Google's bare 429 was a spending cap (D39), so an unnamed 429
holds.

Never a paid resend into a hold or a loop, by the existing doors (kept) and one new rule: a standing hold stops every
request of both passes before anything is built (`jobs._interpreter_or_pause`, `jobs._send_gates`,
`holds.paused_reason`); an identical failed request is not resent without a recorded retry
(`jobs._interpretation_failed_before`, `released_for_retry`); a TOO_LONG answer is never re-sent for a member; a request
whose answer set a request-bound hold is never re-sent for a member, before or after the release (below)
[R:connector-CONN-1]; an UNKNOWN blocks the encounter until reconciled (`jobs._unreconciled_unknown`), and the one new
attempt a member's reconcile allows is a paid resend that member asked for (FINAL 6.9, unchanged); there is no automatic
retry anywhere (`InterpreterV2.send_loop`'s rule, kept).

**Request-bound holds [R:connector-CONN-1].** As built, `_interpretation_failed_before` skips every hold ("which an
operator's release ends") and `retry_target` releases only FAILED and TOO_LONG runs, so after `interpreter_hold
--release` (which ends every standing hold at once) the first Resume or Retry of a declined document sent the
byte-identical request again, paid, declined again and paused the installation again. A hold is request-bound when the
answer that set it began as a 200 stream and says something about that request rather than about the account, the
version or the model: reason `declined` (`stop_reason` refusal), and any hold an `error` event set after `message_start`.
For such a run, on both passes: `jobs._interpretation_failed_before` returns it for its own identical request (as it
returns a FAILED or TOO_LONG run), so a Resume records the not-resent run; `retry_target` releases it only for an
operator's recorded override (`retry_reading(override=True)`, the override C5 already gives a cut-off answer); and
`retry_reading` refuses members with RETRY_DECLINED ("This document's reading was declined, so the same request is not
sent again."). Every other hold (a 401, 402, 403, 404 or 400 body, an unnamed 429, a substituted model) is about the
account, the version or the model: its release lets the next Resume send, as today. A new upload of the same text is a
new encounter and a new member act: it may be declined and billed again, and its hold pauses the installation again -
the residual, stated, and visible to the operator, whose release report names each declined run.

**What the member whose run set a hold reads [R:truth-T6].** PAUSED_MESSAGE ("... is paused on this installation.
Nothing was sent. ...") is untrue for the run whose answer set the hold: that document was sent and, for a decline after
output began, billed. `jobs._settle_outcome` and `mark_stale`'s settled path word that run from the run itself: a
request-bound hold's run ends its stage FAILED with DECLINED_MESSAGE ("This document was sent for reading, and the
reading was declined, so nothing was suggested for it. It is not sent again."; progress situation `declined`, action
`none`); any other hold's run ends CANCELLED with HOLD_SET_MESSAGE ("This document was sent for reading, and no usable
reading came back; reading documented procedures is now paused on this installation. Resume once it is available
again."), which progress reads as the paused phase; PAUSED_MESSAGE stays for every run a standing hold kept unsent. No
sentence names a provider or a model (D22), and the customer denylist tests run on the new ones.

**A reading cut at its output limit [R:truth-T7].** `max_tokens` keeps C5's effect (TOO_LONG: never re-sent for a
member; an operator's recorded override may), but running out of output tokens does not show that a document is long:
Gemini at high spent its whole response thinking on an 823-character note (BRIEF item 3). So the member is told what
happened, never a cause the run does not show: progress gains the situation `cut_off` ("The reading of this document
reached its output limit before it was complete, so nothing was suggested for it. If the document is long, shorten it
or split it, then upload it again.", action `new_document`), `retry_reading` refuses it with RETRY_CUT_OFF ("The reading
of this document reached its output limit before it was complete, and the same request would most likely stop there
again, so it is not sent again. If the document is long, shorten it or split it, then upload it again."), and
`INTERPRET_CUT_OFF_MESSAGE` and `APPRAISE_CUT_OFF_MESSAGE` say the output limit was reached and drop "the document is
too long". The size bound (`INTERPRET_MAX_CHARS`) and the claim bound keep the `too_long` sentences: there the length is
the cause. D2 and D3 report each pass-1 answer's output and thinking by document size, so a short note's tail is
measured (G-SIZE).

`interpretation/holds.py` (step F1):
- `REASONS` gains `REFUSED = 'refused'` and `DECLINED = 'declined'` (`InterpreterHold.reason` is a plain CharField of
  20, no choices: no migration; `studio/models.py:InterpreterHold` gains the two constants); `REASON_TEXT` gains
  "requests of this version were refused as invalid" and "the model declined to answer a request; it was not read and
  nothing was re-asked of another model". `adapter.HOLD_REASONS` (Gemini) is left as it is; `fable_adapter.HOLD_REASONS`
  is (auth, permission, quota, model, refused, declined), and the test that pinned `holds.REASONS` equal to
  `adapter.HOLD_REASONS` pins it to the union of the two (`holds.Outcome.__post_init__` checks a hold's reason against
  it).
- `classify(state, http_status, response_bytes, *, refused, purpose, adapter_version)`: the new keyword dispatches to
  `fable_adapter.classify` for `ADAPTER_VERSION_V3` and to `adapter.classify` for the Gemini versions, so a stored run is
  classified by the adapter that recorded it (refute-cb-r1 CB1-1, TRIAGE G2-02). `classify_run` and
  `jobs.interpretation_effect` pass `run.adapter_version`.
- `record(run, outcome)` sets a hold only for a run of the current adapter version; a stored run of another version
  returns the hold its answer set, if any, and never sets one (a Gemini quota answer never pauses Fable).
  `jobs._record_unsettled_holds` filters `adapter_version=interpretation.ADAPTER_VERSION_V3`.
- `request_bound(hold)` answers the rule above from the hold and its run; `release` returns, and `interpreter_hold
  --release` prints, each hold it ends with its reason, run, encounter and the first 16 hex of the run's request sha256,
  and says for a request-bound one that its request stays blocked for members [R:connector-CONN-1].
- `_check_run` accepts a run whose provider is in `interpretation.READ_PROVIDERS` (today it requires
  `interpretation.PROVIDER`, which would refuse every Fable run).
- `mode()` is unchanged (`settings.GEMINI_MODE`, the interpreter's mode setting; 1.11).
- The hold's `vendor_status` is the Anthropic error type or the refusal category (lowercase, at most 40 characters,
  `fable_adapter._TYPE = [a-z][a-z_]{0,39}`); `violations` stays `[]`.

### 1.6 Model exactness

`message_start.message.model` must equal `claude-fable-5-2` exactly, read before anything else the answer says; a
`message_start` naming another model or none, or a complete stream that opens with neither `message_start` nor an
`error` event, is HOLD `model` and the answer is never read. A stream that opens with an `error` event carries no answer
and no model: it is classified by its error (1.5's precedence), so a transient overload is never read as a substituted
model and never pauses the installation [R:connector-CONN-4]. F2high and F2high-p2 recorded exactly `claude-fable-5-2` on
every send, so the exact-string rule is measured, not assumed. No fallback can occur (none is requested), and a
fallback block or iteration still holds. `READ_MODELS` for `ADAPTER_VERSION_V3` is `('claude-fable-5-2',)`.

### 1.7 Usage and cost

`describe` records the merged usage dict as Anthropic states it (all fields of E.1, unchanged) with
`usage_basis='provider_reported_tokens'`. `participants/pricing.py` (step F5) gains `FABLE_52 = 'claude-fable-5-2'`
with `{'input': 8.00, 'cache_write': 10.00, 'cache_read': 0.20, 'output': 40.00}` US dollars per million tokens, as of
the claude-api reference cached 2026-11-03 (the 5-minute write is 1.25 x input); the build step checks these against
Anthropic's pricing page and, if they differ, the page wins and a DECISIONS entry records it. `_fable_52(usage)`:
`input_tokens` (which excludes cache tokens), `cache_creation_input_tokens`, `cache_read_input_tokens`,
`output_tokens` (thinking included); a usage whose `cache_creation.ephemeral_1h_input_tokens` is above 0, or whose
`ephemeral_5m_input_tokens` differs from `cache_creation_input_tokens`, or which carries `usage.iterations`, has no
estimate (no rate is recorded for it; fail-closed, as `_gemini` refuses unpriced tokens). A run whose stream never
reached `message_delta` has no usage at all (1.4's `describe`): the report counts it unpriced, and every ledger of the
harness counts it at its bound, never at its `message_start` count [R:connector-CONN-3][R:cost-F-COST-3]. The thinking count
(`output_tokens_details.thinking_tokens`) is reported beside the estimate and never priced apart. The reference gives
no dated change for this model, so the rates are undated and `on` is not read; a published change becomes a dated entry
as Gemini's are. `estimate_loop` with one exchange is `estimate`. Gemini's
entries stay and price Gemini's stored runs by the model their request named (TRIAGE G2-05's reasoning).

### 1.8 What is frozen per exchange; replay byte for byte

Frozen per run and per exchange (unchanged columns): the stored request body and its canonical sha256; the raw SSE
bytes as received and their sha256 (`ProviderRun.response_bytes`, `ProviderExchange.response_bytes`, turn 1); the HTTP
status, latency, usage, `request-id` header, message id and returned model. The answer, its settle and its assessment
are a pure function of those bytes, the revision text and the versions (`assemble` is pure), so a stored answer is read
again with no request, and a cache hit or miss changes only the usage fields inside the frozen bytes.

`interpretation/replay.py` (step F1) gains `ReplayInterpreterF(_Recordings, fable_adapter.InterpreterF)`: recordings
at `<GEMINI_REPLAY_DIR>/anthropic/<request sha256>.sse` (`_Recordings.recorded` takes the folder and the suffix from
its interpreter instead of `adapter.NAME` and `.json`), the raw stream of a complete 200 answer; returned with
`sent=False`, `usage={}`, `usage_basis='historical_replay_not_new_usage'`, the model and id `describe` reads. The
replay applies `complete` too, so a recorded stream that is not complete replays as UNKNOWN, the path a live one takes.
The recording harness (step T, section 10) freezes each 200 body at `cases/<id>/r<k>/anthropic/<sha>.sse`, the replay
layout, before anything reads it (FINAL-V2 7.6), and only complete 200 streams become replay files.

### 1.9 Request sha, keys and doors (FINAL-V2 7.4 for Fable)

Unchanged in mechanism (`jobs._interpret_key`, `_appraise_key`, `_appraise_parts`): `interpret:<revision>:gemini-events@3`
and `appraise:<revision>:<extraction run>:<first 16 hex of the appraisal request's sha256>`, the same lengths as today
(115 and 99 characters before suffixes). The appraise stage's doors keep FINAL-V2 7.4's order: 0 the claim bound
(`claims.CLAIM_BOUND_V3` = 1,000 on this path, 8.2 [R:replay-R1][R:truth-T4]; TOO_LONG); 1 an inventory read for this
extraction run and versions; 2 a stored SUCCEEDED answer to the identical request in the same workspace, reused with
`usage_basis='reused_retained_result_no_new_usage'` (`jobs._retained_interpretation`); 3 the unknown-outcome block; 4
the failed-before door - a FAILED or TOO_LONG run, or a run whose answer set a request-bound hold (1.5) - except a run
released for one recorded retry [R:connector-CONN-1]; 5 `_live_gate`; 6 the interpreter mode and the hold (`_interpreter_or_pause`); 7 one exchange, no tools,
`claude-fable-5-2` only. The interpret stage's doors (`jobs.stage_interpret`) are unchanged. The doors match a stored
answer by provider, adapter version, request sha256 and mode, so a Gemini answer is never reused for a Fable request.

### 1.10 Stop, resume, reconcile

Kept: Stop is observed before each send (`jobs._send`, `_stop_requested`; `InterpreterF.send_loop` asks once); a Stop
between the passes leaves pass 1's answer stored and Resume sends pass 2 only (FINAL-V2 7.4). A send in flight is not
cut by a Stop: a cut stream is UNKNOWN (a reconcile and an encounter-wide block) and Anthropic may still bill what was
generated, so a running exchange finishes within its deadline (1.12). The stale sweep settles a dead worker's run from
its recorded exchange only when that exchange is SUCCEEDED with HTTP 200 and a checking sha256
(`jobs._settle_from_exchange`, P-6); `jobs._settle_from_exchange` and `_record_unsettled_holds` call the describe and
classify of the run's own adapter version (`fable_adapter.describe` for `ADAPTER_VERSION_V3`). An incomplete or cut
stream - an EOF before `message_stop`, a connection reset, the deadline or the byte cap - is recorded `unknown` with the
bytes read so far and no usage (1.3), so P-6 never reads it as an answer and no report prices it as one; its partial
bytes and `request-id` are the operator's evidence for the reconcile (`:after-reconcile:<run>`), after which a new
attempt is a paid resend the member asked for, as today [R:connector-CONN-6][R:connector-CONN-3].

### 1.11 The credential and the installer

The interpreter uses CPT Studio's existing Anthropic credential (D275): `settings.ANTHROPIC_CREDENTIALS_FILE`, read by
`load_anthropic_credentials` (`ANTHROPIC_API_KEY`, optional `ANTHROPIC_WORKSPACE_ID`), mounted read-only in the worker
at `/run/cpt-studio/anthropic-credentials.env` from `/etc/cpt-studio/anthropic-credentials.env` (the session
interpretation (a)). The web never mounts it (`service_problems`' rule).

`cptstudio/settings.py` (integration owner): the interpreter's mode and replay directory keep their settings,
`GEMINI_MODE` and `GEMINI_REPLAY_DIR` (env `CPT_STUDIO_GEMINI_MODE`, `CPT_STUDIO_GEMINI_REPLAY_DIR`): the names are
historical and set the interpreter whatever its provider. Renaming them would touch 42 references in 14 test files
(`grep GEMINI_MODE tests`) and `holds.mode()`, which the v1 chain's suites also read, for no safety gain; the rename
goes with the retirement entry (section 9). `GEMINI_CREDENTIALS_FILE` is read by nothing on the path.
`fable_adapter.get_interpreter_v2()` reads at call time: `disabled` None (the stage pauses), `live` needs
`ANTHROPIC_CREDENTIALS_FILE` (ProviderUnavailable otherwise), `replay` needs `GEMINI_REPLAY_DIR`, whose `anthropic/`
folder holds the Fable recordings (its `gemini/` folder keeps Gemini's).

`ops/install.py` (step F8): `INTERPRETER` becomes `{'name': 'anthropic', 'source': PROVIDER_SOURCES/anthropic.env,
'target': ETC_DIR/anthropic-credentials.env, 'mounted': '/run/cpt-studio/anthropic-credentials.env', 'file_env':
'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE', 'mode_env': 'CPT_STUDIO_GEMINI_MODE', 'replay_env':
'CPT_STUDIO_GEMINI_REPLAY_DIR', 'replay_dir': '/app/tests/fixtures/interpretation', 'module':
'studio.interpretation.fable_adapter', 'loader': 'load_anthropic_credentials', 'setting': 'ANTHROPIC_CREDENTIALS_FILE',
'required': ('ANTHROPIC_API_KEY',), 'optional': ('ANTHROPIC_WORKSPACE_ID',)}`, the same source, target and mount as
`PARTICIPANTS['fable']`. The worker binds the file once when the Fable participant or the interpreter is live (one bind
target); `--interpreter-mode` keeps its choices and the reading of the worker's configured mode (install.py:7172) is
unchanged. With one shared credential, `holds_interpreter_key` (install.py:7181-7186) no longer tells whether the
interpreter holds a key of its own: verify (`interpretation_evidence`, 7236-7237) expects the shared file whenever the
Fable participant or the interpreter is live, and reports a bind only when neither is, so an install with the
participant live and the interpreter disabled or in replay (the installer's own advice at 7232-7233) verifies clean;
D14's rule (the key in the worker only) is unchanged [R:replay-R3]. The installer no longer copies or mounts
`gemini.env`; an existing `/etc/cpt-studio/gemini.env` on a host is left untouched and reported (deleting a key copy is
the owner's, class d).

The opt-in access check (`studio/management/commands/participant_access_check.py:_single_flight`, run by the installer
after the new worker starts) takes the installation-wide provider lock that `jobs._send` holds for a whole send, now up
to 1,320 s. It waits for that lock, polling, for up to the interpreter's send deadline plus 60 s before it refuses
("Another provider request is in flight"), and the installer's access-check timeout covers that wait, so a reading in
flight does not fail an install [R:cost-F-COST-8].

### 1.12 Timeouts and deadlines, from the measured latencies

| setting | today | new | from |
|---|---|---|---|
| `INTERPRETER_SEND_DEADLINE_SECONDS`, `APPRAISER_SEND_DEADLINE_SECONDS` | 510 | 1,320 | 128,000 tokens at 100 tok/s (13.5% below the slowest measured 115.6) = 1,280 s, plus 40 s for connect, prefill and the stream's tail; the slowest measured rate cuts 128,000 tokens at 1,107 s. A send the deadline cuts before Anthropic ends it is UNKNOWN, never TOO_LONG (1.5; its bytes kept, its cost unknown): it needs a stream that would run past 1,320 s - 128,000 tokens below about 97 tok/s, 100,000 below about 76 - where the largest measured answer is 79,758 tokens and the slowest measured rate 115.6 (F3all, F3long: 129-131 on the long notes). D1-D3 record every send's rate; if the slowest falls below 110 tok/s, the deadline is re-derived before A at 128,000 tokens at 80% of that rate plus 40 s, with the rows below following it [R:connector-CONN-2] |
| `INTERPRETER_READ_TIMEOUT_SECONDS`, `APPRAISER_READ_TIMEOUT_SECONDS` | 480 | 1,320 | the read timeout bounds each wait for a byte; no inter-event gap was measured (the probe read with 1,800 s), and up to 40,743 thinking tokens can precede the first text, so a shorter wait could cut a live answer into UNKNOWN; the deadline bounds the whole exchange (`_Watch`). D1 records the longest gap (section 11) |
| `JOB_DEADLINE_SECONDS['interpret']`, `['appraise']` | 560 | 1,380 | the send, `LOOP_RECORDING_SECONDS` (15) and 45 s of stage work |
| stale threshold for `interpret`, `appraise` | `STALE_RUNNING_SECONDS` 600 | new `STALE_RUNNING_SECONDS_BY_KIND = {'interpret': 1440, 'appraise': 1440}`; 600 for every other kind | above the stage deadline; read by `jobs.mark_stale` per kind and by `jobs._check_loop_time` (today `min(JOB_DEADLINE_SECONDS, STALE_RUNNING_SECONDS)`, which would requeue every reading stage forever at a 1,320 s send). The per-kind threshold alone would leave a short note's stage, whose send lasts at most about 3 minutes, busy for up to 24 minutes after a worker crash (Resume, Retry and Reconcile all refused while busy). So `work()`'s first sweep, at the worker's start, settles every RUNNING job whatever its age: at most one worker runs (ops/install.py's I-worker: the old one is stopped before the new one starts), so a starting worker has no live peer and every running job is a dead worker's; the periodic sweep keeps the per-kind threshold [R:connector-CONN-7] |
| `ops/install.py:STOP_SECONDS['worker']` | 600 | 1,500 | outlasts a reading stage, so a deploy's `docker stop` lets the stage finish instead of turning its send UNKNOWN; an install may wait up to 25 minutes |
| `jobs.QUEUE_DEADLINE` | 30 min | 60 min | one worker runs one job at a time (`run_worker` -> `jobs.work`); a long note's two passes can hold it for about 20-27 minutes (section 3), so a job queued behind two of them would expire ("expired before it could start; resume") |
| interpreter `max_response_bytes` | 4 MiB | 16 MiB (`INTERPRETER_MAX_RESPONSE_BYTES`) | the raw stream carries one JSON event per delta; its size per output token is unmeasured (the probe kept no raw stream). D1 measures bytes per output token; if a 128,000-token stream would exceed 16 MiB at that rate, the cap rises before D2 |

Latency a member sees: a short note's two passes took 157-290 s (F2high + F2high-p2) and 110-286 s (F3all); a 19.4 KB
note's pass 1 took 566-615 s (F3all; up to 1,107 s at 128,000 at the slowest measured rate) and its pass 2 537-591 s
(F3long), about 18-20 minutes for both passes - not 514 s for pass 2 as first estimated [R:cost-F-COST-1]. While it
runs, the single worker runs nothing else.

---

## 2. The answer form

### 2.1 Pass 1: JSON mode, the shape in the instruction

Measured: neither provider accepts design v2's pass-1 schema as a decoding constraint (Google's complexity refusal,
D1-D1t; Anthropic's grammar refusal, F1schema), and Fable filled LOCAL_SCHEMA_2 written into its instruction on 8 of 8
short notes, every answer schema-valid (F2high: all 8 passed the reader's JSON and schema stages; 2 then stopped at
bounds). Pass 1 therefore goes in JSON mode, as the probe did, with these exact changes to
`contract/extract_prompt.py` (step F2), giving `INSTRUCTIONS_3`:

1. TECHNIQUE: "device: the device the document names for this act; a device the document says was not used for this
   act is that device's fact negated." becomes "device: the device the document names for this act. When the document
   also says that other devices were not used for this act, the slot still holds the named device alone; a negated
   device fact is for a device the document says was not used when it names no device used for this act." (The
   current clause is what produced A-v2's slip: it asks for a negated fact per denied device in a one-fact slot.)
   FACTS' sentence "A slot holds at most one fact; ..." is kept as it is.
2. ANATOMY: "type is the alteration or absence, and organ the organ it concerns;" becomes "type is the alteration or
   absence, and organ the one organ it concerns: an alteration or absence the document states of two or more organs
   is one anatomy entry per organ, each citing the units that state it;" (A-v6's slip).
3. Withdrawn [R:truth-T8]: the TARGETS change first written here ("structure ... also when that is tissue rather than a
   lesion (mucosa, wall), and then lesion stays empty") cannot release B-fb05 45380 - a biopsy's `target.structure` is
   never claimed (`engine/requirements.py:CLAIMED` claims it for drainage and EUS injection only, l.733-734), so it
   settles unappraised, and the bundling readers `engine/coverage.py:_same_lesion` and `_apart` read only
   `target.lesion` and `target.places` - and its "lesion stays empty" would leave lesion-linked tissue acts (a biopsy of
   a lesion's mucosa, a lift injection under a lesion) with a silent lesion. TARGETS is unchanged (5.2). Items 1, 2, 4
   and 5 stand, so `INSTRUCTIONS_3` carries four changes.
4. VALUES' heading line: "One line per list of values; the response schema gives each field its list." becomes "One
   line per list of values; the answer shape below gives each field its list."
5. A new last part, replacing the closing line `_TAIL`: "ANSWER SHAPE\nThe answer is one JSON object that satisfies
   this JSON Schema exactly: every object has exactly the properties listed, all required, and nothing else; an
   enumeration lists every allowed value; an array whose "maxItems" is 1 is a slot and holds at most one fact.\n" +
   `jsonschema.canonical(extract_schema.ANSWER_SHAPE_2)` + "\n\nAnswer with the JSON object only.\n".

`extract_schema.ANSWER_SHAPE_2` (step F2, derived mechanically like RESPONSE_SCHEMA_2 was) is LOCAL_SCHEMA_2 with
`"maxItems": 1` added to the array node of each of the 38 SLOT attributes (`Arity.SLOT` in `ATTRIBUTES`) and nothing
else changed; a test proves that difference node by node. It is shown, never validated: the reader validates
LOCAL_SCHEMA_2, and an overfilled slot is section 4's item-level finding, never a schema refusal.

The probe tree's parenthetical "(a contradicted fact's value is no_value)" is not taken (a Gemini-only token, 2.3). The
F3all probe's two slot sentences quote a development document's words ("a cold snare; no hot snare and no
electrocautery", "the cecum and the ascending colon were removed"); FINAL-V2 2.3 forbids quoted examples and
development-case phrases in the instruction (`extract_prompt`'s docstring: "meanings are described, never surface
forms"; 2a's scan test), so items 1 and 2 state the same rules described. The 2.3 scans run on `INSTRUCTIONS_3`.
F3all therefore measures a near neighbour of this text, not this text; D2 measures this text.

Measured size: the probe's instruction is 119,146 characters, of which 89,759 are LOCAL_SCHEMA_2's canonical JSON
(1,436 schema nodes); about 44,470 tokens of the pass-1 request are this fixed part (the intercept of E.1's fit).

### 2.2 Pass 2: structured outputs over the LOCAL schema

Pass 2 sends `appraise_schema.LOCAL_SCHEMA` as `output_config.format` (1.2's body). Measured: with it 6 of 6 answers
were read (F2high-p2), and 10 of 10 in F3all and F3long; without it 6 of 6 broke the schema (F2high). Every one of those
answers was made under the schema in its declared key order (`claim`, `verdict`, `attached`, `qualifiers`,
`evidence`); the connector sends the canonical body, sorted at every depth (`attached`, `claim`, `evidence`,
`qualifiers`, `verdict`), and the cached reference does not say whether structured outputs generate properties in the
order the schema lists them. The shipped order is therefore unmeasured until D1 and D2, which send it through the
tree's connector; if it lowers G-HEALTH, the remedy is property names whose sorted order is the intended generation
order, as `gemini-appraisal@3`, never a body that is not canonical (the request sha256 is the canonical body's)
[R:replay-R7]. The pass-2 instruction
(`appraise_prompt.INSTRUCTIONS`) is unchanged byte for byte; it names no provider, response schema or Gemini form. The
appraisal's text is read by `appraise_read.read` unchanged (no `sole_object`: the format constrains it).

### 2.3 What happens to the Gemini form

- `extract_schema.RESPONSE_SCHEMA_2` and `appraise_schema.RESPONSE_SCHEMA` are not sent by Fable's requests; they stay
  in the tree for the dormant adapter, with their pins `RESPONSE_SCHEMA_SHA256_V2` and
  `APPRAISAL_RESPONSE_SCHEMA_SHA256` under the @2 / @1 labels. The @3 / appraisal@2 labels pin no RESPONSE schema.
- The `no_value` token (`jsonschema.NO_VALUE`, `from_gemini`) exists only in the probe trees, never in the built tree;
  nothing is removed. `''` stays the empty enumeration value in LOCAL_SCHEMA_2 and in the pass-2 LOCAL schema, which
  JSON mode and Anthropic's structured outputs both accept (F2high-p2).
- `extract_prompt.request_parts`, `appraise_prompt.request_parts`, `TEMPERATURE`, `MAX_OUTPUT_TOKENS`,
  `THINKING_LEVEL`, `RESPONSE_MIME_TYPE` and `check_pins` keep serving the dormant Gemini adapter; the Fable builders
  have their own `check_pins_fable` (section 8.2).

### 2.4 The compact form: not adopted

Measured composition (E.1): key names are about half of the answer's characters, values about 36%, whitespace about
1%; text is 39-46% of a short note's pass-1 output tokens and 36-55% of the cut long answers' (the rest is thinking).
A short-key form could cut a short note's text by roughly 1,900-3,300 tokens ($0.08-0.13 of about $1.0) and a long
note's by roughly 18,000 tokens. It is not adopted now: 128,000 output tokens fit the measured long notes with a
38-43% margin (F3all: 79,758 and 73,224 [R:truth-T4]); and a mapping layer back to LOCAL_SCHEMA_2 is a new place to
misread, with no measurement of how well Fable fills abbreviated keys. (The first text also counted prompt caching's
$0.35 saving per call against it; that saving exists only where pass-1 calls hit, in batches - in production most calls
write the cache and pay $0.089 more than no marker (7.2) - so it is no reason either way [R:cost-F-COST-5].)
The trigger is G-SIZE (section 11): if a development document's pass-1 output passes 85% of 128,000 tokens, the
compact form is designed then, as `gemini-events@4` (FINAL-V2 7.3's compaction order), with its mapping, before the
owner is asked about any bound (class b).

---

## 3. Long notes

**Decision: one request per pass with `max_tokens` 128,000 at effort high, pass 2's claim bound on this path 1,000
(`claims.CLAIM_BOUND_V3`, written before D1: 8.2), and a truthful TOO_LONG if a pass is cut or a claim set passes the
bound; never a partial reading. `INTERPRET_MAX_CHARS` stays 20,000 (D25).**

Measured since the first text (F3all, F3long; E.1) [R:truth-T4][R:replay-R1][R:cost-F-COST-1]: both 19.4 KB notes
answered pass 1 whole at 79,758 and 73,224 output tokens (62% and 57% of 128,000; 615.5 s and 566.3 s). Their claim sets
were 756 and 711 - not about 545 as first estimated (the short notes' fit extrapolated; the long notes' fit is about
0.037 claims per character) - so under the 640 bound sized for Gemini's 32,768-token answer (`claims.py:147`) pass 2 was
never built: GI Note #8, the owner's case, paid pass 1 and ended TOO_LONG, the class-b loss this section exists to
avoid. Under a bound of 1,000, both pass 2s answered whole in one request each (77,483 and 70,263 output tokens, 61% and
55% of 128,000; 590.7 s and 536.9 s; established 0.99 and 0.98; controls not rejected 0/303 and 2/288). So the bound on
this path is 1,000, set from F3long before the first recording under `gemini-appraisal@2` (D202), and GI Note #8 is read
in full; no size refusal reaches the owner.

The measured cut answers of F2high (at 64,000) showed how far the two 19.4 KB notes got and what a whole answer needs:

| | A-note8 | C-C2MEM-023 |
|---|---|---|
| output at the cut (F2high) | 64,000 | 64,000 |
| thinking in it (`thinking_tokens`) | 29,109 | 40,743 |
| answer text at the cut | 80,471 chars = 34,891 tokens (2.31 chars/token) | 53,565 chars = 23,257 tokens (2.30) |
| reached | all lists before `events` complete (26,711 chars); 30 events complete, 1,763 chars each | lists before `events` 29,065 chars; 16 events, 1,511 chars each |
| a whole answer at 38 events (Argon's v1 count for both, `fresh2-frozen/{A/note8,C/C2MEM-023}/r1.body`) | about 69,700 tokens | about 78,300 |
| at 43 events (FINAL-V2 7.1's count) | 73,560 | 81,573 |
| at 60 events | 86,555 | 92,726 |

The estimate takes a whole answer as the thinking the cut answer had already spent plus the remaining events' text:
both cut answers had produced 23,257-34,891 text tokens, so their thinking (29,109 and 40,743, as reported) came
before the text in that single turn. The probe kept no raw stream, so whether Fable thinks again between parts of a
long text is not observed; if it does, the need is higher, which the margin and G-SIZE (section 11) cover. Every
estimate fits 128,000 with at least 27% to spare (36% at 43 events). At the slowest measured rate a 78,000-token
answer takes about 675 s, a cut at 128,000 about 1,107 s (1.12). F3all's whole answers (79,758 and 73,224) fell inside
the estimate's range [R:truth-T4].

The alternatives, with numbers:
- **A lower effort above a size**: unmeasured for Fable, and the owner set effort high (D275); thinking was 45-64% of
  the cut long answers, so medium might fit 64,000, but a different effort per document is a product decision with no
  ruling. Not taken; listed for the owner as an optional measurement (owner questions).
- **A compact form**: would cut the long notes' text by roughly 18,000 tokens but C2MEM-023 would still need about
  63,000-66,000, at the 64,000 limit; it adds a mapping layer (2.4). Kept as G-SIZE's fallback.
- **Reading in parts with stable ids**: every part needs the whole document as context (input x parts), each part
  thinks again, and the design's cross-document rules (section inheritance 1.5, restatements, the pairing of statements
  with acts across sections 4.5, G5 across parts) assume one answer per revision. Not taken: a new class of
  cross-part defects for a problem 128,000 tokens solves.
- **A truthful refusal by size**: a bound that refused the two notes would refuse GI Note #8, the owner's case
  (FINAL-V2 7.3), an accepted-capability loss (class b). It stays only as the residuals, each stated
  [R:truth-T4][R:replay-R1]: an answer of either pass cut at 128,000 is TOO_LONG, never read in part
  (`jobs._settle_outcome`), never re-sent for a member, and worded as a reading that reached its output limit (1.5,
  [R:truth-T7]); a claim set over 1,000 is TOO_LONG at door 0 after pass 1 was paid (no claim count is known before pass
  1 answers; the long notes' 0.0365-0.039 claims per character put a 20,000-character note at about 730-780 claims,
  at least 22% under the bound); and a send the
  deadline cuts before Anthropic ends it is UNKNOWN, reconciled by the member, never TOO_LONG (1.12) [R:connector-CONN-2].
  Pass 2's own size: at the measured 98.8-102.5 output tokens per claim on the long notes, a set at the bound needs
  about 102,500 tokens (80% of 128,000); at the worst rate measured on a short note's small set (155 per claim, mostly
  thinking) a set above 825 claims would be cut - G-SIZE (11.3) gates the per-claim rate on D2's long notes.

Cost, measured (F3all, F3long, at 1.7's rates) [R:cost-F-COST-1]: a long note's pass 1 is $3.00-3.26 when it reads the
cached instruction and $3.44-3.70 when it writes it ($5.63 at the 128,000 worst), its pass 2 $3.11-3.40 at 711-756
claims ($5.52 at the 128,000 worst), so $6.11-7.10 for both passes and about 18-20 minutes - not the $6.1 and 514 s
first estimated at 545 claims (section 7).

---

## 4. The slot rule

### 4.1 What was measured

Fable: 2 of 8 short notes refused whole at `extract_read.read`'s bounds stage (`bound_error` -> `_field_bound` ->
`_too_many(facts, Bound.SLOT, ...)`): A-v2 E2 `technique.device` (3 facts: one supported, two negated) and A-v6 Y1
`organ` (2 supported) (E.2). Gemini low (BRIEF item 5): 4 of 8 (`events[1].technique.device` 3,
`anatomy[2].subtype` 2, `events[0].performer` 2, `events[0].visit.basis` 2). In both of Fable's, the document states
several true values of one object's single-valued attribute; the TECHNIQUE clause itself asked for the negated ones.

### 4.2 Decision

**A slot holding more than one fact is read with that attribute unresolved, fail-closed, and the rest of the answer is
read; the instruction is changed (2.1 items 1 and 2) so the slips become rarer.** D275 asks for this unless the design
shows it unsafe. The refutation showed the first text's merged view unsafe (4.4: a demonstrated false READY, a K rule
switched off, untrue member sentences); the view and its readers are revised below so that it is not, and 4.3.8 keeps
S1's whole-answer refusal for any attribute where the build cannot prove the revised properties [R:truth-T1].

### 4.3 The exact rule, end to end (step F3)

1. `contract/extract_read.py`: `_field_bound` no longer applies `Bound.SLOT`'s count; a SLOT is bounded only by each
   fact's own bounds (sources, options, words). `_Items.facts` drafts every fact of the slot as written (index 0..n-1,
   as today) and, when n > 1, adds the new item-level reason `Reason.SLOT_OVERFULL` to every one of them (their S2, I1,
   I3 and I4 checks still run). Nothing is removed or rewritten. `BOUNDS_2[Bound.SLOT]` keeps its value 1 and now
   decides the finding, not a refusal; the module docstring's S1.3 sentence "each slot at one fact" moves to the
   item-level list.
2. `contract/types.py`: `Reason.SLOT_OVERFULL = 'slot_overfull'` joins the closed list (row 4, after
   `REFERENCE_INVALID`).
3. One merged view, read everywhere a single-valued attribute is read [R:truth-T1][R:truth-T2][R:truth-T3]
   [R:truth-T5][R:truth-T9]: for a slot with n > 1 written facts, the reader of that attribute gets ONE fact - result
   unresolved, reason `slot_overfull`, state `contradicted`, value `''` (engine `None`), options = every value the slot's
   facts wrote, each once in written order, supported or negated: the values pass 1 itself put in the slot, never a
   value it did not write; and `negated_values` = the written values whose fact was negated (a new field of `engine/types.Fact`,
   defaulted empty for every other fact, as D188's three fields are). The first text's options, "the attribute's whole
   domain", put check-made values (`manual`, `incomplete`) where readers take a contradiction's sides as pass 1's own
   claims (T2, T5), and a date slot has no domain at all (T9). Never the first written fact, never silence. Its readers
   are of three kinds, each named by F3's list:
   a. possibility readers (`facts.possibly`, `classes._may_name`, `classes._open` and every rule built on them: rivals
      held by possible acts, positive candidates, D157's possible bleeding control) read the view as the weakest of its
      written facts read alone: every written value is possible, and where `negated_values` is not empty, a reader that takes an
      unestablished denial as leaving every value open (`_may_name`, `_open`) takes the view so too;
   b. readers of what pass 1 STATED (`classes._claims` and the `stated` flags and member sentences it feeds;
      `consistency._names`, `_named` and `_states_or_offers`; any wording reader that quotes a contradiction's sides)
      read the options less `negated_values`: a denied or unwritten value is never worded as stated, found or offered;
   c. claimed-value readers - those resting on "each 9.4 weakening keeps a claimed value": `combination._claims_session`,
      `pairing.digital_examination` and `combination._digital` (which read manual as the device's claim), and every
      other the list finds - read each option not in `negated_values` as claimed. `_claims_session` reads only the claimed value
      today ("never ... a contradiction's side"), so it also misses pass 1's OWN contradiction of a session, whose
      settled value is empty: a release already in the built tree (`refute-truth-scripts/demo_within_contradicted.py`:
      43235 READY beside a same-day EUS whose done examination's session is contradicted), which the same change
      repairs; re-run with the repaired reading (`build-v2/amend2/judge-scripts/repair_check.py`, both the overfilled
      and pass 1's own contradicted session), the demonstration holds 43235 within the EUS.
   The K rules and L1 read slots through `_Answer.one`, and every one of them fires for each value the slot's fact
   states or offers - its supported value, each side of pass 1's own contradiction, each written value of an overfilled
   slot not in `negated_values`; for a rule reading two slots, every combination - wherever its firing demotes another fact:
   `_value` and `_id` (which read a SUPPORTED fact only) give way to that reading in K2's examination-link and date arms,
   K3, K4's type and organ, and K5's performer, person and documenting-clinician reads. As built, a contradicted organ
   already skips K4, so a reach to an organ the same document says was removed can be claimed and supported (E17's
   contradiction); the change repairs it for pass 1's own contradictions too [R:truth-T3].
   The places: `contract/consistency.py:_Answer.one`, `ReadAnswer.fact`, the inheritance reads in `contract/settle.py`,
   any slot read in `contract/geometry.py` and `contract/claims.py`, and `engine/facts.py:fact` (the FactSet builder,
   `_object_facts`, makes one `engine/types.Fact(result=UNRESOLVED, value=None, state=FactState.CONTRADICTED,
   options=<the written values>, negated_values=<the negated ones>, reasons=(SLOT_OVERFULL,), spans=<every written fact's
   spans>, cited=<every source>)`). The builder of F3 lists every call site that reads a slot (`.one(`, `.fact(`,
   `found[0]`, `facts_of.get(...)[0]`), every comparison of a possibly unestablished fact's claimed value (`.value ==`)
   and every K-rule read through `_value` or `_id`, and routes each; a test plants an overfilled slot - supported values
   only (A-v6's shape), one supported value with negated others (A-v2's), and negated values only - on each of the 38
   slot attributes and asserts 4.4's properties at every place, the member sentence of each held item included.
4. `contract/claims.py:build_request` claims no fact carrying a finding (D206: it takes the findings as a required
   keyword), so no overfilled fact is claimed, no control is generated for it, and pass 2 never sees it.
5. `contract/settle.py`: row 4 makes each such fact UNRESOLVED with no table change - a reason in none of
   `GEOMETRY_REASONS`, `LITERAL_REASONS` and `CONSISTENCY_REASONS` is integrity's ("an unforeseen reason fails
   integrity", the tables' comment); the inherited per-act fact of an overfilled section slot (occasion, performer,
   owner, role) is unresolved with the same reason, through the merged view (item 3).
6. `interpretation/store.py`: `row_v2`/`load_v2` accept more than one stored fact at a slot key only for an inventory of
   `gemini-inventory@3` and only when every one of them carries `slot_overfull`; any other multi-fact slot is refused
   at load as a shape violation, as today.
7. The held fact's cause is `unestablished:slot_overfull` (the existing `unestablished:<reason>` form; operator data,
   MO-2); the member's item is that fact's existing question - for an overfilled device, which device was used, never
   "not documented" [R:truth-T2] - and `interpretation/wording.py` changes only where F3's list finds a reader that
   quotes a contradiction's sides itself (3b).
8. If the plant test or 9.4's extended generator (4.4) finds an attribute whose overfilled slot cannot be read with 4.4's
   properties, that attribute keeps S1's whole-answer refusal (`bound_error`), named in DECISIONS by the integration
   owner; the instruction is the first defence either way - F3all, with two sentences close to 2.1's items 1 and 2,
   wrote no overfilled slot in 10 notes [R:truth-T1].

### 4.4 Why it can never give a false READY or a wrong exclusion

- **It establishes nothing.** The overfilled facts are never claimed (4.3.4), settle never makes them supported or
  negated (row 4), and every reader sees one non-established fact (4.3.3): `facts.holds`, `denied` and `established`
  are False for it. A READY needs its deciding facts established (SUPPORT rows, 4.4 of FINAL-V2), so no READY rests on
  that attribute; an exclusion needs an established deciding fact and a statement whose scope is established (4.6
  conditions 2-4), so no exclusion rests on it.
- **It is never silence.** The view's state is set, so `facts.silent` is False. This matters on a statement: a denial
  whose performer, target or scope slot is overfilled does not become a general denial covering every performer or
  target (4.5's performer row reads "D's own statement names a performer" as a non-silent fact); it names something it
  cannot establish, so it can only ask (`statement_scope`, C-7) or leave the code possible, never exclude. Reading it
  as silent would have widened the denial; that is why the view is not the SILENT fact.
- **It is pass 1's own contradiction of the written values, read by repaired readers** [R:truth-T1][R:truth-T2]
  [R:truth-T3][R:truth-T5]. The first text called the view "the weakest reading" because every value of the domain was
  possible, and carried FINAL-V2 P6 over to it. The refutation showed why that does not hold. P6 and 9.4's property
  tests cover weakenings that keep the claimed value (an established fact to unresolved, an added doubt, an unrejected
  control, a deleted list member), while the view erased it, and `combination._claims_session` reads it (T1: a
  release of a base_within hold, 43235 READY beside a same-day EUS, demonstrated on the built engine). The view put
  values pass 1 never wrote where readers take a contradiction's sides as pass 1's claims (T2: a documented colonoscopy
  worded "not documented"; T5: a complete enteroscopy worded "stated to be incomplete"). And the K rules that read a slot
  through `_value` or `_id` fire only on a supported value, so offering more values switched them off instead of firing
  them (T3: K4 skipped, a reach to a removed organ supported). The revised view carries only the written values, and each
  reader kind reads it as 4.3.3 says, so it is never stronger than any single written fact read alone, for any reader,
  and never words a denied or unwritten value as pass 1's. 9.4's generator gains value-erasing contradictions: any
  established single fact turned into (i) pass 1's contradiction of its value and another, and (ii) an overfilled slot
  of its value plus another value, written supported or negated; the P-MONO tests run on both and assert that no HELD
  becomes READY or EXCLUDED, no rival is released and no member sentence words a value pass 1 did not state. The
  deterministic checks only demote (D178's check: "every deterministic check of 3.1 can only make a fact UNRESOLVED"),
  and with 4.3.3's K-rule reading, offering more values can only demote more.
- **Objects merged by the model.** An overfilled slot can be the symptom of two objects written as one. The object's
  other facts are then each a fact about the document that passed every check and pass 2's appraisal with its control
  rejected (P5); the same merger without the symptom is read today, so the rule adds no exposure the built reader
  lacks, and 2.1's items 1 and 2 push such objects apart.

The whole-answer refusal stays the behaviour for every other bound (`bound_error`'s list sizes, words, cited units,
doubt objects and readings). G-SCHEMA (section 11) counts whole-answer refusals; `slot_overfull` holds are counted by
cause in G-NOISE.

---

## 5. The holds

The four held READY-expected rows of the probe, read from the frozen replay (`devsets/replay-F2high-p2`), the scores and
the engine. No engine fix is adopted; one is a measurement artifact.

### 5.1 A-v3 45386: coding_rule:COLFULL - a correct hold by design

45386 (`requirements_table.CODES`: kind DILATION, tags COLFULL and TECH) needs the colonoscopy's reach at a FULL_REACH
landmark or an ileocolic anastomosis. X1's facts: `reached` `anastomosis` supported and appraised; `reached`
`neo_terminal_ileum` unresolved with `geometry_statement` and `extent_inferred`; `reached_anatomy` silent. The reach to
the neo-terminal ileum is told in S8 "...dilated today with a 15 mm through-the-scope balloon, after which the
colonoscope passed into the neo-terminal ileum..." - the anchor unit of the dilation event E4 - while the anastomosis
reach is cited from S7, the examination E3's own anchor; so
`contract/geometry.py:extent_reasons` (G5, D36 restated, D198) finds its source only in an act's units: extent
inferred. The examination's own anchor states the anastomosis, but `reached_anatomy` is silent because the instruction
(EXTENT) names it only when the furthest point is an anastomosis, and here the furthest point is beyond it - Fable
followed the instruction. G5 cannot tell a reach stated inside an act's sentence from a reach inferred from one (D36's
W1S-399 biopsy sentence) without reading words, which P1 forbids; it is the barrier that closed FRESH-2's false READY
W1S-112 45385 (D38). Not changed here. Two repairs exist and both need evidence first, so neither is designed now: an
appraisal path for `extent_inferred` (a claim and a control for the endoscope's own reach, settle row 4 changed), or
`reached_anatomy` for any anastomosis the endoscope reached (a contract change whose read-set includes the class rules
of `engine/classes.py`). D3 counts holds by cause; `extent_inferred` is reported there.

### 5.2 B-fb05 45380: reading_unknown on E5's target - a correct hold by design; no repair in this amendment [R:truth-T8]

45380's trace is T on every SUPPORT row, COLFULL and R7; its one held fact is `act_target` (rank 17, reason silent) on
E5, the random cold-forceps biopsies of the right and left colon. E5's `target.lesion` and `target.structure` are
silent; its `target.places` (right_colon, left_colon) are established, and `left_colon` contains `descending_colon`
(`engine/anatomy.py`, the LEFT_COLON row), the place of L1, the polyp E4 removed by cold snare. Nothing establishes that
E5 was not done to L1, so the same-lesion question stays open and the code is held - P3 (silence is unknown) and the
pairing rules working as designed. The document does say what was biopsied ("Colonic mucosa normal throughout; random
biopsies taken"), but no fact the engine reads can carry it [R:truth-T8]: a biopsy's `target.structure` is never claimed
(`engine/requirements.py:CLAIMED` claims it for drainage and EUS injection only), so it settles unappraised (the frozen
replay settles E4's as unresolved, reason `unappraised`), and `engine/coverage.py:_same_lesion` and `_apart` read only
`target.lesion` and `target.places`. The first text's repair (2.1 item 3, TARGETS) therefore could not release it, and
is withdrawn. The hold is recorded as correct by design; a release needs a CLAIMED row and a control for a biopsy's
structure and a bundling rule that reads an established non-lesion structure as apart - an engine and contract change,
designed and refuted on its own, and weighed on D3's counts with 5.1's and 5.4's candidates.

### 5.3 B-fb10 45330: coding_rule:base_included - a measurement artifact

45330 was held because 45331 (proposed with the quote "No biopsies were taken.") was held by `statement_scope`, and
`engine/combination.py:base_included` rule (a) holds a base code beside a counted code of its family. 45331 was held
because C-10 (`engine/evaluate.py`'s `cover`) judged the quote's span [1215, 1238] a PARTIAL cover of E6's words
[1215, 1237]: the final full stop lies outside, and the replay hands C-10 no R1 word runs
(`tools/v2/replay_v2.py:Integrity.word_runs = None`) where the pipeline hands `geometry.word_runs`
(`jobs._Integrity.word_runs`, DECISIONS D261), which lets a quote pass a covering span by a stop or a space. Verified in
this session: the same frozen batch replayed with the pipeline's word runs
(`build-v2/amend2/verify/replay_wordruns.py`, sha256 `ced35b77...`; outputs under `verify/`) gives 45331 EXCLUDED,
45330 READY and A-v5 45385 EXCLUDED, every other row unchanged. Fix: the replay tool hands C-10 the tree's
`geometry.word_runs` (step T); the engine is right.

### 5.4 B-fb10 99214: frame_role, same_day_em, base_included, competing_codes, context_missing - correct by design under this measurement's inputs

- `context_missing` (rank 23, R6:context): the devset gives no member values (`devsets/d2cmp/proposals.json`
  B-fb10 `user_values {}`), and D3 makes setting and patient status member-entered only on the new path. 99214 cannot
  be READY without them, whatever the reading. The development expectation of READY presumes values the devset does not
  give: a measurement-input gap. Fix (step T): `devsets_v2.py` carries each E/M case's member values when its source
  states them, else the expectation is HELD.
- `unestablished:frame_role` (rank 7) on E1's performer, inherited from N1: K7 (`consistency._k7`) demotes a performer
  sourced from the document frame ("Endoscopist: ...") in a section whose role is framed (`_FRAMED_ROLES`: history,
  indication, medications, plan); Fable gave N1 the role `indication`. The visit's performer is not stated by the
  document; the fail-closed check is right.
- `coding_rule:same_day_em` (rank 20): the visit's `separately_identifiable` (stated in S10) and `basis` were demoted
  to unknown by Fable's doubt about the visit (about `visit`, readings medical_decision_making and total_time, S11),
  and `extract_schema.DOUBT_ATTRIBUTES[DoubtAbout.VISIT]` covers both visit attributes. Both bases are stated in the
  document; the doubt is Fable's way of holding two true values in a single-valued slot. Correct by the doubt rule
  (a doubt only demotes).
- base_included and competing_codes: 99204 and 99214 were both proposed and patient status is unknown (D3).

No engine change. Recorded for D3, by cause: K7 on office-visit sections labelled `indication`, and the `visit` doubt
row's breadth. Both are contract changes (a section role, `DOUBT_ATTRIBUTES`) to be taken only on D3's counts.

### 5.5 Corrected tally

On the 6 complete probe notes: 3 unnecessary holds of 8 READY-expected rows (v3 45386, fb05 45380, fb10 99214), READY
recall 5 of 8, no wrong READY, no wrong exclusion (E.2). G-NOISE (12% / 75%) still fails on this sample; section 11
restates it and its repair order.

---

## 6. Scoring

`tools/v2/score_v2.py:judge` counts a READY whose acts' anchors overlap no expected act as `wrong_ready` kind `act`.
A-v5 45380: the engine anchored the biopsy (E3) on its statement S7 [346, 459]; the expectation anchors it on the
Impression [500, 550], which the pass-1 answer lists as E3's restatement (S9, role `summarizes`) and which the
instruction forbids as an anchor ("an impression line ... is never the anchor of that act"). The act is the same.

Fix, in three parts:
1. **The export carries every event's statements** (step F9): `engine/measure.py` writes `cpt-studio-measure@2`, adding
   `events: [{event, anchor: SPANS, restatements: SPANS}]` for every event of the inventory, a restatement listed only
   when `contract/geometry.py:restatement_valid` holds for it (G6: never another event's anchor units).
   `tools/v2/score_v2.py:validate` accepts @1 and @2.
2. **The scorer counts an act by its statement or a restatement** (step T): in `judge`, when a READY row's act anchors
   overlap no expected span, an expected span X still matches when (a) X overlaps no exported event's anchor, (b)
   exactly one exported event lists a restatement span overlapping X, and (c) that event is one of the code's acts.
   Such a row is `correct` with kind `restatement`, and `summary.json` counts them (`acts_matched_by_restatement`) so
   every one can be inspected. Condition (b) keeps a restatement that two events claim, or one the model attached to
   the wrong event while another lists it too, from forgiving a wrong-act READY; condition (a) keeps an expected
   statement that is some act's anchor from being matched through another act's restatement. With an @1 export the rule
   does not apply (no events), as today. The rule's limit, stated: if pass 1 attached a summarizing line to the wrong
   act of the same kind and no other event lists it, and the engine's READY rests on that act alone, the row is
   forgiven; that is why every restatement-matched row is listed with its anchors in `rows.jsonl` for first-hand
   review, and the acceptance owner may count any of them as wrong after reading it.
3. **Development expectations** (step T): `devsets/d2cmp/expectations.json` and the FRESH source of A-v5 45380 gain the
   act's statement span [346, 459] beside [500, 550] (the scorer's existing any-overlap semantics); `devsets_v2.py`
   reports every development expectation that anchors a READY act on a unit no event of a recorded answer anchors,
   for the development owner to review. The acceptance expectations are frozen and the acceptance owner's; part 2
   applies to them without editing them, and is fixed before the acceptance run and blind to it.

Also measurement fixes from section 5, applied before any gate is read: the replay's R1 word runs (5.3) and E/M member
values (5.4).

---

## 7. Cost and budget

### 7.1 Per document, at effort high

Measured per complete short note, both passes, no caching: $1.19-1.76, mean $1.44 (F2high pass 1 + F2high-p2 pass 2).
F3all's 8 short notes, priced from their usage at 1.7's rates [R:cost-F-COST-5]: $0.59-1.44 when pass 1 read the cached
instruction, $1.03-1.87 as production pays them (every pass 1 writing the 5-minute cache: 7.2), $0.94-1.79 with no
cache marker. The two 19.4 KB notes, measured (F3all pass 1, F3long pass 2) [R:cost-F-COST-1]: $6.11-6.66 with a pass-1
hit, $6.55-7.10 with a write. Modelled over the 103 FRESH development documents (median 823 characters, mean 2,472, p90
2,438, largest 19,460; 8 of them at 10,000 or more), with pass-1 output 408 x chars^0.53 (fitted through the short notes
and the long-note estimate; residuals within 20% on the 8 short notes), the long notes at 78,000 pass-1 output tokens,
pass-2 claims 40.5 + 0.0357 x chars and pass-2 input 3,240 + 47.3 x claims (refitted with F3all's and F3long's claim
sets and inputs: the first text's 60 + 0.025 x chars put a long note at 545 claims, against 711-756 measured) at 109
output tokens each (F2high-p2's mean; the long notes measured 98.8-102.5), and E.1's pass-1 input fit
[R:cost-F-COST-1][R:cost-F-COST-5]:

| per document, both passes | pass-1 cache hit | no cache marker | production (every pass 1 writes the cache) |
|---|---|---|---|
| mean | $1.47 | $1.81 | $1.90 |
| median | $0.94 | $1.29 | $1.38 |
| a 19.4 KB note | $6.70 | $7.05 | $7.14 |
| a 19.4 KB note with both passes cut at 128,000 (the worst) | $10.63 | $10.98 | $11.06 |

(The first text's table - mean $1.43-1.78, a 19.4 KB note $5.77-6.12, $7.78-8.13 at the worst - priced a long note's
pass 2 at 545 claims and showed no production column.)

The 2,000-5,000-character band (20 of 103 documents) has no Fable measurement; the fit interpolates it. Under D184 an
edited legacy encounter's first update costs one such document plus Corti and the peer reviews (AMENDMENT-1 9.2's
Gemini figures are superseded by this table).

### 7.2 Prompt caching

- **Where**: one `cache_control {"type": "ephemeral"}` (5-minute) on pass 1's single system block (1.2). The prefix is
  `system` alone (no tools); it is the same bytes for every document of a version: about 44,470 tokens (E.1's fit;
  the first live send states it exactly as `cache_creation_input_tokens`), far above any model minimum.
- **What makes it miss**: any byte change of `INSTRUCTIONS_3` (a new version), another model or effort, more than 5
  minutes since the prefix was last written or read, another workspace or organization, or an order where pass 1 runs
  are far apart. A miss costs a write at 1.25 x input ($0.445 instead of $0.356); a hit costs $0.009 (saves $0.347).
  Caching pays when more than about 20% of pass-1 calls hit. The 5 minutes run from the START of the request that wrote
  or read the entry - generation time counts against them (the claude-api reference, prompt caching, "Choosing the
  TTL") - so any pass 1 longer than about 280 s ends the chain: a long note's pass 1 (566-615 s) is always followed by a
  write. F3all's long-note read 615.8 s after A-note8's start was a 1-hour read (its probe used `ttl` 1h, E.1); under
  this request's 5-minute marker it would have been a write [R:cost-F-COST-5].
- **Pass 2 gets no breakpoint**: its fixed part is about 4,000 tokens (E.1's intercept, with the schema and the framed
  document) and changes per document after the instruction; a hit would save at most about $0.03.
- **In batches**: for D1-D3, record_v2 sends every pass 1 of a batch before any pass 2 (step T), so pass-1 sends on
  short notes follow each other 1.5-3 minutes apart and nearly all hit, and each long note's pass 1 is followed by one
  write. For A, the order is the acceptance owner's tool's (FINAL-V2 9.6), which step T does not own: with per-document
  order (pass 1 then pass 2, as record_v2 runs today and F3all ran), short notes' pass-1 starts were 109.7-285.5 s apart
  (the widest 14.5 s from expiry), and by 7.1's model 26-28 of the 103 FRESH documents exceed 300 s, so A's cost lies
  between 7.3's hit and production rows unless that tool sends pass 1 first; the owner is given the range
  [R:cost-F-COST-5]. **In production** traffic is sparse and most pass-1 calls will write the cache: $0.089 more than no
  marker and $0.436 more than a hit, which is why 7.1 shows the production column and 7.5 hands it to the owner apart;
  the operator report shows `cache_read_input_tokens`, and a later version drops the breakpoint if the measured
  production hit rate stays under 20%. One request form serves both, so recordings replay on the installed build.

### 7.3 The acceptance run

D178 condition 1 governs the size: THRESHOLDS.md's three runs of the 48 independent cases and of g1's 12 documents and
one run of the other 167 cases, 347 documents. 7.6's "215 cases x 3 runs" (645) is shown beside it. The acceptance
set's sizes are sealed; FRESH stands in for them, as in FINAL-V2 7.1.

| | 347 documents | 645 documents |
|---|---|---|
| every pass 1 a cache hit, long notes as measured (pass 1 at 78,000; pass 2 at 711-756 claims) | about $509 | about $945 |
| no cache marker | about $629 | about $1,169 |
| every pass 1 a cache write (production's pricing; per-document order without pass-1-first lands between the first row and this) | about $660 | about $1,226 |
| long notes with both passes cut at the 128,000 worst | about $614-765 | about $1,142-1,423 |
| Message Batches API (half price): hits best effort, so between the all-hit and the all-write figures | about $254-330 | about $473-613 |

Recomputed with 7.1's model [R:cost-F-COST-1][R:cost-F-COST-5][R:cost-F-COST-7]; the first text's $496 / $616 / $670
(347) priced long notes' pass 2 at 545 claims, assumed every pass 1 a hit in its first row, and showed the Batches
option at half the all-hit figure, although a batch is processed in any order and its cache hits are best effort (the
reference's advice for batches is the 1-hour TTL, at twice the write price).

The Batches API does not fit the acceptance design as frozen: record_v2 reserves, sends, freezes and may stop per send;
a batch request carries no `stream`, so its request sha differs from the installed build's and its recordings would not
replay there (9.6); its result is a Message JSON, not the SSE stream the installed reader reads, so the acceptance run
would not exercise the production reader; and pass 2 waits for pass 1's batch. It is an owner option (half the money)
that needs a harness transport and a second response reader designed and refuted first; not designed here.

### 7.4 Development measurement (D1-D3)

| batch | documents | modelled | guard (D183, about 2 x) |
|---|---|---|---|
| D1 | one short development document, both passes | about $1-2 | $3 |
| D2 | the 10 `devsets/d2cmp` documents x 1 (the two 19.4 KB notes included) | about $21 with pass-1 hits, $24 without: F3all's 8 short notes ($0.95 and $1.30 mean) plus the two long notes as measured ($6.11-7.10) | $50 |
| D3 | 30 development documents x 3, as three batches of 30 x 1 (FINAL-V2 9.6's composition) | about $44-57 each, $132-171 in all | $115 each |
| an iteration | 30 x 1 both passes; or pass 2 only over D3's latest pass-1 answers | about $44-57; about $19 | 2 x |

Recomputed with 7.1's model and F3all/F3long [R:cost-F-COST-1]. D1-D3 come to about $155-195 before iterations.
FINAL-V2 7.6's Gemini figures (D1 $0.10, D2 $1.6, D3 $11) are superseded. A guard is D183's runaway stop, checked as
"spent reached the guard" before each send, so a batch can pass it by one send: its real maximum is the guard plus one
worst-case send, $5.57-5.64 for a pass 1 that writes the cache and runs to 128,000 output tokens and about $5.52 for a
pass 2 at the claim bound (8.3) - D1 can reach about $8.6, not $3 [R:cost-F-COST-6]. Anthropic spend is outside
Google's ~$300 cap (session interpretation (e)); every batch's actual usage goes to `USAGE-LEDGER.md` (D183).

### 7.5 The owner's decision before the acceptance run (class d; D275; FINAL-V2 7.6 rule 1 restored by D275)

Before A is sent, the integration owner gives the owner: the measured cost per document from D2 and D3 (both passes),
with caching as measured AND as production pays it (every pass 1 writing the cache), shown apart [R:cost-F-COST-5]; A's
total at that cost for 347 documents (and for 645 if THRESHOLDS changes) as a range from all pass-1 hits to all writes,
with the long notes' worst (7.3); A' (one re-run after a request-changing repair) at the same total; the month's
recorded Anthropic spend; the Anthropic account's configured monthly limit or prepaid balance as the owner or operator
states it (never read from a credential or guessed), the installed site's monthly Anthropic usage from the operator
report, and the headroom they leave [R:cost-F-COST-4][R:replay-R5]; and the Batches option with its saving (the 7.3
range) and its build cost.

The exposure, stated to the owner with the figure [R:replay-R5][R:cost-F-COST-4]: D1-D3, A and A' run on CPT Studio's
one Anthropic credential (D275; D183 creates no separate key), the same account the installed site's Fable 5.1 second
reader uses. If the balance or limit runs out mid-batch, Anthropic has answered such an exhaustion with HTTP 400
`invalid_request_error` (AMENDMENT-1 A20 and its 7.3 table): the harness records a HOLD and stops, and the installed site's next Fable 5.1
exchange sets the installation-wide `fable` hold (`provider_holds.classify`: a participant's 4xx other than 413), so its
second reader stops for every upload until the owner tops up and an operator releases. Whether the harness keeps a
reserve for the site below the stated limit (record_v2's project threshold, 8.3) is the owner's decision: D183 forbids
a ceiling of the session's own.

How the figure binds [R:cost-F-COST-2]: A is sent only by a tool that enforces the owner's figure as one cap over all of
A (A' under its own figure, if the owner approves one), checked before every send as the spend so far plus that send's
worst-case bound (8.3) against the figure - never as "spent reached the cap", which passes it by one send, and never by
per-batch guards of twice a model, which together could reach about twice the figure. The acceptance owner's tool
(FINAL-V2 9.6) carries this as a stated property, and the integration owner checks it before A. Nothing is sent past the
owner's figure on the session's own judgement.

---

## 8. Versions, pins and recordings

### 8.1 Labels (D202: the first recording under each current label has happened - D1 under `gemini-events@2`, D1v/D1w under `gemini-appraisal@1` - so changed bytes take new versions)

The tree's current names are `INTERPRETATION_VERSION_V2`, `APPRAISAL_VERSION`, `INVENTORY_VERSION_V2`,
`ENGINE_VERSION_V2`, `INTERPRETATION_PAIR` and `ADAPTER_VERSION_V2`; the first text named labels the tree does not have
[R:replay-R4]. Those names keep their values (the dormant adapter and stored rows read them), and the new labels are
NEW names beside them, 1.1's rule:

| label (old name, kept) | old value | new name | new value | why |
|---|---|---|---|---|
| pass 1 (`INTERPRETATION_VERSION_V2`) | `gemini-events@2` | `INTERPRETATION_VERSION_V3` | `gemini-events@3` | new instruction and request form; the slot finding moves out of S1 |
| pass 2 (`APPRAISAL_VERSION`) | `gemini-appraisal@1` | `APPRAISAL_VERSION_V3` | `gemini-appraisal@2` | LOCAL instead of RESPONSE schema as the constraint, a new request form, the bound of 8.2; the seed rule reads the label, so the claim order changes |
| inventory (`INVENTORY_VERSION_V2`) | `gemini-inventory@2` | `INVENTORY_VERSION_V3` | `gemini-inventory@3` | a new reason, the slot rule and the K-rule reading (4.3.3) in the checks, settle and the store |
| engine (`ENGINE_VERSION_V2`; Assessment.engine_version) | `cpt-studio-events@2` | `ENGINE_VERSION_V3` | `cpt-studio-events@3` | the FactSet's overfilled-slot reading and the repaired claimed-value readers (4.3.3) |
| pair (`INTERPRETATION_PAIR`) | `gemini-events@2/appraisal@1` | `INTERPRETATION_PAIR_V3` | `gemini-events@3/appraisal@2` (27 of 40) | the pair |
| adapter (`ADAPTER_VERSION_V2`) | `gemini-generate@cptstudio-2` | `ADAPTER_VERSION_V3` | `anthropic-messages@cptstudio-interp-1` | the connector, its `anthropic-version` included (8.4) |
| `REQUIREMENTS_VERSION`, `CONTEXT_VERSION_V2`, `ROUTING_VERSION_V2` | @1, @2, @2 | - | unchanged | not touched |
| model, provider (`MODEL`, `PROVIDER`, kept) | `gemini-4-carbon`, `gemini` | `MODEL_V3`, `PROVIDER_V3` | `claude-fable-5-2`, `anthropic` | D275; 1.1 |
| measure schema | `cpt-studio-measure@1` | - | `cpt-studio-measure@2` | section 6 |

The families keep their names (`gemini-events@`, `gemini-context@`): `interpretation.is_new_context` and the installer
dispatch by family, and renaming would add readers for no safety gain; the provider and model are on every run.

Who writes and who reads [R:replay-R4]. Every WRITER on the current path writes the new labels only; every READER of a
stored row accepts both families, reading an @2 row as stored. If the writes moved while a reader kept the old name, the
first @3 assessment would be refused (`review.py:1289` would expect `gemini-routing@1` for an @3 inventory while
`engine/derive` writes `@2`, and `persist_assessment` raises), `overlay.py:417` would refuse every @3 proposal,
`readers.READ_ENGINES` would refuse @3 assessments and `review.py:335/359/394` would skip the fingerprint binding of
D259/D270; if nothing moved, `assess.versions()` would stamp @2 labels on assessments the changed engine made and
`engine/measure.py` would copy them into every export. The readers and writers, each with its step:
- `studio/jobs.py` (F6): `V2_VERSIONS`, `current_versions`, `_is_v2_inventory` (the context and routing version
  choice), the engine_version and `event_reading` records, `V2_CHECK_SOURCE`;
- `interpretation/store.py` (F3): `READ_VERSIONS` holds both pairs, rows written at @3, `LABEL_V2`'s successor;
- `engine/assess.py` (F3): `ENGINE_VERSION`, `SERVICES_STUB`, `versions()`, the per-code record; `engine/coverage.py`
  (F3): `CODING_VERSION`;
- `contract/extract_read.py` and `contract/settle.py` check their pins by label (F3); `contract/appraise_read.py` (F2,
  added to its files) checks `APPRAISAL_VERSION_V3`'s pin on the Fable path; `extract_prompt` and `appraise_prompt`
  carry `check_pins_fable` (F2);
- `interpretation/readers.py` (F6: `READ_ENGINES`, `READ_CONTEXTS` hold both), `interpretation/overlay.py` (F6:
  `RECORD_VERSION` written @3, both read), `studio/review.py` (F6: lines 335, 359 and 394 bind the fingerprints for both
  engine versions; 1289 expects `ROUTING_VERSION_V2` for both pairs);
- `interpretation/report.py` (F5), `engine/measure.py` (F9: copies `assess.versions()`), `ops/verify_browser.cjs` (F8,
  9) and `ops/rollback_check.py` (F8, 8.5).
A guard test asserts that no current-path writer names an @2/@1 label constant, and that every reader in the list
accepts both families.

### 8.2 Pins (`interpretation/__init__.py`, written by the integration owner after the build's last repair)

Pass 1 (@3): `INSTRUCTIONS_SHA256_V3` (`INSTRUCTIONS_3`, which contains ANSWER_SHAPE_2), `LOCAL_SCHEMA_SHA256_V2`
(unchanged object), `SEGMENTATION_SHA256` (unchanged); no RESPONSE pin. Pass 2 (@2): `APPRAISAL_INSTRUCTIONS_SHA256`
(text unchanged), `APPRAISAL_LOCAL_SCHEMA_SHA256` (unchanged; now also the structured-output schema),
`TEMPLATES_SHA256`, `STATEMENT_TEMPLATES_SHA256`, `CONTROLS_SHA256`, `CLAIMED_SHA256` (unchanged), and two pins of
their own, because their objects change and `gemini-appraisal@1`, which shares the old names, has recordings (D1v,
D1w) [R:replay-R1]:
- `CLAIM_BOUND_SHA256_V3`, the pin of `claims.CLAIM_BOUND_V3 = 1000` (beside `CLAIM_BOUND = 640`, kept for the dormant
  adapter): sha256 of `{"claims_per_request": 1000}`, `3fe08a5c8ec23575e2df78032d5b4b18dcff0927ce1c628743c47946b9415628`,
  the value F3long ran under. It is written by F0 before D1, so `gemini-appraisal@2`'s first recording is made under it
  and no pinned pass-2 value moves after a recording (D202); any later change of the bound is `gemini-appraisal@3`
  [R:replay-R1][R:truth-T4][R:cost-F-COST-1]. The first text kept 640 "unless D2 says so": D2's long notes would then have
  been recorded as door-0 refusals and, after a bound change under the same label, replayed as a built pass-2 request
  with no recording ("No recorded response for this request.").
- `HEALTH_THRESHOLDS_SHA256_V3`, the pin of the @2 thresholds, set from D3 as FINAL-V2 plans (an unwritten pin written
  once, D1v's state until then); appraisal@1's `HEALTH_THRESHOLDS_SHA256` stays unwritten. The probe trees'
  provisional pin is never committed.
`extract_prompt.check_pins_fable` and `appraise_prompt.check_pins_fable` check these when a body is built and
`extract_read.check_pin` / `appraise_read`'s when an answer is read. The @2/@1 pins stay for the dormant adapter's own
checks.

### 8.3 Recordings and the step-7 tools

- Gemini's recordings (`gemini-project/batches/D1*`, `D2low`, `D2medium`) stay labelled as Gemini's (D275), frozen;
  they replay only on their own probe trees. The Fable probe's (`anthropic-project/batches/F1schema`, `F2high`,
  `F2high-p2`, `F3all` and `F3long`, both frozen since [R:replay-R1]) are Fable's answers inside a Gemini-format envelope made by a probe; they stay
  frozen as evidence and are never replay fixtures of the new connector (other request bytes, no raw stream).
- `tests/fixtures/interpretation` (FRESH Argon recordings, v1) is unchanged and replayed as Argon's (D274).
  `tests/fixtures/interpretation_v2/recordings` holds only `SLOTS.json`: the new connector's replay fixtures are made
  after D2/D3 from their frozen `.sse` bodies (6c's rule), and the constructed answers under `answers/` stay valid
  answer texts.
- The tools (step T): `record_v2.py` calls the tree's `fable_adapter` (build, send, classify), freezes `.sse` bodies,
  reserves each send at its worst case computed from the body it sends - the cached prefix at the 5-minute write rate,
  the rest of the input at the input rate, 128,000 output tokens: pass 1 $5.57-5.64, pass 2 at the claim bound about
  $5.52 (the first text's "about $5.48" priced the prefix as plain input) [R:cost-F-COST-6] - orders all pass-1 sends
  before pass 2, records the inter-chunk gaps, the bytes per output token and the output rate of each stream (a session
  wrapper, as `fable_record.FableSession` wraps the session), and keeps its stop rules (a HOLD stops the batch). Its
  cost rule for an exchange: a send that is unknown, or whose stream never reached `message_delta` (an `error` event
  included), is counted at its bound - `describe` records no usage for it (1.4), so record_v2's `outcome ==
  'succeeded' or usage` estimate (record_v2.py:645) never prices a partial usage [R:connector-CONN-3][R:cost-F-COST-3].
  `--provider-cap-usd`: the Anthropic account's configured monthly limit or prepaid balance as the owner states it,
  with the site reserve the owner decides (7.5; `none` only on the owner's word, the exposure stated)
  [R:replay-R5][R:cost-F-COST-4]. For A, the cap that binds is the owner's figure, checked before every send as spend
  plus the next send's bound (7.5) [R:cost-F-COST-2]. `replay_v2.py` reads `anthropic/*.sse` through
  `ReplayInterpreterF`, refuses a batch whose manifest names another adapter version than the tree's (8.4)
  [R:replay-R8], and hands C-10 `geometry.word_runs`; `score_v2.py` takes section 6; `devsets_v2.py` takes 5.4 and 6.3.
  The Gemini paths stay for the frozen Gemini batches.

### 8.4 Replay compatibility

A recording replays only under the request bytes that made it (keyed by request sha256, FINAL-V2 9.6). Changing
`INSTRUCTIONS_3`, ANSWER_SHAPE_2, the effort, `max_tokens`, the cache marker or the pass-2 schema makes every
recording of the version unreplayable ("No recorded response for this request."), as designed; a settle-only change
re-settles stored pass-1 bytes (INVENTORY_VERSION), and an engine-only change recomputes (ENGINE_VERSION). The
`anthropic-version` header is outside the body, so it moves no request sha256: it is part of what `ADAPTER_VERSION_V3`
names (1.1), a changed value is a new adapter version (the doors match the adapter version, so no answer recorded under
another API version is reused), each run records the value it sent, and replay refuses a recorded batch of another
adapter version [R:replay-R8].

### 8.5 Rollback, the installer and stored runs

- Rollback to `cpt-studio:c2e53f8e7d33` (D15, FINAL-V2 6.4) is unchanged in kind: that image has no interpreter and
  reads new-path rows fail-closed. The D15 runtime test's migrated database gains rows of the new versions
  (`gemini-events@3/appraisal@2`, `gemini-inventory@3`, `cpt-studio-events@3`, a run of `ADAPTER_VERSION_V3`, an
  InterpreterHold with reason `declined`). `ops/rollback_check.py`'s SCENARIO_V2 counts (l.360-391) filter the literals
  `V2_ENGINE = 'cpt-studio-events@2'` and `provider = 'gemini'`, so on a database the Fable candidate filled ten of its
  thirteen kinds would count 0 and assertion 7 would block the install late: F8 changes them to accept both engine
  versions and to match the provider against `interpretation.READ_PROVIDERS` [R:replay-R6].
- The installer's assertions that name versions (`V1_INTERPRETATION_VERSION`, the zero-v1-rows check, the new-path row
  checks around install.py:2734-2862) accept the new versions; the in-image self-test compares
  `interpretation.MODEL_V3`, `fable_adapter.MODEL` and `fable_adapter.ENDPOINT` with `report.D275_MODEL` and
  `report.D275_ENDPOINT` (section 9).
- Stored Gemini or v1 runs: the installed site has none (c2e53f8e has no interpreter and `CPT_STUDIO_GEMINI_MODE` is
  unset; PLAN.md 2026-11-15). On a test instance they stay as stored: never reused for a Fable request (the doors match
  provider and adapter version), never resent, classified only by their own adapter (1.5), never a source of a new hold
  (`holds.record`), counted and priced by their own model in the operator report (section 9), and an unknown one is
  reconciled through the existing flow.

### 8.6 No migration

`ProviderRun.provider` (20), `adapter_version` (40), `EventInventory.interpretation_version` (40),
`InterpreterHold.reason` (20, no choices) hold the new values; reasons and results are stored in JSON; no column is
added.

---

## 9. Retiring Gemini from the interpreter path, and every surface that names a model

- **The path**: the build switches `studio/jobs.py` to `fable_adapter` on the new path (its `interpretation_adapter`
  import names the new module, which exposes the names jobs reads: NotBuilt, REFUSED, TOO_LONG, EXTRACTION, APPRAISAL,
  describe, classify, get_interpreter_v2); where jobs reads `interpretation.PROVIDER`, `MODEL` or `ADAPTER_VERSION_V2`
  for the current path, it reads `_reading_provider()`, `_reading_model()` and `_reading_adapter_version()`, which
  return the v1 names under the test-only v1 chain and the `_V3` names otherwise - or `READ_PROVIDERS`, dispatching by
  the run's own adapter version, where a stored run of either provider is settled. The first text listed four of these
  reads; there are more, and one left on Gemini makes every FAILED Fable reading unretriable for good (`retry_target`
  finds no 'gemini' run: RETRY_NOTHING; a Resume is held by the failed-before door) [R:connector-CONN-5]. All of them,
  by line on 195e06e90: 1783 `_loop_label` (it names 'interpretation' for every provider of `READ_PROVIDERS`, so no loop
  error names Anthropic: D22), 2333-2336 `_interpretation_not_sent`, 2440 `_read_extraction` and 2976 `_extraction_of`
  (both name `ADAPTER_VERSION_V2` directly today, so pass 2 would never follow a Fable pass 1), 2530
  `_settle_from_exchange`, 5152 and 5159 `_record_unsettled_holds`, 5245 and 5265 `mark_stale`, and 5655 `retry_target`;
  besides jobs, `holds._check_run` (F1) and the report's queries (F5). A guard test asserts that no other line of
  `jobs.py` names `interpretation.PROVIDER`, `interpretation.MODEL` or `interpretation.ADAPTER_VERSION_V2`.
  `adapter.py` is not edited and stays importable for
  its tests and the frozen recordings; a guard test asserts no `jobs.py` call reaches `adapter.GeminiInterpreterV2` or
  `adapter.get_interpreter_v2` outside the v1 chain. After D1-D3 measure Fable, the integration owner records the retirement of D230 and
  D272 from the interpreter path in DECISIONS (D275's last bullet); the dormant `GEMINI_*` settings and the Gemini
  pins then go with the next release that touches them, and removing `adapter.py` and its tests is a later, separate
  decision. Until that entry, nothing on the path reads them.
- **The customer denylist** (`ops/verification/customer-denylist.json`, step F8): pattern `interpreter_model` becomes
  `\b(?:gemini-4-(?:argon|carbon)|claude-fable-5-2)\b`. `provider_name` already covers claude, fable and anthropic
  bounded by letters and digits, and `model_id` covers `claude-` ids. New vectors, run by the three readers' tests:
  hits `claude-fable-5-2`, `Claude Fable 5.2`, `fable_unknown`, `AnthropicTimeout`; misses `affable`, `fabled`,
  `fables` (bounded by letters), and no bare clinical word is added (D230 (d)'s rule). `studio/customer_api.py:FORBIDDEN`
  already refuses `claude-[a-z]`, `fable` and `anthropic`; its test gains the same vectors (test file only).
- **The operator report** (`interpretation/report.py`, step F5): new written-out constants `D275_MODEL =
  'claude-fable-5-2'` and `D275_ENDPOINT = 'https://api.anthropic.com/v1/messages'` beside `D13_MODEL` and
  `FINAL_ENDPOINT` (kept for the dormant adapter); the self-test compares `interpretation.MODEL_V3`,
  `fable_adapter.MODEL` and `fable_adapter.ENDPOINT` with them, never with each other; the human labels "gemini runs ..."
  become "interpreter runs ..."; runs are counted for `interpretation.READ_PROVIDERS = ('anthropic', 'gemini')` and
  priced by the model their request named (`pricing.estimate(run.requested_model, ...)`, Gemini runs at their dated
  rates); cache read and write tokens and thinking tokens are summed and shown. The stored record key `gemini_run`
  (`RECORD_KEYS_V2`) keeps its name: it is the field of a stored record shape and means "the interpreter's run"; a
  rename would need a new record version.
- **The price table**: section 1.7; the test that pins `pricing.GEMINI == interpretation.MODEL` stays, and a new one
  pins `pricing.FABLE_52 == interpretation.MODEL_V3`.
- **The installed walk's verifier** (`ops/verify_browser.cjs`, step F8 [R:replay-R2]): its constants `INTERPRETER` and
  `APPRAISER` (`gemini` / `gemini-4-carbon`, l.192 and 201) and `EVENTS_ENGINE_V2` (`cpt-studio-events@2`, l.198) are
  pinned by `ops/verification/test_verify_browser.cjs` (l.3833, 4377, 4379) to `interpretation.PROVIDER`, `MODEL` and
  `ENGINE_VERSION_V2`, which keep Gemini's values (1.1), so CI stays green while the walk would fail
  `provenance.interpretation` on every Fable encounter, never check its appraisal run (an @3 assessment read as not v2),
  and report a released retry of an `anthropic` run as a duplicate paid request (`releasedForRetry` knows only
  `gemini`). F8 makes the walk read the provider and model from `PROVIDER_V3`/`MODEL_V3` and the engine label from
  `ENGINE_VERSION_V3`, still accepting @2 rows as stored, and points the test pins at the new names.
- **The sentinel and guards**: `sentinel.KEPT` gains `fable_adapter`; `tests/v2/test_retirement_manifest.py` lists it as
  kept; the deny set and its pinned sizes are unchanged; the new module imports nothing the sentinel denies, and the
  static guards' new-package rule covers it like `adapter.py`. The new-path write gate and `legacy_calls`/`retired_calls`
  measurement are unchanged; G-GUARD stays.
- **Wording**: the member-facing sentences change in three places and nowhere else: the run whose answer set a hold is told it was sent
  (DECLINED_MESSAGE for a request-bound hold, HOLD_SET_MESSAGE for any other) [R:truth-T6]; a reading cut at its output
  limit is told that, never that the document is too long (progress `cut_off`, RETRY_CUT_OFF) [R:truth-T7]; and a
  declined request's retry is refused with RETRY_DECLINED [R:connector-CONN-1] (all in 1.5). A paused interpreter still
  reads `holds.PAUSED_MESSAGE` ("Nothing was sent") for every run the standing hold kept unsent; the size and claim
  bounds keep the `too_long` sentences. None names a provider or a model (D22); the customer denylist's readers run on
  them.

---

## 10. Files and ownership (FINAL-V2 8.0: one owner per file; the integration owner merges in order)

| step | files (exclusive) | depends on | done when |
|---|---|---|---|
| **F0** integration owner | `docs/gemini-migration/DECISIONS.md` (this amendment's adoption after refutation; the w9r rulings); `interpretation/__init__.py` (the `_V3` labels of 8.1 [R:replay-R4], pin placeholders, `CLAIM_BOUND_SHA256_V3` written before D1 [R:replay-R1], `READ_PROVIDERS`, the `anthropic-version` value beside `ADAPTER_VERSION_V3` [R:replay-R8]); `cptstudio/settings.py` (1.11, 1.12) | the refutation's judgement | labels import; settings load; the suite is green |
| **F1** CONNECT | `interpretation/fable_adapter.py` (new); `interpretation/holds.py`; `interpretation/replay.py`; `participants/http.py` (the `complete` hook and the kept bytes of a cut read, hook set only [R:connector-CONN-6]); `studio/models.py` (two InterpreterHold constants only); `studio/management/commands/interpreter_hold.py` (the release report [R:connector-CONN-1]); tests `tests/v2/test_fable_adapter.py`, `tests/v2/test_holds.py`, `tests/v2/test_replay.py`, `tests/test_participants_send.py` additions (the `complete` hook) | F0 | every row of 1.5's table with a constructed body (SSE and error bodies, built in the test), 1.5's precedence included (an error-first 200 stream FAILED, never HOLD `model`) [R:connector-CONN-4]; 1.4's refusals each with a planted stream; an incomplete stream recorded UNKNOWN with its bytes, live and replay, and a socket-level cut, a deadline cut and a cap overflow each UNKNOWN with the bytes read before the stop [R:connector-CONN-6][R:connector-CONN-2]; no usage from a stream without `message_delta` [R:connector-CONN-3]; model and fallback holds; `request_bound` and the release report [R:connector-CONN-1]; the participants' http tests unchanged and green; no `jobs.py` call reaches the Gemini interpreter |
| **F2** PROMPT | `contract/extract_prompt.py` (INSTRUCTIONS_3, `request_parts_fable`, `check_pins_fable`); `contract/extract_schema.py` (ANSWER_SHAPE_2 only); `contract/appraise_prompt.py` (`request_parts_fable` with `CLAIM_BOUND_V3`, `check_pins_fable`); `contract/appraise_read.py` (its pin check by label [R:replay-R4]); their tests | F0 | 2.1's four changes by grep, item 3 withdrawn [R:truth-T8]; ANSWER_SHAPE_2 differs from LOCAL_SCHEMA_2 by exactly 38 `maxItems` nodes; the 2.3 scans pass on INSTRUCTIONS_3; both bodies have exactly BODY_KEYS; byte-identical bodies for identical inputs; the pins handed to F0 |
| **F3** SLOT | `contract/types.py` (the reason); `contract/extract_read.py`; `contract/consistency.py` (the merged view and the K rules' stated-or-offered reading [R:truth-T3]); `contract/geometry.py` (if it reads a slot); `contract/settle.py`; `contract/claims.py` (`CLAIM_BOUND_V3` [R:replay-R1]; any slot read); `interpretation/store.py`; `engine/types.py` (the defaulted `negated_values` field), `engine/facts.py`, `engine/classes.py`, `engine/combination.py` and `engine/pairing.py` (the reader kinds of 4.3.3 [R:truth-T1][R:truth-T2][R:truth-T5]); `engine/assess.py` and `engine/coverage.py` (the labels [R:replay-R4]); `interpretation/wording.py` only where the list finds a reader of a contradiction's sides; tests incl. `tests/v2/test_properties.py`'s generator | F0 | 4.3's eight items; the 38-attribute plant test (4.3.3), with supported-only, mixed and negated-only slots, proves at every place: nothing derived from the slot established, every K rule fires on each stated or offered value, the FactSet fact non-silent and unresolved with exactly the written values, no member sentence wording a denied or unwritten value as stated; the P6 property holds with value-erasing contradictions (4.4), the demo_within cases (pass 1's contradicted session and the overfilled one) holding 43235; the two probe answers (A-v2, A-v6) read with their slot unresolved and the rest read |
| **F9** MEASURE | `engine/measure.py` (@2) and its test | F0 | events with anchors and G6-valid restatements; @1 readers unaffected |
| **F5** REPORT | `interpretation/report.py`; `participants/pricing.py`; tests | F1 | section 9's report items; 1.7's estimates with every usage field of E.1, a 1-hour write and an iteration unpriced |
| **F6** PIPE | `studio/jobs.py`; `studio/progress.py` (the `declined` and `cut_off` situations, HOLD_SET_MESSAGE as the paused phase [R:truth-T6][R:truth-T7]); `studio/review.py`, `interpretation/readers.py` and `interpretation/overlay.py` (the labels of 8.1 [R:replay-R4]); tests `tests/v2/test_jobs.py`, `test_update_pipeline.py` | F1, F2, F3 | replay stage tests for both passes on the Fable interpreter; every row of 1.5 through the stage (`_settle_interpretation`, `_settle_outcome`), with the member sentence of the run that set each hold [R:truth-T6] and of a cut-off answer [R:truth-T7]; a decline held, released, then a Resume and a Retry refused and an operator override sending once, both passes [R:connector-CONN-1]; a FAILED Fable reading retried once (pass 1, and pass 2 alone) and resumed after a release [R:connector-CONN-5]; the guard test of section 9's path list [R:connector-CONN-5]; P-6 and `_record_unsettled_holds` by adapter version; the per-kind stale threshold in `mark_stale` and `_check_loop_time`, and the startup sweep settling a 70 s-old RUNNING stage [R:connector-CONN-7]; `QUEUE_DEADLINE` 60 min; Stop between the passes; the doors' order |
| **F7** GUARD | `interpretation/sentinel.py` (KEPT); `tests/test_guard_static.py`, `tests/v2/test_retirement_manifest.py` additions | F1, F6 | the new module scanned and clean; every pin used; the planted controls red |
| **F8** OPS | `ops/install.py`; `ops/rollback_check.py` (the D15 rows and SCENARIO_V2's literals [R:replay-R6]); `ops/verify_browser.cjs` and `ops/verification/test_verify_browser.cjs` (the walk's constants and their pins [R:replay-R2]); `ops/verification/*` (denylist and vectors); `studio/management/commands/participant_access_check.py` (the bounded wait for the provider lock [R:cost-F-COST-8]); `ops/test_install_interpreter.py`, `ops/test_rollback_check.py` additions; `tests/test_customer_surface.py` vectors | F1, F6 | 1.11's installer table; one bind of the shared credential, verify clean with the participant live and the interpreter disabled or in replay [R:replay-R3]; `STOP_SECONDS['worker']` 1,500; the rollback test with section 8.5's rows, its thirteen counts non-zero on a Fable-filled database [R:replay-R6]; the walk's tests reading the `_V3` names and passing on a Fable run, a released retry of an `anthropic` run not counted a duplicate [R:replay-R2]; an access check that waits out a reading in flight [R:cost-F-COST-8]; the three readers' denylist tests green |
| **T** TOOLS (session directory) | `tools/v2/record_v2.py`, `replay_v2.py`, `score_v2.py`, `devsets_v2.py`, `v2lib.py` and their tests | F1, F9 | sections 5.3, 5.4, 6 and 8.3; the harness stops at its cap; a reservation at the body's worst case with the prefix at the write rate [R:cost-F-COST-6]; an unknown or error-ended send counted at its bound [R:connector-CONN-3]; the owner's-figure cap mode for A (spend plus next bound) [R:cost-F-COST-2]; replay refusing another adapter version [R:replay-R8]; replay reproduces an assessment byte for byte from an `.sse` recording |

Merges: F1, F2, F3, F9 and T in parallel; then F5, F6, F7, F8; pins by F0 after the last repair of F2 and F3; the full
suite, the seam check (D252) with named scenes for 1.5's table and 4.3, then the mandatory refutation of the finished
diff (FINAL-V2 9.8; AGENTS.md: the clinical generation path), the PR made a draft at the first doubt.

The w9r triage (`build-v2/lead-verify-w9r/TRIAGE.md`) is ruled with this build by the integration owner. Its cb items
G2-01 to G2-05 concern the Gemini swap's timeouts, stored-run classification, comments and prices: G2-01 and G2-03 are
superseded on the path by 1.12, G2-02 by 1.5's dispatch and `holds.record` rule, G2-05 by 1.7's kept Gemini rates;
G2-04 stays a dormant-adapter text item. Items whose files this build also owns (`jobs.py`: G1-04, G3-16, G3-17;
`report.py`: G3-30; `sentinel.py`: G3-04 to G3-08) go to the step that owns that file in this round.

---

## 11. Tests and measurement

### 11.1 Unit tests (no network, CI)

- `test_fable_adapter.py`: both bodies exactly (keys, model, effort, max_tokens, stream, the cache marker on pass 1
  only, the format on pass 2 only, no forbidden field); `body_kind` refusing every altered body (an added
  `temperature`, `thinking`, `tools`, `fallbacks`, a second message, a changed instruction byte); the assembler on
  constructed streams for every rule of 1.4 (a ping anywhere, an unknown event skipped and counted, a duplicate
  `message_start`, a delta to an unopened block, a `tool_use` block, a `citations_delta`, an event after
  `message_stop`, invalid UTF-8, `\r\n` lines); `complete` true only at `message_stop` or `error`; `describe` on streams
  and error bodies; every row of 1.5 including type-before-status precedence (a 529 `overloaded_error` FAILED, a 400
  `billing_error` HOLD quota, a 429 with no body HOLD quota, a 429 `rate_limit_error` FAILED, a 413 FAILED, a 404
  HOLD permission) and the refusal category kept as one word, never the explanation; 1.5's precedence for 200 streams:
  an `error` event first (`overloaded_error`) FAILED and never HOLD `model`, a `message_start` naming another model
  then an `error` event HOLD `model`, a stream opening with `content_block_start` HOLD `model` [R:connector-CONN-4];
  `describe` giving no usage for a stream without `message_delta`, an `error`-ended one included [R:connector-CONN-3].
- `test_holds.py`: dispatch by adapter version; a Gemini run never setting a hold; the two new reasons with their texts;
  `_check_run` accepting both providers of `READ_PROVIDERS` and refusing any other; `request_bound` true for a
  `declined` hold and for a hold an `error` event set after `message_start`, false for every other; the release report
  naming each run, encounter and request [R:connector-CONN-1].
- `test_replay.py`: an `.sse` recording read exactly as live; an incomplete recording UNKNOWN; "No recorded response
  for this request." for a changed instruction byte.
- The participants' send tests (`tests/test_participants_send.py`, `test_participants_loop.py`): `complete=None` leaves
  every outcome as before; with a hook, an EOF mid-stream, a socket-level cut of a chunked body without its terminating
  chunk (a local server closing mid-chunk: requests raises `ChunkedEncodingError` inside `iter_content`), a deadline cut
  and a cap overflow are each UNKNOWN with the bytes read before the stop kept and no usage [R:connector-CONN-6]
  [R:connector-CONN-2][R:connector-CONN-3]. The first text's test (a deadline cut UNKNOWN without bytes, an EOF with)
  could be met by a fake session that ends cleanly, which proves the rare path and not the production one.
- The existing suites that read `interpretation.MODEL`/`PROVIDER` as Gemini's (the v1 adapter, pipeline and prompt
  tests, `tests/v2/test_adapter.py`) are untouched and stay green, because those names keep their values (1.1); the
  retired modules' tests are edited by no step (FINAL-V2 8.0). The kept modules' suites that pin the interpreter in use
  (`tests/test_interpretation_holds.py`, `test_interpretation_pricing.py`, `test_interpretation_report.py`,
  `tests/v2/test_holds.py`, `test_report.py`, `test_jobs.py`, `test_replay.py`) gain the `_V3` cases beside the Gemini
  ones.
- F2's prompt tests and scans; F3's plant test, store tests and property tests (4.3, 4.4: written values only, the
  three reader kinds, the K rules on stated or offered values, value-erasing contradictions in 9.4's generator, the date
  slot's written dates with L1 run on each [R:truth-T9], an overfilled examination device asking which device and
  never "not documented" [R:truth-T2], a complete enteroscopy with a denied "terminated" never worded incomplete
  [R:truth-T5], K4 firing on an overfilled organ [R:truth-T3], demo_within's two cases holding 43235 [R:truth-T1]); F5's
  pricing vectors from E.1's real usage objects; F6's stage tests (1.5's rows through the pipeline, a refusal pausing
  both passes, the request-bound block after a release [R:connector-CONN-1], each hold reason's member sentence
  [R:truth-T6], the cut-off sentence [R:truth-T7], Fable retry and resume [R:connector-CONN-5], Stop and Resume, the
  per-kind stale sweep: a 1,000 s-old interpret stage not swept by the periodic sweep, a 700 s-old predict swept, and
  any RUNNING stage settled by the worker's startup sweep [R:connector-CONN-7]); F8's denylist vectors (section 9), the
  walk's tests [R:replay-R2], the verify rule for the shared key [R:replay-R3], the access check's wait
  [R:cost-F-COST-8]; the D15 rollback test with non-zero counts [R:replay-R6].

### 11.2 D1-D3 for Fable (development documents only, every document checked against `DEV-EXCLUSION.sha256`)

- **D1** (guard $3, real maximum about $8.6: 7.4 [R:cost-F-COST-6]): one short development document, both passes,
  through the tree's `fable_adapter`, after F0 wrote `CLAIM_BOUND_SHA256_V3` [R:replay-R1]. Proves: both request forms
  accepted, pass 2's schema in the connector's canonical key order [R:replay-R7]; the stream read; model pin; usage with
  `cache_creation_input_tokens` equal to the prefix; the reader's acceptance; settle reported refused while
  `HEALTH_THRESHOLDS_SHA256_V3` is unwritten (as D1v); and records the stream's bytes per output token, the longest
  inter-event gap, each send's output rate [R:connector-CONN-2], and pass 1's exact prefix tokens. If a 128,000-token
  stream would pass 16 MiB at the measured byte rate, the cap rises before D2.
- **D2** (guard $50 [R:cost-F-COST-1]): the 10 `devsets/d2cmp` documents x 1, pass 1 first. Gates G-SCHEMA and G-SIZE;
  latency, each send's rate and the thinking tail by document size [R:truth-T7]; the claim count per document and pass
  2's output per claim on the long notes [R:replay-R1]; cache hits.
- **D3** (three batches of 30 x 1, guard $115 each [R:cost-F-COST-1]): FINAL-V2 9.6's 30 development documents (the
  refutation's included where the exclusion list allows; E/M cases with their member values). Gates G-HEALTH, G-DOUBT,
  G-NOISE; stability across the three runs; hold causes. `HEALTH_THRESHOLDS_SHA256_V3` is set from D3's distribution,
  then replay settles.

### 11.3 The gates, restated with Fable's numbers (FINAL-V2 9.2)

| gate | measured on | passes when | probe value | if it fails |
|---|---|---|---|---|
| G-SCHEMA | D1, D2 | 0 whole-answer refusals for both passes (an overfilled slot is no longer one, except on an attribute 4.3.8 keeps refused) | pass 1: 2 of 8 short notes refused at bounds, both slot slips (F2high); 0 of 10 with two slot sentences close to 2.1's items 1-2 (F3all) [R:truth-T1]; pass 2: 0 of 6 with the schema (F2high-p2), 0 of 10 (F3all, F3long) | the instruction or the shown shape, never the reader |
| G-SIZE | D2, the two 19.4 KB notes included | every pass-1 answer at most 85% of 128,000 output tokens (108,800); the largest claim set at most 85% of `CLAIM_BOUND_V3` (850 of 1,000); every pass-2 answer at most 108,800, and pass 2's output per claim on the two 19.4 KB notes at most 108.8 tokens, so a set at the bound fits 85% of 128,000; every send finished inside 85% of its 1,320 s deadline (1,122 s) [R:replay-R1][R:cost-F-COST-1][R:truth-T4] | F3all/F3long (a near neighbour of this request): pass 1 79,758 and 73,224; claim sets 756 and 711; pass 2 77,483 and 70,263 (102.5 and 98.8 per claim); longest send 615.5 s | pass 1: 2.4's compact form as `gemini-events@4`; pass 2: fewer controls on attributes that can only hold (FINAL-V2 9.2's pass-2 remedy, which the first text dropped; the compact form changes no claim count) as `gemini-appraisal@3`; then the owner (class b) for any bound that would refuse a development note; the deadline per 1.12 [R:replay-R1][R:cost-F-COST-1][R:truth-T4] |
| G-HEALTH | D3 | median establishment at least 0.90; control acceptance at most 5% of controlled pairs; no development document refused by the thresholds set from this distribution | median 0.97 (0.93-1.00); max 4.1% (replay-F2high-p2); the long notes 0.98-0.99, controls 0-0.7% (F3long) - all under the schema's declared key order, not the canonical order the connector sends [R:replay-R7] | templates, controls or A-clauses (appraisal@3); for a fall traced to the canonical key order, 2.2's property names (appraisal@3) |
| G-DOUBT | D3 | as FINAL-V2 9.2 | not measured | the doubt clause |
| G-NOISE | D3, with sections 5.3, 5.4 and 6's measurement fixes in place | unnecessary holds at most 12% and READY recall at least 75%, by cause (FINAL-V2's causes plus `unestablished:slot_overfull`) | 3 of 8 holds (37.5%), recall 5 of 8 (62.5%) on 6 notes (5.5) | the dominant cause repaired (prompt, templates, geometry, a coding rule), never settle weakened, never a word list; 5.1's and 5.4's recorded candidates are the first to weigh |
| G-GUARD | every measured assessment | `legacy_calls = retired_calls = 0` | 6 of 6 zero | a defect |

### 11.4 The acceptance run and the walk

- **A**: after D1-D3 pass and the owner's decision (7.5), by the acceptance owner's tool from its manifest, that tool
  enforcing the owner's figure as 7.5 says (spend plus the next send's bound, checked before every send)
  [R:cost-F-COST-2], with section 6's scorer and the pipeline's R1 word runs; THRESHOLDS.md's gate, the acceptance
  owner's; c2e53f8e beside it as a diagnostic (owner amendment 2026-11-09).
- **The installed walk** (FINAL-V2 9.9), with the operator evidence reading both runs `claude-fable-5-2` (in place of
  `gemini-4-argon`), the provider `anthropic`, the new versions, `legacy_calls` and `retired_calls` 0, the cache and
  thinking tokens in the report, and at least one long note walked to the end (its latency recorded) or, if it is cut,
  shown truthfully as a reading that reached its limit [R:truth-T7]. The walk is `ops/verify_browser.cjs` as F8 changes
  it (section 9); unchanged, it would fail every Fable encounter [R:replay-R2].

---

## Owner questions (only the owner can decide) [R:cost-F-COST-4][R:replay-R5][R:cost-F-COST-2]

1. **A's budget (class d; D275; 7.5).** The figure for A (and A' if approved), from the corrected range: 347 documents
   about $509 with every pass-1 a cache hit, $629 with no marker, $660 as production pays (every pass 1 writing the
   cache), up to $614-765 with long notes cut at the worst; 645 documents $945-1,226, up to $1,142-1,423; the Batches
   option $254-330 (347), with its build cost. The figure binds as a cap checked before every send (7.5).
2. **The Anthropic account's headroom and a site reserve (class d).** The account's configured monthly limit or prepaid
   balance (the session cannot read it), against the installed site's monthly Anthropic usage, D1-D3 (about $155-195)
   and A; and whether the harness keeps a reserve below that limit for the installed site's Fable 5.1 second reader,
   which shares the account and holds for every upload if a balance runs out mid-batch (7.5). D183 forbids the session a
   ceiling of its own, so without the owner's word it runs with none and the exposure stands.
3. **Recorded, not asked (D275's text governs).** "A refusal is a hold" makes one document's decline pause every
   customer's reading until an operator reviews it; this revision keeps that and adds the request-bound block (1.5). If
   the owner prefers a decline to hold only its own document, that is a product decision (class a) the build would
   follow. Likewise section 3's optional measurement: a lower effort above a size (unmeasured, not needed now that
   128,000 tokens read both long notes).

---

## Appendix: numbers and their sources

| number | source |
|---|---|
| 44,740-45,155 / 52,150-52,175 pass-1 input tokens; 44,467 + 0.493 x chars | F2high MANIFEST pass1.usage, fitted in this session |
| 10,663-21,002 output; thinking 5,766-12,807 | F2high bodies, `output_tokens_details.thinking_tokens` |
| 64,000 at the cut; thinking 29,109 / 40,743; 491.48 s / 523.63 s | F2high MANIFEST and bodies |
| 80,471 / 53,565 answer chars at the cut; 30 / 16 complete events | F2high bodies, parsed in this session |
| 38 events in each long note's v1 answer | `fresh2-frozen/A/note8/r1.body`, `fresh2-frozen/C/C2MEM-023/r1.body` |
| 6,239-7,737 / 6,252-12,562 pass-2 tokens; 49.3-108.7 s; 68-106 claims | F2high-p2 MANIFEST |
| 115.6-131.6 tok/s | F2high, F2high-p2 |
| 2 overfilled slots (E2 device 3; Y1 organ 2) | F2high bodies scanned against `extract_schema.ATTRIBUTES` |
| 19 rows: 14 / 4 / 1 as scored; 15 / 3 / 1 with word runs; 16 / 3 / 0 with the scorer rule | `devsets/score-F2high-p2`, `build-v2/amend2/verify/score-F2high-p2-wordruns`, section 6 |
| 103 FRESH documents: median 823, mean 2,472, p90 2,438, max 19,460, 8 at 10,000+ | `fresh/inputs/{A,B,C}` |
| 119,146-character instruction, 89,759 of schema, 1,436 schema nodes, 38 slots | the probe tree, measured read-only in this session |
| $15.878128, $2.435728, $0, $1.718684, $4.2778 | the batches' SUMMARY.json |
| 79,758 / 73,224 long-note pass-1 output (thinking 35,841 / 31,604); 615.5 / 566.3 s; short notes 9,716-22,135, 79.8-190.6 s; 41-108 / 756 / 711 claims; 0 overfilled slots in 10 answers; $17.333104 (harness bound) | `anthropic-project/batches/F3all` MANIFEST, SUMMARY and bodies (frozen 19:18:05Z), read by the refutation judge [R:truth-T4][R:replay-R1][R:cost-F-COST-1] |
| 77,483 / 70,263 long-note pass-2 output (thinking 43,623 / 38,435) at 756 / 711 claims; 38,113 / 37,844 input; 590.7 / 536.9 s; health 336/340, 317/322; $6.517496 | `anthropic-project/batches/F3long` MANIFEST, SUMMARY and bodies (frozen 19:38:01Z); `devsets/replay-F3long/*/r1/health.json` [same tags] |
| claim fit 40.5 + 0.0357 x chars; pass-2 input 3,240 + 47.3 x claims; the 7.1, 7.3 and 7.4 figures; worst-case bounds $5.57-5.64 / $5.52 | F3all + F3long, fitted by the refutation judge: `build-v2/amend2/judge-scripts/model.py` (sha256 `cf814230...`) and its `model.out.txt` [R:cost-F-COST-1][R:cost-F-COST-5][R:cost-F-COST-6] |
| the revised merged view's direction on the built engine (written values: no digital examination, 45378 supported as under the true reading; with `_claims_session` reading a contradiction's sides, 43235 held within the EUS) | `build-v2/amend2/judge-scripts/repair_check.py` (sha256 `1f50c421...`, in-memory monkeypatch only, no tree edit) and `repair_check.out.txt` [R:truth-T1][R:truth-T2] |
| short notes $0.59-1.44 (hit) / $1.03-1.87 (production) / $0.94-1.79 (no marker) | F3all usage at 1.7's rates [R:cost-F-COST-5] |
| 22 correct, 4 unnecessary holds, 1 wrong READY (the A-v5 artifact) on F3all's 27 short-note rows; long notes 10 correct, 7 unnecessary holds, 0 wrong READY, 0 wrong exclusion | `devsets/score-F3all/summary.json`, `devsets/score-F3long/summary.json` |
