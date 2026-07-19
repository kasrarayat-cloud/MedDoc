#!/bin/sh
set -eu

socket_path=/run/clamav/clamd.sock
database_dir=/var/lib/clamav
clamd_config=/etc/clamav/clamd.conf
max_age_seconds="${CLAMAV_SIGNATURE_MAX_AGE_SECONDS:-172800}"
readiness_file=/run/clamav/readiness.json
readiness_tmp=''

cleanup() {
  status="$?"
  if [ "$status" -ne 0 ]; then
    rm -f "$readiness_file"
  fi
  if [ -n "$readiness_tmp" ]; then
    rm -f "$readiness_tmp"
  fi
  trap - EXIT
  exit "$status"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

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

version_output="$(clamdscan --config-file="$clamd_config" --version)"
signature_version="$(
  printf '%s\n' "$version_output" |
    sed -n 's#^ClamAV [^/]*/\([0-9][0-9]*\)/.*#\1#p'
)"
case "$signature_version" in
  ''|*[!0-9]*) exit 1 ;;
esac

# Health is a process-local Docker property, so publish a short-lived lease in
# the same read-only-to-app volume as the socket. Admission validates its age,
# signature-file age, and signature version both before and after each scan.
readiness_tmp="${readiness_file}.tmp.$$"
umask 0027
printf '%s\n' \
  "{\"profileVersion\":\"quillmd-clamav-readiness-v1\",\"checkedAtEpochSeconds\":$now,\"signatureModifiedAtEpochSeconds\":$modified_at,\"signatureMaxAgeSeconds\":$max_age_seconds,\"signatureVersion\":\"$signature_version\"}" \
  > "$readiness_tmp"
chown clamav:clamav "$readiness_tmp"
chmod 0640 "$readiness_tmp"
mv -f "$readiness_tmp" "$readiness_file"
readiness_tmp=''
