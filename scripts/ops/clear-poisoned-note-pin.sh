#!/usr/bin/env bash
# ============================================================================
# ONE-SHOT: clear the poisoned note pin on compiled version 617d6de9…
# Runs ONLY through scripts/run-ruled-mutation.sh — it refuses otherwise.
# Declaration: docs/foundation/mutations/20260820-pin-clear-cmsxip5f9.md
# ============================================================================
set -uo pipefail
ROW=617d6de9-3dd5-462d-bcb8-cda05e2f1753

if [ -z "${RULED_MUTATION_DECLARATION:-}" ] || [ -z "${RULED_MUTATION_DECL_COMMIT:-}" ]; then
  echo "🔴 REFUSING — not invoked through run-ruled-mutation.sh."
  echo "   An irreversible act needs a committed declaration in front of it."
  exit 1
fi
echo "declaration : $RULED_MUTATION_DECLARATION"
echo "decl commit : $RULED_MUTATION_DECL_COMMIT"
echo "row         : $ROW"
echo "started     : $(date -u +%Y-%m-%dT%H:%M:%SZ)"

PSQL=(docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc -v ON_ERROR_STOP=1)

echo "-- BEFORE --"
"${PSQL[@]}" -t -A -F' | ' -c \
  "select left(\"pinnedNoteEncounterSha256\",12), \"pinnedNoteGeneratedAt\",
          length(\"pinnedSyntheticNote\"::text) from template_twin_compiled_versions where id='$ROW';"

# ⚠️ SCOPED BY PRIMARY KEY AND ASSERTED INSIDE THE TRANSACTION. A mutation that
# leaves a different state than declared has done something nobody declared, so
# it rolls back rather than being explained afterwards.
out=$("${PSQL[@]}" -t -A <<SQL
begin;
update template_twin_compiled_versions
   set "pinnedSyntheticNote"        = null,
       "pinnedNoteGeneratedAt"      = null,
       "pinnedNoteModelVersion"     = null,
       "pinnedNoteTemplateSha256"   = null,
       "pinnedNoteEncounterSha256"  = null,
       "pinnedSyntheticEntities"    = null,
       "pinnedSyntheticContextText" = null
 where id = '$ROW';
select case when (select count(*) from template_twin_compiled_versions
                   where id='$ROW' and "pinnedSyntheticNote" is null
                     and "pinnedNoteEncounterSha256" is null) = 1
            then 'OK' else 'MISMATCH' end;
commit;
SQL
)
echo "assertion   : $out"
case "$out" in
  *MISMATCH*|"") echo "🔴 the post-state assertion did not hold"; exit 2 ;;
esac

echo "-- AFTER --"
"${PSQL[@]}" -t -A -F' | ' -c \
  "select coalesce(left(\"pinnedNoteEncounterSha256\",12),'(null)'),
          coalesce(\"pinnedNoteGeneratedAt\"::text,'(null)'),
          coalesce(length(\"pinnedSyntheticNote\"::text)::text,'(null)'),
          coalesce(left(\"pinnedSyntheticEntities\"::text,12),'(null)')
     from template_twin_compiled_versions where id='$ROW';"
echo "finished    : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
