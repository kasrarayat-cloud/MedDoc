#!/usr/bin/env bash
# ============================================================================
# THE §2.5 DECLARATION GATE — sourced by every path that changes production.
# ----------------------------------------------------------------------------
# One implementation, two callers: `scripts/deploy-prod.sh` (reversible — a
# rollback exists) and `scripts/run-ruled-mutation.sh` (irreversible — an
# append-only table has no inverse). A second copy would drift from the first.
#
# ⚠️ THE FILE IS NOT THE POINT. THE ORDER IS. A post-hoc check is unfalsifiable:
# every number has a story available to it. A declaration that exists BEFORE the
# evidence has exactly one correct answer, fixed while the outcome was unknown.
#
# ⚠️ AND "EXISTS" IS NOT "EXISTED BEFORE" — WHICH IS THE WHOLE REASON THIS FILE
# EXISTS. `deploy-prod.sh` asserted `[ -f "$DECL" ]`, and a file can be written
# one second before the act. The 2026-08-12 B7 step 3c backfill is the reference
# case: 175 irreversible rows landed at 22:50:16Z and the declaration's ONLY
# commit is 22:52:13Z — one minute fifty-seven seconds LATER. Every declared
# number matched, 8 of 8. Nothing suggests bad faith. **And the record still
# cannot tell an honest declaration from one composed after the outcome was
# known** — which is exactly the property §2.5 was supposed to buy.
#
# So provenance is RECORDED ALWAYS and ENFORCED where the act cannot be undone:
#
#   present  — the file must exist. Provenance printed; uncommitted is a loud
#              warning. Used by DEPLOY, which a rollback can answer.
#   strict   — the file must be TRACKED, UNMODIFIED, and COMMITTED. Its commit
#              timestamp then provably precedes the act, because the act has not
#              happened yet. Used by RULED MUTATIONS, which nothing can answer.
#
# ⚠️ THE ASYMMETRY IS DELIBERATE AND IT IS RULING #96(b)'s LOGIC: strictness is
# proportional to reversibility. Making the deploy path strict today would refuse
# every deploy whose author writes the declaration and commits it in the same PR
# — a real habit, and breaking it would halt the programme to fix a weaker case.
# ============================================================================

# ============================================================================
# F10 — THE CARRY-FORWARD RESOLVER. The circularity, broken by MEASUREMENT.
# ----------------------------------------------------------------------------
# ⚠️ THE BUG THIS FIXES IS STRUCTURAL, NOT CARELESS. `deploy-prod.sh` derived the
# declaration path from `git rev-parse --short HEAD` of the deploying tree. This
# programme's normal cadence moves `main` between a feature merge and its deploy
# — a citation PR, a ledger row, a docs fix. So:
#
#     feature merges as X   ->  you write <date>-X.md
#     canon says nothing reaches `main` outside a PR
#     the PR carrying the declaration merges as Y   ->  HEAD is now Y
#     the gate now wants <date>-Y.md, which does not exist
#
# ⚠️ AND IT DOES NOT CONVERGE: the commit that would CARRY the declaration is
# itself what MOVES HEAD. No number of extra PR cycles reaches a fixed point.
# Session 03 hit it; session 05 deployed with a declaration `tracked: no` and
# said so loudly. Ruling #121 set the acceptance criteria.
#
# THE SHAPE, and why it satisfies all three of #121's criteria:
#
#   A declaration names a COMMIT. The gate accepts it for a DIFFERENT HEAD only
#   when it can PROVE the two are the same program:
#
#     (i)  the named commit is an ANCESTOR of HEAD, and
#     (ii) the diff between them touches ZERO runtime paths.
#
#   (1) THE GATE DOES NOT WEAKEN. `present` is untouched — ruling #96(b) stands
#       and this does NOT flip it to `strict`. The judgement still covers the
#       exact tree shipped, because (ii) proves the shipped tree is
#       runtime-identical to the declared one. ⚠️ AND THE NEW DOOR IS THE
#       STRICTER ONE: a carry-forward is required to be TRACKED, UNMODIFIED and
#       COMMITTED, because by construction there WAS a commit to ride. So the
#       resolver can only ever tighten the record, never loosen it.
#
#   (2) THE CIRCULARITY BREAKS. Write <date>-X.md, land it in the docs PR that
#       becomes Y, deploy at HEAD=Y. The gate resolves X, proves X..Y is
#       docs-only, and the declaration is COMMITTED BEFORE the act. Fixed point
#       reached in one PR, and the interim "written to the shared tree,
#       uncommitted" exception retires with it.
#
#   (3) FALSIFIABILITY DOES NOT NARROW. This cannot name "whatever ships". It
#       REFUSES when the named commit is not an ancestor, when ANY runtime file
#       moved in between, when the name is a sha that does not exist, and when
#       two candidates are equally near (ambiguous). Every one of those arms is
#       proved in `scripts/tests/declaration-resolve-proof.sh`, in BOTH
#       directions — the `retire-branch.sh` lesson: 9 of 9 refusals and a false
#       green on the happy path is a half-proven guard.
#
# ⚠️ THE NON-RUNTIME SET IS AN ALLOWLIST AND IT IS FAIL-CLOSED. A path is
# non-runtime ONLY if it matches here; everything else — apps/, packages/,
# scripts/, .github/, package.json, a Dockerfile, a .md nested inside an app —
# counts as RUNTIME and defeats a carry-forward. Measured before it was written
# rather than assumed: no Dockerfile COPY/ADDs `docs/`, and nothing under
# `apps/` or `packages/` reads `docs/` outside dev and eval scripts.
DECLARATION_NONRUNTIME_RE='^(docs/|[^/]+\.md$)'

