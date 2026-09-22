# Declaration — install the publication sandbox grant, September 22, 2026

A release that carries the exclusion-lock relocation, amends two systemd unit files and creates
one 0700 directory. **No migration, no schema change, no public-asset content change, no provider
call, no backup, restore, readback or renewal, and no change to any credential, policy or
identity.**

## Why this exists

`52b28b36` shipped `ops/activation_exclusion.py` and placed its `flock` at
`.runtime/.activation-publication.lock`. Neither unit that takes that lock was granted write
access to the path, and both run `ProtectSystem=strict`.

⚠️ **MEASURED, NOT INFERRED.** From **2026-09-22T07:53:54Z** — seventy-four seconds after the
activation reported `complete` — every five-minute publisher tick raised
`OSError: [Errno 30] Read-only file system` at `activation_exclusion.py:98`. At the time of
writing the `core_servicehealth` row has not moved since `08:00:09.984136Z`.

⚠️ **THE PROOF THAT SAID OTHERWISE RAN IN THE WRONG PLACE, AND THIS DECLARATION CORRECTS IT.**
The 08:00:09Z publication was cited in the previous report as evidence that publication had
resumed. **That claim was wrong.** It was run by the operator OUTSIDE the unit sandbox, so it
never executed the failing path; it demonstrated that the *command* works, never that the
*service* does. Its row is the very row that then sat frozen for hours. This act therefore
requires its proof from the systemd-managed unit and from a subsequent scheduled tick, and
treats any hand-run command as insufficient by construction.

⚠️ **AND THE DESIGNED BACKSTOP IS DISABLED FOR EXACTLY THE CASE IT EXISTS TO HANDLE.**
`backup_alerts.check()` calls `recover_publication()` inside `except Exception: pass`, and that
call would raise the identical EROFS.

⚠️ **STATED PRECISELY, BECAUSE AN EARLIER DRAFT OF THIS DECLARATION OVERCLAIMED IT.** It did NOT
fire during this outage: `recover_publication()` returns at `pause_owed()` before it ever opens
the lock, and no pause is owed. What is broken is the path that pays a pause DEBT — the one case
the hook is for — so the failure would arrive on the day an activation dies mid-act, silently.
The release carries a recorder for that path, writing into the alerts unit's own grant; the
deferral ledger cannot be used, because in that failure it is the unwritable thing.

## Bounded change

| what | exactly |
|---|---|
| release marker | `52b28b369600549e0ad623fe49bdcd47c2cd44a1` → the target, replaced by the driver, never by hand |
| source | fast-forward only, to the exact reviewed target |
| unit files replaced | **two**, root-owned 0644, byte-identical to their reviewed sources: `quillmd-fresh-operations-publisher.service`, `quillmd-fresh-backup-alerts.service` |
| the delta in each | **one line**: `ReadWritePaths` gains `/opt/meddoc-pro/rebuild/.runtime/publication`. Nothing else in either file changes |
| directory created | **one**: `.runtime/publication`, mode 0700, operations identity |
| files relocated into it | the lock and `publication-deferrals.jsonl`, **byte-identical**, history preserved |
| legacy lock retired | `.runtime/.activation-publication.lock` removed only AFTER every participant runs new code, and recorded |
| services | doctor, admin and worker restarted onto the new release by the driver |
| public assets | recollected and reinstalled by the driver; **no static source changes in this range, so the installed inventory must come back identical** |

**MUST change, and it is the whole purpose:** publication resumes **under the unit**. After the
act, `core_servicehealth` key `backup` must carry a `computed_at` later than
`2026-09-22T08:00:09.956912+00:00`, produced by `quillmd-fresh-operations-publisher.service`
with `Result=success` and `ExecMainStatus=0`, and a **subsequent scheduled tick** must advance it
again within a bounded window.

