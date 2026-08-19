#!/usr/bin/env bash
# ============================================================================
# check-em-note-shape-artifacts.sh — READ-ONLY production watcher.  F12-g.
# ----------------------------------------------------------------------------
# WHICH PRODUCTION VISITS CARRY OFFICE-E/M STATE WHILE `emAppliesToVisit` SAYS
# THE LEVEL DOES NOT APPLY?
#
# `visits/[id]/page.tsx` writes `emScoredCode` while the verdict is TRUE and
# NOTHING CLEARS IT WHEN THE VERDICT LATER FLIPS — same for `cptCodes.em` and,
# on a signed record, the frozen `signedCode`. Verdicts flip for ordinary
# reasons: a template is retired (`onDelete: SetNull`, and every read path joins
# without a status filter), a note body is edited, or the classifier itself is
# corrected — F12-a, F12-d and F12-f each moved it. So this is a standing class,
# not a one-off, and F12-g measured 15 live rows carrying it.
#
# ⚠️ WHY THIS IS A SECOND WATCHER AND NOT A WIDENING OF THE FIRST.
# `check-imaging-em-artifacts.sh` is `where specialty='ultrasound'` — the
# SPECIALTY axis. Note shape (ruling #123) is a SECOND axis, entirely outside
# that script's watched set, so its 🟢 is true and covers none of these rows.
# This one reports WHICH axis suppressed each row, so the relationship between
# the two is legible instead of assumed. Rows reading `axis=specialty` belong to
# the older watcher; `axis=note-shape` rows are watched by nothing else.
#
# ⚠️ THE PREDICATE IS NEVER RE-IMPLEMENTED IN SQL. F12-g's own filing records
# what that costs: an SQL re-implementation with the specialty axis approximated
# answered **19** where the shipped `emAppliesToVisit` answers **15**. The SQL
# here is a PROJECTION and nothing more; every verdict comes from the module.
#
# ⚠️ PHI POSTURE — IT NEVER READS A NOTE BODY, AND THE CLAIM IS CONTROLLED.
# The extract emits, per visit, only the note's markdown HEADING LINES plus
# structured columns. The filter `^[ \t]*#{1,6}[ \t]+` is a strict PREFIX of
# `NOTE_SECTION_HEADING_RE` in note-shape.ts, so it cannot MISS a line the
# shipped regex would accept; and the scanner asserts the other direction (that
# every delivered line survives that regex) so it cannot silently carry body
# text either. Nothing is written to disk at any point — the payload is piped.
#
# ── STRICTLY READ-ONLY ─────────────────────────────────────────────────────
# SELECTs only. Remediation is a deliberate transactional act through
# `scripts/run-ruled-mutation.sh` with its own §2.5 declaration and an audit
# row — never a side effect of a check. The disposition of what this finds is a
# war-room question; the script exists so the number stops being invisible.
#
# Exit codes:  0 = clean   1 = artifacts found (report, do not auto-fix)
#              2 = CANNOT TELL — unreachable, wrong universe, vacuous corpus,
#                  a projection that failed its own control, or a classifier
#                  that does not match the one production runs.
#
# ⚠️ `2` IS NEVER COLLAPSED INTO `0`. A broken instrument and a clean system
# produce the same zero, which is this repository's most expensive recurring
# defect. Every blind state below refuses.
#
# Usage:  bash scripts/check-em-note-shape-artifacts.sh
#
# Invoked via `bash`, not `./`: core.fileMode=false here, so the executable bit
# is not tracked and a fresh clone cannot run scripts/ directly.
#
# ⚠️ ═══ IF YOU ARE THE UNATTENDED LOOP AND THIS FILE WAS REFUSED, READ THIS ═══
#
# `.claude/settings.json` names permitted scripts ONE BY ONE, and **the loop
# cannot edit that file** — settings are protected from the layer they govern,
# which is correct and is not going to change. So the session that wrote this
# script could not ship its own grant, and canon's rule *"an entry that names an
# instrument verifies that instrument's GRANT in the same commit"* is
# STRUCTURALLY UNREACHABLE from here. It is an OWNER ACTION:
#
#     "Bash(bash scripts/check-em-note-shape-artifacts.sh:*)"
#
# ⚠️ **DO NOT WORK AROUND A REFUSAL BY TUNNELLING THIS FILE THROUGH `node -e`,
# `python3 -c`, OR ANY OTHER GRANTED INTERPRETER.** That is the
# sanctioned-hatch-becomes-the-undisciplined-door failure, and MASTER forbids it
# by name. There is a legitimate route, it is fully granted, and it was the one
# actually used to take the 2026-08-19 measurement:
#
#     docker exec -i meddoc-pro-postgres-1 psql -U meddoc meddoc -A -t -f - \
#       < scripts/lib/em-artifact-scan.sql \
#       | npx --no-install tsx scripts/lib/em-artifact-scan-cli.ts \
#           --flags '{"NEXT_PUBLIC_ULTRASOUND_SPECIALTY":"true"}'
#
# ⚠️ THAT ROUTE IS STRICTLY WEAKER AND THE CLI SAYS SO ON EVERY RUN. It skips
# the two controls this wrapper exists to add — the SHIPPED-CODE IDENTITY check
# (§2) and reading the flags FROM THE RUNNING CONTAINER (§3) — so the flag value
# above is something a session TYPED. Read it from the container in the same
# pass and paste what you saw:
#
#     docker exec meddoc-pro-transcribe-md-worker-1 printenv NEXT_PUBLIC_ULTRASOUND_SPECIALTY
#     docker exec meddoc-pro-transcribe-md-worker-1 sha256sum \
#       /app/apps/transcribe-md/src/lib/note-shape.ts /app/packages/shared/src/specialties.ts
#     sha256sum apps/transcribe-md/src/lib/note-shape.ts packages/shared/src/specialties.ts
#
# A typed flag is a claim about production; a printed one is a measurement.
# ============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CONTAINER="${PROD_PG_CONTAINER:-meddoc-pro-postgres-1}"
DB="${PROD_PG_DB:-meddoc}"
DB_USER="${PROD_PG_USER:-meddoc}"
APP_CONTAINER="${PROD_APP_CONTAINER:-meddoc-pro-transcribe-md-worker-1}"

