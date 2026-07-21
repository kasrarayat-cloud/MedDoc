#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFileSync, realpathSync, statSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const EXACT_PROFILE = "exact-production-v1";
const SYNTHETIC_QA_PROFILE = "synthetic-disposable-qa-v1";
const PROFILE_ENVIRONMENT = "QUILLMD_DATABASE_PRINCIPAL_PROFILE";
const STATEMENT_TIMEOUT_ENVIRONMENT = "PRISMA_STATEMENT_TIMEOUT_MS";
const STATIC_STATEMENT_TIMEOUT = "${PRISMA_STATEMENT_TIMEOUT_MS:-30000}";
const MIGRATION_LOCK_TIMEOUT_ENVIRONMENT =
  "DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS";
const STATIC_MIGRATION_LOCK_TIMEOUT =
  "${DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS:-5000}";
const MIGRATION_NETWORK_BOUNDARY_ENVIRONMENT =
  "DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY";
const MIGRATION_NETWORK_BOUNDARY = "postgres-loopback-v1";
const DATABASE_OWNER_LOGIN = "meddoc";
const BACKUP_LOGIN = "meddoc_backup";
const RELEASE_SECURITY_LOGIN = "meddoc_release_security";
const CANONICAL_SEARCH_PATH_OPTION = "-c search_path=pg_catalog,public";
const BASE64URL_CREDENTIAL = /^[A-Za-z0-9_-]{43,128}$/u;
const PASSWORD_ENVIRONMENT_BY_LOGIN = new Map([
  [DATABASE_OWNER_LOGIN, "DB_PASSWORD"],
  ["meddoc_runtime", "DB_RUNTIME_PASSWORD"],
  ["meddoc_release_control", "DB_RELEASE_CONTROL_PASSWORD"],
  ["meddoc_audit_dispatcher", "DB_AUDIT_DISPATCHER_PASSWORD"],
  ["meddoc_auth_email_dispatcher", "DB_AUTH_EMAIL_DISPATCHER_PASSWORD"],
]);
const QA_PASSWORD_ENVIRONMENT_BY_LOGIN = new Map([
  ["meddoc_runtime", "QA_DB_RUNTIME_PASSWORD"],
  ["meddoc_release_control", "QA_DB_RELEASE_CONTROL_PASSWORD"],
  ["meddoc_audit_dispatcher", "QA_DB_AUDIT_DISPATCHER_PASSWORD"],
  ["meddoc_auth_email_dispatcher", "QA_DB_AUTH_EMAIL_DISPATCHER_PASSWORD"],
]);
const BACKUP_IMAGE =
  "prodrigestivill/postgres-backup-local@sha256:a0103fbce0c48ccc7693ddbb2a2bfa733048db845354f635efef9e4566de185d";
const POSTGRES_BASE_IMAGE =
  "pgvector/pgvector:pg16@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff";
const STATIC_POSTGRES_IMAGE =
  "${QUILLMD_POSTGRES_IMAGE:?QUILLMD_POSTGRES_IMAGE must be an immutable sha256 digest}";
const APPROVED_POSTGRES_IMAGE_ENVIRONMENT = "QUILLMD_APPROVED_POSTGRES_IMAGE";
const STATIC_QA_POSTGRES_IMAGE =
  "${QA_POSTGRES_IMAGE:-meddoc-qa-postgres:latest}";
const APPROVED_QA_POSTGRES_IMAGE_ENVIRONMENT =
  "QUILLMD_APPROVED_QA_POSTGRES_IMAGE";
const POSTGRES_DOCKERFILE = "infra/postgres/Dockerfile";
const POSTGRES_DOCKERIGNORE = "infra/postgres/.dockerignore";
const POSTGRES_DOCKERIGNORE_SHA256 =
  "d7084621521d6316ab21063e757e96ac57e8910c3b5571c0557ae28f544c01f0";
const POSTGRES_DOCKERFILE_SHA256 =
  "ea50af8ce2e7561d30931b71490a7c5cfb20799bd9f69ef63c4a1e5f0001035e";
const POSTGRES_HBA_PATH = "/etc/postgresql/quillmd-pg_hba.conf";
const POSTGRES_HBA_SHA256 =
  "8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0";
const POSTGRES_HBA_VERIFIER_PATH = "/opt/quillmd/verify-quillmd-host-auth.sh";
const POSTGRES_HBA_VERIFIER_SHA256 =
  "c243bb5e2d1313025c392bb5a510e0e9d289b0f316e0eb236881484bb0d79e18";
const POSTGRES_ENTRYPOINT_SOURCE =
  "infra/postgres/quillmd-postgres-entrypoint.sh";
const POSTGRES_ENTRYPOINT_PATH =
  "/usr/local/bin/quillmd-postgres-entrypoint.sh";
const POSTGRES_ENTRYPOINT_SHA256 =
  "1121ef841eea8e0b2c7ba3e23c261f19c2806e17217eedd564eccf8c2d705d0a";
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
let staticUnresolved = false;
let resolvedCredentialFingerprintByLogin = new Map();
const DATABASE_CREDENTIAL_ENVIRONMENT_KEYS = [
  "DB_PASSWORD",
  "DB_RUNTIME_PASSWORD",
  "DB_RELEASE_CONTROL_PASSWORD",
  "DB_RELEASE_SECURITY_PASSWORD",
  "DB_AUDIT_DISPATCHER_PASSWORD",
  "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
  "DB_BACKUP_PASSWORD_FILE",
  "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
];
const TRUSTED_PRODUCTION_LOGINS = new Set([
  "meddoc_runtime",
  "meddoc_release_control",
  RELEASE_SECURITY_LOGIN,
  "meddoc_audit_dispatcher",
  "meddoc_auth_email_dispatcher",
]);
const productionServices = new Map([
  [
    "meddoc-pro",
    {
      role: "meddoc-pro-app",
      login: "meddoc_runtime",
      boundary: "quillmd_runtime",
      connectionMechanisms: ["url:DATABASE_URL"],
      envFile: "repository",
      groupAdd: "absent",
      command: "absent",
      securityOpt: "absent",
      volumes: "absent",
    },
  ],
  [
    "transcribe-md",
    {
      role: "physician-app",
      login: "meddoc_runtime",
      boundary: "quillmd_runtime",
      connectionMechanisms: ["url:DATABASE_URL"],
      envFile: "repository",
      groupAdd: ["101", "1001"],
      command: "absent",
      securityOpt: "absent",
      volumes: "physician-app",
    },
  ],
  [
    "template-twin-admin-app",
    {
      role: "template-twin-admin-app",
      login: "meddoc_runtime",
      boundary: "quillmd_runtime",
      connectionMechanisms: ["url:DATABASE_URL"],
      envFile: "empty",
      groupAdd: ["1001"],
      command: "absent",
      securityOpt: "absent",
      volumes: "admin-keyring",
    },
  ],
  [
    "template-twin-admin-control",
    {
      role: "template-twin-admin-control",
      login: "meddoc_release_control",
      boundary: "quillmd_release_control",
      connectionMechanisms: [
        "url:DATABASE_URL",
        "url:TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
      ],
      envFile: "empty",
      groupAdd: "empty",
      command: "absent",
      securityOpt: "absent",
      volumes: "empty",
    },
  ],
  [
    "transcribe-md-worker",
    {
      role: "transcribe-md-worker",
      login: "meddoc_runtime",
      boundary: "quillmd_runtime",
      connectionMechanisms: ["url:DATABASE_URL"],
      envFile: "repository",
      groupAdd: "absent",
      command: "absent",
      securityOpt: "absent",
      volumes: "absent",
    },
  ],
  [
    "template-twin-audit-dispatcher",
    {
      role: "template-twin-audit-dispatcher",
      login: "meddoc_audit_dispatcher",
      boundary: "quillmd_audit_dispatcher",
      connectionMechanisms: ["url:DATABASE_URL"],
      envFile: "absent",
      groupAdd: "absent",
      command: ["npx", "tsx", "src/audit-dispatcher.ts"],
      securityOpt: ["no-new-privileges:true"],
      volumes: "absent",
    },
  ],
  [
    "auth-email-dispatcher",
    {
      role: "auth-email-dispatcher",
      login: "meddoc_auth_email_dispatcher",
      boundary: "quillmd_auth_email_dispatcher",
      connectionMechanisms: ["url:DATABASE_URL"],
      envFile: "empty",
      groupAdd: "absent",
      command: ["npm", "run", "auth-email-dispatcher"],
      securityOpt: ["no-new-privileges:true"],
      volumes: "absent",
    },
  ],
]);

const qaServices = new Map([
  [
    "transcribe-md",
    {
      role: "physician-app",
      login: "meddoc_runtime",
      boundary: "quillmd_runtime",
      connectionMechanisms: ["url:DATABASE_URL"],
      envFile: "absent",
      groupAdd: ["101", "1001"],
      command: "absent",
      securityOpt: "absent",
      volumes: "qa-physician-app",
    },
  ],
  [
    "transcribe-md-worker",
    {
      role: "transcribe-md-worker",
      login: "meddoc_runtime",
      boundary: "quillmd_runtime",
      connectionMechanisms: ["url:DATABASE_URL"],
      envFile: "absent",
      groupAdd: "absent",
      command: "absent",
      securityOpt: "absent",
      volumes: "absent",
    },
  ],
]);

const PRODUCTION_VOLUME_CONSUMERS = new Map([
  ["caddy_config", [["caddy", "/config", false]]],
  ["caddy_data", [["caddy", "/data", false]]],
  ["clamav_signatures", [["template-twin-clamav", "/var/lib/clamav", false]]],
  [
    "clamav_socket",
    [
      ["template-twin-clamav", "/run/clamav", false],
      ["transcribe-md", "/var/run/quillmd-clamav", true],
    ],
  ],
  ["minio_data", [["minio", "/data", false]]],
  ["pgbackups", [["postgres-backup", "/backups", false]]],
  ["pgdata", []],
  ["redis_data", [["redis", "/data", false]]],
]);
const QA_VOLUME_CONSUMERS = new Map([
  [
    "qa_clamav_signatures",
    [["template-twin-clamav", "/var/lib/clamav", false]],
  ],
  [
    "qa_clamav_socket",
    [
      ["template-twin-clamav", "/run/clamav", false],
      ["transcribe-md", "/var/run/quillmd-clamav", true],
    ],
  ],
  ["qa_minio", [["minio", "/data", false]]],
  ["qa_pgdata", [["postgres", "/var/lib/postgresql/data", false]]],
]);
const PRODUCTION_NETWORK_CONSUMERS = new Map([
  ["auth_email_database", ["auth-email-dispatcher", "postgres"]],
  ["auth_email_egress", ["auth-email-dispatcher"]],
  ["backup_database", ["postgres", "postgres-backup"]],
  [
    "default",
    [
      "marketing",
      "meddoc-pro",
      "minio",
      "postgres",
      "redis",
      "template-twin-admin-app",
      "template-twin-admin-control",
      "template-twin-audit-dispatcher",
      "transcribe-md",
      "transcribe-md-worker",
    ],
  ],
  [
    "quillmd_ingress",
    [
      "caddy",
      "marketing",
      "meddoc-pro",
      "template-twin-admin-app",
      "template-twin-admin-control",
      "transcribe-md",
    ],
  ],
  ["template_twin_scanner", ["template-twin-clamav"]],
]);
const QA_NETWORK_CONSUMERS = new Map([
  [
    "default",
    [
      "marketing",
      "minio",
      "minio-template-init",
      "postgres",
      "redis",
      "transcribe-md",
      "transcribe-md-worker",
    ],
  ],
  ["template_twin_scanner", ["template-twin-clamav"]],
]);

function fail(message) {
  process.stderr.write(`database-principal-census: ${message}\n`);
  process.exit(65);
}

