#!/usr/bin/env bash
# Least-privilege SSH access for the independent penetration tester.
#
# The VPS has no sudo for the operator, so the reviewer cannot get a separate OS
# account. The narrowest grant available is a forced-command, tunnel-only entry
# in this user's authorized_keys that permits TCP forwarding ONLY to the two
# private application listeners and nothing else: no shell, no pty, no agent or
# X11 forwarding, no other ports.
#
#   bash scripts/ops/reviewer-tunnel-access.sh grant  <reviewer-id> <public-key-file> <window-end-UTC>
#   bash scripts/ops/reviewer-tunnel-access.sh revoke <reviewer-id>
#   bash scripts/ops/reviewer-tunnel-access.sh status
#
# The reviewer then uses:
#   ssh -N -L 9130:127.0.0.1:9130 -L 9131:127.0.0.1:9131 <vps-user>@<vps-host>
# Any attempt to open a shell runs /bin/false and exits. Revoke at the window end;
# `status` prints grants whose window has passed so nothing lingers silently.
set -euo pipefail
umask 077
action=${1:-}
keys="$HOME/.ssh/authorized_keys"
record_dir="/opt/meddoc-pro/rebuild/.runtime/reviewer-access"
tag_prefix="quillmd-reviewer:"

require() { if ! eval "$1"; then echo "REFUSED: $2" >&2; exit 1; fi; }

case "$action" in
  grant)
    reviewer=${2:-}; keyfile=${3:-}; window_end=${4:-}
    require '[[ "$reviewer" =~ ^[a-z0-9][a-z0-9-]{2,39}$ ]]' "reviewer id must be a short lowercase slug"
    require '[[ -f "$keyfile" ]]' "public key file not found"
    require '[[ "$window_end" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}Z$ ]]' "window end must be UTC like 2026-09-20T18:00Z"
    require '[[ $(wc -l < "$keyfile") -le 1 ]]' "key file must contain exactly one public key line"
    key=$(tr -d '\r' < "$keyfile")
    require '[[ "$key" =~ ^(ssh-ed25519|sk-ssh-ed25519@openssh.com|ssh-rsa)\ [A-Za-z0-9+/=]+ ]]' "unsupported key type; use ed25519 (or rsa >= 3072)"
    if [[ "$key" =~ ^ssh-rsa ]]; then
      bits=$(ssh-keygen -lf "$keyfile" | awk '{print $1}')
      require '[[ "$bits" -ge 3072 ]]' "rsa key shorter than 3072 bits"
    fi
    key_body=$(printf '%s' "$key" | awk '{print $1" "$2}')
    require '! grep -qF "$tag_prefix$reviewer " "$keys" 2>/dev/null' "a grant for this reviewer already exists; revoke first"
    require '! grep -qF "$key_body" "$keys" 2>/dev/null' "this key is already authorized under another entry"
    now=$(date -u +%Y-%m-%dT%H:%MZ)
    require '[[ "$window_end" > "$now" ]]' "window end is in the past"
    mkdir -p "$HOME/.ssh" "$record_dir"; chmod 700 "$HOME/.ssh" "$record_dir"
    touch "$keys"; chmod 600 "$keys"
    options='restrict,port-forwarding,permitopen="127.0.0.1:9130",permitopen="127.0.0.1:9131",command="/bin/false"'
    printf '%s %s %s%s window-end=%s\n' "$options" "$key_body" "$tag_prefix" "$reviewer" "$window_end" >> "$keys"
    require 'grep -qF "$tag_prefix$reviewer " "$keys"' "grant line was not written"
    fingerprint=$(ssh-keygen -lf "$keyfile" | awk '{print $2}')
    printf '{"reviewer":"%s","fingerprint":"%s","granted_at":"%s","window_end":"%s","permitopen":["127.0.0.1:9130","127.0.0.1:9131"],"shell":false}\n' \
      "$reviewer" "$fingerprint" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$window_end" > "$record_dir/$reviewer.json"
    chmod 600 "$record_dir/$reviewer.json"
    echo "GRANTED tunnel-only access for $reviewer (fingerprint $fingerprint) until $window_end"
    ;;
  revoke)
    reviewer=${2:-}
    require '[[ "$reviewer" =~ ^[a-z0-9][a-z0-9-]{2,39}$ ]]' "reviewer id must be a short lowercase slug"
    require 'grep -qF "$tag_prefix$reviewer " "$keys"' "no grant found for $reviewer"
    before=$(grep -cF "$tag_prefix$reviewer " "$keys")
    require '[[ "$before" -eq 1 ]]' "expected exactly one grant line, found $before"
    tmp=$(mktemp "$HOME/.ssh/.authorized_keys.XXXXXX")
    grep -vF "$tag_prefix$reviewer " "$keys" > "$tmp"
    chmod 600 "$tmp"; mv "$tmp" "$keys"
    require '! grep -qF "$tag_prefix$reviewer " "$keys"' "grant line survived removal"
    if [[ -f "$record_dir/$reviewer.json" ]]; then
      printf '{"revoked_at":"%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$record_dir/$reviewer.json"
    fi
    echo "REVOKED tunnel access for $reviewer"
    ;;
  status)
    now=$(date -u +%Y-%m-%dT%H:%MZ)
    if ! grep -F "$tag_prefix" "$keys" 2>/dev/null | grep -q .; then echo "no reviewer grants present"; exit 0; fi
    grep -F "$tag_prefix" "$keys" | while read -r line; do
      id=$(printf '%s' "$line" | grep -o "$tag_prefix[a-z0-9-]*" | sed "s/^$tag_prefix//")
      end=$(printf '%s' "$line" | grep -o 'window-end=[^ ]*' | cut -d= -f2)
      state="active"; [[ "$end" < "$now" ]] && state="EXPIRED — revoke now"
      echo "$id  window-end=$end  $state"
    done
    ;;
  *)
    echo "usage: $0 grant <reviewer-id> <public-key-file> <window-end-UTC> | revoke <reviewer-id> | status" >&2; exit 2;;
esac