# The flags the classifier actually reads. Read from the RUNNING container —
# never from .env, never from the compose file, never from memory.
FLAG_NAMES=(NEXT_PUBLIC_ULTRASOUND_SPECIALTY)

say() { printf '%s\n' "$*"; }
cannot_tell() { printf '\n🟡 CANNOT TELL — %s\n' "$*"; exit 2; }

q() { docker exec "$CONTAINER" psql -U "$DB_USER" "$DB" -A -t -c "$1" 2>/dev/null; }

# ── 1 · REACHABILITY ────────────────────────────────────────────────────────
if ! q 'select 1' >/dev/null; then
  say "SKIPPED — cannot reach ${CONTAINER}/${DB} (not on the prod host?)"
  exit 2
fi
if ! docker exec "$APP_CONTAINER" true >/dev/null 2>&1; then
  cannot_tell "cannot exec into ${APP_CONTAINER} — the shipped-code control below is what makes this a statement about PRODUCTION, and it cannot be taken"
fi

# ── 2 · SHIPPED-CODE IDENTITY ───────────────────────────────────────────────
# The scanner imports note-shape.ts from THIS tree. Production runs the copy in
# the worker image. If they differ, every number below describes a classifier
# production does not run — which is the wrong-universe failure, and it looks
# exactly like a correct answer.
#
# ⚠️ specialties.ts is resolved through node_modules/@meddoc/shared, which is a
# SYMLINK to the shared tree — NOT to this script's tree. A worktree copy of
# this script therefore imports another tree's specialty axis, silently. So the
# path is RESOLVED with realpath and the resolved file is the one hashed.
sha_local() { sha256sum "$1" 2>/dev/null | cut -c1-16; }
sha_ctr()   { docker exec "$APP_CONTAINER" sha256sum "$1" 2>/dev/null | cut -c1-16; }

