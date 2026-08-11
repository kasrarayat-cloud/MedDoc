#!/usr/bin/env bash
# ============================================================================
# Is B5's ledger still APPEND-ONLY, and does the database still DERIVE the
# balance?
# ----------------------------------------------------------------------------
#     ledger_entries_derive_before_insert          seq + balanceAfter + snapshot
#     ledger_entries_append_only_before_update     refuses UPDATE (one hole)
#     ledger_entries_append_only_before_delete     refuses DELETE
#     ledger_entries_append_only_before_truncate   refuses TRUNCATE
#
# SPEC §2.1 says the ledger is append-only and that a correction is another row.
# RELAY's B5 gate says that must be enforced "at the DATABASE, not by
# convention — an UPDATE and a DELETE are both attempted and both refused."
# This file is that sentence turned into a check.
#
# ⚠️ WHY A GUARD AND NOT A COMMENT. `prisma migrate dev` does not know these
# triggers exist. Prisma has no syntax for a trigger, so they appear in NO
# `schema.prisma` diff, and any regenerated migration silently omits them. A
# table that has quietly lost its append-only triggers looks EXACTLY like one
# that has them: same columns, same indexes, same `\d`, every test green. The
# only observable difference is that money can now be edited.
#
# ⚠️ AND THE SAME REASONING THAT PUT `check-composite-fk.sh` IN THE STANDING SET
# APPLIES HERE, HARDER. That guard exists because Prisma OFFERS to drop the
# composite FK as drift. Nothing offers to drop these — which is worse, not
# better: there is no prompt, no diff, no moment where somebody decides. They
# just fail to be recreated.
#
# ── THREE ARMS ─────────────────────────────────────────────────────────────
#
#   STRUCTURAL (always, READ-ONLY, safe on production)
#     All four triggers exist BY NAME **and** are enabled ('O' in tgenabled).
#     ⚠️ Name alone is not enough: `ALTER TABLE … DISABLE TRIGGER` leaves the
#     row in `pg_trigger` and stops it firing. A disabled trigger passes a
#     name-only check and enforces nothing — the same reshape hazard the
#     composite-FK guard checks definitions for.
#
#   DERIVATION (--attempt, on a qa/test database)
#     Three rows are inserted with DELIBERATELY WRONG `balanceAfter`, `seq` and
#     `practiceIdSnapshot` values, and the stored rows must show the DERIVED
#     ones instead. This is the arm that proves the trigger IGNORES the caller
#     rather than trusting it — a trigger that merely validated would reject
#     these inserts, and rejection is a different (weaker) contract.
#
#   REFUSAL (--attempt, on a qa/test database)
#     UPDATE, DELETE and TRUNCATE are each attempted and each must be refused
#     BY THIS TRIGGER — matched on the message, not merely on "an error
#     happened". A refusal is evidence only when you know WHAT refused
#     (AGENTS.md, earned when a `specialty NOT NULL` rejected a row before the
#     FK under test was ever consulted).
#     Plus the POSITIVE CONTROL that the one PERMITTED update — the S4c detach,
#     `practiceId` NOT NULL → NULL — still succeeds. Without it, a guard that
#     refused everything would score full marks while making account deletion
#     impossible, which is precisely the bug S4c exists to fix.
#
# ⚠️ EVERY WRITE IS INSIDE `BEGIN … ROLLBACK`. AGENTS.md, earned on 2026-08-05
# when a mutation proof dropped a live constraint and nulled 21 signers: "any
# write inside a gate that a constraint is supposed to refuse belongs in
# BEGIN; … ROLLBACK;. Then the attempt is observable and never consequential."
# Residue is asserted at the end, on a fresh connection.
#
# READ-ONLY by default. `--attempt` refuses to run against anything that is not
# positively a qa/test database (mirrors packages/db/src/db-guard.ts,
# fail-closed).
#
# Usage:  bash scripts/check-ledger-append-only.sh                # prod, structural
#         bash scripts/check-ledger-append-only.sh --qa           # QA, structural
#         bash scripts/check-ledger-append-only.sh --qa --attempt # QA, behavioural
# Exit:   0 = intact · 1 = WEAKENED OR GONE · 2 = cannot tell
#
# ⚠️ `--qa` IS A FLAG AND NOT AN ENV PREFIX, DELIBERATELY. The env-var form
# (`PG_DB=… bash script`) is outside the FOUNDATION loop's allowlist, and
# ruling 86(d) records what that costs: "a procedure the unattended loop cannot
# execute will not be re-run." A capability nobody can invoke is
# indistinguishable from one that does not exist — which is exactly how
# `assert-migrations-applied.sh` ran prod-only for three months while the QA
# stack drifted two migrations behind with every session reporting it green.
# The env vars still work for anything else; `--qa` is the invocable path.
# ============================================================================
set -uo pipefail

