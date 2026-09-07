#!/usr/bin/env bash
# ============================================================================
# RULING #210 — DOES THE TRIGGER ACTUALLY SERIALIZE? A HARNESS THAT RACES.
# ----------------------------------------------------------------------------
# ⚠️ THE ARGUMENT IS NOT THE PROOF. The migration argues that a VOLATILE plpgsql
# function takes a fresh snapshot per statement under READ COMMITTED, so the
# second racer sees the first's committed demotion. That is a sentence about
# Postgres, and a sentence is not a measurement.
#
# ⚠️ AND THE FINAL STATE CANNOT TELL YOU WHETHER IT RACED — ruling #205's whole
# point. Sequential execution ALSO ends with one owner left. The discriminator
# is the OVERLAP WITNESS, sampled from pg_stat_activity by a third connection
# that is not either racer.
#
# THE CHOREOGRAPHY (advisory-lock interleaving, which #205 permits):
#   A: BEGIN; UPDATE(demote a); sleep 3; COMMIT       <- holds the guard's lock
#   B: (starts 1s later) BEGIN; UPDATE(demote b); COMMIT
# With the lock, B BLOCKS inside the trigger until A commits, then counts on a
# fresh snapshot, sees zero owners left, and REFUSES. Without it, B never
# blocks, never sees A's uncommitted demotion, and both commit -> ZERO owners.
#
# THE MECHANISM IS ASSERTED, NOT THE OUTCOME (canon 121): control #2 DELETES
# the advisory lock and REQUIRES the race to reach zero owners. If removing the
# lock changes nothing, the lock was never doing the work.
#
# Usage: bash admin5-last-owner-trigger-race.sh
# Target: the ISOLATED meddoc-qa stack. NEVER production.
# ============================================================================
set -uo pipefail
PGC=meddoc-qa-postgres-1; DB=meddoc_qa_test; U=meddoc
HERE="$(cd "$(dirname "$0")" && pwd)"
MIGRATION="$HERE/../migrations/20260907040000_admin5_last_owner_trigger/migration.sql"
OUT="$(mktemp -d "${TMPDIR:-/tmp}/t210-race-XXXXXX")"

# ⚠️ RESTORE THE ARMED GUARD ON **ANY** EXIT, NOT JUST THE HAPPY ONE.
# This script installs a DISARMED mutant into a SHARED database as its negative
# control. Its own adversarial pass found that a Ctrl-C, a failed docker exec or
# any early return left that mutant installed — so the next person to use the QA
# stack would be running against a guard with its serialization removed, and
# nothing would say so. The trap runs before the failure is reported.
restore_guard() {
  local rc=$?
  if [ -f "$OUT/fn-shipped.sql" ]; then
    docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -q < "$OUT/fn-shipped.sql" >/dev/null 2>&1
  fi
  if [ -f "$OUT/g2.sql" ]; then
    docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -q < "$OUT/g2.sql" >/dev/null 2>&1
  fi
  local state
  state=$(docker exec -i "$PGC" psql -U "$U" -d "$DB" -Atqc \
    "SELECT count(*) FROM pg_proc WHERE proname IN ('users_last_owner_guard','users_no_orphan_member') AND prosrc LIKE '%pg_advisory_xact_lock%'" 2>/dev/null)
  if [ "$state" = "2" ]; then
    echo "🟢 guard restored (both functions armed)" >&2
  else
    echo "🔴 GUARD NOT RESTORED — $DB may still hold a DISARMED guard. Re-apply the migration by hand." >&2
    rc=1
  fi
  rm -rf "$OUT"
  exit $rc
}
trap restore_guard EXIT INT TERM

q()  { docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -Atq -c "$1"; }
qf() { docker exec -i -e PGAPPNAME="$1" "$PGC" psql -U "$U" -d "$DB" -X < "$2"; }

# ── The function under test, and its mutant. Both derived FROM THE MIGRATION,
#    never retyped — a control that re-derives its subject is not a control.
extract() { sed -n '/CREATE OR REPLACE FUNCTION users_last_owner_guard/,/^\$fn\$ LANGUAGE plpgsql;/p' "$MIGRATION"; }
install_shipped() { extract > "$OUT/fn-shipped.sql"; docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -q < "$OUT/fn-shipped.sql" >/dev/null; }
install_mutant()  {
  # Delete the four physical lines of the PERFORM pg_advisory_xact_lock(...) call.
  extract | awk '/PERFORM pg_advisory_xact_lock\(/{skip=4} skip>0{skip--; next} {print}' > "$OUT/fn-mutant.sql"
  docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -q < "$OUT/fn-mutant.sql" >/dev/null
}
lock_state() { q "SELECT CASE WHEN prosrc LIKE '%pg_advisory_xact_lock%' THEN 'PRESENT' ELSE 'REMOVED' END FROM pg_proc WHERE proname='users_last_owner_guard'"; }

