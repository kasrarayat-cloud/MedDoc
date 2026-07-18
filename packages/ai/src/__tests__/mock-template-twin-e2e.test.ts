import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { z } from "zod";

import {
  mockComplete,
  mockCompleteText,
  mockDeepgramBatch,
  runWithLegacyTemplateTwinInfrastructureFixture,
} from "../mock";
import { TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION } from "../synthetic-qa-context";

const EntitySchema = z.object({
  chief_complaint: z
    .object({ statement: z.string(), evidence_quote: z.string() })
    .nullable(),
  hpi: z
    .object({
      onset: z.string().optional(),
      severity: z.string().optional(),
      context: z.string().optional(),
      evidence_quote: z.string(),
    })
    .nullable(),
  medications: z
    .array(z.object({ name: z.string(), evidence_quote: z.string() }))
    .default([]),
  social_history: z
    .object({
      smoking: z
        .object({ status: z.string(), evidence_quote: z.string() })
        .optional(),
    })
    .default({}),
  plan_discussed: z
    .array(z.object({ item: z.string(), evidence_quote: z.string() }))
    .default([]),
  assessment_discussed: z
    .array(z.object({ finding: z.string(), evidence_quote: z.string() }))
    .default([]),
});

const IcdSchema = z.object({
  codes: z.array(
    z.object({
      code: z.string(),
      description: z.string(),
      evidence_quote: z.string(),
      confidence: z.number(),
      confidenceLevel: z.enum(["high", "medium", "low"]),
    }),
  ),
});

