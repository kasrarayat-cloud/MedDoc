import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

import {
  APPROVED_POLICY_SHA256,
  loadPolicy,
  verifyServerActionManifest,
  verifySourceCensus,
} from "../server-action-manifest-gate.mjs";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = path.resolve(TEST_DIR, "..", "..");
const POLICY_PATH = path.join(
  PROJECT_DIR,
  "scripts",
  "server-action-policy.json",
);
const temporaryDirectories = [];

afterEach(async () => {
  await Promise.all(
    temporaryDirectories
      .splice(0)
      .map((directory) => fs.rm(directory, { recursive: true, force: true })),
  );
});

async function temporaryProject() {
  const directory = await fs.mkdtemp(
    path.join(os.tmpdir(), "server-action-gate-"),
  );
  temporaryDirectories.push(directory);
  await fs.mkdir(path.join(directory, "src", "actions"), { recursive: true });
  return directory;
}

async function fixturePolicy(directory, actions, overrides = {}) {
  const classifications = [
    "AUTH_ENTRYPOINT",
    "SELF_SESSION",
    "PHYSICIAN_CLINICAL",
  ];
  const classificationCounts = Object.fromEntries(
    classifications.map((classification) => [
      classification,
      actions.filter((action) => action.classification === classification)
        .length,
    ]),
  );
  const policyActions = actions.map(
    ({ module, exportedName, classification }) => ({
      module,
      exportedName,
      classification,
    }),
  );
  const expectedCompiledExclusions = actions
    .filter((action) => action.compiled === false)
    .map(({ module, exportedName }) => ({ module, exportedName }));
  const policy = {
    schemaVersion: 2,
    nextMajor: 16,
    expectedModuleCount: new Set(actions.map((action) => action.module)).size,
    expectedActionCount: actions.length,
    expectedCompiledActionCount:
      actions.length - expectedCompiledExclusions.length,
    expectedCompiledExclusions,
    expectedClassificationCounts: classificationCounts,
    actions: policyActions,
    ...overrides,
  };
  const filename = path.join(directory, "policy.json");
  await fs.writeFile(filename, JSON.stringify(policy));
  return filename;
}

function fixtureManifest(entries) {
  return {
    node: Object.fromEntries(
      entries.map((entry, index) => [
        `action-${index}`,
        {
          filename: entry.module,
          exportedName: entry.exportedName,
          workers: { "app/page": { moduleId: index, async: true } },
        },
      ]),
    ),
    edge: {},
    encryptionKey: "synthetic-test-key",
  };
}

