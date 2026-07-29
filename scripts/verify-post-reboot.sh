#!/usr/bin/env bash
# ============================================================================
# Post-reboot proof — the one property a hand-started unit cannot demonstrate.
# ----------------------------------------------------------------------------
# Both PHI stores are unlocked at boot by systemd units ordered
# `Before=docker.service`, and both containers now FAIL CLOSED if their volume
# is missing. Those two facts together mean a boot-ordering race no longer
# corrupts anything — it just takes the stack down. That is the right trade, but
# it is only a trade if the ordering actually works, and starting a unit by hand
# proves nothing about ordering.
#
# So this runs AFTER a real reboot and asserts the whole chain:
#
#   units started at boot → mappings open → mounts live on the dm devices →
#   Postgres and MinIO healthy ON those devices → guards intact → app up →
#   co-tenants up
#
# It also checks the two KNOWN side effects of a reboot on this host, because
# they are expected and should be handled as part of the proof rather than
# discovered as surprises:
#
#   - the QA stack does NOT self-restart (prod does)
#   - a stale `@reboot` cron dirties the working tree
#
# READ-ONLY. Reports; never fixes. Fixing is a decision.
#
# Usage:  bash scripts/verify-post-reboot.sh
# Exit:   0 = everything came back · 1 = something did not
# ============================================================================
set -uo pipefail

inhost() {
  docker run --rm --privileged --ipc=host --pid=host -v /:/host \
    alpine chroot /host bash -c "$1" 2>/dev/null
}

fail=0
note() { printf '   %s\n' "$1"; }
bad()  { printf '🔴 %s\n' "$1"; fail=1; }

REPO=$(cd "$(dirname "$0")/.." && pwd)

# ---------------------------------------------------------------------------
# Assert a compose stack is COMPLETE, not merely non-empty.
#
# THREE false greens lived in sections 4-6 until 2026-07-29, all the same shape:
# each asked "is anything wrong?" of a set whose size it never established.
#
#   §4 printed "🟢 every meddoc-pro container is up" against ZERO containers.
#      `docker ps -a` returns nothing, the grep filters nothing, the emptiness
#      test passes. That is green on a DEAD production stack — and green in
#      precisely the case this proof exists to catch, because both stores now
#      FAIL CLOSED: a lost boot race takes the stack down rather than reverting
#      to plaintext. The check was blindest exactly where it had to see.
#
#   §4 also could not see an UNHEALTHY container, twice over:
#      `grep -vi "healthy"` drops "unhealthy" as a substring, and `Up [0-9]`
#      matches any running container whatever its health says.
#
#   §6 printed "🟢 QA stack: 1 container(s) up" with 5 of 6 down, because it
#      tested `-eq 0`. Exactly one QA container is `unless-stopped`
#      (gotenberg); the other five are `restart: "no"` and ARE the documented
#      side effect this section exists to surface. The one survivor satisfied
#      the test, so the section reported success on the very state it was
#      written to report.
#
# The fix is the one section 1 already models: name what you expect, and
# compare. Derive the expected service set from the compose file, resolve each
# service to its container, and require running + (healthy | no healthcheck).
# An assertion that names its expected set cannot be satisfied by an empty one.
# ---------------------------------------------------------------------------
stack_state() {   # $1 = compose file, $2 = project prefix → "service<TAB>status|health"
  local f="$1" proj="$2" svc cname st
  for svc in $(docker compose -f "$f" config --services 2>/dev/null | sort); do
    cname="${proj}-${svc}-1"
    st=$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cname" 2>/dev/null) \
      || st="absent|none"
    printf '%s\t%s\n' "$svc" "$st"
  done
}

echo "── uptime ──────────────────────────────────────────────────────────"
inhost "uptime -p; echo 'booted: '\$(uptime -s)"
echo

