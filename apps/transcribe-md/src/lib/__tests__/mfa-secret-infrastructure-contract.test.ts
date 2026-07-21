import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = resolve(process.cwd(), "../..");
const compose = readFileSync(resolve(ROOT, "docker-compose.yml"), "utf8");
const qaCompose = readFileSync(resolve(ROOT, "docker-compose.qa.yml"), "utf8");
const environmentExample = readFileSync(
  resolve(ROOT, ".env.production.example"),
  "utf8",
);
const instrumentation = readFileSync(
  resolve(ROOT, "apps/transcribe-md/src/instrumentation.ts"),
  "utf8",
);
const backfill = readFileSync(
  resolve(ROOT, "apps/transcribe-md/scripts/mfa-secret-backfill.ts"),
  "utf8",
);
const runbook = readFileSync(
  resolve(ROOT, "docs/runbooks/mfa-secret-encryption.md"),
  "utf8",
);
const e2eWorkflow = readFileSync(
  resolve(ROOT, ".github/workflows/e2e.yml"),
  "utf8",
);
const lockOrderPgProof = readFileSync(
  resolve(
    ROOT,
    "packages/db/scripts/mfa-secret-backfill-lock-order-pg-test.ts",
  ),
  "utf8",
);

function serviceBlock(source: string, service: string): string {
  const start = source.search(new RegExp(`^  ${service}:`, "mu"));
  expect(start).toBeGreaterThanOrEqual(0);
  const remainder = source.slice(start + 1);
  const next = remainder.search(/^  [a-zA-Z0-9_-]+:/mu);
  return source.slice(start, next < 0 ? source.length : start + 1 + next);
}

function supplementalGroups(block: string): string[] {
  const start = block.search(/^    group_add:/mu);
  if (start < 0) return [];
  const remainder = block.slice(start + 1);
  const next = remainder.search(/^    [a-zA-Z0-9_-]+:/mu);
  const groupBlock = block.slice(
    start,
    next < 0 ? block.length : start + 1 + next,
  );
  return [...groupBlock.matchAll(/^      - "([0-9]+)"$/gmu)].map(
    (match) => match[1],
  );
}

