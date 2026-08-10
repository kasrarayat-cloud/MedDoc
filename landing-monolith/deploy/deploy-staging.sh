#!/usr/bin/env bash
# =============================================================================
# Deploy the QuillMD "obsidian monolith" landing to staging.quillmd.com.
# NET-NEW static vhost served by host nginx. Touches NOTHING in production:
# not quillmd.com / app.quillmd.com, not Caddy, not any co-tenant vhost.
#
# PRECONDITIONS (both are Kasra's, and the script checks them):
#   1. DNS:  staging.quillmd.com  A  147.189.172.8   (must resolve to the VPS)
#   2. The two Higgsfield images are in public/assets/ (hero-monolith.*,
#      security-vault.*) and referenced by the components.
#
# Run from the repo on the VPS. Host-root steps use the documented
# docker --pid=host pattern (the claude user has no sudo).
# =============================================================================
set -euo pipefail

# ⚠️ REGISTRY-BLIP RETRY BUDGET — npm defaults to 2 retries / 60s ceiling, which
# an npm-registry blip outlasts (2026-08-10: three builds, one mechanism, twelve
# minutes). Exported once here so every npm command in this script inherits it.
export NPM_CONFIG_FETCH_RETRIES=5
export NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000
export NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WEBROOT="/var/www/quillmd-staging"
HOST="staging.quillmd.com"
VPS_IP="147.189.172.8"

echo "→ 1/6  DNS check: $HOST"
resolved="$(getent hosts "$HOST" | awk '{print $1}' | head -1 || true)"
if [ "$resolved" != "$VPS_IP" ]; then
  echo "✗ $HOST resolves to '${resolved:-nothing}', not $VPS_IP."
  echo "  Add this DNS record, then re-run:   $HOST  A  $VPS_IP   (grey-cloud / DNS-only)"
  exit 1
fi

echo "→ 2/6  Build static export"
cd "$APP_DIR"
npm ci --no-audit --no-fund
npm run build   # → out/

echo "→ 3/6  Stage files to $WEBROOT (host root via docker)"
docker run --rm --pid=host --security-opt apparmor=unconfined \
  -v /:/host -v "$APP_DIR/out":/src:ro alpine:latest sh -c "
    mkdir -p /host$WEBROOT &&
    rm -rf /host$WEBROOT/* &&
    cp -r /src/. /host$WEBROOT/ &&
    echo staged \$(find /host$WEBROOT -type f | wc -l) files"

echo "→ 4/6  Install the nginx vhost (HTTP only first, for the ACME challenge)"
# (Manual: copy deploy/staging.quillmd.com.nginx.conf to
#  /etc/nginx/sites-available/quillmd-staging, symlink into sites-enabled.
#  The HTTPS server block references a cert that step 5 creates — enable the
#  HTTP block first OR install the full file after the cert exists.)

echo "→ 5/6  Issue the Let's Encrypt cert (webroot)"
echo "    certbot certonly --webroot -w /var/www/certbot -d $HOST --non-interactive --agree-tos -m support@ashtechgroup.com"

echo "→ 6/6  Validate + reload (NEVER restart)"
echo "    nginx -t  &&  nginx -s reload"

echo "✓ once 4–6 are applied: https://$HOST is live. Production + co-tenants untouched."
