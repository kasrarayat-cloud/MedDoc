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
# ⚠️ THE CONTAINER IS RESOLVED, NOT ASSUMED, AND THE LOOKUP IS THE POSITIVE
# CONTROL ON THE INSTRUMENT. `docker-compose.qa.yml` pins `name: meddoc-qa`, so
# the literal happens to be right here and on a runner — but a name that is
# right by coincidence is one rename from a harness that silently measures
# nothing. Derive it, then assert it answers.
DB=meddoc_qa_test; U=meddoc
PGC="${PGC:-$(docker compose -f "$(dirname "${BASH_SOURCE[0]}")/../../../../docker-compose.qa.yml" ps -q postgres 2>/dev/null | head -1)}"
[ -n "$PGC" ] || PGC=meddoc-qa-postgres-1
if ! docker exec -i "$PGC" psql -U "$U" -d "$DB" -Atqc 'SELECT 1' >/dev/null 2>&1; then
  echo "🔴 race harness: cannot reach postgres as '$PGC'. Refusing — a harness that cannot" >&2
  echo "   query the database would report 0 violations for both arms and read as a clean run." >&2
  exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
MIGRATION="$HERE/../migrations/20260907040000_admin5_last_owner_trigger/migration.sql"
OUT="$(mktemp -d "${TMPDIR:-/tmp}/t210-race-XXXXXX")"

# ⚠️ RESTORE THE ARMED GUARD ON **ANY** EXIT, NOT JUST THE HAPPY ONE.
# This script installs a DISARMED mutant into a SHARED database as its negative
# control. Its own adversarial pass found that a Ctrl-C, a failed docker exec or
# any early return left that mutant installed — so the next person to use the QA
# stack would be running against a guard with its serialization removed, and
# nothing would say so. The trap runs before the failure is reported.
# ⚠️ THE FIXTURE IS REAPED ON **EVERY** EXIT PATH — RULING #253.
#
# This ran only after `🟢 RACE HARNESS PASSED`, at the very bottom of the script.
# Every other exit left `ir_p`, `t210r_p` and the two scratch tables behind: a
# refuted prediction (exit 1), a Ctrl-C, a failed docker exec — and **exit 2,
# which CI treats as a PASSING step** and which is followed in the same job by
# the guarded seed and the entire E2E suite, against a database now holding a
# practice whose only member is a suspended owner.
#
# ⚠️ THE SUCCESS PATH IS THE ONE PATH THAT DID NOT NEED IT. Cleanup written at
# the end of the happy path is cleanup that runs exactly when nothing went wrong.
reap_fixture() {
  docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -Atq >/dev/null 2>&1 <<'REAP'
DELETE FROM users u WHERE u."practiceId" IN ('t210r_p','ir_p') AND NOT users_is_active_owner(u);
DELETE FROM users WHERE "practiceId" IN ('t210r_p','ir_p');
DELETE FROM practices WHERE id IN ('t210r_p','ir_p');
DROP TABLE IF EXISTS t210_sample;
DROP TABLE IF EXISTS t210_window;
REAP
  docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -Atqc \
    "SELECT (SELECT count(*) FROM users WHERE \"practiceId\" IN ('t210r_p','ir_p'))
          + (SELECT count(*) FROM practices WHERE id IN ('t210r_p','ir_p'))
          + (SELECT count(*) FROM pg_tables WHERE tablename IN ('t210_sample','t210_window'))" 2>/dev/null
}

