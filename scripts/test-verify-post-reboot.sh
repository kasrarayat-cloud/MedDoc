#!/usr/bin/env bash
# ============================================================================
# Negative controls for verify-post-reboot.sh — the guard for a class that has
# now come back FIVE times.
# ----------------------------------------------------------------------------
# The post-reboot proof has reported success on a state that needed action five
# separate times: twice in PR #459 (section 1's decorative timestamp print, and
# the swallowed git error), and three more found while closing F-pre on the
# 2026-07-29 boot:
#
#   §4 said "🟢 every meddoc-pro container is up" against ZERO containers
#   §4 could not see an `unhealthy` container ("unhealthy" contains "healthy",
#      and `Up [0-9]` matches any running container regardless of health)
#   §6 said "🟢 QA stack: 1 container(s) up" with 5 of 6 down
#
# Every one of them was a check that asked "is anything wrong?" of a set whose
# size it never established. On an empty set, nothing is wrong.
#
# A fix nobody can re-run is a fix that comes back, so this makes the negative
# controls repeatable. It asserts the proof can go RED — because a check that
# has never been observed failing is not known to be a check at all.
#
# READ-ONLY with respect to the real host: it builds a throwaway repo in a temp
# dir with synthetic compose files naming services that have NO containers, and
# points the real script at it. It never touches prod, QA, or the LUKS units.
#
# Usage:  bash scripts/test-verify-post-reboot.sh
# Exit:   0 = every negative control behaved · 1 = the proof has gone blind again
# ============================================================================
set -uo pipefail

REAL=$(cd "$(dirname "$0")" && pwd)/verify-post-reboot.sh
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
ok()   { printf '   🟢 %s\n' "$1"; pass=$((pass + 1)); }
no()   { printf '   🔴 %s\n' "$1"; fail=$((fail + 1)); }

mkdir -p "$TMP/scripts"
# §6 reads the working tree at $REPO, which here is $TMP. Without a git repo it
# fails ("not a git repository") and sets the exit code on its own — which made
# control A's `exit == 1` assertion pass for a reason that had nothing to do
# with §4. That is the very flaw this harness exists to catch, so: give the temp
# dir a real (empty) repo, and let §4 be the only thing that can red it.
git init -q "$TMP" 2>/dev/null
cp "$REAL" "$TMP/scripts/"
# §3 shells out to these by path; copy them so the case under test is §4/§6 and
# not a missing file.
cp "$(dirname "$REAL")/check-pg-encrypted-mount.sh" \
   "$(dirname "$REAL")/check-minio-encrypted-mount.sh" "$TMP/scripts/" 2>/dev/null

# Ghost service names, deliberately unlike any real service. An earlier draft of
# this harness used `postgres` and `transcribe-md` — which resolve to
# meddoc-pro-postgres-1 and meddoc-pro-transcribe-md-1, the REAL running
# containers — so the "dead stack" control found them healthy and passed. The
# control has to be unable to collide, or it tests nothing.
write_compose() {
  cat > "$TMP/docker-compose.yml" <<'EOF'
services:
  ghost-alpha:
    image: alpine
  ghost-beta:
    image: alpine
EOF
  cat > "$TMP/docker-compose.qa.yml" <<'EOF'
services:
  db-migrate:
    image: alpine
  ghost-qa-one:
    image: alpine
  ghost-qa-two:
    image: alpine
EOF
}

run_it() { bash "$TMP/scripts/verify-post-reboot.sh" 2>&1; }

echo "── negative controls for verify-post-reboot.sh ─────────────────────"
echo

echo "A. a DEAD prod stack must go red"
write_compose
out=$(run_it)
if grep -q "prod stack incomplete — 0/2" <<<"$out"; then
  ok "§4 reports 0/2 and names the absent services"
else
  no "§4 did NOT report the dead stack — it has gone blind again"
  grep -A4 "── 4\." <<<"$out" | sed 's/^/        /'
fi
if [ "$(bash "$TMP/scripts/verify-post-reboot.sh" >/dev/null 2>&1; echo $?)" = "1" ]; then
  ok "overall exit is 1 on a dead prod stack"
else
  no "overall exit is 0 on a dead prod stack — THE PROOF PASSES ON A DEAD STACK"
fi
echo

echo "B. a PARTIAL QA stack must be named, not summarised as fine"
if grep -q "QA stack incomplete — 0/2" <<<"$out"; then
  ok "§6 reports 0/2 and names each down service"
else
  no "§6 did NOT report the partial QA stack"
  grep -A4 "── 6\." <<<"$out" | sed 's/^/        /'
fi
if grep -q "ghost-qa-one" <<<"$out" && ! grep -q "db-migrate →" <<<"$out"; then
  ok "the one-shot db-migrate is excluded from the expected set"
else
  no "db-migrate handling is wrong — it is one-shot and must not be expected up"
fi
echo

echo "C. an UNREADABLE compose file must be UNPROVEN, never green"
rm -f "$TMP/docker-compose.yml" "$TMP/docker-compose.qa.yml"
out2=$(run_it)
if grep -q "cannot read the prod compose service list" <<<"$out2"; then
  ok "§4 refuses to claim completeness it cannot establish"
else
  no "§4 stayed silent on an unreadable compose file"
fi
if grep -q "cannot read the QA compose service list" <<<"$out2"; then
  ok "§6 refuses likewise"
else
  no "§6 stayed silent on an unreadable compose file"
fi
echo

echo "D. the real repo must still PASS (guard against a guard that only reds)"
real_out=$(bash "$REAL" 2>&1)
if grep -q "prod stack complete" <<<"$real_out"; then
  ok "§4 goes green against the real, healthy stack"
else
  no "§4 does not pass against the real stack — the fix over-corrected"
  grep -A6 "── 4\." <<<"$real_out" | sed 's/^/        /'
fi
echo

echo "───────────────────────────────────────────────────────────────────"
if [ "$fail" = "0" ]; then
  echo "🟢 all $pass negative controls behaved — the proof can still go red"
  exit 0
fi
echo "🔴 $fail of $((pass + fail)) controls failed — verify-post-reboot.sh has"
echo "   regressed toward reporting success on a state that needs action."
exit 1
