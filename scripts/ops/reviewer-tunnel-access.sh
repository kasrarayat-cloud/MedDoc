#!/usr/bin/env bash
# Least-privilege SSH access for the independent penetration tester.
#
# A key's permitopen options restrict local TCP forwarding only. They do NOT
# prohibit remote TCP or Unix-socket forwarding. Never grant reviewer access to
# the shared operator account. Prepare a dedicated-account policy for host-admin
# activation after its effective configuration and reviewer/window are approved.
#
#   bash scripts/ops/reviewer-tunnel-access.sh prepare <reviewer-id> <public-key-file> <window-end-UTC>
#   bash scripts/ops/reviewer-tunnel-access.sh revoke <reviewer-id>
#   bash scripts/ops/reviewer-tunnel-access.sh status
#
# revoke/status cover historical shared-account entries only. Removing a key or
# expiry-time prevents NEW authentication; existing SSH connections survive and
# need scoped termination against the dedicated reviewer identity at window end.
set -euo pipefail
umask 077
action=${1:-}
keys="$HOME/.ssh/authorized_keys"
record_dir="/opt/meddoc-pro/rebuild/.runtime/reviewer-access"
tag_prefix="quillmd-reviewer:"

require() { if ! eval "$1"; then echo "REFUSED: $2" >&2; exit 1; fi; }

