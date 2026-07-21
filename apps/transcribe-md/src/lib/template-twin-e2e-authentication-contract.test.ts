import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(import.meta.dirname, "../../../..");
const helper = readFileSync(
  resolve(
    repositoryRoot,
    "apps/transcribe-md/tests/e2e/helpers/templateTwin.ts",
  ),
  "utf8",
);
const infrastructureScenario = readFileSync(
  resolve(
    repositoryRoot,
    "apps/transcribe-md/tests/e2e/scenarios/29-template-twin-infrastructure.spec.ts",
  ),
  "utf8",
);
const stagingScenario = readFileSync(
  resolve(
    repositoryRoot,
    "apps/transcribe-md/tests/e2e/scenarios/30-template-twin-staging-ui.spec.ts",
  ),
  "utf8",
);
const setupSources = [helper, infrastructureScenario, stagingScenario].join(
  "\n",
);

function ordered(source: string, markers: readonly string[]): void {
  let cursor = -1;
  for (const marker of markers) {
    const next = source.indexOf(marker, cursor + 1);
    expect(next, `missing or out-of-order marker: ${marker}`).toBeGreaterThan(
      cursor,
    );
    cursor = next;
  }
}

describe("Template Twin Playwright authentication and rollout setup", () => {
  it("accepts only the protected fixed synthetic fixture identities", () => {
    expect(helper).toContain("QA_TEMPLATE_TWIN_FIXTURE_IDENTITIES_FILE");
    expect(helper).toContain('"template-twin-synthetic-ci-release-fixture-v1"');
    expect(helper).toContain('"synthetic-ci-fixture/not-production"');
    expect(helper).toContain('document.phi !== "FORBIDDEN"');
    expect(helper).toContain('document.productionUse !== "FORBIDDEN"');
    expect(helper).toContain("constants.O_NOFOLLOW");
    expect(helper).toContain("(before.mode & 0o777) !== 0o600");
    expect(helper).toContain("(parent.mode & 0o777) !== 0o700");
    expect(helper).toContain("before.uid !== expectedUid");
    expect(helper).toContain("before.nlink !== 1");
    expect(helper).toContain("RANDOM_FIXTURE_PASSWORD");
    for (const marker of [
      "synthetic_ci_template_twin_infrastructure",
      "synthetic_ci_template_twin_infrastructure_doctor",
      "template-twin-infrastructure@synthetic.test",
      "synthetic_ci_template_twin_staging_primary",
      "synthetic_ci_template_twin_staging_primary_doctor",
      "template-twin-staging-primary@synthetic.test",
      "synthetic_ci_template_twin_staging_foreign",
      "synthetic_ci_template_twin_staging_foreign_doctor",
      "template-twin-staging-foreign@synthetic.test",
    ]) {
      expect(helper).toContain(marker);
    }
  });

  it("removes signup, rollout SQL mutation, and session injection bypasses", () => {
    expect(setupSources).not.toContain("setTemplateTwinQaPractice");
    expect(setupSources).not.toContain("signupSyntheticDoctor");
    expect(setupSources).not.toContain("signupFreshUser");
    expect(setupSources).not.toMatch(/goto\(["']\/signup["']\)/u);
    expect(setupSources).not.toMatch(/create account/iu);
    expect(helper).not.toMatch(
      /UPDATE\s+template_twin_rollout_controls[\s\S]{0,300}\bSET\s+enabled\s*=/u,
    );
    expect(helper).not.toMatch(/SET\s+"templateTwinEnabled"\s*=/u);
    expect(setupSources).not.toMatch(
      /storageState|addCookies|sessionToken|next-auth\.session-token/iu,
    );
  });

  it("uses real form login and preserves the primary browser session across release cycles", () => {
    const infrastructureTest = infrastructureScenario.slice(
      infrastructureScenario.indexOf('test("Template Twin:'),
    );
    ordered(infrastructureTest, [
      'readTemplateTwinSyntheticCiFixtureIdentities("infrastructure")',
      "await loginUser(page, infrastructure.doctorEmail, infrastructure.password)",
      "const disabledUpload",
      'command: "activate-cycle"',
      "await page.reload()",
      "const upload = await uploadTemplate",
      "readTemplateTwinQaInventory(\n    infrastructure.practiceId",
    ]);

    const stagingTest = stagingScenario.slice(
      stagingScenario.indexOf('test("Template Twin staging UI'),
    );
    ordered(stagingTest, [
      'readTemplateTwinSyntheticCiFixtureIdentities("staging")',
      "await loginUser(page, stagingPrimary.doctorEmail, stagingPrimary.password)",
      "const deniedFixture",
      'command: "activate-cycle"',
      "await page.reload()",
      "loginCrossTenantDoctor(browser, stagingForeign)",
      "let staleWorkerPaused = false",
      "pause transcribe-md-worker",
      "const staleAdmission",
      "replacementAttempted = true",
      'command: "replace-cycle"',
      "if (staleWorkerPaused && !replacementAttempted)",
      "unpause transcribe-md-worker",
      "await page.reload()",
      "const staleRunRead",
      'code: "ROLLOUT_CHANGED"',
    ]);
    expect(stagingScenario).toContain(
      "await loginUser(page, identity.doctorEmail, identity.password)",
    );
    expect(infrastructureScenario).toContain(
      'test.use({ trace: "off", video: "off" })',
    );
    expect(stagingScenario).toContain("let replacementAttempted = false");
  });

  it("executes one allowlisted orchestrator argument and discards all child output", () => {
    const orchestration = helper.slice(
      helper.indexOf("export function runTemplateTwinSyntheticCiOrchestrator"),
      helper.indexOf("function shellQuote"),
    );
    expect(orchestration).toContain(
      'input.command === "replace-cycle" && input.profile === "staging"',
    );
    expect(orchestration).toContain("process.env[actionVariable]");
    expect(orchestration).toContain(
      '"scripts/template-twin-synthetic-ci-orchestrator.sh"',
    );
    expect(orchestration).toMatch(
      /execFileSync\(configuredOrchestrator, \[input\.command\], \{/u,
    );
    expect(orchestration).toContain("shell: false");
    expect(orchestration).toContain('stdio: ["ignore", "ignore", "ignore"]');
    expect(orchestration).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_CI_RUNTIME_PROFILE: input.profile",
    );
    expect(orchestration).toContain(
      'timeout: input.command === "replace-cycle" ? 600_000 : 300_000',
    );
    expect(orchestration).toContain(
      'throw new Error("Template Twin synthetic CI orchestration failed closed.")',
    );
    expect(orchestration).not.toMatch(
      /console\.|stdout|stderr|encoding:|String\(error\)|shell:\s*true/u,
    );
  });

  it("keeps the remaining random suffix scoped to a synthetic idempotency key", () => {
    expect(infrastructureScenario).not.toContain("randomBytes");
    expect(infrastructureScenario).toContain("test.setTimeout(900_000)");
    expect(stagingScenario).toContain("Math.max(1_500_000");
    expect(stagingScenario.match(/idempotencySuffix/gu)).toHaveLength(2);
    expect(stagingScenario).toContain(
      "`${idempotencySuffix}-changed-fixture-upload`",
    );
    expect(stagingScenario).not.toMatch(
      /qa-template-twin-e2e[^\n]*\$\{idempotencySuffix\}/u,
    );
  });
});
