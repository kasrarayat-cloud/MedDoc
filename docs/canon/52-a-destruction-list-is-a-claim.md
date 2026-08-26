> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **112 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ Close-out hygiene — reap the scratch, every session**.
> Why the split: `docs/canon/README.md`.

### ⚠️ A DESTRUCTION LIST IS A CLAIM

**Standing 2026-08-18.** A list of things to reap — handed over by another
session, a report, or your own earlier self — is a CLAIM about what those paths
are. Destruction is irreversible, so the claim is verified before it is executed,
never after.

> **CLASSIFY BY CONTENT, AND VERIFY REGISTRATION.** Before anything is shredded:
> `git worktree list` (is that directory a registered worktree?), `gh pr list`
> (does an OPEN pr depend on it?), and `git ls-files` (is the file TRACKED?).
> A path is scratch when those three say so — never because a list said so.

⚠️ **REFERENCE CASE, AND IT WAS ONE COMMAND FROM REAL LOSS.** A loop session
handed over a reap list reading, in effect, *"`.f18-comment603.md`,
`.f18-wt/.f18-{msg,msg2,…}`"*. The list meant **scratch files INSIDE a
worktree**. Read literally as *"reap `.f18-*`"* it would have destroyed:

- **`.f18-wt` itself — a REGISTERED git worktree**, not a stray snapshot;
- on an **UNMERGED** branch with **PR #722 OPEN**;
- whose `.jpeg`/`.png` files are **TRACKED repo content** (`certify-panel.png`,
  `audit-new-visit.jpeg` and others), not evidence and not scratch.

**The filenames looked exactly like the liability class this file warns about** —
a directory of images with audit-shaped names, sitting in the repo root. That is
the trap: the shape that should make you suspicious and the shape that is
innocent are the same shape, and only the three checks tell them apart.

⚠️ **AND THE PHI SWEEP'S ONE HIT WAS PROSE.** A grep for PHI/credential shapes
matched the word *"patients"* in one file. Read in context it was
`patients 34` — a §2.5 **clinical-count row**, a number and not content. Had the
sweep's zero been trusted in the other direction, or its one hit been treated as
a finding without reading it, the conclusion would have been wrong both ways.

**POST-DESTRUCTION CONTROLS ARE PART OF THE REAP, NOT AN EXTRA.** After
shredding, assert what must SURVIVE, not only what must be gone: the worktree
still resolves, its tracked files are present, its `git status` is still clean.
A reap that only proves absence cannot tell "I removed the scratch" from
"I removed rather more than the scratch".

#### Session evidence trees are EXTRACT-THEN-SHRED, at session end

**Findings go into the repository; the raw tree is destroyed. An unowned
snapshot never persists.** This is not conditional on the tree being dirty.

The reasoning is the part to remember, because "it is clean, leave it" is the
intuitive answer and it is wrong: **a tree that is provably clean today has to be
re-proven clean by every future sweep, for as long as it exists.** The
verification cost is paid again and again, by people who did not create it and
cannot tell from the outside whether it matters. And the class is not
theoretical — the 2026-07-28 history purge missed six copies of two filled
exports because they sat in exactly this kind of tree, invisible to a stale-copy
scan that enumerated git repositories.

The shape:

1. **EXTRACT the reports** — `.md`/`.txt` summaries, findings, conclusions. Never
   source snapshots, build output, container ids, port files, temp paths or file
   manifests: those are the machine's leftovers, and keeping them is how the
   liability class reconstitutes itself. Land them under `docs/qa-reports/` and
   **commit and push before shredding anything** — extraction must be durable
   before destruction begins.
2. **Check admission harder than the sweep did.** A file entering the repo enters
   every future clone. Credentials by value AND by shape (`PGPASSWORD=`,
   `postgres://user:pass@`, generic `password|secret|token|api_key` assignments,
   `sk-`, `Bearer`, PEM headers, `AKIA`), negative-controlled against a canary
   carrying those shapes; plus a prose read of anything whose title implies a
   secret a pattern cannot see.
3. **Read what you are about to destroy.** The 2026-07-30 extraction found a
   document recording a service credential seen in a process command line, whose
   own disposition made rotation a **release blocker** — and nothing in the repo
   recorded that rotation happening. Shredding first would have destroyed the
   only pointer to an open security item.
4. **Then shred, per the rule above** — `chmod u+w` first (a mode-`0400` file is
   the known failure), unlink symlinks rather than shredding *through* them (a
   symlink is how a sweep destroys something outside its own boundary),
   escalate root-owned files via root-via-docker, and remove the directories
   **only** when the failure count is zero.
5. **Verify with a controlled sweep and state the boundary** — including the
   positive control, or the zero means nothing.

#### A history purge does not clear the filesystem

`docs/smoke-test-2026-05-04/phase-C/export.{docx,pdf}` were purged from every ref
on 2026-07-28. **Six copies were still on this host on 2026-07-30**, in three
plain directory snapshots dated 2026-07-21. The purge's own stale-copy scan was
`find / -name .git` + `git cat-file -e <blob>` per repo — and a snapshot **is not
a git repository**, so it had no `.git` to enumerate and no object database to
query. The scan was right for clones and blind to snapshots.

So a stray-export sweep is not optional after a purge, and it has a shape:

- **Search the CONTENT PATH, not only git objects** — basenames *and* the path
  fragment, not blob SHAs.
- **Unbounded depth.** A first pass at `-maxdepth 6` returned **4 of the 6** and
  read as complete; the other two sat at depth 7. A depth-limited sweep is a
  sample, never an inventory — the same defect as an emptiness test that passes
  on a set whose size it never established.
- **`-xdev`,** and say which device you covered.
- **State the boundary in the report** — roots, depth, filesystem, file count.
  A sweep that does not say what it looked at cannot be checked, and "I found
  nothing" is worthless without "here is where I looked".
- **Positive-control the traversal, not just the needle.** Confirming your
  matcher finds a secret's value in `.env` proves the *needle* works. It says
  nothing about whether the search ever entered the trees you named — and a
  traversal that silently covers nothing returns zero for every needle you try.
  Run the same matcher form against something known to be present in the
  haystack (`meddoc`, `transcribe`) and report the hit count beside the zeros.
  Without it, a clean sweep and a broken sweep are the same output.

  This is the *third* face of one defect — after §4's dead stack and the
  `-maxdepth 6` sample: **an answer about a set whose boundary was never
  established.** Whenever a check reports "nothing wrong", ask what it would
  have taken for it to say anything else.

