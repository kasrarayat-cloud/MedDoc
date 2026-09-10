#!/usr/bin/env bash
# ============================================================================
# Does every co-tenant hostname still answer with the status it is SUPPOSED to?
# ----------------------------------------------------------------------------
# ⚠️ THIS EXISTS BECAUSE "UNWATCHED" AND "FINE" LOOK IDENTICAL. On 2026-08-15,
# a post-deploy sweep found `pro.quillmd.com` returning 410 and nobody could say
# whether that was new. It was not — the `meddoc-pro` CRM container had read
# `Exited (143)` for ELEVEN DAYS (SIGTERM: a deliberate stop, not a crash) — but
# establishing that took reading container state, because NO CHECK WATCHED THAT
# HOSTNAME AT ALL. Every standing check would have stayed green through a total
# outage of it.
#
# ⚠️ SO THE CURE IS NOT "WATCH IT". IT IS "WATCH IT WITH THE RIGHT ANSWER."
# A check that merely required 2xx/3xx would go RED on the deliberate
# retirement, and a check that accepted anything would go green on a 502 wearing
# the retirement's place. Both are useless. The expected status is therefore
# declared PER HOST, and a change AWAY from it is the finding.
#
# ⚠️ CORRECTED 2026-09-09 — AND THE CORRECTION IS TO A CLAIM THIS FILE MADE ABOUT
# ITSELF. The sentence above used to end "...including a change away from 410,
# which would mean the retired CRM started serving again", and the pro row said
# "Caddy answers Gone". BOTH WERE WRONG ABOUT WHICH LAYER ANSWERS, and the error
# was load-bearing: a §2.5 declaration cited this row as the evidence that the
# CRM had not come back. It cannot be. HOST NGINX emits that 410 from a block
# with no proxy_pass, so nothing behind it is consulted and the code is identical
# whether the container runs or not. THIS CHECK WATCHES THE EDGE. A container
# revival is a CONTAINER question and is watched by container state, not by HTTP.
#
# ⚠️ THIS IS NOT `check-ingress-tls.sh`. That one asks whether a fresh TLS
# handshake completes per SNI; it says nothing about what the application
# behind it answers, and its host list does not even contain `pro.quillmd.com`.
# This one asks the HTTP question and is deliberately separate.
#
# READ-ONLY. Issues HEAD requests. Writes nothing, mutates nothing, and never
# touches a clinical route.
#
# Usage:  bash scripts/check-cotenants.sh
# Exit:   0 = every host matches its expected status
#         1 = AT LEAST ONE DIVERGED  (the finding)
#         2 = cannot tell (no curl, no network, or the probe cannot discriminate)
# ============================================================================
set -uo pipefail

# host|expected|why — the "why" is load-bearing: a bare number decays into
# nobody remembering whether it was intended.
EXPECTED=(
  "quillmd.com|200|the marketing site serves"
  "www.quillmd.com|200|the same site on the www host. MASTER.md STEP 0.6 names FIVE hosts and this table shipped with FOUR — the watched-set failure INSIDE the check written to cure watched-set failures. Keep every entry on ONE line: the floor is derived by cutting field 2, and a wrapped reason is parsed as extra expected codes."
  "app.quillmd.com|307|unauthenticated redirect to login"
  "admin.quillmd.com|404|the documented adminApi() 404-gate — admin is INVISIBLE, not merely forbidden"
  "pro.quillmd.com|410|DELIBERATELY RETIRED by owner ruling; ruling #307 then removed the compose service. CORRECTED 2026-09-09 — this row previously read 'Caddy answers Gone', which was FALSE and made it read as a revival detector. MEASURED: the 410 comes from HOST NGINX (/etc/nginx/sites-available/quillmd, a dedicated server block with NO proxy_pass), so it is UNCONDITIONAL AND UPSTREAM-INDEPENDENT; Caddy direct on 127.0.0.1:8443 with that SNI answered 502. THIS ROW THEREFORE CANNOT DETECT THE CRM RUNNING AGAIN: docker start of the retired container leaves it green. Since #307 the Caddy block answers 410 too, so a 502 can no longer wear its place either. A change away from 410 IS still the finding, but it is an INGRESS event: the nginx block tidied away and the host falling through to a co-tenant (sites-enabled/dealhunter declares server_name 5.231.107.93 _; and sorts first in the glob), a TLS failure, or somebody running the documented restore. For a REVIVAL, watch the container instead: docker inspect meddoc-pro-meddoc-pro-1 --format {{.State.Status}} must read exited."
)

