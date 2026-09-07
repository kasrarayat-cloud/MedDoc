# `gh` RETURNS AN EMPTY STRING, NOT NULL, FOR A RUNNING CHECK — KEY ON STATUS FIRST

**Standing 2026-09-07, from a monitor that reported a failure that had not
happened.**

## THE REFERENCE CASE

A monitor watching a PR's required checks, written to alert on failure:

```bash
jq '[.[]|select(.conclusion != null and .conclusion != "success")]'
```

It fired: **"⚠️ A CHECK FAILED: CI:"** — and the alert carried an **empty**
conclusion. `CI` had not failed. It was `in_progress`.

**`gh run list --json conclusion` returns `""` for a run that has not
finished, not `null`.** So `.conclusion != null` is TRUE for every running
check, and every running check looked like a failure.

## THE RULE

> **`status` is the field that says whether there is a verdict. `conclusion` is
> the verdict. Never read the second without gating on the first.**

```bash
jq '[.[]|select(.status=="completed" and .conclusion!="success")]'   # correct
```

## ⚠️ WHY THIS ONE IS DANGEROUS IN BOTH DIRECTIONS

**It cries wolf**, which is the cheap failure: a false alarm costs a look.

**And the same confusion inverts.** A filter written
`select(.conclusion == "failure")` misses a run that was **cancelled**, **timed
out**, or **action_required** — all of which are non-success conclusions that a
`== "failure"` test lets through as if green. A push that cancels somebody's
citation produces exactly `cancelled`, and this repository has recorded that
class five times.

> **Enumerate the terminal states, or gate on `status` and treat everything that
> is not `success` as a finding.**

## THE FAMILY

The empty string is the same trap as the other instruments here that answer
confidently about the wrong thing:

- `gh run list --commit <SHORT-sha>` returns `[]` for **any** abbreviated SHA;
- `gh run list --commit <FULL-sha>` returns `[]` inside the propagation window
  while the runs exist;
- `gh pr checks` reports `pending` for a run already `completed/success`;
- `gh pr edit --body-file` **fails outright** while printing what reads as a
  deprecation notice.

**Four of them return a plausible value rather than an error.** The tell is
never the shape of the answer — it is asking the same question a second way and
requiring the two to agree.
