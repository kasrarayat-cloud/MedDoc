# A DENY MATCHES THE AGENT, NOT THE SCRIPT — SO "IT IS DENIED" IS A CLAIM ABOUT BEHAVIOUR

**Ratified 2026-08-27.**

> **The permission layer matches the command the AGENT runs. It does not see
> what a script that agent runs does internally.** So a deny-list entry tells
> you what you may type — never what a sanctioned script can do.

⚠️ **REFERENCE CASE, AND THE ERROR TRAVELLED THROUGH TWO ACTORS BEFORE ANYONE
RAN THE COMMAND.** A ledger row recorded that `retire-branch.sh`'s remote leg
*"is DENIED"* and *"can never succeed"*, on the grounds that the script shells
`git push origin --delete` at line 77 and that
`Bash(git push origin --delete:*)` sits in the deny list. **Both of those facts
are true.** The conclusion drawn from them is false.

A supervised session then repeated the claim upward and **routed every one of
its own branch retirements through the REST API on that basis** — sound work,
built on an untested premise. The loop settled it by *running the script*:

```
bash scripts/retire-branch.sh feat/f8-s2-coding-view
  -> · remote — retired
git ls-remote --heads origin feat/f8-s2-coding-view
  -> (empty)      [positive control: main still resolves]
```

**The script's remote leg works, unchanged, with the deny entry still in place.**
The deny never sees it, because the agent ran `bash scripts/retire-branch.sh` —
which is granted — and the `git push` happened one process down.

## THE SHAPE, AND WHY IT IS SO CONVINCING

**"X is in the deny list" is a fact about a FILE. "X cannot happen" is a claim
about BEHAVIOUR.** The gap between them is exactly one command, and the reason
nobody runs it is that the file makes the conclusion feel already established.

> **This is the same reflex as *a documented defect is the most convenient
> suspect*, one layer up: the PRECEDENT was consulted in place of the
> MEASUREMENT.** There the precedent was a documented instrument bug; here it is
> a deny-list entry. Both are real, both fit, and both answer a question you did
> not ask.

**THE HABIT:** before recording that something is denied, **run it.** A refusal
is loud, instant, free, and completely unambiguous — it is the cheapest
measurement available in this repository, which is precisely why skipping it
never feels like a shortcut.

⚠️ **AND THE CORRECTION IS APPENDED, NOT SWAPPED.** The original row's wording
is kept beside the refutation, because a reader who remembers the old claim
needs to meet it and see it answered — deleting it would leave them believing it
with nothing to collide against.

**COROLLARY, for the other direction:** a wrapper that a rule routes you
through is *"a hole in its own deny by construction"* — `AGENTS.md` already says
this of `merge-pr.sh`. That is a deliberate, reviewed property of the design,
not an oversight, and this entry is its mirror image: the same mechanic read as
a *limit* rather than as a *guarantee*.