PG_CONTAINER="${PG_CONTAINER:-meddoc-pro-postgres-1}"
PG_USER="${PG_USER:-meddoc}"
PG_DB="${PG_DB:-meddoc}"
ATTEMPT=0

for arg in "$@"; do
  case "$arg" in
    --attempt) ATTEMPT=1 ;;
    --qa)      PG_CONTAINER="meddoc-qa-postgres-1"; PG_DB="meddoc_qa_test" ;;
    *) echo "🟡 unknown argument '$arg' — expected --qa and/or --attempt"; exit 2 ;;
  esac
done

[ "$PG_DB" = "meddoc_qa_test" ] && echo "target: QA stack ($PG_CONTAINER/$PG_DB)"

psql_q() { docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -X -tA -c "$1" 2>/dev/null; }

if ! docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
  echo "🟡 $PG_CONTAINER is not running — cannot tell"; exit 2
fi
if [ -z "$(psql_q 'select 1')" ]; then
  echo "🟡 cannot query $PG_DB on $PG_CONTAINER — cannot tell"; exit 2
fi

# The positive control for the instrument itself: if the table is absent the
# answer is "cannot tell", NEVER "no triggers missing". A guard that reports a
# clean zero against a table that does not exist is the emptiness failure.
if [ "$(psql_q "select to_regclass('public.ledger_entries') is not null")" != "t" ]; then
  echo "🟡 ledger_entries does not exist on '$PG_DB' — B5's migration is not applied here."
  echo "   cannot tell (this is NOT a pass: there is nothing to check)."
  exit 2
fi

# ── ARM 1 — STRUCTURAL ─────────────────────────────────────────────────────
EXPECTED="ledger_entries_append_only_before_delete
ledger_entries_append_only_before_truncate
ledger_entries_append_only_before_update
ledger_entries_derive_before_insert"

FOUND="$(psql_q "select tgname from pg_trigger where tgrelid='public.ledger_entries'::regclass and not tgisinternal order by tgname")"
DISABLED="$(psql_q "select tgname from pg_trigger where tgrelid='public.ledger_entries'::regclass and not tgisinternal and tgenabled <> 'O' order by tgname")"

missing=0
if [ "$FOUND" != "$EXPECTED" ]; then missing=1; fi

if [ "$missing" -ne 0 ]; then
  echo "🔴 B5's APPEND-ONLY TRIGGERS ARE NOT THE SET THEY SHOULD BE on $PG_DB."
  echo "   expected:"; printf '%s\n' "$EXPECTED" | sed 's/^/     /'
  echo "   found:";    printf '%s\n' "${FOUND:-(none)}" | sed 's/^/     /'
  echo
  echo "   Money in ledger_entries may now be editable or erasable. The most"
  echo "   likely cause is a regenerated migration: Prisma has no syntax for a"
  echo "   trigger, so \`prisma migrate dev\` recreates the table WITHOUT them and"
  echo "   reports no drift. Restore them from"
  echo "   packages/db/prisma/migrations/20260811070000_b5_ledger_entries/migration.sql"
  exit 1
fi

if [ -n "$DISABLED" ]; then
  echo "🔴 TRIGGERS PRESENT BUT DISABLED — the names survived, the guarantee did not:"
  printf '%s\n' "$DISABLED" | sed 's/^/     /'
  echo "   \`ALTER TABLE ledger_entries ENABLE TRIGGER <name>\` restores enforcement."
  exit 1
fi
echo "✔ structural: all 4 triggers present and ENABLED on ledger_entries"

# The CHECK constraints are part of the same guarantee — a vocabulary that has
# quietly widened is a bucket nobody sums.
CHECKS="$(psql_q "select count(*) from pg_constraint where conrelid='public.ledger_entries'::regclass and contype='c' and conname like 'ledger\_entries\_%'")"
if [ "${CHECKS:-0}" != "5" ]; then
  echo "🔴 expected 5 named CHECK constraints on ledger_entries, found ${CHECKS:-0}"
  exit 1
fi
echo "✔ structural: 5 named CHECK constraints present"

if [ "$ATTEMPT" -eq 0 ]; then
  echo
  echo "🟢 B5's ledger guards are present and enabled on '$PG_DB'"
  echo "   (structural only. Add --attempt on a qa/test database for the"
  echo "    behavioural proof — it is refused off non-prod, fail-closed.)"
  exit 0
fi

# ── ARMS 2 + 3 — BEHAVIOURAL, opt-in, fail-closed ──────────────────────────
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

echo "· behavioural arms on '$PG_DB' (transactional, always rolled back)"

