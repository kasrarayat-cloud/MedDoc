# V1 operations continuation — 2026-10-03

This continues integration `58e11826807fe9d5eb6158eaf96682e833e27277` in an isolated operations branch. It does not
change the installed `dedac1625032e32c7a149e6771be22e26c307eb1`, public maintenance, synthetic-only policy,
databases, services, provider accounts or unrelated tenants. The unknown previously platform-blocked action remains
stopped. Preflight GO is `docs/preflight-reports/preflight-20261003T215613Z.md` in the shared repository.

## Concrete engineering change

The existing integrations pattern now includes persisted ICD-10-CM release metadata. Doctor and administrator
surfaces show the current version and exact effective dates, count loaded releases, warn when today's date has no
coverage, and report overlapping/unreadable metadata honestly. It reads only CodeSet metadata, with no patient,
encounter, code description or evidence query. Today's status does not choose the version for a visit: the existing
suggestion and acceptance routes still share `coding.applicable_releases(encounter)` and the encounter service date.
The panel explicitly says it does not verify code-file integrity. CPT remains locked without recorded product rights.

The README's September30 expiry statement was stale. The retained September18 installed/import proof records
FY2026-October (2025-10-01–2026-03-31, 74,719 codes), FY2026-April (2026-04-01–2026-09-30, 74,719 codes), and FY2027
(2026-10-01–2027-09-30, 74,879 codes), preserving prior data. No duplicate import or acquisition was performed.
Current installed CodeSet contents were not queried through an unauthorized secret/DB route; the fresh metadata
display can establish that observation after a qualified candidate is served. The official effective period remains
[CMS's FY2027 ICD-10-CM publication](https://www.cms.gov/medicare/coding-billing/icd-10-codes).

## Current operational observations

Read-only observations at 21:59–22:07 UTC used the existing local status readers, fixed nonsecret receipt fields,
systemd status, encrypted-artifact checks and hashes. No backup/restore drill, provider request, email, heartbeat,
ticket issue/import or cleanup was run.

| Control | Observed result | Scope and limitation |
|---|---|---|
| Local capture | October3 `20261003T043001Z-644f9245`, completed04:31:14 UTC; encrypted artifacts present; within30-hour stale bound | Existing capture verified present, not a new restore proof |
| Local schedule | Backup timer nextOctober4 04:30 UTC; offsite next05:00 UTC; both listed | A timer listing does not establish offsite admission |
| B2 policy | SHA256 `742f57d226a44fcb2d0b764e9e9febec00458e3dbee92bd9eafa9bb3d96df7b2`; expiredSeptember23 22:05:53.615210 UTC | More local disk does not renew account evidence |
| Latest offsite attempt | October3 05:00 UTC refused `policy_expired`, zero provider calls | The oneshot service reports exit0/success for this recorded refusal; it is not backup success |
| Last complete remote set/readback | September23 05:00:09.577606 UTC, `20260923T043000Z-2031049f`, 66objects, 18,516,232 cipher bytes | Historical retained recovery set; no current offsite coverage |
| Renewal | September22 ticket `ed9ec56d5c0141cfc6f04917430b6d68` installed/consumed; no fresh waiting ticket | Do not reuse or extend it |
| Local restore proof reused | September27 `aa337127b29071d1`:36tables/226,187rows/64files, all hashes matched; zero invariant violations; no retained container | BindsSeptember27 local capture, not the newly integrated schema or whole-host recovery |
| Independent-key offsite restore retained | September20,35tables/225,615rows/42files, independently retrieved key | Historical proof; no new provider/download attempt |
| Alert incident | September23 incident `28b35bbe9d92aaed5927912d9f824bba`, last announced `offsite_policy_renewal_due`; currentcondition `offsite_policy_expired` | One prior provider-accepted notice; no duplicate message sent |
| Alert delivery | Provider message `01a0cca7-2cee-755e-9e15-c37f84ff45bb`; delivery and human inbox flags false | Provider acceptance is not delivery/inbox acceptance |
| Outside-host monitoring | No external-monitor configuration or heartbeat receipt present | No provisioning or message authorized/performed here |
| Monitor/publisher units | Both failed with exit1 while currentcondition reports policy expiry | Failure remains visible; no status reset to make it green |

An initial attempt to use the candidate's newer alert helper names against installed code failed with AttributeError.
That instrument failure is preserved. A distinct read-only candidate reader interpreted the compatible installed
state successfully; it made no configuration/environment read or transport request. It does not mean the newer
alert code is installed. Before any private installation, account for the candidate's automatic escalation/reminder
behavior and applicable existing alert authority; retain the previous accepted notice and avoid a duplicate test.

## Exact B2 owner handoff

The existing [desktop handoff](../b2-renewal-desktop-handoff.md) remains the supported route. Its three tool hashes
were reread on the installed shared source and match the handoff exactly:

| Tool | SHA256 |
|---|---|
| `offsite_account_audit.py` | `3dcb164ec4cc81668e2d38a23080177ea913fc6bd5870edc75602aaa5e3d1a9f` |
| `offsite_renewal_administration.py` | `7c4505504967b2192be831759315a701582c058b22395ab8fcbd8a1a323fc2b6` |
| `offsite_renewal.py` | `18ea15fd6ec04715d33dff699f896aab1e7f12d0380a7ba73d1d99c48aaf1f61` |

Owner input is narrow: identify the protected desktop/user/vault and confirm the ability to create **and revoke**
a temporary account-wide read-only B2 key. Then the operator rechecks installed source/policy/active work, reserves
the existing post-expiry key-administration allowance (34requests/4,456,448download bytes per covered UTC day),
sets a real session end at most2days ahead, and issues a **new** bounded audit ticket through the committed ruled
mutation gate. The ticket separately reserves20requests/8MiB. These B2 allowances are independent of model-testing
authority and are not reset or enlarged here.

The desktop checks the pinned collector, uses a new protected output directory and credential stdin, performs the
bounded account observation once, revokes the temporary key and confirms authorization then fails401. Return only
the original successful `account-audit.json`; import against the new ticket through the same gate. Validity becomes
observation time+24hours. Wait for the next scheduled05:00 run/readback before saying offsite backup succeeded.
No early extra backup/restore or alert is needed for renewal. Failed/expired tickets stay consumed; the worker key
does not gain account-wide rights.

## Doctor/admin and release checks

Existing persisted account, invitation/recovery, department navigation, form/mapping/review/history, billing and
admin workflows were inspected before changing anything. The retained124 served authorization controls remain
bound to immutable demo`789c0372127d89b1750a2f790c561e68c19f1654`, not the installed release. Middleware, security,
admin views, admin computation and URL files are byte-identical to that revision at the recovered integration base;
views/models/context differ. Reuse the original proof for unchanged enforcement, and rerun affected served controls
on the final demonstration before making an exact-candidate claim. Four original failed served runs remain retained.

Focused fixture-only checks and their actual process exit are appended after completion below. They are component
verification and do not substitute for exact-release CI, served workflows, native Word, human microphone or independent
security review. No billing policy, promotional credit, historical balance, payer allocation, provider usage rating,
live payment or receipt is changed by this slice.

Retention now has holds, signed journals, narrowly bounded empty-draft disposition/redaction and quarantined restore
admission; the [updated inventory](retention-deletion-readiness.md) distinguishes these from unsupported general
purge. Explicit transcription/maximum-charge confirmation exists; it is not a counsel-approved patient recording/
retention/consent policy. No disposal is enabled and no duration/legal authority is invented.

The remaining owner-side operations inputs are: covered production/backup/provider accounts and agreements naming
the actual intended Sonnet5.5 model/regions/retention; approved retention/consent and downstream-copy schedule;
independent custody/recovery access; B2 renewal if maintaining this synthetic schedule; existing alert delivery
confirmation and separately authorized outside-host monitor/recipient; authentic provider billing evidence; authorized
test-environment payment acceptance; independent security review; native Word and human microphone acceptance.
Live Stripe, public cutover and real-patient processing remain outside this continuation. The old$40 campaign does
not constrain new eligible synthetic model/transcription testing; `quillmd-v1-private-api-testing-standing-20260930`
is unchanged, and this operations slice makes zero new API attempts.

## Activation and rollback preparation

Integrate this small source change with the coherent candidate; cite required CI on that exact commit. Keep the
doctor/admin/worker source identity, model/profile, immutable mappings/originals/exports and migration preservation
baseline bound to the private installation declaration. The existing private install procedure owns migration,
service stop/start and data-preserving rollback; do not deploy from this worktree or change relative shared mounts.
This slice needs no database migration or import. Rolling its source back preserves all CodeSet/history/billing data.
Keep current public maintenance and synthetic-only settings, CPT locked, disposal disabled absent its own authority,
and all original failures/unknown provider outcomes intact. New install failures must be preserved and reconciled
before retries. Offsite/alert status remains red until its actual external evidence is renewed/confirmed.

Protected raw evidence is under
`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/`.
The source/restore manifest rechecks the originalSep27 proof SHA256
`5e900543d002fcb8a91580ce6aeab02a20a1bcfed115d1a0a301455dccec2ec6`; no expensive drill was repeated.

## Completed focused verification

The isolated fixture-only PostgreSQL run finished with actual process **exit0**: **172tests PASS in71.305seconds**,
no skips, under a900-second outer deadline. Its test database was destroyed by the normal Django runner. The
eight new persisted metadata controls exercise the FY2027 positive and both inclusive boundaries, expired/future/
CPT-only gaps, overlapping and unreadable metadata, integration-row parity, and an actual MFA administrator
Services request without clinical membership. The latter displays the persisted version/dates and excludes a
stored clinical sentinel. The164existing affected controls cover20invite tests,11account recovery,6doctor ledger
status tests,87admin console tests,6published production operations status,12retention-readiness and22coding
service-date controls. Their declared method counts reconcile exactly with the runner's172.

No test or claim depends on a login redirect/screenshot alone. Existing admin tests include authenticated persisted
positive controls, denied access/CSRF and unchanged unauthorized writes, financial sums/detail and useful filters.
Current coverage still does not certify the future external target or current installed CodeSet contents.
The [evidence manifest](storage-resume-operations-20261003/manifest.json) binds raw focused output, result/source
hashes and the read-only operations observations, including the first alert instrument failure. `git diff --check`
passed. No new provider operation, subscription, live payment, service mutation or cleanup occurred.