function decodedIdentity(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

function credentialFingerprint(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function emptyInspection() {
  return {
    candidate: false,
    identities: new Set(),
    issues: new Set(),
    mechanisms: [],
    postgresOptions: [],
    postgresOptionGroups: [],
    postgresUrlContracts: [],
    postgresAuthority: null,
    postgresCredentialContract: "missing",
    postgresDatabase: null,
    postgresFragmentPresent: false,
    postgresQueryEntries: [],
  };
}

function mergeInspection(target, source) {
  if (!source) return;
  target.candidate ||= source.candidate;
  for (const identity of source.identities) target.identities.add(identity);
  for (const issue of source.issues) target.issues.add(issue);
  target.postgresOptions.push(...source.postgresOptions);
}

function addMechanism(target, kind, key, source) {
  target.mechanisms.push(`${kind}:${key}`);
  if (kind === "url") {
    target.postgresOptionGroups.push({
      key,
      options: [...source.postgresOptions],
    });
    target.postgresUrlContracts.push({
      key,
      authority: source.postgresAuthority,
      credentialContract: source.postgresCredentialContract,
      credentialFingerprint: source.postgresCredentialFingerprint,
      database: source.postgresDatabase,
      fragmentPresent: source.postgresFragmentPresent,
      queryEntries: [...source.postgresQueryEntries],
    });
  }
  mergeInspection(target, source);
}

function addLiteralIdentity(inspection, value) {
  const identity = value?.trim() ?? "";
  if (!identity || /\$\{|\$\(/u.test(identity)) {
    inspection.issues.add("identity-unresolved");
    return;
  }
  inspection.identities.add(identity);
}

function inspectPostgresUrl(value) {
  const trimmed = value.trim();
  const scheme = /^postgres(?:ql)?:\/\//iu.exec(trimmed);
  if (!scheme) return null;

  const inspection = emptyInspection();
  inspection.candidate = true;
  const authorityStart = scheme[0].length;
  const firstPathSeparator = trimmed.indexOf("/", authorityStart);
  const possibleUserInfoEnd = trimmed.lastIndexOf("@");
  const userInfoEnd =
    possibleUserInfoEnd >= authorityStart &&
    (firstPathSeparator < 0 || possibleUserInfoEnd < firstPathSeparator)
      ? possibleUserInfoEnd
      : -1;
  let authorityIdentityDeclared = false;
  let credentialContract = "missing";
  if (userInfoEnd >= 0) {
    authorityIdentityDeclared = true;
    const encodedUserInfo = trimmed.slice(authorityStart, userInfoEnd);
    const credentialSeparator = encodedUserInfo.indexOf(":");
    const encodedIdentity =
      credentialSeparator < 0
        ? encodedUserInfo
        : encodedUserInfo.slice(0, credentialSeparator);
    const identity = decodedIdentity(encodedIdentity);
    if (identity === null) inspection.issues.add("identity-unresolved");
    else addLiteralIdentity(inspection, identity);
    if (credentialSeparator >= 0) {
      const credential = decodedIdentity(
        encodedUserInfo.slice(credentialSeparator + 1),
      );
      if (credential === "qa_test_pw") {
        credentialContract = "synthetic-qa";
      } else if (credential !== null && BASE64URL_CREDENTIAL.test(credential)) {
        credentialContract = "resolved-base64url";
        inspection.postgresCredentialFingerprint =
          credentialFingerprint(credential);
      } else if (credential !== null) {
        const match = /^\$\{([A-Z][A-Z0-9_]*):\?\1 is required\}$/u.exec(
          credential,
        );
        credentialContract = match ? `env:${match[1]}` : "invalid";
      } else {
        credentialContract = "invalid";
      }
    }
  }

  // Compose's unresolved `${VAR:?message}` password syntax contains a `?`
  // before the authority terminator. Only query delimiters after userinfo can
  // affect PostgreSQL connection parameters.
  const queryStart = trimmed.indexOf(
    "?",
    userInfoEnd >= 0 ? userInfoEnd + 1 : authorityStart,
  );
  const queryEnd = trimmed.indexOf("#", queryStart < 0 ? 0 : queryStart);
  const query =
    queryStart < 0
      ? ""
      : trimmed.slice(queryStart + 1, queryEnd < 0 ? undefined : queryEnd);
  const queryParameters = new URLSearchParams(query);
  const queryUsers = [];
  let serviceIndirection = false;
  for (const [rawKey, rawValue] of queryParameters.entries()) {
    const key = rawKey.toLowerCase();
    inspection.postgresQueryEntries.push([rawKey, rawValue]);
    if (key === "user") queryUsers.push(rawValue);
    if (key === "options") inspection.postgresOptions.push(rawValue);
    if (key === "service" || key === "servicefile") {
      serviceIndirection = true;
    }
  }
  if (queryUsers.length > 1) {
    inspection.issues.add("identity-duplicate");
  }
  if (authorityIdentityDeclared && queryUsers.length > 0) {
    inspection.issues.add("identity-duplicate");
  }
  for (const identity of queryUsers) addLiteralIdentity(inspection, identity);
  if (serviceIndirection) inspection.issues.add("identity-indirect");
  if (inspection.identities.size === 0) {
    inspection.issues.add("identity-unresolved");
  }
  const hostStart = userInfoEnd >= 0 ? userInfoEnd + 1 : authorityStart;
  const authorityEnd = trimmed.indexOf("/", hostStart);
  inspection.postgresAuthority =
    authorityEnd < 0 ? "" : trimmed.slice(hostStart, authorityEnd);
  const databaseEndCandidates = [queryStart, trimmed.indexOf("#", hostStart)]
    .filter((position) => position >= 0)
    .sort((left, right) => left - right);
  const databaseEnd = databaseEndCandidates[0] ?? trimmed.length;
  const encodedDatabase =
    authorityEnd < 0 ? "" : trimmed.slice(authorityEnd + 1, databaseEnd);
  inspection.postgresDatabase = decodedIdentity(encodedDatabase);
  inspection.postgresFragmentPresent = trimmed.includes("#");
  inspection.postgresCredentialContract = credentialContract;
  return inspection;
}

const LIBPQ_CONNECTION_KEYS = new Set([
  "application_name",
  "channel_binding",
  "client_encoding",
  "connect_timeout",
  "dbname",
  "fallback_application_name",
  "gssencmode",
  "host",
  "hostaddr",
  "keepalives",
  "keepalives_count",
  "keepalives_idle",
  "keepalives_interval",
  "krbsrvname",
  "options",
  "passfile",
  "password",
  "port",
  "requirepeer",
  "service",
  "servicefile",
  "sslcert",
  "sslcrl",
  "sslkey",
  "sslmode",
  "sslrootcert",
  "target_session_attrs",
  "user",
]);

function inspectLibpqDsn(value) {
  const inspection = emptyInspection();
  const userValues = [];
  const tokenPattern =
    /(?:^|[\s;])([a-z_][a-z0-9_]*)\s*=\s*(?:'([^']*)'|"([^"]*)"|([^\s;]+))/giu;
  for (const match of value.matchAll(tokenPattern)) {
    const key = match[1]?.toLowerCase() ?? "";
    if (!LIBPQ_CONNECTION_KEYS.has(key)) continue;
    inspection.candidate = true;
    const tokenValue = match[2] ?? match[3] ?? match[4] ?? "";
    if (key === "user") userValues.push(tokenValue);
    if (key === "service" || key === "servicefile") {
      inspection.issues.add("identity-indirect");
    }
  }
  if (!inspection.candidate) return null;
  if (userValues.length > 1) {
    inspection.issues.add("identity-duplicate");
  }
  for (const identity of userValues) addLiteralIdentity(inspection, identity);
  if (inspection.identities.size === 0) {
    inspection.issues.add("identity-unresolved");
  }
  return inspection;
}

function isPostgresHintKey(key) {
  return /^PG[A-Z0-9_]*$/u.test(key) || /^POSTGRES_[A-Z0-9_]+$/u.test(key);
}

function isPotentialDsnKey(key) {
  return (
    key === "DATABASE_URL" ||
    key === "DIRECT_URL" ||
    key === "SHADOW_DATABASE_URL" ||
    /(?:^|_)(?:DATABASE|POSTGRES|POSTGRESQL|PG)_(?:URL|DSN)(?:_FILE)?$/u.test(
      key,
    )
  );
}

function isDirectDatabaseIdentityKey(key) {
  return (
    key === "PGUSER" ||
    key === "POSTGRES_USER" ||
    (isPostgresHintKey(key) &&
      /(?:^|_)(?:USER|USERNAME|ROLE|LOGIN)$/u.test(key))
  );
}

function isIndirectDatabaseIdentityKey(key) {
  return (
    key === "PGSERVICE" ||
    key === "PGSERVICEFILE" ||
    (isPostgresHintKey(key) &&
      /(?:^|_)(?:USER|USERNAME|ROLE|LOGIN)_FILE$/u.test(key)) ||
    (isPotentialDsnKey(key) && key.endsWith("_FILE"))
  );
}

function inspectDatabaseEnvironment(environment) {
  const inspection = emptyInspection();
  const postgresEnvironment = [];
  for (const [key, rawValue] of Object.entries(environment)) {
    if (typeof rawValue !== "string") {
      if (isPotentialDsnKey(key) || isPostgresHintKey(key)) {
        const unresolved = emptyInspection();
        unresolved.candidate = true;
        unresolved.issues.add("identity-unresolved");
        addMechanism(inspection, "unresolved-value", key, unresolved);
      }
      continue;
    }
    if (rawValue.length === 0) continue;
    const postgresUrl = inspectPostgresUrl(rawValue);
    const libpqDsn = postgresUrl ? null : inspectLibpqDsn(rawValue);
    if (postgresUrl) addMechanism(inspection, "url", key, postgresUrl);
    if (libpqDsn) addMechanism(inspection, "dsn", key, libpqDsn);

    if (isPotentialDsnKey(key) && !postgresUrl && !libpqDsn) {
      const unresolvedDsn = emptyInspection();
      unresolvedDsn.candidate = true;
      unresolvedDsn.issues.add("identity-unresolved");
      addMechanism(inspection, "unresolved-dsn", key, unresolvedDsn);
    }
    if (isPostgresHintKey(key) && !isPotentialDsnKey(key)) {
      postgresEnvironment.push([key, rawValue]);
    }
  }

  if (postgresEnvironment.length > 0) {
    const pgInspection = emptyInspection();
    pgInspection.candidate = true;
    const identityDeclarations = postgresEnvironment.filter(([key]) =>
      isDirectDatabaseIdentityKey(key),
    );
    if (identityDeclarations.length !== 1) {
      pgInspection.issues.add(
        identityDeclarations.length === 0
          ? "identity-unresolved"
          : "identity-duplicate",
      );
    }
    for (const [, value] of identityDeclarations) {
      addLiteralIdentity(pgInspection, value);
    }
    if (
      postgresEnvironment.some(([key]) => isIndirectDatabaseIdentityKey(key))
    ) {
      pgInspection.issues.add("identity-indirect");
    }
    addMechanism(inspection, "pg-env", "PG*", pgInspection);
  }
  if (inspection.candidate && inspection.identities.size === 0) {
    inspection.issues.add("identity-unresolved");
  }
  return inspection;
}

function hasOnlyIdentity(inspection, expected) {
  return (
    inspection.issues.size === 0 &&
    inspection.identities.size === 1 &&
    inspection.identities.has(expected)
  );
}

function hasExactMechanisms(inspection, expected) {
  const actual = [...inspection.mechanisms].sort();
  const reviewed = [...expected].sort();
  return JSON.stringify(actual) === JSON.stringify(reviewed);
}

function exactArray(actual, expected) {
  return (
    Array.isArray(actual) &&
    actual.length === expected.length &&
    actual.every((value, index) => value === expected[index])
  );
}

function hasExactKeys(actual, expected) {
  return (
    actual !== null &&
    typeof actual === "object" &&
    !Array.isArray(actual) &&
    exactArray(Object.keys(actual).sort(), [...expected].sort())
  );
}

function hasExactCanonicalSearchPath(inspection, expectedUrlCount) {
  return (
    inspection.postgresOptionGroups.length === expectedUrlCount &&
    inspection.postgresOptionGroups.every(({ options }) =>
      exactArray(options, [CANONICAL_SEARCH_PATH_OPTION]),
    )
  );
}

function hasExactReviewedPostgresUrls(
  inspection,
  expectedMechanisms,
  expectedLogin,
  qa,
) {
  const expectedKeys = expectedMechanisms.map((mechanism) =>
    mechanism.slice("url:".length),
  );
  const expectedQueryEntries = [
    ["options", CANONICAL_SEARCH_PATH_OPTION],
    ["schema", "public"],
  ];
  const normalizedExpectedQuery = JSON.stringify(
    expectedQueryEntries.sort(([left], [right]) => left.localeCompare(right)),
  );
  const expectedCredentialEnvironment = qa
    ? QA_PASSWORD_ENVIRONMENT_BY_LOGIN.get(expectedLogin)
    : PASSWORD_ENVIRONMENT_BY_LOGIN.get(expectedLogin);
  const expectedCredentialContract =
    qa && expectedLogin === DATABASE_OWNER_LOGIN
      ? "synthetic-qa"
      : staticUnresolved
        ? `env:${expectedCredentialEnvironment ?? ""}`
        : "resolved-base64url";
  const expectedCredentialFingerprint =
    !(qa && expectedLogin === DATABASE_OWNER_LOGIN) && !staticUnresolved
      ? resolvedCredentialFingerprintByLogin.get(expectedLogin)
      : null;
  return (
    expectedCredentialContract !== "env:" &&
    ((qa && expectedLogin === DATABASE_OWNER_LOGIN) ||
      staticUnresolved ||
      expectedCredentialFingerprint !== undefined) &&
    inspection.postgresUrlContracts.length === expectedKeys.length &&
    inspection.postgresUrlContracts.every((contract) => {
      const normalizedActualQuery = JSON.stringify(
        [...contract.queryEntries].sort(
          ([leftKey, leftValue], [rightKey, rightValue]) =>
            leftKey === rightKey
              ? leftValue.localeCompare(rightValue)
              : leftKey.localeCompare(rightKey),
        ),
      );
      return (
        expectedKeys.includes(contract.key) &&
        contract.authority === "postgres:5432" &&
        contract.credentialContract === expectedCredentialContract &&
        ((qa && expectedLogin === DATABASE_OWNER_LOGIN) ||
          staticUnresolved ||
          contract.credentialFingerprint === expectedCredentialFingerprint) &&
        contract.database === (qa ? "meddoc_qa_test" : "meddoc") &&
        contract.fragmentPresent === false &&
        normalizedActualQuery === normalizedExpectedQuery
      );
    })
  );
}

function hasExactEnvFile(service, expected) {
  if (!staticUnresolved) return service?.env_file === undefined;
  if (expected === "absent") return service?.env_file === undefined;
  if (expected === "empty") return exactArray(service?.env_file, []);
  return (
    Array.isArray(service?.env_file) &&
    service.env_file.length === 1 &&
    hasExactKeys(service.env_file[0], ["path", "required"]) &&
    service.env_file[0].path === `${process.cwd()}/.env` &&
    service.env_file[0].required === true
  );
}

function isAbsentAfterComposeNormalization(value) {
  return staticUnresolved ? value === undefined : value === null;
}

function hasExactCommandContract(service, expected) {
  const commandIsExact =
    expected === "absent"
      ? isAbsentAfterComposeNormalization(service?.command)
      : exactArray(service?.command, expected);
  return (
    commandIsExact && isAbsentAfterComposeNormalization(service?.entrypoint)
  );
}

function hasExactOptionalArray(actual, expected) {
  if (expected === "absent") return actual === undefined;
  if (expected === "empty") {
    return staticUnresolved ? actual === null : actual === undefined;
  }
  return exactArray(actual, expected);
}

function isExactNamedVolume(volume, source, target, readOnly) {
  return (
    hasExactKeys(volume, [
      ...(readOnly ? ["read_only"] : []),
      "source",
      "target",
      "type",
      "volume",
    ]) &&
    volume.source === source &&
    volume.target === target &&
    volume.type === "volume" &&
    (readOnly ? volume.read_only === true : volume.read_only === undefined) &&
    hasExactKeys(volume.volume, [])
  );
}

function approvedKeyringPath(qa) {
  const key = qa
    ? "QUILLMD_APPROVED_QA_MFA_SECRET_KEYRING_FILE"
    : "QUILLMD_APPROVED_MFA_SECRET_KEYRING_FILE";
  const value = process.env[key];
  if (typeof value !== "string" || !path.isAbsolute(value)) return null;
  let canonical;
  let metadata;
  try {
    canonical = realpathSync.native(value);
    metadata = statSync(canonical);
  } catch {
    return null;
  }
  if (canonical !== path.normalize(value) || !metadata.isFile()) return null;
  const relative = path.relative(process.cwd(), canonical);
  if (
    relative === "" ||
    (!relative.startsWith("..") && !path.isAbsolute(relative))
  ) {
    return null;
  }
  return canonical;
}

function isExactKeyringMount(volume, qa) {
  const environmentName = qa
    ? "QA_MFA_SECRET_KEYRING_FILE"
    : "MFA_SECRET_KEYRING_FILE";
  const marker = `\${${environmentName}:?${environmentName} is required}`;
  const approved = staticUnresolved ? marker : approvedKeyringPath(qa);
  const source = staticUnresolved ? path.join(process.cwd(), marker) : approved;
  return (
    approved !== null &&
    hasExactKeys(volume, ["bind", "read_only", "source", "target", "type"]) &&
    volume.type === "bind" &&
    volume.read_only === true &&
    volume.source === source &&
    volume.target === approved &&
    (staticUnresolved
      ? hasExactKeys(volume.bind, ["create_host_path"]) &&
        volume.bind.create_host_path === false
      : hasExactKeys(volume.bind, []))
  );
}

function hasExactRuntimeVolumes(service, contract, qa) {
  const volumes = service?.volumes;
  if (contract === "absent") return volumes === undefined;
  if (contract === "empty") {
    return staticUnresolved ? exactArray(volumes, []) : volumes === undefined;
  }
  if (contract === "admin-keyring") {
    return (
      Array.isArray(volumes) &&
      volumes.length === 1 &&
      isExactKeyringMount(volumes[0], qa)
    );
  }
  if (contract === "physician-app" || contract === "qa-physician-app") {
    const socketName =
      contract === "qa-physician-app" ? "qa_clamav_socket" : "clamav_socket";
    return (
      Array.isArray(volumes) &&
      volumes.length === 2 &&
      isExactNamedVolume(
        volumes[0],
        socketName,
        "/var/run/quillmd-clamav",
        true,
      ) &&
      isExactKeyringMount(volumes[1], qa)
    );
  }
  return false;
}

function isDatabaseCredentialEnvironmentKey(key) {
  return (
    DATABASE_CREDENTIAL_ENVIRONMENT_KEYS.includes(key) ||
    /^DB_[A-Z0-9_]*(?:PASSWORD|SECRET|CREDENTIAL|TOKEN|URL|DSN)(?:_FILE)?$/u.test(
      key,
    )
  );
}

function hasExactRuntimeCredentialBoundary(name, environment, expected, qa) {
  if (qa) {
    return !Object.keys(environment).some(isDatabaseCredentialEnvironmentKey);
  }
  const reviewedNonBlank = new Set(
    expected.connectionMechanisms.map((mechanism) =>
      mechanism.slice("url:".length),
    ),
  );
  const requiredBlank = new Set(
    name === "template-twin-audit-dispatcher"
      ? [
          "DB_AUDIT_DISPATCHER_PASSWORD",
          "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
          "DB_BACKUP_PASSWORD_FILE",
          "DB_RELEASE_CONTROL_PASSWORD",
          "DB_RELEASE_SECURITY_PASSWORD",
          "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
        ]
      : DATABASE_CREDENTIAL_ENVIRONMENT_KEYS,
  );
  for (const key of requiredBlank) {
    if (reviewedNonBlank.has(key)) continue;
    if (environment[key] !== "") return false;
  }
  return !Object.entries(environment).some(
    ([key, value]) =>
      isDatabaseCredentialEnvironmentKey(key) &&
      !requiredBlank.has(key) &&
      !reviewedNonBlank.has(key) &&
      value !== "",
  );
}

function expectedReleaseSha() {
  if (staticUnresolved) return "${QUILLMD_RELEASE_SHA:-development}";
  const approved = process.env.QUILLMD_APPROVED_RELEASE_SHA;
  return typeof approved === "string" && /^[a-f0-9]{40}$/u.test(approved)
    ? approved
    : null;
}

function exactFrontendBuildArguments() {
  return {
    NEXT_PUBLIC_MARKETING_URL: staticUnresolved
      ? "${MARKETING_URL:-https://quillmd.com}"
      : "https://quillmd.com",
    NEXT_PUBLIC_SHOW_PIPELINE_TAB: staticUnresolved
      ? "${NEXT_PUBLIC_SHOW_PIPELINE_TAB:-false}"
      : "false",
    NEXT_PUBLIC_SKIN_BETA: staticUnresolved
      ? "${NEXT_PUBLIC_SKIN_BETA:-true}"
      : "true",
    NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL: staticUnresolved
      ? "${TRANSCRIBE_MD_AUTH_URL:-https://app.quillmd.com}"
      : "https://app.quillmd.com",
    NEXT_PUBLIC_ULTRASOUND_SPECIALTY: staticUnresolved
      ? "${NEXT_PUBLIC_ULTRASOUND_SPECIALTY:-false}"
      : "false",
    QUILLMD_RELEASE_SHA: expectedReleaseSha(),
  };
}

function hasExactRuntimeBuildAndImage(name, service) {
  const worker = [
    "transcribe-md-worker",
    "template-twin-audit-dispatcher",
    "auth-email-dispatcher",
  ].includes(name);
  const frontend = [
    "transcribe-md",
    "template-twin-admin-app",
    "template-twin-admin-control",
  ].includes(name);
  const build = service?.build;
  if (!build || typeof build !== "object" || Array.isArray(build)) return false;
  if (name === "meddoc-pro") {
    return (
      hasExactKeys(build, ["context", "dockerfile"]) &&
      build.context === process.cwd() &&
      build.dockerfile === "apps/meddoc-pro/Dockerfile" &&
      service?.image === undefined
    );
  }
  if (!worker && !frontend) return false;
  const expectedArguments = worker
    ? {
        QUILLMD_RELEASE_SHA: expectedReleaseSha(),
      }
    : exactFrontendBuildArguments();
  if (
    !hasExactKeys(build, ["args", "context", "dockerfile"]) ||
    build.context !== process.cwd() ||
    build.dockerfile !==
      (worker
        ? "apps/transcribe-md/Dockerfile.worker"
        : "apps/transcribe-md/Dockerfile") ||
    !hasExactKeys(build.args, Object.keys(expectedArguments)) ||
    !Object.entries(expectedArguments).every(
      ([key, value]) => build.args[key] === value,
    )
  ) {
    return false;
  }
  if (staticUnresolved) {
    return (
      service.image ===
      (worker
        ? "${TRANSCRIBE_MD_WORKER_IMAGE:-meddoc-pro-transcribe-md-worker:latest}"
        : "${TRANSCRIBE_MD_IMAGE:-meddoc-pro-transcribe-md:latest}")
    );
  }
  const approvalKey = worker
    ? "QUILLMD_APPROVED_TRANSCRIBE_MD_WORKER_IMAGE"
    : "QUILLMD_APPROVED_TRANSCRIBE_MD_IMAGE";
  const approved = process.env[approvalKey];
  return (
    typeof approved === "string" &&
    /@sha256:[a-f0-9]{64}$/u.test(approved) &&
    service.image === approved
  );
}

function isExactPortBinding(binding, hostPort, containerPort) {
  return (
    hasExactKeys(binding, [
      "host_ip",
      "mode",
      "protocol",
      "published",
      "target",
    ]) &&
    binding.host_ip === "127.0.0.1" &&
    binding.mode === "ingress" &&
    binding.protocol === "tcp" &&
    binding.published === hostPort &&
    binding.target === containerPort
  );
}

function hasExactRuntimePorts(name, ports) {
  if (name === "meddoc-pro") {
    return (
      Array.isArray(ports) &&
      ports.length === 1 &&
      isExactPortBinding(ports[0], "3001", 3000)
    );
  }
  if (name === "transcribe-md") {
    return (
      Array.isArray(ports) &&
      ports.length === 1 &&
      isExactPortBinding(ports[0], "3011", 3011)
    );
  }
  if (name === "template-twin-admin-app") {
    return staticUnresolved ? exactArray(ports, []) : ports === undefined;
  }
  if (name === "template-twin-admin-control") {
    return staticUnresolved
      ? exactArray(ports, [
          "127.0.0.1:${TEMPLATE_TWIN_ADMIN_CONTROL_PORT:-3012}:3011",
        ])
      : Array.isArray(ports) &&
          ports.length === 1 &&
          isExactPortBinding(ports[0], "3012", 3011);
  }
  return ports === undefined;
}

function hasExactRuntimeNetworks(name, networks) {
  const expected = {
    "meddoc-pro": { default: null, quillmd_ingress: null },
    "transcribe-md": { default: null, quillmd_ingress: null },
    "template-twin-admin-app": { default: null, quillmd_ingress: null },
    "template-twin-admin-control": { default: null, quillmd_ingress: null },
    "transcribe-md-worker": { default: null },
    "template-twin-audit-dispatcher": { default: null },
    "auth-email-dispatcher": {
      auth_email_database: {},
      auth_email_egress: { gw_priority: 1 },
    },
  }[name];
  return JSON.stringify(networks) === JSON.stringify(expected);
}

function expectedRuntimeHealthcheck(name) {
  const endpoint = {
    "meddoc-pro": "http://127.0.0.1:3000/api/health",
    "transcribe-md": "http://127.0.0.1:3011/api/health",
    "template-twin-admin-app":
      "http://127.0.0.1:3011/api/health/template-twin-admin-app",
    "template-twin-admin-control":
      "http://127.0.0.1:3011/api/admin/template-twin/control-health",
  }[name];
  if (endpoint) {
    return {
      interval: "30s",
      retries: 3,
      start_period: "30s",
      test: ["CMD", "wget", "-qO-", "--spider", endpoint],
      timeout: "5s",
    };
  }
  const command = {
    "transcribe-md-worker": staticUnresolved
      ? "test -f /tmp/worker-heartbeat && [ $(( $(date +%s) - $(stat -c %Y /tmp/worker-heartbeat) )) -lt 60 ]"
      : "test -f /tmp/worker-heartbeat && [ $$(( $$(date +%s) - $$(stat -c %Y /tmp/worker-heartbeat) )) -lt 60 ]",
    "template-twin-audit-dispatcher":
      "test -f /tmp/template-twin-audit-dispatcher-heartbeat && [ $$(( $$(date +%s) - $$(stat -c %Y /tmp/template-twin-audit-dispatcher-heartbeat) )) -lt 90 ]",
    "auth-email-dispatcher":
      "test -f /tmp/auth-email-dispatcher-heartbeat && [ $$(( $$(date +%s) - $$(stat -c %Y /tmp/auth-email-dispatcher-heartbeat) )) -lt 90 ]",
  }[name];
  return {
    interval: "30s",
    retries: 3,
    start_period: staticUnresolved ? "60s" : "1m0s",
    test: ["CMD-SHELL", command],
    timeout: "5s",
  };
}

function hasExactRuntimeHealthcheck(name, actual) {
  const expected = expectedRuntimeHealthcheck(name);
  return (
    hasExactKeys(actual, [
      "interval",
      "retries",
      "start_period",
      "test",
      "timeout",
    ]) &&
    actual.interval === expected.interval &&
    actual.retries === expected.retries &&
    actual.start_period === expected.start_period &&
    exactArray(actual.test, expected.test) &&
    actual.timeout === expected.timeout
  );
}

function hasExactQaRuntimeImage(name, service) {
  if (service?.build !== undefined) return false;
  const worker = name === "transcribe-md-worker";
  if (staticUnresolved) {
    return (
      service?.image ===
      (worker
        ? "${QA_TRANSCRIBE_MD_WORKER_IMAGE:-meddoc-pro-transcribe-md-worker:latest}"
        : "${QA_TRANSCRIBE_MD_IMAGE:-meddoc-pro-transcribe-md:latest}")
    );
  }
  const approvalKey = worker
    ? "QUILLMD_APPROVED_QA_TRANSCRIBE_MD_WORKER_IMAGE"
    : "QUILLMD_APPROVED_QA_TRANSCRIBE_MD_IMAGE";
  const approved = process.env[approvalKey];
  return (
    typeof approved === "string" &&
    /@sha256:[a-f0-9]{64}$/u.test(approved) &&
    service?.image === approved
  );
}

function qaRuntimeSurfaceIssue(name, service) {
  const worker = name === "transcribe-md-worker";
  if (
    service?.restart !== "no" ||
    service?.profiles !== undefined ||
    service?.hostname !== undefined ||
    service?.container_name !== undefined
  ) {
    return "restart, profile, or container identity";
  }
  if (!hasExactQaRuntimeImage(name, service)) return "image";
  if (
    service?.cpus !== (staticUnresolved ? "1.0" : 1) ||
    service?.mem_limit !==
      (staticUnresolved
        ? worker
          ? "1g"
          : "512m"
        : worker
          ? "1073741824"
          : "536870912")
  ) {
    return "resource limits";
  }
  if (JSON.stringify(service?.networks) !== JSON.stringify({ default: null })) {
    return "networks";
  }
  if (
    !(worker
      ? service?.ports === undefined
      : Array.isArray(service?.ports) &&
        service.ports.length === 1 &&
        isExactPortBinding(service.ports[0], "9020", 3011))
  ) {
    return "ports";
  }
  if (
    !(worker
      ? hasExactRuntimeHealthcheck(name, service?.healthcheck)
      : hasExactKeys(service?.healthcheck, [
          "interval",
          "retries",
          "start_period",
          "test",
          "timeout",
        ]) &&
        exactArray(service.healthcheck.test, [
          "CMD",
          "wget",
          "-qO-",
          "--spider",
          "http://127.0.0.1:3011/api/health",
        ]) &&
        service.healthcheck.interval === "15s" &&
        service.healthcheck.retries === 10 &&
        service.healthcheck.start_period === "30s" &&
        service.healthcheck.timeout === "5s")
  ) {
    return "healthcheck";
  }
  if (
    service?.read_only !== undefined ||
    service?.tmpfs !== undefined ||
    service?.stop_grace_period !== undefined
  ) {
    return "filesystem surface";
  }
  return null;
}

function runtimeSurfaceIssue(name, service, qa) {
  if (qa) return qaRuntimeSurfaceIssue(name, service);
  const dispatcher = [
    "template-twin-audit-dispatcher",
    "auth-email-dispatcher",
  ].includes(name);
  if (
    service?.restart !== "unless-stopped" ||
    service?.profiles !== undefined
  ) {
    return "restart or profile";
  }
  if (
    service?.hostname !== undefined ||
    service?.container_name !== undefined
  ) {
    return "container identity";
  }
  if (!hasExactRuntimeBuildAndImage(name, service)) return "build or image";
  if (!hasExactRuntimePorts(name, service?.ports)) return "ports";
  if (!hasExactRuntimeNetworks(name, service?.networks)) return "networks";
  if (!hasExactRuntimeHealthcheck(name, service?.healthcheck)) {
    return "healthcheck";
  }
  if (
    !(dispatcher
      ? service.read_only === true &&
        exactArray(service.tmpfs, [
          "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
        ]) &&
        service.stop_grace_period === "45s"
      : service.read_only === undefined &&
        service.tmpfs === undefined &&
        service.stop_grace_period === undefined)
  ) {
    return "filesystem surface";
  }
  return null;
}

function runtimeAuthorityIssue(name, service, expected, qa) {
  const environment = service?.environment ?? {};
  if (service?.user !== undefined) return "user override";
  if (!exactArray(service?.cap_drop, ["ALL"])) {
    return "capability drop";
  }
  if (
    service?.use_api_socket !== undefined ||
    service?.post_start !== undefined ||
    service?.pre_stop !== undefined ||
    service?.sysctls !== undefined ||
    service?.secrets !== undefined ||
    service?.configs !== undefined
  ) {
    return "delegated authority";
  }
  if (!hasExactOptionalArray(service?.group_add, expected.groupAdd)) {
    return "supplemental groups";
  }
  if (!hasExactOptionalArray(service?.security_opt, expected.securityOpt)) {
    return "security options";
  }
  if (!hasExactCommandContract(service, expected.command)) {
    return "process command";
  }
  if (!hasExactRuntimeVolumes(service, expected.volumes, qa)) {
    return "volume mounts";
  }
  if (!hasExactRuntimeCredentialBoundary(name, environment, expected, qa)) {
    return "credential suppression";
  }
  const surfaceIssue = runtimeSurfaceIssue(name, service, qa);
  if (surfaceIssue !== null) {
    return `runtime surface ${surfaceIssue}`;
  }
  return null;
}

function databaseMaterialIsAllowedAt(name, keyPath, qa) {
  const pathKey = keyPath.join(".");
  const expected = (qa ? qaServices : productionServices).get(name);
  if (
    expected?.connectionMechanisms.some(
      (mechanism) =>
        pathKey === `environment.${mechanism.slice("url:".length)}`,
    )
  ) {
    return true;
  }
  if (name === "db-migrate" && pathKey === "environment.DATABASE_URL") {
    return true;
  }
  if (name === "postgres" && keyPath[0] === "environment") {
    return [
      "POSTGRES_PASSWORD",
      "DB_RUNTIME_PASSWORD",
      "DB_RELEASE_CONTROL_PASSWORD",
      "DB_AUDIT_DISPATCHER_PASSWORD",
      "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
    ].includes(keyPath[1]);
  }
  return false;
}

function containsResolvedReviewedCredential(value) {
  if (staticUnresolved || resolvedCredentialFingerprintByLogin.size === 0) {
    return false;
  }
  const fingerprints = new Set(resolvedCredentialFingerprintByLogin.values());
  for (const match of value.matchAll(/[A-Za-z0-9_-]{43,128}/gu)) {
    if (fingerprints.has(credentialFingerprint(match[0]))) return true;
  }
  return false;
}

function containsDatabaseMaterial(value) {
  return (
    /postgres(?:ql)?:\/\//iu.test(value) ||
    inspectLibpqDsn(value) !== null ||
    /\$(?:\{)?DB_[A-Z0-9_]*(?:PASSWORD|SECRET|CREDENTIAL|TOKEN)(?:[^A-Z0-9_]|$)/u.test(
      value,
    ) ||
    /\$(?:\{)?(?:DATABASE_URL|DIRECT_URL|SHADOW_DATABASE_URL|PGPASSWORD|PGUSER|PGHOST|PGDATABASE|PGSERVICE)(?:[^A-Z0-9_]|$)/u.test(
      value,
    ) ||
    containsResolvedReviewedCredential(value)
  );
}

function assertDatabaseMaterialLocations(name, service, qa) {
  const visit = (value, keyPath) => {
    if (typeof value === "string") {
      if (
        containsDatabaseMaterial(value) &&
        !databaseMaterialIsAllowedAt(name, keyPath, qa)
      ) {
        fail(
          `P1 pre-production blocker: ${name} contains database connection material outside reviewed environment locations`,
        );
      }
      return;
    }
    if (value === null || typeof value !== "object") return;
    for (const [key, nested] of Object.entries(value)) {
      visit(nested, [...keyPath, key]);
    }
  };
  visit(service, []);
}

function normalizedResourceConsumers(values) {
  return [...values].map((value) => JSON.stringify(value)).sort();
}

function hasExactPostgresHostAuthenticationSources() {
  const contracts = [
    [
      path.join(process.cwd(), POSTGRES_DOCKERIGNORE),
      POSTGRES_DOCKERIGNORE_SHA256,
      false,
    ],
    [
      path.join(process.cwd(), POSTGRES_DOCKERFILE),
      POSTGRES_DOCKERFILE_SHA256,
      false,
    ],
    [
      path.join(process.cwd(), "infra/postgres/quillmd-pg_hba.conf"),
      POSTGRES_HBA_SHA256,
      false,
    ],
    [
      path.join(process.cwd(), "infra/postgres/verify-quillmd-host-auth.sh"),
      POSTGRES_HBA_VERIFIER_SHA256,
      true,
    ],
    [
      path.join(process.cwd(), POSTGRES_ENTRYPOINT_SOURCE),
      POSTGRES_ENTRYPOINT_SHA256,
      false,
    ],
  ];
  try {
    return contracts.every(([source, expectedSha256, executable]) => {
      const metadata = statSync(source);
      return (
        metadata.isFile() &&
        realpathSync(source) === source &&
        (!executable || (metadata.mode & 0o111) !== 0) &&
        createHash("sha256").update(readFileSync(source)).digest("hex") ===
          expectedSha256
      );
    });
  } catch {
    return false;
  }
}

function hasExactQaPostgresBuild(build) {
  return (
    hasExactKeys(build, ["context", "dockerfile"]) &&
    build.context === path.join(process.cwd(), "infra/postgres") &&
    build.dockerfile === "Dockerfile"
  );
}

function hasExactProductionPostgresImage(image) {
  if (staticUnresolved) return image === STATIC_POSTGRES_IMAGE;
  const approved = process.env[APPROVED_POSTGRES_IMAGE_ENVIRONMENT];
  return (
    typeof approved === "string" &&
    approved !== POSTGRES_BASE_IMAGE &&
    /@sha256:[a-f0-9]{64}$/u.test(approved) &&
    image === approved
  );
}

function hasExactQaPostgresImage(image) {
  if (staticUnresolved) return image === STATIC_QA_POSTGRES_IMAGE;
  const approved = process.env[APPROVED_QA_POSTGRES_IMAGE_ENVIRONMENT];
  return (
    typeof approved === "string" &&
    /^sha256:[a-f0-9]{64}$/u.test(approved) &&
    image === approved
  );
}

function hasExactNetworkResource(resource, key, qa, projectName) {
  if (!resource || typeof resource !== "object" || Array.isArray(resource)) {
    return false;
  }
  const internal =
    !qa && ["auth_email_database", "backup_database"].includes(key);
  const ingress = !qa && key === "quillmd_ingress";
  const bridge =
    ingress ||
    key === "template_twin_scanner" ||
    (!qa && key === "auth_email_egress");
  const expectedKeys = [
    ...(bridge ? ["driver"] : []),
    ...(internal ? ["internal"] : []),
    ...(ingress || !staticUnresolved ? ["ipam"] : []),
    "name",
  ];
  if (!hasExactKeys(resource, expectedKeys)) return false;
  if (resource.name !== `${projectName}_${key}`) return false;
  if (bridge && resource.driver !== "bridge") return false;
  if (internal && resource.internal !== true) return false;
  if (ingress) {
    return (
      hasExactKeys(resource.ipam, ["config"]) &&
      Array.isArray(resource.ipam.config) &&
      resource.ipam.config.length === 1 &&
      hasExactKeys(resource.ipam.config[0], ["gateway", "subnet"]) &&
      resource.ipam.config[0].gateway === "172.31.252.1" &&
      resource.ipam.config[0].subnet === "172.31.252.0/24"
    );
  }
  return staticUnresolved || hasExactKeys(resource.ipam, []);
}

function assertExactNamedResources(model, services, qa) {
  const volumeContracts = new Map(
    [...(qa ? QA_VOLUME_CONSUMERS : PRODUCTION_VOLUME_CONSUMERS)].filter(
      ([key]) => qa || staticUnresolved || key !== "pgdata",
    ),
  );
  const networkContracts = qa
    ? QA_NETWORK_CONSUMERS
    : PRODUCTION_NETWORK_CONSUMERS;
  const projectName = model?.name;
  if (
    typeof projectName !== "string" ||
    projectName.length === 0 ||
    projectName !== (qa ? "meddoc-qa" : "meddoc-pro")
  ) {
    fail("P1 pre-production blocker: Compose project identity drifted");
  }
  if (!hasExactKeys(model?.volumes, [...volumeContracts.keys()])) {
    fail(
      `P1 pre-production blocker: ${qa ? "QA " : ""}named volume resource set drifted`,
    );
  }
  for (const key of volumeContracts.keys()) {
    const resource = model.volumes[key];
    if (
      !hasExactKeys(resource, ["name"]) ||
      resource.name !== `${projectName}_${key}`
    ) {
      fail(
        `P1 pre-production blocker: ${qa ? "QA " : ""}named volume resource shape drifted`,
      );
    }
  }
  if (!hasExactKeys(model?.networks, [...networkContracts.keys()])) {
    fail(
      `P1 pre-production blocker: ${qa ? "QA " : ""}network resource set drifted`,
    );
  }
  for (const key of networkContracts.keys()) {
    if (!hasExactNetworkResource(model.networks[key], key, qa, projectName)) {
      fail(
        `P1 pre-production blocker: ${qa ? "QA " : ""}${key} network resource shape drifted`,
      );
    }
  }
  if (!qa) {
    if (
      model?.secrets?.postgres_backup_password?.name !==
      `${projectName}_postgres_backup_password`
    ) {
      fail(
        "P1 pre-production blocker: production secret resource identity drifted",
      );
    }
  } else {
    const secret = model?.secrets?.qa_postgres_backup_password;
    const expectedFile = staticUnresolved
      ? `${process.cwd()}/\${QA_DB_BACKUP_PASSWORD_FILE:?QA_DB_BACKUP_PASSWORD_FILE is required}`
      : process.env.QUILLMD_APPROVED_QA_DB_BACKUP_PASSWORD_FILE;
    if (
      !hasExactKeys(model?.secrets, ["qa_postgres_backup_password"]) ||
      !hasExactKeys(secret, ["file", "name"]) ||
      secret.name !== `${projectName}_qa_postgres_backup_password` ||
      typeof expectedFile !== "string" ||
      !path.isAbsolute(expectedFile) ||
      secret.file !== expectedFile
    ) {
      fail("P1 pre-production blocker: QA bootstrap secret resource drifted");
    }
  }
  if (Object.keys(model?.configs ?? {}).length > 0) {
    fail("P1 pre-production blocker: unreviewed Compose config resource");
  }

  const actualVolumes = new Map(
    [...volumeContracts.keys()].map((key) => [key, []]),
  );
  const actualNetworks = new Map(
    [...networkContracts.keys()].map((key) => [key, []]),
  );
  const keyringConsumers = [];
  const qaBootstrapSecretConsumers = [];
  const qaPrincipalInitConsumers = [];
  const qaPrincipalInitSource = `${process.cwd()}/infra/postgres/init-template-twin-roles.sh`;
  const qaPrincipalInitTarget =
    "/docker-entrypoint-initdb.d/20-quillmd-exact-principals.sh";
  const keyringMarker = staticUnresolved
    ? `\${${qa ? "QA_MFA_SECRET_KEYRING_FILE" : "MFA_SECRET_KEYRING_FILE"}:?${qa ? "QA_MFA_SECRET_KEYRING_FILE" : "MFA_SECRET_KEYRING_FILE"} is required}`
    : approvedKeyringPath(qa);
  for (const [name, service] of Object.entries(services)) {
    const networks = service?.networks;
    if (networks !== undefined) {
      if (
        networks === null ||
        typeof networks !== "object" ||
        Array.isArray(networks)
      ) {
        fail(
          `P1 pre-production blocker: ${name} has an unreviewed network attachment`,
        );
      }
      for (const [network, attachment] of Object.entries(networks)) {
        if (!actualNetworks.has(network)) {
          fail(
            `P1 pre-production blocker: ${name} has an unreviewed network attachment`,
          );
        }
        if (
          attachment !== null &&
          !(
            name === "auth-email-dispatcher" &&
            network === "auth_email_database" &&
            hasExactKeys(attachment, [])
          ) &&
          !(
            name === "auth-email-dispatcher" &&
            network === "auth_email_egress" &&
            hasExactKeys(attachment, ["gw_priority"]) &&
            attachment.gw_priority === 1
          )
        ) {
          fail(
            `P1 pre-production blocker: ${name} has an unreviewed network attachment`,
          );
        }
        actualNetworks.get(network).push(name);
      }
    }
    if (qa) {
      for (const secret of Array.isArray(service?.secrets)
        ? service.secrets
        : []) {
        if (
          !hasExactKeys(secret, ["source", "target"]) ||
          secret.source !== "qa_postgres_backup_password" ||
          secret.target !== "/run/secrets/qa_postgres_backup_password"
        ) {
          fail(
            `P1 pre-production blocker: ${name} has an unreviewed QA secret mount`,
          );
        }
        qaBootstrapSecretConsumers.push(name);
      }
    }
    for (const volume of Array.isArray(service?.volumes)
      ? service.volumes
      : []) {
      if (volume?.type === "volume" && actualVolumes.has(volume?.source)) {
        actualVolumes
          .get(volume.source)
          .push([name, volume.target, volume.read_only === true]);
      }
      if (
        keyringMarker !== null &&
        (volume?.source === keyringMarker || volume?.target === keyringMarker)
      ) {
        keyringConsumers.push(name);
      }
      if (
        qa &&
        (volume?.source === qaPrincipalInitSource ||
          volume?.target === qaPrincipalInitTarget)
      ) {
        if (
          !isExactBindMount(
            volume,
            qaPrincipalInitSource,
            qaPrincipalInitTarget,
            true,
          )
        ) {
          fail(
            `P1 pre-production blocker: ${name} has an invalid QA principal-init mount`,
          );
        }
        qaPrincipalInitConsumers.push(name);
      }
    }
  }
  for (const [key, expected] of volumeContracts) {
    if (
      JSON.stringify(normalizedResourceConsumers(actualVolumes.get(key))) !==
      JSON.stringify(normalizedResourceConsumers(expected))
    ) {
      fail(
        `P1 pre-production blocker: ${key} named volume consumer census drifted`,
      );
    }
  }
  for (const [key, expected] of networkContracts) {
    if (
      !exactArray(
        [...new Set(actualNetworks.get(key))].sort(),
        [...expected].sort(),
      )
    ) {
      fail(`P1 pre-production blocker: ${key} network consumer census drifted`);
    }
  }
  const expectedKeyringConsumers = qa
    ? ["transcribe-md"]
    : ["template-twin-admin-app", "transcribe-md"];
  if (
    !exactArray([...new Set(keyringConsumers)].sort(), expectedKeyringConsumers)
  ) {
    fail("P1 pre-production blocker: MFA keyring consumer census drifted");
  }
  if (
    qa &&
    (!exactArray([...new Set(qaBootstrapSecretConsumers)].sort(), [
      "postgres",
    ]) ||
      !exactArray([...new Set(qaPrincipalInitConsumers)].sort(), ["postgres"]))
  ) {
    fail("P1 pre-production blocker: QA principal bootstrap census drifted");
  }
}

function hasExactBackupSecretMounts(actual) {
  return (
    Array.isArray(actual) &&
    actual.length === 1 &&
    hasExactKeys(actual[0], ["source", "target"]) &&
    actual[0].source === "postgres_backup_password" &&
    actual[0].target === "/run/secrets/postgres_backup_password"
  );
}

function hasExactBackupNetwork(network) {
  return (
    hasExactKeys(
      network,
      staticUnresolved ? ["internal", "name"] : ["internal", "ipam", "name"],
    ) &&
    network.internal === true &&
    typeof network.name === "string" &&
    network.name.endsWith("_backup_database") &&
    (staticUnresolved || hasExactKeys(network.ipam, []))
  );
}

function hasExactBackupVolume(volume, expected) {
  if (!volume || typeof volume !== "object" || Array.isArray(volume)) {
    return false;
  }
  if (expected === "archive") {
    return (
      hasExactKeys(volume, ["source", "target", "type", "volume"]) &&
      volume.source === "pgbackups" &&
      volume.target === "/backups" &&
      volume.type === "volume" &&
      hasExactKeys(volume.volume, [])
    );
  }
  return (
    hasExactKeys(volume, ["bind", "read_only", "source", "target", "type"]) &&
    volume.type === "bind" &&
    volume.read_only === true &&
    volume.source === `${process.cwd()}/infra/postgres-backup/hooks` &&
    volume.target === "/hooks" &&
    hasExactKeys(volume.bind, ["create_host_path"]) &&
    volume.bind.create_host_path === true
  );
}

function hasExactBackupProvisioning(model, services) {
  const postgres = services.postgres;
  const environment = postgres?.environment ?? {};
  const provisionerMounts = Array.isArray(postgres?.volumes)
    ? postgres.volumes.filter(
        (volume) =>
          volume?.type === "bind" &&
          volume?.target ===
            "/opt/quillmd/provision-postgres-backup-principal.sh",
      )
    : [];
  const exactProvisionerMount =
    provisionerMounts.length === 1 &&
    hasExactKeys(provisionerMounts[0], [
      "bind",
      "read_only",
      "source",
      "target",
      "type",
    ]) &&
    provisionerMounts[0].type === "bind" &&
    provisionerMounts[0].read_only === true &&
    provisionerMounts[0].source ===
      `${process.cwd()}/infra/postgres/provision-postgres-backup-principal.sh` &&
    hasExactKeys(provisionerMounts[0].bind, ["create_host_path"]) &&
    provisionerMounts[0].bind.create_host_path === true;
  const postgresSecrets = postgres?.secrets;
  const postgresNetworks = postgres?.networks;
  const secret = model?.secrets?.postgres_backup_password;
  const network = model?.networks?.backup_database;
  const backupVolume = model?.volumes?.pgbackups;
  return (
    environment.DB_BACKUP_PASSWORD_FILE ===
      "/run/secrets/postgres_backup_password" &&
    exactProvisionerMount &&
    exactArray(postgres?.cap_drop, ["ALL"]) &&
    postgres?.user === "999:999" &&
    hasExactBackupSecretMounts(postgresSecrets) &&
    postgresNetworks !== null &&
    typeof postgresNetworks === "object" &&
    !Array.isArray(postgresNetworks) &&
    postgresNetworks.backup_database === null &&
    hasExactKeys(secret, ["file", "name"]) &&
    typeof secret.file === "string" &&
    (staticUnresolved
      ? secret.file ===
        `${process.cwd()}/\${DB_BACKUP_PASSWORD_FILE:?DB_BACKUP_PASSWORD_FILE is required}`
      : typeof process.env.QUILLMD_APPROVED_DB_BACKUP_PASSWORD_FILE ===
          "string" &&
        process.env.QUILLMD_APPROVED_DB_BACKUP_PASSWORD_FILE.startsWith("/") &&
        secret.file === process.env.QUILLMD_APPROVED_DB_BACKUP_PASSWORD_FILE) &&
    typeof secret.name === "string" &&
    secret.name.endsWith("_postgres_backup_password") &&
    hasExactBackupNetwork(network) &&
    hasExactKeys(backupVolume, ["name"]) &&
    typeof backupVolume.name === "string" &&
    backupVolume.name.endsWith("_pgbackups")
  );
}

function isExactBackupRuntime(name, service, inspection, model, services) {
  const environment = service?.environment ?? {};
  const expectedEnvironment = {
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
    POSTGRES_USER: BACKUP_LOGIN,
    SCHEDULE: "@daily",
  };
  const volumes = service?.volumes;
  return (
    name === "postgres-backup" &&
    hasExactKeys(service, [
      "cap_drop",
      ...(!staticUnresolved ? ["command", "entrypoint"] : []),
      "cpus",
      "depends_on",
      "environment",
      "healthcheck",
      "image",
      "mem_limit",
      "networks",
      "profiles",
      "restart",
      "secrets",
      "user",
      "volumes",
    ]) &&
    (staticUnresolved ||
      (service.command === null && service.entrypoint === null)) &&
    service.image === BACKUP_IMAGE &&
    exactArray(service.profiles, ["backup-ops-approved"]) &&
    service.restart === "unless-stopped" &&
    service.user === "999:999" &&
    exactArray(service.cap_drop, ["ALL"]) &&
    service.cpus === (staticUnresolved ? "0.5" : 0.5) &&
    service.mem_limit === (staticUnresolved ? "128m" : "134217728") &&
    hasExactKeys(environment, Object.keys(expectedEnvironment)) &&
    Object.entries(expectedEnvironment).every(
      ([key, value]) => environment[key] === value,
    ) &&
    environment.QUILLMD_SERVICE_ROLE === undefined &&
    environment[PROFILE_ENVIRONMENT] === undefined &&
    hasOnlyIdentity(inspection, BACKUP_LOGIN) &&
    hasExactMechanisms(inspection, ["pg-env:PG*"]) &&
    hasExactKeys(service.depends_on, ["postgres"]) &&
    hasExactKeys(service.depends_on.postgres, ["condition", "required"]) &&
    service.depends_on.postgres.condition === "service_healthy" &&
    service.depends_on.postgres.required === true &&
    hasExactKeys(service.networks, ["backup_database"]) &&
    service.networks.backup_database === null &&
    hasExactBackupSecretMounts(service.secrets) &&
    Array.isArray(volumes) &&
    volumes.length === 2 &&
    hasExactBackupVolume(volumes[0], "archive") &&
    hasExactBackupVolume(volumes[1], "hooks") &&
    hasExactKeys(service.healthcheck, [
      "interval",
      "retries",
      "start_period",
      "test",
      "timeout",
    ]) &&
    exactArray(service.healthcheck.test, [
      "CMD",
      "curl",
      "-fsS",
      "http://127.0.0.1:8080",
    ]) &&
    service.healthcheck.interval === (staticUnresolved ? "60s" : "1m0s") &&
    service.healthcheck.retries === 3 &&
    service.healthcheck.start_period === "10s" &&
    service.healthcheck.timeout === "5s" &&
    hasExactBackupProvisioning(model, services)
  );
}

function assertExclusiveBackupResources(model, services, qa) {
  if (qa) {
    if (
      model?.secrets?.postgres_backup_password !== undefined ||
      model?.networks?.backup_database !== undefined ||
      model?.volumes?.pgbackups !== undefined
    ) {
      fail(
        "P1 pre-production blocker: QA contains production backup resources",
      );
    }
  } else if (!hasExactKeys(model?.secrets, ["postgres_backup_password"])) {
    fail("P1 pre-production blocker: backup secret resource set drifted");
  }
  if (Object.keys(model?.configs ?? {}).length > 0) {
    fail("P1 pre-production blocker: unreviewed Compose config resource");
  }

  const approvedSecret = qa
    ? model?.secrets?.qa_postgres_backup_password
    : model?.secrets?.postgres_backup_password;
  const approvedNetwork = model?.networks?.backup_database;
  const approvedVolume = model?.volumes?.pgbackups;
  const canonicalPath = (value) => {
    if (typeof value !== "string") return null;
    const resolved = path.resolve(value);
    try {
      return realpathSync.native(resolved);
    } catch {
      return resolved;
    }
  };
  const sameFile = (candidate, approved) =>
    canonicalPath(candidate) !== null &&
    canonicalPath(candidate) === canonicalPath(approved);
  const sourceContainsFile = (source, protectedFile) => {
    const canonicalSource = canonicalPath(source);
    const canonicalProtected = canonicalPath(protectedFile);
    if (canonicalSource === null || canonicalProtected === null) {
      return false;
    }
    const relative = path.relative(canonicalSource, canonicalProtected);
    return (
      relative === "" ||
      (!relative.startsWith("..") && !path.isAbsolute(relative))
    );
  };
  const pathsOverlap = (left, right) =>
    sourceContainsFile(left, right) || sourceContainsFile(right, left);
  const repositoryEnvironmentFile = path.resolve(process.cwd(), ".env");
  const primaryDatabaseDataRoot = "/mnt/pgdata-encrypted";
  const protectedContainerDataRoots = [
    "/var/lib/containerd",
    "/var/lib/containers",
    "/var/lib/docker",
  ];
  const protectedRuntimeSockets = [
    "/run/containerd/containerd.sock",
    "/run/docker.sock",
    "/run/podman/podman.sock",
    "/var/run/containerd/containerd.sock",
    "/var/run/docker.sock",
    "/var/run/podman/podman.sock",
  ];
  if (
    !staticUnresolved &&
    (sameFile(approvedSecret?.file, repositoryEnvironmentFile) ||
      sourceContainsFile(process.cwd(), approvedSecret?.file))
  ) {
    fail(
      "P1 pre-production blocker: resolved database secret source is inside the repository",
    );
  }
  if (!qa) {
    const networkAliases = Object.entries(model?.networks ?? {})
      .filter(
        ([, resource]) =>
          typeof approvedNetwork?.name === "string" &&
          resource?.name === approvedNetwork.name,
      )
      .map(([key]) => key);
    const volumeAliases = Object.entries(model?.volumes ?? {})
      .filter(
        ([, resource]) =>
          typeof approvedVolume?.name === "string" &&
          resource?.name === approvedVolume.name,
      )
      .map(([key]) => key);
    if (!exactArray(networkAliases, ["backup_database"])) {
      fail("P1 pre-production blocker: backup network has a physical alias");
    }
    if (!exactArray(volumeAliases, ["pgbackups"])) {
      fail("P1 pre-production blocker: backup archive has a physical alias");
    }
  }

  const consumers = {
    network: [],
    secret: [],
    archive: [],
    hook: [],
    provisioner: [],
  };
  for (const [name, service] of Object.entries(services)) {
    const capAdd = Array.isArray(service?.cap_add) ? service.cap_add : [];
    const exactScannerCapabilities =
      name === "template-twin-clamav" &&
      exactArray(capAdd, [
        "CHOWN",
        "DAC_OVERRIDE",
        "FOWNER",
        "SETGID",
        "SETUID",
      ]);
    const exactIngressCapabilities =
      name === "caddy" && exactArray(capAdd, ["NET_BIND_SERVICE"]);
    const exactSecurityOptions =
      ["template-twin-audit-dispatcher", "auth-email-dispatcher"].includes(
        name,
      ) && exactArray(service?.security_opt, ["no-new-privileges:true"]);
    const exactSupplementalGroups =
      name === "transcribe-md"
        ? exactArray(service?.group_add, ["101", "1001"])
        : name === "template-twin-admin-app"
          ? exactArray(service?.group_add, ["1001"])
          : name === "template-twin-admin-control" && staticUnresolved
            ? service?.group_add === null
            : service?.group_add === undefined;
    if (
      service?.privileged === true ||
      ["0", "0:0", "root", "root:root"].includes(service?.user) ||
      (capAdd.length > 0 &&
        !exactScannerCapabilities &&
        !exactIngressCapabilities) ||
      (Array.isArray(service?.devices) && service.devices.length > 0) ||
      (Array.isArray(service?.device_cgroup_rules) &&
        service.device_cgroup_rules.length > 0) ||
      service?.pid !== undefined ||
      service?.ipc !== undefined ||
      service?.uts !== undefined ||
      service?.userns_mode !== undefined ||
      service?.use_api_socket !== undefined ||
      service?.post_start !== undefined ||
      service?.pre_stop !== undefined ||
      service?.sysctls !== undefined ||
      (service?.security_opt !== undefined && !exactSecurityOptions) ||
      (service?.group_add !== undefined && !exactSupplementalGroups)
    ) {
      fail(
        `P1 pre-production blocker: ${name} has unreviewed container authority`,
      );
    }
    const networks = service?.networks;
    if (
      networks !== null &&
      typeof networks === "object" &&
      !Array.isArray(networks) &&
      Object.prototype.hasOwnProperty.call(networks, "backup_database")
    ) {
      consumers.network.push(name);
    }
    const exactMigrationNetworkNamespace =
      name === "db-migrate" &&
      service?.network_mode === "service:postgres" &&
      isExactSegmentedMigrator(name, service, qa);
    if (
      (service?.network_mode !== undefined &&
        !exactMigrationNetworkNamespace) ||
      service?.volumes_from !== undefined ||
      service?.extra_hosts !== undefined ||
      service?.links !== undefined ||
      service?.external_links !== undefined
    ) {
      fail(
        `P1 pre-production blocker: ${name} uses unreviewed namespace or volume sharing`,
      );
    }
    if (
      name !== "postgres" &&
      (service?.hostname === "postgres" ||
        service?.container_name === "postgres")
    ) {
      fail(
        `P1 pre-production blocker: ${name} collides with the protected database endpoint`,
      );
    }
    for (const secret of Array.isArray(service?.secrets)
      ? service.secrets
      : []) {
      if (
        secret?.source === "postgres_backup_password" ||
        secret?.target === "/run/secrets/postgres_backup_password"
      ) {
        consumers.secret.push(name);
      }
    }
    for (const volume of Array.isArray(service?.volumes)
      ? service.volumes
      : []) {
      if (
        volume?.type === "bind" &&
        pathsOverlap(volume?.source, primaryDatabaseDataRoot) &&
        !(
          name === "postgres" &&
          sameFile(volume.source, primaryDatabaseDataRoot) &&
          volume.target === "/var/lib/postgresql/data"
        )
      ) {
        fail(
          `P1 pre-production blocker: ${name} exposes the primary PostgreSQL data bind`,
        );
      }
      if (
        volume?.type === "bind" &&
        (sourceContainsFile(volume?.source, repositoryEnvironmentFile) ||
          sourceContainsFile(volume?.source, approvedSecret?.file))
      ) {
        fail(
          `P1 pre-production blocker: ${name} bind-mounts a protected credential source`,
        );
      }
      if (
        volume?.type === "bind" &&
        protectedRuntimeSockets.some(
          (socket) =>
            sourceContainsFile(volume?.source, socket) ||
            sameFile(volume?.target, socket),
        )
      ) {
        fail(
          `P1 pre-production blocker: ${name} exposes a container runtime socket`,
        );
      }
      if (
        volume?.type === "bind" &&
        protectedContainerDataRoots.some((root) =>
          pathsOverlap(volume?.source, root),
        )
      ) {
        fail(
          `P1 pre-production blocker: ${name} exposes protected container runtime data`,
        );
      }
      if (volume?.source === "pgbackups" || volume?.target === "/backups") {
        consumers.archive.push(name);
      }
      if (
        volume?.target === "/hooks" ||
        volume?.source === `${process.cwd()}/infra/postgres-backup/hooks`
      ) {
        consumers.hook.push(name);
      }
      if (
        volume?.target ===
          "/opt/quillmd/provision-postgres-backup-principal.sh" ||
        volume?.source ===
          `${process.cwd()}/infra/postgres/provision-postgres-backup-principal.sh`
      ) {
        consumers.provisioner.push(name);
      }
    }
  }
  const expected = qa
    ? { network: [], secret: [], archive: [], hook: [], provisioner: [] }
    : {
        network: ["postgres", "postgres-backup"],
        secret: ["postgres", "postgres-backup"],
        archive: ["postgres-backup"],
        hook: ["postgres-backup"],
        provisioner: ["postgres"],
      };
  for (const key of Object.keys(expected)) {
    const actualNames = [...new Set(consumers[key])].sort();
    const expectedNames = [...expected[key]].sort();
    if (!exactArray(actualNames, expectedNames)) {
      fail(`P1 pre-production blocker: ${key} backup resource census drifted`);
    }
  }
  if (!qa && !hasExactBackupNetwork(model?.networks?.backup_database)) {
    fail("P1 pre-production blocker: backup network is not exact and internal");
  }
}

function isRequiredResolvedSecret(value, name) {
  return staticUnresolved
    ? value === `\${${name}:?${name} is required}`
    : typeof value === "string" && BASE64URL_CREDENTIAL.test(value);
}

function initializeResolvedCredentialBindings(services, qa) {
  resolvedCredentialFingerprintByLogin = new Map();
  if (staticUnresolved) return;
  const environment = services?.postgres?.environment ?? {};
  const fingerprints = new Set();
  const reviewedLogins = qa
    ? [...PASSWORD_ENVIRONMENT_BY_LOGIN].filter(
        ([login]) => login !== DATABASE_OWNER_LOGIN,
      )
    : [...PASSWORD_ENVIRONMENT_BY_LOGIN];
  for (const [login, key] of reviewedLogins) {
    const value =
      environment[key === "DB_PASSWORD" ? "POSTGRES_PASSWORD" : key];
    if (typeof value !== "string" || !BASE64URL_CREDENTIAL.test(value)) {
      fail(
        "P1 pre-production blocker: resolved database credential contract is invalid",
      );
    }
    const fingerprint = credentialFingerprint(value);
    fingerprints.add(fingerprint);
    resolvedCredentialFingerprintByLogin.set(login, fingerprint);
  }
  if (fingerprints.size !== reviewedLogins.length) {
    fail(
      "P1 pre-production blocker: resolved database credentials are not role-distinct",
    );
  }
}

function isExactBindMount(volume, source, target, readOnly) {
  return (
    hasExactKeys(volume, [
      "bind",
      ...(readOnly ? ["read_only"] : []),
      "source",
      "target",
      "type",
    ]) &&
    volume.type === "bind" &&
    volume.source === source &&
    volume.target === target &&
    (readOnly ? volume.read_only === true : volume.read_only === undefined) &&
    hasExactKeys(volume.bind, ["create_host_path"]) &&
    volume.bind.create_host_path === true
  );
}

function hasExactQaBootstrapSecretMount(actual) {
  return (
    Array.isArray(actual) &&
    actual.length === 1 &&
    hasExactKeys(actual[0], ["source", "target"]) &&
    actual[0].source === "qa_postgres_backup_password" &&
    actual[0].target === "/run/secrets/qa_postgres_backup_password"
  );
}

function isExactDatabaseServer(name, service, inspection, qa) {
  const environment = service?.environment ?? {};
  const databaseHintKeys = Object.entries(environment)
    .filter(
      ([key, value]) =>
        typeof value === "string" && value.length > 0 && isPostgresHintKey(key),
    )
    .map(([key]) => key)
    .sort();
  const shared =
    name === "postgres" &&
    (qa
      ? hasExactQaPostgresImage(service?.image) &&
        hasExactQaPostgresBuild(service?.build)
      : service?.build === undefined &&
        hasExactProductionPostgresImage(service?.image)) &&
    hasExactPostgresHostAuthenticationSources() &&
    environment.POSTGRES_USER === DATABASE_OWNER_LOGIN &&
    typeof environment.POSTGRES_PASSWORD === "string" &&
    environment.PGDATA === "/var/lib/postgresql/data/pgdata" &&
    environment.QUILLMD_SERVICE_ROLE === undefined &&
    environment[PROFILE_ENVIRONMENT] === undefined &&
    JSON.stringify(databaseHintKeys) ===
      JSON.stringify([
        "PGDATA",
        "POSTGRES_DB",
        "POSTGRES_INITDB_ARGS",
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
      ]) &&
    hasOnlyIdentity(inspection, DATABASE_OWNER_LOGIN) &&
    hasExactMechanisms(inspection, ["pg-env:PG*"]);
  if (!shared) return false;
  if (qa) {
    return (
      hasExactKeys(service, [
        "build",
        "cap_drop",
        "command",
        "entrypoint",
        "cpus",
        "environment",
        "healthcheck",
        "image",
        "mem_limit",
        "networks",
        "read_only",
        "restart",
        "secrets",
        "tmpfs",
        "user",
        "volumes",
      ]) &&
      exactArray(service.command, POSTGRES_HBA_COMMAND) &&
      exactArray(service.entrypoint, [POSTGRES_ENTRYPOINT_PATH]) &&
      service.restart === "no" &&
      service.user === "999:999" &&
      exactArray(service.cap_drop, ["ALL"]) &&
      service.read_only === true &&
      exactArray(service.tmpfs, [
        "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
        "/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=3777",
      ]) &&
      service.cpus === (staticUnresolved ? "1.0" : 1) &&
      service.mem_limit === (staticUnresolved ? "512m" : "536870912") &&
      hasExactKeys(environment, [
        "DB_AUDIT_DISPATCHER_PASSWORD",
        "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
        "DB_BACKUP_PASSWORD_FILE",
        "DB_RELEASE_CONTROL_PASSWORD",
        "DB_RUNTIME_PASSWORD",
        "PGDATA",
        "POSTGRES_DB",
        "POSTGRES_INITDB_ARGS",
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
      ]) &&
      environment.POSTGRES_DB === "meddoc_qa_test" &&
      environment.POSTGRES_PASSWORD === "qa_test_pw" &&
      environment.POSTGRES_INITDB_ARGS ===
        "--auth-host=scram-sha-256 --auth-local=trust" &&
      isRequiredResolvedSecret(
        environment.DB_RUNTIME_PASSWORD,
        "QA_DB_RUNTIME_PASSWORD",
      ) &&
      isRequiredResolvedSecret(
        environment.DB_RELEASE_CONTROL_PASSWORD,
        "QA_DB_RELEASE_CONTROL_PASSWORD",
      ) &&
      isRequiredResolvedSecret(
        environment.DB_AUDIT_DISPATCHER_PASSWORD,
        "QA_DB_AUDIT_DISPATCHER_PASSWORD",
      ) &&
      isRequiredResolvedSecret(
        environment.DB_AUTH_EMAIL_DISPATCHER_PASSWORD,
        "QA_DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
      ) &&
      environment.DB_BACKUP_PASSWORD_FILE ===
        "/run/secrets/qa_postgres_backup_password" &&
      hasExactKeys(service.networks, ["default"]) &&
      service.networks.default === null &&
      hasExactQaBootstrapSecretMount(service.secrets) &&
      Array.isArray(service.volumes) &&
      service.volumes.length === 2 &&
      hasExactKeys(service.volumes[0], [
        "source",
        "target",
        "type",
        "volume",
      ]) &&
      service.volumes[0].source === "qa_pgdata" &&
      service.volumes[0].target === "/var/lib/postgresql/data" &&
      service.volumes[0].type === "volume" &&
      hasExactKeys(service.volumes[0].volume, []) &&
      isExactBindMount(
        service.volumes[1],
        `${process.cwd()}/infra/postgres/init-template-twin-roles.sh`,
        "/docker-entrypoint-initdb.d/20-quillmd-exact-principals.sh",
        true,
      ) &&
      hasExactKeys(service.healthcheck, [
        "interval",
        "retries",
        "test",
        "timeout",
      ]) &&
      exactArray(service.healthcheck.test, [
        "CMD",
        "/bin/sh",
        POSTGRES_HBA_VERIFIER_PATH,
      ]) &&
      service.healthcheck.interval === "5s" &&
      service.healthcheck.retries === 10 &&
      service.healthcheck.timeout === "5s"
    );
  }
  const volumes = service.volumes;
  const ports = service.ports;
  return (
    hasExactKeys(service, [
      "cap_drop",
      "command",
      "entrypoint",
      "cpus",
      "environment",
      "healthcheck",
      "image",
      "mem_limit",
      "networks",
      "ports",
      "read_only",
      "restart",
      "secrets",
      "tmpfs",
      "user",
      "volumes",
    ]) &&
    exactArray(service.command, POSTGRES_HBA_COMMAND) &&
    exactArray(service.entrypoint, [POSTGRES_ENTRYPOINT_PATH]) &&
    service.restart === "unless-stopped" &&
    service.user === "999:999" &&
    exactArray(service.cap_drop, ["ALL"]) &&
    service.read_only === true &&
    exactArray(service.tmpfs, [
      "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
      "/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=3777",
    ]) &&
    service.cpus === (staticUnresolved ? "1.0" : 1) &&
    service.mem_limit === (staticUnresolved ? "512m" : "536870912") &&
    hasExactKeys(environment, [
      "DB_AUDIT_DISPATCHER_PASSWORD",
      "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
      "DB_BACKUP_PASSWORD_FILE",
      "DB_RELEASE_CONTROL_PASSWORD",
      "DB_RUNTIME_PASSWORD",
      "PGDATA",
      "POSTGRES_DB",
      "POSTGRES_INITDB_ARGS",
      "POSTGRES_PASSWORD",
      "POSTGRES_USER",
    ]) &&
    environment.POSTGRES_DB === "meddoc" &&
    environment.POSTGRES_INITDB_ARGS ===
      "--auth-host=scram-sha-256 --auth-local=trust" &&
    isRequiredResolvedSecret(environment.POSTGRES_PASSWORD, "DB_PASSWORD") &&
    isRequiredResolvedSecret(
      environment.DB_RUNTIME_PASSWORD,
      "DB_RUNTIME_PASSWORD",
    ) &&
    isRequiredResolvedSecret(
      environment.DB_RELEASE_CONTROL_PASSWORD,
      "DB_RELEASE_CONTROL_PASSWORD",
    ) &&
    isRequiredResolvedSecret(
      environment.DB_AUDIT_DISPATCHER_PASSWORD,
      "DB_AUDIT_DISPATCHER_PASSWORD",
    ) &&
    isRequiredResolvedSecret(
      environment.DB_AUTH_EMAIL_DISPATCHER_PASSWORD,
      "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
    ) &&
    environment.DB_BACKUP_PASSWORD_FILE ===
      "/run/secrets/postgres_backup_password" &&
    hasExactKeys(service.networks, [
      "auth_email_database",
      "backup_database",
      "default",
    ]) &&
    service.networks.auth_email_database === null &&
    service.networks.backup_database === null &&
    service.networks.default === null &&
    Array.isArray(ports) &&
    ports.length === 1 &&
    hasExactKeys(ports[0], [
      "host_ip",
      "mode",
      "protocol",
      "published",
      "target",
    ]) &&
    ports[0].host_ip === "127.0.0.1" &&
    ports[0].mode === "ingress" &&
    ports[0].protocol === "tcp" &&
    ports[0].published === "5432" &&
    ports[0].target === 5432 &&
    hasExactBackupSecretMounts(service.secrets) &&
    Array.isArray(volumes) &&
    volumes.length === 3 &&
    isExactBindMount(
      volumes[0],
      "/mnt/pgdata-encrypted",
      "/var/lib/postgresql/data",
      false,
    ) &&
    isExactBindMount(
      volumes[1],
      `${process.cwd()}/infra/postgres/init-template-twin-roles.sh`,
      "/docker-entrypoint-initdb.d/20-template-twin-roles.sh",
      true,
    ) &&
    isExactBindMount(
      volumes[2],
      `${process.cwd()}/infra/postgres/provision-postgres-backup-principal.sh`,
      "/opt/quillmd/provision-postgres-backup-principal.sh",
      true,
    ) &&
    hasExactKeys(service.healthcheck, [
      "interval",
      "retries",
      "test",
      "timeout",
    ]) &&
    exactArray(service.healthcheck.test, [
      "CMD",
      "/bin/sh",
      POSTGRES_HBA_VERIFIER_PATH,
    ]) &&
    service.healthcheck.interval === "5s" &&
    service.healthcheck.retries === 5 &&
    service.healthcheck.timeout === "5s"
  );
}

function hasExactMigrationLoopbackUrl(environment, qa) {
  const inspection = inspectDatabaseEnvironment(environment);
  const contract = inspection.postgresUrlContracts[0];
  const expectedCredentialEnvironment = qa
    ? null
    : PASSWORD_ENVIRONMENT_BY_LOGIN.get(DATABASE_OWNER_LOGIN);
  const expectedCredentialContract = qa
    ? "synthetic-qa"
    : staticUnresolved
      ? `env:${expectedCredentialEnvironment ?? ""}`
      : "resolved-base64url";
  const expectedCredentialFingerprint =
    !qa && !staticUnresolved
      ? resolvedCredentialFingerprintByLogin.get(DATABASE_OWNER_LOGIN)
      : null;
  const normalizedActualQuery = JSON.stringify(
    [...(contract?.queryEntries ?? [])].sort(
      ([leftKey, leftValue], [rightKey, rightValue]) =>
        leftKey === rightKey
          ? leftValue.localeCompare(rightValue)
          : leftKey.localeCompare(rightKey),
    ),
  );
  const normalizedExpectedQuery = JSON.stringify([
    ["options", CANONICAL_SEARCH_PATH_OPTION],
    ["schema", "public"],
  ]);
  return (
    hasOnlyIdentity(inspection, DATABASE_OWNER_LOGIN) &&
    hasExactMechanisms(inspection, ["url:DATABASE_URL"]) &&
    hasExactCanonicalSearchPath(inspection, 1) &&
    inspection.postgresUrlContracts.length === 1 &&
    contract?.key === "DATABASE_URL" &&
    contract.authority === "127.0.0.1:5432" &&
    contract.credentialContract === expectedCredentialContract &&
    (qa ||
      staticUnresolved ||
      contract.credentialFingerprint === expectedCredentialFingerprint) &&
    contract.database === (qa ? "meddoc_qa_test" : "meddoc") &&
    contract.fragmentPresent === false &&
    normalizedActualQuery === normalizedExpectedQuery
  );
}

function isExactSegmentedMigrator(name, service, qa) {
  const environment = service?.environment ?? {};
  const migrationLockTimeout = reviewedMigrationLockTimeout(environment);
  const sharedContract =
    name === "db-migrate" &&
    exactArray(service?.profiles, ["migrations"]) &&
    exactArray(service?.entrypoint, [
      "npm",
      "run",
      "--silent",
      "database-release:migrate",
      "--",
    ]) &&
    exactArray(service?.command, ["--phase", "status"]) &&
    service?.working_dir === "/app/packages/db" &&
    hasExactKeys(environment, [
      "DATABASE_URL",
      MIGRATION_LOCK_TIMEOUT_ENVIRONMENT,
      MIGRATION_NETWORK_BOUNDARY_ENVIRONMENT,
      STATEMENT_TIMEOUT_ENVIRONMENT,
    ]) &&
    migrationLockTimeout !== null &&
    environment[MIGRATION_NETWORK_BOUNDARY_ENVIRONMENT] ===
      MIGRATION_NETWORK_BOUNDARY &&
    hasExactMigrationLoopbackUrl(environment, qa) &&
    environment.QUILLMD_SERVICE_ROLE === undefined &&
    environment[PROFILE_ENVIRONMENT] === undefined &&
    hasExactKeys(service?.depends_on, ["postgres"]) &&
    hasExactKeys(service?.depends_on?.postgres, ["condition", "required"]) &&
    service.depends_on.postgres.condition === "service_healthy" &&
    service.depends_on.postgres.required === true &&
    service?.network_mode === "service:postgres" &&
    service?.networks === undefined;
  if (!sharedContract) return false;
  if (qa) {
    const approvedMigratorImage =
      process.env.QUILLMD_APPROVED_QA_DB_MIGRATE_IMAGE;
    return (
      hasExactKeys(service, [
        "command",
        "depends_on",
        "entrypoint",
        "environment",
        "image",
        "network_mode",
        "profiles",
        "restart",
        "working_dir",
      ]) &&
      service.image ===
        (staticUnresolved
          ? "${QA_DB_MIGRATE_IMAGE:-meddoc-pro-db-migrate:latest}"
          : approvedMigratorImage) &&
      (staticUnresolved ||
        (typeof approvedMigratorImage === "string" &&
          /@sha256:[a-f0-9]{64}$/u.test(approvedMigratorImage))) &&
      service.restart === "no"
    );
  }
  return (
    hasExactKeys(service, [
      "build",
      "command",
      "depends_on",
      "entrypoint",
      "environment",
      "network_mode",
      "profiles",
      "working_dir",
    ]) &&
    hasExactKeys(service.build, ["context", "dockerfile", "target"]) &&
    service.build.context === process.cwd() &&
    service.build.dockerfile === "apps/transcribe-md/Dockerfile" &&
    service.build.target === "builder"
  );
}

function reviewedMigrationLockTimeout(environment) {
  const value = environment?.[MIGRATION_LOCK_TIMEOUT_ENVIRONMENT];
  if (staticUnresolved) {
    return value === STATIC_MIGRATION_LOCK_TIMEOUT ? value : null;
  }
  if (typeof value !== "string" || !/^[1-9][0-9]*$/u.test(value)) {
    return null;
  }
  const milliseconds = Number(value);
  return Number.isSafeInteger(milliseconds) && milliseconds <= 60_000
    ? value
    : null;
}

function reviewedStatementTimeout(environment) {
  const value = environment?.[STATEMENT_TIMEOUT_ENVIRONMENT];
  if (staticUnresolved) {
    return value === STATIC_STATEMENT_TIMEOUT ? value : null;
  }
  if (typeof value !== "string" || !/^[1-9][0-9]*$/u.test(value)) {
    return null;
  }
  const milliseconds = Number(value);
  return Number.isSafeInteger(milliseconds) && milliseconds <= 2_147_483_647
    ? value
    : null;
}

let qa = false;
for (const argument of process.argv.slice(2)) {
  if (argument === "--qa") qa = true;
  else if (argument === "--static-unresolved") staticUnresolved = true;
  else fail("unexpected argument");
}

let raw = "";
for await (const chunk of process.stdin) raw += chunk;

let model;
try {
  model = JSON.parse(raw);
} catch {
  fail("resolved Compose model is not valid JSON");
}
const services = model?.services;
if (!services || typeof services !== "object" || Array.isArray(services)) {
  fail("resolved Compose service map is unavailable");
}
initializeResolvedCredentialBindings(services, qa);

const expectedServices = qa ? qaServices : productionServices;
const expectedProfile = qa ? SYNTHETIC_QA_PROFILE : EXACT_PROFILE;
const inspectionsByService = new Map();
const excludedInfrastructureServices = new Set();
if (!qa && !Object.prototype.hasOwnProperty.call(services, "postgres-backup")) {
  fail("P1 pre-production blocker: exact postgres-backup runtime is missing");
}
if (!Object.prototype.hasOwnProperty.call(services, "db-migrate")) {
  fail("P1 pre-production blocker: exact db-migrate runtime is missing");
}
const databaseServerInspection = inspectDatabaseEnvironment(
  services.postgres?.environment ?? {},
);
if (
  !isExactDatabaseServer(
    "postgres",
    services.postgres,
    databaseServerInspection,
    qa,
  )
) {
  fail(
    "P1 pre-production blocker: exact PostgreSQL database server is missing",
  );
}
const migratorInspection = inspectDatabaseEnvironment(
  services["db-migrate"]?.environment ?? {},
);
const migratorStatementTimeout = reviewedStatementTimeout(
  services["db-migrate"]?.environment ?? {},
);
if (
  !isExactSegmentedMigrator("db-migrate", services["db-migrate"], qa) ||
  !hasOnlyIdentity(migratorInspection, DATABASE_OWNER_LOGIN) ||
  !hasExactMechanisms(migratorInspection, ["url:DATABASE_URL"]) ||
  !hasExactMigrationLoopbackUrl(
    services["db-migrate"]?.environment ?? {},
    qa,
  ) ||
  !hasExactCanonicalSearchPath(migratorInspection, 1) ||
  migratorStatementTimeout === null
) {
  fail(
    "P1 pre-production blocker: exact closed segmented db-migrate runtime is missing",
  );
}
assertExclusiveBackupResources(model, services, qa);
for (const [name, service] of Object.entries(services)) {
  const environment = service?.environment ?? {};
  const inspection = inspectDatabaseEnvironment(environment);
  inspectionsByService.set(name, inspection);

  if (service?.env_file !== undefined && !expectedServices.has(name)) {
    fail(`P1 pre-production blocker: ${name} has an unreviewed env_file`);
  }

  if (isExactDatabaseServer(name, service, inspection, qa)) {
    excludedInfrastructureServices.add(name);
    continue;
  }
  if (inspection.issues.size > 0) {
    fail(
      `P1 pre-production blocker: ${name} has an unresolved, duplicate, or indirect PostgreSQL database identity`,
    );
  }
  if (!qa && name === "postgres-backup") {
    if (!isExactBackupRuntime(name, service, inspection, model, services)) {
      fail(
        "P1 pre-production blocker: postgres-backup does not match the exact dedicated backup runtime contract",
      );
    }
    excludedInfrastructureServices.add(name);
    continue;
  }
  const identities = inspection.identities;
  if (identities.has(RELEASE_SECURITY_LOGIN)) {
    fail(
      `P1 pre-production blocker: ${name} uses ${RELEASE_SECURITY_LOGIN}, which has no allowed long-lived runtime`,
    );
  }
  const unreviewedDedicatedLogin = [...identities].find(
    (identity) =>
      /^meddoc_/u.test(identity) && !TRUSTED_PRODUCTION_LOGINS.has(identity),
  );
  if (unreviewedDedicatedLogin) {
    fail(
      `P1 pre-production blocker: ${name} uses an unreviewed dedicated meddoc database identity`,
    );
  }

  const exactOneShotMigrator =
    isExactSegmentedMigrator(name, service, qa) &&
    hasOnlyIdentity(inspection, DATABASE_OWNER_LOGIN) &&
    hasExactMechanisms(inspection, ["url:DATABASE_URL"]) &&
    hasExactMigrationLoopbackUrl(service?.environment ?? {}, qa) &&
    hasExactCanonicalSearchPath(inspection, 1);
  if (exactOneShotMigrator) {
    excludedInfrastructureServices.add(name);
    continue;
  }
  if (identities.has(DATABASE_OWNER_LOGIN)) {
    const restartable = ![undefined, null, "no"].includes(service?.restart);
    fail(
      `P1 pre-production blocker: ${name}${restartable ? " is restartable and" : ""} uses the ${DATABASE_OWNER_LOGIN} owner database identity outside the exact closed segmented db-migrate boundary`,
    );
  }
  if (inspection.candidate && !expectedServices.has(name)) {
    fail(
      `P1 pre-production blocker: ${name} is an unreviewed PostgreSQL database consumer`,
    );
  }
}

const discovered = Object.entries(services)
  .filter(([name, service]) => {
    const environment = service?.environment ?? {};
    return (
      !excludedInfrastructureServices.has(name) &&
      (Object.prototype.hasOwnProperty.call(environment, PROFILE_ENVIRONMENT) ||
        (inspectionsByService.get(name)?.candidate ?? false))
    );
  })
  .map(([name]) => name)
  .sort();
const expectedNames = [...expectedServices.keys()].sort();
if (JSON.stringify(discovered) !== JSON.stringify(expectedNames)) {
  fail("database-principal service census drifted");
}

for (const [name, expected] of expectedServices) {
  const environment = services[name]?.environment ?? {};
  if (environment.NODE_ENV !== "production") {
    fail(`${name} does not force NODE_ENV production`);
  }
  if (environment.QUILLMD_SERVICE_ROLE !== expected.role) {
    fail(`${name} has an unexpected service role`);
  }
  if (environment[PROFILE_ENVIRONMENT] !== expectedProfile) {
    fail(`${name} has an unexpected database-principal profile`);
  }
  const statementTimeout = reviewedStatementTimeout(environment);
  if (
    statementTimeout === null ||
    statementTimeout !== migratorStatementTimeout
  ) {
    fail(`${name} does not share the exact preflight statement timeout`);
  }
  const primaryDatabaseUrl = environment.DATABASE_URL;
  const primaryInspection =
    typeof primaryDatabaseUrl === "string"
      ? inspectPostgresUrl(primaryDatabaseUrl)
      : null;
  if (
    !primaryInspection ||
    !hasOnlyIdentity(primaryInspection, expected.login)
  ) {
    fail(`${name} has an unexpected DATABASE_URL login`);
  }
  const completeInspection = inspectionsByService.get(name);
  if (
    !completeInspection ||
    !hasOnlyIdentity(completeInspection, expected.login)
  ) {
    fail(`${name} has an unexpected database identity set`);
  }
  if (!hasExactMechanisms(completeInspection, expected.connectionMechanisms)) {
    fail(`${name} has an unexpected database connection mechanism set`);
  }
  if (
    !hasExactCanonicalSearchPath(
      completeInspection,
      expected.connectionMechanisms.length,
    )
  ) {
    fail(`${name} does not force the canonical PostgreSQL search_path`);
  }
  if (
    !hasExactReviewedPostgresUrls(
      completeInspection,
      expected.connectionMechanisms,
      expected.login,
      qa,
    )
  ) {
    fail(`${name} has an unexpected PostgreSQL destination or query contract`);
  }
  if (!hasExactEnvFile(services[name], expected.envFile)) {
    fail(`${name} has an unexpected env_file contract`);
  }
  const authorityIssue = runtimeAuthorityIssue(
    name,
    services[name],
    expected,
    qa,
  );
  if (authorityIssue !== null) {
    fail(
      `${name} has an unexpected runtime authority contract: ${authorityIssue}`,
    );
  }
}

for (const [name, service] of Object.entries(services)) {
  assertDatabaseMaterialLocations(name, service, qa);
}
assertExactNamedResources(model, services, qa);

process.stdout.write(
  `database-principal-census: PASS profile=${qa ? "synthetic-qa" : "production"} mode=${staticUnresolved ? "static-unresolved" : "resolved"} services=${expectedServices.size}\n`,
);
