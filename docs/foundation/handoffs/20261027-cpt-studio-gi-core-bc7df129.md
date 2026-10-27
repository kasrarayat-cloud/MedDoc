# Handoff: CPT Studio GI core, session bc7df129 (meddoc-pro-01), paused for host maintenance 2026-10-27

The owner announced a host maintenance shutdown at 04:00 Pacific (11:00Z) on 27 October 2026 and asked for everything
to be saved by 03:30 Pacific (10:30Z) and work to stop until the host is back. This note is the state at that stop.

Owner chose "Take over now"; 909be030 was stopped at 02:50:59Z (ruling file interpretation 18). Branch
`fix/cpt-studio-gi-service-core-20261027`, PUSHED to origin (no PR yet; feature-branch pushes trigger no workflow).
The live install is unchanged (2734a6f3, installed from 057a7d398).

## Where everything is
- Code: the branch. Commits after the peer's WIP 2: WIP 3-7 (triage round 1 and 2 merges), WIP 8 (a7f2810c, round-2
  skeptic repairs), WIP 8b (8f8a3b48, consent subject). Check `git log --oneline 057a7d398..HEAD`.
- Scratch that survives the reboot (`/tmp` is cleared at boot on this host): `/home/claude/cpt-studio-gi-core-save-20261027/`
  (mode 0700). `bc7df129/gi-core/` = this session's tools, drafts (pr-body-draft.md, residuals-draft.md), triage NOTES,
  patches, probes, refute/workflow.js; `909be030/gi-core/` = the peer's dev env file (`cpt-dev-env.sh`), the held-out
  set (`heldout/`, `heldout-out/`: do NOT read its documents or tune on them), the live-dump evidence of the 11 original
  encounters (`live-dump/`), and corpus/eval files. It holds synthetic clinical text: reap it at session close
  (`scripts/reap-session-scratch.sh`), never commit it.
- After the reboot, restore the scratch paths the tools expect, e.g.
  `rsync -a /home/claude/cpt-studio-gi-core-save-20261027/bc7df129/ /tmp/claude-1000/-opt-meddoc-pro/bc7df129-c1e5-42ac-bc52-4068c37c67be/scratchpad/`
  and the same for 909be030's scratchpad; then check the dev test database (container `cpt-studio-test-pg`,
  127.0.0.1:55452) is up.

## State at the stop
- Round-2 skeptics (wf_c8621dd8-f03): every refuted repair was replaced by a general rule with regression tests (WIP 8:
  strict boxes and form fields, consent, modal scope, label-line headings, engine status signal and own-mark
  exclusion, the snare "Site:" line). Interpretations 23-24 and ARCHITECTURE 5.12 record them. The facts_wording
  skeptic's batteries (six, in triage2/facts_wording-skeptic/probes) now read as before the modal fix except the
  intended hypothetical repairs.
- Targeted runs green on WIP 8/8b: the 23 classes that had failed, the reader, corpus, formats, second-review, wording
  and routing modules. Full suite: runs/wip8-a (snapshot taken before WIP 8's tests) and a run on 8f8a3b48 if it
  finished before the stop - see the scratch runs/ directory. Known load-sensitive timing tests (r4c_validation
  Bounded4, r4_validation CoverageCost) fail under host load; re-time them on a quiet host.
- Refutation pass (mandatory, AGENTS.md): workflow run `wf_7881c326-ebd`, 10 lenses (release, missed, negtime, sends,
  report, cost, migrate, formats, context, boxes) in armed sandboxes `.lens-r1-<lens>` at 8f8a3b48 (ARMs 0-5 and 7-9
  green; ARM 6 checks a JS package and does not apply to this Python app). If it was stopped at the shutdown, do NOT
  simply resume it: a resume replays only the longest unchanged PREFIX of agent calls, so one unfinished early lens
  re-runs every later one live. Read the journal under
  `~/.claude/projects/-opt-meddoc-pro/bc7df129-c1e5-42ac-bc52-4068c37c67be/subagents/workflows/wf_7881c326-ebd`
  (journal.jsonl), keep the finished lenses' and verifiers' results, and run a continuation script for the missing
  work only (args `{"commit": "8f8a3b48f263c58c4cfa68568d986bc58ca54c96"}`; the script's durable copy is in the save
  directory, `bc7df129/gi-core/refute/workflow.js`).

## Left (in order)
1. Finish the refutation pass; verify every finding yourself; repair blocking ones by general rules; re-attack each
   repair once (interpretation 21); record non-blocking misreadings in `cpt-studio/ACCURACY-RESIDUALS.md` (draft rows in
   the save directory's residuals-draft.md) and the PR body.
2. Full suite green on the final commit (one suite at a time; swap is high on this shared host).
3. PR (body via file; draft in the save directory), CI (CI, cpt-studio, secrets-scan), `bash scripts/merge-pr.sh`.
4. Declaration `docs/foundation/mutations/20261027-cpt-studio-gi-core-upgrade.md` in its own PR, naming the merged
   revision; counts baseline from `tools/live_counts.sh` (03:23Z: encounters 11, proposals 134, decisions 15, audit 108,
   jobs 44/0 active, studio migrations 5, credits 0.504880 - re-take it before the act). Install via
   `scripts/run-ruled-mutation.sh` (phases preflight, image, app with `--provider-mode live --authorization-ref` the
   ruling file, verify; receipts in /home/claude/cpt-studio-install-20261023; the app phase parks the old pair and
   applies migration 0006).
5. Live HTTPS walk with the held-out set (`ops/verify_browser.cjs` against https://cpt.quillmd.com with the agent
   credentials file, `--allow-live-provider`), then `ops/verify_downloads.py`, usage, and the final report the owner's
   directive lists (installed revision, root causes, repairs, coverage matrix, acceptance results, preserved failures,
   usage, dependencies; no accuracy percentages).
6. Reap: the lens sandboxes (`scripts/reap-lens-sandbox.sh`, including the peer's stale `.lens-cptgi-*` at 9eb82f0d),
   the save directory and the session scratch.