restore_guard() {
  local rc=$?
  if [ "${t210_signalled:-0}" = "1" ]; then
    echo "RACE_CANNOT_TELL_REASON=terminated"
    echo "🟡 RACE HARNESS TERMINATED MID-RUN — it never reached its verdict. Exit 2 is CANNOT-TELL, and the reason is not 'no_overlap', so CI must fail this." >&2
    rc=2
  fi
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
  # ⚠️ REAPED HERE, AND THE REAP ASSERTS ITSELF. A cleanup that reports nothing
  # is a claim; the count is what makes it evidence.
  local left
  left=$(reap_fixture)
  if [ "${left:-1}" = "0" ]; then
    echo "🟢 fixture reaped (0 rows, 0 scratch tables)" >&2
  else
    echo "🔴 FIXTURE NOT REAPED — ${left:-?} artifact(s) survive in $DB, which the seed and the E2E suite use next." >&2
    rc=1
  fi
  rm -rf "$OUT"
  exit $rc
}
# ⚠️ A TERMINATION IS NOT A PASS — RULING #251, GAP (4).
#
# `restore_guard` opens with `local rc=$?`, and when a trap fires on a SIGNAL
# bash reports the LAST COMMAND's status, not the signal. So a SIGTERM arriving
# after any successful command produced `rc=0` and the harness exited **0** —
# and CI's own `case` then printed "race harness PASSED — every predicted cell
# held" for a run that never reached its verdict.
#
# ⚠️ EXIT 2 RATHER THAN 1, AND THAT IS DELIBERATE: a termination is a
# CANNOT-TELL, not a refutation. But the reason it prints is `terminated`, NOT
# `no_overlap` — and the CI step greps for `no_overlap` specifically, so this
# path FAILS the job. Cannot-tell for an unstated reason is a failure (#240e).
t210_signalled=0
trap 't210_signalled=1' INT TERM
trap restore_guard EXIT

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

