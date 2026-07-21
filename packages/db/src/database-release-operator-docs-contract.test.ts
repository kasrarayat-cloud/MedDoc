import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const source = (path: string): string =>
  readFileSync(resolve(repositoryRoot, path), "utf8");

const compose = source("docker-compose.yml");
const qaCompose = source("docker-compose.qa.yml");
const rootReadme = source("README.md");
const deploymentRunbook = source("docs/DEPLOYMENT_RUNBOOK.md");
const launchChecklist = source("docs/LAUNCH_CHECKLIST.md");
const qaRunbook = source("docs/qa/README.md");
const postMergeTodo = source("docs/POST_MERGE_TODO.md");
const releaseStatus = source(
  "docs/releases/template-twin-ga-20260719/status.md",
);
const humanApprovalPackets = [
  source(
    "docs/releases/template-twin-ga-20260719/clinical-safety-approval-packet.md",
  ),
  source(
    "docs/releases/template-twin-ga-20260719/operations-approval-packet.md",
  ),
  source(
    "docs/releases/template-twin-ga-20260719/physician-review-packet.md",
  ),
  source(
    "docs/releases/template-twin-ga-20260719/privacy-legal-approval-packet.md",
  ),
];
const lineageRunbook = source(
  "docs/runbooks/template-twin-lineage-online-migration.md",
);
const authTokenRunbook = source(
  "docs/runbooks/auth-token-linearization-online.md",
);
const legacyOperationsReadme = source("apps/meddoc-pro/scripts/README.md");
const disasterRecoveryRunbook = source("docs/runbooks/disaster-recovery.md");
const postgresRecoveryRunbook = source("docs/runbooks/postgres-recovery.md");
const rolloutRevocationRunbook = source(
  "docs/runbooks/template-twin-rollout-revocation.md",
);
const durableStagingRunbook = source(
  "docs/runbooks/template-twin-durable-staging-admission.md",
);
const productionReleaseControlRunbook = source(
  "docs/runbooks/template-twin-production-release-control.md",
);
const visitAutomationRunbook = source(
  "docs/runbooks/visit-automation-transaction-integrity.md",
);
const templateTwinDesign = source("docs/template-twin-docx-v1.md");
const migrationRunner = source("packages/db/scripts/prisma-migrate-segment.ts");
const lineageOperator = source(
  "packages/db/scripts/template-twin-lineage-online.ts",
);
const lineageLibrary = source(
  "packages/db/src/template-twin-lineage-online.ts",
);
const authTokenOperator = source(
  "packages/db/scripts/auth-token-linearization-online.ts",
);
const authTokenLibrary = source(
  "packages/db/src/auth-token-linearization-online.ts",
);
const normalizedDeploymentRunbook = deploymentRunbook.replace(/\s+/gu, " ");
const normalizedRootReadme = rootReadme.replace(/\s+/gu, " ");
const normalizedLaunchChecklist = launchChecklist.replace(/\s+/gu, " ");
const normalizedQaRunbook = qaRunbook.replace(/\s+/gu, " ");
const normalizedLegacyOperationsReadme = legacyOperationsReadme.replace(
  /\s+/gu,
  " ",
);
const normalizedDisasterRecoveryRunbook = disasterRecoveryRunbook.replace(
  /\s+/gu,
  " ",
);
const normalizedPostgresRecoveryRunbook = postgresRecoveryRunbook.replace(
  /\s+/gu,
  " ",
);
const normalizedRolloutRevocationRunbook = rolloutRevocationRunbook.replace(
  /\s+/gu,
  " ",
);
const normalizedTemplateTwinDesign = templateTwinDesign.replace(/\s+/gu, " ");
const normalizedDurableStagingRunbook = durableStagingRunbook.replace(
  /\s+/gu,
  " ",
);
const normalizedProductionReleaseControlRunbook =
  productionReleaseControlRunbook.replace(/\s+/gu, " ");
const normalizedVisitAutomationRunbook = visitAutomationRunbook.replace(
  /\s+/gu,
  " ",
);
const normalizedAuthTokenRunbook = authTokenRunbook.replace(/\s+/gu, " ");

