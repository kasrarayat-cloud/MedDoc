import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";

import { afterAll, describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../../../..");
const CENSUS = path.join(ROOT, "scripts/database-principal-runtime-census.mjs");
const CANONICAL_OPTIONS = "options=-c%20search_path%3Dpg_catalog%2Cpublic";
const CANONICAL_QUERY = `schema=public&${CANONICAL_OPTIONS}`;
const STATIC_STATEMENT_TIMEOUT = "${PRISMA_STATEMENT_TIMEOUT_MS:-30000}";
const STATIC_MIGRATION_LOCK_TIMEOUT =
  "${DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS:-5000}";
const MIGRATION_NETWORK_BOUNDARY = "postgres-loopback-v1";
const BACKUP_IMAGE =
  "prodrigestivill/postgres-backup-local@sha256:a0103fbce0c48ccc7693ddbb2a2bfa733048db845354f635efef9e4566de185d";
const STATIC_POSTGRES_IMAGE =
  "${QUILLMD_POSTGRES_IMAGE:?QUILLMD_POSTGRES_IMAGE must be an immutable sha256 digest}";
const STATIC_QA_POSTGRES_IMAGE =
  "${QA_POSTGRES_IMAGE:-meddoc-qa-postgres:latest}";
const APPROVED_POSTGRES_IMAGE = `registry.invalid/quillmd/postgres@sha256:${"f".repeat(64)}`;
const APPROVED_QA_POSTGRES_IMAGE = `sha256:${"e".repeat(64)}`;
const POSTGRES_HBA_PATH = "/etc/postgresql/quillmd-pg_hba.conf";
const POSTGRES_HBA_VERIFIER_PATH = "/opt/quillmd/verify-quillmd-host-auth.sh";
const POSTGRES_ENTRYPOINT_PATH =
  "/usr/local/bin/quillmd-postgres-entrypoint.sh";
const POSTGRES_HBA_SHA256 =
  "8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0";
const POSTGRES_HBA_COMMAND = [
  "postgres",
  "-c",
  `hba_file=${POSTGRES_HBA_PATH}`,
  "-c",
  "password_encryption=scram-sha-256",
  "-c",
  `quillmd.hba_contract_path=${POSTGRES_HBA_PATH}`,
  "-c",
  `quillmd.hba_contract_sha256=${POSTGRES_HBA_SHA256}`,
];
const PASSWORD_ENVIRONMENT_BY_LOGIN: Record<string, string> = {
  meddoc: "DB_PASSWORD",
  meddoc_audit_dispatcher: "DB_AUDIT_DISPATCHER_PASSWORD",
  meddoc_auth_email_dispatcher: "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
  meddoc_release_control: "DB_RELEASE_CONTROL_PASSWORD",
  meddoc_runtime: "DB_RUNTIME_PASSWORD",
};
const QA_PASSWORD_ENVIRONMENT_BY_LOGIN: Record<string, string> = {
  meddoc_audit_dispatcher: "QA_DB_AUDIT_DISPATCHER_PASSWORD",
  meddoc_auth_email_dispatcher: "QA_DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
  meddoc_release_control: "QA_DB_RELEASE_CONTROL_PASSWORD",
  meddoc_runtime: "QA_DB_RUNTIME_PASSWORD",
};
const RESOLVED_CREDENTIAL_BY_LOGIN: Record<string, string> = {
  meddoc: "A".repeat(43),
  meddoc_audit_dispatcher: "B".repeat(43),
  meddoc_auth_email_dispatcher: "C".repeat(43),
  meddoc_release_control: "D".repeat(43),
  meddoc_runtime: "E".repeat(43),
};
const DATABASE_CREDENTIAL_ENVIRONMENT_KEYS = [
  "DB_PASSWORD",
  "DB_RUNTIME_PASSWORD",
  "DB_RELEASE_CONTROL_PASSWORD",
  "DB_RELEASE_SECURITY_PASSWORD",
  "DB_AUDIT_DISPATCHER_PASSWORD",
  "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
  "DB_BACKUP_PASSWORD_FILE",
  "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
] as const;
const TEMPLATE_TWIN_NEXT_RUNTIME_SERVICES = [
  "transcribe-md",
  "template-twin-admin-app",
  "template-twin-admin-control",
] as const;
const STATIC_TEMPLATE_TWIN_NEXT_MEMORY_LIMIT = "768m";
const RESOLVED_TEMPLATE_TWIN_NEXT_MEMORY_LIMIT = "805306368";
const APPROVED_FRONTEND_IMAGE = `registry.invalid/quillmd/transcribe@sha256:${"a".repeat(64)}`;
const APPROVED_WORKER_IMAGE = `registry.invalid/quillmd/worker@sha256:${"b".repeat(64)}`;
const APPROVED_QA_MIGRATOR_IMAGE = `registry.invalid/quillmd/migrator@sha256:${"d".repeat(64)}`;
const APPROVED_RELEASE_SHA = "c".repeat(40);
const APPROVED_KEYRING_DIRECTORY = mkdtempSync(
  path.join(os.tmpdir(), "meddoc-runtime-keyring-"),
);
const APPROVED_KEYRING_PATH = path.join(
  APPROVED_KEYRING_DIRECTORY,
  "mfa-keyring.json",
);
const APPROVED_QA_BACKUP_PASSWORD_PATH = path.join(
  APPROVED_KEYRING_DIRECTORY,
  "qa-backup-password",
);
writeFileSync(APPROVED_KEYRING_PATH, '{"synthetic":"runtime-census"}\n', {
  mode: 0o600,
});
writeFileSync(APPROVED_QA_BACKUP_PASSWORD_PATH, "synthetic-only\n", {
  mode: 0o600,
});
afterAll(() => {
  rmSync(APPROVED_KEYRING_DIRECTORY, { force: true, recursive: true });
});

function copyPostgresHostAuthenticationSources(destinationRoot: string) {
  const destination = path.join(destinationRoot, "infra/postgres");
  mkdirSync(destination, { recursive: true });
  for (const [name, mode] of [
    [".dockerignore", 0o644],
    ["Dockerfile", 0o644],
    ["quillmd-pg_hba.conf", 0o644],
    ["quillmd-postgres-entrypoint.sh", 0o644],
    ["verify-quillmd-host-auth.sh", 0o755],
  ] as const) {
    writeFileSync(
      path.join(destination, name),
      readFileSync(path.join(ROOT, "infra/postgres", name)),
      { mode },
    );
  }
}

function staticCredential(login: string) {
  const name = PASSWORD_ENVIRONMENT_BY_LOGIN[login];
  if (!name) throw new Error(`unreviewed fixture login: ${login}`);
  return `\${${name}:?${name} is required}`;
}

function staticQaCredential(login: string) {
  const name = QA_PASSWORD_ENVIRONMENT_BY_LOGIN[login];
  if (!name) throw new Error(`unreviewed QA fixture login: ${login}`);
  return `\${${name}:?${name} is required}`;
}

const productionServices = {
  "meddoc-pro": ["meddoc-pro-app", "meddoc_runtime"],
  "transcribe-md": ["physician-app", "meddoc_runtime"],
  "template-twin-admin-app": ["template-twin-admin-app", "meddoc_runtime"],
  "template-twin-admin-control": [
    "template-twin-admin-control",
    "meddoc_release_control",
  ],
  "transcribe-md-worker": ["transcribe-md-worker", "meddoc_runtime"],
  "template-twin-audit-dispatcher": [
    "template-twin-audit-dispatcher",
    "meddoc_audit_dispatcher",
  ],
  "auth-email-dispatcher": [
    "auth-email-dispatcher",
    "meddoc_auth_email_dispatcher",
  ],
} as const;

function exactPostgresService() {
  return {
    image: STATIC_POSTGRES_IMAGE,
    entrypoint: [POSTGRES_ENTRYPOINT_PATH],
    command: POSTGRES_HBA_COMMAND,
    restart: "unless-stopped",
    user: "999:999",
    cap_drop: ["ALL"],
    read_only: true,
    tmpfs: [
      "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
      "/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=3777",
    ],
    cpus: "1.0",
    mem_limit: "512m",
    environment: {
      DB_AUDIT_DISPATCHER_PASSWORD:
        "${DB_AUDIT_DISPATCHER_PASSWORD:?DB_AUDIT_DISPATCHER_PASSWORD is required}",
      DB_AUTH_EMAIL_DISPATCHER_PASSWORD:
        "${DB_AUTH_EMAIL_DISPATCHER_PASSWORD:?DB_AUTH_EMAIL_DISPATCHER_PASSWORD is required}",
      DB_BACKUP_PASSWORD_FILE: "/run/secrets/postgres_backup_password",
      DB_RELEASE_CONTROL_PASSWORD:
        "${DB_RELEASE_CONTROL_PASSWORD:?DB_RELEASE_CONTROL_PASSWORD is required}",
      DB_RUNTIME_PASSWORD:
        "${DB_RUNTIME_PASSWORD:?DB_RUNTIME_PASSWORD is required}",
      PGDATA: "/var/lib/postgresql/data/pgdata",
      POSTGRES_DB: "meddoc",
      POSTGRES_INITDB_ARGS: "--auth-host=scram-sha-256 --auth-local=trust",
      POSTGRES_PASSWORD: "${DB_PASSWORD:?DB_PASSWORD is required}",
      POSTGRES_USER: "meddoc",
    },
    volumes: [
      {
        bind: { create_host_path: true },
        source: "/mnt/pgdata-encrypted",
        target: "/var/lib/postgresql/data",
        type: "bind",
      },
      {
        bind: { create_host_path: true },
        read_only: true,
        source: `${ROOT}/infra/postgres/init-template-twin-roles.sh`,
        target: "/docker-entrypoint-initdb.d/20-template-twin-roles.sh",
        type: "bind",
      },
      {
        bind: { create_host_path: true },
        read_only: true,
        source: `${ROOT}/infra/postgres/provision-postgres-backup-principal.sh`,
        target: "/opt/quillmd/provision-postgres-backup-principal.sh",
        type: "bind",
      },
    ],
    secrets: [
      {
        source: "postgres_backup_password",
        target: "/run/secrets/postgres_backup_password",
      },
    ],
    networks: {
      auth_email_database: null,
      backup_database: null,
      default: null,
    },
    ports: [
      {
        host_ip: "127.0.0.1",
        mode: "ingress",
        protocol: "tcp",
        published: "5432",
        target: 5432,
      },
    ],
    healthcheck: {
      interval: "5s",
      retries: 5,
      test: ["CMD", "/bin/sh", POSTGRES_HBA_VERIFIER_PATH],
      timeout: "5s",
    },
  };
}

function exactQaPostgresService() {
  return {
    image: STATIC_QA_POSTGRES_IMAGE,
    build: {
      context: path.join(ROOT, "infra/postgres"),
      dockerfile: "Dockerfile",
    },
    entrypoint: [POSTGRES_ENTRYPOINT_PATH],
    command: POSTGRES_HBA_COMMAND,
    restart: "no",
    user: "999:999",
    cap_drop: ["ALL"],
    read_only: true,
    tmpfs: [
      "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
      "/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=3777",
    ],
    cpus: "1.0",
    mem_limit: "512m",
    environment: {
      DB_AUDIT_DISPATCHER_PASSWORD: staticQaCredential(
        "meddoc_audit_dispatcher",
      ),
      DB_AUTH_EMAIL_DISPATCHER_PASSWORD: staticQaCredential(
        "meddoc_auth_email_dispatcher",
      ),
      DB_BACKUP_PASSWORD_FILE: "/run/secrets/qa_postgres_backup_password",
      DB_RELEASE_CONTROL_PASSWORD: staticQaCredential("meddoc_release_control"),
      DB_RUNTIME_PASSWORD: staticQaCredential("meddoc_runtime"),
      PGDATA: "/var/lib/postgresql/data/pgdata",
      POSTGRES_DB: "meddoc_qa_test",
      POSTGRES_INITDB_ARGS: "--auth-host=scram-sha-256 --auth-local=trust",
      POSTGRES_PASSWORD: "qa_test_pw",
      POSTGRES_USER: "meddoc",
    },
    networks: { default: null },
    volumes: [
      {
        source: "qa_pgdata",
        target: "/var/lib/postgresql/data",
        type: "volume",
        volume: {},
      },
      {
        bind: { create_host_path: true },
        read_only: true,
        source: `${ROOT}/infra/postgres/init-template-twin-roles.sh`,
        target: "/docker-entrypoint-initdb.d/20-quillmd-exact-principals.sh",
        type: "bind",
      },
    ],
    secrets: [
      {
        source: "qa_postgres_backup_password",
        target: "/run/secrets/qa_postgres_backup_password",
      },
    ],
    healthcheck: {
      interval: "5s",
      retries: 10,
      test: ["CMD", "/bin/sh", POSTGRES_HBA_VERIFIER_PATH],
      timeout: "5s",
    },
  };
}

function exactBackupService() {
  return {
    cap_drop: ["ALL"],
    cpus: "0.5",
    depends_on: {
      postgres: { condition: "service_healthy", required: true },
    },
    environment: {
      BACKUP_KEEP_DAYS: "7",
      BACKUP_KEEP_MONTHS: "6",
      BACKUP_KEEP_WEEKS: "4",
      BACKUP_SUFFIX: ".dump",
      HEALTHCHECK_PORT: "8080",
      PGAPPNAME: "meddoc-postgres-backup",
      POSTGRES_CLUSTER: "FALSE",
      POSTGRES_DB: "meddoc",
      POSTGRES_EXTRA_OPTS:
        "--format=custom --compress=6 --no-owner --create --large-objects --lock-wait-timeout=60s",
      POSTGRES_HOST: "postgres",
      POSTGRES_PASSWORD_FILE: "/run/secrets/postgres_backup_password",
      POSTGRES_PORT: "5432",
      POSTGRES_USER: "meddoc_backup",
      SCHEDULE: "@daily",
    },
    healthcheck: {
      interval: "60s",
      retries: 3,
      start_period: "10s",
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8080"],
      timeout: "5s",
    },
    image: BACKUP_IMAGE,
    mem_limit: "128m",
    networks: { backup_database: null },
    profiles: ["backup-ops-approved"],
    restart: "unless-stopped",
    secrets: [
      {
        source: "postgres_backup_password",
        target: "/run/secrets/postgres_backup_password",
      },
    ],
    user: "999:999",
    volumes: [
      {
        source: "pgbackups",
        target: "/backups",
        type: "volume",
        volume: {},
      },
      {
        bind: { create_host_path: true },
        read_only: true,
        source: `${ROOT}/infra/postgres-backup/hooks`,
        target: "/hooks",
        type: "bind",
      },
    ],
  };
}

function exactProductionMigratorService() {
  return {
    build: {
      context: ROOT,
      dockerfile: "apps/transcribe-md/Dockerfile",
      target: "builder",
    },
    depends_on: {
      postgres: { condition: "service_healthy", required: true },
    },
    profiles: ["migrations"],
    working_dir: "/app/packages/db",
    entrypoint: ["npm", "run", "--silent", "database-release:migrate", "--"],
    command: ["--phase", "status"],
    network_mode: "service:postgres",
    environment: {
      DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS: STATIC_MIGRATION_LOCK_TIMEOUT,
      DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY: MIGRATION_NETWORK_BOUNDARY,
      DATABASE_URL: `postgresql://meddoc:${staticCredential("meddoc")}@127.0.0.1:5432/meddoc?${CANONICAL_QUERY}`,
      PRISMA_STATEMENT_TIMEOUT_MS: STATIC_STATEMENT_TIMEOUT,
    },
  };
}

function exactFrontendBuildArguments() {
  return {
    NEXT_PUBLIC_MARKETING_URL: "${MARKETING_URL:-https://quillmd.com}",
    NEXT_PUBLIC_SHOW_PIPELINE_TAB: "${NEXT_PUBLIC_SHOW_PIPELINE_TAB:-false}",
    NEXT_PUBLIC_SKIN_BETA: "${NEXT_PUBLIC_SKIN_BETA:-true}",
    NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL:
      "${TRANSCRIBE_MD_AUTH_URL:-https://app.quillmd.com}",
    NEXT_PUBLIC_ULTRASOUND_SPECIALTY:
      "${NEXT_PUBLIC_ULTRASOUND_SPECIALTY:-false}",
    QUILLMD_RELEASE_SHA: "${QUILLMD_RELEASE_SHA:-development}",
  };
}

function exactRuntimeHealthcheck(name: string) {
  const endpoint: Record<string, string> = {
    "meddoc-pro": "http://127.0.0.1:3000/api/health",
    "transcribe-md": "http://127.0.0.1:3011/api/health",
    "template-twin-admin-app":
      "http://127.0.0.1:3011/api/health/template-twin-admin-app",
    "template-twin-admin-control":
      "http://127.0.0.1:3011/api/admin/template-twin/control-health",
  };
  if (endpoint[name]) {
    return {
      interval: "30s",
      retries: 3,
      start_period: "30s",
      test: ["CMD", "wget", "-qO-", "--spider", endpoint[name]],
      timeout: "5s",
    };
  }
  const command: Record<string, string> = {
    "transcribe-md-worker":
      "test -f /tmp/worker-heartbeat && [ $(( $(date +%s) - $(stat -c %Y /tmp/worker-heartbeat) )) -lt 60 ]",
    "template-twin-audit-dispatcher":
      "test -f /tmp/template-twin-audit-dispatcher-heartbeat && [ $$(( $$(date +%s) - $$(stat -c %Y /tmp/template-twin-audit-dispatcher-heartbeat) )) -lt 90 ]",
    "auth-email-dispatcher":
      "test -f /tmp/auth-email-dispatcher-heartbeat && [ $$(( $$(date +%s) - $$(stat -c %Y /tmp/auth-email-dispatcher-heartbeat) )) -lt 90 ]",
  };
  return {
    interval: "30s",
    retries: 3,
    start_period: "60s",
    test: ["CMD-SHELL", command[name]],
    timeout: "5s",
  };
}

function exactPort(hostPort: string, target: number) {
  return {
    host_ip: "127.0.0.1",
    mode: "ingress",
    protocol: "tcp",
    published: hostPort,
    target,
  };
}

function exactProductionRuntimeSurface(name: string) {
  const worker = [
    "transcribe-md-worker",
    "template-twin-audit-dispatcher",
    "auth-email-dispatcher",
  ].includes(name);
  const meddoc = name === "meddoc-pro";
  const build = meddoc
    ? { context: ROOT, dockerfile: "apps/meddoc-pro/Dockerfile" }
    : {
        args: worker
          ? { QUILLMD_RELEASE_SHA: "${QUILLMD_RELEASE_SHA:-development}" }
          : exactFrontendBuildArguments(),
        context: ROOT,
        dockerfile: worker
          ? "apps/transcribe-md/Dockerfile.worker"
          : "apps/transcribe-md/Dockerfile",
      };
  const networks: Record<string, unknown> =
    name === "auth-email-dispatcher"
      ? {
          auth_email_database: {},
          auth_email_egress: { gw_priority: 1 },
        }
      : ["transcribe-md-worker", "template-twin-audit-dispatcher"].includes(
            name,
          )
        ? { default: null }
        : { default: null, quillmd_ingress: null };
  const ports =
    name === "meddoc-pro"
      ? [exactPort("3001", 3000)]
      : name === "transcribe-md"
        ? [exactPort("3011", 3011)]
        : name === "template-twin-admin-app"
          ? []
          : name === "template-twin-admin-control"
            ? ["127.0.0.1:${TEMPLATE_TWIN_ADMIN_CONTROL_PORT:-3012}:3011"]
            : undefined;
  const dispatcher = [
    "template-twin-audit-dispatcher",
    "auth-email-dispatcher",
  ].includes(name);
  const templateTwinNextRuntime = TEMPLATE_TWIN_NEXT_RUNTIME_SERVICES.includes(
    name as (typeof TEMPLATE_TWIN_NEXT_RUNTIME_SERVICES)[number],
  );
  return {
    build,
    ...(meddoc
      ? {}
      : {
          image: worker
            ? "${TRANSCRIBE_MD_WORKER_IMAGE:-meddoc-pro-transcribe-md-worker:latest}"
            : "${TRANSCRIBE_MD_IMAGE:-meddoc-pro-transcribe-md:latest}",
        }),
    restart: "unless-stopped",
    ...(templateTwinNextRuntime
      ? { mem_limit: STATIC_TEMPLATE_TWIN_NEXT_MEMORY_LIMIT }
      : {}),
    networks,
    ...(ports === undefined ? {} : { ports }),
    healthcheck: exactRuntimeHealthcheck(name),
    ...(dispatcher
      ? {
          read_only: true,
          tmpfs: ["/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777"],
          stop_grace_period: "45s",
        }
      : {}),
  };
}

interface NamedComposeResourceFixture extends Record<string, unknown> {
  name: string;
}

interface ProductionModelFixture {
  name: string;
  networks: Record<string, NamedComposeResourceFixture>;
  secrets: Record<string, Record<string, unknown>>;
  services: Record<string, unknown>;
  volumes: Record<string, NamedComposeResourceFixture>;
}

function productionModel(
  extra: Record<string, unknown> = {},
): ProductionModelFixture {
  const services: Record<string, unknown> = {};
  for (const [name, [role, login]] of Object.entries(productionServices)) {
    const databaseUrl = `postgresql://${login}:${staticCredential(login)}@postgres:5432/meddoc?${CANONICAL_QUERY}`;
    const repositoryEnvFile = [
      "meddoc-pro",
      "transcribe-md",
      "transcribe-md-worker",
    ].includes(name);
    const emptyEnvFile = [
      "template-twin-admin-app",
      "template-twin-admin-control",
      "auth-email-dispatcher",
    ].includes(name);
    const credentialBoundary = Object.fromEntries(
      DATABASE_CREDENTIAL_ENVIRONMENT_KEYS.map((key) => [key, ""]),
    );
    if (name === "template-twin-audit-dispatcher") {
      delete credentialBoundary.DB_PASSWORD;
      delete credentialBoundary.DB_RUNTIME_PASSWORD;
    }
    const command =
      name === "template-twin-audit-dispatcher"
        ? ["npx", "tsx", "src/audit-dispatcher.ts"]
        : name === "auth-email-dispatcher"
          ? ["npm", "run", "auth-email-dispatcher"]
          : undefined;
    const mfaPlaceholder =
      "${MFA_SECRET_KEYRING_FILE:?MFA_SECRET_KEYRING_FILE is required}";
    const volumes =
      name === "transcribe-md"
        ? [
            {
              read_only: true,
              source: "clamav_socket",
              target: "/var/run/quillmd-clamav",
              type: "volume",
              volume: {},
            },
            {
              bind: { create_host_path: false },
              read_only: true,
              source: path.join(ROOT, mfaPlaceholder),
              target: mfaPlaceholder,
              type: "bind",
            },
          ]
        : name === "template-twin-admin-app"
          ? [
              {
                bind: { create_host_path: false },
                read_only: true,
                source: path.join(ROOT, mfaPlaceholder),
                target: mfaPlaceholder,
                type: "bind",
              },
            ]
          : name === "template-twin-admin-control"
            ? []
            : undefined;
    services[name] = {
      ...exactProductionRuntimeSurface(name),
      cap_drop: ["ALL"],
      ...(name === "transcribe-md"
        ? { group_add: ["101", "1001"] }
        : name === "template-twin-admin-app"
          ? { group_add: ["1001"] }
          : name === "template-twin-admin-control"
            ? { group_add: null }
            : {}),
      ...(command ? { command } : {}),
      ...(["template-twin-audit-dispatcher", "auth-email-dispatcher"].includes(
        name,
      )
        ? { security_opt: ["no-new-privileges:true"] }
        : {}),
      ...(volumes === undefined ? {} : { volumes }),
      ...(repositoryEnvFile
        ? { env_file: [{ path: `${ROOT}/.env`, required: true }] }
        : emptyEnvFile
          ? { env_file: [] }
          : {}),
      environment: {
        ...credentialBoundary,
        DATABASE_URL: databaseUrl,
        ...(name === "template-twin-admin-control"
          ? { TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL: databaseUrl }
          : {}),
        NODE_ENV: "production",
        QUILLMD_SERVICE_ROLE: role,
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
        PRISMA_STATEMENT_TIMEOUT_MS: STATIC_STATEMENT_TIMEOUT,
      },
    };
  }
  return {
    name: "meddoc-pro",
    services: {
      ...services,
      postgres: exactPostgresService(),
      "postgres-backup": exactBackupService(),
      "db-migrate": exactProductionMigratorService(),
      caddy: {
        cap_add: ["NET_BIND_SERVICE"],
        networks: { quillmd_ingress: null },
        volumes: [
          { source: "caddy_data", target: "/data", type: "volume", volume: {} },
          {
            source: "caddy_config",
            target: "/config",
            type: "volume",
            volume: {},
          },
        ],
      },
      marketing: { networks: { default: null, quillmd_ingress: null } },
      minio: {
        networks: { default: null },
        volumes: [
          { source: "minio_data", target: "/data", type: "volume", volume: {} },
        ],
      },
      redis: {
        networks: { default: null },
        volumes: [
          { source: "redis_data", target: "/data", type: "volume", volume: {} },
        ],
      },
      "template-twin-clamav": {
        cap_add: ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"],
        networks: { template_twin_scanner: null },
        volumes: [
          {
            source: "clamav_signatures",
            target: "/var/lib/clamav",
            type: "volume",
            volume: {},
          },
          {
            source: "clamav_socket",
            target: "/run/clamav",
            type: "volume",
            volume: {},
          },
        ],
      },
      ...extra,
    },
    networks: {
      auth_email_database: {
        internal: true,
        name: "meddoc-pro_auth_email_database",
      },
      auth_email_egress: {
        driver: "bridge",
        name: "meddoc-pro_auth_email_egress",
      },
      backup_database: { internal: true, name: "meddoc-pro_backup_database" },
      default: { name: "meddoc-pro_default" },
      quillmd_ingress: {
        driver: "bridge",
        ipam: {
          config: [{ gateway: "172.31.252.1", subnet: "172.31.252.0/24" }],
        },
        name: "meddoc-pro_quillmd_ingress",
      },
      template_twin_scanner: {
        driver: "bridge",
        name: "meddoc-pro_template_twin_scanner",
      },
    },
    secrets: {
      postgres_backup_password: {
        file: `${ROOT}/\${DB_BACKUP_PASSWORD_FILE:?DB_BACKUP_PASSWORD_FILE is required}`,
        name: "meddoc-pro_postgres_backup_password",
      },
    },
    volumes: Object.fromEntries(
      [
        "caddy_config",
        "caddy_data",
        "clamav_signatures",
        "clamav_socket",
        "minio_data",
        "pgbackups",
        "pgdata",
        "redis_data",
      ].map((key) => [key, { name: `meddoc-pro_${key}` }]),
    ),
  };
}

function run(model: unknown, ...arguments_: string[]) {
  return spawnSync("node", [CENSUS, "--static-unresolved", ...arguments_], {
    cwd: ROOT,
    encoding: "utf8",
    input: JSON.stringify(model),
  });
}

function runResolved(
  model: unknown,
  approvedSecretPath = "/approved/backup",
  approvedKeyringPath = APPROVED_KEYRING_PATH,
) {
  return spawnSync("node", [CENSUS], {
    cwd: ROOT,
    encoding: "utf8",
    env: {
      ...process.env,
      QUILLMD_APPROVED_DB_BACKUP_PASSWORD_FILE: approvedSecretPath,
      QUILLMD_APPROVED_MFA_SECRET_KEYRING_FILE: approvedKeyringPath,
      QUILLMD_APPROVED_POSTGRES_IMAGE: APPROVED_POSTGRES_IMAGE,
      QUILLMD_APPROVED_RELEASE_SHA: APPROVED_RELEASE_SHA,
      QUILLMD_APPROVED_TRANSCRIBE_MD_IMAGE: APPROVED_FRONTEND_IMAGE,
      QUILLMD_APPROVED_TRANSCRIBE_MD_WORKER_IMAGE: APPROVED_WORKER_IMAGE,
    },
    input: JSON.stringify(model),
  });
}

function resolvedProductionModel(keyringPath = APPROVED_KEYRING_PATH) {
  const model = productionModel();
  delete model.volumes.pgdata;
  for (const [key, network] of Object.entries(model.networks)) {
    if (key !== "quillmd_ingress") {
      (network as { ipam?: Record<string, never> }).ipam = {};
    }
  }
  model.secrets.postgres_backup_password.file = "/approved/backup";
  const postgres = model.services.postgres as {
    command?: null | string[];
    entrypoint?: null | string[];
    environment: Record<string, string>;
  };
  postgres.command = [...POSTGRES_HBA_COMMAND];
  postgres.entrypoint = [POSTGRES_ENTRYPOINT_PATH];
  (postgres as Record<string, unknown>).image = APPROVED_POSTGRES_IMAGE;
  (postgres as Record<string, unknown>).cpus = 1;
  (postgres as Record<string, unknown>).mem_limit = "536870912";
  const backup = model.services["postgres-backup"] as {
    command?: null;
    entrypoint?: null;
  };
  backup.command = null;
  backup.entrypoint = null;
  (backup as Record<string, unknown>).cpus = 0.5;
  (backup as Record<string, unknown>).mem_limit = "134217728";
  (
    backup as unknown as { healthcheck: { interval: string } }
  ).healthcheck.interval = "1m0s";
  for (const [login, key] of Object.entries(PASSWORD_ENVIRONMENT_BY_LOGIN)) {
    postgres.environment[key === "DB_PASSWORD" ? "POSTGRES_PASSWORD" : key] =
      RESOLVED_CREDENTIAL_BY_LOGIN[login];
  }
  for (const [name, [, login]] of Object.entries(productionServices)) {
    const service = model.services[name] as {
      build: { args?: Record<string, string> };
      command?: null;
      entrypoint?: null;
      env_file?: unknown;
      environment: Record<string, string>;
      group_add?: unknown;
      healthcheck: { start_period: string; test: string[] };
      image?: string | null;
      mem_limit?: string;
      ports?: unknown;
      volumes?: Array<Record<string, unknown>>;
    };
    delete service.env_file;
    service.entrypoint = null;
    if (
      !["template-twin-audit-dispatcher", "auth-email-dispatcher"].includes(
        name,
      )
    ) {
      service.command = null;
    }
    if (name === "template-twin-admin-control") {
      delete service.group_add;
    }
    if (name === "template-twin-admin-app") delete service.ports;
    if (name === "template-twin-admin-control") {
      service.ports = [exactPort("3012", 3011)];
      delete service.volumes;
    }
    if (name !== "meddoc-pro") {
      service.image = [
        "transcribe-md-worker",
        "template-twin-audit-dispatcher",
        "auth-email-dispatcher",
      ].includes(name)
        ? APPROVED_WORKER_IMAGE
        : APPROVED_FRONTEND_IMAGE;
    }
    if (
      TEMPLATE_TWIN_NEXT_RUNTIME_SERVICES.includes(
        name as (typeof TEMPLATE_TWIN_NEXT_RUNTIME_SERVICES)[number],
      )
    ) {
      service.mem_limit = RESOLVED_TEMPLATE_TWIN_NEXT_MEMORY_LIMIT;
    }
    if (service.build.args) {
      for (const key of Object.keys(service.build.args)) {
        service.build.args[key] =
          key === "NEXT_PUBLIC_MARKETING_URL"
            ? "https://quillmd.com"
            : key === "NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL"
              ? "https://app.quillmd.com"
              : key === "NEXT_PUBLIC_SKIN_BETA"
                ? "true"
                : key === "QUILLMD_RELEASE_SHA"
                  ? APPROVED_RELEASE_SHA
                  : "false";
      }
    }
    if (service.healthcheck.start_period === "60s") {
      service.healthcheck.start_period = "1m0s";
    }
    if (name === "transcribe-md-worker") {
      service.healthcheck.test[1] =
        "test -f /tmp/worker-heartbeat && [ $$(( $$(date +%s) - $$(stat -c %Y /tmp/worker-heartbeat) )) -lt 60 ]";
    }
    if (Array.isArray(service.volumes)) {
      for (const volume of service.volumes) {
        if (
          volume.target ===
          "${MFA_SECRET_KEYRING_FILE:?MFA_SECRET_KEYRING_FILE is required}"
        ) {
          Object.assign(volume, {
            bind: {},
            source: keyringPath,
            target: keyringPath,
            type: "bind",
          });
        }
      }
    }
    for (const key of [
      "DATABASE_URL",
      "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
    ]) {
      if (typeof service.environment[key] === "string") {
        service.environment[key] = service.environment[key].replace(
          staticCredential(login),
          RESOLVED_CREDENTIAL_BY_LOGIN[login],
        );
      }
    }
    service.environment.PRISMA_STATEMENT_TIMEOUT_MS = "30000";
  }
  const migrator = model.services["db-migrate"] as {
    environment: {
      DATABASE_URL: string;
      DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS: string;
      PRISMA_STATEMENT_TIMEOUT_MS: string;
    };
  };
  migrator.environment.DATABASE_URL = migrator.environment.DATABASE_URL.replace(
    staticCredential("meddoc"),
    RESOLVED_CREDENTIAL_BY_LOGIN.meddoc,
  );
  migrator.environment.PRISMA_STATEMENT_TIMEOUT_MS = "30000";
  migrator.environment.DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS = "5000";
  return model;
}

function exactQaModel() {
  const mfaPlaceholder =
    "${QA_MFA_SECRET_KEYRING_FILE:?QA_MFA_SECRET_KEYRING_FILE is required}";
  return {
    name: "meddoc-qa",
    secrets: {
      qa_postgres_backup_password: {
        file: `${ROOT}/\${QA_DB_BACKUP_PASSWORD_FILE:?QA_DB_BACKUP_PASSWORD_FILE is required}`,
        name: "meddoc-qa_qa_postgres_backup_password",
      },
    },
    networks: {
      default: { name: "meddoc-qa_default" },
      template_twin_scanner: {
        driver: "bridge",
        name: "meddoc-qa_template_twin_scanner",
      },
    },
    volumes: Object.fromEntries(
      ["qa_clamav_signatures", "qa_clamav_socket", "qa_minio", "qa_pgdata"].map(
        (key) => [key, { name: `meddoc-qa_${key}` }],
      ),
    ),
    services: {
      postgres: exactQaPostgresService(),
      "transcribe-md": {
        image: "${QA_TRANSCRIBE_MD_IMAGE:-meddoc-pro-transcribe-md:latest}",
        restart: "no",
        cap_drop: ["ALL"],
        cpus: "1.0",
        mem_limit: STATIC_TEMPLATE_TWIN_NEXT_MEMORY_LIMIT,
        group_add: ["101", "1001"],
        networks: { default: null },
        ports: [exactPort("9020", 3011)],
        healthcheck: {
          interval: "15s",
          retries: 10,
          start_period: "30s",
          test: [
            "CMD",
            "wget",
            "-qO-",
            "--spider",
            "http://127.0.0.1:3011/api/health",
          ],
          timeout: "5s",
        },
        volumes: [
          {
            read_only: true,
            source: "qa_clamav_socket",
            target: "/var/run/quillmd-clamav",
            type: "volume",
            volume: {},
          },
          {
            bind: { create_host_path: false },
            read_only: true,
            source: path.join(ROOT, mfaPlaceholder),
            target: mfaPlaceholder,
            type: "bind",
          },
        ],
        environment: {
          DATABASE_URL: `postgresql://meddoc_runtime:${staticQaCredential("meddoc_runtime")}@postgres:5432/meddoc_qa_test?${CANONICAL_QUERY}`,
          NODE_ENV: "production",
          QUILLMD_SERVICE_ROLE: "physician-app",
          QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
          PRISMA_STATEMENT_TIMEOUT_MS: STATIC_STATEMENT_TIMEOUT,
        },
      },
      "transcribe-md-worker": {
        image:
          "${QA_TRANSCRIBE_MD_WORKER_IMAGE:-meddoc-pro-transcribe-md-worker:latest}",
        restart: "no",
        cap_drop: ["ALL"],
        cpus: "1.0",
        mem_limit: "1g",
        networks: { default: null },
        healthcheck: exactRuntimeHealthcheck("transcribe-md-worker"),
        environment: {
          DATABASE_URL: `postgresql://meddoc_runtime:${staticQaCredential("meddoc_runtime")}@postgres:5432/meddoc_qa_test?${CANONICAL_QUERY}`,
          NODE_ENV: "production",
          QUILLMD_SERVICE_ROLE: "transcribe-md-worker",
          QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
          PRISMA_STATEMENT_TIMEOUT_MS: STATIC_STATEMENT_TIMEOUT,
        },
      },
      "db-migrate": {
        profiles: ["migrations"],
        restart: "no",
        working_dir: "/app/packages/db",
        entrypoint: [
          "npm",
          "run",
          "--silent",
          "database-release:migrate",
          "--",
        ],
        command: ["--phase", "status"],
        depends_on: {
          postgres: { condition: "service_healthy", required: true },
        },
        image: "${QA_DB_MIGRATE_IMAGE:-meddoc-pro-db-migrate:latest}",
        network_mode: "service:postgres",
        environment: {
          DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS:
            STATIC_MIGRATION_LOCK_TIMEOUT,
          DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY:
            MIGRATION_NETWORK_BOUNDARY,
          DATABASE_URL: `postgresql://meddoc:qa_test_pw@127.0.0.1:5432/meddoc_qa_test?${CANONICAL_QUERY}`,
          PRISMA_STATEMENT_TIMEOUT_MS: STATIC_STATEMENT_TIMEOUT,
        },
      },
      marketing: { networks: { default: null } },
      minio: {
        networks: { default: null },
        volumes: [
          { source: "qa_minio", target: "/data", type: "volume", volume: {} },
        ],
      },
      "minio-template-init": { networks: { default: null } },
      redis: { networks: { default: null } },
      "template-twin-clamav": {
        cap_add: ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"],
        networks: { template_twin_scanner: null },
        volumes: [
          {
            source: "qa_clamav_signatures",
            target: "/var/lib/clamav",
            type: "volume",
            volume: {},
          },
          {
            source: "qa_clamav_socket",
            target: "/run/clamav",
            type: "volume",
            volume: {},
          },
        ],
      },
    },
  };
}

function resolvedQaModel(keyringPath = APPROVED_KEYRING_PATH) {
  const model = exactQaModel();
  for (const network of Object.values(model.networks)) {
    (network as Record<string, unknown>).ipam = {};
  }
  model.secrets.qa_postgres_backup_password.file =
    APPROVED_QA_BACKUP_PASSWORD_PATH;
  const postgres = model.services.postgres as Record<string, unknown> & {
    environment: Record<string, string>;
  };
  postgres.image = APPROVED_QA_POSTGRES_IMAGE;
  postgres.cpus = 1;
  postgres.mem_limit = "536870912";
  postgres.command = [...POSTGRES_HBA_COMMAND];
  postgres.entrypoint = [POSTGRES_ENTRYPOINT_PATH];
  for (const [login, key] of Object.entries(PASSWORD_ENVIRONMENT_BY_LOGIN)) {
    if (login === "meddoc") continue;
    postgres.environment[key] = RESOLVED_CREDENTIAL_BY_LOGIN[login];
  }
  const app = model.services["transcribe-md"] as Record<string, unknown> & {
    environment: Record<string, string>;
    volumes: Array<Record<string, unknown>>;
  };
  app.image = APPROVED_FRONTEND_IMAGE;
  app.cpus = 1;
  app.mem_limit = RESOLVED_TEMPLATE_TWIN_NEXT_MEMORY_LIMIT;
  app.command = null;
  app.entrypoint = null;
  Object.assign(app.volumes[1], {
    bind: {},
    source: keyringPath,
    target: keyringPath,
    type: "bind",
  });
  app.environment.DATABASE_URL = app.environment.DATABASE_URL.replace(
    staticQaCredential("meddoc_runtime"),
    RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_runtime,
  );
  app.environment.PRISMA_STATEMENT_TIMEOUT_MS = "30000";
  const worker = model.services["transcribe-md-worker"] as Record<
    string,
    unknown
  > & {
    environment: Record<string, string>;
    healthcheck: { start_period: string; test: string[] };
  };
  worker.image = APPROVED_WORKER_IMAGE;
  worker.cpus = 1;
  worker.mem_limit = "1073741824";
  worker.command = null;
  worker.entrypoint = null;
  worker.environment.DATABASE_URL = worker.environment.DATABASE_URL.replace(
    staticQaCredential("meddoc_runtime"),
    RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_runtime,
  );
  worker.environment.PRISMA_STATEMENT_TIMEOUT_MS = "30000";
  worker.healthcheck.start_period = "1m0s";
  worker.healthcheck.test[1] =
    "test -f /tmp/worker-heartbeat && [ $$(( $$(date +%s) - $$(stat -c %Y /tmp/worker-heartbeat) )) -lt 60 ]";
  const migrator = model.services["db-migrate"] as Record<string, unknown> & {
    environment: {
      DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS: string;
      PRISMA_STATEMENT_TIMEOUT_MS: string;
    };
  };
  migrator.image = APPROVED_QA_MIGRATOR_IMAGE;
  migrator.environment.DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS = "5000";
  migrator.environment.PRISMA_STATEMENT_TIMEOUT_MS = "30000";
  return model;
}

function runResolvedQa(model: unknown) {
  return spawnSync("node", [CENSUS, "--qa"], {
    cwd: ROOT,
    encoding: "utf8",
    env: {
      ...process.env,
      QUILLMD_APPROVED_QA_DB_MIGRATE_IMAGE: APPROVED_QA_MIGRATOR_IMAGE,
      QUILLMD_APPROVED_QA_POSTGRES_IMAGE: APPROVED_QA_POSTGRES_IMAGE,
      QUILLMD_APPROVED_QA_DB_BACKUP_PASSWORD_FILE:
        APPROVED_QA_BACKUP_PASSWORD_PATH,
      QUILLMD_APPROVED_QA_MFA_SECRET_KEYRING_FILE: APPROVED_KEYRING_PATH,
      QUILLMD_APPROVED_QA_TRANSCRIBE_MD_IMAGE: APPROVED_FRONTEND_IMAGE,
      QUILLMD_APPROVED_QA_TRANSCRIBE_MD_WORKER_IMAGE: APPROVED_WORKER_IMAGE,
    },
    input: JSON.stringify(model),
  });
}

describe("database-principal runtime census", () => {
  it("accepts the exact seven-service production mapping", () => {
    const result = run(productionModel());
    expect(result.status).toBe(0);
    expect(result.stdout).toContain(
      "profile=production mode=static-unresolved services=7",
    );
  });

  it("accepts the actual static Compose model without resolving environment files", () => {
    const compose = spawnSync(
      "docker",
      [
        "compose",
        "--profile",
        "*",
        "-f",
        "docker-compose.yml",
        "config",
        "--no-interpolate",
        "--no-env-resolution",
        "--format",
        "json",
      ],
      {
        cwd: ROOT,
        encoding: "utf8",
        env: Object.fromEntries(
          ["PATH", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"]
            .filter((key) => process.env[key] !== undefined)
            .map((key) => [key, process.env[key]]),
        ) as NodeJS.ProcessEnv,
      },
    );
    expect(compose.status, compose.stderr).toBe(0);

    const model = JSON.parse(compose.stdout) as {
      services: Record<
        string,
        {
          environment?: Record<string, string | null>;
          group_add?: string[] | null;
          mem_limit?: string;
          volumes?: Array<Record<string, unknown>>;
        }
      >;
    };
    expect(
      model.services["transcribe-md"]?.environment?.DATABASE_URL,
    ).toContain("${DB_RUNTIME_PASSWORD:?DB_RUNTIME_PASSWORD is required}");
    expect(model.services["transcribe-md"]?.group_add).toEqual(["101", "1001"]);
    expect(model.services["template-twin-admin-app"]?.group_add).toEqual([
      "1001",
    ]);
    expect(model.services["template-twin-admin-control"]?.group_add).toBeNull();
    for (const serviceName of TEMPLATE_TWIN_NEXT_RUNTIME_SERVICES) {
      expect(model.services[serviceName]?.mem_limit).toBe(
        STATIC_TEMPLATE_TWIN_NEXT_MEMORY_LIMIT,
      );
    }

    const census = run(model);
    expect(census.status, census.stderr).toBe(0);
    expect(census.stdout).toContain(
      "profile=production mode=static-unresolved services=7",
    );

    const driftedModel = JSON.parse(compose.stdout) as typeof model;
    const driftedEnvironment =
      driftedModel.services["transcribe-md"]?.environment;
    if (!driftedEnvironment) {
      throw new Error("actual static Compose model omitted transcribe-md env");
    }
    driftedEnvironment.QUILLMD_DATABASE_PRINCIPAL_PROFILE =
      "synthetic-disposable-qa-v1";
    const driftedCensus = run(driftedModel);
    expect(driftedCensus.status).not.toBe(0);
    expect(driftedCensus.stderr).toContain(
      "transcribe-md has an unexpected database-principal profile",
    );

    const keyringDriftModel = JSON.parse(compose.stdout) as typeof model;
    const physicianVolumes =
      keyringDriftModel.services["transcribe-md"]?.volumes;
    const worker = keyringDriftModel.services["transcribe-md-worker"];
    const keyringMount = physicianVolumes?.find(
      (volume) =>
        typeof volume.source === "string" &&
        volume.source.includes("MFA_SECRET_KEYRING_FILE"),
    );
    if (!worker || !keyringMount) {
      throw new Error(
        "actual static Compose model omitted the MFA keyring mount",
      );
    }
    worker.volumes = [structuredClone(keyringMount)];
    const keyringDriftCensus = run(keyringDriftModel);
    expect(keyringDriftCensus.status).not.toBe(0);
    expect(keyringDriftCensus.stderr).toContain(
      "transcribe-md-worker has an unexpected runtime authority contract: volume mounts",
    );
  });

  it.each([
    ["base image bypass", "image", "pgvector/pgvector:pg16"],
    ["command bypass", "command", ["postgres"]],
    ["entrypoint bypass", "entrypoint", ["/bin/sh"]],
    ["owner uid bypass", "user", "0:0"],
    ["writable root filesystem", "read_only", false],
    ["missing runtime tmpfs", "tmpfs", []],
  ] as const)(
    "rejects production immutable PostgreSQL drift: %s",
    (_label, key, value) => {
      const model = productionModel();
      (model.services.postgres as Record<string, unknown>)[key] = value;
      const result = run(model);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(
        "exact PostgreSQL database server is missing",
      );
    },
  );

  it.each(TEMPLATE_TWIN_NEXT_RUNTIME_SERVICES)(
    "rejects production Next runtime memory-limit drift on %s",
    (serviceName) => {
      const model = productionModel();
      const service = model.services[serviceName] as Record<string, unknown>;
      service.mem_limit = "512m";
      const result = run(model);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(
        `${serviceName} has an unexpected runtime authority contract: runtime surface memory limit`,
      );
    },
  );

  it("rejects a host replacement for the image-embedded HBA", () => {
    const model = productionModel();
    const postgres = model.services.postgres as {
      volumes: Array<Record<string, unknown>>;
    };
    postgres.volumes.push({
      bind: { create_host_path: true },
      read_only: true,
      source: `${ROOT}/infra/postgres/quillmd-pg_hba.conf`,
      target: POSTGRES_HBA_PATH,
      type: "bind",
    });
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "exact PostgreSQL database server is missing",
    );
  });

  it("accepts only a fully resolved deployment model in resolved mode", () => {
    const result = runResolved(resolvedProductionModel());
    expect(result.status, result.stderr).toBe(0);
    expect(result.stdout).toContain(
      "profile=production mode=resolved services=7",
    );

    const unresolved = runResolved(productionModel());
    expect(unresolved.status).not.toBe(0);

    const unresolvedRuntime = resolvedProductionModel();
    const meddocPro = unresolvedRuntime.services["meddoc-pro"] as {
      environment: Record<string, string>;
    };
    meddocPro.environment.DATABASE_URL =
      meddocPro.environment.DATABASE_URL.replace(
        RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_runtime,
        staticCredential("meddoc_runtime"),
      );
    expect(runResolved(unresolvedRuntime).status).not.toBe(0);

    const sharedCredential = resolvedProductionModel();
    const sharedPostgres = sharedCredential.services.postgres as {
      environment: Record<string, string>;
    };
    sharedPostgres.environment.DB_RUNTIME_PASSWORD =
      sharedPostgres.environment.POSTGRES_PASSWORD;
    expect(runResolved(sharedCredential).status).not.toBe(0);

    const wrongApprovedPath = runResolved(
      resolvedProductionModel(),
      "/approved/different-backup",
    );
    expect(wrongApprovedPath.status).not.toBe(0);

    const missingKeyringPath = path.join(
      APPROVED_KEYRING_DIRECTORY,
      "missing-keyring.json",
    );
    const missingKeyring = runResolved(
      resolvedProductionModel(missingKeyringPath),
      "/approved/backup",
      missingKeyringPath,
    );
    expect(missingKeyring.status).not.toBe(0);

    const aliasedKeyringPath = path.join(
      APPROVED_KEYRING_DIRECTORY,
      "aliased-keyring.json",
    );
    symlinkSync(APPROVED_KEYRING_PATH, aliasedKeyringPath);
    const aliasedKeyring = runResolved(
      resolvedProductionModel(aliasedKeyringPath),
      "/approved/backup",
      aliasedKeyringPath,
    );
    expect(aliasedKeyring.status).not.toBe(0);
  });

  it("accepts the actual fully resolved Compose model without retaining env_file declarations", () => {
    const directory = mkdtempSync(
      path.join(os.tmpdir(), "meddoc-runtime-census-"),
    );
    try {
      writeFileSync(
        path.join(directory, "docker-compose.yml"),
        readFileSync(path.join(ROOT, "docker-compose.yml")),
      );
      copyPostgresHostAuthenticationSources(directory);
      writeFileSync(
        path.join(directory, ".env"),
        [
          `DB_PASSWORD=${RESOLVED_CREDENTIAL_BY_LOGIN.meddoc}`,
          `DB_AUDIT_DISPATCHER_PASSWORD=${RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_audit_dispatcher}`,
          `DB_AUTH_EMAIL_DISPATCHER_PASSWORD=${RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_auth_email_dispatcher}`,
          `DB_RELEASE_CONTROL_PASSWORD=${RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_release_control}`,
          `DB_RUNTIME_PASSWORD=${RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_runtime}`,
          "DB_BACKUP_PASSWORD_FILE=/approved/backup",
          "MFA_SECRET_ACTIVE_KEY_ID=synthetic-census-key",
          `MFA_SECRET_KEYRING_FILE=${APPROVED_KEYRING_PATH}`,
          "MINIO_KMS_SECRET_KEY=synthetic-census-kms-key",
          "MINIO_ROOT_PASSWORD=synthetic-census-minio-password",
          `QUILLMD_RELEASE_SHA=${APPROVED_RELEASE_SHA}`,
          `QUILLMD_POSTGRES_IMAGE=${APPROVED_POSTGRES_IMAGE}`,
          `TRANSCRIBE_MD_IMAGE=${APPROVED_FRONTEND_IMAGE}`,
          `TRANSCRIBE_MD_WORKER_IMAGE=${APPROVED_WORKER_IMAGE}`,
          "",
        ].join("\n"),
        { mode: 0o600 },
      );
      const compose = spawnSync(
        "docker",
        [
          "compose",
          "--profile",
          "*",
          "-f",
          "docker-compose.yml",
          "config",
          "--format",
          "json",
        ],
        {
          cwd: directory,
          encoding: "utf8",
          env: Object.fromEntries(
            ["PATH", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"]
              .filter((key) => process.env[key] !== undefined)
              .map((key) => [key, process.env[key]]),
          ) as NodeJS.ProcessEnv,
        },
      );
      expect(compose.status).toBe(0);
      expect(
        Object.keys(
          (JSON.parse(compose.stdout) as { volumes: Record<string, unknown> })
            .volumes,
        ).sort(),
      ).toEqual([
        "caddy_config",
        "caddy_data",
        "clamav_signatures",
        "clamav_socket",
        "minio_data",
        "pgbackups",
        "redis_data",
      ]);
      const census = spawnSync("node", [CENSUS], {
        cwd: directory,
        encoding: "utf8",
        env: {
          ...process.env,
          QUILLMD_APPROVED_DB_BACKUP_PASSWORD_FILE: "/approved/backup",
          QUILLMD_APPROVED_MFA_SECRET_KEYRING_FILE: APPROVED_KEYRING_PATH,
          QUILLMD_APPROVED_POSTGRES_IMAGE: APPROVED_POSTGRES_IMAGE,
          QUILLMD_APPROVED_RELEASE_SHA: APPROVED_RELEASE_SHA,
          QUILLMD_APPROVED_TRANSCRIBE_MD_IMAGE: APPROVED_FRONTEND_IMAGE,
          QUILLMD_APPROVED_TRANSCRIBE_MD_WORKER_IMAGE: APPROVED_WORKER_IMAGE,
        },
        input: compose.stdout,
      });
      expect(census.status, census.stderr).toBe(0);
      expect(census.stdout).toContain(
        "profile=production mode=resolved services=7",
      );
    } finally {
      rmSync(directory, { force: true, recursive: true });
    }
  });

  it.each([
    [
      "host",
      `postgresql://meddoc_runtime:credential@unreviewed-db:5432/meddoc?${CANONICAL_QUERY}`,
    ],
    [
      "port",
      `postgresql://meddoc_runtime:credential@postgres:5433/meddoc?${CANONICAL_QUERY}`,
    ],
    [
      "database",
      `postgresql://meddoc_runtime:credential@postgres:5432/unreviewed?${CANONICAL_QUERY}`,
    ],
    [
      "query key",
      `postgresql://meddoc_runtime:credential@postgres:5432/meddoc?${CANONICAL_QUERY}&sslmode=disable`,
    ],
    [
      "schema query",
      `postgresql://meddoc_runtime:credential@postgres:5432/meddoc?${CANONICAL_OPTIONS}`,
    ],
    [
      "query-key case",
      `postgresql://meddoc_runtime:credential@postgres:5432/meddoc?schema=public&OPTIONS=-c%20search_path%3Dpg_catalog%2Cpublic`,
    ],
  ] as const)(
    "rejects production PostgreSQL %s drift",
    (_label, databaseUrl) => {
      const model = productionModel();
      const meddocPro = model.services["meddoc-pro"] as {
        environment: Record<string, string>;
      };
      meddocPro.environment.DATABASE_URL = databaseUrl;
      const result = run(model);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(
        "meddoc-pro has an unexpected PostgreSQL destination or query contract",
      );
    },
  );

  it("rejects a missing canonical search_path option", () => {
    const model = productionModel();
    const meddocPro = model.services["meddoc-pro"] as {
      environment: Record<string, string>;
    };
    meddocPro.environment.DATABASE_URL =
      "postgresql://meddoc_runtime:credential@postgres:5432/meddoc";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro does not force the canonical PostgreSQL search_path",
    );
  });

  it("rejects an unsafe search_path option", () => {
    const model = productionModel();
    const meddocPro = model.services["meddoc-pro"] as {
      environment: Record<string, string>;
    };
    meddocPro.environment.DATABASE_URL =
      "postgresql://meddoc_runtime:credential@postgres:5432/meddoc?options=-c%20search_path%3Dpublic";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro does not force the canonical PostgreSQL search_path",
    );
  });

  it("rejects duplicate search_path options even when each value is canonical", () => {
    const model = productionModel();
    const meddocPro = model.services["meddoc-pro"] as {
      environment: Record<string, string>;
    };
    meddocPro.environment.DATABASE_URL = `postgresql://meddoc_runtime:credential@postgres:5432/meddoc?${CANONICAL_OPTIONS}&${CANONICAL_OPTIONS}`;
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro does not force the canonical PostgreSQL search_path",
    );
  });

  it("requires one canonical search_path option on each reviewed DSN", () => {
    const model = productionModel();
    const control = model.services["template-twin-admin-control"] as {
      environment: Record<string, string>;
    };
    control.environment.DATABASE_URL =
      "postgresql://meddoc_release_control:credential@postgres:5432/meddoc";
    control.environment.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL = `postgresql://meddoc_release_control:credential@postgres:5432/meddoc?${CANONICAL_OPTIONS}&${CANONICAL_OPTIONS}`;
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "template-twin-admin-control does not force the canonical PostgreSQL search_path",
    );
  });

  it("requires the exact dedicated backup runtime", () => {
    const model = productionModel();
    delete model.services["postgres-backup"];
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("exact postgres-backup runtime is missing");
  });

  it("requires the exact closed segmented migrator to be present", () => {
    const model = productionModel();
    delete model.services["db-migrate"];
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("exact db-migrate runtime is missing");
  });

  it.each([
    [
      "unpinned image",
      (service: Record<string, unknown>) => {
        service.image = "prodrigestivill/postgres-backup-local:latest";
      },
    ],
    [
      "owner login",
      (service: Record<string, unknown>) => {
        const environment = service.environment as Record<string, string>;
        environment.POSTGRES_USER = "meddoc";
      },
    ],
    [
      "secondary DSN",
      (service: Record<string, unknown>) => {
        const environment = service.environment as Record<string, string>;
        environment.DATABASE_URL =
          "postgresql://meddoc_backup:credential@postgres:5432/meddoc";
      },
    ],
    [
      "ACL-stripping dump option",
      (service: Record<string, unknown>) => {
        const environment = service.environment as Record<string, string>;
        environment.POSTGRES_EXTRA_OPTS = "--format=custom --no-acl";
      },
    ],
    [
      "additional network",
      (service: Record<string, unknown>) => {
        service.networks = { backup_database: null, default: null };
      },
    ],
    [
      "command override",
      (service: Record<string, unknown>) => {
        service.command = ["sleep", "infinity"];
      },
    ],
    [
      "premature default activation",
      (service: Record<string, unknown>) => {
        delete service.profiles;
      },
    ],
    [
      "root uid",
      (service: Record<string, unknown>) => {
        service.user = "0:0";
      },
    ],
    [
      "added capability",
      (service: Record<string, unknown>) => {
        service.cap_add = ["SYS_ADMIN"];
      },
    ],
    [
      "missing immutable hook",
      (service: Record<string, unknown>) => {
        service.volumes = (service.volumes as unknown[]).slice(0, 1);
      },
    ],
    [
      "secret target drift",
      (service: Record<string, unknown>) => {
        service.secrets = [
          {
            source: "postgres_backup_password",
            target: "/run/secrets/other",
          },
        ];
      },
    ],
  ] as const)("rejects backup contract drift: %s", (_label, mutate) => {
    const model = productionModel();
    const backup = model.services["postgres-backup"] as Record<string, unknown>;
    mutate(backup);
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      _label === "missing immutable hook"
        ? "hook backup resource census drifted"
        : _label === "added capability"
          ? "postgres-backup has unreviewed container authority"
          : _label === "root uid"
            ? "postgres-backup has unreviewed container authority"
            : "postgres-backup does not match the exact dedicated backup runtime contract",
    );
  });

  it("rejects an egress-capable backup network", () => {
    const model = productionModel();
    model.networks.backup_database.internal = false;
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("backup network is not exact and internal");
  });

  it("rejects an unreviewed backup secret source", () => {
    const model = productionModel();
    model.secrets.postgres_backup_password.file = "/tmp/unreviewed-secret";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "postgres-backup does not match the exact dedicated backup runtime contract",
    );
  });

  it.each([
    [
      "network",
      { networks: { backup_database: null } },
      "network backup resource census drifted",
    ],
    [
      "secret",
      {
        secrets: [
          {
            source: "postgres_backup_password",
            target: "/run/secrets/postgres_backup_password",
          },
        ],
      },
      "secret backup resource census drifted",
    ],
    [
      "archive",
      {
        volumes: [
          {
            source: "pgbackups",
            target: "/backups",
            type: "volume",
            volume: {},
          },
        ],
      },
      "archive backup resource census drifted",
    ],
  ] as const)(
    "rejects an additional consumer of the backup %s resource",
    (_label, service, expectedMessage) => {
      const result = run(productionModel({ "unreviewed-consumer": service }));
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(expectedMessage);
    },
  );

  it("rejects physical aliases and alternate exposure of backup resources", () => {
    const secretAlias = productionModel();
    (
      secretAlias.secrets as Record<string, { file: string; name: string }>
    ).backup_alias = {
      file: secretAlias.secrets.postgres_backup_password.file as string,
      name: "fixture_backup_alias",
    };
    expect(run(secretAlias).stderr).toContain(
      "backup secret resource set drifted",
    );

    const volumeAlias = productionModel();
    (volumeAlias.volumes as Record<string, { name: string }>).archive_alias = {
      name: volumeAlias.volumes.pgbackups.name,
    };
    volumeAlias.services["unreviewed-volume-alias"] = {
      volumes: [
        {
          source: "archive_alias",
          target: "/alternate",
          type: "volume",
          volume: {},
        },
      ],
    };
    expect(run(volumeAlias).stderr).toContain(
      "backup archive has a physical alias",
    );

    const networkAlias = productionModel();
    (
      networkAlias.networks as Record<
        string,
        { internal: boolean; name: string }
      >
    ).network_alias = {
      internal: true,
      name: networkAlias.networks.backup_database.name,
    };
    networkAlias.services["unreviewed-network-alias"] = {
      networks: { network_alias: null },
    };
    expect(run(networkAlias).stderr).toContain(
      "backup network has a physical alias",
    );

    const configAlias = productionModel() as ReturnType<
      typeof productionModel
    > & {
      configs: Record<string, { file: string; name: string }>;
    };
    configAlias.configs = {
      backup_config_alias: {
        file: configAlias.secrets.postgres_backup_password.file as string,
        name: "fixture_backup_config_alias",
      },
    };
    expect(run(configAlias).stderr).toContain(
      "unreviewed Compose config resource",
    );

    const bindAlias = productionModel();
    bindAlias.services["unreviewed-secret-bind"] = {
      volumes: [
        {
          bind: { create_host_path: true },
          read_only: true,
          source: bindAlias.secrets.postgres_backup_password.file,
          target: "/alternate-secret",
          type: "bind",
        },
      ],
    };
    expect(run(bindAlias).stderr).toContain(
      "bind-mounts a protected credential source",
    );

    const repositoryEnvironmentBind = productionModel();
    repositoryEnvironmentBind.services["unreviewed-env-bind"] = {
      volumes: [
        {
          bind: { create_host_path: true },
          read_only: true,
          source: `${ROOT}/.env`,
          target: "/alternate-env",
          type: "bind",
        },
      ],
    };
    expect(run(repositoryEnvironmentBind).stderr).toContain(
      "bind-mounts a protected credential source",
    );

    const runtimeSocket = productionModel();
    runtimeSocket.services["unreviewed-runtime-socket"] = {
      volumes: [
        {
          bind: { create_host_path: true },
          source: "/var/run/docker.sock",
          target: "/var/run/docker.sock",
          type: "bind",
        },
      ],
    };
    expect(run(runtimeSocket).stderr).toContain(
      "exposes a container runtime socket",
    );
  });

  it("keeps the primary PostgreSQL data bind exclusive to the exact server", () => {
    const extraService = productionModel();
    extraService.services["unreviewed-pgdata-reader"] = {
      volumes: [
        {
          bind: { create_host_path: true },
          read_only: true,
          source: "/mnt/pgdata-encrypted",
          target: "/raw-database",
          type: "bind",
        },
      ],
    };
    expect(run(extraService).stderr).toContain(
      "unreviewed-pgdata-reader exposes the primary PostgreSQL data bind",
    );

    const expectedService = productionModel();
    const transcribeMd = expectedService.services["transcribe-md"] as {
      volumes?: Array<Record<string, unknown>>;
    };
    transcribeMd.volumes = [
      {
        bind: { create_host_path: true },
        read_only: true,
        source: "/mnt/pgdata-encrypted/pgdata",
        target: "/raw-database",
        type: "bind",
      },
    ];
    expect(run(expectedService).stderr).toContain(
      "transcribe-md exposes the primary PostgreSQL data bind",
    );
  });

  it("rejects backup hook, provisioner, and secret path substitutions", () => {
    const hookModel = productionModel();
    const hookBackup = hookModel.services["postgres-backup"] as {
      volumes: Array<Record<string, unknown>>;
    };
    hookBackup.volumes[1].source = `${ROOT}/unreviewed/infra/postgres-backup/hooks`;
    expect(run(hookModel).status).not.toBe(0);

    const provisionerModel = productionModel();
    const provisionerPostgres = provisionerModel.services.postgres as {
      volumes: Array<Record<string, unknown>>;
    };
    provisionerPostgres.volumes[2].source = `${ROOT}/unreviewed/infra/postgres/provision-postgres-backup-principal.sh`;
    expect(run(provisionerModel).status).not.toBe(0);

    const secretModel = productionModel();
    secretModel.secrets.postgres_backup_password.file = `${ROOT}/unreviewed/\${DB_BACKUP_PASSWORD_FILE:?DB_BACKUP_PASSWORD_FILE is required}`;
    expect(run(secretModel).status).not.toBe(0);
  });

  it("rejects a missing PostgreSQL-side backup provisioner", () => {
    const model = productionModel();
    const postgres = model.services.postgres as Record<string, unknown>;
    postgres.volumes = [];
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "exact PostgreSQL database server is missing",
    );
  });

  it("rejects an unreviewed backup archive volume", () => {
    const model = productionModel();
    model.volumes.pgbackups.name = "fixture_unreviewed_archive";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "postgres-backup does not match the exact dedicated backup runtime contract",
    );
  });

  it("discovers an extra trusted-login consumer even when it omits the profile", () => {
    const result = run(
      productionModel({
        "unreviewed-trusted-consumer": {
          environment: {
            DATABASE_URL:
              "postgresql://meddoc_runtime:credential@postgres:5432/meddoc",
            QUILLMD_SERVICE_ROLE: "unreviewed-service",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "unreviewed-trusted-consumer is an unreviewed PostgreSQL database consumer",
    );
  });

  it("detects a trusted runtime login supplied through POSTGRES_USER", () => {
    const result = run(
      productionModel({
        "unreviewed-postgres-environment-consumer": {
          environment: {
            POSTGRES_HOST: "postgres",
            POSTGRES_USER: "meddoc_runtime",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "unreviewed-postgres-environment-consumer is an unreviewed PostgreSQL database consumer",
    );
  });

  it("detects trusted identities in secondary PostgreSQL DSN variables", () => {
    const result = run(
      productionModel({
        "unreviewed-secondary-dsn-consumer": {
          environment: {
            DIRECT_URL: "postgresql://postgres:5432/meddoc?user=meddoc_runtime",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "unreviewed-secondary-dsn-consumer is an unreviewed PostgreSQL database consumer",
    );
  });

  it("rejects every arbitrary unreviewed PostgreSQL consumer regardless of login naming", () => {
    const result = run(
      productionModel({
        "arbitrary-restartable-consumer": {
          restart: "unless-stopped",
          environment: {
            DATABASE_URL:
              "postgresql://vendor_reader:credential@postgres:5432/meddoc",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "arbitrary-restartable-consumer is an unreviewed PostgreSQL database consumer",
    );
  });

  it("rejects a null database environment value instead of skipping it", () => {
    const result = run(
      productionModel({
        "unresolved-database-consumer": {
          environment: { DATABASE_URL: null },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "unresolved-database-consumer has an unresolved, duplicate, or indirect PostgreSQL database identity",
    );
  });

  it("rejects unreviewed and drifted env_file declarations", () => {
    const extra = run(
      productionModel({
        "unreviewed-env-file": {
          env_file: [{ path: `${ROOT}/.env`, required: true }],
        },
      }),
    );
    expect(extra.status).not.toBe(0);
    expect(extra.stderr).toContain(
      "unreviewed-env-file has an unreviewed env_file",
    );

    const driftedModel = productionModel();
    const meddocPro = driftedModel.services["meddoc-pro"] as {
      env_file: Array<{ path: string; required: boolean }>;
    };
    meddocPro.env_file.push({
      path: `${ROOT}/unreviewed.env`,
      required: true,
    });
    const drifted = run(driftedModel);
    expect(drifted.status).not.toBe(0);
    expect(drifted.stderr).toContain(
      "meddoc-pro has an unexpected env_file contract",
    );
  });

  it("rejects an expected service whose secondary DSN adds any other identity", () => {
    const model = productionModel();
    const meddocPro = model.services["meddoc-pro"] as {
      environment: Record<string, string>;
    };
    meddocPro.environment.DIRECT_URL =
      "postgresql://vendor_reader:credential@postgres:5432/meddoc";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro has an unexpected database identity set",
    );
  });

  it("rejects an unreviewed secondary DSN even when it repeats the expected identity", () => {
    const model = productionModel();
    const meddocPro = model.services["meddoc-pro"] as {
      environment: Record<string, string>;
    };
    meddocPro.environment.DIRECT_URL =
      "postgresql://meddoc_runtime:credential@postgres:5432/meddoc";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro has an unexpected database connection mechanism set",
    );
  });

  it("rejects an implicit PG environment connection group beside a correct URL", () => {
    const model = productionModel();
    const meddocPro = model.services["meddoc-pro"] as {
      environment: Record<string, string>;
    };
    meddocPro.environment.PGHOST = "postgres";
    meddocPro.environment.PGDATABASE = "meddoc";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro has an unresolved, duplicate, or indirect PostgreSQL database identity",
    );
  });

  it("rejects a duplicate PGUSER declaration beside the reviewed URL even when the identity matches", () => {
    const model = productionModel();
    const meddocPro = model.services["meddoc-pro"] as {
      environment: Record<string, string>;
    };
    meddocPro.environment.PGUSER = "meddoc_runtime";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro has an unexpected database connection mechanism set",
    );
  });

  it("rejects duplicate user query parameters even when they resolve to the same set value", () => {
    const model = productionModel();
    model.services["meddoc-pro"] = {
      environment: {
        DATABASE_URL:
          "postgresql://postgres:5432/meddoc?user=meddoc_runtime&user=meddoc_runtime",
        NODE_ENV: "production",
        QUILLMD_SERVICE_ROLE: "meddoc-pro-app",
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
      },
    };
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro has an unresolved, duplicate, or indirect PostgreSQL database identity",
    );
  });

  it("rejects a userless PostgreSQL URL as an unresolved candidate", () => {
    const result = run(
      productionModel({
        "userless-consumer": {
          environment: {
            DATABASE_URL: "postgresql://postgres:5432/meddoc",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "userless-consumer has an unresolved, duplicate, or indirect PostgreSQL database identity",
    );
  });

  it("rejects PGHOST and PGDATABASE when the login would be implicit", () => {
    const result = run(
      productionModel({
        "implicit-pg-consumer": {
          environment: {
            PGHOST: "postgres",
            PGDATABASE: "meddoc",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "implicit-pg-consumer has an unresolved, duplicate, or indirect PostgreSQL database identity",
    );
  });

  it.each([
    ["PGSERVICE", { PGSERVICE: "quillmd" }],
    ["PGSERVICEFILE", { PGSERVICEFILE: "/run/secrets/pg_service" }],
    [
      "POSTGRES_USER_FILE",
      {
        POSTGRES_HOST: "postgres",
        POSTGRES_DB: "meddoc",
        POSTGRES_USER_FILE: "/run/secrets/postgres_user",
      },
    ],
    ["DATABASE_URL_FILE", { DATABASE_URL_FILE: "/run/secrets/db_url" }],
  ] as const)("rejects indirect identity through %s", (_label, environment) => {
    const result = run(
      productionModel({
        "indirect-consumer": { environment },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "indirect-consumer has an unresolved, duplicate, or indirect PostgreSQL database identity",
    );
  });

  it.each([
    ["service-name DSN", "service=quillmd"],
    [
      "URL service parameter",
      "postgresql://meddoc_runtime@postgres:5432/meddoc?service=quillmd",
    ],
  ] as const)("rejects %s indirection", (_label, databaseUrl) => {
    const result = run(
      productionModel({
        "service-indirect-consumer": {
          environment: { DATABASE_URL: databaseUrl },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "service-indirect-consumer has an unresolved, duplicate, or indirect PostgreSQL database identity",
    );
  });

  it("rejects future meddoc-prefixed logins until they are explicitly reviewed", () => {
    const result = run(
      productionModel({
        "unreviewed-backup-runtime": {
          environment: {
            SHADOW_DATABASE_URL:
              "postgresql://meddoc_backup:credential@postgres:5432/meddoc",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "P1 pre-production blocker: unreviewed-backup-runtime uses an unreviewed dedicated meddoc database identity",
    );
  });

  it("rejects an incomplete meddoc_backup service", () => {
    const result = run(
      productionModel({
        "postgres-backup": {
          restart: "unless-stopped",
          environment: {
            POSTGRES_HOST: "postgres",
            POSTGRES_DB: "meddoc",
            POSTGRES_USER: "meddoc_backup",
            POSTGRES_PASSWORD_FILE: "/run/secrets/postgres_backup_password",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("network backup resource census drifted");
  });

  it("rejects the release-security login through PGUSER because it has no long-lived runtime", () => {
    const result = run(
      productionModel({
        "unreviewed-security-runtime": {
          restart: "unless-stopped",
          environment: {
            PGHOST: "postgres",
            PGUSER: "meddoc_release_security",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "P1 pre-production blocker: unreviewed-security-runtime uses meddoc_release_security, which has no allowed long-lived runtime",
    );
  });

  it("rejects an owner credential in the backup runtime", () => {
    const result = run(
      productionModel({
        "postgres-backup": {
          restart: "unless-stopped",
          environment: {
            POSTGRES_HOST: "postgres",
            POSTGRES_USER: "meddoc",
          },
        },
      }),
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("network backup resource census drifted");
  });

  it("allows the owner only for the exact closed segmented db-migrate contract", () => {
    const exactMigrator = exactProductionMigratorService();
    expect(run(productionModel({ "db-migrate": exactMigrator })).status).toBe(
      0,
    );

    const drifted = run(
      productionModel({
        "db-migrate": {
          ...exactMigrator,
          command: ["--phase", "all"],
        },
      }),
    );
    expect(drifted.status).not.toBe(0);
    expect(drifted.stderr).toContain(
      "exact closed segmented db-migrate runtime is missing",
    );

    const unsafeSearchPath = run(
      productionModel({
        "db-migrate": {
          ...exactMigrator,
          environment: {
            DATABASE_URL: "postgresql://meddoc:credential@postgres:5432/meddoc",
          },
        },
      }),
    );
    expect(unsafeSearchPath.status).not.toBe(0);
    expect(unsafeSearchPath.stderr).toContain(
      "exact closed segmented db-migrate runtime is missing",
    );

    const privilegedOverride = run(
      productionModel({
        "db-migrate": { ...exactMigrator, privileged: true },
      }),
    );
    expect(privilegedOverride.status).not.toBe(0);
    expect(privilegedOverride.stderr).toContain(
      "exact closed segmented db-migrate runtime is missing",
    );

    const injectedEnvironment = run(
      productionModel({
        "db-migrate": {
          ...exactMigrator,
          environment: {
            ...exactMigrator.environment,
            NODE_OPTIONS: "--require=/unreviewed/bootstrap.cjs",
          },
        },
      }),
    );
    expect(injectedEnvironment.status).not.toBe(0);
    expect(injectedEnvironment.stderr).toContain(
      "exact closed segmented db-migrate runtime is missing",
    );
  });

  it("requires one exact statement-timeout contract for preflight and every runtime", () => {
    const staticDrift = productionModel();
    (
      staticDrift.services["transcribe-md"] as {
        environment: Record<string, string>;
      }
    ).environment.PRISMA_STATEMENT_TIMEOUT_MS = "250";
    const staticResult = run(staticDrift);
    expect(staticResult.status).not.toBe(0);
    expect(staticResult.stderr).toContain(
      "does not share the exact preflight statement timeout",
    );

    const resolved = resolvedProductionModel();
    for (const name of Object.keys(productionServices)) {
      (
        resolved.services[name] as {
          environment: Record<string, string>;
        }
      ).environment.PRISMA_STATEMENT_TIMEOUT_MS = "250";
    }
    (
      resolved.services["db-migrate"] as {
        environment: Record<string, string>;
      }
    ).environment.PRISMA_STATEMENT_TIMEOUT_MS = "250";
    expect(runResolved(resolved).status).toBe(0);

    (
      resolved.services["auth-email-dispatcher"] as {
        environment: Record<string, string>;
      }
    ).environment.PRISMA_STATEMENT_TIMEOUT_MS = "0";
    const invalid = runResolved(resolved);
    expect(invalid.status).not.toBe(0);
    expect(invalid.stderr).toContain(
      "does not share the exact preflight statement timeout",
    );
  });

  it("excludes only the exact database server from owner-consumer enforcement", () => {
    const result = run(
      productionModel({
        postgres: exactPostgresService(),
      }),
    );
    expect(result.status).toBe(0);
  });

  it("rejects a mutable PostgreSQL server image tag", () => {
    const model = productionModel();
    const postgres = model.services.postgres as Record<string, unknown>;
    postgres.image = "pgvector/pgvector:pg16";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "exact PostgreSQL database server is missing",
    );
  });

  it.each(["entrypoint", "command", "privileged"] as const)(
    "rejects a PostgreSQL server %s override",
    (key) => {
      const model = productionModel();
      const postgres = model.services.postgres as Record<string, unknown>;
      postgres[key] = key === "privileged" ? true : ["unreviewed"];
      const result = run(model);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(
        "exact PostgreSQL database server is missing",
      );
    },
  );

  it("rejects a trusted production service whose NODE_ENV can drift", () => {
    const model = productionModel();
    model.services["meddoc-pro"] = {
      environment: {
        DATABASE_URL:
          "postgresql://meddoc_runtime:credential@postgres:5432/meddoc",
        NODE_ENV: "development",
        QUILLMD_SERVICE_ROLE: "meddoc-pro-app",
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
      },
    };
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "meddoc-pro does not force NODE_ENV production",
    );
  });

  it.each([
    ["meddoc-pro", "privileged", true],
    ["transcribe-md", "cap_add", ["SYS_ADMIN"]],
    ["transcribe-md-worker", "devices", ["/dev/null:/dev/example"]],
    ["template-twin-admin-app", "pid", "host"],
  ] as const)(
    "rejects unreviewed container authority on %s via %s",
    (serviceName, key, value) => {
      const model = productionModel();
      const service = model.services[serviceName] as Record<string, unknown>;
      service[key] = value;
      const result = run(model);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(
        `${serviceName} has unreviewed container authority`,
      );
    },
  );

  it("rejects unreviewed host authority even without a declared database consumer", () => {
    const model = productionModel({
      "unreviewed-privileged": { privileged: true },
    });
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "unreviewed-privileged has unreviewed container authority",
    );
  });

  it.each([
    ["user override", "user", "0:0"],
    ["missing capability drop", "cap_drop", undefined],
    ["unsafe security option", "security_opt", ["seccomp=unconfined"]],
    ["API socket delegation", "use_api_socket", true],
    ["post-start hook", "post_start", [{ command: ["true"] }]],
    ["pre-stop hook", "pre_stop", [{ command: ["true"] }]],
    ["supplemental group drift", "group_add", ["0"]],
    ["sysctl drift", "sysctls", { "kernel.unprivileged_userns_clone": "1" }],
  ] as const)(
    "rejects production runtime authority drift: %s",
    (_label, key, value) => {
      const model = productionModel();
      const service = model.services["meddoc-pro"] as Record<string, unknown>;
      if (value === undefined) delete service[key];
      else service[key] = value;
      const result = run(model);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain("meddoc-pro");
    },
  );

  it("rejects protected container-runtime data binds", () => {
    const model = productionModel();
    const service = model.services["transcribe-md-worker"] as Record<
      string,
      unknown
    >;
    service.volumes = [
      {
        bind: { create_host_path: true },
        source: "/var/lib/docker",
        target: "/host-runtime-data",
        type: "bind",
      },
    ];
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("exposes protected container runtime data");
  });

  it.each([
    ["command", { command: ["postgresql://unreviewed.invalid/db"] }],
    ["entrypoint", { entrypoint: ["$DATABASE_URL"] }],
    [
      "healthcheck",
      { healthcheck: { test: ["CMD", "postgresql://unreviewed.invalid/db"] } },
    ],
    [
      "build argument",
      { build: { args: { DATABASE_BOOTSTRAP: "${DB_PASSWORD:?required}" } } },
    ],
    ["label", { labels: { diagnostic: "postgresql://unreviewed.invalid/db" } }],
    [
      "nested environment value",
      {
        environment: {
          UNRELATED_JSON: '{"endpoint":"postgresql://unreviewed.invalid/db"}',
        },
      },
    ],
  ] as const)(
    "rejects database material in an unreviewed %s location",
    (_label, service) => {
      const result = run(productionModel({ "unreviewed-material": service }));
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(
        "unreviewed-material contains database connection material outside reviewed environment locations",
      );
    },
  );

  it("rejects a resolved reviewed credential fingerprint outside its URL location", () => {
    const model = resolvedProductionModel();
    model.services["unreviewed-resolved-material"] = {
      labels: { diagnostic: RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_runtime },
    };
    const result = runResolved(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "unreviewed-resolved-material contains database connection material outside reviewed environment locations",
    );
  });

  it("requires explicit blank credential suppression on env-file runtimes", () => {
    const nonEmpty = productionModel();
    const nonEmptyEnvironment = (
      nonEmpty.services["meddoc-pro"] as {
        environment: Record<string, string>;
      }
    ).environment;
    nonEmptyEnvironment.DB_PASSWORD = "synthetic-non-production-value";
    expect(run(nonEmpty).stderr).toContain(
      "meddoc-pro has an unexpected runtime authority contract",
    );

    const missing = productionModel();
    delete (
      missing.services["meddoc-pro"] as {
        environment: Record<string, string>;
      }
    ).environment.DB_PASSWORD;
    expect(run(missing).stderr).toContain(
      "meddoc-pro has an unexpected runtime authority contract",
    );

    const folded = resolvedProductionModel();
    (
      folded.services["meddoc-pro"] as {
        environment: Record<string, string>;
      }
    ).environment.DB_BACKUP_PASSWORD_FILE = "/synthetic/unreviewed";
    expect(runResolved(folded).stderr).toContain(
      "meddoc-pro has an unexpected runtime authority contract",
    );
  });

  it("rejects unreviewed database credential channels even outside the fixed key list", () => {
    const model = productionModel();
    (
      model.services["transcribe-md-worker"] as {
        environment: Record<string, string>;
      }
    ).environment.DB_VENDOR_PASSWORD = "synthetic-non-production-value";
    const result = run(model);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "transcribe-md-worker has an unexpected runtime authority contract",
    );
  });

  it.each(["extra_hosts", "links", "external_links"] as const)(
    "rejects database destination indirection through %s",
    (key) => {
      const model = productionModel();
      (model.services["transcribe-md"] as Record<string, unknown>)[key] = [
        "postgres:127.0.0.1",
      ];
      const result = run(model);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(
        "uses unreviewed namespace or volume sharing",
      );
    },
  );

  it("rejects protected endpoint aliases and network attachment aliases", () => {
    const endpoint = productionModel({
      "unreviewed-endpoint": { hostname: "postgres" },
    });
    expect(run(endpoint).stderr).toContain(
      "collides with the protected database endpoint",
    );

    const attachment = productionModel();
    (
      attachment.services["transcribe-md"] as {
        networks: Record<string, unknown>;
      }
    ).networks.default = { aliases: ["postgres"] };
    expect(run(attachment).status).not.toBe(0);
  });

  it("freezes production runtime build, image, command, port, and network surfaces", () => {
    const cases: Array<[string, () => ReturnType<typeof productionModel>]> = [
      [
        "build",
        () => {
          const model = productionModel();
          (
            model.services["meddoc-pro"] as { build: { context: string } }
          ).build.context = "/unreviewed";
          return model;
        },
      ],
      [
        "image",
        () => {
          const model = productionModel();
          (model.services["transcribe-md"] as { image: string }).image =
            "unreviewed:latest";
          return model;
        },
      ],
      [
        "port",
        () => {
          const model = productionModel();
          (
            model.services["template-twin-admin-control"] as { ports: unknown }
          ).ports = ["0.0.0.0:3012:3011"];
          return model;
        },
      ],
      [
        "network",
        () => {
          const model = productionModel();
          (
            model.services["template-twin-admin-control"] as {
              networks: Record<string, null>;
            }
          ).networks.auth_email_egress = null;
          return model;
        },
      ],
      [
        "command",
        () => {
          const model = productionModel();
          (
            model.services["template-twin-audit-dispatcher"] as {
              command: string[];
            }
          ).command = ["unreviewed"];
          return model;
        },
      ],
    ];
    for (const [, create] of cases) {
      const result = run(create());
      expect(result.status).not.toBe(0);
    }
  });

  it("enforces exact production named-resource and MFA keyring consumers", () => {
    const named = productionModel();
    (
      named.services["transcribe-md"] as {
        volumes: Array<Record<string, unknown>>;
      }
    ).volumes.push({
      source: "minio_data",
      target: "/object-store",
      type: "volume",
      volume: {},
    });
    expect(run(named).status).not.toBe(0);

    const legacy = productionModel({
      "legacy-volume-reader": {
        volumes: [
          { source: "pgdata", target: "/legacy", type: "volume", volume: {} },
        ],
      },
    });
    expect(run(legacy).stderr).toContain(
      "pgdata named volume consumer census drifted",
    );

    const keyring = productionModel();
    keyring.services["unreviewed-keyring-reader"] = {
      volumes: [
        {
          bind: { create_host_path: false },
          read_only: true,
          source: path.join(
            ROOT,
            "${MFA_SECRET_KEYRING_FILE:?MFA_SECRET_KEYRING_FILE is required}",
          ),
          target:
            "${MFA_SECRET_KEYRING_FILE:?MFA_SECRET_KEYRING_FILE is required}",
          type: "bind",
        },
      ],
    };
    expect(run(keyring).stderr).toContain(
      "MFA keyring consumer census drifted",
    );
  });

  it.each([
    "type",
    "source",
    "target",
    "read_only",
    "missing_read_only",
    "create_host_path",
    "extra_bind_option",
  ])(
    "rejects %s drift in both static and resolved MFA keyring mounts",
    (drift) => {
      const applyDrift = (model: ReturnType<typeof productionModel>): void => {
        const service = model.services["template-twin-admin-app"] as {
          volumes: Array<Record<string, unknown>>;
        };
        const mount = service.volumes[0];
        if (!mount) throw new Error("fixture omitted admin MFA keyring mount");
        if (drift === "type") mount.type = "volume";
        else if (drift === "source") mount.source = "/unreviewed/keyring";
        else if (drift === "target") mount.target = "/unreviewed/keyring";
        else if (drift === "read_only") mount.read_only = false;
        else if (drift === "missing_read_only") delete mount.read_only;
        else if (drift === "create_host_path") {
          const bind = mount.bind as Record<string, unknown>;
          bind.create_host_path = true;
        } else {
          const bind = mount.bind as Record<string, unknown>;
          bind.propagation = "rprivate";
        }
      };

      const staticModel = productionModel();
      applyDrift(staticModel);
      expect(run(staticModel).status).not.toBe(0);

      const resolvedModel = resolvedProductionModel();
      applyDrift(resolvedModel);
      expect(runResolved(resolvedModel).status).not.toBe(0);
    },
  );

  it("rejects an omitted static no-create keyring bind contract", () => {
    const model = productionModel();
    const service = model.services["template-twin-admin-app"] as {
      volumes: Array<{ bind: Record<string, unknown> }>;
    };
    delete service.volumes[0].bind.create_host_path;
    expect(run(model).status).not.toBe(0);
  });

  it.each([
    ["transcribe-md", [null, ["101"], ["1001"], ["101", "1001", "2000"]]],
    ["template-twin-admin-app", [null, [], ["2000"], ["1001", "2000"]]],
  ] as const)(
    "rejects omitted, wrong, or extra MFA reader groups for %s",
    (serviceName, driftedGroups) => {
      for (const groupAdd of driftedGroups) {
        for (const [model, execute] of [
          [productionModel(), run],
          [resolvedProductionModel(), runResolved],
        ] as const) {
          const service = model.services[serviceName] as Record<
            string,
            unknown
          >;
          service.group_add = groupAdd;
          const result = execute(model);
          expect(result.status).not.toBe(0);
          expect(result.stderr).toContain(serviceName);
        }
      }
    },
  );

  it("rejects MFA keyring gid 1001 on every non-consumer runtime", () => {
    for (const serviceName of [
      "meddoc-pro",
      "template-twin-admin-control",
      "transcribe-md-worker",
      "template-twin-audit-dispatcher",
      "auth-email-dispatcher",
    ]) {
      const model = productionModel();
      const service = model.services[serviceName] as Record<string, unknown>;
      service.group_add = ["1001"];
      const result = run(model);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(serviceName);
    }
  });

  it("rejects non-disposable or aliased QA resources and consumers", () => {
    const external = exactQaModel();
    (external.volumes.qa_pgdata as Record<string, unknown>).external = true;
    expect(run(external, "--qa").status).not.toBe(0);

    const productionNamed = exactQaModel();
    productionNamed.volumes.qa_pgdata.name = "meddoc-pro_pgdata";
    expect(run(productionNamed, "--qa").status).not.toBe(0);

    const alias = exactQaModel();
    (alias.volumes as Record<string, unknown>).qa_pgdata_alias = {
      name: "meddoc-qa_qa_pgdata",
    };
    expect(run(alias, "--qa").status).not.toBe(0);

    const appMount = exactQaModel();
    (
      appMount.services["transcribe-md"] as {
        volumes: Array<Record<string, unknown>>;
      }
    ).volumes.push({
      source: "qa_pgdata",
      target: "/database",
      type: "volume",
      volume: {},
    });
    expect(run(appMount, "--qa").status).not.toBe(0);

    const secret = exactQaModel();
    (secret.secrets as Record<string, unknown>).unreviewed = {
      file: "/synthetic/secret",
    };
    (secret.services["transcribe-md"] as Record<string, unknown>).secrets = [
      { source: "unreviewed", target: "/run/secrets/unreviewed" },
    ];
    expect(run(secret, "--qa").stderr).toContain(
      "transcribe-md has an unexpected runtime authority contract",
    );

    const network = exactQaModel();
    (network.networks.default as Record<string, unknown>).external = true;
    expect(run(network, "--qa").status).not.toBe(0);
  });

  it("unconditionally requires the exact QA database and migrator runtimes", () => {
    const database = exactQaModel();
    database.services.postgres = { image: "busybox:latest" } as never;
    expect(run(database, "--qa").stderr).toContain(
      "exact PostgreSQL database server is missing",
    );

    const migrator = exactQaModel();
    migrator.services["db-migrate"] = { image: "busybox:latest" } as never;
    expect(run(migrator, "--qa").stderr).toContain(
      "exact closed segmented db-migrate runtime is missing",
    );
  });

  it("rejects the owner login and noncanonical options in long-lived QA runtimes", () => {
    const owner = exactQaModel();
    (
      owner.services["transcribe-md"] as {
        environment: Record<string, string>;
      }
    ).environment.DATABASE_URL =
      `postgresql://meddoc:qa_test_pw@postgres:5432/meddoc_qa_test?${CANONICAL_QUERY}`;
    expect(run(owner, "--qa").stderr).toContain(
      "uses the meddoc owner database identity outside the exact closed segmented db-migrate boundary",
    );

    const options = exactQaModel();
    const app = options.services["transcribe-md"] as {
      environment: Record<string, string>;
    };
    app.environment.DATABASE_URL = app.environment.DATABASE_URL.replace(
      `&${CANONICAL_OPTIONS}`,
      "",
    );
    expect(run(options, "--qa").stderr).toContain(
      "transcribe-md does not force the canonical PostgreSQL search_path",
    );
  });

  it("requires the exact QA role initializer and backup-secret consumer", () => {
    const missingInitializer = exactQaModel();
    (
      missingInitializer.services.postgres as {
        volumes: Array<Record<string, unknown>>;
      }
    ).volumes.pop();
    expect(run(missingInitializer, "--qa").stderr).toContain(
      "exact PostgreSQL database server is missing",
    );

    const missingSecret = exactQaModel();
    delete (
      missingSecret.services.postgres as {
        secrets?: Array<Record<string, string>>;
      }
    ).secrets;
    expect(run(missingSecret, "--qa").stderr).toContain(
      "exact PostgreSQL database server is missing",
    );

    const extraConsumer = exactQaModel();
    (
      extraConsumer.services["transcribe-md-worker"] as Record<string, unknown>
    ).secrets = [
      {
        source: "qa_postgres_backup_password",
        target: "/run/secrets/qa_postgres_backup_password",
      },
    ];
    expect(run(extraConsumer, "--qa").status).not.toBe(0);
  });

  it("binds resolved QA runtime URLs to the exact provisioned role credential", () => {
    const wrongRuntimeCredential = resolvedQaModel();
    const app = wrongRuntimeCredential.services["transcribe-md"] as {
      environment: Record<string, string>;
    };
    app.environment.DATABASE_URL = app.environment.DATABASE_URL.replace(
      RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_runtime,
      RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_release_control,
    );
    expect(runResolvedQa(wrongRuntimeCredential).status).not.toBe(0);

    const duplicateRoleCredentials = resolvedQaModel();
    const postgres = duplicateRoleCredentials.services.postgres as {
      environment: Record<string, string>;
    };
    postgres.environment.DB_RELEASE_CONTROL_PASSWORD =
      RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_runtime;
    expect(runResolvedQa(duplicateRoleCredentials).stderr).toContain(
      "resolved database credentials are not role-distinct",
    );
  });

  it.each([
    ["mutable image", "image", "unreviewed:latest"],
    ["missing capability drop", "cap_drop", undefined],
    ["restart drift", "restart", "unless-stopped"],
    ["public port drift", "ports", ["0.0.0.0:9020:3011"]],
    ["healthcheck drift", "healthcheck", undefined],
    ["resource drift", "mem_limit", "2g"],
  ] as const)("rejects QA runtime surface drift: %s", (_label, key, value) => {
    const model = exactQaModel();
    const service = model.services["transcribe-md"] as Record<string, unknown>;
    if (value === undefined) delete service[key];
    else service[key] = value;
    const result = run(model, "--qa");
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "transcribe-md has an unexpected runtime authority contract",
    );
  });

  it.each([
    ["missing", undefined],
    [
      "existence only",
      {
        interval: "30s",
        retries: 3,
        start_period: "60s",
        test: ["CMD-SHELL", "test -f /tmp/worker-heartbeat"],
        timeout: "5s",
      },
    ],
    [
      "stale threshold",
      {
        ...exactRuntimeHealthcheck("transcribe-md-worker"),
        test: [
          "CMD-SHELL",
          "test -f /tmp/worker-heartbeat && [ $(( $(date +%s) - $(stat -c %Y /tmp/worker-heartbeat) )) -lt 600 ]",
        ],
      },
    ],
    [
      "timing drift",
      {
        ...exactRuntimeHealthcheck("transcribe-md-worker"),
        start_period: "30s",
      },
    ],
  ] as const)("rejects QA worker healthcheck drift: %s", (_label, value) => {
    const model = exactQaModel();
    const worker = model.services["transcribe-md-worker"] as Record<
      string,
      unknown
    >;
    if (value === undefined) delete worker.healthcheck;
    else worker.healthcheck = value;
    const result = run(model, "--qa");
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "transcribe-md-worker has an unexpected runtime authority contract",
    );
  });

  it("admits the exact disposable QA runtimes and closed segmented migrator", () => {
    const result = run(exactQaModel(), "--qa");
    expect(result.status, result.stderr).toBe(0);
    expect(result.stdout).toContain(
      "profile=synthetic-qa mode=static-unresolved services=2",
    );
  });

  it("rejects omitted, wrong, or extra MFA reader groups in QA", () => {
    for (const groupAdd of [null, ["101"], ["1001"], ["101", "1001", "2000"]]) {
      for (const [model, execute] of [
        [exactQaModel(), (value: unknown) => run(value, "--qa")],
        [resolvedQaModel(), runResolvedQa],
      ] as const) {
        const service = model.services["transcribe-md"] as Record<
          string,
          unknown
        >;
        service.group_add = groupAdd;
        const result = execute(model);
        expect(result.status).not.toBe(0);
        expect(result.stderr).toContain("transcribe-md");
      }
    }
  });

  it("rejects QA PostgreSQL Dockerfile or rootfs drift", () => {
    const buildDrift = exactQaModel();
    (
      buildDrift.services.postgres as {
        build: { dockerfile: string };
      }
    ).build.dockerfile = "unreviewed.Dockerfile";
    expect(run(buildDrift, "--qa").stderr).toContain(
      "exact PostgreSQL database server is missing",
    );

    const rootfsDrift = exactQaModel();
    (rootfsDrift.services.postgres as { read_only: boolean }).read_only = false;
    expect(run(rootfsDrift, "--qa").stderr).toContain(
      "exact PostgreSQL database server is missing",
    );
  });

  it("admits only approved immutable QA images in resolved mode", () => {
    const result = runResolvedQa(resolvedQaModel());
    expect(result.status, result.stderr).toBe(0);
    expect(result.stdout).toContain(
      "profile=synthetic-qa mode=resolved services=2",
    );

    const mutable = resolvedQaModel();
    (mutable.services["transcribe-md"] as Record<string, unknown>).image =
      "meddoc-pro-transcribe-md:latest";
    expect(runResolvedQa(mutable).status).not.toBe(0);
  });

  it("accepts the actual fully resolved QA Compose model with approved images", () => {
    const directory = mkdtempSync(
      path.join(os.tmpdir(), "meddoc-runtime-qa-census-"),
    );
    try {
      writeFileSync(
        path.join(directory, "docker-compose.qa.yml"),
        readFileSync(path.join(ROOT, "docker-compose.qa.yml")),
      );
      copyPostgresHostAuthenticationSources(directory);
      const composeEnvironment = {
        ...Object.fromEntries(
          ["PATH", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"]
            .filter((key) => process.env[key] !== undefined)
            .map((key) => [key, process.env[key]]),
        ),
        QA_DB_MIGRATE_IMAGE: APPROVED_QA_MIGRATOR_IMAGE,
        QA_POSTGRES_IMAGE: APPROVED_QA_POSTGRES_IMAGE,
        QA_DB_RUNTIME_PASSWORD: RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_runtime,
        QA_DB_RELEASE_CONTROL_PASSWORD:
          RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_release_control,
        QA_DB_AUDIT_DISPATCHER_PASSWORD:
          RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_audit_dispatcher,
        QA_DB_AUTH_EMAIL_DISPATCHER_PASSWORD:
          RESOLVED_CREDENTIAL_BY_LOGIN.meddoc_auth_email_dispatcher,
        QA_DB_BACKUP_PASSWORD_FILE: APPROVED_QA_BACKUP_PASSWORD_PATH,
        QA_MFA_SECRET_ACTIVE_KEY_ID: "synthetic-runtime-census-key",
        QA_MFA_SECRET_KEYRING_FILE: APPROVED_KEYRING_PATH,
        QA_TRANSCRIBE_MD_IMAGE: APPROVED_FRONTEND_IMAGE,
        QA_TRANSCRIBE_MD_WORKER_IMAGE: APPROVED_WORKER_IMAGE,
      };
      const compose = spawnSync(
        "docker",
        [
          "compose",
          "--profile",
          "*",
          "-f",
          "docker-compose.qa.yml",
          "config",
          "--format",
          "json",
        ],
        {
          cwd: directory,
          encoding: "utf8",
          env: composeEnvironment as unknown as NodeJS.ProcessEnv,
        },
      );
      expect(compose.status, compose.stderr).toBe(0);
      const resolvedModel = JSON.parse(compose.stdout) as {
        services: Record<string, { group_add?: string[] }>;
      };
      expect(resolvedModel.services["transcribe-md"]?.group_add).toEqual([
        "101",
        "1001",
      ]);
      const census = spawnSync("node", [CENSUS, "--qa"], {
        cwd: directory,
        encoding: "utf8",
        env: {
          ...process.env,
          QUILLMD_APPROVED_QA_DB_MIGRATE_IMAGE: APPROVED_QA_MIGRATOR_IMAGE,
          QUILLMD_APPROVED_QA_POSTGRES_IMAGE: APPROVED_QA_POSTGRES_IMAGE,
          QUILLMD_APPROVED_QA_DB_BACKUP_PASSWORD_FILE:
            APPROVED_QA_BACKUP_PASSWORD_PATH,
          QUILLMD_APPROVED_QA_MFA_SECRET_KEYRING_FILE: APPROVED_KEYRING_PATH,
          QUILLMD_APPROVED_QA_TRANSCRIBE_MD_IMAGE: APPROVED_FRONTEND_IMAGE,
          QUILLMD_APPROVED_QA_TRANSCRIBE_MD_WORKER_IMAGE: APPROVED_WORKER_IMAGE,
        },
        input: compose.stdout,
      });
      expect(census.status, census.stderr).toBe(0);
      expect(census.stdout).toContain(
        "profile=synthetic-qa mode=resolved services=2",
      );
    } finally {
      rmSync(directory, { force: true, recursive: true });
    }
  });
});
