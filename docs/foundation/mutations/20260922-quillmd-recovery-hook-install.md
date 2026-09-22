# Declaration — install the recovery-hook import repair, September 22, 2026

A code-only release. **No migration, no schema change, no unit change, no public-asset content
change, no provider call, no backup, restore, readback or renewal, and no change to any
credential, policy, mode or identity.**

## Why this exists

The 2026-09-22 publication install shipped a recorder so that `recover_publication()` could no
longer fail in silence. **It fired on its first two ticks in production:**

```
{"event":"publication_recovery_failed","error_class":"ModuleNotFoundError",
 "detail":"No module named 'ops'"}        16:39:55Z and 16:44:55Z
```

⚠️ **SO THE MECHANISM EVERYONE ASCRIBED TO THAT HOOK WAS WRONG, INCLUDING THE DECLARATION FOR
THE RELEASE THAT SHIPPED THE RECORDER.** The hook was not failing on EROFS. It was never
importing at all.

`quillmd-fresh-backup-alerts.service` runs
`python -B /opt/meddoc-pro/rebuild/ops/backup_alerts.py check`. Running a FILE puts its own
directory — `rebuild/ops` — on `sys.path`, not `rebuild`. So `from ops import
activation_exclusion` raises `ModuleNotFoundError` on every tick, and in `52b28b36` that landed
inside a bare `except Exception: pass`. **The independent recovery path has been inert since the
moment it shipped, and said nothing about it.**

Reproduced, not inferred:

```
sys.path[0] = rebuild/ops
from ops import activation_exclusion  -> ModuleNotFoundError: No module named 'ops'
import activation_exclusion           -> OK
```

The repair is the file's own convention: line 22 already imports `scheduled_backup` with
`try: from . import … except ImportError: import …`. Every sibling uses that form; this one line
did not.

## Bounded change

| what | exactly |
|---|---|
| release marker | `411d57bd338e85daa9547a3f2c8689412179e111` → the target, replaced by the driver, never by hand |
| source | fast-forward only, to the exact reviewed target |
| files changed | **two**, both under `rebuild/ops/`: the import form and its regression tests |
| systemd units | **none** — no unit file, timer, override or enablement link is touched |
| public assets | recollected by the driver; no static source changes, so the inventory must come back identical |
| services | doctor, admin and worker restarted onto the new release by the driver |

**MUST change:** after the act, `backup_alerts.check()` must reach `recover_publication()` under
its own unit — evidenced by the recovery-failure ledger recording **no new
`ModuleNotFoundError`** on ticks after the release, where it recorded one on every tick before.

⚠️ **THE ROW'S `healthy` FLAG STAYS FALSE.** It reports `offsite_policy_renewal_due`, which is
true and unrelated to this repair.

## MUST NOT change, each asserted before the act

| quantity | declared value |
|---|---|
| tables | 36, exactly the set below |
| applied migrations | unchanged; head stays `0018_servicehealth` |
| encounters | 29 (17 finalized) |
| patients | 4 |
| jobs | 29 |
| ledger entries | 47 |
| payments | 3 |
| usage rows | 29 |
| service-health ROWS | 1 — the row's content moves; the count does not |
| installed public assets | 37 entries, unchanged in name and digest |
| every systemd unit, override and enablement link | identical — this release installs none |
| documents, balances, audit history, MFA, synthetic-only, public maintenance | untouched |

⚠️ `core_auditevent` is expected to GROW and is named rather than omitted.

<!-- declared-schema -->
```
auth_group
auth_group_permissions
auth_permission
core_auditevent
core_code
core_codeset
core_codesuggestion
core_costreconciliation
core_department
core_encounter
core_invitation
core_job
core_ledgerentry
core_loginattempt
core_membership
core_organization
core_patient
core_payment
core_platformcost
core_providerreceipt
core_refund
core_reservation
core_servicehealth
core_template
core_templateversion
core_usage
core_user
core_user_groups
core_user_user_permissions
core_verification
core_wallet
core_webhookevent
django_content_type
django_migrations
django_session
otp_totp_totpdevice
```

<!-- declared-source-scope -->
```
rebuild/ops/backup_alerts.py
rebuild/ops/test_backup_alerts.py
```

## Rollback

Stop on failure; retain current data, schema, configuration and prior source. The driver retains
the prior source archive, the prior environment and the prior static inventory. A failed act
leaves the recovery hook exactly as inert as it already is, and the publisher — which is
unaffected by this change — still publishing.

**No provider call. No B2 call. No restore drill. No new capture.** The retained capture
`20260922T043002Z-7d766ca1` and the independent-key restore proof
`f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f` are reused unchanged.
