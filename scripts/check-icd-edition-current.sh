#!/usr/bin/env bash
# ============================================================================
# THE SHIPPED ICD-10-CM SET HAS AN EXPIRY DATE. NOTHING WAS WATCHING IT.
# ----------------------------------------------------------------------------
# READ-ONLY.  0 = current · 1 = DUE or STALE or the two copies DISAGREE · 2 = can't tell
#
# ── WHY ────────────────────────────────────────────────────────────────────
# CMS publishes ICD-10-CM by fiscal year. FY2026 is effective 2025-10-01 to
# 2026-09-30. On 2026-10-01 every code in `ICD10_ALLOWLIST` becomes a
# PREVIOUS-YEAR code, and the set stops being the current one.
#
# ⚠️ NOTHING BREAKS LOUDLY, WHICH IS THE HAZARD. The ingestion gates assert
# FY2026's counts against FY2026's data, so they stay green forever on a stale
# set: 74_719, 23_467, 98_186 and the rest are hard-coded across three test
# files. `docs/backlog/fy2027-icd10-ingestion-20261001.md` names this exactly —
# "nothing tells you the edition is stale; the ingestion is what tells you, and
# only if somebody runs it." This is the somebody.
#
# The cost of a stale set is not cosmetic and it lands on a billing surface:
# codes CMS deleted keep being accepted, codes CMS added keep being refused,
# and a code whose billable/header status flipped is refused or admitted
# wrongly — with the doctor told to bill a child that no longer exists.
#
# ── IT CROSS-CHECKS TWO COPIES OF ONE FACT, BECAUSE THERE ARE TWO ──────────
# ⚠️ The effective window is written down TWICE:
#
#   · `icd10cm-<edition>-provenance.json` -> effectiveFrom / effectiveTo
#   · `icd10-allowlist.ts` -> ICD10_EDITION, a hand-written display string
#     that repeats the same two dates in prose
#
# Two copies of one fact drift, and the drift is silent because nothing reads
# them together. This check reads BOTH and refuses if they disagree — a
# disagreement is a finding in its own right, not a reason to pick one.
#
# ── TREE-RELATIVE ON PURPOSE, AND THAT IS NOT THE F28 DEFECT ───────────────
# It resolves the data files from its OWN checkout, because the question is
# "is the set THIS TREE ships current?" — the same reasoning
# `check-agents-md-size.sh` records. The standing PRODUCTION checks must run
# from /opt/meddoc-pro because they make claims about production; this one
# makes a claim about a file in a tree. Do not "fix" it to anchor elsewhere.
#
# ── LEAD TIME IS PART OF THE ANSWER ────────────────────────────────────────
# Firing on the expiry date is too late: the FY2027 row lists SIX steps, one of
# which is re-certifying every twin whose mapping names a code that changed
# status. So it fires while there is still time to act — default 30 days —
# and says which of DUE and STALE it is.
# ============================================================================
set -uo pipefail

LEAD_DAYS="${ICD_EDITION_LEAD_DAYS:-30}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$REPO_DIR/packages/ai/src/data"

case "$LEAD_DAYS" in
  ''|*[!0-9]*) echo "🟡 CANNOT TELL — lead days '$LEAD_DAYS' is not a number"; exit 2 ;;
esac

[ -d "$DATA_DIR" ] || { echo "🟡 CANNOT TELL — no $DATA_DIR"; exit 2; }

# ⚠️ EXACTLY ONE provenance file, or the active edition is ambiguous. During a
# swap both may exist; that is a state to resolve, never to guess through.
mapfile -t PROV < <(find "$DATA_DIR" -maxdepth 1 -name 'icd10cm-*-provenance.json' | sort)
if [ "${#PROV[@]}" -eq 0 ]; then
  echo "🟡 CANNOT TELL — no icd10cm-*-provenance.json under $DATA_DIR"; exit 2
fi
if [ "${#PROV[@]}" -gt 1 ]; then
  echo "🟡 CANNOT TELL — ${#PROV[@]} provenance files present, so the ACTIVE edition is ambiguous:"
  printf '   %s\n' "${PROV[@]}"
  echo "   Resolve which edition is wired before believing any answer about staleness."
  exit 2
fi
PROV_FILE="${PROV[0]}"

