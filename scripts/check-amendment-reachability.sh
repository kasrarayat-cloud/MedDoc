#!/usr/bin/env bash
# ============================================================================
# EVERY AMENDMENT TOKEN IN AN ARCHIVE MUST BE REACHABLE FROM THE HEAD.
#   0 = no NEW unreachable amendment   1 = a new one appeared   2 = CANNOT TELL
# ----------------------------------------------------------------------------
# ⚠️ WHY. Ruling #164 item 4. An amended ruling appends into its archive row, so
# the row's opening text stays the ORIGINAL title forever and the head's
# generated title cannot see the final form. On 2026-09-01 a plain regeneration
# of `main` reverted #157's head row to its explicitly-falsified original and
# `grep -c '157(d)'` went 1 -> 0 — the mandated citation route stopped
# resolving on a ruling about what may be printed into a signed document.
#
# The cure is the `<!-- head: … -->` marker, which makes a hand amendment
# durable DATA. This is the guard that says when somebody forgets it.
#
# ⚠️ IT IS A RATCHET, AND THAT IS A MEASURED CONCESSION, NOT A PREFERENCE.
# Ruling #164 asked for "every #N(x) token reachable from the head". Measured on
# `main` the day it was written: 38 amendment tokens in the archives, 29 of them
# ALREADY unreachable. A literal implementation reds `main` on arrival, which is
# canon 73's "measure the population first" — the obvious arm fails the tree it
# is meant to protect. So the pre-existing set is baselined BY NAME below and
# the gate refuses anything NEW. The baseline may only SHRINK.
#
# ⚠️ THE BACKLOG IS REAL AND IS NOT CLOSED BY THIS FILE. Each baselined token is
# an amendment a session cannot find from the head — the same defect that hit
# #157, sitting on 29 other rulings. Clearing it is content archaeology (which
# amendment is each ruling's current form?) and belongs to whoever owns those
# rulings, one at a time, by deleting its line here.
# ============================================================================
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || { echo "🔴 amendment-reach: cannot resolve repo root."; exit 2; }

HEAD_FILE="docs/foundation/RULINGS.md"
ARCH_DIR="docs/foundation/rulings"
[ -r "$HEAD_FILE" ] || { echo "🔴 amendment-reach: $HEAD_FILE unreadable. CANNOT TELL."; exit 2; }
[ -d "$ARCH_DIR" ]  || { echo "🔴 amendment-reach: $ARCH_DIR missing. CANNOT TELL."; exit 2; }

# Pre-existing unreachable amendments, baselined 2026-09-01. SHRINK ONLY.
BASELINE="#93(c) #95(a) #96(a) #97(a) #97(b) #97(c) #97(d) #98(b) #99(a) #103(c) #106(a) #106(b) #106(c) #106(g) #116(b) #117(a) #117(b) #117(e) #131(c) #148(b) #148(c) #148(d) #148(e) #149(a) #149(d) #153(g) #156(d) #157(b) #157(c) "

mapfile -t TOKENS < <(grep -ohE '#[0-9]+\([a-z]\)' "$ARCH_DIR"/*.md 2>/dev/null | sort -u)

# ⚠️ POSITIVE CONTROL BEFORE ANY ZERO IS BELIEVED. A scanner that matches nothing
# reports a perfectly clean tree, and that zero is indistinguishable from health.
if [ "${#TOKENS[@]}" -lt 20 ]; then
  echo "🔴 amendment-reach: only ${#TOKENS[@]} amendment tokens parsed from $ARCH_DIR —"
  echo "   the archives are known to carry dozens. Refusing to read that as clean."
  exit 2
fi

NEW=()
for t in "${TOKENS[@]}"; do
  grep -qF "$t" "$HEAD_FILE" && continue
  case " $BASELINE " in *" $t "*) continue ;; esac
  NEW+=("$t")
done

if [ "${#NEW[@]}" -gt 0 ]; then
  echo "🔴 amendment-reach: ${#NEW[@]} amendment(s) in the archives are NOT reachable"
  echo "   from $HEAD_FILE, and are not in the baseline:"
  printf '     %s\n' "${NEW[@]}"
  echo "   A citation that does not resolve on the head is a ruling a session cannot"
  echo "   find. Add a '<!-- head: … -->' marker to the archive row and regenerate:"
  echo "     python3 scripts/lib/rulings-index.py"
  exit 1
fi

echo "🟢 amendment-reach: ${#TOKENS[@]} amendment tokens · 0 new unreachable · baseline $(echo $BASELINE | wc -w)"
exit 0
