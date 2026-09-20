# Private operational readiness — 2026-09-20

This records completed recovery and the demonstrated repair scope. Exact final
CI, installed revisions and activation results are recorded separately in
`rebuild/.runtime/private-readiness-20260920/FINAL-REPORT.md` and the append-only
`rebuild/.runtime/CHECKPOINT-LATEST.md`; source preparation alone is not activation.
Public maintenance and synthetic-only operation remain in force.

## Recovery evidence

The three direct desktop uploads completed at 19:10:32 UTC. Server receipt verified
regular single-link files, claude ownership, 0600 under 0700, and 45/3,859/16,135 bytes and
both supplied nonsecret SHA-256 values. All 12 ZIP member paths/types/sizes passed
before extraction. The initial refused desktop read-preflight is preserved;
desktop remote readback is not claimed. The exact temporary grant was removed,
with unrelated keys/shared SSH policy preserved and no active claude SSH session.

The original Windows evidence confirms existing Credential Manager import at
18:47:24 UTC, separate-process vault-only retrieval at 18:47:30 and third retrieval
for the return at 18:47:56. No archive/SSH/original-secret fallback was used.
Custody is outside the VPS but tied to that Windows computer/account. It does
not establish offline, Windows-loss, LUKS or whole-host disaster recovery.

At 19:20:10–19:20:33 UTC the existing returned-key verifier and bounded composition
of the installed Native transport/budget/restore primitives completed one actual
download-only isolated restore. Selected run: `20260920T095332Z-a9da0017`;
manifest cipher SHA-256:
`910153b7d671bbd147ab5a840e5a9e6c7a3f4d8fa3913046c852cfc67c062ace`.
All 44 encrypted objects/14,422,252 bytes authenticated. Manifest-derived 35 tables,
225,615 rows and 42 files matched; four invariants were zero, nine triggers present.
The returned key was the sole decryption source; the process guard positively
refused a live-key read. The restore used downloaded ciphertext, not original
plaintext. Its networkless container used nonswapping tmpfs, no ports/workers or
provider credentials, and was independently confirmed absent after cleanup.

Actual transport accounting: 46 new Native requests and 18,551,020 reserved response
bytes. Shared ledger: 296 requests/68,551,020 bytes, including a conservative external
reservation of 250 requests/50 MB. Reservations are not measured provider usage;
unquantified desktop navigation is not silently called zero. No objects were
uploaded and no additional restore was performed for independent review.

Evidence:
`recovery-custody-handoff-20260920/return-evidence/independent-key-restore/result.json`,
its nested original verification, `independent-result-review.json` and receipt/
cleanup records. The original ZIP and operating evidence remain intact under
`return-evidence/original-return-files/`. The server's returned key was shredded,
unlinked and checked absent; no storage-level secure-erasure guarantee is implied.
The desktop temporary return key can be removed. Keep its vault entries and all
working keys. The existing VPS B2 credential supplied remote access; independent
B2 credential use in this restore is not claimed.

## Offsite admission remains explicit

The uploaded 18:40:30 account observations show one bucket / 44 current files and
rounded daily displays 4 MB storage / 14 MB download, 10 GB/$0.00 storage and 1 GB/$0.00 download
caps, Class B 44/2500 and C 36/2500. The 18:43:45 scoped inventory completely enumerated
44 versions/44 names/14,422,252 bytes with no start/hide markers. Neither observation
enumerates hidden versions or unfinished parts outside the restricted prefix.

The actual restored credential was reauthorized with exactly listFiles/readFiles/
writeFiles for one bucket and prefix. It cannot establish the absent account-wide
population. The visible current-file count does not bound hidden versions or
unfinished parts. A daily storage counter or nominal cap is not an instantaneous
account-wide stored-byte upper bound. No supported numerical bound follows from
the supplied evidence, so no such bound or recurring allocation is manufactured.

The existing 17-field policy remains uninstalled and offsite remains disabled.
Local execution lock and durable budgets serialize this restore and scheduled
Native calls; retries retain reservations. They do not observe external/manual
consumers that bypass that transport. Further account-level observation and an
enforceable allocation/accounting arrangement for those consumers are the precise
remaining inputs. Routine engineering may select a shorter supported validity
window; a one-time observation cannot guarantee 30 days of headroom.

Once those inputs exist, the established installer must prove eligibility and a
new controlled authenticated upload/readback before enabling the daily timer.
Keep all old versions; the key cannot delete. Capacity/expiry refuses and alerts,
never silently prunes or increases a cap. A controlled service run and a future
daily firing remain separate evidence.

## Demonstrated repair scope

- Suspending and re-enabling an account could revive untouched old cookies and
  unused recovery links. Persistent generation revocation closes that gap while
  preserving active version 0 sessions. Existing suspended users are initialized
  separately; the real 0015→0016 migration edge was independently reproduced and
  repaired before activation.
- Pending invoice adjustments did not resume after unused paid holds, paid
  credit-backs or platform-failure reversals freed funds. Payer-scoped after-commit
  continuation now applies them once. Example: a waiting $1.50 adjustment resumes
  when a later $2 hold settles at $0.30, leaving $0.70. No existing live balance or
  receipt is rewritten by deployment.
- A restore could return success after cleanup failed and retained its temporary
  container. Overall success must now include cleanup, while preserving data
  verification and the primary failure record separately.
- A read-only monitoring status could retain an old healthy local result after
  the backup became stale or missing. Current local state, timer state, policy
  freshness and labelled budget reservations are checked and exposed through the
  existing protected operator command. No dashboard redesign or application
  access to backup secrets is required.

Focused synthetic evidence lives in `private-readiness-20260920/{security,billing,monitoring}/`.
Original failures, migration refutation and corrected results are retained.
Authentic invoice reconciliation remains pending: `provider-evidence/` exists
with 0700 but is empty. Existing reconciliation workflows and Stripe sandbox
verification remain complete within their previously recorded scope.

## Remaining external boundaries

Outside-host monitoring has no authorized configured endpoint. Optional bounded
integration support and its private handoff can be completed, but actual pings,
external missed-heartbeat detection and inbox receipt require that endpoint and
provider observation. Do not send another test email to replace the existing
outstanding human inbox confirmation.

The consolidated final report also retains authentic provider billing evidence,
independent security reviewer engagement, legitimate CPT rights, patient-data
agreements/regions/retention and the deferred natural human dictation/new SOAP
native-Word checks. Prior WM IOV Word acceptance is complete. Internal tests do
not replace independent penetration testing or approve public release.