read -r P_EDITION P_FROM P_TO < <(python3 - "$PROV_FILE" <<'PY' 2>/dev/null
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
print(d.get('edition',''), d.get('effectiveFrom',''), d.get('effectiveTo',''))
PY
) || true

for v in "$P_EDITION" "$P_FROM" "$P_TO"; do
  [ -n "${v:-}" ] || { echo "🟡 CANNOT TELL — provenance is missing edition/effectiveFrom/effectiveTo: $PROV_FILE"; exit 2; }
done
case "$P_TO" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
  *) echo "🟡 CANNOT TELL — effectiveTo '$P_TO' is not an ISO date"; exit 2 ;;
esac

# ---- the second copy, and they must agree -------------------------------
ALLOWLIST="$REPO_DIR/packages/ai/src/data/icd10-allowlist.ts"
[ -r "$ALLOWLIST" ] || { echo "🟡 CANNOT TELL — cannot read $ALLOWLIST"; exit 2; }
EDITION_LINE="$(grep -m1 'ICD10_EDITION *=' "$ALLOWLIST" || true)"
[ -n "$EDITION_LINE" ] || { echo "🟡 CANNOT TELL — no ICD10_EDITION in $ALLOWLIST"; exit 2; }

MISMATCH=""
case "$EDITION_LINE" in
  *"$P_FROM"*) ;;
  *) MISMATCH="effectiveFrom $P_FROM is not in ICD10_EDITION" ;;
esac
case "$EDITION_LINE" in
  *"$P_TO"*) ;;
  *) MISMATCH="${MISMATCH:+$MISMATCH; }effectiveTo $P_TO is not in ICD10_EDITION" ;;
esac

TODAY="$(date -u +%Y-%m-%d)"
TO_EPOCH="$(date -u -d "$P_TO" +%s 2>/dev/null)" || TO_EPOCH=""
TODAY_EPOCH="$(date -u -d "$TODAY" +%s 2>/dev/null)" || TODAY_EPOCH=""
if [ -z "$TO_EPOCH" ] || [ -z "$TODAY_EPOCH" ]; then
  echo "🟡 CANNOT TELL — could not convert dates ('$P_TO', '$TODAY')"; exit 2
fi
DAYS_LEFT=$(( (TO_EPOCH - TODAY_EPOCH) / 86400 ))

echo "   edition   : $P_EDITION   ($P_FROM .. $P_TO)"
echo "   today     : $TODAY"
echo "   days left : $DAYS_LEFT   (lead window $LEAD_DAYS)"
echo "   provenance: ${PROV_FILE#$REPO_DIR/}"

if [ -n "$MISMATCH" ]; then
  cat <<MSG
🔴 THE TWO COPIES OF THE EFFECTIVE WINDOW DISAGREE — $MISMATCH

  The provenance JSON and the hand-written ICD10_EDITION string state the same
  fact twice, and they have drifted. Neither is trustworthy until they are
  reconciled, so this is reported instead of a staleness verdict.
MSG
  exit 1
fi

if [ "$DAYS_LEFT" -lt 0 ]; then
  cat <<MSG
🔴 STALE — the shipped ICD-10-CM set expired $(( -DAYS_LEFT )) day(s) ago.

  Every code in ICD10_ALLOWLIST is a previous-year code. Deleted codes are still
  accepted, added codes are still refused, and any code whose billable/header
  status flipped is now wrong on a BILLING surface.

  The gates will NOT tell you: they assert this edition's counts against this
  edition's data and stay green. Run the ingestion.
    docs/backlog/fy2027-icd10-ingestion-20261001.md
MSG
  exit 1
fi

if [ "$DAYS_LEFT" -le "$LEAD_DAYS" ]; then
  cat <<MSG
🔴 DUE — $DAYS_LEFT day(s) of validity left, inside the $LEAD_DAYS-day lead window.

  The next edition's ingestion is a six-step job, and one of those steps is
  re-certifying every twin whose mapping names a code that changed status. That
  does not fit into the last afternoon.
    docs/backlog/fy2027-icd10-ingestion-20261001.md
MSG
  exit 1
fi

echo "🟢 current — $DAYS_LEFT day(s) of validity left"
exit 0
