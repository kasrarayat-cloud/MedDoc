#!/usr/bin/env bash
# ============================================================================
# ADMIN-4 — DOES `platform_rates` STILL ENFORCE #178, IN THE DATABASE?
# ----------------------------------------------------------------------------
#     platform_rates_stamp_created_before_insert   createdAt + effectiveFrom
#                                                  + THE PREVIOUS PAIR (derived)
#     platform_rates_no_update                     refuses UPDATE (one hole)
#     platform_rates_no_delete                     refuses DELETE
#     platform_rates_no_truncate                   refuses TRUNCATE
#
# ⚠️ WHY A SCRIPT AND NOT A TEST. `gate-admin4-platform-rate.test.ts` reads the
# migration as TEXT, because CI has no Postgres. A source read cannot tell you
# that a trigger is INSTALLED, ENABLED, or that it does what its body says — and
# Prisma has no syntax for a trigger, so a regenerated migration silently omits
# all four and `prisma migrate diff` reports no drift. `check-ledger-append-only.sh`
# makes exactly this split one table over, and states the cost: *"every test
# green. The only observable difference is that money can now be edited."*
#
# ⚠️ AND FOUR OF THE FIVE ARMS BELOW EXIST BECAUSE THE SOURCE-ONLY GATE COULD NOT
# SEE THE DEFECT. Round 5's refutation pass found, on a database with this
# migration applied byte-for-byte, that a rate row could record a previous value
# that was never in effect; that a legal in-bounds margin was refused with an
# unnamed `integer out of range`; and that a TAB was an accepted actor. The
# shipped gate was green throughout all three, because it asserted that
# CONSTRAINT NAMES appear in the file.
#
# ── ARMS ───────────────────────────────────────────────────────────────────
#
#   STRUCTURAL (always, READ-ONLY, safe on production)
#     All four triggers exist BY NAME **and** are enabled ('O' in tgenabled),
#     and all five CHECKs exist by name. ⚠️ Name alone is not enough:
#     `ALTER TABLE … DISABLE TRIGGER` leaves the row in `pg_trigger` and stops it
#     firing, which passes a name-only check and enforces nothing.
#
#   DERIVATION (--attempt)
#     The four inserts round 5 measured as producing a FALSE HISTORY are
#     attempted, with deliberately wrong `previous*` values, and the stored rows
#     must show the DERIVED pair instead. This is the arm that proves the trigger
#     IGNORES the caller rather than trusting it — a trigger that merely
#     VALIDATED would reject these inserts, which is a different (weaker)
#     contract.
#
#   BOUNDS (--attempt)
#     Every case in `scripts/fixtures/platform-rate-bounds-cases.json` is
#     attempted, and the database's answer must match the `usable` flag — the
#     SAME file the TypeScript arm drives `isUsableMargin` with. ⚠️ THIS IS THE
#     CLASS FIX for "#178's bound encoded twice in two places free to drift":
#     widening a hand-written list closes instances, deriving both sides from one
#     list closes the class. A refusal must also NAME `platform_rates_margin_bounds`
#     — an unnamed `integer out of range` is the round-5 defect and FAILS here.
#
#   ACTOR (--attempt)
#     Every blank the round-5 finding measured as ACCEPTED is attempted and must
#     be refused, plus positive controls (an email, a CJK name, a Cyrillic name,
#     an accented name) which must be ACCEPTED. Without those a constraint that
#     refused every actor would score full marks while making ADMIN-4's writer
#     unusable — the same trap `check-ledger-append-only.sh` names.
#
#   REFUSAL (--attempt)
#     UPDATE, DELETE and TRUNCATE are each attempted and each must be refused BY
#     THIS TABLE'S OWN MESSAGE, not merely by "an error happened". Plus the
#     POSITIVE CONTROL that the one PERMITTED update — the `ON DELETE SET NULL`
#     detach — still succeeds, or the trigger holds account deletion hostage.
#
# ⚠️ EVERY WRITE IS INSIDE `BEGIN … ROLLBACK`. AGENTS.md, earned on 2026-08-05
# when a mutation proof dropped a live constraint and nulled 21 signers: "any
# write inside a gate that a constraint is supposed to refuse belongs in
# BEGIN; … ROLLBACK;. Then the attempt is observable and never consequential."
# Residue is asserted at the end, on a fresh connection.
#
# ── USAGE ──────────────────────────────────────────────────────────────────
#   bash scripts/check-platform-rates-invariants.sh                # structural
#   bash scripts/check-platform-rates-invariants.sh --attempt      # + behaviour
#   PSQL='docker exec -i <container> psql -U postgres -d <db>' \
#     bash scripts/check-platform-rates-invariants.sh --attempt
# ============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASES="$HERE/fixtures/platform-rate-bounds-cases.json"

ATTEMPT=0
for a in "$@"; do [ "$a" = "--attempt" ] && ATTEMPT=1; done

# The connection. Override with PSQL for a throwaway container.
PSQL="${PSQL:-psql -v ON_ERROR_STOP=0 -q}"