⚠️ **AND THE PANEL'S BADGE TEXT IS PART OF THE CLAIM, NOT JUST ITS COLOUR.** The template read
`stale` whenever the row was stale — and a failed row IS stale, so a dead publisher would have
rendered the escalated colour under the word *stale*. The word is now `failed`. A severity a
reader cannot see is not a distinction.

⚠️ **THE ROW'S `healthy` FLAG IS DECLARED TO STAY FALSE.** It reports
`offsite_policy_renewal_due`, a true statement about the 19:32:21Z policy expiry and not a
symptom of this defect. An act that turned it green would be hiding something.

## MUST NOT change, each asserted before the act

| quantity | declared value |
|---|---|
| tables | 36, exactly the set below |
| applied migrations | unchanged; head stays `0018_servicehealth` |
| encounters | 29 |
| finalized encounters | 17 |
| patients | 4 |
| jobs | 29 |
| ledger entries | 47 |
| payments | 3 |
| usage rows | 29 |
| service-health ROWS | 1 — the row's content moves; the count does not |
| installed public assets | 37 entries, unchanged in name and digest |
| every other systemd unit, override and enablement link | identical |
| both `.timer` files and their `timers.target.wants` links | identical |
| `User=`, `Group=`, `ProtectSystem=`, `NoNewPrivileges=`, `UMask=` on both amended services | identical |
| documents, balances, audit history, MFA, synthetic-only, public maintenance | untouched |
| protected configuration and the `.env` secrets | never read, never written except the release marker |

⚠️ `core_auditevent` is expected to GROW and is named here rather than omitted, because a count
nobody declared cannot be judged either way.

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
docs/foundation/mutations/20260922-quillmd-publication-sandbox-grant.md
rebuild/core/admin_console.py
rebuild/core/tests/test_admin_console.py
rebuild/core/tests/test_configuration_status.py
rebuild/core/views.py
rebuild/deploy/quillmd-fresh-backup-alerts.service
rebuild/deploy/quillmd-fresh-operations-publisher.service
rebuild/ops/activation_exclusion.py
rebuild/ops/backup_alerts.py
rebuild/ops/test_activation_exclusion.py
rebuild/ops/test_backup_alerts.py
rebuild/templates/admin_services.html
```

## The lock-path transition is coordinated, not assumed away

⚠️ **THE HAZARD IS TWO LOCKS AND NO EXCLUSION.** The installed code locks
`.runtime/.activation-publication.lock`; the code being installed locks
`.runtime/publication/.activation-publication.lock`. A participant on each side would take a
different lock and exclude nothing — and silently, because every check still passes. The module's
own `bind_runtime` docstring names this exact failure.

Four participants are accounted for:

| participant | how it is coordinated |
|---|---|
| the publisher timer | **stopped** for the act and restored in a `finally`; a stopped timer cannot tick whichever lock path its code uses |
| a publication already in flight | **drained** by waiting for the process to exit, before any snapshot |
| `backup_alerts` recovery | its pause marker is written at the NEW path, so installed OLD code reads nothing and is a no-op; after the advance it reads the marker, finds exclusion held, and refuses — and if it cannot open the lock at all it now RECORDS that |
| this activation | holds **BOTH** lock paths for the whole act, so neither an old-code nor a new-code participant can proceed |

**Interruption recovery is covered at every stage.** Before the units are amended the sandboxed
recovery path cannot open the new lock, so the bootstrap watchdog — spawned from the target
source, unconfined, before the debt is incurred — is what pays a pause debt in that window. It is
started first and reaped last.

## Rollback

Stop on failure; retain current data, schema, configuration and prior source. The driver retains
the prior source archive, the prior environment and the prior static inventory. The prior unit
bytes are retained in this act's evidence before either file is replaced. A failed act leaves the
publisher no worse than it is now — already not publishing — and the timer is restored regardless.

**No provider call. No B2 call. No restore drill. No new capture.** The qualified recovery proof
`f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f` and the retained capture
`20260922T043002Z-7d766ca1` are reused unchanged; this release needs neither.
