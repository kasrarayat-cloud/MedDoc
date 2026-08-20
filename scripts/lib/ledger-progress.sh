#!/usr/bin/env bash
# ============================================================================
# F20 — THE PROGRESS SIGNAL, MEASURED WHERE THE WORK ACTUALLY LANDS.
# ----------------------------------------------------------------------------
# Sourced by `scripts/foundation-loop.sh`. Never executed directly.
#
# ── WHAT WENT WRONG, MEASURED RATHER THAN ARGUED ────────────────────────────
# KILL SWITCH 4 (no-progress) hashed the SHARED TREE's working copy of
# `docs/foundation/RELAY.md`. A session does not write that file: it works in
# its own `git worktree` and lands its ledger row on `origin/main` through a
# merged PR. The shared tree picks that up only via the launch-time `--ff-only`
# sync, which runs BEFORE the session and therefore cannot see anything the
# session goes on to do.
#
# So `ledger_after` and `ledger_before` were sampled from a file the session
# had no way to change, and the switch was a LAGGING indicator of a sync rather
# than a measurement of progress.
#
# ⚠️ IT FIRED FALSELY ON 2026-08-19 AND ENDED A PRODUCTIVE NIGHT. Run
# `20260818-232127-b1`:
#
#     session   launch (sample)   shared-tree commit   ledger hash
#     run03     06:52:02Z         febfdcfd             c631a099
#     run04     09:11:51Z         febfdcfd             c631a099   <- identical
#
# At BOTH sample moments `origin/main` genuinely was `febfdcfd`, so the sync was
# not broken — it correctly did nothing. Session 04 then merged #740 at
# 10:00:35Z and #741/#742 at ~12:07Z, all of them carrying RELAY rows, and
# closed at 12:44:53Z. **Every one of those merges landed AFTER the last sample
# the switch would ever take.** It halted the run on NO-PROGRESS while three PRs
# with ledger rows sat on `main`, 14 commits ahead of the file it was reading.
#
# ⚠️ THE DEFECT IS THIS HOUSE'S OWN NAMED CLASS: two distinguishable states
# collapsed into one observation. "The ledger did not move" and "I am reading a
# file the ledger does not move in" produced byte-identical output, and only one
# of them is a finding.
#
# ── THE REPAIR ──────────────────────────────────────────────────────────────
# Measure the ledger ON `origin/main`, after a fresh fetch, at BOTH ends of the
# session. Then the two samples BRACKET the session instead of trailing it, and
# a difference means precisely what the switch has always claimed it means: a
# ledger row landed while this session was running.
#
# ⚠️ THIS IS NOT A LOOSENING, AND THAT IS CHECKABLE RATHER THAN ASSERTED. The
# switch exists to catch "busy but landing nothing" (the runner's own words).
# The old sample could not observe the judged session AT ALL; the new one
# observes exactly it. A genuinely spinning session still trips it — see the
# gate's `still HALTS` arms — and the contract it enforces is untouched: an item
# is not finished until its ledger row lands.
#
# ── THE THIRD STATE, AND WHY IT NEVER HALTS ON ITS FIRST APPEARANCE ─────────
# A fetch can fail, `origin/main` can be missing, the ledger can be absent from
# `main`. None of those is evidence about the session, so none of them may be
# reported as NO-PROGRESS — that is the collapse this file exists to undo, and
# re-committing it in the fix would be its own joke.
#
# `2` = CANNOT TELL, distinct from `0` = measured. The caller is expected to
# treat a cannot-tell as breaking the streak, LOUDLY, and to halt only if it
# PERSISTS — the debounce shape, because a degraded service answers
# intermittently and one blind sample is not an outage.
#
# ⚠️ EVERY VARIABLE IS INITIALISED BEFORE USE. The runner is `set -u`, and
# F14-a's `runs_api_mode_banner` aborted a whole script by reading two globals
# nothing assigned — after its positive control, so it printed no verdict at
# all. That is cheaper to copy than to relearn.
# ============================================================================