fails=0
cannot=0
pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fails=$((fails + 1)); }
# ⚠️ ROUND 6 — A THIRD OUTCOME. An arm whose FIXTURE could not be built has not
# measured the property, and reporting it as FAIL blames the trigger for the
# instrument's defect — the exact false diagnosis round 6 found ("this trigger
# holds account deletion hostage" on a trigger that detaches correctly).
unknown() { printf '  \033[33m????\033[0m  %s\n' "$1"; cannot=$((cannot + 1)); }

q() { $PSQL -tAc "$1" 2>&1; }

# --------------------------------------------------------------------------
echo '── POSITIVE CONTROL ON THE INSTRUMENT ─────────────────────────────────'
# ⚠️ A BROKEN CONNECTION AND A CLEAN DATABASE PRODUCE THE SAME ZERO. Every
# count below is meaningless until this answers, so it runs first and exits.
probe="$(q "SELECT to_regclass('public.platform_rates') IS NOT NULL")"
if [ "$probe" != "t" ]; then
  fail "cannot reach platform_rates (psql said: ${probe})"
  echo
  echo "CANNOT TELL — refusing to report a green from an instrument that is not answering."
  exit 2
fi
pass "the runner reaches public.platform_rates"

# --------------------------------------------------------------------------
echo '── STRUCTURAL (read-only) ─────────────────────────────────────────────'
for t in platform_rates_stamp_created_before_insert platform_rates_no_update \
         platform_rates_no_delete platform_rates_no_truncate; do
  en="$(q "SELECT tgenabled FROM pg_trigger WHERE tgrelid='\"platform_rates\"'::regclass AND tgname='${t}'")"
  # ⚠️ ROUND 6 — 'A' (ENABLE ALWAYS) IS ENABLED, AND STRONGER THAN 'O'. It fires
  # even under `session_replication_role = replica`, where an 'O' trigger does
  # not — measured: at 'A' an UPDATE under replica was refused by this table's
  # own message; at 'O' the same UPDATE went through. Failing 'A' rejected a
  # configuration strictly stronger than the one this accepts, and "a check that
  # fails when the thing it guards starts working is a check nobody keeps".
  # 'D' (disabled) and 'R' (fires ONLY in replica mode — never in an ordinary
  # session) enforce nothing an ordinary writer meets, and still fail.
  case "$en" in
    O) pass "trigger ${t} exists and is ENABLED" ;;
    A) pass "trigger ${t} exists and is ENABLED ALWAYS (fires even under replica)" ;;
    '') fail "trigger ${t} is MISSING" ;;
    D) fail "trigger ${t} exists but is DISABLED (tgenabled='D') — it enforces nothing" ;;
    R) fail "trigger ${t} is ENABLE REPLICA only (tgenabled='R') — an ordinary session never fires it" ;;
    *) unknown "trigger ${t} has an unrecognised tgenabled='${en}' — not a pass" ;;
  esac
done

for c in platform_rates_margin_bounds platform_rates_previous_pair \
         platform_rates_actor_present platform_rates_previous_bounds \
         platform_rates_forward_only; do
  n="$(q "SELECT count(*) FROM pg_constraint WHERE conrelid='\"platform_rates\"'::regclass AND contype='c' AND conname='${c}'")"
  [ "$n" = "1" ] && pass "CHECK ${c} present" || fail "CHECK ${c} MISSING"
done

# ⚠️ THE int4 OVERFLOW IS VISIBLE IN THE STORED PREDICATE, so it is checked
# structurally too — a database restored from a pre-round-5 dump carries the
# int4 form and every bounds arm below would then fail with an unnamed 22003.
for c in platform_rates_margin_bounds platform_rates_previous_bounds; do
  def="$(q "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='\"platform_rates\"'::regclass AND conname='${c}'")"
  case "$def" in
    *"(5)::bigint"*|*"5::bigint"*) pass "${c} cross-multiplies in bigint" ;;
    *) fail "${c} still multiplies in int4 — it refuses legal margins with an unnamed 22003: ${def}" ;;
  esac
done

# ⚠️ ROUND 6 — EVERY FUNCTION RUNS WITH A PINNED search_path, READ FROM THE LIVE
# CATALOGUE. Unpinned, a caller's TEMP `platform_rates` supplied the derived
# previous pair, and a `public.clock_timestamp()` back-dated a rate with every
# trigger still enabled. Read here rather than from the migration file because
# a later `CREATE OR REPLACE` is invisible to the file and visible to pg_proc.
for f in platform_rates_stamp_created platform_rates_append_only platform_rates_no_truncate; do
  cfg="$(q "SELECT coalesce(array_to_string(proconfig, ';'), '') FROM pg_proc WHERE oid = to_regprocedure('${f}()')")"
  case "$cfg" in
    *"search_path=pg_catalog, public, pg_temp"*) pass "${f} pins search_path (pg_catalog first, pg_temp last)" ;;
    *) fail "${f} resolves names through the CALLER's search_path (proconfig: '${cfg}')" ;;
  esac
done

