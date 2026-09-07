# A REAL DIRECTORY IS NOT AN ISOLATED RESOLUTION — VERIFY THE LOOKUP, NOT THE ARTIFACT

**Standing 2026-09-07, from an incident I caused while trying to avoid it.**

## WHAT HAPPENED

A merge required regenerating the Prisma client. Two peer sessions were live, so
the question was whether the write would stay inside my worktree.

**I checked, and I checked the wrong thing:**

```
$ ls -ld .wt-omit/node_modules
drwxrwxr-x   ← a real DIRECTORY, not a symlink
```

That looked like isolation, so I ran `npx prisma generate`. It rewrote
`/opt/meddoc-pro/node_modules` — **the shared client — while a peer had seven
test processes running.**

**The path that decided the outcome was one level down:**

```
$ ls -ld .wt-omit/node_modules/@prisma
lrwxrwxrwx -> /opt/meddoc-pro/node_modules/@prisma     ← a SYMLINK
$ node -e 'console.log(require.resolve("@prisma/client"))'
/opt/meddoc-pro/node_modules/@prisma/client/default.js  ← OUT OF TREE
```

`node_modules` being real told me nothing about where `@prisma/client`
**resolves**, and resolution is what decides where an output lands.

## THE RULE

> **Where a write lands is a question about RESOLUTION, and resolution is a
> runtime fact. No `ls` can answer it. Ask the resolver.**

    node -e 'console.log(require.resolve("<pkg>"))'   # then realpath and compare

⚠️ **AND COMPARE WITH AN ANCHORED PREFIX.** `realpath` both sides first, or a
symlinked root compares unequal to its own contents — and a naive
`case "$out" in "$root"*` lets `/opt/meddoc-pro-other` pass as
`/opt/meddoc-pro`. The check is `"$root_real"/*`.

## ⚠️ THE SHAPE, WHICH IS OLDER THAN THIS INSTANCE

**Ask what your identifier is an identifier OF, and whether the thing you
inspected is the thing that decides.**

| inspected | what actually decided |
|---|---|
| `node_modules` is a real directory | where `@prisma/client` **resolves** |
| `$$` in a tool shell | a subshell that has already exited (canon 122) |
| a 40-hex string's **form** | whether that commit **exists** (canon 115) |
| `origin/<branch>` | a cached belief, not the remote |
| a property **mentioned** in a matrix | whether it is **varied** (ruling #227) |

In every case the instrument answered correctly about the wrong thing, and in
every case it did not present as broken.

## WHAT MAKES THIS ONE WORSE THAN THE OTHERS

**I was actively trying not to do it.** I knew peers shared the tree, I checked
before writing, and the check I chose was the plausible one. **A wrong check
performed diligently reads exactly like a right one**, and the diligence is what
makes it convincing — to yourself most of all.

The guard is therefore mechanical, not a habit:
`scripts/prisma-generate.sh` asks node and refuses out-of-tree output;
`check-worktree-resolution.sh` asserts it standing;
`setup-worktree.sh` gives each worktree a real `@prisma/client` and `.prisma`.

⚠️ **AND THE FIX HAD TWO DEFECTS OF ITS OWN, BOTH FOUND BY RUNNING IT** — a
refusal message whose backticks the shell executed, and a probe appended after
the script's `exit` that never ran at all. **Writing the guard is not the same as
arming it.**
