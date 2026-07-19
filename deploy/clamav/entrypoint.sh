#!/bin/sh
set -eu

socket_dir=/run/clamav
database_dir=/var/lib/clamav
clamd_config=/etc/clamav/clamd.conf
freshclam_config=/etc/clamav/freshclam.conf
max_age_seconds="${CLAMAV_SIGNATURE_MAX_AGE_SECONDS:-172800}"

case "$max_age_seconds" in
  ''|*[!0-9]*)
    echo "ClamAV signature freshness limit is invalid" >&2
    exit 1
    ;;
esac
if [ "$max_age_seconds" -lt 3600 ] || [ "$max_age_seconds" -gt 604800 ]; then
  echo "ClamAV signature freshness limit is outside the safe range" >&2
  exit 1
fi

if grep -Eq '^[[:space:]]*(TCPAddr|TCPSocket)[[:space:]]' "$clamd_config"; then
  echo "ClamAV TCP listeners are forbidden for Template Twin" >&2
  exit 1
fi
grep -Eq '^[[:space:]]*LocalSocket[[:space:]]+/run/clamav/clamd\.sock[[:space:]]*$' "$clamd_config"
grep -Eq '^[[:space:]]*LocalSocketMode[[:space:]]+660[[:space:]]*$' "$clamd_config"

install -d -o clamav -g clamav -m 0770 "$socket_dir"
chown -R clamav:clamav "$database_dir"

signature_is_fresh() {
  signature_file=''
  for candidate in "$database_dir/daily.cld" "$database_dir/daily.cvd"; do
    if [ -f "$candidate" ]; then
      signature_file="$candidate"
      break
    fi
  done
  [ -n "$signature_file" ] || return 1
  modified_at="$(stat -c %Y "$signature_file")"
  now="$(date +%s)"
  age="$((now - modified_at))"
  [ "$age" -ge 0 ] && [ "$age" -le "$max_age_seconds" ]
}

# The pinned image contains a bootstrap database, but a persistent volume may
# be older than the admission freshness limit. Refresh synchronously before
# clamd starts; a failed refresh with stale signatures leaves the service
# unready instead of serving scans with outdated evidence.
if ! signature_is_fresh; then
  bootstrap_config=/tmp/freshclam-bootstrap.conf
  sed '/^[[:space:]]*NotifyClamd[[:space:]]/d' "$freshclam_config" > "$bootstrap_config"
  freshclam --foreground --stdout --config-file="$bootstrap_config"
  rm -f "$bootstrap_config"
fi
if ! signature_is_fresh; then
  echo "ClamAV signatures are missing or stale after refresh" >&2
  exit 1
fi

exec /init