# ⚠️ ROUND 6 — AND THE LIVE BODY REFUSES ABOVE READ COMMITTED, THEN LOCKS, THEN
# STAMPS. Measured with the stamp before the lock: 80 of 4800 derived pairs false
# at the DEFAULT isolation with 16 honest writers; with the lock first, 0. The
# body is read with its `--` comments STRIPPED, because the comments name every
# one of these words — a probe whose pattern appears in the prose cannot fail.
order="$(q "SELECT CASE
    WHEN s IS NULL                                            THEN 'MISSING'
    WHEN position('transaction_isolation' in s) = 0           THEN 'NO_ISOLATION_REFUSAL'
    WHEN position('pg_advisory_xact_lock' in s) = 0           THEN 'NO_LOCK'
    WHEN position('NEW.\"createdAt\" :=' in s) = 0            THEN 'NO_STAMP'
    WHEN position('transaction_isolation' in s) > position('pg_advisory_xact_lock' in s) THEN 'LOCK_BEFORE_ISOLATION_CHECK'
    WHEN position('pg_advisory_xact_lock' in s) > position('NEW.\"createdAt\" :=' in s)  THEN 'STAMP_BEFORE_LOCK'
    ELSE 'ISOLATION_LOCK_STAMP' END
  FROM (SELECT regexp_replace(prosrc, '--[^\n]*', '', 'g') AS s FROM pg_proc
         WHERE oid = to_regprocedure('platform_rates_stamp_created()')) x")"
case "$order" in
  ISOLATION_LOCK_STAMP) pass "the live derivation refuses above READ COMMITTED, then locks, then stamps createdAt" ;;
  *) fail "the live derivation is out of order (${order}) — honest concurrent writers can record a false previous pair" ;;
esac

if [ "$ATTEMPT" = "0" ]; then
  echo
  echo "structural only. Re-run with --attempt on a QA/test database for the behavioural arms."
  # ⚠️ ROUND 6 — THIS EXIT IGNORED THE CANNOT-TELL COUNT, AND ITS OWN MUTATION
  # PROOF FOUND IT: with the 'A' acceptance removed, an 'A' trigger fell to
  # `unknown` and the structural run still exited 0 — an arm that could not tell
  # reported as a pass. Same three outcomes as the full run, in the same order.
  [ "$fails" != "0" ] && exit 1
  [ "$cannot" != "0" ] && { echo "CANNOT TELL — ${cannot} arm(s) could not decide. Not a pass."; exit 2; }
  exit 0
fi

# --------------------------------------------------------------------------
echo '── DERIVATION — the caller does not get an opinion (--attempt) ────────'
# The four inserts round 5 measured as producing a permanent FALSE HISTORY.
derived="$(q "
BEGIN;
INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\") VALUES ('r5R1',3,2,'op@x');
INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\",\"previousNumerator\",\"previousDenominator\") VALUES ('r5R2',4,1,'op@x',5,1);
INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\") VALUES ('r5R3',2,1,'op@x');
INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\",\"previousNumerator\",\"previousDenominator\") VALUES ('r5R4',3,1,'op@x',1,1);
SELECT string_agg(id||'='||coalesce(\"previousNumerator\"||'/'||\"previousDenominator\",'null'), ' ' ORDER BY \"createdAt\")
  FROM platform_rates WHERE id LIKE 'r5R%';
ROLLBACK;")"
# r5R1 has no predecessor ONLY on an empty table; on a seeded one it inherits the
# live rate, so the assertion is on the CHAIN, which holds either way.
case "$derived" in
  *"r5R2=3/2"*) pass "a caller-claimed previous of 5/1 was DISCARDED and derived as 3/2" ;;
  *) fail "the previous pair is still a caller claim: ${derived}" ;;
esac
case "$derived" in
  *"r5R3=4/1"*) pass "a second change with NO pair was derived as 4/1, not left null" ;;
  *) fail "a non-first change carried no previous pair: ${derived}" ;;
esac
case "$derived" in
  *"r5R4=2/1"*) pass "a caller-claimed previous of 1/1 was DISCARDED and derived as 2/1" ;;
  *) fail "the previous pair is still a caller claim: ${derived}" ;;
esac

PR_COLS="id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\""

