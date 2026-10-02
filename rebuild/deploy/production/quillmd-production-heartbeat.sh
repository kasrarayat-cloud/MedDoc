#!/usr/bin/env bash
# QuillMD production outside-host heartbeat, run by quillmd-production-heartbeat.service.
#
# 1. Both surfaces must answer /health/ with HTTP 200 on this host (through loopback, as the host
#    proxy would, with X-Forwarded-Proto https so the HTTPS redirect does not stand in for health).
# 2. The doctor surface must answer /health/ready/ with 200: the worker's heartbeat is recent, the
#    queue is within its thresholds and processing health is not in error (core.readiness, thresholds
#    and the alarm table in ops/alarms.json). Readiness answers on the host only, as here.
# 3. Only then is the owner-controlled check URL pinged. The check service raises the alert when a
#    ping is MISSING, so host loss, service failure, network loss and a stopped or stuck worker all
#    produce one.
#
# The check URL is a credential (anyone holding it can suppress the alert): it arrives through
# systemd LoadCredential from a root-only file and is never printed. No patient data is sent: the
# ping carries no body.
set -euo pipefail

url_file="${CREDENTIALS_DIRECTORY:?heartbeat: no credentials directory}/heartbeat-url"
url=$(head -c 512 -- "$url_file" | tr -d '\r\n')
case "$url" in
  https://hc-ping.com/*) ;;
  *) echo "heartbeat: the check URL is not an https://hc-ping.com/ address; refusing" >&2; exit 2 ;;
esac

check() {
  local port=$1 host=$2 code
  code=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 10 \
    --header "Host: ${host}" --header 'X-Forwarded-Proto: https' "http://127.0.0.1:${port}/health/") || code=000
  if [ "$code" != "200" ]; then
    echo "heartbeat: ${host} /health/ answered ${code}; no ping sent" >&2
    return 1
  fi
}

ready() {
  local port=$1 host=$2 code
  code=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 10 \
    --header "Host: ${host}" --header 'X-Forwarded-Proto: https' "http://127.0.0.1:${port}/health/ready/") || code=000
  if [ "$code" != "200" ]; then
    echo "heartbeat: ${host} /health/ready/ answered ${code}; not ready; no ping sent" >&2
    return 1
  fi
}

check 9140 app.quillmd.com
check 9141 admin.quillmd.com
ready 9140 app.quillmd.com
curl --silent --show-error --output /dev/null --max-time 10 --retry 3 --retry-delay 5 --fail -- "$url"
echo "heartbeat: both surfaces healthy and ready; ping delivered"
