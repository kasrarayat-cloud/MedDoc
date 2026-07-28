#!/usr/bin/env bash
# ============================================================================
# check-imaging-em-artifacts.sh — READ-ONLY close-out check
# ----------------------------------------------------------------------------
# An imaging report has no office-visit E/M level. A clinic code on an
# ultrasound is wrong as DATA — it outlives any UI decision, because the export
# and the signed record read the column, not the screen.
#
# The invariant is enforced in three places already: the compute/store guards in
# the app, the fixture guards in the review-doc E2E pack, and a sweep in
# seed-certified-twin.ts. None of those watch PRODUCTION.
#
# WHY THIS EXISTS. Five prod imaging visits acquired `emScoredCode` from a page
# render made by a build that predated the specialtyLabel-vs-specialtyId fix. No
# seeder wrote them; no test could see them; they sat in the database for two
# days. They were remediated on 2026-07-28 (see docs/qa-reports/). A sixth row
# carried a doctor-set `cptCodes.em.override.code` from the same window, which is
# a different class and was deliberately left alone.
#
# So the class needs a watcher that looks at prod, from outside the app.
#
# ── STRICTLY READ-ONLY ─────────────────────────────────────────────────────
# This script runs SELECTs. It must NEVER mutate production. Remediation is a
# separate, deliberate, transactional act with an abort-on-mismatch guard and an
# audit row — never a side effect of a check. If this reports rows, decide what
# they are BEFORE touching them: a computed baseline (`emScoredCode`) and a
# doctor-set override (`cptCodes.em.override`) are not the same finding.
#
# Exit codes:  0 = clean   1 = artifacts found (report, do not auto-fix)
#              2 = could not reach the database
#
# Usage:  bash scripts/check-imaging-em-artifacts.sh
#
# Invoked via `bash`, not `./`, on purpose: this repo sets core.fileMode=false, so
# the executable bit is not tracked — all 14 files in scripts/ are mode 100644 and
# a fresh clone cannot run any of them directly. `./` worked on the machine that
# wrote the file and failed on the next checkout.
# ============================================================================
set -uo pipefail

CONTAINER="${PROD_PG_CONTAINER:-meddoc-pro-postgres-1}"
DB="${PROD_PG_DB:-meddoc}"
DB_USER="${PROD_PG_USER:-meddoc}"

q() { docker exec "$CONTAINER" psql -U "$DB_USER" "$DB" -A -t -c "$1" 2>/dev/null; }

if ! q 'select 1' >/dev/null; then
  echo "SKIPPED — cannot reach ${CONTAINER}/${DB} (not on the prod host?)"
  exit 2
fi

TOTAL="$(q "select count(*) from transcribe_visits where specialty='ultrasound';")"

# Key EXISTENCE on `em`, not `em.code` — the artifact that motivated this check
# a second time was at cptCodes.em.override.code, and a `->>'code'` probe reads
# it as absent. Ask whether the key is there at all.
ROWS="$(q "
  select id
      || '  status=' || status
      || '  signed=' || (\"signedAt\" is not null)
      || '  ' || concat_ws(', ',
           nullif('emScoredCode=' || coalesce(\"emScoredCode\",''), 'emScoredCode='),
           case when \"cptCodes\"->'em' ? 'code'     then 'cptCodes.em.code=' || (\"cptCodes\"->'em'->>'code') end,
           case when \"cptCodes\"->'em' ? 'override' then 'cptCodes.em.override.code=' || (\"cptCodes\"->'em'->'override'->>'code') end,
           case when \"cptCodes\"->'em' ? 'signedCode' then 'cptCodes.em.signedCode=' || (\"cptCodes\"->'em'->>'signedCode') end,
           case when \"emPendingChange\" is not null then 'emPendingChange set' end)
    from transcribe_visits
   where specialty='ultrasound'
     and (\"emScoredCode\" is not null or \"cptCodes\" ? 'em' or \"emPendingChange\" is not null)
   order by \"createdAt\";")"

if [ -z "${ROWS//[[:space:]]/}" ]; then
  echo "🟢 imaging E/M invariant holds on prod — 0 of ${TOTAL} imaging visits carry office E/M state"
  exit 0
fi

COUNT="$(printf '%s\n' "$ROWS" | grep -c .)"
echo "🔴 IMAGING E/M ARTIFACTS ON PROD — ${COUNT} of ${TOTAL} imaging visits:"
printf '%s\n' "$ROWS" | sed 's/^/    /'
cat <<'NOTE'

    An office-visit E/M level on an imaging report is wrong as data: the export
    and the signed record read the column, not the screen.

    DO NOT auto-fix from here. Classify first:
      • emScoredCode              — a computed baseline. Pre-fix residue if the
                                    visit predates the specialtyId fix. Safe to
                                    clear on an UNSIGNED visit, transactionally,
                                    with an audit row.
      • cptCodes.em.override      — a DOCTOR-SET code. A recorded clinical
                                    judgement; clearing it deletes what someone
                                    chose. Needs its own decision, not a sweep.
      • cptCodes.em.signedCode    — frozen into a SIGNED record. Never touch.

    Since 2026-07-28 the EXPORT path is guarded too: projectDisplayedEmCode
    takes a required `emApplies` and returns null for an imaging visit, so a row
    holding an `em` blob no longer prints an office code in PDF/DOCX/EHR output.
    A row reported here is therefore wrong DATA rather than a live leak — still
    worth clearing, no longer urgent.
NOTE
exit 1