# --------------------------------------------------------------------------
echo '── ORDER — the previous pair follows marginAt’s own order (--attempt) ─'
# ⚠️ ROUND 6 — every insert in the DERIVATION arm above has effectiveFrom equal to
# createdAt, so `ORDER BY "effectiveFrom" DESC, "createdAt" DESC` and a plausible
# "newest row" rewrite (`ORDER BY "createdAt" DESC`) agree on all of them —
# measured, the rewrite passed every arm. A row SCHEDULED ahead separates them:
# A 3/2; S 5/1 effective +400ms; B 2/1; wait; C. At C's createdAt S is in effect
# (marginAt says 5/1); `createdAt DESC` records B (2/1). The reference is
# computed with marginAt's order in the same transaction, not hard-coded alone.
ord="$(q "BEGIN;
INSERT INTO platform_rates (${PR_COLS}) VALUES ('r6oA',3,2,'op@x');
INSERT INTO platform_rates (${PR_COLS},\"effectiveFrom\") VALUES ('r6oS',5,1,'op@x', clock_timestamp() + interval '400 milliseconds');
INSERT INTO platform_rates (${PR_COLS}) VALUES ('r6oB',2,1,'op@x');
SELECT pg_sleep(0.6);
INSERT INTO platform_rates (${PR_COLS}) VALUES ('r6oC',4,1,'op@x');
SELECT 'PREV=' || \"previousNumerator\" || '/' || \"previousDenominator\" FROM platform_rates WHERE id='r6oC';
SELECT 'REF=' || p.\"marginNumerator\" || '/' || p.\"marginDenominator\"
  FROM platform_rates p, platform_rates c
 WHERE c.id='r6oC' AND p.id <> 'r6oC' AND p.\"effectiveFrom\" <= c.\"createdAt\"
 ORDER BY p.\"effectiveFrom\" DESC, p.\"createdAt\" DESC LIMIT 1;
ROLLBACK;")"
case "$ord" in
  *"PREV=5/1"*"REF=5/1"*) pass "a row scheduled ahead is recorded as the previous rate once in effect (5/1, as marginAt reads)" ;;
  *"REF=5/1"*) fail "the previous pair is not the rate marginAt says was in effect — the derivation order drifted: ${ord}" ;;
  *) unknown "the ORDER scenario did not set up as designed (the reference is not the scheduled row): ${ord}" ;;
esac

# --------------------------------------------------------------------------
echo '── ISOLATION — the derivation refuses above READ COMMITTED (--attempt) '
# ⚠️ ROUND 6 — measured before the refusal existed: at REPEATABLE READ and at
# SERIALIZABLE a racing insert recorded previous 3/2 where 2/1 was in effect, and
# SERIALIZABLE raised NO 40001. The snapshot predates the lock; ruling #269.
for lvl in "REPEATABLE READ" "SERIALIZABLE"; do
  out="$(q "BEGIN ISOLATION LEVEL ${lvl}; INSERT INTO platform_rates (${PR_COLS}) VALUES ('r6iso',3,2,'op@x'); ROLLBACK;")"
  case "$out" in
    *"cannot derive the previous rate at isolation level"*) pass "an insert at ${lvl} is refused BY NAME" ;;
    *ERROR*) fail "an insert at ${lvl} was refused by something ELSE: ${out}" ;;
    *) fail "an insert at ${lvl} was ACCEPTED — its previous pair is read from a snapshot older than the lock" ;;
  esac
done
# POSITIVE CONTROL, or the two arms above pass on a trigger that refuses everything.
out="$(q "BEGIN ISOLATION LEVEL READ COMMITTED; INSERT INTO platform_rates (${PR_COLS}) VALUES ('r6iso',3,2,'op@x'); SELECT 'RC_OK'; ROLLBACK;")"
case "$out" in
  *RC_OK*) pass "an insert at READ COMMITTED is accepted" ;;
  *) fail "an insert at READ COMMITTED was refused — the writer is stranded: ${out}" ;;
esac

# --------------------------------------------------------------------------
echo '── SHADOW — no name resolves through the caller (--attempt) ───────────'
# ⚠️ ROUND 6 — (1) a session TEMP table named platform_rates, needing only the
# default TEMP privilege, supplied the previous pair; (2) a public.clock_timestamp()
# under SET LOCAL search_path back-dated a rate to 2026-08-01.
sh1="$(q "BEGIN;
INSERT INTO public.platform_rates (${PR_COLS}) VALUES ('r6s1',3,2,'op@x');
INSERT INTO public.platform_rates (${PR_COLS}) VALUES ('r6s2',4,1,'op@x');
CREATE TEMP TABLE platform_rates (\"marginNumerator\" int, \"marginDenominator\" int, \"effectiveFrom\" timestamptz, \"createdAt\" timestamptz) ON COMMIT DROP;
INSERT INTO pg_temp.platform_rates VALUES (5,1,'2000-01-01','2000-01-01');
INSERT INTO public.platform_rates (${PR_COLS}) VALUES ('r6s3',2,1,'op@x');
SELECT 'PREV=' || \"previousNumerator\" || '/' || \"previousDenominator\" FROM public.platform_rates WHERE id='r6s3';
ROLLBACK;")"
case "$sh1" in
  *"PREV=4/1"*) pass "a caller's TEMP platform_rates does not reach the derivation (previous 4/1, the real one)" ;;
  *"PREV=5/1"*) fail "a caller's TEMP table supplied the previous pair (5/1) — the table name is not qualified" ;;
  *) unknown "the TEMP-shadow scenario could not run: ${sh1}" ;;
