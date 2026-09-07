#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# Does moving `resolveFrozenPointer`'s override read INSIDE the sign's
# SERIALIZABLE transaction make Postgres refuse the interleaving?
#
# Board: docs/foundation/board/THE-POINTER-IS-RESOLVED-OUTSIDE-THE-LOCK.md
#
# ⚠️ THIS SCRIPT EXISTS BECAUSE THE ANSWER IS NO, AND REASONING SAID YES.
# The obvious fix is to move the read inside the transaction that is already
# SERIALIZABLE. ARM A measures that fix and shows the harm surviving it: SSI
# aborts on a CYCLE, and the door is READ COMMITTED, so the return edge is
# never recorded. One edge is not a cycle. ARM B raises the door too and the
# sign correctly takes 40001.
#
#   control : a genuine two-way cycle MUST abort  -> proves SSI is live here.
#             Without it, "no 40001" and "SSI is off" are the same output and
#             every arm below would be unreadable.
#   ARM A   : door BEGIN;                         -> expect COMMITTED (the bug)
#   ARM B   : door BEGIN ISOLATION LEVEL SERIALIZABLE; -> expect 40001
#
# Read-only with respect to every real database: it creates, uses and leaves a
# throwaway `ssi_probe` db inside the QA postgres container. Production is
# never contacted.
#
# Exit: 0 = all three arms as expected, 2 = CANNOT-TELL (control did not abort).
# ════════════════════════════════════════════════════════════════════════════
# Does moving resolveFrozenPointer's override read INSIDE the sign's SERIALIZABLE
# transaction make Postgres refuse the interleaving?  Measured, not reasoned.
PSQL() { docker exec -i meddoc-qa-postgres-1 psql -U meddoc -d ssi_probe -v ON_ERROR_STOP=0 -q 2>&1; }
reset() { docker exec -i meddoc-qa-postgres-1 psql -U meddoc -d ssi_probe -q -c \
  "TRUNCATE o; DELETE FROM ctl WHERE val=999; UPDATE v SET status='READY', sv=7 WHERE id='v1';" >/dev/null 2>&1; }

echo "════════ POSITIVE CONTROL — a genuine cycle MUST abort ════════"
reset
( PSQL <<'S1'
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT sum(val) AS ctl1_read FROM ctl WHERE class=1;
SELECT pg_sleep(2);
INSERT INTO ctl (class,val) VALUES (2,999);
COMMIT;
S1
) > /tmp/ctl1.$$ 2>&1 &
( PSQL <<'S2'
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT sum(val) AS ctl2_read FROM ctl WHERE class=2;
SELECT pg_sleep(2);
INSERT INTO ctl (class,val) VALUES (1,999);
COMMIT;
S2
) > /tmp/ctl2.$$ 2>&1 &
wait
CTL=$( (cat /tmp/ctl1.$$ /tmp/ctl2.$$) | grep -c "could not serialize")
cat /tmp/ctl1.$$ /tmp/ctl2.$$ | grep -E "could not serialize|ERROR" | sed 's/^/    /'
echo "  >> control aborts: $CTL  (expected >=1)"
[ "$CTL" -ge 1 ] || { echo "  🔴 CANNOT-TELL: SSI is not detecting a cycle it must detect. Every arm below is meaningless."; exit 2; }
echo "  🟢 SSI is live in this database."

run_arm() {
  local name="$1" door_begin="$2"
  reset
  ( PSQL <<'SIGN'
BEGIN ISOLATION LEVEL SERIALIZABLE;
-- the proposed fix: resolveFrozenPointer's override read, moved INSIDE
SELECT count(*) AS overrides_seen FROM o WHERE vid='v1';
SELECT pg_sleep(4);
UPDATE v SET status='SIGNED' WHERE id='v1' AND status='READY' AND sv=7;
COMMIT;
SIGN
) > /tmp/sign.$$ 2>&1 &
  ( { echo "SELECT pg_sleep(1);"; echo "$door_begin"; \
      echo "SELECT status FROM v WHERE id='v1' FOR UPDATE;"; \
      echo "INSERT INTO o VALUES ('v1','f-42');"; echo "COMMIT;"; } | PSQL
) > /tmp/door.$$ 2>&1 &
  wait
  local aborted upd
  aborted=$(grep -c "could not serialize" /tmp/sign.$$)
  upd=$(grep -Eo "UPDATE [0-9]+" /tmp/sign.$$ | tail -1)
  echo "  sign: $( [ "$aborted" -ge 1 ] && echo '40001 SERIALIZATION FAILURE — refused' || echo "committed  ($upd)" )"
  grep -E "could not serialize" /tmp/sign.$$ | sed 's/^/      /'
  docker exec -i meddoc-qa-postgres-1 psql -U meddoc -d ssi_probe -Atc \
    "SELECT 'visit status='||status||'  overrides='||(SELECT count(*) FROM o WHERE vid='v1') FROM v WHERE id='v1';" \
    | sed 's/^/      /'
}

echo
echo "════════ ARM A — door READ COMMITTED (what the code does today) ════════"
run_arm A "BEGIN;"
echo
echo "════════ ARM B — door SERIALIZABLE too ════════"
run_arm B "BEGIN ISOLATION LEVEL SERIALIZABLE;"
rm -f /tmp/ctl1.$$ /tmp/ctl2.$$ /tmp/sign.$$ /tmp/door.$$