# ⚠️ TEARDOWN IS ORDER-SENSITIVE, AND GETTING IT WRONG INVALIDATED TWO CONTROLS
# ON THE FIRST RUN — they raced against a fixture that had never been reset, and
# both printed a plausible-looking line. NON-ACTIVE-OWNERS FIRST, then the rest:
# once no other members remain, exemption 2 lets the final owner go. A teardown
# that needs the guard disabled would also be a teardown that cannot prove the
# guard is on.
teardown() {
  q "DELETE FROM users u WHERE u.\"practiceId\"='t210r_p' AND NOT users_is_active_owner(u);" >/dev/null
  q "DELETE FROM users WHERE \"practiceId\"='t210r_p';" >/dev/null
  q "DELETE FROM practices WHERE id='t210r_p';" >/dev/null
  local leftover=$(q "SELECT (SELECT count(*) FROM users WHERE \"practiceId\"='t210r_p') + (SELECT count(*) FROM practices WHERE id='t210r_p')")
  if [ "${leftover:-1}" != "0" ]; then
    echo "🔴 TEARDOWN FAILED — $leftover fixture rows survive. Every result below would be measured against a dirty fixture. Aborting." >&2
    exit 1
  fi
}

# ── Fixture. Teardown deletes in an order the trigger ALLOWS (clinician, then
#    the non-last owner, then the last owner of an empty practice) — the guard
#    is not disabled to clean up after itself.
fixture() {
  teardown
  q "INSERT INTO practices(id,name,slug,\"updatedAt\") VALUES ('t210r_p','T210 Race','t210-race',now());
     INSERT INTO users(id,email,\"passwordHash\",\"updatedAt\",\"practiceId\",\"practiceRole\",\"isActive\") VALUES
       ('t210r_a','t210ra@x.test','x',now(),'t210r_p','OWNER',true),
       ('t210r_b','t210rb@x.test','x',now(),'t210r_p','OWNER',true),
       ('t210r_c','t210rc@x.test','x',now(),'t210r_p','CLINICIAN',true);" >/dev/null
}
owners_left() { q "SELECT count(*) FROM users u WHERE u.\"practiceId\"='t210r_p' AND users_is_active_owner(u)"; }

q "CREATE TABLE IF NOT EXISTS t210_sample(at timestamptz, n_open int, racers text);" >/dev/null

cat > "$OUT/racer-a.sql" <<'SQL'
\set ON_ERROR_STOP 0
BEGIN;
UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210r_a';
SELECT pg_sleep(3);
COMMIT;
SQL
cat > "$OUT/racer-b.sql" <<'SQL'
\set ON_ERROR_STOP 0
BEGIN;
UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210r_b';
COMMIT;
SQL

# ── The independent overlap witness: a THIRD connection sampling the server's
#    own view. Neither racer reports on itself.
# ⚠️ THE FIRST VERSION SAMPLED VIA ONE `docker exec` PER SAMPLE — ~100ms of
#    overhead each — and reported max_concurrent=1 for a control in which the
#    overlap certainly happened, because B lived for only 0.21s. A witness that
#    misses is not a witness that refutes; it reported a LOWER BOUND in a column
#    that reads like a count. The loop now runs SERVER-SIDE in one session at
#    10ms, and records the transaction INTERVALS so overlap is computed from
#    endpoints rather than from whether a sample happened to land.
witness() {
  docker exec -i -e PGAPPNAME=t210-witness "$PGC" psql -U "$U" -d "$DB" -X -q -Atc "
    TRUNCATE t210_sample;
    DO \$\$
    DECLARE i int := 0;
    BEGIN
      WHILE i < 600 LOOP
        PERFORM pg_stat_clear_snapshot();
        INSERT INTO t210_sample(at, n_open, racers)
        SELECT clock_timestamp(), count(*), coalesce(string_agg(application_name, ',' ORDER BY application_name), '')
          FROM pg_stat_activity
         WHERE datname = current_database()
           AND application_name LIKE 't210-racer-%'
           AND xact_start IS NOT NULL;
        i := i + 1;
        PERFORM pg_sleep(0.01);
      END LOOP;
    END \$\$;" >/dev/null 2>&1
}
witness_result() {
  q "SELECT max(n_open)||'/'||count(*) FILTER (WHERE racers LIKE '%,%') FROM t210_sample"
}

run_pair() {  # $1 = parallel|sequential
  fixture
  witness & WP=$!
  local t0=$(date +%s.%N)
  if [ "$1" = parallel ]; then
    ( qf t210-racer-a "$OUT/racer-a.sql" > "$OUT/a.out" 2>&1 ) & PA=$!
    sleep 1
    local tb0=$(date +%s.%N)
    ( qf t210-racer-b "$OUT/racer-b.sql" > "$OUT/b.out" 2>&1 ) & PB=$!
    wait $PB; local tb1=$(date +%s.%N); wait $PA
  else
    qf t210-racer-a "$OUT/racer-a.sql" > "$OUT/a.out" 2>&1
    local tb0=$(date +%s.%N)
    qf t210-racer-b "$OUT/racer-b.sql" > "$OUT/b.out" 2>&1
    local tb1=$(date +%s.%N)
  fi
  wait $WP 2>/dev/null
  local ref=0
  grep -q 'users_last_owner_guard:' "$OUT/a.out" && ref=$((ref+1))
  grep -q 'users_last_owner_guard:' "$OUT/b.out" && ref=$((ref+1))
  printf '%-11s owners_left=%s  refusals=%s  B_blocked_for=%.2fs  overlap[max_open/samples_with_BOTH]=%s\n' \
    "$1" "$(owners_left)" "$ref" "$(echo "$tb1 - $tb0" | bc)" "$(witness_result)"
}

echo "=== RULING #210 — RACE HARNESS (target: meddoc-qa, NEVER production) ==="
echo
echo "############ RACE A — THE REMOVAL GUARD UNDER CONCURRENCY ############"
install_shipped; echo "trigger function: advisory lock $(lock_state)"
echo "--- SUBJECT: parallel, AS SHIPPED ---"
S=$(run_pair parallel); echo "$S"
echo "--- CONTROL A1 (#205): the SAME scripts run SEQUENTIALLY ---"
C1=$(run_pair sequential); echo "$C1"
echo "    ⚠️ IDENTICAL final state, zero overlap — this is why ruling #205 says"
echo "    the final state is not the proof. The discriminator is the witness."
echo
echo "⚠️  NOTE ON RACE A AND THE ADVISORY LOCK, STATED SO IT IS NOT MISREAD."
echo "    Deleting the advisory lock does NOT break Race A any more, because the"
echo "    guard now also takes FOR UPDATE on the sibling owner rows and THAT"
echo "    serializes this case. The lock's own control lives in Race B; a control"
echo "    that has stopped discriminating must be replaced, not quietly kept."
echo
echo "############ RACE B — WHAT THE ADVISORY LOCK IS ACTUALLY FOR ############"
echo "    Suspending a SOLO owner is legal (nobody to strand) and INSERTing a live"
echo "    member is legal (an owner exists). Run them at the same instant and the"
echo "    practice ends with a live member and NO active owner. The INSERT guard"
echo "    has no row to FOR UPDATE, so the shared advisory lock is the only thing"
echo "    that makes the two mutually exclusive."
race_b() {   # $1 = removal-guard fn, $2 = orphan-guard fn
  q_ "$1" ; q_ "$2"
  q "DELETE FROM users WHERE \"practiceId\"='ir_p'; DELETE FROM practices WHERE id='ir_p';
     INSERT INTO practices(id,name,slug,\"updatedAt\") VALUES ('ir_p','I','ir-p',now());
     INSERT INTO users(id,email,\"passwordHash\",\"updatedAt\",\"practiceId\",\"practiceRole\",\"isActive\")
       VALUES ('ir_o','iro@x.test','x',now(),'ir_p','OWNER',true);" >/dev/null
  local T; T=$(date -u -d '+2 seconds' +%Y-%m-%dT%H:%M:%S.%3NZ)
  sed "s/SENTINEL/$T/" "$OUT/rb-a.sql" > "$OUT/rb-a.run"; sed "s/SENTINEL/$T/" "$OUT/rb-b.sql" > "$OUT/rb-b.run"
  docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -q < "$OUT/rb-a.run" >/dev/null 2>&1 &
  docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -q < "$OUT/rb-b.run" >/dev/null 2>&1 &
  wait
  q "SELECT CASE WHEN count(*) FILTER (WHERE users_is_active_owner(u))=0
                  AND count(*) FILTER (WHERE users_is_live_member(u))>0 THEN 'V' ELSE '.' END
       FROM users u WHERE u.\"practiceId\"='ir_p'"
}
q_() { docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -q < "$1" >/dev/null 2>&1; }
cat > "$OUT/rb-a.sql" <<'SQL'
BEGIN;
SELECT pg_sleep(GREATEST(0, EXTRACT(EPOCH FROM (TIMESTAMPTZ 'SENTINEL' - clock_timestamp()))));
UPDATE users SET "suspendedAt"=now() WHERE id='ir_o';
COMMIT;
SQL
cat > "$OUT/rb-b.sql" <<'SQL'
BEGIN;
SELECT pg_sleep(GREATEST(0, EXTRACT(EPOCH FROM (TIMESTAMPTZ 'SENTINEL' - clock_timestamp()))));
INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
  VALUES ('ir_new','irn@x.test','x',now(),'ir_p','CLINICIAN',true);
COMMIT;
SQL
sed -n '/CREATE OR REPLACE FUNCTION users_last_owner_guard()/,/^\$fn\$ LANGUAGE plpgsql;/p' "$MIGRATION" > "$OUT/g1.sql"
sed -n '/CREATE OR REPLACE FUNCTION users_no_orphan_member()/,/^\$fn\$ LANGUAGE plpgsql;/p'  "$MIGRATION" > "$OUT/g2.sql"
awk '/PERFORM pg_advisory_xact_lock\(/{skip=4} skip>0{skip--; next} {print}' "$OUT/g1.sql" > "$OUT/g1n.sql"
awk '/PERFORM pg_advisory_xact_lock\(/{skip=4} skip>0{skip--; next} {print}' "$OUT/g2.sql" > "$OUT/g2n.sql"
# ⚠️ ASSERT THE MUTATION APPLIED. An unapplied mutation yields a green that
# proves nothing and is indistinguishable from a guard that works.
before=$(grep -c pg_advisory_xact_lock "$OUT/g1.sql" "$OUT/g2.sql" | awk -F: '{s+=$2} END{print s}')
after=$(grep -c  pg_advisory_xact_lock "$OUT/g1n.sql" "$OUT/g2n.sql" | awk -F: '{s+=$2} END{print s}')
echo "    mutation applied: advisory-lock occurrences $before -> $after"
[ "$before" = 2 ] && [ "$after" = 0 ] || { echo "🔴 MUTATION DID NOT APPLY — every result below would be meaningless."; exit 1; }
N=12
printf "    WITHOUT the lock (%d runs): " "$N"; V=0
for _ in $(seq $N); do r=$(race_b "$OUT/g1n.sql" "$OUT/g2n.sql"); printf '%s' "$r"; [ "$r" = V ] && V=$((V+1)); done
echo "   -> $V/$N VIOLATIONS"
printf "    WITH    the lock (%d runs): " "$N"; W=0
for _ in $(seq $N); do r=$(race_b "$OUT/g1.sql" "$OUT/g2.sql"); printf '%s' "$r"; [ "$r" = V ] && W=$((W+1)); done
echo "   -> $W/$N VIOLATIONS"
echo
echo "=== VERDICT ==="
echo "raceA subject   : $S"
echo "raceA control#1 : $C1"
echo "raceB           : without lock $V/$N violations, with lock $W/$N"

# ⚠️ THE HARNESS ASSERTS ITS OWN 2x2 AND EXITS NON-ZERO IF IT DOES NOT HOLD.
# Its adversarial pass found it PRINTED the numbers and asserted nothing, so it
# exited 0 even when its own negative control REFUTED the claim it exists to
# prove. A harness whose output has to be read by a human to notice a refutation
# is a harness that will be read quickly at 01:00. Every row below is a
# prediction made before the run, and a miss is a FAILURE.
fail=0
say() { echo "   $1"; }
case "$S" in
  *owners_left=1*refusals=1*) say "🟢 raceA subject held the invariant and refused once" ;;
  *) say "🔴 raceA SUBJECT: expected owners_left=1 with 1 refusal — got: $S"; fail=1 ;;
esac
case "$S" in
  *"overlap[max_open/samples_with_BOTH]=2/"*) say "🟢 raceA witnessed a real overlap" ;;
  *) say "🔴 raceA SUBJECT: no overlap witnessed — it did not actually race, so its green means nothing"; fail=1 ;;
