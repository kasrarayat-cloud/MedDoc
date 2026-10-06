# Sol continuation — recovered state and initial repairs

This is an append to the earlier handoff, not a replacement of its failed
results. Engineering and qualification remain in progress.

Recovered candidate `d49ece788c058c9e733e895910a81c8aad94c6a3` is clean and equal
to origin `v1/release-integration`. CI37065186821 passed all six jobs;
secrets-scan37065186594 passed. Installed revision remains
`dedac1625032e32c7a149e6771be22e26c307eb1`. The recovered presentation demo was
the older fixture environment14ed2459, on localhost9140/9141, not this candidate.
All96 V1/V2 worktree identities were inventoried. Two dirty worktrees and their
diffs, original campaigns, sealed corpus and other sessions were preserved.

## QA credential incident

The disclosed credential belonged exclusively to synthetic QA PostgreSQL
`v1-sonnet5-qa-pg`, TCP127.0.0.1:55731. The real demo launcher was found and
stopped after its PID/cwd/command identities were checked. A new password was
generated in memory, the QA role changed, and its protected0600 handoff replaced
atomically. A new connection succeeds; the old credential fails on a new
connection. Doctor/admin/worker restarted with the new credential. Real
authenticated doctor `/patients/` and MFA admin `/console/` requests return200.
Installed9130/9131 still reportdedac162 and synthetic-only; public maintenance and
co-tenants retain their expected status. Production credentials were not read
or changed.

One matching original test-agent transcript was retained in place with0600
permissions and hashed in the protected incident manifest. It was not copied
into this report. Shell tracing of the historical runner expanded its password
variable. The current mapping runner already reads it inside an untraced child;
the new continuation QA runner likewise loads it inside Python with a scrubbed
environment. A shell-traced wrapper test verified the child received the secret
and that the trace did not contain it. All new runs use this protected route.

Incident evidence lives in
`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/qa-rotation/`.

## Accounting correction

The committed standing authority record was hash-verified; no duplicate grant,
new ceiling or counter reset was created. Five standing campaigns retain119
attempts, zero open attempts and one historical unknown outcome.

Their `$1.415165987600` total is **calculated exposure**, not wholly measured
spend. Known metered responses total `$1.1404629876` at the configured rates;
the remaining `$0.274703` is the original uncertain-request bound. Historical
staged testing remains separate at `$0.130880`. Provider-billed invoices or
reports remain unavailable.

The unknown request's original capture proves HTTP400 schema rejection with no
metered message. A separate committed declaration prepares audited resolution
of its still-held QA reservation. This document does not claim that act has run.
The failed campaign, original outcome and accounting records remain unchanged;
the recovered outcome will be appended. No prior request has been repeated.

## Resource gate and cleanup

Initial preflight correctly blocked at91% disk. The owner's explicit scoped
cleanup authority was applied before any subagent/product work. The old reclaim
script was inspected, not run. Two exact stopped synthetic Word-battery trees
were archived by content SHA256, every member verified, and all original paths
and file identities recorded before checked removal. Their loose allocation was
5,861,744,640bytes across142,945files. Source manifests, first-pass evidence,
campaign databases, financial ledgers and original forms were retained.

Four proposed source copies were refused before deletion because the first
contained an unexpected symlink. They remain intact. No shared tree, Docker root,
cache-wide or other-agent sweep occurred. Compressed archive encodings are being
verified separately; final filesystem recovery is measured after those steps,
not inferred from a9GB estimate. No physical secure-erasure claim is made.

Preflight at21:56Z admits FIX-AND-GO with disk90%,29GB available, healthy required
containers and passing co-tenant statuses. OOM journal inspection was skipped
because this account cannot read the kernel journal; it is not a no-OOM finding.
Four isolated worktrees were created fromd49 and the three native specialists
started only after this gate. Heavy suites and paid work remain serialized.

Protected continuation checkpoint and preservation manifests:
`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/`.
