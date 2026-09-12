# Preserved orphan-worktree refs — for the admin lane to adjudicate

**Filed 2026-09-12 by the worktree-sweep close-out. FOR THE ADMIN LANE:
adjudicate each as MERGE / SUPERSEDE / CLOSE when the lane reopens.**

During the owner-authorized worktree sweep, three worktrees held work that was
the **only copy on the box** — the remote branch had been retired while the
branch was unmerged, or the work was uncommitted. Per the owner's standing rule
(*nothing on this box may be the only copy of committed work*), each was pushed
back to origin and pinned with a tag **before** anything else. **None was
reaped.** Tags trigger no CI; the branch pushes carried no open PR, so they
triggered nothing either.

This note exists so the work is not silently lost and is not silently merged:
the disposition is the admin lane's to make, not the sweep's. The rows below
carry the FACTS and the signals found — not a verdict.

| # | branch (tip) | preservation tag | commits vs main | worktree |
|---|---|---|---|---|
| 1 | `fix/ruling-162-blank-proof` (`a1d76e1d`) | `preserve/ruling-162-blank-proof-20260912` | 8, none patch-present in main | `.r162` (kept, clean) |
| 2 | `fix/ruling-297-keep-policy` (`0708b581`) | `preserve/ruling-297-keep-policy-20260912` | 5, none patch-present in main | `.wt-keep` (kept, clean) |
| 3 | `scratch/cdev-certify-live-template` (`ce0efcc5`) | `preserve/cdev-certify-live-template-20260912` | 1 (a rescued untracked file) | `.cdev` (kept, detached before; **left alone** per owner) |

## 1 · `fix/ruling-162-blank-proof` — ruling #162 blank-proof (twin)

Commits (newest first): `a1d76e1d` fix(ops) dc.sh must not grant what
settings.json denies · `1456c7a8` fix(twin) legacy form field's result cleared
across paragraphs · `d7df9288` #162(c) emptiness is one byte comparison ·
`c75ebf20` docs #162(c) · `70e410f3` #162(b) content locus declared, emptiness an
allowlist · `7368b5ee` docs #162(b) · `c7d7e715` #162 blank proof proven in the
OUTPUT · `3828750c` docs #162.

⚠️ **SIGNAL — likely SUPERSEDE, the lane decides.** `RULINGS.md:278` records
**#162(c) as SUPERSEDED by #164 then #165** — *"the renderer fix rides the PR;
emptiness is byte-equality."* So the blank-proof direction this branch encodes
was re-decided and shipped under #164/#165. Whether any part here (e.g. the
`dc.sh` ops fix, or the legacy-form-field clear-across-paragraphs fix) is worth
cherry-picking is the lane's call.

## 2 · `fix/ruling-297-keep-policy` — ruling #297(b) rollback keep policy

Commits: `0708b581` #297(b) the gate moves with the policy (two arms) ·
`02cb1dc6` #297(b) rollback keep policy amended, declaration lands with it ·
`84bda1dd` docs #297–#300 · `b8acb4ac` docs(qa) #295 Gate-C · `65ef2f5e` docs
#294–#296.

⚠️ **SIGNAL — possibly MERGE, the lane decides.** `RULINGS.md:413` records
**#297 as STANDING — CLASS (d)**: the amended keep policy (keep tags < 72 h PLUS
the last FIVE judged deploys, via `prune-rollback-tags.sh`, act under a
§2.5-style declaration). The ruling stands but **these implementing commits are
not patch-present in main** — so the standing ruling's `prune-rollback-tags.sh`
amendment may be unshipped. Confirm against current `main` before acting (it may
have landed by another path). If it did not, this is a standing ruling with its
implementation still on a branch.

## 3 · `scratch/cdev-certify-live-template` — a rescued uncommitted file

`ce0efcc5` commits `apps/transcribe-md/scripts/certify-live-template.ts` (176
lines), which was an **untracked** file in the detached-HEAD `.cdev` worktree.
Its committed base (`157eeef8`, PR #927) is already in main; only this one script
was unique. Scratch branch off that base so origin holds a copy. The lane
decides whether the script is wanted (merge/rework) or disposable (close). The
`.cdev` worktree itself was **left in place**, not reaped.

## What the sweep did NOT do

It did not merge, rebase, or reword any of this work, and it did not delete the
three worktrees. Preservation only. Everything else adjudicated in the sweep was
either active (remote still present) or already merged; only `.wt-d2`
(`docs/deploy-decl-7445308b`, merged via `4e4d8e7c`) was reaped.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01E4qB6iqNwX22CXmtMyJvjq