esac
sh2="$(q "BEGIN;
CREATE FUNCTION public.clock_timestamp() RETURNS timestamptz LANGUAGE sql AS \$\$ SELECT '2000-01-01 00:00:00+00'::timestamptz \$\$;
SET LOCAL search_path = public, pg_catalog;
INSERT INTO public.platform_rates (${PR_COLS}) VALUES ('r6c1',3,2,'op@x');
SELECT 'AGE_S=' || floor(extract(epoch FROM (pg_catalog.clock_timestamp() - \"effectiveFrom\")))::bigint FROM public.platform_rates WHERE id='r6c1';
ROLLBACK;")"
age="$(printf '%s' "$sh2" | sed -n 's/.*AGE_S=\(-\{0,1\}[0-9]*\).*/\1/p' | head -1)"
if [ -z "$age" ]; then
  unknown "the clock-shadow scenario could not run (this role may lack CREATE on public; the proconfig arm still covers it): ${sh2}"
elif [ "$age" -le 60 ]; then
  pass "a shadowing public.clock_timestamp() does not back-date a rate (effective ${age}s ago)"
else
  fail "a shadowing public.clock_timestamp() back-dated a rate by ${age}s — the clock is not pg_catalog-qualified"
fi

# --------------------------------------------------------------------------
echo '── BOUNDS — both encodings answer ONE shared list (--attempt) ─────────'
if [ ! -f "$CASES" ]; then
  fail "the shared bounds list is missing at ${CASES} — this arm cannot run"
else
  # ⚠️ Read with python3, not a hand-rolled grep: the list is the contract and a
  # parser that silently skipped a row would make this arm quietly narrower.
  # ⚠️ THE CASES ARE READ INTO AN ARRAY FIRST, NOT PIPED INTO THE LOOP.
  # `docker exec -i` (the documented PSQL override) READS STDIN, so a
  # `while read … done < <(…)` loop that calls psql per row has its remaining
  # input EATEN by the first call. Measured while writing this file: the loop ran
  # 1 of 16 cases and every arm passed. The `ncases` control below is the only
  # reason that was visible at all — which is why it is here.
  mapfile -t _rows < <(python3 -c "
import json,sys
for c in json.load(open('$CASES'))['cases']:
    print('%s|%d|%d|%s' % (c['id'], c['n'], c['d'], c['usable']))
")
  ncases=0
  for _row in "${_rows[@]}"; do
    IFS='|' read -r id n d usable <<< "$_row"
    [ -z "${id:-}" ] && continue
    ncases=$((ncases + 1))
    out="$(q "BEGIN; INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\") VALUES ('r5b_${id}',${n},${d},'ops@example.test'); ROLLBACK;")"
    if [ "$usable" = "True" ]; then
      case "$out" in
        *ERROR*) fail "${id} (${n}/${d}) is legal under #178 and isUsableMargin, and the DB refused it: ${out}" ;;
        *)       pass "${id} (${n}/${d}) accepted, as isUsableMargin says" ;;
      esac
    else
      case "$out" in
        *"platform_rates_margin_bounds"*) pass "${id} (${n}/${d}) refused BY NAME" ;;
        *ERROR*) fail "${id} (${n}/${d}) was refused, but NOT by name — a refusal is evidence only when you know what refused: ${out}" ;;
        *)       fail "${id} (${n}/${d}) is out of bounds under #178 and the DB ACCEPTED it" ;;
      esac
    fi
  done
  # POSITIVE CONTROL ON THE LOOP ITSELF: an empty list would print no FAILs and
  # read exactly like a clean pass.
  [ "$ncases" -ge 10 ] && pass "the shared list supplied ${ncases} cases" \
    || fail "the shared list supplied only ${ncases} cases — this arm is near-vacuous"
fi

# --------------------------------------------------------------------------
echo '── ACTOR — every blank round 5 measured as accepted (--attempt) ───────'
actor_case() { # $1 = label, $2 = SQL expression for the label, $3 = expect refuse|accept
  out="$(q "BEGIN; INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\") VALUES ('r5a',3,2,${2}); ROLLBACK;")"
  if [ "$3" = "refuse" ]; then
    case "$out" in
      *"platform_rates_actor_present"*) pass "actor ${1} refused BY NAME" ;;
      *ERROR*) fail "actor ${1} refused, but not by platform_rates_actor_present: ${out}" ;;
      *) fail "actor ${1} was ACCEPTED — a permanent price change with no readable actor" ;;
    esac
  else
    case "$out" in
      *ERROR*) fail "actor ${1} is a REAL label and was refused: ${out}" ;;
      *) pass "actor ${1} accepted" ;;
    esac
  fi
}
actor_case "'' (empty)"          "''"                    refuse
actor_case "spaces"              "'   '"                 refuse
actor_case "TAB"                 "E'\t'"                 refuse
actor_case "LF+CR"               "E'\n\r'"               refuse
actor_case "VT"                  "chr(11)"               refuse
actor_case "FF"                  "chr(12)"               refuse
actor_case "U+00A0 NBSP"         "U&'\\00a0'"            refuse
actor_case "U+2007 figure space" "U&'\\2007'"            refuse
actor_case "U+3000 ideographic"  "U&'\\3000'"            refuse
actor_case "U+200B zero-width"   "U&'\\200b'"            refuse
actor_case "U+FEFF BOM"          "U&'\\feff'"            refuse
actor_case "mixed blanks"        "E' \t'||U&'\\00a0\\3000\\feff'" refuse
# ⚠️ POSITIVE CONTROLS. Without these a constraint that refused EVERY actor
# scores full marks above while making the ADMIN-4 writer unusable.
actor_case "an email"            "'kasra@example.com'"   accept
actor_case "a CJK name"          "U&'\\738b\\5c0f\\660e'" accept
actor_case "a Cyrillic name"     "U&'\\0418\\0432\\0430\\043d'" accept
actor_case "an accented name"    "U&'\\00c9lodie'"       accept
# ⚠️ ROUND 6 — the named inputs the round-6 pass measured as ACCEPTED under round
# 5's enumerated trim set. Kept by name so a regression is legible in the log.
actor_case "chr(1) SOH"          "chr(1)"                refuse
actor_case "chr(27) ESC"         "chr(27)"               refuse
actor_case "chr(127) DEL"        "chr(127)"              refuse
actor_case "U+200E LRM (Cf)"     "U&'\\200e'"            refuse
actor_case "U+00AD soft hyphen"  "U&'\\00ad'"            refuse
actor_case "U+2800 braille blank" "U&'\\2800'"           refuse
actor_case "U+2061 function app." "U&'\\2061'"           refuse
actor_case "U+202E RLO"          "U&'\\202e'"            refuse
actor_case "a single digit"      "'7'"                   accept
actor_case "an Arabic name"      "U&'\\0639\\0644\\064a'" accept

