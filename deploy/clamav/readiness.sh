#!/bin/sh
set -eu

socket_path=/run/clamav/clamd.sock
database_dir=/var/lib/clamav
clamd_config=/etc/clamav/clamd.conf
max_age_seconds="${CLAMAV_SIGNATURE_MAX_AGE_SECONDS:-172800}"

case "$max_age_seconds" in
  ''|*[!0-9]*) exit 1 ;;
esac

test -S "$socket_path"
test "$(stat -c %a "$socket_path")" = "660"
clamdscan --config-file="$clamd_config" --ping=1 >/dev/null

signature_file=''
for candidate in "$database_dir/daily.cld" "$database_dir/daily.cvd"; do
  if [ -f "$candidate" ]; then
    signature_file="$candidate"
    break
  fi
done
test -n "$signature_file"
modified_at="$(stat -c %Y "$signature_file")"
now="$(date +%s)"
age="$((now - modified_at))"
test "$age" -ge 0
test "$age" -le "$max_age_seconds"