describe("Server Action source and compiled-manifest gate", () => {
  it("locks the complete current source census and classifications", async () => {
    const result = await verifySourceCensus({
      projectDir: PROJECT_DIR,
      policyPath: POLICY_PATH,
    });

    expect(result.policyDigest).toBe(APPROVED_POLICY_SHA256);
    expect(result.sourceModuleCount).toBe(14);
    expect(result.sourceActionCount).toBe(30);
    expect(result.policy.expectedClassificationCounts).toEqual({
      AUTH_ENTRYPOINT: 2,
      SELF_SESSION: 3,
      PHYSICIAN_CLINICAL: 25,
    });
  }, 30_000);

  it("classifies every compiled identity without depending on action IDs", async () => {
    const directory = await temporaryProject();
    const actions = [
      {
        module: "src/actions/auth.ts",
        exportedName: "loginAction",
        classification: "AUTH_ENTRYPOINT",
      },
      {
        module: "src/actions/visits.ts",
        exportedName: "createVisitAction",
        classification: "PHYSICIAN_CLINICAL",
      },
    ];
    await fs.writeFile(
      path.join(directory, "src", "actions", "auth.ts"),
      '"use server"; export async function loginAction() {}',
    );
    await fs.writeFile(
      path.join(directory, "src", "actions", "visits.ts"),
      '"use server"; export async function createVisitAction() {}',
    );
    const policyPath = await fixturePolicy(directory, actions);
    const manifestPath = path.join(directory, "manifest.json");
    await fs.writeFile(manifestPath, JSON.stringify(fixtureManifest(actions)));

    const result = await verifyServerActionManifest({
      projectDir: directory,
      policyPath,
      manifestPath,
      expectedPolicySha256: null,
      verifyInstalledNext: false,
    });

    expect(result.compiledActionCount).toBe(2);
    expect(result.compiledClassificationCounts).toEqual({
      AUTH_ENTRYPOINT: 1,
      SELF_SESSION: 0,
      PHYSICIAN_CLINICAL: 1,
    });
  });

  it("binds the policy to the installed Next 16 manifest contract", async () => {
    const { policy } = await loadPolicy(POLICY_PATH);
    const exclusions = new Set(
      policy.expectedCompiledExclusions.map(
        (action) => `${action.module}#${action.exportedName}`,
      ),
    );
    const expectedCompiledActions = policy.actions.filter(
      (action) => !exclusions.has(`${action.module}#${action.exportedName}`),
    );
    const directory = await temporaryProject();
    const manifestPath = path.join(directory, "manifest.json");
    await fs.writeFile(
      manifestPath,
      JSON.stringify(fixtureManifest(expectedCompiledActions)),
    );

    const result = await verifyServerActionManifest({
      projectDir: PROJECT_DIR,
      policyPath: POLICY_PATH,
      manifestPath,
    });

    expect(result.installedNextVersion).toMatch(/^16\./);
    expect(result.compiledActionCount).toBe(28);
  });

  it("allows only the exact source exports recorded as compiled exclusions", async () => {
    const directory = await temporaryProject();
    const actions = [
      {
        module: "src/actions/auth.ts",
        exportedName: "loginAction",
        classification: "AUTH_ENTRYPOINT",
      },
      {
        module: "src/actions/patients.ts",
        exportedName: "loadMorePatientsAction",
        classification: "PHYSICIAN_CLINICAL",
        compiled: false,
      },
    ];
    await fs.writeFile(
      path.join(directory, "src", "actions", "auth.ts"),
      '"use server"; export async function loginAction() {}',
    );
    await fs.writeFile(
      path.join(directory, "src", "actions", "patients.ts"),
      '"use server"; export async function loadMorePatientsAction() {}',
    );
    const policyPath = await fixturePolicy(directory, actions);
    const manifestPath = path.join(directory, "manifest.json");
    await fs.writeFile(
      manifestPath,
      JSON.stringify(fixtureManifest([actions[0]])),
    );

    await expect(
      verifyServerActionManifest({
        projectDir: directory,
        policyPath,
        manifestPath,
        expectedPolicySha256: null,
        verifyInstalledNext: false,
      }),
    ).resolves.toMatchObject({ compiledActionCount: 1 });

    await fs.writeFile(manifestPath, JSON.stringify(fixtureManifest(actions)));
    await expect(
      verifyServerActionManifest({
        projectDir: directory,
        policyPath,
        manifestPath,
        expectedPolicySha256: null,
        verifyInstalledNext: false,
      }),
    ).rejects.toThrow(
      "unexpected=[src/actions/patients.ts#loadMorePatientsAction]",
    );
  });

  it("rejects compiled actions without a worker route", async () => {
    const directory = await temporaryProject();
    const actions = [
      {
        module: "src/actions/auth.ts",
        exportedName: "loginAction",
        classification: "AUTH_ENTRYPOINT",
      },
    ];
    await fs.writeFile(
      path.join(directory, "src", "actions", "auth.ts"),
      '"use server"; export async function loginAction() {}',
    );
    const policyPath = await fixturePolicy(directory, actions);
    const manifest = fixtureManifest(actions);
    Object.values(manifest.node)[0].workers = {};
    const manifestPath = path.join(directory, "manifest.json");
    await fs.writeFile(manifestPath, JSON.stringify(manifest));

    await expect(
      verifyServerActionManifest({
        projectDir: directory,
        policyPath,
        manifestPath,
        expectedPolicySha256: null,
        verifyInstalledNext: false,
      }),
    ).rejects.toThrow("missing identity or workers");
  });

  it("fails closed on a new unclassified source export", async () => {
    const directory = await temporaryProject();
    const actions = [
      {
        module: "src/actions/auth.ts",
        exportedName: "loginAction",
        classification: "AUTH_ENTRYPOINT",
      },
    ];
    await fs.writeFile(
      path.join(directory, "src", "actions", "auth.ts"),
      '"use server"; export async function loginAction() {} export async function surprise() {}',
    );
    const policyPath = await fixturePolicy(directory, actions);

    await expect(
      verifySourceCensus({
        projectDir: directory,
        policyPath,
        expectedPolicySha256: null,
      }),
    ).rejects.toThrow("unknown=[src/actions/auth.ts#surprise]");
  });

  it("fails closed on an inline Server Function", async () => {
    const directory = await temporaryProject();
    await fs.writeFile(
      path.join(directory, "src", "actions", "inline.ts"),
      'export function wrapper() { async function hidden() { "use server"; } return hidden; }',
    );
    const policyPath = await fixturePolicy(directory, []);

    await expect(
      verifySourceCensus({
        projectDir: directory,
        policyPath,
        expectedPolicySha256: null,
      }),
    ).rejects.toThrow("inline Server Function is not allowed");
  });

  it("fails closed on an unknown compiled export", async () => {
    const directory = await temporaryProject();
    const actions = [
      {
        module: "src/actions/auth.ts",
        exportedName: "loginAction",
        classification: "AUTH_ENTRYPOINT",
      },
    ];
    await fs.writeFile(
      path.join(directory, "src", "actions", "auth.ts"),
      '"use server"; export async function loginAction() {}',
    );
    const policyPath = await fixturePolicy(directory, actions);
    const manifestPath = path.join(directory, "manifest.json");
    await fs.writeFile(
      manifestPath,
      JSON.stringify(
        fixtureManifest([
          ...actions,
          {
            module: "src/actions/auth.ts",
            exportedName: "unreviewedAction",
          },
        ]),
      ),
    );

    await expect(
      verifyServerActionManifest({
        projectDir: directory,
        policyPath,
        manifestPath,
        expectedPolicySha256: null,
        verifyInstalledNext: false,
      }),
    ).rejects.toThrow("unclassified=[src/actions/auth.ts#unreviewedAction]");
  });

  it("fails closed when a classified source export is absent from the compiled manifest", async () => {
    const directory = await temporaryProject();
    const actions = [
      {
        module: "src/actions/auth.ts",
        exportedName: "loginAction",
        classification: "AUTH_ENTRYPOINT",
      },
      {
        module: "src/actions/visits.ts",
        exportedName: "createVisitAction",
        classification: "PHYSICIAN_CLINICAL",
      },
    ];
    await fs.writeFile(
      path.join(directory, "src", "actions", "auth.ts"),
      '"use server"; export async function loginAction() {}',
    );
    await fs.writeFile(
      path.join(directory, "src", "actions", "visits.ts"),
      '"use server"; export async function createVisitAction() {}',
    );
    const policyPath = await fixturePolicy(directory, actions);
    const manifestPath = path.join(directory, "manifest.json");
    await fs.writeFile(
      manifestPath,
      JSON.stringify(fixtureManifest([actions[0]])),
    );

    await expect(
      verifyServerActionManifest({
        projectDir: directory,
        policyPath,
        manifestPath,
        expectedPolicySha256: null,
        verifyInstalledNext: false,
      }),
    ).rejects.toThrow("missing=[src/actions/visits.ts#createVisitAction]");
  });

  it("requires an explicit review-lock update for reclassification", async () => {
    const policy = JSON.parse(await fs.readFile(POLICY_PATH, "utf8"));
    policy.actions.find(
      (action) => action.exportedName === "loginAction",
    ).classification = "PHYSICIAN_CLINICAL";
    policy.expectedClassificationCounts.AUTH_ENTRYPOINT -= 1;
    policy.expectedClassificationCounts.PHYSICIAN_CLINICAL += 1;
    const directory = await temporaryProject();
    const changedPolicyPath = path.join(directory, "changed-policy.json");
    await fs.writeFile(changedPolicyPath, JSON.stringify(policy));

    await expect(loadPolicy(changedPolicyPath)).rejects.toThrow(
      "policy classification or census changed",
    );
  });

  it("fails closed when the Next manifest schema changes", async () => {
    const directory = await temporaryProject();
    const actions = [
      {
        module: "src/actions/auth.ts",
        exportedName: "loginAction",
        classification: "AUTH_ENTRYPOINT",
      },
    ];
    await fs.writeFile(
      path.join(directory, "src", "actions", "auth.ts"),
      '"use server"; export async function loginAction() {}',
    );
    const policyPath = await fixturePolicy(directory, actions);
    const manifest = fixtureManifest(actions);
    manifest.unreviewedFrameworkField = true;
    const manifestPath = path.join(directory, "manifest.json");
    await fs.writeFile(manifestPath, JSON.stringify(manifest));

    await expect(
      verifyServerActionManifest({
        projectDir: directory,
        policyPath,
        manifestPath,
        expectedPolicySha256: null,
        verifyInstalledNext: false,
      }),
    ).rejects.toThrow("compiled manifest root keys changed");
  });
});