describe("MFA secret infrastructure boundary", () => {
  it("mounts the keyring only into physician and admin-app services", () => {
    const physician = serviceBlock(compose, "transcribe-md");
    const adminApp = serviceBlock(compose, "template-twin-admin-app");
    for (const block of [physician, adminApp]) {
      expect(block).toContain("MFA_SECRET_ACTIVE_KEY_ID:");
      expect(block).toContain("MFA_SECRET_KEYRING_FILE:");
      expect(block).toContain("MFA_SECRET_KEYRING_FILE is required}");
      expect(block).toContain("type: bind");
      expect(block).toContain(
        "source: ${MFA_SECRET_KEYRING_FILE:?MFA_SECRET_KEYRING_FILE is required}",
      );
      expect(block).toContain(
        "target: ${MFA_SECRET_KEYRING_FILE:?MFA_SECRET_KEYRING_FILE is required}",
      );
      expect(block).toContain("read_only: true");
      expect(block).toContain("create_host_path: false");
      expect(block).not.toContain("required}:${MFA_SECRET_KEYRING_FILE");
    }
    expect(supplementalGroups(physician)).toEqual(["101", "1001"]);
    expect(supplementalGroups(adminApp)).toEqual(["1001"]);

    for (const service of [
      "meddoc-pro",
      "transcribe-md-worker",
      "template-twin-audit-dispatcher",
      "auth-email-dispatcher",
      "template-twin-admin-control",
    ]) {
      const block = serviceBlock(compose, service);
      expect(block).toContain('MFA_SECRET_ACTIVE_KEY_ID: ""');
      expect(block).toContain('MFA_SECRET_KEYRING_FILE: ""');
      expect(block).not.toContain("MFA_SECRET_KEYRING_FILE is required}");
      expect(supplementalGroups(block)).not.toContain("1001");
    }
  });

  it("requires a separate external synthetic-QA keyring without mounting it into the worker", () => {
    const app = serviceBlock(qaCompose, "transcribe-md");
    const worker = serviceBlock(qaCompose, "transcribe-md-worker");
    expect(app).toContain("QA_MFA_SECRET_ACTIVE_KEY_ID is required");
    expect(app).toContain("QA_MFA_SECRET_KEYRING_FILE is required");
    expect(app).toContain("type: bind");
    expect(app).toContain(
      "source: ${QA_MFA_SECRET_KEYRING_FILE:?QA_MFA_SECRET_KEYRING_FILE is required}",
    );
    expect(app).toContain(
      "target: ${QA_MFA_SECRET_KEYRING_FILE:?QA_MFA_SECRET_KEYRING_FILE is required}",
    );
    expect(app).toContain("read_only: true");
    expect(app).toContain("create_host_path: false");
    expect(app).not.toContain("required}:${QA_MFA_SECRET_KEYRING_FILE");
    expect(supplementalGroups(app)).toEqual(["101", "1001"]);
    expect(worker).toContain('MFA_SECRET_KEYRING_FILE: ""');
    expect(worker).not.toContain("QA_MFA_SECRET_KEYRING_FILE is required");
    expect(supplementalGroups(worker)).not.toContain("1001");
  });

  it("makes startup validation and the operator key contract explicit", () => {
    expect(instrumentation).toContain("assertMfaSecretRuntimeConfiguration");
    expect(environmentExample).toContain("MFA_SECRET_ACTIVE_KEY_ID=");
    expect(environmentExample).toContain("MFA_SECRET_KEYRING_FILE=");
    expect(environmentExample).not.toMatch(
      /MFA_SECRET_(?:ACTIVE_)?KEY(?:RING)?[^\n]*=[A-Za-z0-9_-]{43}/u,
    );
    expect(runbook).toContain("`root:1001`");
    expect(runbook).toContain("`0440`");
    expect(runbook).toContain("Never roll back to a pre-envelope");
  });

  it("keeps backfill dry-run by default with bounded locks and zero-plaintext verification", () => {
    expect(backfill).toContain(
      'process.env.MFA_SECRET_BACKFILL_APPLY ?? "false"',
    );
    expect(backfill).toContain("MFA_SECRET_BACKFILL_EXPECTED_CANDIDATES");
    expect(backfill).toContain("MFA_SECRET_BACKFILL_EXPECTED_MANIFEST_SHA256");
    expect(backfill).toContain("candidateManifestSha256");
    expect(backfill).toContain("buildMfaSecretBackfillCandidateManifest");
    expect(backfill).toContain("FOR UPDATE");
    expect(backfill).toContain("lock_timeout = '2s'");
    expect(backfill).toContain("statement_timeout = '10s'");
    expect(backfill).toContain("current.mfaSecret !== snapshot.mfaSecret");
    expect(backfill).toContain("after.legacyPlaintextSecrets === 0");
    expect(backfill).toContain("after.legacyRecoveryVerifiers === 0");
    expect(backfill).toContain("MFA_SECRET_BACKFILL_DATABASE_URL");
    expect(backfill).toContain("requireExternalBackfillKeyring();");
    expect(backfill).toContain('runtimeEnvironment.NODE_ENV = "production"');
    expect(backfill).toContain(
      'runtimeEnvironment.QUILLMD_SERVICE_ROLE = "physician-app"',
    );
    expect(backfill.indexOf("requireExternalBackfillKeyring();")).toBeLessThan(
      backfill.indexOf("configureDedicatedDatabaseTarget();"),
    );
    expect(
      backfill.indexOf("configureDedicatedDatabaseTarget();"),
    ).toBeLessThan(backfill.indexOf('await import("@meddoc/db")'));
    expect(backfill).toContain('cardinality("mfaBackupCodes") > 0');
    expect(backfill).toContain('"mfaEnabled" = TRUE');
    expect(backfill).toContain("const censusAt = new Date()");
    expect(backfill.match(/AS "mfaVerifiedAtCanonical"/gu)).toHaveLength(3);
    expect(backfill).toContain(
      "current.mfaVerifiedAtCanonical !== snapshot.mfaVerifiedAtCanonical",
    );
    expect(backfill).toContain(
      "verifiedTimestamp: verifiedTimestamp(snapshot)",
    );
    expect(backfill).not.toContain("mfaVerifiedAt?.getTime()");
    expect(backfill).not.toContain("mfaVerifiedAt: current.mfaVerifiedAt");
    expect(backfill).toContain("incompleteEnabledEnrollments");
    expect(backfill).toContain("before.incompleteEnabledEnrollments !== 0");
    expect(backfill).toContain("after.incompleteEnabledEnrollments === 0");
    expect(backfill).toContain("userSession.deleteMany");
    expect(backfill).toContain('action: "MFA_CREDENTIALS_MIGRATED"');
    const updateCandidate = backfill.slice(
      backfill.indexOf("async function updateCandidate"),
      backfill.indexOf("function safeReport"),
    );
    const advisoryLock = updateCandidate.indexOf(
      "pg_advisory_xact_lock(73119, 20260719)",
    );
    const practiceLock = updateCandidate.indexOf('FROM "practices"');
    const userLock = updateCandidate.indexOf('FROM "users"');
    expect(advisoryLock).toBeGreaterThan(-1);
    expect(updateCandidate).toContain(
      'pg_advisory_xact_lock(73119, 20260719)::text AS "lockAcquired"',
    );
    expect(practiceLock).toBeGreaterThan(advisoryLock);
    expect(userLock).toBeGreaterThan(practiceLock);
    expect(backfill).not.toContain("console.log");
  });

  it("provisions and removes a non-committed CI keyring for every compose parse", () => {
    expect(e2eWorkflow).toContain("Provision ephemeral synthetic MFA keyring");
    expect(e2eWorkflow).toContain("randomBytes(32)");
    expect(e2eWorkflow).toContain("sudo chown root:1001");
    expect(e2eWorkflow).toContain("sudo chmod 0440");
    expect(e2eWorkflow).toContain("QA_MFA_SECRET_ACTIVE_KEY_ID=");
    expect(e2eWorkflow).toContain("QA_MFA_SECRET_KEYRING_FILE=%s");
    expect(e2eWorkflow).toContain("MFA_SECRET_ACTIVE_KEY_ID=");
    expect(e2eWorkflow).toContain("MFA_SECRET_KEYRING_FILE=%s");
    const keyringProvisioning = e2eWorkflow.slice(
      e2eWorkflow.indexOf("- name: Provision ephemeral synthetic MFA keyring"),
      e2eWorkflow.indexOf(
        "- name: Provision ephemeral synthetic database credentials",
      ),
    );
    const maskRegistration = keyringProvisioning.indexOf(
      'maskSecret("MFA key", keyBase64Url)',
    );
    const keyringWrite = keyringProvisioning.indexOf("writeFileSync(");
    const environmentWrite = keyringProvisioning.indexOf(
      "printf 'QA_MFA_SECRET_ACTIVE_KEY_ID=",
    );
    expect(keyringProvisioning).toContain("set +x");
    expect(keyringProvisioning).toContain("const maskedSecrets = new Set()");
    expect(keyringProvisioning).toContain("maskedSecrets.has(value)");
    expect(keyringProvisioning).toContain("writeSync(1, command)");
    expect(keyringProvisioning).toContain("Buffer.byteLength(command)");
    expect(keyringProvisioning).toContain("::add-mask::${value}");
    expect(keyringProvisioning).toContain("value.length === 0");
    expect(keyringProvisioning).toContain("/[\\r\\n]/u.test(value)");
    expect(maskRegistration).toBeGreaterThan(-1);
    expect(keyringWrite).toBeGreaterThan(maskRegistration);
    expect(environmentWrite).toBeGreaterThan(keyringWrite);
    expect(e2eWorkflow).toContain("Remove ephemeral synthetic MFA keyring");
    expect(e2eWorkflow).toContain('sudo rm -f -- "$keyring_path"');
    expect(e2eWorkflow).not.toMatch(
      /keyBase64Url:\s*["'][A-Za-z0-9_-]{43}["']/u,
    );
  });

  it("proves the exact non-root app image can read the mounted keyring without printing it", () => {
    const probeStart = e2eWorkflow.indexOf(
      "- name: Verify app runtime can read the MFA keyring",
    );
    expect(probeStart).toBeGreaterThan(-1);
    const probe = e2eWorkflow.slice(
      probeStart,
      e2eWorkflow.indexOf("- name: Start qa infra", probeStart),
    );
    expect(probe).toContain("--network none");
    expect(probe).toContain("--read-only");
    expect(probe).toContain("--cap-drop ALL");
    expect(probe).toContain("--group-add 101");
    expect(probe).toContain("--group-add 1001");
    expect(probe).toContain(
      '[[ "$QA_TRANSCRIBE_MD_IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]]',
    );
    expect(probe).toContain('"$QA_TRANSCRIBE_MD_IMAGE" -');
    expect(probe).toContain("process.getuid() !== 1001");
    expect(probe).toContain("process.getgid() !== 65533");
    expect(probe).toContain("const expectedGroups = [101, 1001, 65533]");
    expect(probe).toContain("groups.length !== expectedGroups.length");
    expect(probe).toContain(
      "groups.some((group, index) => group !== expectedGroups[index])",
    );
    expect(probe).toContain("stat.uid !== 0");
    expect(probe).toContain("stat.gid !== 1001");
    expect(probe).toContain("(stat.mode & 0o777) !== 0o440");
    expect(probe).toContain('readFileSync(path, "utf8")');
    expect(probe).not.toContain("console.log");
    expect(probe).not.toContain("process.stdout");
  });

  it("has a disposable PostgreSQL contention proof for the shared lock order", () => {
    expect(lockOrderPgProof).toContain(
      "MFA_SECRET_BACKFILL_LOCK_ORDER_TEST_DATABASE_URL",
    );
    expect(lockOrderPgProof).toContain(
      "pg_advisory_xact_lock(73119, 20260719)",
    );
    expect(lockOrderPgProof).toContain("waitForAdvisoryWaiter");
    expect(lockOrderPgProof).toContain(
      "SET \"mfaSecret\" = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'",
    );
    expect(lockOrderPgProof).toContain(
      'lockOrder: ["advisory", "practice", "user"]',
    );
    expect(lockOrderPgProof).toContain("deadlock: false");
  });

  it("documents residual plaintext backups and post-backfill keyring escrow proof", () => {
    expect(runbook).toContain("Pre-backfill backups are not remediated");
    expect(runbook).toContain("plaintext TOTP secrets");
    expect(runbook).toContain("legal-hold/retention policy");
    expect(runbook).toContain("keyring is separately escrowed");
  });
});
