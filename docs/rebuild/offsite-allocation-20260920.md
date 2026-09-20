# Finite account allocation and shared allowance

The owner supplied a complete desktop account audit ending
2026-09-20T20:16:35.867379Z. Two fully paginated scans agreed: one private
bucket,44 retained uploaded versions,14,422,252 bytes account-wide and in the
QuillMD prefix, no unfinished uploads or parts. The VPS did not perform those
scans. The temporary unrestricted-bucket read-only audit credential was revoked;
a later fresh authorization returned401. Existing restricted runtime scope
remained listFiles/readFiles/writeFiles for the same bucket/prefix. No listKeys
proof or complete credential inventory exists.

The original Windows artifact's **reported** SHA256 is
`e6494517db15db349276966790fec9cab4b06c019bfa7f509a212f1684816a89`.
The original bytes were not supplied; embedded JSON was reserialized locally.
Protected local audit hash:
`1812e68eb8f054da1b6678a9df7883d4266d7b3bd1765fd28a92ce2cbea96eb0`.
Protected updated operating-evidence hash:
`45d387be82724f1ae236e18c7da5431be41818a609ff0cd8e4ccdcd7973f73c5`.
They live under `.runtime/offsite-account-evidence/20260920T201635Z/` alongside
provenance. Original pending-revocation and incomplete earlier observations
remain history. The later revocation addendum supersedes only that pending state.

The20:20:54.200Z authenticated UI showed rounded daily4MB storage and29MB
downloads,10GB/$0 and1GB/$0 caps,ClassB88/2500 andClassC58/2500. Those displays
are neither exact stored-byte inventory nor present guarantees. Four subsequent
authorization calls and potential browser requests must be accounted for.

## Allocation and assumptions

The supported consumer inventory and commands are in
[offsite-consumers-20260920.md](offsite-consumers-20260920.md). Known project
consumers share one canonical lock, ledger and policy. The fixed protected
allocation companion binds the policy bytes, local source hashes, original
desktop provenance and observed inventory. Changing operational controls requires
reviewed source and a refreshed companion; it cannot refresh the original audit
time. The original296 requests/68,551,020 reserved response bytes remain a
nondecreasing historical floor, including after UTC rollover.

Reserved limits:1GB prefix storage,100MB response bytes and500 requests per UTC
day,900-second technical work,30-hour local age. Requests are debited before
HTTP, failed/uncertain work has no refund, and possible midnight spill is charged
to both days. The whole known cycle is admitted before first network activity;
additional pagination still consumes the same hard limits. A crash leaves its
charges and pending writes behind. Existing versions plus pending bytes must fit
the ceiling, with the previous recoverable set retained. Capacity exhaustion
requires investigation or separately authorized retention decisions, not pruning.

The conditional account bound is **observed non-prefix bytes0 + reserved
prefix1,000,000,000 bytes**. It assumes no unregistered prefix writer or
unobserved outside storage growth during validity. The owner can administer the
account; the audit does not claim otherwise. Before changing other storage,
credentials, caps or consumers, suspend recurrence and obtain new account evidence.
Before outside reads/audits, reserve bounded request/response consumption in the
same ledger or suspend recurrence. The operator's ability to deliberately bypass
code is an administrative boundary, not evidence of exclusive credentials.

This24-hour validity is an engineering limit, not a future-usage guarantee.
It ends **2026-09-21T20:16:35.867379Z**, supporting the firstSep21 05:00UTC
run and its full bounded interval. Without renewal the following daily run must
refuse. The restricted runtime can only refresh scoped versions and verify no
unfinished uploads. Fresh account-wide renewal requires owner desktop access;
the worker cannot do it unaided.

The Native API enumerates retained versions and separately reports unfinished
large files; refusing any unfinished upload avoids pretending unknown parts have
zero bytes. See the official [version listing](https://www.backblaze.com/apidocs/b2-list-file-versions)
and [unfinished upload listing](https://www.backblaze.com/apidocs/b2-list-unfinished-large-files)
contracts. These public documentation reads consume no authenticated B2 allowance.

## Installation, renewal and current outcome

The scoped declaration is
[`20260920-quillmd-offsite-activation.md`](../foundation/mutations/20260920-quillmd-offsite-activation.md).
`install_offsite_policy.py` validates protected desktop evidence, derives finite
expiry from its actual observation, preserves prior policy/allocation records and
publishes under the shared lock. Its default plan is not an activation; execution
uses the committed declaration and reviewed permanent main. The schedule installer
then adopts unchanged units and qualifies the actual service before timer enablement.

Installed monitoring and operator responses are documented in
[offsite-activation-operations-20260920.md](offsite-activation-operations-20260920.md).
Actual live outcome, exact revisions, allowance/object totals, timer and next run
are in `.runtime/offsite-activation-20260920/FINAL-REPORT.md` and the append-only
`.runtime/CHECKPOINT-LATEST.md`; source documentation is not execution evidence.
Historical custody/receipt/independent restore remain separate from policy
eligibility and actual timer activation. Desktop temporary secret files remain
protected because their deletion was blocked; no VPS operation removes them.
