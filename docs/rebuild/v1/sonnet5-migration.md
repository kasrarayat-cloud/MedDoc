# Claude Sonnet 5 migration — 2026-09-27

**Status: code only. The deployed configuration is unchanged.** This change edits code, tests, this note,
[`cost-definition.md`](../cost-definition.md) and `rebuild/.env.example`. The switch itself is the owner's act. It means
editing the private environment, which no session reads or writes, and restarting the services. This note gives the
exact values for the switch and for the rollback, the pricing version to expect for each, and a bounded live check.
It is the clinical generation path, so the refutation pass over the finished diff is required before merge.

Sources, read 2026-09-27:
[migration guide](https://platform.claude.com/docs/en/models/sonnet-5/migration-guide),
[pricing](https://platform.claude.com/docs/en/about-claude/pricing),
[structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
The installed SDK, `anthropic==0.125.0`, already carries every type used; no upgrade is needed.

## What changed in the code

| Area | Before | Now |
|---|---|---|
| Request | one call: `max_tokens=6000`, 60 s, no `thinking`/`effort` | model-keyed profile (`core.generation.request_profile`), snapshotted in `Job.config`, hashed into `pricing_version` |
| claude-sonnet-4-6 | — | the **legacy profile**: the old call byte for byte (tested down to the HTTP body), and the old fingerprint |
| claude-sonnet-5 | would have run Sonnet 5's defaults (adaptive thinking, effort `high`) | explicit `thinking` and `output_config.effort`; never `temperature`/`top_p`/`top_k`/`budget_tokens`/prefill |
| claude-haiku-4-5, claude-sonnet-4-5-20250929 | — | the legacy profile, like claude-sonnet-4-6 (the explicit list `LEGACY_CLAUDE_MODELS`, matched exactly). `claude-opus-4-1` is not listed: it is deprecated (retiring 2026-08-05) and unused here, so it is refused |
| any other Claude model id (e.g. `claude-mythos-preview`, `claude-opus-5`, `claude-sonnet-5-1`, a dated or misspelt id such as `Claude-Sonnet-4-6`) | the old call, which on a newer model means a larger tokenizer and default thinking | **refused before any request** until it has its own profile. Deny by default, not a version comparison |
| Output bound | `6000` written twice | one `max_output_tokens` per profile, read by the hold and the request: 6000 / 8000 / 16000 |
| Timeout | 60 s | legacy 60 s; Sonnet 5 120 s, under the worker's `TimeoutStopSec=150` and the 5-minute stale mark |
| Receipt units | tokens | + `inference_geo`, `thinking_tokens` (if reported), `stop_reason`, `stop_details_category` — new receipts only |
| US-only inference | not priced | ×1.1 when **metered** `us` on Claude 4.6+; `audit_billing` recomputes in lockstep; old receipts unchanged |
| `configuration_status` | mode, provider, key presence | + model, three rates, Sonnet 5 settings, request profile, `pricing_version`; the admin console's services page renders the same rows from the same function (`admin_console.language_model_rows`) |

Response handling needed no change and is now tested with real SDK objects. Anything other than
`stop_reason: end_turn` is refused, and only `type == "text"` blocks are read. Refusal, `max_tokens` (even with JSON
that happens to parse) and `model_context_window_exceeded` all leave the document untouched. They are settled, the job
fails as a platform failure, and the charge is absorbed. A thinking block before the text changes nothing.

## Values to set — Claude Sonnet 5

Change these four together, exactly as written. The rate strings are hashed, so `0.2` and `0.20` produce different
pricing versions.

```
QUILLMD_AI_MODEL=claude-sonnet-5
QUILLMD_AI_INPUT_RATE=2
QUILLMD_AI_OUTPUT_RATE=10
QUILLMD_AI_CACHED_RATE=0.20
```

Request profile. The defaults apply when these are unset:

```
# Thinking: disabled | adaptive
QUILLMD_AI_THINKING=disabled
# Effort: low | medium | high
QUILLMD_AI_EFFORT=medium
# Inference geography: empty (inference_geo is not sent), or us (US-only inference, billed 1.1x)
QUILLMD_AI_INFERENCE_GEO=
```

Copy value lines exactly as they are. Comments go on their own line, as in `rebuild/.env.example`, never after a value.
The services read the private environment through systemd's `EnvironmentFile=`, which treats `#` as a comment only at
the start of a line and keeps an inline `# …` as part of the value. So `QUILLMD_AI_THINKING=disabled # …` or
`QUILLMD_AI_INFERENCE_GEO= # …` makes every generation refused. A `manage.py` run outside systemd reads the same file
with python-dotenv, which strips some inline comments (after a value) and not others (after an empty value), so its
output can disagree with what the services loaded.

`disabled` / `medium` is the parity choice. Thinking stays off, as on Sonnet 4.6, and the migration guide rates Sonnet 5
at `medium` as comparable to Sonnet 4.6 at `high`. `adaptive` is **an owner decision**, to be taken on measured quality,
latency and cost. With it, `display` is fixed to `omitted`, so no reasoning summary can reach a stored receipt, and the
output bound doubles to 16000.

`QUILLMD_AI_INFERENCE_GEO=us` is also an owner decision. It depends on the workspace's default geography, which only an
Admin credential can read. Settlement bills 1.1× whenever the provider **meters** `us`, whether or not it was requested.
Set this so the hold includes it too.

Any other value refuses every generation before a request is made, and says why on `configuration_status`.
Transcription is unaffected.

## Rollback values — Claude Sonnet 4.6

```
QUILLMD_AI_MODEL=claude-sonnet-4-6
QUILLMD_AI_INPUT_RATE=3
QUILLMD_AI_OUTPUT_RATE=15
QUILLMD_AI_CACHED_RATE=0.30
# Empty, so inference_geo is not sent: the byte-identical request
QUILLMD_AI_INFERENCE_GEO=
```

`QUILLMD_AI_THINKING` and `QUILLMD_AI_EFFORT` are ignored for claude-sonnet-4-6 and may stay as they are. Rollback is a
configuration change: there is no migration, and no code or data change. claude-sonnet-4-6 is Active until at least
2027-02-17.

## Expected `pricing_version`

These values assume the rest of the price is as recorded for the live system: `QUILLMD_DEEPGRAM_RATE_PER_MINUTE=0.0043`,
no per-second voice rate, and no provider discount. If any of those differ, the version differs. Either way,
`configuration_status` prints the version a job queued now would carry, and that printed value is the one to record.

| Model | Thinking | Effort | Geography | `pricing_version` |
|---|---|---|---|---|
| claude-sonnet-4-6 (rollback) | ignored | ignored | unset | `configured-v1:fcc802676fc66faa1dca2e574588ab96d9ee90cba679f047d6a80bb7924583ae` |
| claude-sonnet-4-6 | ignored | ignored | us | `configured-v1:25ba5f3bdd0fc8640985d0bdcb4f1e62b1ab7101d6303fe09fc0e65bd09c858c` |
| claude-sonnet-5 | disabled | low | unset | `configured-v1:e27cb778353227b236afe4a42b4772d13ea4fa3d1022eef1198c9a7acca67371` |
| **claude-sonnet-5 (default)** | **disabled** | **medium** | **unset** | **`configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d`** |
| claude-sonnet-5 | disabled | high | unset | `configured-v1:d05a8af78bd1017416da8c881fba9adb8739f18af10adbdfcdda86f9890faba3` |
| claude-sonnet-5 | adaptive | low | unset | `configured-v1:f003ef808325f23fb92ed0895f368c03b19cc2cbf4c39eef27781c167e7ee9f2` |
| claude-sonnet-5 | adaptive | medium | unset | `configured-v1:359a0737160deaf1f0c07168c63dd12012929f0d2498189feaa814afaa67419a` |
| claude-sonnet-5 | adaptive | high | unset | `configured-v1:72499d75fc8e03228190c025154113fcca82da8ab3274ffce9a48ab89b68b4db` |
| claude-sonnet-5 | disabled | low | us | `configured-v1:70ec5230f7fe896cad38ca2a2e97590ee47874095420c50f97b594fd4dbe37cd` |
| claude-sonnet-5 | disabled | medium | us | `configured-v1:f95e38269021772b2800c48ce729e149a0f27f272bf3ec63b122dde81f6d609e` |
| claude-sonnet-5 | disabled | high | us | `configured-v1:63339324c0aa795ef08e0624f4f19d0a4f45b3af8d7f6734c065685f36f002a2` |
| claude-sonnet-5 | adaptive | low | us | `configured-v1:3ec871643b8d5d2971260b1c11686abec5925238be264293ca88f2c1fbca9708` |
| claude-sonnet-5 | adaptive | medium | us | `configured-v1:850dbe5af4dc78ef141b9e9701ea6692a411f5f4ec6195b88cb705df9b7c8a24` |
| claude-sonnet-5 | adaptive | high | us | `configured-v1:f3db6b8f87330ad6e72fad1394a596b82f5ced5968736561a5321f9639468573` |

Four of these are pinned by tests (`core/tests/test_sonnet5_profile.py`): rollback, default, adaptive/medium and
disabled/medium/us. A config-only switch with no profile would have produced
`configured-v1:64e88144…`. That value must never appear, and the test asserts it does not.

As an example of the hold, take the three-line synthetic note `verify_live` uses. The maximum charge is $0.19 on Sonnet
4.6, $0.16 on Sonnet 5 with thinking disabled, and $0.28 adaptive. US-only raises each by 10%.

## Switching (owner)

1. Declare the expected delta first (runbook §2.5). For the switch, the declaration covers configuration only:
   `pricing_version` moves from the rollback value to the table value, and nothing else changes.
2. Drain. There must be no generation `queued`, `running` or in `reconciliation`. A queued job keeps the model and profile
   it was quoted with. A page loaded before the change still holds a quote signed under the old model and prices (it
   lives 10 minutes). When it is used after the restart, enqueue compares its `pricing_version` with the current one
   and refuses it: no job, no hold, nothing sent. The doctor sees "The prices or the language model changed after this
   page loaded" and the page re-quotes. Draining is therefore enough; open pages need no action. `configuration_status`
   and the services page print `live generation jobs: N queued, M running, R in reconciliation` (counts only); drained
   means all three are 0. A job in reconciliation does not clear by waiting: its hold is kept until you reconcile it.
   Switching `QUILLMD_AI_MODE` between `live` and `fixture` is also a stop: a quote from the other mode is refused at
   enqueue, and a job already queued in the other mode is refused by the worker before anything is sent (not processed,
   nothing charged, hold released).
3. Set the four values and the profile in the private environment, then restart the doctor, admin and worker services.
   They read the environment only at start.
4. Run `manage.py configuration_status`. Confirm the model, the rates, `request profile: explicit {…}` and the
   `pricing_version` from the table.

## Bounded live verification (owner-approved spend, synthetic only)

This check spends real money, so it needs explicit owner approval (money class d). Scope: `SYNTHETIC_ONLY`, the
synthetic doctor account, generation only. `verify_live` also spends on Deepgram, and its 120-second wait matches the
new timeout with no slack. Budget: at most 10 requests. Each request's provider cost is bounded by its maximum cost,
which is the hold it displays before sending ÷ 1.5. For the three-line note the hold is $0.31 at most (adaptive with
US-only); larger forms and notes hold more. Sum the displayed holds before starting. Use **fresh encounters**. `request_key` is `generation:<encounter>:<revision>`, so re-asking
on an old revision returns the old job, and would verify nothing.

Suggested set: five legacy-contract forms and five tab-contract forms from the frozen synthetic fixtures.

For **each** request, read the job, the `Usage` row, and the stored provider result (**Download provider result**,
which is available for charged jobs). Check:

| Check | Where | Expect |
|---|---|---|
| model served | provider result `model` | `claude-sonnet-5` |
| stop | `Usage.units.stop_reason` | `end_turn` |
| block types | provider result `content[].type` | disabled: `["text"]`; adaptive: `thinking`… then `text`, each thinking block with empty `thinking` |
| input bound | `units.input_tokens` against the byte bound (`maximum_cost` input term) | ratio well under 1; record it |
| output headroom | `units.output_tokens` (and `thinking_tokens`) against `job.config.request_profile.max_output_tokens` | under 70% |
| latency | `job.finished_at − job.started_at` | under 90 s, with the 120 s timeout. The first request per schema also pays grammar compilation |
| geography | `units.inference_geo` | `global`, or `us` only if configured |
| provider | `Usage.provider` | `anthropic:claude-sonnet-5` |
| price | `job.config.pricing_version` | the table value |
| charge | `Usage.charged_cost` | exactly 1.5 × `actual_cost`, and no more than the hold |
| audit | `manage.py audit_billing` | `all_checks_pass: true` |

**Stop and roll back** if any of these happens:

- any `stop_reason` other than `end_turn`
- any timeout or `reconciliation`
- `inference_geo: us` metered while unset. Then the workspace default is US-only: decide `QUILLMD_AI_INFERENCE_GEO`.
- output above 70% of `max_tokens`
- a served model other than `claude-sonnet-5`

Quality is judged separately. Compare against the Sonnet 4.6 results on the same frozen fixtures, using the existing
frozen scorers, and have the owner review whether adaptive thinking is worth its cost and latency. The WM narrative
campaign runner (another stream) pins claude-sonnet-4-6 and `fcc80267…`. Re-running it on Sonnet 5 needs a new campaign
id with its own expected model, rates and version.

## Rolling back

Set the rollback values, restart the three services, and confirm that `configuration_status` shows exactly
`request profile: legacy (the pre-profile request, unchanged)` and `configured-v1:fcc80267…`. If
`QUILLMD_AI_INFERENCE_GEO=us` was left set, the line reads `request profile: NOT the pre-profile request: legacy-v1 plus
inference_geo us` instead: that request sends `inference_geo`, holds 1.1× and has a different `pricing_version`, so it is
not the rollback. Jobs already queued under Sonnet 5 keep their Sonnet 5 snapshot, so drain first. A page loaded before
the rollback cannot queue Sonnet 5 afterwards: its quote no longer matches the current `pricing_version`, so it is refused
before any hold, and the page re-quotes under the rollback values.

## Open, and not decidable in code

- **Thinking mode and effort.** This is a product and quality decision (owner), to be taken on the bounded evaluation.
  Record it as a ruling.
- **The workspace's default `inference_geo`.** Only an Admin credential can read it (owner).
- **Data-processing terms.** Confirm the BAA and DPA cover `claude-sonnet-5`.
  `docs/rebuild/patient-data-release-requirements.md` names claude-sonnet-4-6.
- **Rate limits.** Sonnet 5 has its own rate-limit bucket. Confirm the organization's tier in the Console.
- **Structured outputs with adaptive thinking.** The structured-outputs page says nothing about this combination, so the
  bounded check must include adaptive requests before it is chosen.
- **Refusal billing.** Anthropic's rule for refusals that arrive before any output is documented for other models. For
  Sonnet 5's cyber refusals it is inferred. An absorbed refusal records the metered tokens as platform cost, and
  `stop_details_category` is kept for reconciliation.