const CptSchema = z.object({
  em: z
    .object({
      code: z.string(),
      description: z.string(),
      reasoning: z.object({
        problems: z.array(
          z.object({ description: z.string(), status: z.string() }),
        ),
        data: z.string(),
        risk: z.enum(["minimal", "low", "moderate", "high"]),
      }),
      evidence_quote: z.string(),
    })
    .nullable(),
  procedures: z.array(z.unknown()).default([]),
  modifiers: z.array(z.unknown()).default([]),
});

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  process.env = { ...ORIGINAL_ENV };
  process.env.MOCK_AI_CALLS = "true";
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("Template Twin infrastructure-E2E model fixture", () => {
  it("preserves the existing empty entity fixture by default", () => {
    const result = mockComplete({
      purpose: "tm_entities",
      schema: EntitySchema,
    });

    expect(result).toMatchObject({
      chief_complaint: null,
      hpi: null,
    });
  });

  it("preserves the existing generic transcription fixture by default", () => {
    const result = mockDeepgramBatch();

    expect(result.transcript).toContain("My head has been aching");
    expect(result.transcript).not.toContain("Syntheticmed");
  });

  it("preserves the existing generic SOAP fixture by default", () => {
    for (const purpose of ["tm_soap_draft", "tm_polish"] as const) {
      const result = mockCompleteText({ purpose });
      expect(result.text).toContain("tension headache");
      expect(result.text).not.toContain("Syntheticmed");
    }
  });

  it("returns fully synthetic, evidence-bearing entities for the explicit fixture profile", () => {
    const result = mockComplete({
      purpose: "tm_entities",
      schema: EntitySchema,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    });

    expect(result).toEqual({
      chief_complaint: {
        statement: "synthetic wrist discomfort",
        evidence_quote: "Chief concern is synthetic wrist discomfort.",
      },
      hpi: {
        onset: "2099-07-16",
        severity: "Moderate",
        context: "Explicit synthetic detail",
        evidence_quote:
          "Synthetic wrist discomfort began on 2099-07-16 with Moderate severity and context Explicit synthetic detail.",
      },
      medications: [
        {
          name: "Syntheticmed",
          evidence_quote: "Medication Syntheticmed documented.",
        },
      ],
      social_history: {
        smoking: {
          status: "Current",
          evidence_quote: "Smoking status is Current.",
        },
      },
      plan_discussed: [
        {
          item: "Use synthetic brace",
          evidence_quote: "Plan use synthetic brace.",
        },
      ],
      assessment_discussed: [
        {
          finding: "Follow-up",
          evidence_quote: "Encounter category is Follow-up.",
        },
      ],
    });
  });

  it("returns a transcript containing every synthetic evidence quote under the same gates", () => {
    const entities = mockComplete({
      purpose: "tm_entities",
      schema: EntitySchema,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    });
    const transcription = mockDeepgramBatch(
      TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    );
    const evidenceQuotes = [
      entities.chief_complaint?.evidence_quote,
      entities.hpi?.evidence_quote,
      entities.social_history.smoking?.evidence_quote,
      ...entities.medications.map((item) => item.evidence_quote),
      ...entities.plan_discussed.map((item) => item.evidence_quote),
      ...entities.assessment_discussed.map((item) => item.evidence_quote),
    ].filter((quote): quote is string => typeof quote === "string");

    expect(evidenceQuotes).toHaveLength(6);
    for (const quote of evidenceQuotes) {
      expect(transcription.transcript).toContain(quote);
    }
  });

  it("keeps the draft and polished SOAP aligned with the exact synthetic facts", () => {
    for (const purpose of ["tm_soap_draft", "tm_polish"] as const) {
      const result = mockCompleteText({
        purpose,
        fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      });
      expect(result.text).toContain("synthetic wrist discomfort");
      expect(result.text).toContain("Current");
      expect(result.text).toContain("Syntheticmed");
      expect(result.text).toContain("synthetic brace");
      expect(result.text).toContain("2099-07-16");
      expect(result.text).toContain("Follow-up");
      expect(result.text).toContain("Explicit synthetic detail");
      expect(result.text).not.toContain("headache");
    }
  });

  it("provides non-empty evidence-bound coding fixtures only for admitted staging", () => {
    const icd = mockComplete({
      purpose: "tm_icd_coding",
      schema: IcdSchema,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    });
    const cpt = mockComplete({
      purpose: "tm_cpt_coding",
      schema: CptSchema,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    });
    expect(icd.codes).toEqual([
      expect.objectContaining({
        code: "M25.50",
        evidence_quote: "synthetic wrist discomfort",
      }),
    ]);
    expect(cpt.em).toEqual(
      expect.objectContaining({
        code: "99212",
        evidence_quote: "Encounter category is Follow-up.",
      }),
    );

    expect(
      mockComplete({ purpose: "tm_icd_coding", schema: IcdSchema }).codes,
    ).toEqual([]);
    expect(
      mockComplete({ purpose: "tm_cpt_coding", schema: CptSchema }).em,
    ).toBeNull();
  });

  it("temporarily preserves the legacy triple-gated certification harness", async () => {
    process.env.MOCK_TEMPLATE_TWIN_E2E = "true";
    process.env.DATABASE_URL = "postgresql:///meddoc_qa_test";
    const { result, soap, transcription } =
      await runWithLegacyTemplateTwinInfrastructureFixture(() => ({
        result: mockComplete({
          purpose: "tm_entities",
          schema: EntitySchema,
          visitId: "legacy-template-twin-qa-visit",
        }),
        soap: mockCompleteText({
          purpose: "tm_soap_draft",
          visitId: "legacy-template-twin-qa-visit",
        }),
        transcription: mockDeepgramBatch(
          undefined,
          "legacy-template-twin-qa-visit",
        ),
      }));

    expect(result.medications).toEqual([
      expect.objectContaining({ name: "Syntheticmed" }),
    ]);
    expect(result.hpi).toBeNull();
    expect(soap.text).toContain("Syntheticmed");
    expect(soap.text).not.toContain("2099-");
    expect(transcription.transcript).toContain("Syntheticmed");
    expect(transcription.transcript).not.toContain("2099-");
  });

  it.each([
    ["mock mode off", { MOCK_AI_CALLS: "false" }],
    ["dedicated flag off", { MOCK_TEMPLATE_TWIN_E2E: "false" }],
    ["unsafe database", { DATABASE_URL: "postgresql:///meddoc" }],
    ["missing database", { DATABASE_URL: "" }],
  ])(
    "keeps the legacy compatibility fixture fail-closed when %s",
    (_label, overrides) => {
      process.env.MOCK_TEMPLATE_TWIN_E2E = "true";
      process.env.DATABASE_URL = "postgresql:///meddoc_qa_test";
      Object.assign(process.env, overrides);

      const result = mockComplete({
        purpose: "tm_entities",
        schema: EntitySchema,
      });
      expect(result.chief_complaint).toBeNull();
      expect(result.medications).toEqual([]);
    },
  );
});