echo "── 1. the units started AT BOOT, not by hand ───────────────────────"
# THE ASSERTION THIS WHOLE SCRIPT EXISTS FOR, and the first draft got it wrong:
# it printed the two timestamps with a comment telling the reader to compare
# them, and passed either way. A hand-started unit reads `active` exactly like a
# boot-started one — which is the ONE case this proof is meant to catch — so a
# check that only displays the values is decorative. Caught on the dry-run,
# where miniodata-encrypted had been started by hand two days after boot and
# condition 1 went green.
#
# So: compare in the script, and fail on drift. A unit ordered
# Before=docker.service lands within seconds of boot; anything past the grace
# window was started by a human and proves nothing about ordering.
BOOT_GRACE=120
boot_epoch=$(inhost "date -d \"\$(uptime -s)\" +%s")
for u in pgdata-encrypted miniodata-encrypted; do
  st=$(inhost "systemctl is-active $u.service")
  since=$(inhost "systemctl show -p ActiveEnterTimestamp --value $u.service")
  if [ "$st" != "active" ]; then
    bad "$u.service is '$st' after boot — Before=docker.service did not hold"
    continue
  fi
  since_epoch=$(inhost "date -d '$since' +%s" 2>/dev/null)
  if [ -z "$since_epoch" ] || [ -z "$boot_epoch" ]; then
    bad "$u.service: could not parse start time ('$since') — cannot prove it started at boot"
    continue
  fi
  delta=$(( since_epoch - boot_epoch ))
  if [ "$delta" -lt 0 ] || [ "$delta" -gt "$BOOT_GRACE" ]; then
    bad "$u.service started ${delta}s after boot (grace ${BOOT_GRACE}s) — that is a HAND START, not boot ordering. This proof is invalid until the host is actually rebooted."
  else
    note "🟢 $u.service started ${delta}s after boot — boot ordering held"
  fi
done
echo

echo "── 2. mappings + mounts ────────────────────────────────────────────"
inhost "lsblk -o NAME,TYPE,FSTYPE,MOUNTPOINT | grep -E 'loop|crypt' || echo '(no crypt devices!)'"
for m in /mnt/pgdata-encrypted /mnt/miniodata-encrypted; do
  s=$(inhost "findmnt -no SOURCE $m")
  [ -n "$s" ] && note "🟢 $m ← $s" || bad "$m is NOT mounted"
done
echo

echo "── 3. the stores are on those devices (the real check) ─────────────"
for s in check-pg-encrypted-mount check-minio-encrypted-mount; do
  if bash "$(dirname "$0")/$s.sh" >/tmp/prb 2>&1; then
    note "🟢 $s → 0"
  else
    bad "$s → $? "; sed 's/^/      /' /tmp/prb
  fi
done
rm -f /tmp/prb
echo

echo "── 4. prod stack ───────────────────────────────────────────────────"
prod_expected=$(docker compose -f "$REPO/docker-compose.yml" config --services 2>/dev/null | sort)
if [ -z "$prod_expected" ]; then
  # Must fail loudly. An unreadable compose file means we cannot establish what
  # "complete" is, and "I could not check" must never render as "🟢".
  bad "cannot read the prod compose service list — the stack's completeness is UNPROVEN, not fine"
else
  n_exp=$(printf '%s\n' "$prod_expected" | wc -l)
  n_ok=0; prod_bad=""
  while IFS=$'\t' read -r svc st; do
    [ -z "$svc" ] && continue
    status="${st%%|*}"; health="${st##*|}"
    if [ "$status" != "running" ]; then
      prod_bad="${prod_bad}      ${svc} → ${status}"$'\n'
    elif [ "$health" != "healthy" ] && [ "$health" != "none" ]; then
      prod_bad="${prod_bad}      ${svc} → running but ${health}"$'\n'
    else
      n_ok=$((n_ok + 1))
    fi
  done < <(stack_state "$REPO/docker-compose.yml" meddoc-pro)
  if [ -n "$prod_bad" ]; then
    bad "prod stack incomplete — $n_ok/$n_exp services running and healthy:"
    printf '%s' "$prod_bad"
    note "   (MinIO can read 'unhealthy' after losing its mc alias while serving fine —"
    note "    classify before acting, do not assume either way)"
  else
    note "🟢 prod stack complete — $n_ok/$n_exp services running and healthy"
  fi
fi
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 https://quillmd.com || echo 000)
[ "$code" = "200" ] && note "🟢 quillmd.com → 200" || bad "quillmd.com → $code"
echo

