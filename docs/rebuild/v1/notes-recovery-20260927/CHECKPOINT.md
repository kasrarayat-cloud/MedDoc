# Ordinary notes recovery — 2026-09-27

Owner milestone: invited US real-patient QuillMD V1; ordinary typed/dictated notes and broad custom Word support remain required. This is engineering preparation, no launch claim.

- Worktree: `/opt/meddoc-pro/.worktrees/v1-notes`; branch `v1/ordinary-notes`; recovered HEAD `d346f7c0f8721b91399030eeb40d9cac728df019`.
- Sole writer: Astra notes recovery subagent. No notes mutation or test process was active at recovery 16:20Z. PostgreSQL 55706 is the isolated synthetic notes test DB; one process at a time.
- Preserved uncommitted work: 44 lines of `RoundThreeMutantPins` in `rebuild/core/tests/test_v3_ordinary_notes.py`.
- Prior scratch retained in `/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/notes-repair3` and prior execution log in `/home/claude/.claude/projects/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/subagents/agent-a70ba6c17594e921a.jsonl`.
- Interrupted batch F actually finished exit 0 at 15:55Z. Original `generation.py` SHA restored and independently checked against `gen-F.sha`: `40be29702245bbba` prefix. No restore was repeated.
- Proof defect found during recovery: batch-F FD mutant produces a syntax error (extra quote), so its claimed kill is invalid. Preserve original attempt and replace only that proof with a compiling mutant and specific failing test.
- Next: repair FD proof, run final core and explicit document suites once, identity harness, cost and finite existing hold-rate probes; report residual incorrect adoption and usefulness limits; finish local commit only.
- No providers, spending, deployment, push, merge, campaign/holdout, or email authorized/performed by this stream. No active operation needs retry or financial reconciliation here.

## 16:42Z continuation update

- Baseline core suite on recovered `d346f7c0` plus original uncommitted mutation pins passed: 1263 tests, 9 skips, 463.772 s. R3 first-pass hold rates remain 11/12 and 72/77 held; these are retained unchanged, not redefined around successful examples.
- New recovery tests committed `00dcc969ec79ec79447a2e5ee3ae135691998da8`: five of seven targeted tests failed before the repair.
- First repair candidate committed `af948a44cdd79fca0d33f971790bb1331633ff40`; generation SHA `a08a0fb560bfa9b151042a6c815aa88e342cdf21405d4e349329122f9bf167a4`. Source is stable, no active mutation. 11 compiling mutants failed meaningful assertions and restored the source. Ten focused cases and worker→review→finalize→Word export passed with a mocked provider. Historical tab/WM/legacy identity remains `083b6fca176780ea999f827beae2285273e8706c80a18910def636fbb42a8c9b`.
- Independent refutation found TWO release-blocking defects in the new intact-paragraph relaxation. `Lt knee` and `Allergies` wrongly accept paragraphs on another topic; repeated instructions are deduplicated, dropping a later dose. **Do not integrate af948a44.** Reproductions and before/after source snapshots are retained under the sibling `blockers-repair5/astra-recovery/notes-refutation/` scratch directory.
- The full core/document sequence is currently running on af948a44; logs `notes-repair3/recovery-final-core.txt` and `recovery-final-documents.txt`, tool session 86418 (OS process initially 645109). Let it finish; do not edit generation.py while it runs.
- Next safe action: add prewritten RED tests from `/tmp/quillmd-notes-refutation-repairs.py` and `/tmp/quillmd-notes-duplicate-worker.py`; narrow relaxation to explicit general narrative target names; preserve duplicate occurrences in intact paragraphs; run changed focused/worker/identity checks and independent refutation. Retain full suite evidence with its actual candidate SHA instead of pretending it proves a later diff.
- Read-only independent review of v1-review b15c44c6 found no integrity defect, one LOW refusal wording overclaim for a never-existent UUID after a real notes change. Reproduction `/tmp/quillmd_review_warning_probe.py`, `/tmp/quillmd-review-warning-probe.log`; reported to lead. No review-branch edits.
- After notes closeout, lead additionally assigned selective required WM narrative integration in a NEW isolated `v1/wm-required-repairs` worktree. Base must be the confirmed prepared release after cleared notes/review integration. No new branch created yet. WM draft stays untouched; no campaign, spend, flag activation or deployment authority is implied.

## 16:51Z stable closeout

- Final code HEAD `6ea775b6683afe4aa0b56b73bc0582d9ce72380d`; generation SHA `4375da5758ee5457148c842d27214e65af0b8d08294ca3313b4caf4db26721fe`. No active notes test/mutant; all source restores reconciled. Durable docs/evidence are the only pending changes before their own commit.
- `af948a44` full sequence completed: core 1275 / 9 skips; explicit documents 108. Final repaired changed-path tests: 134 pass. Two final compiling mutants killed, restored=true. 30-case identity unchanged. First-pass hold rates unchanged1/12 and5/77 supported; no reclassification.
- Independent refuter verified final code: Lt knee and Allergies wrong-destination cases now held; repeated dose all3 occurrences survive in order, exact offsets. NOTHING ELSE FOUND within these claims; semantic/model qualification remains open. The source tree is ready for lead's local integration decision, not release admission.
- Independent review-guards LOW false-history warning concern was reproduced, repaired by lead, and reread with no remaining demonstrated concern. No edits were made to that worktree.
- Next safe action after docs commit: lead supplies exact combined release SHA containing cleared notes/review. Create NEW `/opt/meddoc-pro/.worktrees/v1-wm-integration`, branch `v1/wm-required-repairs`, selectively integrate required WM ordinary-narrative path including paired adapter/digest and Sonnet5 profile. Preserve PR1287/draft; no providers, campaigns, flags, production writes or spend.
- All prior scratch, failures, attempted metrics and refutation evidence remain intact. No financial authority consumed; no pending provider outcome exists in this stream.