q "CREATE TABLE IF NOT EXISTS t210_sample(at timestamptz, n_open int, racers text);
     CREATE TABLE IF NOT EXISTS t210_window(who text primary key, t0 timestamptz, t1 timestamptz);" >/dev/null

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
witness() {   # $1 = samples at 10ms (default 600)
  local budget="${1:-600}"
  docker exec -i -e PGAPPNAME=t210-witness "$PGC" psql -U "$U" -d "$DB" -X -q -Atc "
    TRUNCATE t210_sample;
    DO \$\$
    DECLARE i int := 0;
    BEGIN
      WHILE i < $budget LOOP
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
     TRUNCATE t210_window;
     INSERT INTO practices(id,name,slug,\"updatedAt\") VALUES ('ir_p','I','ir-p',now());
     INSERT INTO users(id,email,\"passwordHash\",\"updatedAt\",\"practiceId\",\"practiceRole\",\"isActive\")
       VALUES ('ir_o','iro@x.test','x',now(),'ir_p','OWNER',true);" >/dev/null
  local T; T=$(date -u -d '+2 seconds' +%Y-%m-%dT%H:%M:%S.%3NZ)
  sed "s/SENTINEL/$T/" "$OUT/rb-a.sql" > "$OUT/rb-a.run"; sed "s/SENTINEL/$T/" "$OUT/rb-b.sql" > "$OUT/rb-b.run"
  # ⚠️ THE SAME INDEPENDENT WITNESS RACE A USES — RULING #240d.
  #
  # Race B used to time itself with `t210_window`, a table each racer wrote
  # INSIDE its own transaction. When the lock does its job the guard REFUSES B,
  # B's transaction rolls back — AND ITS WITNESS ROW ROLLS BACK WITH IT. So the
  # WITH-lock arm could never report an overlap: `count(*)=2` was unreachable by
  # construction, and the cell ruling #220 rests on was structurally unable to
  # show that its two transactions had ever met.
  #
  # ⚠️ A WITNESS THAT LIVES INSIDE THE THING IT WITNESSES DISAPPEARS EXACTLY WHEN
  # THE ANSWER MATTERS. Race A already had the cure — a THIRD connection sampling
  # `pg_stat_activity` — and race B simply never used it. Its racers were not even
  # given an application_name, so the sampler could not have seen them.
  docker exec -i -e PGAPPNAME=t210-racer-a "$PGC" psql -U "$U" -d "$DB" -X -At < "$OUT/rb-a.run" > "$OUT/a.marks" 2>&1 &
  local PA=$!
  docker exec -i -e PGAPPNAME=t210-racer-b "$PGC" psql -U "$U" -d "$DB" -X -At < "$OUT/rb-b.run" > "$OUT/b.marks" 2>&1 &
  local PB=$!
  wait $PA; wait $PB
  # ⚠️ THE VERDICT AND THE WITNESS TOGETHER. "No violation" is ambiguous on its
  # own — it means the guard worked OR the two never overlapped — and those are
  # different facts. The window rows come from the racers' own transactions, so
  # overlap is MEASURED rather than inferred from the fact that we launched two
  # processes.
  local v ov
  v=$(q "SELECT CASE WHEN count(*) FILTER (WHERE users_is_active_owner(u))=0
                      AND count(*) FILTER (WHERE users_is_live_member(u))>0 THEN 'V' ELSE '.' END
           FROM users u WHERE u.\"practiceId\"='ir_p'")
  # ⚠️ OVERLAP FROM THE MARKERS, and CANNOT-TELL when a marker is missing.
  # Four numbers or nothing: a witness that lost a mark must say so, never
  # default to 'no overlap' (which reads as a clean control) or to 'overlap'
  # (which reads as a valid cell). '?' is neither.
  ov=$(awk '
    /T210MARK/ { split($0,f," "); m[f[2] "_" f[3]] = f[4]+0 }
    END {
      if (!("A_ENTRY" in m) || !("A_EXIT" in m) || !("B_ENTRY" in m) || !("B_EXIT" in m)) { print "?"; exit }
      ae=m["A_ENTRY"]; ax=m["A_EXIT"]; be=m["B_ENTRY"]; bx=m["B_EXIT"];
      lo = (ae>be)?ae:be; hi = (ax<bx)?ax:bx;
      print (lo < hi) ? "o" : "-"
    }' "$OUT/a.marks" "$OUT/b.marks")
  printf '%s%s' "$v" "$ov"
}
q_() { docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -q < "$1" >/dev/null 2>&1; }
# ⚠️ THE WITNESS IS AUTONOMOUS — RULING #252. TWO PREDECESSORS FAILED HERE, IN
# OPPOSITE DIRECTIONS, AND BOTH FAILURES WERE INVISIBLE UNTIL SOMEBODY KILLED
# THE INSTRUMENT.
#
#   1. `t210_window` wrote each racer's interval INSIDE its own transaction. When
#      the lock works the guard REFUSES B and B's marker rolls back with it, so
#      the WITH-lock cell could never report an overlap — 0/12, structurally.
#   2. The `pg_stat_activity` sampler that replaced it counted the `pg_sleep`
#      SYNCHRONISATION WAIT as overlap: 4091 of 4209 sampled instants were both
#      racers ASLEEP and 16 had both inside the conflicting statement. A sampler
#      killed 1.4s BEFORE either racer executed still reported 12/12.
#
# So the markers now travel on **stdout**, which no rollback can reach, and they
# bracket the CONFLICTING STATEMENT ONLY — the sleep finishes before the ENTRY
# mark is printed, so the starting gun cannot contribute a single microsecond.
#
# ⚠️ `ON_ERROR_ROLLBACK` IS A STATED APPROXIMATION AND IT IS LOAD-BEARING. It
# wraps each statement in an implicit SAVEPOINT so the EXIT mark still prints
# after a REFUSED statement — without it the refusal aborts the transaction and
# the losing racer, the one whose timing matters most, reports nothing.
#
# ⚠️ THE JUSTIFICATION THAT STOOD HERE WAS FALSE, AND IT WAS FALSE ABOUT
# POSTGRES ITSELF. It read: "`pg_advisory_xact_lock` and the row locks are
# TRANSACTION-scoped, so a savepoint does not release them". **A savepoint
# rollback DOES release an advisory xact lock.** Measured, twice, two ways:
#
#     BEGIN; SAVEPOINT s1;
#     SELECT pg_advisory_xact_lock(424242,1);
#     SELECT count(*) FROM pg_locks WHERE locktype='advisory'
#       AND pid=pg_backend_pid() AND classid=424242;      -->  1
#     ROLLBACK TO SAVEPOINT s1;
#     SELECT count(*) FROM pg_locks WHERE ... classid=424242;  -->  0
#
#   and inside a plpgsql BEGIN…EXCEPTION block, which is what ON_ERROR_ROLLBACK
#   models: "inside the block, after taking it: 1" / "after the block aborted: 0".
#
# ⚠️ THE CONCLUSION SURVIVES AND THE REASON DID NOT, WHICH IS THE WORSE OF THE
# TWO WAYS TO BE RIGHT. The race is still unchanged, for a reason that has to be
# stated properly:
#
#   · the lock is released only AFTER the guard has already refused, i.e. after
#     serialization has done the whole of its work — the losing racer blocked on
#     the winner's lock, waited, acquired, and was refused, all before its
#     statement's savepoint unwinds;
#   · and a rollback releases only THAT racer's own lock, never the other's, so
#     no racer can be let past by the other's unwinding.
#
# The check below is here so the claim is measured on every run rather than
# believed: it is the same probe, inline, and it FAILS THE HARNESS if Postgres
# ever behaves differently than this comment says.
assert_savepoint_semantics() {
  local got
  got=$(docker exec -i "$PGC" psql -U "$U" -d "$DB" -X -Atq <<'PROBE'
BEGIN;
SAVEPOINT s1;
SELECT pg_advisory_xact_lock(424242, 1);
ROLLBACK TO SAVEPOINT s1;
SELECT count(*) FROM pg_locks
 WHERE locktype='advisory' AND pid=pg_backend_pid() AND classid=424242;
ROLLBACK;
PROBE
)
  got=$(printf '%s' "$got" | tr -d '[:space:]' | tail -c 1)
  if [ "$got" != "0" ]; then
    echo "🔴 SAVEPOINT SEMANTICS CHANGED — a savepoint rollback no longer releases the advisory lock (read '$got', expected 0). The comment above and the ON_ERROR_ROLLBACK approximation must both be re-derived before this harness is trusted." >&2
    return 1
  fi
  echo "   savepoint probe: a savepoint rollback RELEASES the advisory lock (0 held) — as documented above" >&2
  return 0
}
cat > "$OUT/rb-a.sql" <<'SQL'
\set ON_ERROR_ROLLBACK on
BEGIN;
SELECT pg_sleep(GREATEST(0, EXTRACT(EPOCH FROM (TIMESTAMPTZ 'SENTINEL' - clock_timestamp()))));
SELECT 'T210MARK A ENTRY ' || extract(epoch from clock_timestamp());
UPDATE users SET "suspendedAt"=now() WHERE id='ir_o';
SELECT 'T210MARK A EXIT ' || extract(epoch from clock_timestamp());
COMMIT;
SQL
cat > "$OUT/rb-b.sql" <<'SQL'
\set ON_ERROR_ROLLBACK on
BEGIN;
SELECT pg_sleep(GREATEST(0, EXTRACT(EPOCH FROM (TIMESTAMPTZ 'SENTINEL' - clock_timestamp()))));
SELECT 'T210MARK B ENTRY ' || extract(epoch from clock_timestamp());
INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
  VALUES ('ir_new','irn@x.test','x',now(),'ir_p','CLINICIAN',true);
SELECT 'T210MARK B EXIT ' || extract(epoch from clock_timestamp());
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

# ⚠️ THE SAVEPOINT CLAIM IS MEASURED ON EVERY RUN, NOT BELIEVED. The comment
# above race B's scripts documents what a savepoint rollback does to an advisory
# lock — because the previous version of that comment said the OPPOSITE and was
# wrong about Postgres. A documented fact nobody re-measures is the next stale
# comment.
assert_savepoint_semantics || { echo "🔴 refusing to report a race whose stated semantics no longer hold." >&2; exit 1; }
N=12
# ⚠️ THREE OUTCOMES PER RUN, NOT TWO — RULING #252. A run whose markers did not
# both arrive is '?', and '?' is counted SEPARATELY. Folding it into "did not
# overlap" would make a dead witness look like a clean sequential control; folding
# it into "overlapped" would make it look like a valid cell. Neither is true.
printf "    WITHOUT the lock (%d runs): " "$N"; V=0; OV=0; QV=0
for _ in $(seq $N); do r=$(race_b "$OUT/g1n.sql" "$OUT/g2n.sql"); printf '%s' "$r"
  case "$r" in V*) V=$((V+1));; esac
  case "$r" in *o) OV=$((OV+1));; *\?) QV=$((QV+1));; esac; done
