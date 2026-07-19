import { beforeEach, describe, expect, it, vi } from "vitest";

import { TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION } from "@meddoc/ai";

const mocks = vi.hoisted(() => ({ findMany: vi.fn() }));

vi.mock("@meddoc/db", () => ({
  default: { noteTemplate: { findMany: mocks.findMany } },
}));

import {
  listDoctorStagingQaTemplates,
  listDoctorTemplates,
} from "./read";

const generic = {
  id: "template-generic-synthetic-test",
  name: "Synthetic ordinary template",
  encounterType: null,
  status: "active",
  version: 1,
  sections: [],
  templateKind: "structured",
  templateTwinCompiledVersion: null,
  updatedAt: new Date("2026-07-17T00:00:00.000Z"),
};

const admitted = {
  id: "template-admitted-synthetic-test",
  name: "Template Twin — Synthetic QA fixture",
  encounterType: "family_medicine",
  status: "draft",
  version: 1,
  sections: [],
  templateKind: "template_twin_docx",
  templateTwinCompiledVersion: {
    certificationStatus: "NEEDS_CONFIRMATION",
    blockingUnsupportedCount: 0,
    _count: { fields: 8 },
  },
  updatedAt: new Date("2026-07-17T00:01:00.000Z"),
};

beforeEach(() => {
  mocks.findMany.mockReset().mockImplementation(async (query) =>
    query.where.templateTwinSyntheticQaAdmissions ? [admitted] : [generic, admitted],
  );
});

describe("note-template settings collections", () => {
  it("returns only templates linked to a current tenant-scoped staging admission", async () => {
    const result = await listDoctorStagingQaTemplates({
      doctorId: "doctor-settings@synthetic.test",
      practiceId: "practice-settings-synthetic",
      globalGeneration: BigInt(31),
      practiceGeneration: BigInt(37),
      now: new Date("2026-07-17T00:00:00.000Z"),
    });

    expect(result.map((template) => template.id)).toEqual([
      admitted.id,
    ]);
    expect(mocks.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          doctorId: "doctor-settings@synthetic.test",
          templateKind: "template_twin_docx",
          templateTwinSyntheticQaAdmissions: {
            some: expect.objectContaining({
              practiceId: "practice-settings-synthetic",
              actorId: "doctor-settings@synthetic.test",
              fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
              phase: { in: ["TEMPLATE_LINKED", "CERTIFIED"] },
              pinnedGlobalRolloutGeneration: BigInt(31),
              pinnedPracticeRolloutGeneration: BigInt(37),
              failedAt: null,
              revokedAt: null,
            }),
          },
        }),
      }),
    );
  });

  it("keeps ordinary templates unchanged outside synthetic QA", async () => {
    const result = await listDoctorTemplates(
      "doctor-settings@synthetic.test",
    );
    expect(result.map((template) => template.id)).toEqual([
      generic.id,
      admitted.id,
    ]);
  });
});
