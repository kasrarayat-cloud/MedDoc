#!/usr/bin/env bash
# ============================================================================
# citation-gate.sh — A DEPLOY REFUSES A COMMIT ITS OWN GATE HAS NOT SEEN.
# ----------------------------------------------------------------------------
# ⚠️ THE INCIDENT, MEASURED 2026-08-20 AND OWNER-RULED THE SAME MORNING:
#
#     06:14:42Z   `e2e` created on 7c42d2d7
#     06:15:13Z   `secrets-scan` finishes — THE ONLY CHECK THAT HAD
#     06:15:17Z   deploy-prod.sh STARTS
#     06:19:26Z   `a11y-ci` finishes
#     06:22:33Z   `CI` finishes
#     06:52:02Z   `e2e` finishes
#
# All four passed in the end, so nothing unverified survives in production.
# **That is luck wearing a process's clothes.** The deploy was taken on evidence
# that did not yet exist, and had `e2e` gone red the tree would already have been
# live for thirty-seven minutes.
#
# This is §2.5's own argument arriving one step earlier. The declaration gate
# makes the deploy state its expected delta BEFORE the act; this makes the deploy
# hold a COMPLETE CITATION before the act. Neither is a check you can write
# afterwards and have it mean anything.
#
# ── THE GATE IS A CALL, NOT A NEW MECHANISM ─────────────────────────────────
# `scripts/gh-runs.sh` is the only sanctioned door to "what ran on this SHA?",
# and it already carries every refusal this gate needs:
#
#   · a sha under 40 characters is REFUSED (an abbreviation matches NOTHING on
#     the runs routes — exit 0, no rows, a false all-clear)
#   · a 40-hex sha that is not a real commit is REFUSED as CANNOT TELL, because
#     a fabricated sha and a real sha with pending runs return the same nothing
#   · a ZERO-run commit is NOT CITED — vacuous, not clean
#   · the runs API is POSITIVE-CONTROLLED before any zero from it is believed
#   · a truncated payload is refused rather than answered from a subset
#
# Re-implementing any of that here would be a second copy that drifts from the
# first the day either is fixed. So this file decides NOTHING about run state —
# it maps four exit codes onto "deploy" or "refuse", and refuses everything that
# is not an unambiguous 0.
#
#   0 = CITED        every required run concluded success   -> PROCEED
#   1 = PENDING      at least one run not completed         -> REFUSE
#   2 = CANNOT TELL  blind instrument, no runs, timeout     -> REFUSE (fail-closed)
#   3 = FAILED       a run concluded non-success, TERMINAL  -> REFUSE
#
# ⚠️ FAIL-CLOSED ON 2 IS THE LOAD-BEARING ARM. A runs-API outage is not a licence
# to ship. A broken instrument and a green commit produce the same silence, and
# this house has paid for that confusion five times over under its own name.
#
# ── ON "TAKE BOTH VIEWS" ────────────────────────────────────────────────────
# The push and merge doors take TWO views (`--commit` and `--branch`) because
# `--commit` under-reports in the propagation window right after a push, so a
# zero from it is not a fact until `--branch` agrees. That rule's SUBSTANCE is
# what matters here and it is discharged, by a different and stricter route: this
# gate never believes a zero at all. `gh-runs.sh cited` returns 2 = CANNOT TELL
# on zero rows, and 2 refuses. A propagation-window zero therefore stops the
# deploy rather than passing it.
#
# ⚠️ AND THE BRANCH VIEW IS DELIBERATELY NOT A SECOND ARM HERE — stated so the
# absence reads as a decision rather than an oversight. `--branch main` counts
# non-completed runs on main from ANY commit, including somebody else's merge
# that has nothing to do with the tree being deployed. As a gate arm it would
# refuse deploys for reasons unrelated to the deployed code, which is a different
# check wearing this one's name. The commit view is also the one that carries
# `runs-api.sh`'s check-suites coverage control; the branch view's count is a
# FLOOR in fallback mode and is documented as such in `lib/inflight.sh`.
#
# ── THE OVERRIDE IS A DECLARATION, NEVER A FLAG ─────────────────────────────
# An incident may need to ship past a broken gate. It may not need to do so
# silently. The reason is prose, validated by the SAME `inflight_declaration_ok`
# the push and merge doors use — a bare `1`/`true`/`yes`, or anything under 12
# characters, is refused, because a declaration wearing a token's clothes is a
# bypass and an audit trail's "why" is somebody's words or nothing.
#
# ⚠️ IT IS A COMMAND-LINE FLAG AND NOT ONLY AN ENV VAR, AND THAT IS THE WHOLE
# REASON IT IS SHAPED THIS WAY. `VAR=... cmd` is REFUSED to the unattended loop
# by `.claude/settings.json`, and the loop is the only deploy actor. An
# env-only hatch would be inert in exactly the sessions that would ever need it —
# the same defect `gh-runs.sh --force-fallback` was added to fix. The env var is
# honoured too, for a supervised operator's muscle memory; the flag wins.
#
# ── USAGE ───────────────────────────────────────────────────────────────────
#   citation_gate <full-40-char-sha> <mode> <override-prose>
#     mode      : refuse | wait
#     override  : prose, or empty
#   0 = proceed · 1 = REFUSE (caller must leave production untouched)
# ============================================================================

