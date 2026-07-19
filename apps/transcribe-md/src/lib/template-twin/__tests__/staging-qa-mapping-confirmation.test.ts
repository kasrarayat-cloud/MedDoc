import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ findTemplate: vi.fn() }));

vi.mock("@meddoc/db", () => ({
  default: { noteTemplate: { findFirst: mocks.findTemplate } },
}));

import { buildTemplateTwinIntegrationFixture } from "./integration-fixture";
import { templateTwinFieldIntentsSha256 } from "../field-intent";
import { templateTwinMappingsSha256 } from "../mapping-hash";
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "../staging-qa-fixtures";
import { confirmTemplateTwinStagingQaMappings } from "../staging-qa-mapping-confirmation";

beforeEach(() => vi.clearAllMocks());

describe("staging QA durable mapping confirmation", () => {
  it("accepts only the exact current mapping and intent hashes", async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    mocks.findTemplate.mockResolvedValue({
      templateTwinCompiledVersion: {
        compiledDocumentIr: fixture.ir,
        fields: fixture.mappings.map((mapping, displayOrder) => ({
          id: `field-row-${displayOrder}`,
          fieldId: mapping.fieldId,
          mapping: {
            ...mapping,
            mappingStatus: "CERTIFIED",
          },
          intentDecisions: [],
        })),
      },
    });
    const mappingsSha256 = templateTwinMappingsSha256(fixture.mappings);
    const fieldIntentsSha256 = templateTwinFieldIntentsSha256([]);
    const base = {
      noteTemplateId: "template-staging-mapping",
      doctorId: "doctor-staging-mapping",
      practiceId: "practice-staging-mapping",
      source: {
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      },
    };

    await expect(
      confirmTemplateTwinStagingQaMappings({
        ...base,
        expected: { mappingsSha256, fieldIntentsSha256 },
      }),
    ).resolves.toBe(true);
    await expect(
      confirmTemplateTwinStagingQaMappings({
        ...base,
        expected: {
          mappingsSha256: "f".repeat(64),
          fieldIntentsSha256,
        },
      }),
    ).resolves.toBe(false);
    await expect(
      confirmTemplateTwinStagingQaMappings({
        ...base,
        expected: {
          mappingsSha256,
          fieldIntentsSha256: "e".repeat(64),
        },
      }),
    ).resolves.toBe(false);
  });
});
