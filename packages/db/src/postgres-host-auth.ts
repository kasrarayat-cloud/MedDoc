import { Prisma } from "@prisma/client";

interface HostAuthenticationQueryClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

interface PostgresHostAuthenticationRow {
  contractPath: string | null;
  contractSha256: string | null;
  passwordEncryption: string;
  tcpSession: boolean;
  initialConfigGeneration: boolean;
}

export const QUILLMD_POSTGRES_HBA_CONTRACT = Object.freeze({
  path: "/etc/postgresql/quillmd-pg_hba.conf",
  sha256: "8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0",
  passwordEncryption: "scram-sha-256",
} as const);

/**
 * Ordinary-session half of the PostgreSQL host-authentication proof.
 *
 * The container-local owner healthcheck independently hashes and parses the
 * read-only HBA file. This assertion binds each admitted application session
 * to that exact server startup contract and to TCP, without exposing HBA
 * contents or requiring a privileged database helper.
 */
export async function assertPostgresHostAuthenticationContract(input: {
  prisma: HostAuthenticationQueryClient;
}): Promise<void> {
  const rows = await input.prisma.$queryRaw<PostgresHostAuthenticationRow[]>(
    Prisma.sql`
      SELECT
        pg_catalog.current_setting(
          'quillmd.hba_contract_path', TRUE
        )::TEXT AS "contractPath",
        pg_catalog.current_setting(
          'quillmd.hba_contract_sha256', TRUE
        )::TEXT AS "contractSha256",
        pg_catalog.current_setting(
          'password_encryption'
        )::TEXT AS "passwordEncryption",
        pg_catalog.inet_client_addr() IS NOT NULL AS "tcpSession",
        pg_catalog.pg_conf_load_time() <=
          pg_catalog.pg_postmaster_start_time()
          AS "initialConfigGeneration"
    `,
  );
  const row = rows[0];
  if (
    rows.length !== 1 ||
    !row ||
    row.contractPath !== QUILLMD_POSTGRES_HBA_CONTRACT.path ||
    row.contractSha256 !== QUILLMD_POSTGRES_HBA_CONTRACT.sha256 ||
    row.passwordEncryption !==
      QUILLMD_POSTGRES_HBA_CONTRACT.passwordEncryption ||
    row.tcpSession !== true ||
    row.initialConfigGeneration !== true
  ) {
    throw new Error("Exact PostgreSQL host authentication is required.");
  }
}
