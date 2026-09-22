# B2 offsite-policy renewal — desktop handoff (nonsecret)

Delivered through the owner's private repository — the same authorized route that already carries
the collector and the runbook. **No credential, key, token or secret is in this file.** Verify
every file below by sha256 on the desktop before running anything.

## State when prepared (2026-09-22 ~21:15Z, installed release `d9660e34f9d3217369212ffc7d0d8302d4ad568c`)

| fact | value |
|---|---|
| offsite policy | **expired** 2026-09-22T19:32:21.377935Z; the published backup status reports `offsite_policy_expired` (failure) |
| expired policy at its original time | validates — sha256 `8b325a43102fac18…`; limits 500 requests / 100,000,000 bytes per UTC day |
| allocation contract | active; all 7 pinned control sources match the files on disk |
| renewal state | `installed` on ticket `98b609fe…` (consumed 2026-09-21, **not reusable**); `673a83fb…` expired unused |
| replacement ticket / renewal in flight | **none** |
| budget 2026-09-22 | 285 / 500 requests, 81,169,896 / 100,000,000 bytes; no future days reserved |
| **next offsite run** | **2026-09-23T05:00Z NOT admitted**; stays blocked until an import succeeds. The local 04:30Z capture continues. |

## After the 2026-09-22 renewal (appended 2026-09-22)

The table above is the state when this handoff was prepared, kept as written.

| fact | value |
|---|---|
| renewal | ticket `ed9ec56d5c0141cfc6f04917430b6d68` imported 2026-09-22T22:22:35Z; **consumed, not reusable** |
| offsite policy | sha256 `742f57d226a44fcb…`, observed 2026-09-22T22:05:53.615210Z, **valid until 2026-09-23T22:05:53.615210Z** (scan time + 24 h) |
| next offsite runs | 2026-09-23T05:00Z admitted by that policy; 2026-09-24T05:00Z needs another renewal |

For the next renewal, read live state first, then follow the sequence below. Two instructions were
corrected after this renewal: step 1's reservation door depends on whether the policy has expired,
and step 4's `--output` names a new directory, not the JSON file.

## Integrity

| file (repository path) | sha256 |
|---|---|
| `rebuild/ops/offsite_account_audit.py` (the collector) | `3dcb164ec4cc81668e2d38a23080177ea913fc6bd5870edc75602aaa5e3d1a9f` |
| `rebuild/ops/offsite_renewal_administration.py` (post-expiry reservation) | `7c4505504967b2192be831759315a701582c058b22395ab8fcbd8a1a323fc2b6` |
| `rebuild/ops/offsite_renewal.py` (ticket issue / import) | `18ea15fd6ec04715d33dff699f896aab1e7f12d0380a7ba73d1d99c48aaf1f61` |
| `docs/foundation/mutations/20260922-quillmd-renewal-administration-reservation.md` | `b0cf28878bbc080b5dc4702615a99b7d4d0680e34fc2772d8e7b9f5c2694e624` |
| `docs/foundation/mutations/20260920-quillmd-offsite-activation.md` | `55156bf6eccc00296221f72d14ecc673ca320fb067028ecd23da03606a8d08b3` |
| `docs/rebuild/offsite-renewal-operations-20260920.md` (runbook) | `15d0acbbd9433552fcfb2857b51c5c5f92aabd74e8a5e7b52faf0349da58aa70` (was `9223eeb1…` before the 2026-09-22 `--output` correction) |

The ticket issued in step 2 pins the collector's sha256 itself; a mismatch refuses on the desktop
and spends the ticket, so verify the collector's sha256 above before running it.

## Sequence — start only when the owner confirms step 0

0. **Owner confirms:** a designated desktop and user with a protected directory, Python 3, the
   collector file above, a vault that can pipe credential JSON to stdin, and the ability to create
   **and later revoke** a temporary **account-wide read-only** B2 key. The worker key is untouched.