# ⚠️ ROUND 6 — THE SWEEP. The named cases above can only test code points
# somebody thought of, which is exactly how round 5's enumeration passed its own
# arm while 21 invisible actors were accepted. So the must-REFUSE set is DERIVED:
# every assigned code point whose Unicode general category is NOT a letter (L*)
# or decimal digit (Nd), per python's `unicodedata` — an oracle that shares
# nothing with the constraint's spelling. Private-use (Co) is sampled, Cn and
# surrogates are skipped. A sample of letters and digits from long-stable
# scripts must be ACCEPTED, or the constraint strands the writer. Each attempt
# runs in its own subtransaction and is rolled back; a refusal counts only if it
# NAMES platform_rates_actor_present.
qs() { printf '%s\n' "$1" | $PSQL -tA 2>&1; }
SWEEP_SQL="$(python3 - <<'PY'
import unicodedata
ALNUM = {'Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Nd'}
FILLERS = [0x115F, 0x1160, 0x3164, 0xFFA0]   # Lo, yet Default_Ignorable
refuse, accept = [], []
for cp in range(1, 0x110000):
    if 0xD800 <= cp <= 0xDFFF:
        continue
    cat = unicodedata.category(chr(cp))
    if cat == 'Cn':
        continue
    if cat == 'Co':
        if cp in (0xE000, 0xF8FF, 0xF0000, 0x10FFFD):
            refuse.append(cp)
        continue
    if cat not in ALNUM:
        refuse.append(cp)
for a, b in [(0x30, 0x39), (0x41, 0x5A), (0x61, 0x7A), (0xC0, 0x24F), (0x391, 0x3C9),
             (0x410, 0x44F), (0x5D0, 0x5EA), (0x627, 0x64A), (0x660, 0x669), (0x905, 0x939),
             (0xE01, 0xE30), (0x3041, 0x3096), (0x30A1, 0x30FA), (0x4E00, 0x4EFF), (0xAC00, 0xACFF)]:
    for cp in range(a, b + 1):
        if unicodedata.category(chr(cp)) in ALNUM and cp not in FILLERS:
            accept.append(cp)
def sweep(name, cps, want_refused):
    w = 'true' if want_refused else 'false'
    return f"""DO $sw$
DECLARE cp int; odd int[] := '{{}}'; other int[] := '{{}}'; cname text; n int := 0;
BEGIN
  FOREACH cp IN ARRAY ARRAY[{','.join(map(str, cps))}]::int[] LOOP
    n := n + 1;
    BEGIN
      INSERT INTO platform_rates (id,"marginNumerator","marginDenominator","changedByLabel") VALUES ('r6sw',3,2,chr(cp));
      RAISE EXCEPTION 'r6sw accepted' USING ERRCODE = 'P0R06';
    EXCEPTION
      WHEN SQLSTATE 'P0R06' THEN IF {w} THEN odd := odd || cp; END IF;
      WHEN check_violation THEN
        GET STACKED DIAGNOSTICS cname = CONSTRAINT_NAME;
        IF cname IS DISTINCT FROM 'platform_rates_actor_present' THEN other := other || cp;
        ELSIF NOT {w} THEN odd := odd || cp; END IF;
    END;
  END LOOP;
  RAISE NOTICE 'SWEEP {name} n=% odd=% other=% first=%', n, coalesce(array_length(odd, 1), 0),
    coalesce(array_length(other, 1), 0),
    coalesce((SELECT string_agg('U+' || upper(to_hex(x)), ',') FROM unnest(odd[1:12]) AS x), '-');
END $sw$;"""
print('BEGIN;')
print(sweep('REFUSE', refuse, True))
print(sweep('ACCEPT', accept, False))
print(sweep('RESIDUAL', FILLERS, True))
print('ROLLBACK;')
print(f"SELECT 'UNIDATA {unicodedata.unidata_version} refuse-set {len(refuse)} accept-set {len(accept)}';")
PY
)"
sw="$(qs "$SWEEP_SQL")"
sweep_field() { printf '%s' "$sw" | sed -n "s/.*SWEEP $1 n=\([0-9]*\) odd=\([0-9]*\) other=\([0-9]*\) first=\([^ ]*\).*/\\$2/p" | head -1; }
echo "  (oracle: $(printf '%s' "$sw" | grep -o 'UNIDATA [^|]*' | head -1))"
rn="$(sweep_field REFUSE 1)"; rodd="$(sweep_field REFUSE 2)"; rother="$(sweep_field REFUSE 3)"; rfirst="$(sweep_field REFUSE 4)"
an="$(sweep_field ACCEPT 1)"; aodd="$(sweep_field ACCEPT 2)"; aother="$(sweep_field ACCEPT 3)"; afirst="$(sweep_field ACCEPT 4)"
xodd="$(sweep_field RESIDUAL 2)"
if [ -z "$rn" ] || [ -z "$an" ]; then
  unknown "the derived actor sweep did not run: $(printf '%s' "$sw" | grep -m1 ERROR)"
