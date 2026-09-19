# Declared act — one end-to-end recording demonstration against the real provider

**Date:** 2026-09-18 · **Act:** run `rebuild/verify-private-release.mjs --expected-release <TARGET>` against the
private services with `QUILLMD_BETA_LIVE=1`, after the recording repair is activated.

This is money, so it is declared before it runs. The numbers below are what MUST be true afterwards; anything else is
the finding.

## Why this harness and not a script written for the occasion

It is the existing, reviewed release-proof mechanism. It uses the existing synthetic seed accounts, the existing
private credential file (`rebuild/.runtime/private-access.json`, mode 0600, asserted before use), the existing
provider configuration held by the services themselves, and it enforces its own spending ceiling. **No credential is
read, printed or copied by this session:** the services already hold the provider keys, and the harness reads the
account file itself without echoing it.

The speech is generated locally by `espeak-ng` — one sentence, about six seconds — so no recording of any person is
involved at any point.

## What it will create

| record | expected | note |
| --- | --- | --- |
| encounters | **+1** | synthetic-only, created through the browser by the synthetic doctor |
| transcription jobs | **+1** | the demonstration: authenticated HTTP upload → worker → Deepgram |
| generation jobs | **+1** | the same harness also proves the Anthropic path and the admin console |
| `Usage` rows | **+2** | one per metered job, neither simulated |
| `ProviderReceipt` rows | **+2** | request ids matching Job and Usage on both |
| finalized documents | **+1** | the new encounter only; **no existing document is touched** |
| synthetic users | **+1** | `release-<timestamp>@synthetic.quillmd.invalid`, created by the invitation check |
| promo wallets | **+1** | $10 welcome grant, exactly one `welcome` ledger entry |
| audit events | grows | by this run's own rows only |

## What it will charge

| | expected |
| --- | --- |
| transcription, actual | ~$0.0005 — the previously measured 6.43 s sample cost $0.00046 |
| transcription, charged | actual × 1.5, and never above the per-recording limit displayed in the quote |
| generation, actual | ~$0.02 — the six prior Anthropic calls averaged $0.023 |
| generation, charged | actual × 1.5, drawn from the doctor's personal promotional credit |
| **total charged, both jobs** | **strictly greater than 0 and at most USD 1**, asserted by the harness itself |

Spend to date across the whole programme is $0.1418 (6 Anthropic, 4 Deepgram). This run is expected to add well under
one cent of provider cost.

## What MUST NOT happen

- no existing encounter, document, job, usage row, receipt or ledger entry is modified or deleted
- **no reservation is left held** — the harness asserts `Reservation.objects.filter(job__in=jobs, state='held')` is
  empty, which is the proof that both settled exactly once
- no charge exceeds its displayed quote, and the two together do not exceed USD 1
- nothing but synthetic material reaches the provider

## Evidence retained

The sanitized JSON report names: the release under test, both provider request ids, both actual and charged costs,
the pricing snapshot version, the submitted artifact's identity, the decoded audio length, and the held-reservation
count. The transcript is displayed in the application and downloadable from it; it is **not** copied into any report.
The exported `.docx` is deleted after its assertions. Application records, originals, ledger and audit rows remain.

## If it fails

⚠️ **A failure is reported as a failure, with the specific dependency named. It is never replaced with a simulated
result.** If the provider key is absent the job stops with "Transcription provider is not connected", nothing is
charged, and that is the answer. If a quota or authentication error occurs, the provider's classification is recorded
and the run stops.