1. **Reserve the key administration** (from `/opt/meddoc-pro`, clean on `main`). The door depends on
   whether the policy has expired. *(Split 2026-09-22: this step described only the post-expiry door.)*
   - **After expiry:** `offsite_renewal_administration.py`, which refuses `state_invalid` while the
     policy is still valid (`offsite_renewal_administration.py:86-92`). Choose a session end by which
     the key will be created AND revoked, at most 2 days ahead. The full 34 / 4,456,448 reservation is
     charged to every UTC date through that end:
     ```
     bash scripts/run-ruled-mutation.sh \
       --declaration /opt/meddoc-pro/docs/foundation/mutations/20260922-quillmd-renewal-administration-reservation.md \
       -- /opt/meddoc-pro/rebuild/.venv/bin/python -B rebuild/ops/offsite_renewal_administration.py \
       --requests 34 --download-bytes 4456448 --label desktop-key-administration-<date> --session-end <UTC ISO time>
     ```
   - **Before expiry:** `offsite_operator.py reserve-external`, which refuses `policy_expired` once the
     policy lapses. Run it through `scripts/run-ruled-mutation.sh` under a NEW committed declaration
     naming the quantities, shaped like `docs/foundation/mutations/20260921-quillmd-desktop-key-administration.md`.
     It has **no session end**: it charges the UTC day it runs (and the next day only when its
     bounded deadline crosses midnight, `automatic_offsite.py:305-309`). Key creation **and** revocation
     must both fall on the charged day, or reserve the revocation day before revoking.
     ```
     bash scripts/run-ruled-mutation.sh \
       --declaration /opt/meddoc-pro/docs/foundation/mutations/<new committed declaration>.md \
       -- /opt/meddoc-pro/rebuild/.venv/bin/python -B rebuild/ops/offsite_operator.py reserve-external \
       --requests <bound> --download-bytes <bound> --reference <unique nonsecret reference>
     ```
2. **Issue the ticket** (charges 20 requests / 8 MiB to its start day):
   ```
   bash scripts/run-ruled-mutation.sh \
     --declaration docs/foundation/mutations/20260920-quillmd-offsite-activation.md \
     -- rebuild/.venv/bin/python -B rebuild/ops/offsite_renewal.py issue-ticket \
     --expected-commit "$(git -C /opt/meddoc-pro rev-parse HEAD)" --not-before <UTC start> --valid-until <UTC end>
   ```
3. Deliver only the new **792-byte `ticket.json`**.
4. **Desktop:** create the temporary read-only key; within the ticket window run
   `python offsite_account_audit.py --ticket ticket.json --output <existing protected folder>/<NEW folder name> --credential-stdin`
   with the credential JSON piped from the vault. Never put the key in an argument, chat, git or the VPS.
   `--output` names a directory that must **not exist yet**, inside an existing protected parent. The
   collector creates it and writes `intent.json` and `account-audit.json` inside it. Give the parent
   as a plain absolute path: a symlink, junction or `..` is refused. It checks the parent's mode bits
   on POSIX only; on Windows nothing verifies the ACL, so choose the restricted folder yourself. These
   checks run before the ticket is spent. The ticket is spent **before the credential is read**, so
   every later refusal spends it: a wrong or empty credential pipe, a collector copy whose sha256
   differs from the ticket, an authentication, scope or timeout refusal, or a failure writing into the
   new directory (keep the path short). A refusal during collection prints a JSON line with
   `"status": "failed"` and a `reason_code`, exits 2 and writes a failed `account-audit.json`; the
   others print one generic *Account audit refused* line and exit 1. Either way the ticket was spent
   exactly when `<home>/.quillmd-account-audit-spend/<ticket id>.used.json` exists, and then a retry
   needs a new ticket. Use a new `--output` name for any retry.
   *Corrected 2026-09-22: this step read `--output <new protected path>/account-audit.json`. That
   refuses when the path does not exist yet, and when it does exist and is protected, creates a
   directory named `account-audit.json` holding the real `account-audit.json` and `intent.json`.*
5. **Revoke the key** and confirm an authorization with it fails (HTTP 401), inside what step 1
   reserved: before its session end (after-expiry door) or on its charged UTC day (before-expiry door).
6. Return **only `account-audit.json`** from inside that output directory, and only when the collector
   printed `"status": "verified_over_observed_interval"` and exited 0. Original bytes, to a
   `claude`-owned 0600 file under a 0700 directory. Keep a failed result on the desktop and ask for a
   new ticket.
7. **Import:**
   ```
   bash scripts/run-ruled-mutation.sh \
     --declaration docs/foundation/mutations/20260920-quillmd-offsite-activation.md \
     -- rebuild/.venv/bin/python -B rebuild/ops/offsite_renewal.py import-result \
     --expected-commit "$(git -C /opt/meddoc-pro rev-parse HEAD)" --ticket-id <issued id> --result <protected returned json>
   ```
   The new policy is valid until **scan time + 24 h**, and the next scheduled 05:00Z run is admitted.
   Do not run an early capture, offsite run, restore drill or alert email to "prove" it.

## Do not

- Reuse `98b609fe…`, `673a83fb…` or `ed9ec56d…`, or issue a ticket before step 0.
- Rush key creation to beat a clock: renewal remains possible after expiry, and only the offsite
  run waits.

## After import

A successful import renews COVERAGE and ADMITS the next scheduled run. It is not a backup: report
"offsite backup succeeded" only after the next scheduled 05:00Z run completes with verified
readback. No restore drill and no extra backup are needed for the renewal itself.