else
  if [ "$rn" -lt 1000 ]; then fail "the derived refuse-set held only ${rn} code points — near-vacuous"
  elif [ "$rodd" != "0" ]; then fail "${rodd} of ${rn} non-letter, non-digit code points were ACCEPTED as the only actor (first: ${rfirst})"
  elif [ "$rother" != "0" ]; then fail "${rother} refuse-set code points were refused by a DIFFERENT constraint — a refusal is evidence only when you know what refused"
  else pass "every one of ${rn} non-letter, non-digit code points (derived from Unicode category) is refused BY NAME"; fi
  if [ "$an" -lt 500 ]; then fail "the derived accept-set held only ${an} code points — near-vacuous"
  elif [ "$aodd" != "0" ] || [ "$aother" != "0" ]; then fail "${aodd} real letters/digits were REFUSED (first: ${afirst}) — the writer is stranded"
  else pass "all ${an} sampled letters and digits (Latin, Greek, Cyrillic, Hebrew, Arabic, Devanagari, Thai, kana, CJK, Hangul) are accepted"; fi
  printf '  NOTE  known residual, recorded not hidden: %s of 4 Hangul fillers (Lo, Default_Ignorable) are accepted as an actor\n' "${xodd:-?}"
fi

# --------------------------------------------------------------------------
echo '── REFUSAL — append-only, by this table’s own message (--attempt) ─────'
refusal() { # $1 = what, $2 = SQL, $3 = expected message fragment
  out="$(q "BEGIN; INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\") VALUES ('r5x',3,2,'op@x'); ${2} ROLLBACK;")"
  case "$out" in
    *"$3"*) pass "$1 refused by platform_rates' own message" ;;
    *ERROR*) fail "$1 was refused by something ELSE — a refusal is evidence only when you know what refused: ${out}" ;;
    *) fail "$1 was NOT refused" ;;
  esac
}
refusal "UPDATE"   "UPDATE platform_rates SET \"marginNumerator\"=4 WHERE id='r5x';" "append-only"
refusal "DELETE"   "DELETE FROM platform_rates WHERE id='r5x';"                      "DELETE is refused"
refusal "TRUNCATE" "TRUNCATE platform_rates;"                                        "TRUNCATE is refused"
refusal "backdated INSERT" "INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\",\"effectiveFrom\",\"createdAt\") VALUES ('r5y',5,1,'op@x',now()-interval '1 month',now()-interval '1 month');" "never before"

