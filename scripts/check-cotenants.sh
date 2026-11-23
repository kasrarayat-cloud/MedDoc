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
# ⚠️ AN EXPECTATION CAN NAME THE REDIRECT OR THE BODY, AND A ROW CAN NAME MORE
# THAN ONE DELIBERATE STATE (D396, the admin.quillmd.com move). `302>URL` means
# status 302 AND curl's redirect_url exactly URL: app.quillmd.com and the CPT
# Studio console on admin.quillmd.com both answer 302, and only the target tells
# a working console from an app answering in its place. `503~TEXT` means status
# 503 AND the body (fetched with GET, at most 64 KiB) contains TEXT: QuillMD's
# maintenance notice and CPT Studio's own outage page are both 503, and only the
# text tells a deliberate notice from a dead console. Alternatives are
# comma-separated and each is a whole, named state - never a range: a row that
# accepts "the notice or the console's sign-in" still goes red on a 502, a 200,
# a 404, or a 503 that is not the notice. A two-state row exists only across a
# move and is narrowed when it lands.
#
# ⚠️ A FAILED HANDSHAKE IS A FINDING, NOT "NO RESPONSE". curl's TLS failures (a
# wrong or expired certificate is exactly what a move can break) are red rows;
# only a failure to resolve, connect or get an answer is "cannot tell" - and
# every row is still probed, so one silent host never hides another's finding.
#
# ⚠️ CPT_INSTALLER_SKIP_HOSTS is how CPT Studio's installer tells this script not
# to judge the one host it judges itself, admin.quillmd.com; the installer passes
# it alone, from a constant. It may name THAT HOST ONLY - any other name, or any
# other host, refuses (exit 2) before a probe, so nobody's variable can silence a
# co-tenant. A skipped host is printed as SKIPPED and left out of the
# discrimination floor, which is counted from the rows actually judged - so a
# skip can never make the floor easier to pass.
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
  "admin.quillmd.com|503~QuillMD administration is temporarily unavailable,302>https://admin.quillmd.com/login/|TWO DELIBERATE STATES ACROSS ONE MOVE (D396): 503 with the fresh rebuild's maintenance notice (public administration in maintenance; the rebuild's private admin stays on 127.0.0.1:9131); 302 to https://admin.quillmd.com/login/ is CPT Studio's operator console once release 2 of the admin.quillmd.com move is installed. Narrowed to the second when that release lands. Anything else - a 502, a 200, a 404, a 302 elsewhere, a 503 that is not the notice (CPT Studio's outage page) - is the finding."
  "pro.quillmd.com|410|DELIBERATELY RETIRED. The meddoc-pro CRM container was stopped (SIGTERM) on ~2026-08-04 and Caddy answers Gone. A change AWAY from 410 is the finding: either it started serving again, or a 502 is wearing its place."
)

have() { command -v "$1" >/dev/null 2>&1; }
have curl || { echo "🟡 cannot tell — curl not installed"; exit 2; }

# curl's exit codes for a TLS or certificate failure: a red row, never "no response"
TLS_EXITS=' 35 51 53 54 58 59 60 64 66 77 80 82 83 90 91 '

# matches <alternatives> <status> <redirect_url> <body file>: one alternative names this state
matches() {
  local alt
  local -a alts
  IFS=',' read -ra alts <<< "$1"
  for alt in "${alts[@]}"; do
    case "$alt" in
      *'>'*) [ "$2" = "${alt%%>*}" ] && [ "$3" = "${alt#*>}" ] && return 0 ;;
      *'~'*) [ "$2" = "${alt%%~*}" ] && [ -s "$4" ] && grep -qF -- "${alt#*~}" "$4" && return 0 ;;
      *) [ "$2" = "$alt" ] && return 0 ;;
    esac
  done
  return 1
}

declare -A SKIP=()
read -ra _skip_hosts <<< "${CPT_INSTALLER_SKIP_HOSTS:-}"
for h in "${_skip_hosts[@]}"; do
  if [ "$h" != admin.quillmd.com ]; then
    echo "🟡 cannot tell — CPT_INSTALLER_SKIP_HOSTS may name admin.quillmd.com only (CPT Studio's installer judges that host itself); it names '$h'. Nothing was probed."
    exit 2
  fi
  SKIP["$h"]=1
done

BODY="$(mktemp)"
trap 'rm -f "$BODY"' EXIT
declare -a OBSERVED=() JUDGED=()
findings=0; silent=0
printf '%-22s %-9s %s\n' HOST EXPECTED OBSERVED
for row in "${EXPECTED[@]}"; do
  host="${row%%|*}"; rest="${row#*|}"; want="${rest%%|*}"; why="${rest#*|}"
  if [ -n "${SKIP[$host]:-}" ]; then
    printf '  ⏭  %-20s SKIPPED: CPT_INSTALLER_SKIP_HOSTS names it (CPT Studio'"'"'s installer judges it); not judged here\n' "$host"
    continue
  fi
  : > "$BODY"
  # -I HEAD unless an expectation reads the body; no reuse across hosts; a generous but bounded timeout
  case "$want" in
    *'~'*) answer="$(curl -s -m 12 --max-filesize 65536 -o "$BODY" -w '%{http_code} %{redirect_url}' "https://$host" 2>/dev/null)"; rc=$? ;;
    *) answer="$(curl -sI -o /dev/null -m 12 -w '%{http_code} %{redirect_url}' "https://$host" 2>/dev/null)"; rc=$? ;;
  esac
  if [ "$rc" -ne 0 ] || ! [[ $answer =~ ^[0-9]{3}\  ]] || [ "${answer%% *}" = 000 ]; then
    if [[ $TLS_EXITS == *" $rc "* ]]; then answer="tls "; else answer="000 "; fi
  fi
  got="${answer%% *}"; target="${answer#* }"
  JUDGED+=("$want")
  case "$want" in
    *'>'*|*'~'*) OBSERVED+=("$got>$target"); shown="$got${target:+ → $target}" ;;
    *) OBSERVED+=("$got"); shown="$got" ;;
  esac
  if [ "$got" = 000 ]; then
    silent=$((silent + 1))
    printf '  🟡 %-20s %-9s %s  (no response — network or DNS)\n' "$host" "$want" "$got"
  elif [ "$got" = tls ]; then
    findings=$((findings + 1))
    printf '  🔴 %-20s %-9s %s  (the TLS handshake failed: curl exit %s)\n' "$host" "$want" "$got" "$rc"
    echo "     WHY $want WAS EXPECTED: $why"
  elif matches "$want" "$got" "$target" "$BODY"; then
    printf '  🟢 %-20s %-9s %s\n' "$host" "$want" "$shown"
  else
    findings=$((findings + 1))
    printf '  🔴 %-20s %-9s %s\n' "$host" "$want" "$shown"
    echo "     WHY $want WAS EXPECTED: $why"
  fi
done
if [ "$silent" -gt 0 ]; then
  if [ "$findings" -gt 0 ]; then
    echo "🔴 $findings co-tenant(s) diverged from the expected status (and $silent did not respond). That is THE FINDING."
    exit 1
  fi
  echo "🟡 cannot tell — $silent host(s) did not respond at all."
  exit 2
fi

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