echo "   -> $V/$N VIOLATIONS, $OV/$N overlapped, $QV/$N no-witness"
printf "    WITH    the lock (%d runs): " "$N"; W=0; OW=0; QW=0
for _ in $(seq $N); do r=$(race_b "$OUT/g1.sql" "$OUT/g2.sql"); printf '%s' "$r"
  case "$r" in V*) W=$((W+1));; esac
  case "$r" in *o) OW=$((OW+1));; *\?) QW=$((QW+1));; esac; done
echo "   -> $W/$N VIOLATIONS, $OW/$N overlapped, $QW/$N no-witness"
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
cannot_tell=0
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
# ⚠️ THE WITH-LOCK CELL READS ITS OWN WITNESS — RULING #240d.
#
# This was `if [ "$W" -eq 0 ]` and nothing else. `OW` — the count of WITH-lock
# runs that genuinely overlapped — was computed, printed, and NEVER READ. So the
# one cell ruling #220 rests on ("0/12 violations WITH the lock") passed on a
# machine where the two transactions never met, which is not evidence the lock
# works: it is evidence the lock was never asked.
#
# ⚠️ AND IT IS THE CELL WHERE A VACUOUS PASS IS MOST EXPENSIVE, because it is the
# one quoted as proof. The WITHOUT-lock cell already had this check; the cell
# that matters did not.
if [ "$W" -gt 0 ]; then
  say "🔴 raceB: $W/$N violations WITH the lock — the invariant does not hold"; fail=1
