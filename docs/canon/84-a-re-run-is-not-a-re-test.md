# A RE-RUN IS NOT A RE-TEST — IT REPLAYS THE WORKFLOW THE RUN WAS BORN WITH

**Recorded 2026-09-02, by owner ruling #164, from the merge queue of that night.**

## The measurement

A CI gate was fixed and merged to `main`. Three open PRs were red on that gate,
so each had its failed run re-run — `gh run rerun <id> --failed` — on the
reasonable-sounding belief that a `pull_request` run resolves its workflow from
the merge of base and head, and would therefore pick up the fixed gate now that
it was on `main`.

**All three re-runs failed identically**, and the run's own log said why:

```
npm audit --audit-level=high --omit=dev …      ← the RETIRED command
```

not the replacement that was by then on `main`. **`gh run rerun` replays the
workflow definition as it existed when the run was CREATED.** It re-executes
history; it does not re-ask the question.

## Why the belief was reasonable, which is the dangerous part

The premise is true of *new* runs: a `pull_request` event does resolve the
workflow from the merge commit, so a fresh run after the base moves genuinely
does see the new definition. The false step is assuming a re-run is a fresh run.
It is not — it is the same run, again.

> **A re-run answers "would this have passed then?" A new run answers "does this
> pass now?"** They differ exactly when the workflow itself has changed — which
> is precisely the moment you are most tempted to re-run.

⚠️ **AND THE FAILURE IS SILENT IN THE DIRECTION THAT MATTERS.** The re-run does
not warn that its definition is stale. It fails for the old reason and looks
like the fix did not work — inviting the conclusion that the merged change is
broken, when nothing was ever tested.

## The practice

- **After changing a workflow, bring each open branch ONTO the new base and
  push.** That produces new runs with the new definition, and it is also the
  correct pre-merge hygiene: the PR is then tested against the state it will
  actually land into, not against a base several merges old.
- **Read the run's own log before believing a re-run's verdict.** One grep for
  the command you expect to see settles it in seconds.
- **A re-run is legitimate for FLAKE**, where the definition is unchanged and
  only the world moved — a timing-sensitive UI assertion, a runner that lost
  communication. That is the case it is built for.