describe("closed database-release operator documentation contract", () => {
  it("documents the Compose migrator default as status-only", () => {
    for (const model of [compose, qaCompose]) {
      expect(model).toContain('command: ["--phase", "status"]');
    }
    expect(deploymentRunbook).toContain(
      "A bare\n`docker compose run --rm db-migrate` uses the Compose default",
    );
    expect(deploymentRunbook).toContain(
      "it is exactly the same read-only status operation and never\napplies a migration",
    );
    expect(qaRunbook).toContain(
      "A bare `$QA run --rm db-migrate` also uses the Compose default",
    );
    expect(qaRunbook).toContain("it never applies migrations");
    expect(deploymentRunbook).not.toContain(
      "docker compose run --rm db-migrate        # Prisma will apply + log diff",
    );
    expect(qaRunbook).not.toContain(
      "$QA run --rm db-migrate\n\n# 3. app + worker",
    );
  });

  it("documents only the closed cumulative migration release graph", () => {
    for (const phase of ["lineage-expand", "auth-expand", "pre-v9", "v9"]) {
      expect(migrationRunner).toContain(`"${phase}"`);
      expect(deploymentRunbook).toContain(`\`${phase}\``);
    }
    for (const control of [
      "DATABASE_RELEASE_MIGRATION_APPROVED_TARGET_FINGERPRINT",
      "DATABASE_RELEASE_MIGRATION_ALLOW_PRODUCTION",
      "DATABASE_RELEASE_MIGRATION_PRODUCTION_CHANGE_ID",
      "DATABASE_RELEASE_MIGRATION_PRODUCTION_ACK",
    ]) {
      expect(migrationRunner).toContain(control);
      expect(deploymentRunbook).toContain(control);
    }
    expect(deploymentRunbook).toContain(
      "Raw or one-shot `prisma migrate deploy` is not a supported\nproduction entrypoint",
    );
    expect(normalizedDeploymentRunbook).toContain(
      "Mutation is also bound to the Compose-shared PostgreSQL loopback namespace",
    );
    expect(qaRunbook).toContain(
      "Schema mutation is available\nonly through the closed cumulative runner phases",
    );
    expect(migrationRunner).toContain(
      "targetFingerprints: migrationApprovalFingerprints({",
    );
    expect(migrationRunner).toContain("if (input.inRecovery) return {};");
  });

  it("requires a fresh phase-specific migration challenge for every segment", () => {
    const migrationDocuments = [
      rootReadme,
      legacyOperationsReadme,
      deploymentRunbook,
      launchChecklist,
      qaRunbook,
      disasterRecoveryRunbook,
      postgresRecoveryRunbook,
      rolloutRevocationRunbook,
      durableStagingRunbook,
      productionReleaseControlRunbook,
      visitAutomationRunbook,
      templateTwinDesign,
    ];
    for (const document of migrationDocuments) {
      expect(document).toContain("targetFingerprints.");
      expect(document).not.toContain("`targetFingerprint`");
    }
    expect(normalizedDeploymentRunbook).toContain(
      "The map is phase-, ledger-, accepted-source-, and target-bound",
    );
    expect(normalizedDeploymentRunbook).toContain(
      "Status emits no approval entries while PostgreSQL is in recovery",
    );
    expect(normalizedDeploymentRunbook).toContain(
      "another segment, retry, resumed invocation, or zero-change invocation",
    );
    expect(normalizedQaRunbook).toContain(
      "An empty map on a recovery target is a stop condition",
    );
  });

  it("routes production and recovery migration instructions through the closed runner", () => {
    for (const document of [
      rootReadme,
      legacyOperationsReadme,
      launchChecklist,
      disasterRecoveryRunbook,
      postgresRecoveryRunbook,
      rolloutRevocationRunbook,
      durableStagingRunbook,
      productionReleaseControlRunbook,
      visitAutomationRunbook,
    ]) {
      expect(document).toContain(
        "docker compose run --rm db-migrate --phase status",
      );
      expect(document).toContain("docs/DEPLOYMENT_RUNBOOK.md");
    }
    expect(normalizedLegacyOperationsReadme).toContain(
      "is **not** eligible for a routine baseline marker",
    );
    expect(normalizedDisasterRecoveryRunbook).toContain(
      "new protected snapshot and an approved DBA forward-reconciliation decision",
    );
    expect(disasterRecoveryRunbook).not.toContain("grep '^DB_PASSWORD=' .env");
    expect(normalizedPostgresRecoveryRunbook).toContain(
      "not permission to repair Prisma's ledger",
    );
    expect(normalizedRolloutRevocationRunbook).toContain(
      "this runbook does not authorize or provide a ledger-repair command",
    );
    expect(rolloutRevocationRunbook).toContain("(`auth-expand`)");
    expect(normalizedTemplateTwinDesign).toContain(
      "The closed `db-migrate --phase lineage-expand` cumulative segment",
    );
    expect(normalizedTemplateTwinDesign).toContain(
      "There is no root migration-deploy alias",
    );
    expect(normalizedRootReadme).toContain(
      "A bare `docker compose run --rm db-migrate` is also read-only status",
    );
    expect(normalizedLaunchChecklist).toContain(
      "`targetFingerprints.lineage-expand` entry authorizes one approved `lineage-expand` cumulative-segment invocation",
    );
    expect(normalizedDurableStagingRunbook).toContain(
      "this runbook does not authorize a ledger-repair command",
    );
    expect(normalizedDurableStagingRunbook).toContain(
      "closed `auth-expand` cumulative segment",
    );
    expect(normalizedVisitAutomationRunbook).toContain(
      "this runbook does not authorize a ledger-repair command",
    );
    expect(normalizedVisitAutomationRunbook).toContain(
      "closed `auth-expand` cumulative segment",
    );
    expect(normalizedProductionReleaseControlRunbook).toContain(
      "before the closed `auth-expand` cumulative segment",
    );
  });

  it("prevents executable raw deploy and routine ledger-resolution instructions from returning", () => {
    const operationalDocuments = [
      rootReadme,
      legacyOperationsReadme,
      deploymentRunbook,
      launchChecklist,
      disasterRecoveryRunbook,
      postgresRecoveryRunbook,
      rolloutRevocationRunbook,
      durableStagingRunbook,
      productionReleaseControlRunbook,
      visitAutomationRunbook,
      templateTwinDesign,
      qaRunbook,
      lineageRunbook,
      authTokenRunbook,
      postMergeTodo,
    ];
    const forbiddenInstructions = [
      /^\s*docker\s+compose\s+exec[^\n]*prisma\s+migrate\s+deploy\b/mu,
      /^\s*docker\s+run[\s\S]{0,800}?prisma\s+migrate\s+deploy\b/mu,
      /^\s*(?:npx\s+)?prisma\s+migrate\s+(?:deploy|resolve)\b/mu,
      /^\s*npm\s+run\s+db:migrate:deploy\b/mu,
      /^\s*docker[^\n]*migrate\s+resolve\b/mu,
      /^\s*docker\s+compose\s+run\s+--rm\s+db-migrate\s*(?:#.*)?$/mu,
    ];
    for (const document of operationalDocuments) {
      for (const forbidden of forbiddenInstructions) {
        expect(document).not.toMatch(forbidden);
      }
    }
    const rootPackage = JSON.parse(source("package.json")) as {
      scripts?: Record<string, string>;
    };
    expect(rootPackage.scripts?.["db:migrate:deploy"]).toBeUndefined();
    expect(postMergeTodo).toContain(
      "Historical record — not an operator runbook",
    );
    expect(postMergeTodo).toContain(
      "docker compose run --rm db-migrate --phase status",
    );
    expect(postMergeTodo).toContain("docs/DEPLOYMENT_RUNBOOK.md");
  });

  it("requires one retained target-proved lineage session and a fresh challenge per mutation", () => {
    expect(lineageRunbook).toContain(
      "retains that same target-proved PostgreSQL session",
    );
    expect(lineageRunbook).toContain(
      "No second session is trusted to carry the approval or the lock",
    );
    expect(lineageRunbook).toContain(
      "Every mutating lineage invocation, including a retry, resumed batch, and\nzero-change idempotency run, requires a **fresh**",
    );
    expect(lineageRunbook).toContain("`targetFingerprints.<phase>`");
    expect(lineageRunbook).toContain(
      "TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT",
    );
    expect(lineageRunbook).toContain(
      "Do not reuse a challenge for another phase or after any status/progress change",
    );

    const connect = lineageOperator.indexOf(
      "connection = await pool.connect()",
    );
    const initialStatus = lineageOperator.indexOf(
      "readLineageMigrationStatusSnapshot(client)",
      connect,
    );
    const approval = lineageOperator.indexOf(
      "assertApprovedLineageOperatorTarget(",
      initialStatus,
    );
    const sessionLock = lineageOperator.indexOf(
      "acquireLineageOperatorSessionLockOnClient(connection)",
      approval,
    );
    const lockedStatus = lineageOperator.indexOf(
      "readLineageMigrationStatusSnapshot(client)",
      sessionLock,
    );
    expect(connect).toBeGreaterThan(-1);
    expect(initialStatus).toBeGreaterThan(connect);
    expect(approval).toBeGreaterThan(initialStatus);
    expect(sessionLock).toBeGreaterThan(approval);
    expect(lockedStatus).toBeGreaterThan(sessionLock);
  });

  it("pins every exact status field and all production lineage controls", () => {
    for (const field of [
      "presentIndexesExact",
      "validationConstraintExact",
      "transitionContractExact",
    ]) {
      expect(lineageLibrary).toContain(field);
      expect(lineageRunbook).toContain(`${field}=true`);
      expect(qaRunbook).toContain(field);
    }
    for (const control of [
      "TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION",
      "TEMPLATE_TWIN_LINEAGE_PRODUCTION_CHANGE_ID",
      "TEMPLATE_TWIN_LINEAGE_PRODUCTION_ACK",
      "TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT",
      "TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK",
    ]) {
      expect(lineageOperator).toContain(control);
      expect(lineageRunbook).toContain(control);
    }
  });

  it("requires one retained target-proved auth session and a fresh state challenge per mutation", () => {
    expect(authTokenRunbook).toContain(
      "Each mutating command retains one target-proved PostgreSQL connection",
    );
    expect(authTokenRunbook).toContain(
      "No second session carries approval or the lock",
    );
    expect(normalizedAuthTokenRunbook).toContain(
      "The fingerprint is phase- and protocol-state-specific",
    );
    expect(normalizedAuthTokenRunbook).toContain(
      "Every mutation, including a retry, resumed batch, and zero-change idempotency run, requires a new status observation",
    );
    expect(normalizedAuthTokenRunbook).toContain(
      "session advisory lock on the same retained target-proved connection",
    );

    const connect = authTokenOperator.indexOf("client = await pool.connect()");
    const preflight = authTokenOperator.indexOf(
      "await preflightAuthTokenOperatorTarget(",
      connect,
    );
    const initialStatus = authTokenOperator.indexOf(
      "await readAuthTokenLinearizationStatusSnapshot(client)",
      preflight,
    );
    const approval = authTokenOperator.indexOf(
      "assertApprovedAuthTokenOperatorTarget(",
      initialStatus,
    );
    const sessionLock = authTokenOperator.indexOf(
      "acquireAuthTokenOperatorSessionLockOnClient(client)",
      approval,
    );
    const lockedStatus = authTokenOperator.indexOf(
      "const lockedStatus = await readAuthTokenLinearizationStatusSnapshot(client)",
      sessionLock,
    );
    const lockedEpoch = authTokenOperator.indexOf(
      "authTokenOperatorProtocolEpoch(lockedStatus)",
      lockedStatus,
    );
    const firstMutation = authTokenOperator.indexOf(
      "await reconcileAuthTokenDuplicateBatch(",
      lockedEpoch,
    );
    expect(authTokenOperator).toContain("max: 1");
    expect(connect).toBeGreaterThan(-1);
    expect(preflight).toBeGreaterThan(connect);
    expect(initialStatus).toBeGreaterThan(preflight);
    expect(approval).toBeGreaterThan(initialStatus);
    expect(sessionLock).toBeGreaterThan(approval);
    expect(lockedStatus).toBeGreaterThan(sessionLock);
    expect(lockedEpoch).toBeGreaterThan(lockedStatus);
    expect(firstMutation).toBeGreaterThan(lockedEpoch);
  });

  it("pins the auth principal, recovery, and exact completion contracts", () => {
    for (const sourceCheck of [
      "row.sessionRole !== AUTH_TOKEN_OPERATOR_PRINCIPAL",
      "row.currentRole !== AUTH_TOKEN_OPERATOR_PRINCIPAL",
      "row.databaseOwner !== AUTH_TOKEN_OPERATOR_PRINCIPAL",
      "row.principalCanLogin !== true",
      "row.principalSuperuser !== true",
      "Math.trunc(row.serverVersionNumber / 10_000) !== 16",
      "if (target.inRecovery) return {};",
    ]) {
      expect(authTokenOperator).toContain(sourceCheck);
    }
    expect(normalizedAuthTokenRunbook).toContain(
      "session/current role and database owner are exactly `meddoc`, that principal is LOGIN+SUPERUSER",
    );
    expect(normalizedAuthTokenRunbook).toContain(
      "Status emits no approval fingerprints while the target is in recovery",
    );
    expect(normalizedAuthTokenRunbook).toContain(
      "Complete every exact database-principal preflight",
    );
    for (const field of [
      "duplicateGroups",
      "indexExists",
      "indexValid",
      "indexReady",
      "indexExact",
      "transitionTriggerEnabled",
      "transitionTriggerState",
      "complete",
    ]) {
      expect(authTokenLibrary).toContain(field);
      expect(authTokenRunbook).toContain(`${field}=`);
    }
  });

  it("requires a complete topology proof before an invalid index shell is dropped", () => {
    expect(lineageRunbook).toContain(
      "Before any drop, the operator proves that the fixed-name object is the\n  expected persistent btree index on the exact table",
    );
    expect(lineageRunbook).toContain(
      "A wrong same-name object\n  fails closed and is never modified",
    );
    const topologyProof = lineageLibrary.indexOf(
      "lineageIndexContractMatches(existing, indexName, false)",
    );
    const invalidShellDrop = lineageLibrary.indexOf(
      "DROP INDEX CONCURRENTLY IF EXISTS",
      topologyProof,
    );
    expect(topologyProof).toBeGreaterThan(-1);
    expect(invalidShellDrop).toBeGreaterThan(topologyProof);
  });

  it("keeps PostgreSQL host authentication distinct from TLS evidence", () => {
    expect(normalizedDeploymentRunbook).toContain(
      "HBA does not provide or prove TLS",
    );
    expect(normalizedQaRunbook).toContain("It does not provide or prove TLS");
    expect(normalizedPostgresRecoveryRunbook).toContain(
      "HBA authentication is not transport encryption",
    );
    expect(normalizedPostgresRecoveryRunbook).toContain(
      "It does not provide or prove TLS",
    );
    expect(normalizedAuthTokenRunbook).toContain(
      "it does not provide or prove TLS",
    );
    expect(normalizedDeploymentRunbook).toContain(
      "Encryption and peer-certificate verification for any network transport are separate infrastructure gates",
    );
  });

  it("keeps exact-head scan claims bound and human approvals visibly unfilled", () => {
    expect(releaseStatus).not.toContain(
      "Current whole-workspace verified-only secret scan",
    );
    expect(releaseStatus).toMatch(
      /Exact `[0-9a-f]{7,40}` whole-workspace verified-only secret scan:/u,
    );

    for (const packet of humanApprovalPackets) {
      const humanDecision = packet.split("## Human decision\n\n")[1] ?? "";
      const fields = humanDecision
        .split("\n")
        .filter((line) => line.startsWith("- "));

      expect(fields[0]).toBe(
        "- Decision: `APPROVE` / `REJECT` / `REVISE`",
      );
      expect(fields.length).toBeGreaterThan(1);
      for (const field of fields.slice(1)) {
        expect(field).toMatch(/: \*\*UNFILLED — HUMAN REQUIRED\*\*$/u);
      }
      expect(humanDecision).not.toMatch(/\\[\*_]/u);
    }
  });
});
