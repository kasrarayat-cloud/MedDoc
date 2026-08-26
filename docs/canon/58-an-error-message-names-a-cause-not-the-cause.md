> **CANON — authored 2026-08-26, landed directly here.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries one-line index rows
> pointing here; those rows are POINTERS, never the rule. Nothing in this file
> is rewritten — corrections are appended and dated and superseded wording is
> kept, because in this programme the correction is the point.
>
> Provenance: these three entries were written against the pre-split
> `AGENTS.md` in **PR #871** and were still open when the owner-directed SPLIT
> landed as **PR #873** (`c6263cfc`). They are therefore the **first entries
> authored for `AGENTS.md` and landed in `docs/canon/` instead** — the bodies
> are unchanged from #871; only their destination moved.
>
> Why the split: `docs/canon/README.md`.

## AN ERROR MESSAGE NAMES *A* CAUSE, NOT *THE* CAUSE

**Standing 2026-08-26. The one-word-two-worlds family, arriving from a vendor.**

> **A vendor's error string is a HYPOTHESIS with authority attached. Verify the
> mechanism before you act on the noun.**

⚠️ **REFERENCE CASE.** `actions/upload-artifact` failed with
**`Failed to CreateArtifact: Artifact storage quota has been hit.`** Read
literally, that is a storage problem. So storage was measured (2591 artifacts,
10.77 GB; 1124 live against a 2 GB allowance), **344 artifacts were deleted
across two repositories, 2.85 GB freed** — and the next run failed **identically**.

**The real mechanism was a BUDGET throttle**: Actions spend sat at `$383.37 of
$390`, **98%**, and stop-usage refuses *every* billable operation — uploads
included — regardless of how much storage is free. Proven when the ceiling moved
$390 → $395 and **the same job was accepted on attempt 1**.

**THE TELL WAS AVAILABLE AND WAS NOT READ AS ONE:** the deletions demonstrably
worked (live storage 3.38 → 1.84 GB, under the allowance) **and the symptom did
not move.** *A fix that provably lands and changes nothing is evidence about the
diagnosis, not about the fix.*

## AND DO NOT LET A FIX TAKE CREDIT IT DID NOT EARN

**Same incident, and it is the reporting half.**

The artifact deletions were **correct hygiene** — they cut a retention surface
nobody had sized against the repo's real run rate. They were **not the cure**,
and a report that lists them beside "and then it worked" implies a causal chain
that did not exist.

> **When a fix ships alongside the real cure, say which one worked.** The next
> reader inherits the mechanism, and a wrong mechanism stated confidently
> outlives the session that wrote it.

## THREE ACTORS, ONE DIAGNOSIS — THE STANDING AUTHORITY'S THIRD-ACTOR PROOF

**Standing 2026-08-26.**

The unattended loop hit the same wall independently, wrote
*"THE GITHUB ACTIONS BUDGET IS EXHAUSTED. THE REPOSITORY CANNOT MERGE"*,
classified it **STANDING AUTHORITY class (d) — money** — and **HALTED** rather
than working around it. It stayed dark four hours rather than spend.

Three instruments converged: a supervised session's wall-clock arithmetic, the
loop's merge failure, and the owner's Budgets UI. **The routing held under a
class it had never been tested on** — the loop had authority to build, prove and
merge, and correctly judged that none of that entitled it to spend.

> **An authority boundary is only proven by the case where stopping is
> expensive.**