# ledger_progress_hash <ledger-path-relative-to-repo-root>
#
#   stdout : a 64-char sha256 of the ledger as it exists on `origin/main`
#   exit 0 : measured
#
#   stdout : CANNOT-TELL:<reason>
#   exit 2 : could not measure — NEVER to be read as "unchanged"
#
# ⚠️ THE CALLER BRANCHES ON THE EXIT CODE, NOT ON THE STRING. A guard that
# distinguishes its states by parsing stdout is one typo away from treating
# `CANNOT-TELL:fetch-failed` as a hash that simply never matches — which
# presents as permanent progress, the exact inverse of the bug being fixed.
ledger_progress_hash() {
  local ledger="${1:-}"
  local blob_hash=""

  if [ -z "$ledger" ]; then
    printf 'CANNOT-TELL:no-ledger-path\n'
    return 2
  fi

  # `origin/main` is a remote-tracking ref; in a tree nobody commits to, a fetch
  # is the ONLY thing that advances it. Failing to fetch and then reading the
  # stale ref would reproduce the original defect one layer out.
  if ! git fetch --quiet origin 2>/dev/null; then
    printf 'CANNOT-TELL:fetch-failed\n'
    return 2
  fi

  if ! git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then
    printf 'CANNOT-TELL:no-origin-main\n'
    return 2
  fi

  # Existence is asked separately so that "the ledger is not on main" is
  # distinguishable from "the ledger is empty" — an empty file hashes fine, and
  # conflating the two would put a real hash on a missing contract.
  if ! git cat-file -e "origin/main:$ledger" 2>/dev/null; then
    printf 'CANNOT-TELL:ledger-absent-on-main\n'
    return 2
  fi

  # Piped, never through a variable: `$(git show …)` strips trailing newlines,
  # so a hash taken that way is not the hash of the blob. It would still be
  # deterministic and would still work — which is precisely why it would never
  # be noticed, and why the byte-faithful form is used instead.
  #
  # ⚠️ BUT A PIPE DISCARDS THE LEFT SIDE'S EXIT CODE, AND THAT CONVERTS A
  # FAILURE INTO A STABLE, PLAUSIBLE VALUE. On failure `git show` writes
  # nothing, the pipe runs ANYWAY, and `sha256sum` hashes EMPTY STDIN to the
  # constant `e3b0c442…855`. That is 64 hex characters — so the `-z` guard
  # below cannot see it — and it is IDENTICAL ON EVERY BROKEN READ, so two
  # consecutive blind sessions compare EQUAL and the no-progress switch fires.
  # This function exists to prevent exactly that false halt, so failing this
  # way would make it the cause of the bug it was written to cure.
  #
  # `git cat-file -e` above proves the blob exists, which is what makes this
  # near-unreachable — a corrupt object, a gc racing the read, a truncated
  # pack. Near-unreachable is not unreachable, and the cost of being wrong is a
  # dark loop nobody can explain.
  #
  # `pipefail` is set INSIDE the substitution, not at file scope: this is a
  # sourced library and it must not mutate the shell options of whatever
  # sources it. It also means the guard holds no matter how the caller is
  # configured, rather than depending on the caller for its correctness.
  local pipe_status=0
  blob_hash="$(set -o pipefail; git show "origin/main:$ledger" 2>/dev/null | sha256sum | cut -d' ' -f1)" || pipe_status=$?

  if [ "$pipe_status" -ne 0 ]; then
    printf 'CANNOT-TELL:show-failed\n'
    return 2
  fi

  # ⚠️ COMPARING AGAINST THE EMPTY-STDIN DIGEST WAS CONSIDERED AS A SECOND NET
  # AND IS DELIBERATELY NOT DONE — it cannot tell "we hashed nothing" from "the
  # ledger is legitimately a zero-byte file", and the existence check above is
  # separate PRECISELY so those two stay distinguishable (see its comment: "an
  # empty file hashes fine"). `pipefail` is also STRICTLY STRONGER: it catches a
  # truncated read that emitted some bytes before failing, which produces a
  # WRONG hash rather than the empty one, and no constant comparison can see
  # that at all.
  if [ -z "$blob_hash" ]; then
    printf 'CANNOT-TELL:hash-empty\n'
    return 2
  fi

  printf '%s\n' "$blob_hash"
  return 0
}