# ⚠️ THE POSITIVE CONTROL FOR THE APPEND-ONLY ARM. The ONE permitted update is
# the `ON DELETE SET NULL` detach; without it this trigger holds user deletion
# hostage, which is the bug the carve-out exists to prevent.
#
# ⚠️ ROUND 6 — THE OLD FIXTURE WAS NOT A USER, SO THIS ARM COULD NEVER PASS.
# It was `INSERT INTO users (id) VALUES ('r5u') ON CONFLICT DO NOTHING`, and
# `users` has five NOT NULL columns with no default (id, email, passwordHash,
# practiceId, updatedAt). NOT NULL is checked before ON CONFLICT, so it errored
# on EVERY database built from this repo's migrations — and the arm then blamed
# the TRIGGER ("holds account deletion hostage") for a defect that does not
# exist. The round-5 "ALL ARMS PASSED … the detach control" could not have come
# from such a database.
#
# So the fixture is a REAL one — a practice, an active OWNER (the last-owner
# guard needs one), and a CLINICIAN who changed a rate — its construction is
# asserted SEPARATELY, and the detach is the real act: `DELETE FROM users`, which
# fires the FK's ON DELETE SET NULL, not a hand-written UPDATE standing in for it.
USER_FIXTURE="
INSERT INTO practices (id,name,slug,\"updatedAt\") VALUES ('r6det_p','r6 detach fixture','r6det-p',now());
INSERT INTO users (id,email,\"passwordHash\",\"updatedAt\",\"practiceId\",\"practiceRole\") VALUES
  ('r6det_owner','r6det-owner@example.test','x',now(),'r6det_p','OWNER'),
  ('r6det_u','r6det-u@example.test','x',now(),'r6det_p','CLINICIAN');
INSERT INTO platform_rates (id,\"marginNumerator\",\"marginDenominator\",\"changedByLabel\",\"changedByUserId\") VALUES ('r5d',3,2,'r6det-u@example.test','r6det_u');
SELECT 'FIXTURE_OK';"

fx="$(q "BEGIN; ${USER_FIXTURE} ROLLBACK;")"
case "$fx" in
  *FIXTURE_OK*) pass "the user fixture builds on this schema (practice, OWNER, CLINICIAN, a rate the CLINICIAN changed)" ;;
  *) unknown "CANNOT BUILD the user fixture, so the detach and smuggle arms below measure nothing — NOT a verdict on the trigger: ${fx}" ;;
esac

det="$(q "BEGIN; ${USER_FIXTURE}
DELETE FROM users WHERE id='r6det_u';
SELECT 'DETACH:' || coalesce(\"changedByUserId\",'NULL') || ':' || \"changedByLabel\" FROM platform_rates WHERE id='r5d';
ROLLBACK;")"
case "$det" in
  *"DETACH:NULL:r6det-u@example.test"*) pass "a REAL user deletion detaches the rate (changedByUserId NULL, label kept)" ;;
  *FIXTURE_OK*) fail "the permitted detach is refused — this trigger holds account deletion hostage: ${det}" ;;
  *) unknown "the detach arm could not run (the fixture did not build — see above)" ;;
esac

# ⚠️ ROUND 6 — THE SMUGGLE ARMS, which the prior art has and this port dropped.
# `check-ledger-append-only.sh` asserts "a detach carrying another change is
# still refused". Without it the carve-out's whole-row jsonb equality was
# untested from BOTH directions: the refusal arm above updates a row whose actor
# is already NULL (so the carve-out is never entered), and the detach control
# changes only the actor. Measured: deleting the jsonb line let
# `SET "changedByUserId"=NULL, "marginNumerator"=5, "marginDenominator"=1,
# "effectiveFrom"='2020-01-01Z', "createdAt"='2020-01-01Z'` through — a
# retroactive re-price wearing the detach's clothes — with every arm green.
smuggle() { # $1 = what, $2 = the extra SET that rides along with the detach
  out="$(q "BEGIN; ${USER_FIXTURE} UPDATE platform_rates SET \"changedByUserId\"=NULL, ${2} WHERE id='r5d'; ROLLBACK;")"
  case "$out" in
    *"append-only"*) pass "a detach smuggling ${1} is refused by platform_rates' own message" ;;
    *FIXTURE_OK*ERROR*) fail "a detach smuggling ${1} was refused by something ELSE: ${out}" ;;
    *FIXTURE_OK*) fail "a detach smuggling ${1} was ACCEPTED — the carve-out rewrites history" ;;
    *) unknown "the smuggle arm (${1}) could not run (the fixture did not build)" ;;
  esac
}
smuggle "a new margin"                        "\"marginNumerator\"=5, \"marginDenominator\"=1"
smuggle "a back-dated effectiveFrom+createdAt" "\"effectiveFrom\"='2020-01-01Z', \"createdAt\"='2020-01-01Z'"
smuggle "a rewritten actor label"             "\"changedByLabel\"='someone-else@example.test'"
smuggle "a rewritten previous pair"           "\"previousNumerator\"=5, \"previousDenominator\"=1"
smuggle "an edited note"                      "\"note\"='edited'"

# --------------------------------------------------------------------------
echo '── RESIDUE — every write above was inside BEGIN … ROLLBACK ────────────'
res="$(q "SELECT count(*) FROM platform_rates WHERE id LIKE 'r5%' OR id LIKE 'r6%'")"
[ "$res" = "0" ] && pass "no residue (0 rate rows matching r5%/r6%)" \
  || fail "${res} row(s) survived — a write escaped its transaction"
ures="$(q "SELECT (SELECT count(*) FROM users WHERE id LIKE 'r6det_%') + (SELECT count(*) FROM practices WHERE id LIKE 'r6det_%')")"
[ "$ures" = "0" ] && pass "no residue (0 fixture users/practices)" \
  || fail "${ures} fixture user/practice row(s) survived — a write escaped its transaction"

echo
if [ "$fails" != "0" ]; then
  echo "${fails} ARM(S) FAILED."
  exit 1
fi
if [ "$cannot" != "0" ]; then
  echo "CANNOT TELL — ${cannot} arm(s) could not run. Not a pass."
  exit 2
fi
echo "ALL ARMS PASSED."
exit 0
