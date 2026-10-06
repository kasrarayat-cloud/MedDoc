# Department billing and application surface repair — 2026-10-02

Base: `d49ece788c058c9e733e895910a81c8aad94c6a3`; writer branch `fix/v1-sol-security-20261002`, isolated worktree.
Synthetic fixture tests only. No provider requests, payment requests, production environment reads, installed changes,
credential copies, or financial mutations outside test databases.

## Demonstrated authorization failure and repair

An active owner membership in one department formerly granted every organization-paid job in the shared organization,
including another department's requester, request identifier/status, hold, financial detail, global wallet balance and
ledger. Prior `HeldListScope` deliberately expected this interpretation. The owner's October 2 instruction supersedes
that expectation; changing email display alone would leave the actual access and aggregates open.

The server now grants own requested financial history (including after clinical membership revocation), and other users'
organization-paid requests only in departments the viewer actively owns. Encounter and mapping jobs use their actual
foreign-key department and that department's exact organization payer. Usage/search/pagination/aggregates and job ledger
entries use this same job set. Global organization wallet balances and before/after balances stay restricted because they
include other departments' funds. Personal balances/payment history remain. Job-specific financial projections continue
to omit notes, answers, patient identity, recordings and original/provider-result files. Every authorized held row opens
its corresponding financial detail; mapping and complete-form grouping retain their earlier controls.

No stored wallet, reservation, ledger, usage, receipt or job changes in this repair. Tests compare all money rows before
and after read requests. Separate active owner membership in the second department is an authorized positive; inactive
owner, clinician/manager/employee role, wrong department and wrong organization are negative controls.

## Host and administration surface

The integrated candidate already rejects console paths on the doctor process using PATH_INFO and a URLconf without
console routes. Its prior tests include SCRIPT_NAME, missing slash and actual callback spies. One remaining process/host
boundary accepted the public doctor Host on the admin loopback listener. Both public hostnames are accepted by Django,
so ALLOWED_HOSTS alone did not decide which process could serve one.

Requests naming the opposite public host now receive 404 before any console/doctor view, MFA or login action; case,
port and DNS trailing dot variants are covered. An empty resolver prevents CommonMiddleware changing this refusal into
a slash redirect. Correct administration host and localhost/loopback tunnel continue to reach the console for an MFA
administrator. Actual candidate serving still requires final demo rebuild and served retest by the lead.

The **old served demonstration**, observed without following redirects: doctor9140 `/console/` returns302 to login;
admin9141 `/login/` returns200 with either public host. These are retained old-demo facts, not a claim about the repaired
source. A first probe followed redirects and was discarded as an instrument error before this evidence was saved.

## Preserved validation

- First baseline:10tests/1.004s,28host-negative failures plus7mapping-fixture errors. The mapping fixture omitted required
  tenant/source binding and was corrected; its original output remains retained.
- Correct financial baseline:7tests/1.624s,6failures. The clinical API/export and admin-role guard positives/negatives were
  already protected. The financial leakage and new authorized department history expectations failed.
- First repair:11tests/5.469s,4failures, all an admin wrong-host `/console` slash redirect. The empty resolver closes them.
- Final focused run:11tests/5.955s,OK.
- Affected run:110tests/106.728s,OK. Includes full console surface, doctor financial wording/grouping/ledger, isolation
  matrix, security, recovery, invitation-account races, admin session revocation, console authorization and usage CSV.
- `git diff --check`:clean. The source was unchanged throughout the affected run.

Raw logs and hashes: `security-continuation-20261002/`. The QA runner loaded the rotated synthetic PostgreSQL password
inside its child process; no credential was in argv or logs. No paid API call or native Word claim follows.

## Remaining limits

The current V1 register's hosting/accounts/legal/native Word/independent security/human microphone gates remain. Existing
retention policy remains unset; code neither invents a schedule nor deletes historical financial rows. Integration
coverage for the newly added transcript-review evidence is a separate affected change. Final served candidate
verification and exact integrated CI remain the lead's closeout gates.

## Recording and redaction race R6R-1

The actual upload-to-over-limit route formerly wrote a recording, rolled back the nested admission on an over-limit
exception, and recorded its only durable ownership reference afterward. Redaction could journal its file manifest in
that gap and leave unreferenced recording bytes. The new PostgreSQL two-connection regression reproduces this before
the repair: redaction completed while the over-limit audit was paused, before that reference was committed.

Voice admission now locks the exact available encounter before storing bytes, rechecks membership/finalization, and
holds that row until either a job or the over-limit quote commits. The outer transaction survives the nested admission
rollback. Redaction/disposition take the same row first. A failed outer commit is caught after rollback, and the
unowned recording is removed through the existing preservation-aware cleanup. No pricing, customer settlement,
provider usage, retention schedule or legal authority changes.

Both redaction race orders are exercised: upload-first makes redaction wait and include/sweep the quoted recording;
redaction-first admits no recording, quote, job or hold. A commit failure admits nothing and removes unowned bytes.
Empty-draft disposition is also exercised in both orders: disposition-first refuses a stale upload; upload-first makes
disposition wait, then refuse the now nonempty draft and preserve its job/recording. No provider sends in these controls.

- Initial race:2tests/4.951s,1failure, retained.
- Final admission/commit controls:3tests/4.628s,OK.
- Affected recording/retention/redaction run:188tests/132.608s,187pass and1RF3 test scheduling error. Its old harness
  synchronously joined disposition from inside `store_upload`, which now correctly holds the row, so the harness
  waited on itself and had no completed result. The original failure is retained. The regression now disposes in the
  remaining pre-admission window, after the scoped read and before the row lock, preserving its prior refusal checks.
- Final focused run including both genuine disposition orders:5tests/6.444s,OK. Source frozen during each run.

The full affected suite still needs its final rerun after the revised race schedule. Independent finished-diff refutation
and exact integrated CI remain required. All first failures and green runs are retained under the report's evidence
directory with SHA-256 verification.
