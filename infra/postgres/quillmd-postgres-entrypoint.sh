#!/bin/sh
set -eu
set +x

contract_path=/etc/postgresql/quillmd-pg_hba.conf
contract_sha256=8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0
verifier_path=/opt/quillmd/verify-quillmd-host-auth.sh
verifier_sha256=c243bb5e2d1313025c392bb5a510e0e9d289b0f316e0eb236881484bb0d79e18

fail() {
  printf '%s\n' 'QUILLMD_POSTGRES_IMAGE_CONTRACT_FAIL' >&2
  exit 1
}

# Fail before the upstream entrypoint when an operator attempts to replace or
# append a protected PostgreSQL startup setting. The exact vector is repeated
# in the image CMD and both reviewed Compose profiles.
[ "$#" -eq 9 ] || fail
[ "$1" = postgres ] || fail
shift
[ "$1" = -c ] || fail
shift
[ "$1" = "hba_file=$contract_path" ] || fail
shift
[ "$1" = -c ] || fail
shift
[ "$1" = password_encryption=scram-sha-256 ] || fail
shift
[ "$1" = -c ] || fail
shift
[ "$1" = "quillmd.hba_contract_path=$contract_path" ] || fail
shift
[ "$1" = -c ] || fail
shift
[ "$1" = "quillmd.hba_contract_sha256=$contract_sha256" ] || fail

actual_contract_sha256=$(
  LC_ALL=C sha256sum "$contract_path" 2>/dev/null | cut -d ' ' -f 1
) || fail
actual_verifier_sha256=$(
  LC_ALL=C sha256sum "$verifier_path" 2>/dev/null | cut -d ' ' -f 1
) || fail

[ "$actual_contract_sha256" = "$contract_sha256" ] || fail
[ "$actual_verifier_sha256" = "$verifier_sha256" ] || fail
[ "$(stat -c '%u:%g:%a' "$contract_path" 2>/dev/null)" = 0:0:444 ] || fail
[ "$(stat -c '%u:%g:%a' "$verifier_path" 2>/dev/null)" = 0:0:555 ] || fail

exec /usr/local/bin/docker-entrypoint.sh \
  postgres \
  -c "hba_file=$contract_path" \
  -c password_encryption=scram-sha-256 \
  -c "quillmd.hba_contract_path=$contract_path" \
  -c "quillmd.hba_contract_sha256=$contract_sha256"
