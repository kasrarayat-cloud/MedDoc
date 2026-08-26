#!/usr/bin/env bash
# ============================================================================
# REPORT-THROUGHPUT — the counterweight line for the morning report.
# ----------------------------------------------------------------------------
# Ordered 2026-08-26. An audit that week found the loop scoring perfectly on
# every cadence metric it had — 72.2% wall-clock utilisation, 105 of 109
# sessions rc=0 — while PRODUCT throughput halved: 2 of the last 25 merges
# touched product source, and both were held from deployment. A loop that is
# 100% awake writing only rules about itself is indistinguishable, on those
# metrics, from one shipping the product.
#
# ⚠️ COMMIT COUNTS MISLEAD, AND THAT IS THE WHOLE REASON THIS IS A SCRIPT.
# "65 commits undeployed" says nothing about whether any RUNTIME changed. The
# undeployed figure below is a FILE diff over non-test app/package sources
# between the deployed commit and HEAD, not a commit count.
#
# READ-ONLY. Exit 0 always — this reports, it does not gate. A metric that can
# block is a metric people learn to game.
# ============================================================================
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 0

WINDOW="${THROUGHPUT_WINDOW:-25}"

is_product() {  # $1 = merge sha
  git diff-tree --no-commit-id --name-only -r -m --first-parent "$1" 2>/dev/null \
    | grep -E '^(apps|packages)/' \
    | grep -vE '__tests__|/tests/|\.test\.|\.spec\.' | head -1
}

prod=0; total=0; prod_prs=""
while read -r sha rest; do
  [ -z "$sha" ] && continue
  total=$((total+1))
  if [ -n "$(is_product "$sha")" ]; then
    prod=$((prod+1))
    prod_prs="$prod_prs $(printf '%s' "$rest" | grep -oE '#[0-9]+' | head -1)"
  fi
done < <(git log --merges --first-parent -"$WINDOW" --format='%H %s' main 2>/dev/null)

echo "### THROUGHPUT — product vs meta"
if [ "$total" -eq 0 ]; then
  echo "  CANNOT TELL — no merges found in the window (is this a fresh clone?)"
else
  pct=$(( prod * 100 / total ))
  echo "  product merges: ${prod} of last ${total} first-parent merges (${pct}%)${prod_prs:+ —${prod_prs}}"
  echo "  classifier: touches apps/ or packages/, excluding __tests__ /tests/ .test. .spec."
fi

# ── deploys in the window ───────────────────────────────────────────────────
if [ -d docs/deploy-logs ]; then
  n=$(find docs/deploy-logs -name 'deploy-*.log' -newermt '4 days ago' 2>/dev/null | wc -l | tr -d ' ')
  last=$(ls -1t docs/deploy-logs/deploy-*.log 2>/dev/null | head -1)
  echo "  deploys, last 4 days: ${n}${last:+ · most recent $(basename "$last")}"
else
  echo "  deploys: CANNOT TELL — docs/deploy-logs absent (it is gitignored; only present on the host)"
fi

# ── undeployed RUNTIME, by file not by commit ───────────────────────────────
DEPLOYED="${DEPLOYED_SHA:-}"
if [ -z "$DEPLOYED" ] && [ -d docs/foundation/deploys ]; then
  # ⚠️ TWO TRAPS, BOTH HIT ON THE FIRST RUN OF THIS SCRIPT, BOTH LEFT NAMED:
  #  1. `grep -oE '[0-9a-f]{8,40}'` matched the DATE `20260823`, not the sha —
  #     an 8-digit date IS valid hex. The substring trap, fourth sighting in
  #     this repo's canon. Anchor on the field, never on a character class.
  #  2. `ls -1t` sorts by MTIME, which is not chronology: a 08-23 file touched
  #     later outranked a 08-25 one. Sort by NAME; these filenames lead with
  #     an ISO date precisely so that works.
  # -JUDGED supersedes its plain sibling, so it sorts last and wins.
  #  3. AND A THIRD, CAUGHT THE SAME MINUTE: sorting FILENAMES picked
  #     `bd1eeb57` over `61b07e1f` because shas sort lexically and both carry
  #     the same date — but bd1eeb57's own record supersedes itself INTO
  #     61b07e1f. A sha is not a clock. Ask GIT which is latest, not the
  #     filesystem: the deployed commit is the candidate that has every other
  #     candidate as an ancestor.
  cands=$(ls -1 docs/foundation/deploys/[0-9]*-*.md 2>/dev/null \
          | sed -E 's|.*/[0-9]{8}-([0-9a-f]{7,40})(-JUDGED)?\.md|\1|' \
          | grep -xE '[0-9a-f]{7,40}' | sort -u)
  for c in $cands; do
    git cat-file -e "${c}^{commit}" 2>/dev/null || continue
    git merge-base --is-ancestor "$c" HEAD 2>/dev/null || continue
    if [ -z "$DEPLOYED" ] || git merge-base --is-ancestor "$DEPLOYED" "$c" 2>/dev/null; then
      DEPLOYED="$c"
    fi
  done
fi
if [ -n "$DEPLOYED" ] && git cat-file -e "${DEPLOYED}^{commit}" 2>/dev/null; then
  rt=$(git diff --name-only "$DEPLOYED"..HEAD -- apps packages 2>/dev/null \
       | grep -vE '__tests__|/tests/|\.test\.|\.spec\.' | wc -l | tr -d ' ')
  cm=$(git rev-list --count "$DEPLOYED"..HEAD 2>/dev/null)
  echo "  undeployed: ${rt} runtime files across ${cm} commits (vs ${DEPLOYED})"
  [ "$rt" = "0" ] && echo "    -> ${cm} commits but ZERO runtime files: nothing to deploy, despite the commit count"
else
  echo "  undeployed: CANNOT TELL — no deployed SHA resolved (set DEPLOYED_SHA=)"
fi

# ── the interim backup posture, kept visible ────────────────────────────────
echo "  backups: local dailies $( \
  docker exec meddoc-pro-postgres-backup-1 sh -c 'ls -1 /backups/daily 2>/dev/null | wc -l' 2>/dev/null \
  | tr -d '\r' | grep -qE '^[1-9]' && echo 'PRESENT' || echo 'CANNOT TELL') · \
offsite leg DORMANT pending the vendor BAA (owner-parked, not a regression)"
exit 0