RESULT="$(docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -X -tA -v ON_ERROR_STOP=0 <<'SQL' 2>&1
BEGIN;
DO $probe$
DECLARE
  v_practice text;
  b1 bigint; b2 bigint; s1 bigint; s2 bigint; snap text;
  n_left int;
BEGIN
  SELECT id INTO v_practice FROM practices LIMIT 1;
  IF v_practice IS NULL THEN
    RAISE NOTICE 'FIXTURE-MISSING no practice row to attach a ledger entry to';
    RETURN;
  END IF;

  -- ── ARM 2 — DERIVATION ───────────────────────────────────────────────
  -- Every derived column is supplied WRONG on purpose. The trigger must
  -- overwrite them, not reject them: "ignores the caller" is a strictly
  -- stronger contract than "validates the caller", and only one of the two
  -- makes a threaded balance impossible.
  INSERT INTO ledger_entries
    (id,"practiceId","practiceIdSnapshot",bucket,kind,"amountMicroUsd","balanceAfter",seq)
  VALUES ('ledgerprobe-1', v_practice, 'WRONG-SNAPSHOT', 'paid', 'topup', 5000000, 99999, 77);
  INSERT INTO ledger_entries
    (id,"practiceId","practiceIdSnapshot",bucket,kind,"amountMicroUsd","balanceAfter",seq)
  VALUES ('ledgerprobe-2', v_practice, 'WRONG-SNAPSHOT', 'paid', 'usage', -1500000, -42, 3);
  -- A different bucket keeps its OWN running balance. If the buckets were one
  -- number with a note, this row would read 3500000 - 250000.
  INSERT INTO ledger_entries
    (id,"practiceId","practiceIdSnapshot",bucket,kind,"amountMicroUsd","balanceAfter",seq)
  VALUES ('ledgerprobe-3', v_practice, 'WRONG-SNAPSHOT', 'promo', 'grant', 10000000, 0, 0);

  SELECT "balanceAfter", seq, "practiceIdSnapshot" INTO b1, s1, snap
    FROM ledger_entries WHERE id = 'ledgerprobe-1';
  SELECT "balanceAfter", seq INTO b2, s2
    FROM ledger_entries WHERE id = 'ledgerprobe-2';

  IF b1 = 5000000 AND s1 = 1 AND snap = v_practice THEN
    RAISE NOTICE 'DERIVE-1-OK first row: balanceAfter=% seq=% snapshot derived', b1, s1;
  ELSE
    RAISE NOTICE 'DERIVE-1-FAILED balanceAfter=% (want 5000000) seq=% (want 1) snapshot=% (want %)', b1, s1, snap, v_practice;
  END IF;

  IF b2 = 3500000 AND s2 = 2 THEN
    RAISE NOTICE 'DERIVE-2-OK running sum: balanceAfter=% seq=%', b2, s2;
  ELSE
    RAISE NOTICE 'DERIVE-2-FAILED balanceAfter=% (want 3500000) seq=% (want 2)', b2, s2;
  END IF;

  -- The promo bucket must be a SEPARATE running balance starting from zero.
  IF (SELECT "balanceAfter" FROM ledger_entries WHERE id='ledgerprobe-3') = 10000000
     AND (SELECT seq FROM ledger_entries WHERE id='ledgerprobe-3') = 1 THEN
    RAISE NOTICE 'DERIVE-3-OK promo bucket runs its own balance from zero';
  ELSE
    RAISE NOTICE 'DERIVE-3-FAILED promo bucket balance=% seq=%',
      (SELECT "balanceAfter" FROM ledger_entries WHERE id='ledgerprobe-3'),
      (SELECT seq FROM ledger_entries WHERE id='ledgerprobe-3');
  END IF;

  -- ── ARM 3 — REFUSAL ──────────────────────────────────────────────────
  BEGIN
    UPDATE ledger_entries SET "amountMicroUsd" = 1 WHERE id = 'ledgerprobe-1';
    RAISE NOTICE 'UPDATE-FAILED: a ledger row was EDITED';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE '%ledger_entries_append_only%' THEN
      RAISE NOTICE 'UPDATE-OK refused by ledger_entries_append_only';
    ELSE
      RAISE NOTICE 'UPDATE-WRONG-CAUSE %', SQLERRM;
    END IF;
  END;

  BEGIN
    DELETE FROM ledger_entries WHERE id = 'ledgerprobe-1';
    RAISE NOTICE 'DELETE-FAILED: a ledger row was ERASED';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE '%ledger_entries_append_only%' THEN
      RAISE NOTICE 'DELETE-OK refused by ledger_entries_append_only';
    ELSE
      RAISE NOTICE 'DELETE-WRONG-CAUSE %', SQLERRM;
    END IF;
  END;

  BEGIN
    TRUNCATE ledger_entries;
    RAISE NOTICE 'TRUNCATE-FAILED: the whole ledger was emptied in one statement';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE '%ledger_entries_append_only%' THEN
      RAISE NOTICE 'TRUNCATE-OK refused by ledger_entries_append_only';
    ELSE
      RAISE NOTICE 'TRUNCATE-WRONG-CAUSE %', SQLERRM;
    END IF;
  END;

  -- POSITIVE CONTROL: the ONE permitted update. Without this, a trigger that
  -- refused every UPDATE would pass all three arms above and make account
  -- deletion impossible — the S4c bug, arriving through the guard.
  BEGIN
    UPDATE ledger_entries SET "practiceId" = NULL WHERE id = 'ledgerprobe-1';
    IF (SELECT "practiceIdSnapshot" FROM ledger_entries WHERE id='ledgerprobe-1') = v_practice THEN
      RAISE NOTICE 'DETACH-OK the S4c detach is permitted and the tombstone survived';
    ELSE
      RAISE NOTICE 'DETACH-FAILED the tombstone did not survive the detach';
    END IF;
  EXCEPTION WHEN others THEN
    RAISE NOTICE 'DETACH-FAILED %', SQLERRM;
  END;

  -- And the detach must not be a doorway: nulling practiceId WHILE changing
  -- something else must still be refused.
  BEGIN
    UPDATE ledger_entries
       SET "practiceId" = NULL, "amountMicroUsd" = 999
     WHERE id = 'ledgerprobe-2';
    RAISE NOTICE 'SMUGGLE-FAILED: an amount was changed under cover of the detach';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE '%ledger_entries_append_only%' THEN
      RAISE NOTICE 'SMUGGLE-OK a detach carrying another change is still refused';
    ELSE
      RAISE NOTICE 'SMUGGLE-WRONG-CAUSE %', SQLERRM;
    END IF;
  END;

  -- An INSERT with no practice must be refused by the derive trigger: the
  -- column is nullable for the detach only.
  BEGIN
    INSERT INTO ledger_entries
      (id,"practiceId","practiceIdSnapshot",bucket,kind,"amountMicroUsd")
    VALUES ('ledgerprobe-4', NULL, 'x', 'paid', 'topup', 1);
    RAISE NOTICE 'NOPRACTICE-FAILED: a tenantless ledger row was accepted';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE '%ledger_entries_insert_requires_practice%' THEN
      RAISE NOTICE 'NOPRACTICE-OK a tenantless insert is refused';
    ELSE
      RAISE NOTICE 'NOPRACTICE-WRONG-CAUSE %', SQLERRM;
    END IF;
  END;
