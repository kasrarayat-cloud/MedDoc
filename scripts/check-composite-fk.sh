#!/usr/bin/env bash
# ============================================================================
# Is T3's COMPOSITE foreign key still there, and still the shape that enforces?
# ----------------------------------------------------------------------------
#     transcribe_visits_patientId_practiceId_fkey
#       FOREIGN KEY ("patientId", "practiceId")
#       REFERENCES transcribe_md_patients(id, "practiceId")
#
# This constraint is what makes a visit whose practice differs from its
# patient's UNREPRESENTABLE — not discouraged, unrepresentable. There is no
# application code to route around it and no trigger to disable: the storage
# layer refuses the row.
#
# ⚠️ WHY IT NEEDS A GUARD RATHER THAN A COMMENT — PRISMA OFFERS ITS DELETION AS
# TIDYING. Prisma has no syntax for a composite FK, so `TranscribeVisit.practice`
# renders as a SIMPLE FK on `practiceId`. `prisma migrate diff` therefore reports
# a permanent difference, and the script it generates says:
#
#     ALTER TABLE "transcribe_visits"
#       DROP CONSTRAINT "transcribe_visits_patientId_practiceId_fkey";
#     ALTER TABLE "transcribe_visits"
#       ADD  CONSTRAINT "transcribe_visits_practiceId_fkey"
#       FOREIGN KEY ("practiceId") REFERENCES "practices"("id") …;
#
# That reads like closing drift. It is the removal of the tenancy wall. The
# replacement checks only that the practice EXISTS — which every wrong practice
# id also satisfies. Anyone running `prisma migrate dev` to "clean up drift"
# deletes the guarantee and gets a tidy-looking migration for it.
#
# ⚠️ AND THAT IS EXACTLY WHY A WARNING COMMENT IS NOT ENOUGH. A stated invariant
# is a WISH until something asserts it — `DEPLOYMENT_RUNBOOK.md` §5.6 asserted
# the ingress used internal certs for two months while it did not, and the gap
# was invisible to every reader of both documents. This file is that sentence
# turned into a check.
#
# ── TWO ARMS ───────────────────────────────────────────────────────────────
#
#   STRUCTURAL (always, READ-ONLY, safe on production)
#     The constraint exists BY NAME **and** its definition still names BOTH
#     columns on both sides. Name alone is not enough: a constraint can be
#     dropped and re-added under the same name with one column, which is
#     precisely the reshape Prisma proposes.
#
#   BEHAVIOURAL (--attempt, opt-in, FAIL-CLOSED off non-prod)
#     A cross-practice INSERT is attempted inside BEGIN … ROLLBACK and must be
#     refused BY THIS CONSTRAINT. ⚠️ Every unrelated NOT NULL is satisfied first,
#     so the FK is the thing that rejects — an earlier attempt "passed" only
#     because `specialty` NOT NULL rejected the row before the FK was ever
#     consulted, which proves nothing about the FK. A refusal is only evidence
#     when you know WHAT refused.
#
#     Plus a POSITIVE CONTROL: the same INSERT with the CORRECT practice must
#     SUCCEED (also rolled back). Without it, a refusal could come from any
#     typo, and "the insert failed" would be indistinguishable from the guard
#     working.
#
# READ-ONLY by default. `--attempt` writes only inside a transaction that always
# rolls back, and refuses to run against anything that is not positively a
# qa/test database (mirrors packages/db/src/db-guard.ts, fail-closed).
#
# Usage:  bash scripts/check-composite-fk.sh [--attempt]
#         PG_CONTAINER=meddoc-qa-postgres-1 PG_DB=meddoc_qa_test \
#           bash scripts/check-composite-fk.sh --attempt
# Exit:   0 = intact · 1 = ABSENT OR RESHAPED · 2 = cannot tell
# ============================================================================
set -uo pipefail

PG_CONTAINER="${PG_CONTAINER:-meddoc-pro-postgres-1}"
PG_USER="${PG_USER:-meddoc}"
PG_DB="${PG_DB:-meddoc}"
FK_NAME="transcribe_visits_patientId_practiceId_fkey"
ATTEMPT=0
[ "${1:-}" = "--attempt" ] && ATTEMPT=1