# ⚠️ ANCHORED TO THIS FILE, NOT TO THE CALLER'S CWD. A lib that silently resolved
# a DIFFERENT tree's `gh-runs.sh` would answer perfectly about the wrong
# repository — MASTER's own `cd`-decides-which-copy-you-run trap, which cost this
# programme a `218 failed | 177 passed` measurement against a true 16/301.
_CITATION_GATE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"

# ⚠️ SOURCED FAIL-CLOSED. The declaration validator is shared with the push hook
# and the merge wrapper; a second copy of it here would be a second definition of
# what counts as a reason. If it cannot be reached, the override cannot be
# validated, so the override is not available — the gate still works, it simply
# cannot be waived.
if [ -n "${_CITATION_GATE_LIB_DIR:-}" ] && [ -r "$_CITATION_GATE_LIB_DIR/inflight.sh" ]; then
  # shellcheck source=inflight.sh
  . "$_CITATION_GATE_LIB_DIR/inflight.sh"
fi

# The one instrument. Resolved, never guessed.
citation_gate_runner() {
  printf '%s' "${_CITATION_GATE_LIB_DIR}/../gh-runs.sh"
}

# citation_gate <sha> <mode> <override>
citation_gate() {
  local sha="${1:-}" mode="${2:-refuse}" override="${3:-}"
  local runner rc

  runner="$(citation_gate_runner)"

  echo "=== 0a. THE CITATION GATE — has this commit's own gate seen it? ==="
  echo "   commit: $sha"

  # ── the override, decided BEFORE any network call ─────────────────────────
  if [ -n "$override" ]; then
    if ! command -v inflight_declaration_ok >/dev/null 2>&1; then
      echo "🔴 REFUSING TO DEPLOY — an override was offered and it cannot be validated."
      echo "   scripts/lib/inflight.sh is missing or unreadable, so the declaration"
      echo "   validator that the push and merge doors use is not reachable. A"
      echo "   waiver nothing can check is not a waiver."
      return 1
    fi
    if ! inflight_declaration_ok "$override"; then
      echo "🔴 REFUSING TO DEPLOY — the citation override is not a declaration."
      echo "   Use: --declare-citation-override 'why this deploy ships uncited'"
      return 1
    fi
    echo "   ⚠️ CITATION GATE OVERRIDDEN BY DECLARATION:"
    echo "      $override"
    echo "   The gate is NOT being skipped silently. It is still probed below and"
    echo "   whatever it says is in this log — the deploy simply does not stop on it."
    # ⚠️ PROBED ANYWAY, AND DELIBERATELY IN THE FAST FORM. The record of WHAT was
    # overridden is the entire product of an override; a waiver with no state
    # attached is indistinguishable from never having looked. `cited` is used
    # rather than `wait` because an override is reached during an incident and a
    # gate that hangs for an hour after being waived is a gate that gets killed.
    if [ -x "$runner" ] || [ -r "$runner" ]; then
      bash "$runner" cited "$sha"; rc=$?
      echo "   (state at the moment of override: gh-runs cited -> exit $rc)"
    else
      echo "   (state at the moment of override: UNKNOWN — $runner is not readable)"
    fi
    return 0
  fi

  # ── fail-closed on a missing instrument ───────────────────────────────────
  if [ ! -r "$runner" ]; then
    echo "🔴 REFUSING TO DEPLOY — $runner is missing or unreadable."
    echo "   A deploy that silently skipped its own citation gate is exactly the"
    echo "   state this gate exists to make impossible. Production is untouched."
    return 1
  fi

  case "$mode" in
    refuse|wait) ;;
    *)
      echo "🔴 REFUSING TO DEPLOY — unknown citation-gate mode '$mode'."
      return 1 ;;
  esac

  if [ "$mode" = "wait" ]; then
    echo "   mode: WAIT — polling until every run on this commit concludes."
    bash "$runner" wait "$sha"; rc=$?
  else
    echo "   mode: REFUSE — one decisive read, no polling."
    bash "$runner" cited "$sha"; rc=$?
  fi

  case "$rc" in
    0)
      echo "   🟢 CITED — every run on this commit concluded success."
      # ⚠️ DESCRIPTIVE, AND IT RUNS *AFTER* THE DECISION SO IT CANNOT INFLUENCE
      # IT. The deploy log is the record; a citation with no run names in it is a
      # claim. If this call fails, nothing is at risk — the verdict is already
      # made — so its failure is reported and not acted on.
      if ! bash "$runner" status "$sha"; then
        echo "   (the per-run listing could not be read; the verdict above stands"
        echo "    on its own — it was taken from a separate, successful read.)"
      fi
      return 0 ;;
    1)
      echo "🔴 REFUSING TO DEPLOY — the gate has NOT finished looking at this commit."
      echo "   At least one required run is still in flight. Deploying now would"
      echo "   take the tree live on evidence that does not yet exist."
      echo
      echo "   Wait for it, then deploy:"
      echo "      bash scripts/gh-runs.sh wait $sha"
      echo "   or run the deploy itself in waiting mode:"
      echo "      bash scripts/deploy-prod.sh --wait-for-citation"
      echo "   Nothing has been built, migrated or recreated. Production is untouched."
      return 1 ;;
    2)
      echo "🔴 REFUSING TO DEPLOY — CANNOT TELL whether this commit is cited."
      echo "   No runs, a blind instrument, a fabricated sha, or a timeout — all"
      echo "   of them produce this, and none of them is an all-clear. A"
      echo "   runs-API outage is not a licence to ship."
      echo
      echo "   If this is a genuine incident and the deploy must go anyway, say so:"
      echo "      bash scripts/deploy-prod.sh --declare-citation-override '<why>'"
      echo "   Nothing has been built, migrated or recreated. Production is untouched."
      return 1 ;;
    3)
      echo "🔴 REFUSING TO DEPLOY — a required run on this commit CONCLUDED NON-SUCCESS."
      echo "   This is TERMINAL: the sha can never reach a full citation as it"
      echo "   stands. Push a fix, or re-run the failed job AND SAY WHY in the"
      echo "   ledger row — canon forbids re-run-and-hope."
      echo "   Nothing has been built, migrated or recreated. Production is untouched."
      return 1 ;;
    *)
      # ⚠️ THE `*)` ARM IS NOT DEFENSIVE PADDING. `gh-runs.sh` grew its 2 and its
      # 3 one incident at a time, each time because two states had been collapsed
      # into one code. An unmapped code here must refuse, or the next state it
      # learns to report arrives as a silent PROCEED.
      echo "🔴 REFUSING TO DEPLOY — gh-runs.sh returned an unmapped exit code $rc."
      echo "   An exit code this gate does not understand is a cannot-tell."
      echo "   Nothing has been built, migrated or recreated. Production is untouched."
      return 1 ;;
  esac
}
