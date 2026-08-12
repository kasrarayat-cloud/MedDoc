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
