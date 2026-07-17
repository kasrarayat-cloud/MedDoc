import { describe, expect, it } from "vitest";

import { compileTemplateDocx } from "../../note-template-docx/compiler";
import { assertTemplateTwinSourcePhiFree } from "../source-phi";
import {
  buildTemplateTwinStagingQaDocx,
  isTemplateTwinStagingQaFixtureSource,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
  TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER,
  TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT,
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  templateTwinStagingQaFixtureDescriptor,
  templateTwinStagingQaSha256,
} from "../staging-qa-fixtures";

describe("Template Twin staging QA fixture", () => {
  it("rebuilds to identical bytes without relying on a cached buffer", async () => {
    const first = await buildTemplateTwinStagingQaDocx();
    const second = await buildTemplateTwinStagingQaDocx();

    expect(first).not.toBe(second);
    expect(first.equals(second)).toBe(true);
    expect(templateTwinStagingQaSha256(first)).toBe(
      templateTwinStagingQaSha256(second),
    );
  });

  it("uses the shared version and compiles through the production compiler", async () => {
    const fixture = await templateTwinStagingQaFixtureDescriptor();
    const ir = compileTemplateDocx(fixture.bytes);

    expect(fixture.fixtureVersion).toBe(
      TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    );
    expect(fixture.sha256).toBe(TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256);
    expect(fixture.sizeBytes).toBe(TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES);
    expect(ir.fields.length).toBeGreaterThanOrEqual(8);
    expect(ir.stats.dropdowns).toBeGreaterThanOrEqual(1);
    expect(ir.stats.checkboxes).toBeGreaterThanOrEqual(1);
    expect(ir.stats.tables).toBeGreaterThanOrEqual(1);
  });

  it("passes the production pre-storage privacy gate without a staging bypass", async () => {
    const fixture = await templateTwinStagingQaFixtureDescriptor();
    const evidence = await assertTemplateTwinSourcePhiFree({
      source: fixture.bytes,
      practiceId: "practice-synthetic-qa",
      userId: "doctor-synthetic-qa",
      staticAssetApprovalResolver: async () => [],
      client: {
        complete: async () => ({ phiFields: [], anyUncertain: false }),
      } as never,
    });

    expect(evidence.scannedPartCount).toBeGreaterThan(0);
    expect(evidence.approvedStaticAssetUsedCount).toBe(0);
  });

  it("pins all intended deterministic values in both evidence modes", () => {
    expect(TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER).toBe(
      TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT,
    );
    for (const value of [
      "synthetic wrist discomfort",
      "Current",
      "Follow-up",
      "2099-07-16",
      "synthetic cough",
      "Syntheticmed",
      "synthetic brace",
      "Explicit synthetic detail",
    ]) {
      expect(TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT).toContain(value);
    }
  });

  it("recognizes staging UI provenance only from the exact source digest and byte count", () => {
    expect(
      isTemplateTwinStagingQaFixtureSource({
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      }),
    ).toBe(true);
    expect(
      isTemplateTwinStagingQaFixtureSource({
        sha256: "0".repeat(64),
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      }),
    ).toBe(false);
    expect(
      isTemplateTwinStagingQaFixtureSource({
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES + 1,
      }),
    ).toBe(false);
  });
});