# declaration_resolve <decl_dir>
#   Sets DECLARATION_PATH and DECLARATION_MODE on success.
#   0 = resolved   1 = nothing covers the shipped tree   2 = AMBIGUOUS
declaration_resolve() {
  local dir="${1:?}"
  DECLARATION_PATH=""; DECLARATION_MODE=""

  local head head_short
  head=$(git rev-parse --verify HEAD 2>/dev/null) || {
    echo "🔴 REFUSING — cannot read HEAD. This is not a git tree, or git is broken."
    echo "   Nothing has been changed."
    return 1
  }
  head_short=$(git rev-parse --short HEAD)

  echo "=== DECLARATION RESOLUTION (§2.5, F10) ==="
  echo "shipping    : $head_short  ($head)"

  local exact="" exact_dup="" best="" best_dist="" best_total="" best_sha="" ambiguous="no" ambig_with=""
  local f base shapart cand dist total runtime

  for f in "$dir"/*.md; do
    [ -e "$f" ] || continue
    base=$(basename "$f" .md)
    # the sha is the text after the LAST dash. `README.md` and any prose name
    # fail the hex test below and are skipped — they are not declarations.
    shapart="${base##*-}"
    case "$shapart" in
      ""|*[!0-9a-fA-F]*) continue ;;
    esac
    [ "${#shapart}" -ge 7 ] || continue

    # ⚠️ RESOLVED THROUGH GIT, NEVER PARSED AND TRUSTED. A fabricated sha, a
    # sha from another repository, or an AMBIGUOUS abbreviation all fail here
    # rather than being padded, completed or guessed at. "Full-looking is not
    # full" — and neither is "hex-looking is a commit".
    cand=$(git rev-parse --verify --quiet "${shapart}^{commit}" 2>/dev/null) || continue

    # ⚠️ TWO FILES CAN NAME THE SAME COMMIT. Matching is by SHA and the date
    # prefix is decoration, so `20260816-abc.md` and `20260817-abc.md` BOTH
    # match — a deploy that crosses midnight and gets a second declaration
    # written. The pre-F10 code could not hit this because the date was part of
    # the derived filename. Taking the last one silently would be the exact
    # defect the carry-forward tie already refuses, so it is refused too.
    if [ "$cand" = "$head" ]; then
      if [ -n "$exact" ]; then exact_dup="$f"; else exact="$f"; fi
      continue
    fi

    git merge-base --is-ancestor "$cand" "$head" 2>/dev/null || continue

    total=$(git diff --name-only "$cand" "$head" -- | wc -l)
    runtime=$(git diff --name-only "$cand" "$head" -- | grep -Ecv "$DECLARATION_NONRUNTIME_RE" || true)
    [ "$runtime" -eq 0 ] || continue

    dist=$(git rev-list --count "${cand}..${head}" 2>/dev/null) || continue
    if [ -z "$best" ] || [ "$dist" -lt "$best_dist" ]; then
      best="$f"; best_dist="$dist"; best_total="$total"; best_sha="$cand"
      ambiguous="no"; ambig_with=""
    elif [ "$dist" -eq "$best_dist" ]; then
      ambiguous="yes"; ambig_with="$f"
    fi
  done

  if [ -n "$exact_dup" ]; then
    echo
    echo "🔴 REFUSING — AT LEAST TWO declarations name THIS commit:"
    echo "     $exact"
    echo "     $exact_dup"
    echo "   Matching is by SHA; the date prefix is decoration. Nothing here can"
    echo "   say which one was written about this deploy, and judging against the"
    echo "   wrong one looks exactly like judging against the right one."
    echo "   Keep one and re-run. Nothing has been changed."
    return 2
  fi

  # ── the EXACT match is the pre-F10 behaviour, unchanged and still `present` ──
  if [ -n "$exact" ]; then
    echo "declared    : $head_short — the deploying tree itself"
    echo "resolution  : EXACT. Pre-F10 behaviour, unchanged; mode stays 'present'"
    echo "              per ruling #96(b) — strictness proportional to reversibility."
    DECLARATION_PATH="$exact"; DECLARATION_MODE="present"
    echo
    return 0
  fi

  if [ "$ambiguous" = "yes" ]; then
    echo
    # ⚠️ "AT LEAST TWO", NOT "TWO". Three equidistant candidates would print two
    # of them, and a refusal message that asserts a count it did not measure is
    # the same defect as a check whose title is wider than what it computes.
    # Both shown are real; there may be more.
    echo "🔴 REFUSING — AT LEAST TWO declarations are equally near the shipped tree:"
    echo "     $best"
    echo "     $ambig_with"
    echo "   Both are ancestors of HEAD at distance $best_dist with no runtime change,"
    echo "   so nothing here can say WHICH ONE was written about this deploy."
    echo "   Judging against the wrong one would look exactly like judging against"
    echo "   the right one. Write a declaration naming $head_short and re-run."
    echo "   Nothing has been changed."
    return 2
  fi

  if [ -n "$best" ]; then
    local declared_short; declared_short=$(git rev-parse --short "$best_sha")
    echo "declared    : $declared_short — an ANCESTOR of the shipped tree, $best_dist commit(s) back"
    echo "range       : ${declared_short}..${head_short} — $best_total file(s) changed, 0 of them runtime"
    if [ "$best_total" -eq 0 ]; then
      echo "control     : the two commits have IDENTICAL TREES, so this is not a"
      echo "              measurement over an empty set — it is the strongest case there is."
    else
      echo "control     : the range is NON-EMPTY ($best_total file(s)) — an empty runtime"
      echo "              diff over an empty range would prove nothing, so this is a"
      echo "              real measurement rather than a vacuous one."
    fi
    echo "resolution  : CARRY-FORWARD. The declaration is about a different COMMIT and"
    echo "              provably about the SAME PROGRAM. ⚠️ Mode is 'strict' here, not"
    echo "              'present': a carry-forward means a commit existed to ride, so"
    echo "              the declaration must be COMMITTED. This tightens the record."
    DECLARATION_PATH="$best"; DECLARATION_MODE="strict"
    echo
    return 0
  fi

  echo
  echo "🔴 REFUSING — no delta declaration covers the tree you are shipping."
  echo
  echo "   expected: $dir/$(date -u +%Y%m%d)-${head_short}.md"
  echo
  echo "   §2.5 requires the expected delta to be written down BEFORE the act."
  echo "   Afterwards it is unfalsifiable — every number has a story available"
  echo "   to it. Write it, then re-run. It must state:"
  echo "     · the BASELINE, captured before anything changes"
  echo "     · what MUST change"
  echo "     · what MUST NOT change — clinical counts are never omitted"
  echo "     · what would make the check FAIL"
  echo
  echo "   A declaration naming an ANCESTOR of this commit is also accepted, but"
  echo "   ONLY when nothing runtime moved in between — that is what makes it a"
  echo "   statement about the tree being shipped rather than about a different"
  echo "   one. If you have such a file and it was not taken, the range carries a"
  echo "   runtime change. Read it:"
  echo "     git diff --name-only <declared-sha> ${head_short}"
  echo
  echo "   Nothing has been changed."
  return 1
}

# declaration_gate <path> <present|strict> <label>
#   0 = gate passed (provenance printed)   1 = REFUSED
declaration_gate() {
  local decl="${1:?}" mode="${2:?}" label="${3:-declaration}"

  echo "=== ${label^^} GATE (§2.5, enforced) ==="
  if [ ! -f "$decl" ]; then
    echo "🔴 REFUSING — no delta declaration."
    echo
    echo "   expected: $decl"
    echo
    echo "   §2.5 requires the expected delta to be written down BEFORE the act."
    echo "   Afterwards it is unfalsifiable — every number has a story available"
    echo "   to it. Write it, then re-run. It must state:"
    echo "     · the BASELINE, captured before anything changes"
    echo "     · what MUST change"
    echo "     · what MUST NOT change — clinical counts are never omitted"
    echo "     · what would make the check FAIL"
    echo
    echo "   Nothing has been changed."
    return 1
  fi

  # ── provenance, always measured, never assumed ────────────────────────────
  local sha256 tracked="no" modified="n/a" csha="-" cdate="-"
  sha256=$(sha256sum "$decl" 2>/dev/null | cut -c1-16)
  if git ls-files --error-unmatch "$decl" >/dev/null 2>&1; then
    tracked="yes"
    if git diff --quiet HEAD -- "$decl" 2>/dev/null; then modified="no"; else modified="YES"; fi
    csha=$(git log -1 --format=%h -- "$decl" 2>/dev/null)
    cdate=$(git log -1 --format=%cI -- "$decl" 2>/dev/null)
  fi

  echo "declaration : $decl"
  echo "sha256      : $sha256…"
  echo "tracked     : $tracked   modified-vs-HEAD: $modified"
  echo "committed   : ${csha:--}  at ${cdate:--}"

  if [ "$mode" = "strict" ]; then
    if [ "$tracked" != "yes" ] || [ -z "$csha" ]; then
      echo
      echo "🔴 REFUSING — the declaration is NOT COMMITTED, and this act cannot be undone."
      echo "   A file on disk proves nothing about ORDER: it can be written one second"
      echo "   before the act, and afterwards nothing distinguishes that from one"
      echo "   composed once the outcome was known."
      echo "   Commit it first. Its commit timestamp is then the proof, because this"
      echo "   act has not happened yet."
      echo "   Nothing has been changed."
      return 1
    fi
    if [ "$modified" = "YES" ]; then
      echo
      echo "🔴 REFUSING — the declaration is committed but MODIFIED in the working tree."
      echo "   The committed text and the text you are about to act on differ, so the"
      echo "   commit timestamp certifies something other than what is printed here."
      echo "   Commit the change, or revert it. Nothing has been changed."
      return 1
    fi
  elif [ "$tracked" != "yes" ] || [ "$modified" = "YES" ]; then
    echo
    echo "⚠️  the declaration is not committed as it stands. This is allowed here"
    echo "    because a deploy is reversible — but the ORDER is then asserted by"
    echo "    this transcript alone, not provable from git. Commit it with the"
    echo "    change so the record can be checked later."
  fi

  echo "─────────────────────────────────────────────────────────────────────"
  cat "$decl"
  echo "─────────────────────────────────────────────────────────────────────"
  echo
  return 0
}
