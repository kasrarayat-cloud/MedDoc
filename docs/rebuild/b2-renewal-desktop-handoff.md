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

## Integrity

| file (repository path) | sha256 |
|---|---|
| `rebuild/ops/offsite_account_audit.py` (the collector) | `3dcb164ec4cc81668e2d38a23080177ea913fc6bd5870edc75602aaa5e3d1a9f` |
| `rebuild/ops/offsite_renewal_administration.py` (post-expiry reservation) | `7c4505504967b2192be831759315a701582c058b22395ab8fcbd8a1a323fc2b6` |
| `rebuild/ops/offsite_renewal.py` (ticket issue / import) | `18ea15fd6ec04715d33dff699f896aab1e7f12d0380a7ba73d1d99c48aaf1f61` |
| `docs/foundation/mutations/20260922-quillmd-renewal-administration-reservation.md` | `b0cf28878bbc080b5dc4702615a99b7d4d0680e34fc2772d8e7b9f5c2694e624` |
| `docs/foundation/mutations/20260920-quillmd-offsite-activation.md` | `55156bf6eccc00296221f72d14ecc673ca320fb067028ecd23da03606a8d08b3` |
| `docs/rebuild/offsite-renewal-operations-20260920.md` (runbook) | `9223eeb16797a08e13889231f8ded080f9a3e7a4f04a255aafe629d92d131f3b` |

The ticket issued in step 2 pins the collector's sha256 itself; a mismatch refuses on the desktop.

## Sequence — start only when the owner confirms step 0

0. **Owner confirms:** a designated desktop and user with a protected directory, Python 3, the
   collector file above, a vault that can pipe credential JSON to stdin, and the ability to create
   **and later revoke** a temporary **account-wide read-only** B2 key. The worker key is untouched.
1. **Reserve the key administration** (from `/opt/meddoc-pro`, clean on `main`). Choose a session
   end by which the key will be created AND revoked, at most 2 days ahead. The full 34 / 4,456,448
   reservation is charged to every UTC date through that end:
   ```
   bash scripts/run-ruled-mutation.sh \
     --declaration /opt/meddoc-pro/docs/foundation/mutations/20260922-quillmd-renewal-administration-reservation.md \
     -- /opt/meddoc-pro/rebuild/.venv/bin/python -B rebuild/ops/offsite_renewal_administration.py \
     --requests 34 --download-bytes 4456448 --label desktop-key-administration-<date> --session-end <UTC ISO time>
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
   `python offsite_account_audit.py --ticket ticket.json --output <new protected path>/account-audit.json --credential-stdin`
   with the credential JSON piped from the vault. Never put the key in an argument, chat, git or the VPS.
5. **Revoke the key** and confirm an authorization with it fails (HTTP 401) — before the session end in step 1.
6. Return **only `account-audit.json`**, original bytes, to a `claude`-owned 0600 file under a 0700 directory.
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

- Reuse `98b609fe…` or `673a83fb…`, or issue a ticket before step 0.
- Rush key creation to beat a clock: renewal remains possible after expiry, and only the offsite
  run waits.

## After import

A successful import renews COVERAGE and ADMITS the next scheduled run. It is not a backup: report
"offsite backup succeeded" only after the next scheduled 05:00Z run completes with verified
readback. No restore drill and no extra backup are needed for the renewal itself.