case "$action" in
  grant)
    echo "REFUSED: shared-account reviewer grants cannot enforce the promised tunnel boundary. Use prepare; a host administrator must activate and verify the dedicated-account SSH policy." >&2
    exit 1
    ;;
  prepare)
    reviewer=${2:-}; keyfile=${3:-}; window_end=${4:-}
    require '[[ "$reviewer" =~ ^[a-z0-9][a-z0-9-]{2,39}$ ]]' "reviewer id must be a short lowercase slug"
    require '[[ -f "$keyfile" ]]' "public key file not found"
    require '[[ "$window_end" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}Z$ ]]' "window end must be UTC like 2026-09-20T18:00Z"
    normalized=$(date -u -d "$window_end" +%Y-%m-%dT%H:%MZ 2>/dev/null) || { echo "REFUSED: invalid calendar date" >&2; exit 1; }
    require '[[ "$normalized" == "$window_end" ]]' "window end must be an exact valid UTC minute"
    mapfile -t key_lines < "$keyfile"
    require '[[ ${#key_lines[@]} -eq 1 ]]' "key file must contain exactly one public key line"
    key=${key_lines[0]%$'\r'}
    require '[[ "$key" =~ ^(ssh-ed25519|sk-ssh-ed25519@openssh.com|ssh-rsa)\ [A-Za-z0-9+/=]+ ]]' "unsupported key type; use ed25519 (or rsa >= 3072)"
    require 'ssh-keygen -lf "$keyfile" >/dev/null 2>&1' "invalid public key"
    if [[ "$key" =~ ^ssh-rsa ]]; then
      bits=$(ssh-keygen -lf "$keyfile" | awk '{print $1}')
      require '[[ "$bits" -ge 3072 ]]' "rsa key shorter than 3072 bits"
    fi
    key_body=$(printf '%s' "$key" | awk '{print $1" "$2}')
    now=$(date -u +%Y-%m-%dT%H:%MZ)
    require '[[ "$window_end" > "$now" ]]' "window end is in the past"
    mkdir -p "$record_dir"; chmod 700 "$record_dir"
    prepared=$(mktemp -d "$record_dir/prepared-$reviewer-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
    expiry=$(date -u -d "$window_end" +%Y%m%d%H%MZ)
    options="restrict,port-forwarding,expiry-time=\"$expiry\",permitopen=\"127.0.0.1:9130\",permitopen=\"127.0.0.1:9131\",command=\"/bin/false\""
    printf '%s %s %s%s window-end=%s\n' "$options" "$key_body" "$tag_prefix" "$reviewer" "$window_end" > "$prepared/authorized_keys"
    cat > "$prepared/sshd-match.conf" <<'POLICY'
# Dedicated account only. Never apply to the shared operator identity.
Match User quillmd-reviewer
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding local
    AllowStreamLocalForwarding no
    PermitOpen 127.0.0.1:9130 127.0.0.1:9131
    PermitListen none
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    PermitUserRC no
    PermitTunnel no
    MaxSessions 0
    ForceCommand /bin/false
Match all
POLICY
    fingerprint=$(ssh-keygen -lf "$keyfile" | awk '{print $2}')
    printf '{"event":"prepared_not_granted","reviewer":"%s","fingerprint":"%s","prepared_at":"%s","window_end":"%s","permitopen":["127.0.0.1:9130","127.0.0.1:9131"],"shell":false}\n' \
      "$reviewer" "$fingerprint" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$window_end" > "$prepared/event.json"
    echo "PREPARED ONLY: $prepared"
    echo "No access granted. Host-admin activation, effective sshd verification and termination of established connections at window end remain required."
    ;;
  revoke)
    reviewer=${2:-}
    require '[[ "$reviewer" =~ ^[a-z0-9][a-z0-9-]{2,39}$ ]]' "reviewer id must be a short lowercase slug"
    # Keep the lock inode: unlinking it would allow later writers to lock a
    # different inode and resurrect a key from a stale snapshot.
    exec 9>"$(dirname "$keys")/.quillmd-reviewer-revoke.lock"
    flock -x 9
    require 'grep -qF "$tag_prefix$reviewer " "$keys"' "no grant found for $reviewer"
    before=$(grep -cF "$tag_prefix$reviewer " "$keys")
    require '[[ "$before" -eq 1 ]]' "expected exactly one grant line, found $before"
    # Establish an append-only write-ahead record BEFORE changing authorization.
    mkdir -p "$record_dir"; chmod 700 "$record_dir"
    event=$(mktemp "$record_dir/revoked-$reviewer-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.jsonl")
    before_hash=$(sha256sum "$keys" | awk '{print $1}')
    printf '{"event":"revocation_requested","reviewer":"%s","requested_at":"%s","authorization_sha256_before":"%s"}\n' "$reviewer" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$before_hash" > "$event"
    tmp=""
    revoke_cleanup() {
      result=$?
      rm -f "$tmp"
      if [[ "$result" -ne 0 ]]; then
        printf '{"event":"revocation_failed","exit_status":%s,"failed_at":"%s"}\n' "$result" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$event" || echo "ERROR: failed to append audit outcome; preserve write-ahead record $event" >&2
      fi
    }
    trap revoke_cleanup EXIT
    tmp=$(mktemp "$(dirname "$keys")/.authorized_keys.XXXXXX")
    # grep returns 1 when the final grant was the only line. That is success for
    # removal, not an error that should leave the grant in place under set -e.
    grep -vF "$tag_prefix$reviewer " "$keys" > "$tmp" || [[ $? == 1 ]]
    require '[[ "$(sha256sum "$keys" | awk '\''{print $1}'\'')" == "$before_hash" ]]' "authorization changed outside this helper; retry after coordinating the writer"
    chmod 600 "$tmp"; mv "$tmp" "$keys"
    require '! grep -qF "$tag_prefix$reviewer " "$keys"' "grant line survived removal"
    printf '{"event":"key_removed","reviewer":"%s","revoked_at":"%s","established_connections_terminated":false}\n' "$reviewer" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$event"
    echo "REMOVED authorization for $reviewer; established connections are NOT terminated."
    ;;
  status)
    now=$(date -u +%Y-%m-%dT%H:%MZ)
    if [[ ! -e "$keys" && ! -L "$keys" ]]; then echo "authorization file does not exist; no entries inspected"; exit 0; fi
    require '[[ -f "$keys" && -r "$keys" ]]' "authorization file is not a readable regular file; status unknown"
    matched=$(grep -F "$tag_prefix" "$keys") || {
      result=$?
      if [[ "$result" -eq 1 ]]; then echo "no reviewer grants present in readable authorization file"; exit 0; fi
      echo "REFUSED: could not read authorization file; status unknown" >&2; exit "$result"
    }
    printf '%s\n' "$matched" | while read -r line; do
      id=$(printf '%s' "$line" | grep -o "$tag_prefix[a-z0-9-]*" | sed "s/^$tag_prefix//")
      end=$(printf '%s' "$line" | grep -o 'window-end=[^ ]*' | cut -d= -f2)
      state="present (effective server policy not verified)"
      [[ "$end" > "$now" ]] || state="WINDOW ENDED — remove key and terminate established connections"
      echo "$id  window-end=$end  $state"
    done
    ;;
  *)
    echo "usage: $0 prepare <reviewer-id> <public-key-file> <window-end-UTC> | revoke <legacy-reviewer-id> | status (grant is disabled)" >&2; exit 2;;
esac