have() { command -v "$1" >/dev/null 2>&1; }
have curl || { echo "🟡 cannot tell — curl not installed"; exit 2; }

probe() {
  # -I HEAD, no reuse across hosts, generous but bounded timeout.
  curl -sI -o /dev/null -m 12 -w '%{http_code}' "https://$1" 2>/dev/null || echo 000
}

declare -a OBSERVED=()
findings=0
printf '%-22s %-9s %s\n' HOST EXPECTED OBSERVED
for row in "${EXPECTED[@]}"; do
  host="${row%%|*}"; rest="${row#*|}"; want="${rest%%|*}"; why="${rest#*|}"
  got="$(probe "$host")"
  OBSERVED+=("$got")
  if [ "$got" = "$want" ]; then
    printf '  🟢 %-20s %-9s %s\n' "$host" "$want" "$got"
  elif [ "$got" = "000" ]; then
    printf '  🟡 %-20s %-9s %s  (no response — network or DNS)\n' "$host" "$want" "$got"
    echo "🟡 cannot tell — $host did not respond at all."
    exit 2
  else
    findings=$((findings + 1))
    printf '  🔴 %-20s %-9s %s\n' "$host" "$want" "$got"
    echo "     WHY $want WAS EXPECTED: $why"
  fi
done

# ── DISCRIMINATION CONTROL ────────────────────────────────────────────────
# ⚠️ A PROBE THAT RETURNS THE SAME CODE FOR EVERY HOST IS NOT ROUTING. If an
# ingress fault made all four answer identically, a naive check could still
# "match" by luck on one of them. The four hosts carry four DIFFERENT expected
# codes, which hands this check a free control: the observed set must contain
# at least three distinct values, or the probe is not discriminating between
# hostnames and its greens mean nothing.
# ⚠️ THE THRESHOLD IS DERIVED FROM THE TABLE, NOT A CONSTANT. A hardcoded 3
# was the first draft and it was arbitrary: it neither scales when a host is
# added nor tolerates a genuine single divergence. The table declares N distinct
# expected codes, so the probe should observe about N — allow exactly ONE to
# differ (that is a finding, reported above, not a broken probe) and treat
# anything flatter as an instrument that is not distinguishing hostnames.
expected_distinct="$(printf '%s\n' "${EXPECTED[@]}" | cut -d'|' -f2 | sort -u | wc -l)"
floor=$(( expected_distinct - 1 )); [ "$floor" -lt 2 ] && floor=2
distinct="$(printf '%s\n' "${OBSERVED[@]}" | sort -u | wc -l)"
if [ "$distinct" -lt "$floor" ]; then
  echo "🟡 cannot tell — only $distinct distinct status codes across ${#OBSERVED[@]} hosts (floor $floor, from $expected_distinct distinct expected)."
  echo "   The probe is not discriminating between hostnames; a green here would"
  echo "   be indistinguishable from an ingress answering everything the same."
  exit 2
fi

if [ "$findings" -eq 0 ]; then
  echo "🟢 every co-tenant answers its expected status ($distinct distinct codes — the probe discriminates)."
  exit 0
fi
echo "🔴 $findings co-tenant(s) diverged from the expected status. That is THE FINDING,"
echo "   whatever the explanation sounds like afterwards."
exit 1