SHARED_SPECIALTIES="$(node -e 'console.log(require("fs").realpathSync(process.argv[1]))' \
  "$ROOT/node_modules/@meddoc/shared/src/specialties.ts" 2>/dev/null)"
[ -n "$SHARED_SPECIALTIES" ] || cannot_tell "could not resolve @meddoc/shared/src/specialties.ts from $ROOT"

declare -a PAIRS=(
  "$ROOT/apps/transcribe-md/src/lib/note-shape.ts|/app/apps/transcribe-md/src/lib/note-shape.ts"
  "$SHARED_SPECIALTIES|/app/packages/shared/src/specialties.ts"
)
say "shipped-code control — the classifier this scan runs vs the one in ${APP_CONTAINER}:"
IDENTITY_OK=1
for pair in "${PAIRS[@]}"; do
  L="${pair%%|*}"; C="${pair##*|}"
  LS="$(sha_local "$L")"; CS="$(sha_ctr "$C")"
  if [ -z "$LS" ] || [ -z "$CS" ]; then
    say "   ✘ ${C}  local=${LS:-<unreadable>} container=${CS:-<unreadable>}"
    IDENTITY_OK=0
  elif [ "$LS" = "$CS" ]; then
    say "   ✔ ${C}  ${LS}"
  else
    say "   ✘ ${C}  local=${LS} container=${CS}  DIVERGED"
    IDENTITY_OK=0
  fi
done
say "   (reading note-shape from: ${ROOT})"
say "   (reading specialties from: ${SHARED_SPECIALTIES})"
[ "$IDENTITY_OK" = "1" ] || cannot_tell "the classifier on disk is not the one production runs — a number from it would be about a system nobody ships"

# ── 3 · THE FLAG UNIVERSE, FROM THE RUNNING CONTAINER ───────────────────────
FLAGS_JSON="{"
FIRST=1
for f in "${FLAG_NAMES[@]}"; do
  V="$(docker exec "$APP_CONTAINER" printenv "$f" 2>/dev/null)"
  [ -n "$V" ] || cannot_tell "${f} is unset or unreadable in ${APP_CONTAINER} — refusing to scan in a guessed configuration"
  [ "$FIRST" = "1" ] || FLAGS_JSON="${FLAGS_JSON},"
  FIRST=0
  FLAGS_JSON="${FLAGS_JSON}\"${f}\":\"${V}\""
done
FLAGS_JSON="${FLAGS_JSON}}"

# ── 4 · THE PROJECTION ──────────────────────────────────────────────────────
# The query lives in its own tracked file so that what a session runs BY HAND is
# byte-identical to what this wrapper runs — an inline heredoc is a second copy,
# and a second copy drifts from the first the day either is edited.
SQL_FILE="$ROOT/scripts/lib/em-artifact-scan.sql"
[ -f "$SQL_FILE" ] || cannot_tell "missing $SQL_FILE"

ROWS_JSON="$(docker exec -i "$CONTAINER" psql -U "$DB_USER" "$DB" -A -t -f - \
              < "$SQL_FILE" 2>/dev/null)"

[ -n "${ROWS_JSON//[[:space:]]/}" ] || cannot_tell "the projection query returned nothing — the extract, not the corpus, is what failed"

# ── 5 · THE SCAN ────────────────────────────────────────────────────────────
# Piped, never written. The payload is production-derived and a scratch file is
# how that class escapes a session.
say ""
printf '{"flags":%s,"rows":%s}' "$FLAGS_JSON" "$ROWS_JSON" \
  | ( cd "$ROOT" && npx --no-install tsx scripts/lib/em-artifact-scan-cli.ts )
exit $?
