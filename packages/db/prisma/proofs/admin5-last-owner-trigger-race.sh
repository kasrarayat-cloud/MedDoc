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
install_shipped; echo "trigger function: advisory lock $(lock_state)"
echo "--- SUBJECT: parallel, trigger AS SHIPPED ---"
S=$(run_pair parallel); echo "$S"
echo "    expect: owners_left=1  refusals=1  B blocked ~2s  concurrency>=2"
echo
echo "--- CONTROL 1 (#205): the SAME scripts run SEQUENTIALLY ---"
C1=$(run_pair sequential); echo "$C1"
echo "    expect: owners_left=1 (IDENTICAL final state) but B_blocked ~0s and concurrency=1"
echo "    ⚠️ this is why the final state is not the proof — sequential reaches it too"
echo
install_mutant; echo "trigger function: advisory lock $(lock_state)"
echo "--- CONTROL 2 (canon 121): parallel, ADVISORY LOCK DELETED ---"
C2=$(run_pair parallel); echo "$C2"
echo "    expect: owners_left=0  refusals=0  — the invariant BREAKS without the lock"
echo
echo "--- CONTROL 3: SEQUENTIAL with the lock STILL DELETED — completes the 2x2 ---"
C3=$(run_pair sequential); echo "$C3"
echo "    expect: owners_left=1 — WITHOUT concurrency the missing lock costs nothing,"
echo "    because B's fresh snapshot sees A's COMMITTED demotion unaided."
echo "    ⚠️ THIS IS WHAT MAKES CONTROL 2 A PROOF RATHER THAN A SAMPLE. owners_left=0"
echo "    requires BOTH the missing lock AND real concurrency; three of the four cells"
echo "    hold the invariant and only the two-fault cell breaks it. The overlap column"
echo "    is uninformative in controls 2/3 — an UNBLOCKED transaction is open for"
echo "    milliseconds — so the 2x2 carries the argument, not the sampler."
echo
install_shipped; echo "restored: advisory lock $(lock_state)"
teardown
q "DROP TABLE IF EXISTS t210_sample;" >/dev/null
rm -rf "$OUT"