echo "── 5. co-tenants (this host is shared) ─────────────────────────────"
# Count baselines observed 2026-07-29 on a clean boot. Weaker than §4's
# service-identity check — these are other people's stacks and we do not own
# their compose files — but strictly better than `-gt 0`, which passes on 1 of 6.
for spec in "leathererp:3" "voiceassistmain:6" "openclaw:1"; do
  p="${spec%%:*}"; want="${spec##*:}"
  n=$(docker ps --filter "name=$p" --format '{{.Names}}' | wc -l)
  if [ "$n" -eq 0 ]; then
    bad "$p has NO containers up (expected $want)"
  elif [ "$n" -lt "$want" ]; then
    bad "$p: only $n of $want container(s) up — a co-tenant lost something to the boot"
  else
    note "🟢 $p: $n/$want container(s) up"
  fi
done
echo

echo "── 6. KNOWN reboot side effects — expected, handle them ────────────"
# A PARTIAL QA stack is the normal post-boot state, not a rare one: exactly one
# of its services (gotenberg) is `unless-stopped` and comes back on its own,
# while the rest are `restart: "no"`. So "some containers are up" is precisely
# what a reboot leaves behind, and it was the passing condition. Check the whole
# set. `db-migrate` is one-shot — it exits 0 by design and is not expected up.
QA_ONESHOT="db-migrate"
qa_expected=$(docker compose -f "$REPO/docker-compose.qa.yml" config --services 2>/dev/null \
                | grep -vx "$QA_ONESHOT" | sort)
if [ -z "$qa_expected" ]; then
  bad "cannot read the QA compose service list — QA posture UNPROVEN"
else
  n_qa_exp=$(printf '%s\n' "$qa_expected" | wc -l)
  n_qa_ok=0; qa_down=""
  while IFS=$'\t' read -r svc st; do
    [ -z "$svc" ] && continue
    [ "$svc" = "$QA_ONESHOT" ] && continue
    status="${st%%|*}"; health="${st##*|}"
    if [ "$status" = "running" ] && { [ "$health" = "healthy" ] || [ "$health" = "none" ]; }; then
      n_qa_ok=$((n_qa_ok + 1))
    else
      qa_down="${qa_down}      ${svc} → ${status}/${health}"$'\n'
    fi
  done < <(stack_state "$REPO/docker-compose.qa.yml" meddoc-qa)
  if [ -n "$qa_down" ]; then
    # Deliberately a warning, not a failure: this side effect is EXPECTED and
    # this script reports rather than fixes. But it must report ACCURATELY —
    # the bug was never that it warned too weakly, it was that it fell silent.
    note "⚠️  QA stack incomplete — $n_qa_ok/$n_qa_exp up. EXPECTED, it does not self-restart:"
    printf '%s' "$qa_down"
    note "   Bring it back:  docker compose -f docker-compose.qa.yml up -d"
    note "   Then re-run:    bash scripts/check-qa-mock-posture.sh"
    note "   (the posture check reads the RUNNING containers, so it only means"
    note "    anything once they are actually running again)"
  else
    note "🟢 QA stack complete — $n_qa_ok/$n_qa_exp services up"
  fi
fi
# `git status` must be allowed to FAIL LOUDLY. Run from the boot unit this
# executes as root against a repo owned by `claude`, and git then refuses with
# "detected dubious ownership" — on stderr, with an empty stdout. The first
# version piped that straight into an emptiness test and printed
# "🟢 working tree clean" off a hard error. An unreadable tree is not a clean
# one. `safe.directory` is passed per-invocation rather than written to a global
# config, because a check should not mutate the host it is checking.
if ! git_out=$(git -c safe.directory="$REPO" -C "$REPO" status --porcelain 2>&1); then
  bad "cannot read the working tree — git said: ${git_out%%$'\n'*}"
  git_out=""
fi
dirty=$(printf '%s\n' "$git_out" | grep -v '^?? ' | grep -v '^$' || true)
if [ -n "$dirty" ]; then
  note "⚠️  working tree dirty — a stale @reboot cron does this. Inspect, do NOT clobber:"
  echo "$dirty" | sed 's/^/      /'
  note "   (only 'M Caddyfile' is an expected standing modification)"
else
  note "🟢 working tree clean"
fi
echo

if [ "$fail" = "0" ]; then
  echo "🟢 POST-REBOOT PROOF PASSED — both encrypted stores came back on their"
  echo "   own, in the right order, with both fail-closed guards intact."
  exit 0
fi
echo "🔴 POST-REBOOT PROOF FAILED — see the red lines above."
echo "   If a store is down because its unit did not run, that is the guard"
echo "   working: nothing wrote plaintext. Unlock, then investigate ordering."
exit 1
