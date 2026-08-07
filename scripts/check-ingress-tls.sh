#!/usr/bin/env bash
# ============================================================================
# Can nginx still complete a FRESH TLS handshake with Caddy, per hostname?
# ----------------------------------------------------------------------------
# This exists because on 2026-08-07 the answer was NO for every public hostname
# for six hours and fifteen minutes, and NOTHING reported it.
#
# Ingress: internet → host nginx (owns :80/:443) → Caddy at 127.0.0.1:8443 →
# app containers. nginx re-encrypts to Caddy with `proxy_ssl_name $host` and
# `proxy_ssl_verify off`.
#
# ⚠️ `proxy_ssl_verify off` IS WHY THIS NEEDS ITS OWN CHECK. Because nginx does
# not verify the upstream certificate, an EXPIRED cert on this hop works
# perfectly — so expiry is not merely unmonitored, it is UNOBSERVABLE from any
# normal signal. Caddy served expired certs out of its in-memory cache for
# weeks with every layer green.
#
# What actually failed: certmagic's storage clean removed those certs from disk
# (memory cache now the only copy), the host rebooted, the cache went with it,
# and Caddy came back holding no certificate at all. Every fresh handshake got
# `tlsv1 alert internal error` (alert 80); nginx turned each into a 502.
# Full write-up: docs/qa-reports/ingress-tls-outage-20260807.md
#
# ⚠️ WHY "FRESH" IS THE LOAD-BEARING WORD, AND WHY A CURL SWEEP IS NOT THIS
# CHECK. nginx REUSES upstream TLS sessions. During the outage, requests riding
# an already-resumed session kept returning 200/307 in the same second that
# fresh ones returned 502 — so the failure read as intermittent and
# path-specific, and it was neither. Only a probe that forces a NEW handshake
# per SNI separates "the cert is fine" from "the cache has not expired yet".
# `openssl s_client` with an explicit -servername is that probe.
#
# NEGATIVE CONTROL, RUN EVERY TIME: a bogus SNI must FAIL. If Caddy answers a
# name that does not exist, the probe cannot discriminate and its greens mean
# nothing — that is a `2`, not a `0`. A sweep that would pass on anything is
# indistinguishable from a sweep that passes because all is well.
#
# READ-ONLY. Opens TLS connections and closes them; writes nothing, mutates
# nothing, and never sends an HTTP request.
#
# Usage:  bash scripts/check-ingress-tls.sh
# Exit:   0 = every hostname handshakes · 1 = AT LEAST ONE FAILS · 2 = cannot tell
# ============================================================================
set -uo pipefail

UPSTREAM="127.0.0.1:8443"
# The hostnames nginx forwards on. Kept in step with the site blocks in
# ./Caddyfile and `server_name` in /etc/nginx/sites-enabled/quillmd.
HOSTS=(quillmd.com www.quillmd.com app.quillmd.com admin.quillmd.com)
BOGUS="this-name-is-not-configured.invalid"

have() { command -v "$1" >/dev/null 2>&1; }

if ! have openssl; then
  echo "🟡 cannot tell — openssl not installed"; exit 2
fi

if ! (exec 3<>/dev/tcp/127.0.0.1/8443) 2>/dev/null; then
  echo "🟡 cannot tell — nothing is listening on ${UPSTREAM}."
  echo "   Off-host, or Caddy is down. Check: docker ps | grep caddy"
  exit 2
fi

# Returns the issuer line on success; empty on handshake failure.
probe() {
  timeout 10 openssl s_client -connect "$UPSTREAM" -servername "$1" \
    </dev/null 2>/dev/null | grep -m1 '^issuer='
}

# ── The negative control comes FIRST, so a broken probe can never report 0 ──
if [ -n "$(probe "$BOGUS")" ]; then
  echo "🟡 cannot tell — the probe does not discriminate."
  echo "   ${BOGUS} completed a handshake, so a green below would be vacuous."
  echo "   (On-demand TLS, or a catch-all site block, would do this.)"
  exit 2
fi

fail=0
echo "fresh TLS handshake to ${UPSTREAM}, one per SNI:"
for h in "${HOSTS[@]}"; do
  issuer="$(probe "$h")"
  if [ -z "$issuer" ]; then
    printf '   ✘ %-22s NO HANDSHAKE — nginx will answer 502 for this host\n' "$h"
    fail=1
  else
    printf '   ✔ %-22s %s\n' "$h" "${issuer#issuer=}"
  fi
done
printf '   · %-22s refused (negative control — the probe discriminates)\n' "$BOGUS"

if [ "$fail" -ne 0 ]; then
  cat <<'EOS'

🔴 AT LEAST ONE HOSTNAME CANNOT COMPLETE A HANDSHAKE.

   Live traffic to it is 502ing right now, EXCEPT on already-resumed
   sessions — so a browser that has been here recently may still work and
   tell you nothing.

   Expect: issuer = "Caddy Local Authority". Public ACME cannot succeed on
   this hop (nginx owns :80 and :443, so both challenge types are blocked),
   which is why every site block carries `tls internal`. If a block lost it,
   that is the bug — do NOT "restore real certificates" here.

   ⚠️ A file bind-mount binds the INODE: editing ./Caddyfile with a tool that
   writes-then-renames does NOT reach the container, and `caddy validate`
   will happily green the OLD file. Confirm the container agrees, then
   force-recreate:

     docker exec meddoc-pro-caddy-1 grep -c '^    tls internal$' /etc/caddy/Caddyfile
     docker compose up -d --no-deps --force-recreate caddy

   docs/qa-reports/ingress-tls-outage-20260807.md
EOS
  exit 1
fi

echo
echo "🟢 every ingress hostname completes a fresh handshake"
exit 0
