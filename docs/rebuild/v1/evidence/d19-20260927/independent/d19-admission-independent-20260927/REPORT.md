# Independent D19 generation-admission refutation

Reviewer: Astra `/root/word_recovery`.
Read-only candidate: `/opt/meddoc-pro/.worktrees/v1-word-d19`, clean committed head `9e04ff7810144737138eeab2012e0f95170336b8`, compared with `7d3828f13eb772198ed8146f4f2f774f1ceebe0c`.

**NOTHING FOUND** in the requested omission, mismatch, old-warning and admission-order lenses. The unchanged Word engine retains the separate completed source-protection refutation.

## Exact source identity

| File in rebuild | SHA-256 |
|---|---|
| `core/jobs.py` | `ad1f9e4334b11cdc932605fbeb0f097267de810b51e4f61b099348d83d1095aa` |
| `core/v3_mapping.py` | `c64d3eb48df6175b692c4f0af6ebbcb85a2382eafdd645498e0ca0e994242698` |
| `core/views.py` | `b33a170ad224ad828fcc8874d4481235567f4ddd3b7c93fcff839a810a995511` |
| `documents/word_v3.py` | `190c470192e49005166e3d2b6b792772dd7284d616bdf2977854a19306de4e80` |

## Bounded independent controls

Fourteen controls completed with exit 0. The first five exercise the actual isolated document-inspection entrypoint using newly created synthetic forms, with no database or provider:

- Floating form with omitted warnings refuses.
- Floating form with an unrelated historical warning refuses.
- Ordinary nonfloating form with matching digest is permitted.
- An ordinary replacement file retaining the floating original's digest refuses.
- Missing original refuses.

Two controls prove a stored refusal warning only causes refusal and does not call inspection: its original floating source and a copied warning on an ordinary form. This intentional conservative behavior is not mistaken for proof of the source's layout.

Four stubbed response controls reject wrong/missing inspection contract and wrong/missing digest. Three simulated inspection failures (`DocumentError`, `ValueError`, `FileNotFoundError`) refuse with the fixed generic explanation and expose none of the synthetic private detail strings.

The probe does not fabricate a provider result or create any financial record. Existing author tests of billed mock positives, refused HTTP/direct enqueue, released old holds and voice delivery were inspected and reused, not counted as independently rerun financial workflows.

## Source path inspection

- `views.py:1005` checks the restriction before `usage_quote` at line 1006.
- `jobs.py:217` checks the selected version after the encounter row lock and before idempotency lookup, Job creation, cost computation and reservation.
- `jobs.py:626-627` checks old queued generation jobs before any generation call or receipt. It raises the existing `NoProviderRequest` class; the existing exception path classifies an unsent request, marks failed, and atomically releases the hold with the state update.
- Both job checks are restricted to generation. The transcription path remains separate; no new restriction is applied to independent reviewed voice transcription.
- Source inspection requests contract v3 explicitly and the trusted inspection service calculates the digest from the bytes read into its isolated workspace. It does not accept a source digest supplied by document content.

The declared scope is contract-v3 versions, whose contract is an immutable application-owned mapping attribute. No unsupported claim is made about arbitrary database-owner mutation or every historical non-v3 engine.

## Evidence and next action

`probe.py` and `probe.json` preserve every control and source hash. Synthetic originals remain in this directory's private `state/files/templates/`; no original source was overwritten. Reproduce with:

```
/opt/meddoc-pro/.worktrees/v1-release/rebuild/.venv/bin/python \
 /opt/meddoc-pro/.worktrees/v1-host-readiness/rebuild/.runtime/d19-admission-independent-20260927/probe.py
```

The harness explicitly imports the D19 candidate and configures an unreachable database port 1. No application source, real data, provider, payment, agreement, deployment or unseen corpus was changed. No broad suite ran and no process remains. The test's parser subprocesses completed; no new paid service was used.

This closes the scoped admission refutation. Root owns integration and its final combined verification. D19 remains an automatic compatibility failure because filled export is refused for the unqualified floating layout; this guard does not convert the retained clipping failure into a pass.