psql_q() { docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -X -tA -c "$1" 2>/dev/null; }

if ! docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
  echo "🟡 $PG_CONTAINER is not running — cannot tell"; exit 2
fi
if [ -z "$(psql_q 'select 1')" ]; then
  echo "🟡 cannot query $PG_DB on $PG_CONTAINER — cannot tell"; exit 2
fi

# ── ARM 1 — STRUCTURAL ─────────────────────────────────────────────────────
DEF="$(psql_q "select pg_get_constraintdef(oid) from pg_constraint where conname='${FK_NAME}'")"

if [ -z "$DEF" ]; then
  cat <<EOS
🔴 T3's COMPOSITE FK IS GONE — $FK_NAME does not exist on $PG_DB.

   A visit whose practice differs from its patient's is now REPRESENTABLE.
   Nothing in the application prevents it; the composite FK was the only thing
   that did.

   The most likely cause is someone applying a \`prisma migrate diff\` hunk that
   offered to drop it as drift. DO NOT re-add a simple practiceId FK in its
   place — that checks only that the practice EXISTS. Restore the composite:

     ALTER TABLE "transcribe_visits" ADD CONSTRAINT "$FK_NAME"
       FOREIGN KEY ("patientId", "practiceId")
       REFERENCES "transcribe_md_patients"(id, "practiceId")
       ON UPDATE CASCADE ON DELETE RESTRICT;

   (Requires transcribe_md_patients @@unique([id, practiceId]) — schema.prisma.)
EOS
  exit 1
fi

# BY DEFINITION, not by name. A same-named single-column FK is the reshape.
ok=1
printf '%s' "$DEF" | grep -q 'FOREIGN KEY ("patientId", "practiceId")' || ok=0
printf '%s' "$DEF" | grep -qE 'REFERENCES transcribe_md_patients\(id, "practiceId"\)' || ok=0

if [ "$ok" -ne 1 ]; then
  echo "🔴 $FK_NAME EXISTS BUT HAS BEEN RESHAPED — the name survived, the guarantee may not."
  echo "   actual:   $DEF"
  echo "   expected: FOREIGN KEY (\"patientId\", \"practiceId\") REFERENCES transcribe_md_patients(id, \"practiceId\")"
  echo "   A single-column FK under this name enforces only that the practice EXISTS."
  exit 1
fi
echo "✔ structural: $FK_NAME references BOTH columns on both sides"

if [ "$ATTEMPT" -eq 0 ]; then
  echo
  echo "🟢 T3's composite FK is present and correctly shaped on '$PG_DB'"
  echo "   (structural only. Add --attempt on a qa/test database for the"
  echo "    behavioural proof — it is refused off non-prod, fail-closed.)"
  exit 0
fi

# ── ARM 2 — BEHAVIOURAL, opt-in, fail-closed ───────────────────────────────
# Mirrors packages/db/src/db-guard.ts: a positive qa/test/e2e/ci marker is
# REQUIRED. Absence of proof that this is non-prod is treated as proof that it
# might be prod.
case "$PG_DB" in
  meddoc|meddoc_pro|postgres)
    echo "🟡 refusing --attempt against '$PG_DB' — that is a production database name."
    echo "   F3: READ-ONLY on production stays the default."
    exit 2 ;;
esac
if ! printf '%s' "$PG_DB" | grep -qiE '(qa|test|e2e|ci)'; then
  echo "🟡 refusing --attempt against '$PG_DB' — no qa/test/e2e/ci marker, so this"
  echo "   cannot be POSITIVELY confirmed non-prod. Fail-closed."
  exit 2
fi

echo "· behavioural arm on '$PG_DB' (transactional, always rolled back)"

RESULT="$(docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -X -tA -v ON_ERROR_STOP=0 <<'SQL' 2>&1
BEGIN;
DO $$
DECLARE
  v_pat   text; v_right text; v_wrong text; v_user text;
BEGIN
  SELECT p.id, p."practiceId" INTO v_pat, v_right
    FROM transcribe_md_patients p JOIN practices pr ON pr.id = p."practiceId" LIMIT 1;
  SELECT id INTO v_wrong FROM practices WHERE id <> v_right LIMIT 1;
  SELECT id INTO v_user FROM users LIMIT 1;

  IF v_pat IS NULL OR v_wrong IS NULL OR v_user IS NULL THEN
    RAISE NOTICE 'FIXTURE-MISSING patient=% wrongPractice=% user=%', v_pat, v_wrong, v_user;
    RETURN;
  END IF;

  -- NEGATIVE: the WRONG practice. Every unrelated NOT NULL is supplied, so the
  -- composite FK is what rejects — not `specialty`, not `inputMode`.
  BEGIN
    INSERT INTO transcribe_visits
      (id,"userId",specialty,"inputMode","updatedAt","patientId","practiceId","createdBy")
    VALUES ('fkprobe-wrong', v_user, 'primary_care', 'text_notes', now(), v_pat, v_wrong, v_user);
    RAISE NOTICE 'NEGATIVE-FAILED: a cross-practice visit was ACCEPTED';
  EXCEPTION
    WHEN foreign_key_violation THEN
      IF SQLERRM LIKE '%patientId_practiceId%' THEN
        RAISE NOTICE 'NEGATIVE-OK refused by the composite FK';
      ELSE
        RAISE NOTICE 'NEGATIVE-WRONG-CAUSE %', SQLERRM;
      END IF;
    WHEN others THEN
      RAISE NOTICE 'NEGATIVE-WRONG-CAUSE %', SQLERRM;
  END;

  -- POSITIVE CONTROL: identical row, CORRECT practice. Must succeed, or the
  -- refusal above proves only that the INSERT was malformed.
  BEGIN
    INSERT INTO transcribe_visits
      (id,"userId",specialty,"inputMode","updatedAt","patientId","practiceId","createdBy")
    VALUES ('fkprobe-right', v_user, 'primary_care', 'text_notes', now(), v_pat, v_right, v_user);
    RAISE NOTICE 'POSITIVE-OK the same insert with the correct practice succeeded';
  EXCEPTION WHEN others THEN
    RAISE NOTICE 'POSITIVE-FAILED %', SQLERRM;
  END;
END $$;
ROLLBACK;
SQL
)"

neg_ok=0; pos_ok=0
printf '%s\n' "$RESULT" | grep -q 'NEGATIVE-OK' && neg_ok=1
printf '%s\n' "$RESULT" | grep -q 'POSITIVE-OK' && pos_ok=1
printf '%s\n' "$RESULT" | grep -E 'NOTICE' | sed 's/^NOTICE:  /   /'

if printf '%s\n' "$RESULT" | grep -q 'FIXTURE-MISSING'; then
  echo "🟡 no usable fixture on '$PG_DB' (needs a patient, a second practice and a user) — cannot tell"
  exit 2
fi
if [ "$neg_ok" -ne 1 ] || [ "$pos_ok" -ne 1 ]; then
  echo
  echo "🔴 BEHAVIOURAL PROOF FAILED."
  [ "$neg_ok" -ne 1 ] && echo "   the cross-practice insert was NOT refused by the composite FK"
  [ "$pos_ok" -ne 1 ] && echo "   the correct-practice control did NOT succeed — the refusal above means nothing"
  exit 1
fi

# Residue: the transaction rolled back, so neither probe row may survive.
LEFT="$(psql_q "select count(*) from transcribe_visits where id in ('fkprobe-wrong','fkprobe-right')")"
if [ "${LEFT:-0}" != "0" ]; then
  echo "🔴 $LEFT probe row(s) SURVIVED the rollback — the guard mutated the database."
  exit 1
fi
echo "   · residue 0 — both probes rolled back"

echo
echo "🟢 T3's composite FK is present, correctly shaped, AND proven to refuse"
echo "   a cross-practice visit while accepting the same row correctly scoped."
exit 0