esac
case "$C1" in
  *"overlap[max_open/samples_with_BOTH]=1/0"*) say "🟢 raceA control#1 was genuinely sequential" ;;
  *) say "🔴 raceA CONTROL#1: expected NO overlap — got: $C1"; fail=1 ;;
esac
if [ "$W" -eq 0 ]; then say "🟢 raceB: 0 violations WITH the advisory lock"
else say "🔴 raceB: $W/$N violations WITH the lock — the invariant does not hold"; fail=1; fi
if [ "$V" -gt 0 ]; then say "🟢 raceB control: $V/$N violations WITHOUT the lock — the lock is load-bearing"
else say "🔴 raceB CONTROL DID NOT FIRE: 0/$N violations without the advisory lock. Either the lock is now redundant or this control has stopped discriminating. Canon 121: delete the mechanism or delete the control — do not keep both."; fail=1; fi

if [ "$fail" -ne 0 ]; then
  echo "🔴 RACE HARNESS FAILED — a prediction above did not hold." >&2
  exit 1
fi
echo "🟢 RACE HARNESS PASSED — every predicted cell held."
q "DELETE FROM users WHERE \"practiceId\"='ir_p'; DELETE FROM practices WHERE id='ir_p';" >/dev/null
teardown
q "DROP TABLE IF EXISTS t210_sample;" >/dev/null
# the EXIT trap restores the armed guard and removes $OUT