elif [ "$QW" -gt 0 ]; then
  # ⚠️ A DEAD WITNESS IS A FAILURE, NOT A CANNOT-TELL — RULING #252. "The race
  # did not happen" is survivable; "my instrument lost a marker" is not, and
  # collapsing the two is exactly how a broken harness rides a CI pass.
  say "🔴 raceB: $QW/$N runs produced NO WITNESS — the instrument is broken, not the race. Refusing to report this cell either way."; fail=1
elif [ "$OW" -eq 0 ]; then
  say "🟡 raceB WITH-LOCK CELL CANNOT TELL: 0/$N violations, 0/$N overlapped and every witness reported — the two transactions genuinely did not meet."
  cannot_tell=1
else
  say "🟢 raceB: 0 violations WITH the advisory lock, and $OW/$N runs genuinely overlapped INSIDE the conflicting statement"
fi
# ⚠️ THREE STATES, BECAUSE "THE CONTROL DID NOT FIRE" HAS TWO CAUSES AND THEY
# ARE NOT THE SAME FINDING. Exit 2 is CANNOT-TELL, not refusal — the house
# convention, and the distinction canon 119 demands: a probe that answers
# correctly about the wrong universe is not a probe that answers.
if [ "$QV" -gt 0 ]; then
  say "🔴 raceB control: $QV/$N runs produced NO WITNESS — the control cannot be read."; fail=1
elif [ "$V" -gt 0 ]; then
  say "🟢 raceB control: $V/$N violations WITHOUT the lock — the lock is load-bearing"
elif [ "$OV" -eq 0 ]; then
  say "🟡 raceB INCONCLUSIVE: 0/$N violations AND 0/$N overlapped — the two transactions never met on this machine, so the control was never given the chance to fire. This is NOT evidence the lock is redundant; it is evidence the race did not happen here. Re-run, or widen the sentinel delay."
  cannot_tell=1
else
  say "🔴 raceB CONTROL DID NOT FIRE: 0/$N violations WITHOUT the lock, but $OV/$N runs DID overlap — so the race happened and the invariant held anyway. Either the lock is now redundant or this control has stopped discriminating. Canon 121: delete the mechanism or delete the control — do not keep both."
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "🔴 RACE HARNESS FAILED — a prediction above did not hold." >&2
  exit 1
fi
if [ "$cannot_tell" -ne 0 ]; then
  # ⚠️ A MACHINE-READABLE REASON, AND CI IS REQUIRED TO SEE IT — RULING #240e.
  #
  # Exit 2 means CANNOT-TELL. CI may treat that as a pass ONLY when the reason is
  # that the two transactions genuinely never met — never as a catch-all. Every
  # OTHER way of not being able to tell (a dead control, a refuted prediction, a
  # missing container, a mutation that did not apply) exits 1 above and stays a
  # failure.
  #
  # ⚠️ WITHOUT THIS LINE THE EXIT CODE IS AMBIGUOUS IN THE DIRECTION THAT COSTS:
  # "cannot tell because they did not overlap" and "cannot tell because my
  # instrument is dead" are different facts, and only the first is survivable.
  echo "RACE_CANNOT_TELL_REASON=no_overlap"
  echo "🟡 RACE HARNESS CANNOT TELL — the race did not occur on this machine. Exit 2 is not a pass and not a refutation." >&2
  exit 2
fi
echo "🟢 RACE HARNESS PASSED — every predicted cell held."
# ⚠️ NO CLEANUP HERE ANY MORE — the EXIT trap reaps the fixture and restores the
# armed guard on EVERY path, including this one. Duplicating it here would make
# the success path the only tested one, which is how it came to be the only
# path that had it.exit
