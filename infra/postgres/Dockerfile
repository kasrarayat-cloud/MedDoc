FROM pgvector/pgvector:pg16@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff

USER root

# These files form one immutable startup contract. Runtime Compose mounts no
# replacement at either path; the release image digest therefore commits to
# the exact policy, its health proof, and the pre-entrypoint verifier.
COPY quillmd-pg_hba.conf /etc/postgresql/quillmd-pg_hba.conf
COPY verify-quillmd-host-auth.sh /opt/quillmd/verify-quillmd-host-auth.sh
COPY quillmd-postgres-entrypoint.sh /usr/local/bin/quillmd-postgres-entrypoint.sh

RUN set -eu; set +x; \
    chown 0:0 /etc/postgresql/quillmd-pg_hba.conf /opt/quillmd/verify-quillmd-host-auth.sh /usr/local/bin/quillmd-postgres-entrypoint.sh; \
    chmod 0444 /etc/postgresql/quillmd-pg_hba.conf; \
    chmod 0555 /opt/quillmd/verify-quillmd-host-auth.sh /usr/local/bin/quillmd-postgres-entrypoint.sh; \
    [ "$(sha256sum /etc/postgresql/quillmd-pg_hba.conf | cut -d ' ' -f 1)" = "8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0" ]; \
    [ "$(sha256sum /opt/quillmd/verify-quillmd-host-auth.sh | cut -d ' ' -f 1)" = "c243bb5e2d1313025c392bb5a510e0e9d289b0f316e0eb236881484bb0d79e18" ]; \
    [ "$(sha256sum /usr/local/bin/quillmd-postgres-entrypoint.sh | cut -d ' ' -f 1)" = "1121ef841eea8e0b2c7ba3e23c261f19c2806e17217eedd564eccf8c2d705d0a" ]; \
    [ "$(stat -c '%u:%g:%a' /etc/postgresql/quillmd-pg_hba.conf)" = "0:0:444" ]; \
    [ "$(stat -c '%u:%g:%a' /opt/quillmd/verify-quillmd-host-auth.sh)" = "0:0:555" ]; \
    [ "$(stat -c '%u:%g:%a' /usr/local/bin/quillmd-postgres-entrypoint.sh)" = "0:0:555" ]

USER 999:999

ENTRYPOINT ["/usr/local/bin/quillmd-postgres-entrypoint.sh"]
CMD ["postgres", "-c", "hba_file=/etc/postgresql/quillmd-pg_hba.conf", "-c", "password_encryption=scram-sha-256", "-c", "quillmd.hba_contract_path=/etc/postgresql/quillmd-pg_hba.conf", "-c", "quillmd.hba_contract_sha256=8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0"]
