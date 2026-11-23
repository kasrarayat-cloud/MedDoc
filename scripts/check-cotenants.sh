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
# ⚠️ AN EXPECTATION CAN NAME THE REDIRECT, AND A ROW CAN NAME MORE THAN ONE
# DELIBERATE STATE (D396, the admin.quillmd.com move). `302>URL` means status
# 302 AND curl's redirect_url exactly URL: app.quillmd.com and the CPT Studio
# console on admin.quillmd.com both answer 302, and only the target tells a
# working console from an app answering in its place. Alternatives are
# comma-separated and each is a whole, named state - never a range: a row that
# accepts "503 or the console's sign-in" still goes red on a 502, a 200 or a
# 404. A two-state row exists only across a move and is narrowed when it lands.
#
# ⚠️ CPT_INSTALLER_SKIP_HOSTS (exact host names, space-separated) is how CPT
# Studio's installer tells this script not to judge the hosts it judges itself;
# the installer passes it alone, from a constant. A skipped host is printed as
# SKIPPED and left out of the discrimination floor, which is counted from the
# rows actually judged - so a skip can never make the floor easier to pass.
# Anyone who sets it by hand silences that host, and the output says so.
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
  "app.quillmd.com|302|owner-authorized normal HTTPS account login; protected application requires an invited account"
  "admin.quillmd.com|503,302>https://admin.quillmd.com/login/|TWO DELIBERATE STATES ACROSS ONE MOVE (D396): 503 is the fresh rebuild's maintenance notice (public administration in maintenance; the rebuild's private admin stays on 127.0.0.1:9131); 302 to https://admin.quillmd.com/login/ is CPT Studio's operator console once release 2 of the admin.quillmd.com move is installed. Narrowed to the second when that release lands. Anything else - a 502, a 200, a 404, a 302 elsewhere - is the finding."
  "pro.quillmd.com|410|DELIBERATELY RETIRED. The meddoc-pro CRM container was stopped (SIGTERM) on ~2026-08-04 and Caddy answers Gone. A change AWAY from 410 is the finding: either it started serving again, or a 502 is wearing its place."
)

have() { command -v "$1" >/dev/null 2>&1; }
have curl || { echo "🟡 cannot tell — curl not installed"; exit 2; }

probe() {
  # -I HEAD, no reuse across hosts, generous but bounded timeout. Prints the
  # status and curl's redirect_url (empty when the answer is not a redirect).
  local out
  out="$(curl -sI -o /dev/null -m 12 -w '%{http_code} %{redirect_url}' "https://$1" 2>/dev/null)" || out='000 '
  case "$out" in [0-9][0-9][0-9]\ *) printf '%s' "$out" ;; *) printf '000 ' ;; esac
}

# matches <alternatives> <status> <redirect_url>: one alternative names this state
matches() {
  local alt
  local -a alts
  IFS=',' read -ra alts <<< "$1"
  for alt in "${alts[@]}"; do
    case "$alt" in
      *'>'*) [ "$2" = "${alt%%>*}" ] && [ "$3" = "${alt#*>}" ] && return 0 ;;
      *) [ "$2" = "$alt" ] && return 0 ;;
    esac
  done
  return 1
}

declare -A SKIP=()
read -ra _skip_hosts <<< "${CPT_INSTALLER_SKIP_HOSTS:-}"
for h in "${_skip_hosts[@]}"; do SKIP["$h"]=1; done

declare -a OBSERVED=() JUDGED=()
declare -A NAMED=()
findings=0
printf '%-22s %-9s %s\n' HOST EXPECTED OBSERVED
for row in "${EXPECTED[@]}"; do
  host="${row%%|*}"; rest="${row#*|}"; want="${rest%%|*}"; why="${rest#*|}"
  NAMED["$host"]=1
  if [ -n "${SKIP[$host]:-}" ]; then
    printf '  ⏭  %-20s SKIPPED: CPT_INSTALLER_SKIP_HOSTS names it (its installer judges it); not judged here\n' "$host"
    continue
  fi
  answer="$(probe "$host")"; got="${answer%% *}"; target="${answer#* }"
  JUDGED+=("$want")
  case "$want" in
    *'>'*) OBSERVED+=("$got>$target"); shown="$got${target:+ → $target}" ;;
    *) OBSERVED+=("$got"); shown="$got" ;;
  esac
  if [ "$got" != "000" ] && matches "$want" "$got" "$target"; then
    printf '  🟢 %-20s %-9s %s\n' "$host" "$want" "$shown"
  elif [ "$got" = "000" ]; then
    printf '  🟡 %-20s %-9s %s  (no response — network or DNS)\n' "$host" "$want" "$got"
    echo "🟡 cannot tell — $host did not respond at all."
    exit 2
  else
    findings=$((findings + 1))
    printf '  🔴 %-20s %-9s %s\n' "$host" "$want" "$shown"
    echo "     WHY $want WAS EXPECTED: $why"
  fi
done
for h in "${!SKIP[@]}"; do
  [ -n "${NAMED[$h]:-}" ] || echo "  note: CPT_INSTALLER_SKIP_HOSTS names $h, which no row names; nothing was skipped for it"
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
# Counted from the rows JUDGED (a skipped host neither lowers nor raises it). A
# row with alternatives is one expected answer: its states exclude each other.
expected_distinct="$(printf '%s\n' "${JUDGED[@]}" | sort -u | grep -c .)"
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
