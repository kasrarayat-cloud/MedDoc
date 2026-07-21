#!/bin/sh
set -eu
set +x

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

contract_path=/etc/postgresql/quillmd-pg_hba.conf
contract_sha256=8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0

fail() {
  printf '%s\n' 'QUILLMD_POSTGRES_HOST_AUTH_FAIL' >&2
  exit 1
}

actual_sha256=$(
  LC_ALL=C sha256sum "$contract_path" 2>/dev/null | cut -d ' ' -f 1
) || fail
[ "$actual_sha256" = "$contract_sha256" ] || fail

# The health proof is socket-local and target-explicit. Ambient libpq routing,
# credentials, services, and session settings must not redirect it.
unset PGHOST PGHOSTADDR PGPORT PGDATABASE PGUSER PGSERVICE PGSERVICEFILE
unset PGOPTIONS PGPASSWORD PGPASSFILE

result=$(
  PGCONNECT_TIMEOUT=3 psql -X --no-psqlrc --quiet --tuples-only --no-align \
    --set ON_ERROR_STOP=1 \
    --host /var/run/postgresql --port 5432 \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --command "
      SELECT
        pg_catalog.current_setting('server_version_num')::INTEGER
          BETWEEN 160000 AND 169999
        AND pg_catalog.current_setting('hba_file') =
          '$contract_path'
        AND pg_catalog.current_setting('password_encryption') =
          'scram-sha-256'
        AND pg_catalog.current_setting(
          'quillmd.hba_contract_path', TRUE
        ) = '$contract_path'
        AND pg_catalog.current_setting(
          'quillmd.hba_contract_sha256', TRUE
        ) = '$contract_sha256'
        AND pg_catalog.inet_client_addr() IS NULL
        -- pg_hba_file_rules reflects current file bytes, not necessarily the
        -- generation loaded by postmaster. This immutable release contract
        -- therefore rejects every SIGHUP-era configuration reload. A restart
        -- from the reviewed Compose command is required before health can
        -- return green, proving the loaded generation began with these bytes.
        AND pg_catalog.pg_conf_load_time() <=
          pg_catalog.pg_postmaster_start_time()
        AND (
          SELECT pg_catalog.jsonb_agg(
            pg_catalog.jsonb_build_array(
              rule_number,
              type,
              database,
              user_name,
              address::TEXT,
              netmask::TEXT,
              auth_method,
              options,
              error
            ) ORDER BY rule_number
          )
          FROM pg_catalog.pg_hba_file_rules
        ) = pg_catalog.jsonb_build_array(
          pg_catalog.jsonb_build_array(
            1, 'local', ARRAY['replication'], ARRAY['all'],
            NULL, NULL, 'reject', NULL, NULL
          ),
          pg_catalog.jsonb_build_array(
            2, 'host', ARRAY['replication'], ARRAY['all'],
            'all', NULL, 'reject', NULL, NULL
          ),
          pg_catalog.jsonb_build_array(
            3, 'local', ARRAY['all'], ARRAY['all'],
            NULL, NULL, 'trust', NULL, NULL
          ),
          pg_catalog.jsonb_build_array(
            4, 'host', ARRAY['all'], ARRAY[
              'meddoc',
              'meddoc_runtime',
              'meddoc_release_control',
              'meddoc_release_security',
              'meddoc_audit_dispatcher',
              'meddoc_auth_email_dispatcher',
              'meddoc_backup'
            ], 'all', NULL, 'scram-sha-256', NULL, NULL
          ),
          pg_catalog.jsonb_build_array(
            5, 'host', ARRAY['all'], ARRAY['all'],
            '0.0.0.0', '0.0.0.0', 'reject', NULL, NULL
          ),
          pg_catalog.jsonb_build_array(
            6, 'host', ARRAY['all'], ARRAY['all'],
            '::', '::', 'reject', NULL, NULL
          )
        );
    " 2>/dev/null
) || fail

[ "$result" = "t" ] || fail
exit 0
