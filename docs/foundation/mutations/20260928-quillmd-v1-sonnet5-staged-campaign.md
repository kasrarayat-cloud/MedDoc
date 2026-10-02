# Declaration — V1 staged synthetic Sonnet 5 campaign, September 28, 2026

This is the project record of an owner spending approval, written before any provider request under it. It binds
every paid attempt of this campaign to one authority. It is not a new allowance, it does not reset when a session or
assistant changes, and nothing in it covers Stripe, AWS, contracts, subscriptions, real patient data or a launch.

## Authority

```
campaign: quillmd-v1-sonnet5-staged-40
authority_id: quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk
authorization: owner 2026-09-28 approved the staged $40 maximum at the stated limits
owner_words: Approve the staged $40 maximum
```

The question the owner answered, verbatim: "Do you approve the report’s one-time synthetic Sonnet 5 testing budget:
up to $40 total ($5 model check, then up to $25 mapping and $10 notes only if that check succeeds)? This excludes live
Stripe payments, AWS purchases and real patient data. The report explicitly lists this spending as unapproved."

Provenance, stated at its actual strength. The owner answered in a desktop assistant conversation; that assistant
recorded the reply as `QuillMD-V1-Sonnet5-Budget-Approval-20260928.json` (`recorded_at_utc` 2026-09-28T22:59:06Z,
which is the recording time, not the reply time). The owner delivered that record to this VPS session directly, in
the session's own user turn, at about 23:00Z. It is stored verbatim at
`docs/rebuild/v1/QuillMD-V1-Sonnet5-Budget-Approval-20260928.json`. A search of the repository, every worktree, the
runtime evidence and git history on all refs found no earlier record of this authority, so this is not a duplicate.
The unexecuted 2026-09-26 WM narrative Stage 1 grant (Sonnet 4.6, candidate `b7e1534d`) is a different grant and is
not used, reused or consumed here.

## Limits (provider cost, USD, cumulative across sessions, retries and workers)

```
total_limit_provider_usd: 40.00
stage: model_check limit_provider_usd 5.00 max_requests 10 requires none
stage: mapping limit_provider_usd 25.00 requires model_check_passed
stage: ordinary_notes limit_provider_usd 10.00 requires model_check_passed
unused_stage_budget_transfers: no
```

A stage starts only after `model_check` has **passed with recorded evidence** (served model `claude-sonnet-5`,
`end_turn`, parsed and validated, settled, receipts retained, billing audit clean). A failed model check stops the
campaign for offline diagnosis; the mapping and notes allocations are never used to repeat a failed setup.

The limits are provider cost at the configured rates below, applied to the provider-reported usage of each response.
The organization cost API refused the generation key (2026-09-27), so no invoice is available to the session; the
provider's actual charge is to be read by the owner from the provider console and is recorded separately from these
figures. Wallet charges in the private QA database are 1.5 × provider cost and are synthetic.

## Model and request, fixed before any send

```
model: claude-sonnet-5
provider: anthropic
rates: input 2 output 10 cached 0.20 (USD per million tokens)
thinking: disabled
effort: medium
inference_geo: unset
pricing_version model_check: configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d
pricing_version mapping: configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d
pricing_version ordinary_notes: configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d
pricing_version ordinary_notes_field_relations: configured-v1:eb280d15cbfc2cf52477c57040c3ff11d60352aac5d9a9894bdae4e6a0594180
```

The versions were computed offline with the candidate's own `core.generation.configuration()` at `8e3dcfd0` under
these settings (and `QUILLMD_DEEPGRAM_RATE_PER_MINUTE=0.0043`, no discount); the first equals the migration note's
documented Sonnet 5 default. Profiles: generation `claude-sonnet-5-v1` (8,000 output tokens, 120 s); mapping
`claude-sonnet-5-blank-mapping-v3` (20,000, 120 s); ordinary field relations `claude-sonnet-5-ordinary-v1` (20,000,
120 s). No fallback to any other model: a refused or unavailable Sonnet 5 stops the campaign.

The workspace's default inference geography can be read only with an Admin credential. Until it is known, every
attempt is admitted and counted at **1.1 × its maximum cost**.

## Admission, per request

- Maximum exposure is the candidate's own `maximum_cost` for the exact request (input byte bound + output limit at the
  rates above), × 1.1. It must fit the remaining stage and total limits **before** the request is built; otherwise
  admission stops.
- Every attempt is written to an append-only ledger before it is sent (write-once files, one runner at a time). An
  outcome that is not reconciled counts at its maximum exposure. A lost response is never re-sent; the SDK runs with
  `max_retries=0`, and any retry is a new recorded attempt inside the same limits.
- Prior attempts and unknown outcomes are reconciled before any new admission. At recording time there are none for
  this campaign: the only V1 provider interactions on record are the free model-metadata request and eight
  token-count requests of 2026-09-27, all completed.

## Where it runs, and what its results prove

An isolated private QA process: its own synthetic PostgreSQL database and state directory, the candidate's real
views (authenticated) and real worker function (`core.jobs.run_one`), fresh synthetic encounters. It is **QA-worker
evidence, never installed-worker evidence**. The installed release `dedac162`, its services, configuration, flags and
database are not touched. The candidate is not promoted to obtain a test. Each attempt records the runner's exact
commit and the hashes of the engine files it ran.

Credential: the runner never reads `rebuild/.env` by any route. It uses only an owner-delivered campaign credential
file, in a scrubbed environment with the SDK's other credential sources disabled (`ANTHROPIC_CONFIG_DIR` pointed at an
empty directory; no profile, federation, base-URL or custom-header variables). Until that file exists, the campaign
cannot start.

```
credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/anthropic-api-key
credential_file_requirements: one line, the API key only; mode 0600; owned by the account that runs the runner
```

Recommended to the owner (not required by this declaration): a dedicated API key in a workspace whose provider-side
spend limit is at most the remaining campaign total, revoked when the campaign ends. That makes the ceiling hard at
the provider as well as in the runner's ledger.

## Inputs (rights)

Only synthetic material authored for this project is sent: seeded synthetic forms and notes, and synthetic
structure-twins of the development findings. The 40 development originals carry "no provider upload" in their rights
ledger, so none of their content is sent; they are exercised in offline, mocked app replays only.

## Stop conditions

Any stop reason other than `end_turn`; a timeout, uncertain outcome or reconciliation; a served model other than
`claude-sonnet-5`; `inference_geo: us` metered while unset; output above 70% of the output limit; a validator or
billing-audit failure; unsafe output (a clinical answer accepted without source support, or a wrong side, denial or
destination); an admission that does not fit the remaining limits; a leaked credential in any retained file.

## Retained evidence (no secrets)

Exact request bodies, raw responses, usage, served model id, stop reason, the per-attempt cost bound and computed
cost, the settlement and wallet records, failures, and a provenance manifest per attempt; the validator's decision and
any clinician review change are kept separately from the raw model output.