END
$probe$;
ROLLBACK;
SQL
)"

printf '%s\n' "$RESULT" | grep -E 'NOTICE' | sed 's/^NOTICE:  /   /'

if printf '%s\n' "$RESULT" | grep -q 'FIXTURE-MISSING'; then
  echo "🟡 no practice row on '$PG_DB' to attach a probe entry to — cannot tell"
  exit 2
fi

fail=0
for marker in DERIVE-1-OK DERIVE-2-OK DERIVE-3-OK UPDATE-OK DELETE-OK TRUNCATE-OK DETACH-OK SMUGGLE-OK NOPRACTICE-OK; do
  printf '%s\n' "$RESULT" | grep -q "$marker" || { echo "   ✗ missing: $marker"; fail=1; }
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "🔴 BEHAVIOURAL PROOF FAILED — see the missing markers above."
  echo "   A '-WRONG-CAUSE' line means something refused, but not the guard:"
  echo "   a refusal is evidence only when you know WHAT refused."
  exit 1
fi

# Residue, on a FRESH connection: the transaction rolled back, so no probe row
# may survive. A guard that mutated the database while proving it cannot be
# mutated would be its own worst finding.
LEFT="$(psql_q "select count(*) from ledger_entries where id like 'ledgerprobe-%'")"
if [ "${LEFT:-0}" != "0" ]; then
  echo "🔴 $LEFT probe row(s) SURVIVED the rollback — the guard mutated the ledger."
  exit 1
fi
echo "   · residue 0 — every probe rolled back"

echo
echo "🟢 B5's ledger is append-only AND self-deriving, proven behaviourally:"
echo "   UPDATE, DELETE and TRUNCATE refused by name; the S4c detach still"
echo "   permitted; a detach carrying any other change refused; a tenantless"
echo "   insert refused; and balanceAfter/seq/snapshot derived by the database"
echo "   over three deliberately-wrong caller values, per bucket."
exit 0
