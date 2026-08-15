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
# declared PER HOST, and a change AWAY from it is the finding — including a
# change away from 410, which would mean the retired CRM started serving again.
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
  "pro.quillmd.com|410|DELIBERATELY RETIRED. The meddoc-pro CRM container was stopped (SIGTERM) on ~2026-08-04 and Caddy answers Gone. A change AWAY from 410 is the finding: either it started serving again, or a 502 is wearing its place."
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
