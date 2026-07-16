// Client-safe certified scalar field specification contract. This module has
// no model, filesystem, Node crypto, database, or runtime-provider imports so
// certification UI/API boundaries can share the exact same Zod contract.

import { z } from "zod";

export const TEMPLATE_FIELD_SPECIFICATION_VERSION =
  "template-twin-field-specification/1.1.0" as const;

// Safe-alpha limits are intentionally much smaller than the surrounding DOCX
// field limits. Every option/unit must be exercised and every example is sent
// through bounded privacy and extraction gates, so admitting an unbounded
// specification set would create both an availability risk and dishonest test
// coverage.
export const TEMPLATE_TWIN_CUSTOM_FIELD_LIMIT = 12;
export const TEMPLATE_TWIN_CUSTOM_EXAMPLE_LIMIT = 60;
export const TEMPLATE_TWIN_CUSTOM_EXAMPLE_TEXT_LIMIT = 8_000;
export const TEMPLATE_TWIN_CUSTOM_OPTION_LIMIT = 16;
export const TEMPLATE_TWIN_CUSTOM_UNIT_LIMIT = 16;
export const TEMPLATE_TWIN_RESERVED_SYNTHETIC_DATE_YEAR = 2099;

const CUSTOM_CONCEPT_ID = /^ttcustom_[a-f0-9]{24}$/;
const FIELD_ID = /^ttf_[a-f0-9]{24}$/;
const SHA256 = /^[a-f0-9]{64}$/;

export const CustomScalarDataTypeSchema = z.enum([
  "narrative_text",
  "number",
  "measurement",
  "date",
  "boolean",
  "single_select",
]);
export type CustomScalarDataType = z.infer<typeof CustomScalarDataTypeSchema>;

export const CustomScalarValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
]);
export type CustomScalarValue = z.infer<typeof CustomScalarValueSchema>;

const AllowedOptionSchema = z
  .object({
    ordinal: z.number().int().nonnegative(),
    value: z.string().min(1).max(240),
    displayText: z.string().min(1).max(240),
  })
  .strict();

const PermittedUnitConversionSchema = z
  .object({
    from: z.string().min(1).max(40),
    to: z.string().min(1).max(40),
    multiplier: z.number().finite().positive(),
    offset: z.number().finite(),
  })
  .strict();

const SyntheticPositiveExampleSchema = z
  .object({
    exampleId: z.string().min(1).max(80),
    syntheticEvidence: z.string().min(10).max(2_000),
    expectedValue: CustomScalarValueSchema,
    expectedUnit: z.string().min(1).max(40).nullable(),
    expectedStatus: z.enum(["supported", "explicitly_denied"]).optional(),
  })
  .strict();

const SyntheticNegativeExampleSchema = z
  .object({
    exampleId: z.string().min(1).max(80),
    syntheticEvidence: z.string().min(10).max(2_000),
    prohibitedValue: CustomScalarValueSchema.nullable(),
    reason: z.string().min(1).max(500),
  })
  .strict();

const SyntheticAmbiguityExampleSchema = z
  .object({
    exampleId: z.string().min(1).max(80),
    syntheticEvidence: z.string().min(10).max(2_000),
    possibleValues: z.array(CustomScalarValueSchema).min(1).max(8),
    reason: z.string().min(1).max(500),
  })
  .strict();

export const TemplateFieldSpecificationContentSchema = z
  .object({
    specificationVersion: z.literal(TEMPLATE_FIELD_SPECIFICATION_VERSION),
    templateLineageId: z.string().min(1).max(160),
    compiledVersionId: z.string().min(1).max(160),
    fieldId: z.string().regex(FIELD_ID),
    conceptId: z.string().regex(CUSTOM_CONCEPT_ID),
    physicianName: z.string().min(1).max(160),
    physicianDescription: z.string().min(1).max(1_000),
    approvedEvidenceCues: z
      .array(z.string().trim().min(2).max(120))
      .min(1)
      .max(12),
    dataType: CustomScalarDataTypeSchema,
    allowedOptions: z
      .array(AllowedOptionSchema)
      .max(TEMPLATE_TWIN_CUSTOM_OPTION_LIMIT),
    allowedUnits: z
      .array(z.string().min(1).max(40))
      .max(TEMPLATE_TWIN_CUSTOM_UNIT_LIMIT),
    permittedUnitConversions: z
      .array(PermittedUnitConversionSchema)
      .max(TEMPLATE_TWIN_CUSTOM_UNIT_LIMIT),
    allowedTemporalities: z
      .array(z.enum(["current", "historical", "planned", "unknown"]))
      .min(1)
      .max(4),
    allowedLateralities: z
      .array(
        z.enum([
          "left",
          "right",
          "bilateral",
          "midline",
          "not_applicable",
          "unknown",
        ]),
      )
      .min(1)
      .max(6),
    polarityPolicy: z
      .object({
        allowExplicitDenial: z.boolean(),
        exactDeniedOutput: CustomScalarValueSchema.nullable(),
      })
      .strict(),
    required: z.boolean(),
    unknownPolicy: z.enum(["blank", "not_documented", "requires_input"]),
    maximumLength: z.number().int().min(1).max(4_000).nullable(),
    numericRange: z
      .object({
        minimum: z.number().finite().nullable(),
        maximum: z.number().finite().nullable(),
      })
      .strict()
      .nullable(),
    evidenceRequirements: z
      .object({
        minimumAnchors: z.number().int().min(1).max(5),
        acceptedEvidenceQualities: z
          .array(z.enum(["direct", "unclear"]))
          .min(1)
          .max(2),
      })
      .strict(),
    positiveSyntheticExamples: z
      .array(SyntheticPositiveExampleSchema)
      .min(1)
      .max(20),
    negativeSyntheticExamples: z
      .array(SyntheticNegativeExampleSchema)
      .min(1)
      .max(20),
    ambiguitySyntheticExamples: z
      .array(SyntheticAmbiguityExampleSchema)
      .min(1)
      .max(20),
  })
  .strict()
  .superRefine((specification, context) => {
    const normalizedCues = new Set<string>();
    for (const cue of specification.approvedEvidenceCues) {
      const normalized = cue.normalize("NFKC").replace(/\s+/gu, " ").toLowerCase();
      if (normalizedCues.has(normalized)) {
        context.addIssue({
          code: "custom",
          message: "Approved evidence cues must be unique.",
          path: ["approvedEvidenceCues"],
        });
      }
      normalizedCues.add(normalized);
    }
    const explicitSyntheticMarker =
      /\b(?:synthetic|fictional|mock(?:ed)?|test[- ]?only|example)\b/iu;
    for (const [collection, examples] of [
      ["positiveSyntheticExamples", specification.positiveSyntheticExamples],
      ["negativeSyntheticExamples", specification.negativeSyntheticExamples],
      ["ambiguitySyntheticExamples", specification.ambiguitySyntheticExamples],
    ] as const) {
      const exampleIds = new Set<string>();
      for (const example of examples) {
        if (exampleIds.has(example.exampleId)) {
          context.addIssue({
            code: "custom",
            message: "Synthetic example IDs must be unique within each example kind.",
            path: [collection],
          });
        }
        exampleIds.add(example.exampleId);
      }
      if (
        examples.some(
          (example) => !explicitSyntheticMarker.test(example.syntheticEvidence),
        )
      ) {
        context.addIssue({
          code: "custom",
          message:
            "Every certification example must be explicitly labeled synthetic, fictional, mock, test-only, or example data.",
          path: [collection],
        });
      }
    }
    const optionValues = new Set<string>();
    const optionOrdinals = new Set<number>();
    const optionLiteralOwner = new Map<string, number>();
    for (const option of specification.allowedOptions) {
      if (optionValues.has(option.value)) {
        context.addIssue({
          code: "custom",
          message: "Single-select option values must be unique.",
          path: ["allowedOptions"],
        });
      }
      if (optionOrdinals.has(option.ordinal)) {
        context.addIssue({
          code: "custom",
          message: "Single-select option ordinals must be unique.",
          path: ["allowedOptions"],
        });
      }
      optionValues.add(option.value);
      optionOrdinals.add(option.ordinal);
      for (const literal of new Set([option.value, option.displayText])) {
        const normalizedLiteral = literal
          .normalize("NFKC")
          .replace(/\s+/gu, " ")
          .trim()
          .toLowerCase();
        const owner = optionLiteralOwner.get(normalizedLiteral);
        if (owner !== undefined && owner !== option.ordinal) {
          context.addIssue({
            code: "custom",
            message:
              "Every single-select value and display label must identify exactly one option after case and whitespace normalization.",
            path: ["allowedOptions"],
          });
        } else {
          optionLiteralOwner.set(normalizedLiteral, option.ordinal);
        }
      }
    }

    if (
      specification.dataType === "single_select" &&
      specification.allowedOptions.length === 0
    ) {
      context.addIssue({
        code: "custom",
        message: "A single-select custom field requires exact allowed options.",
        path: ["allowedOptions"],
      });
    }
    if (
      specification.dataType !== "single_select" &&
      specification.allowedOptions.length > 0
    ) {
      context.addIssue({
        code: "custom",
        message: "Only a single-select custom field may define options.",
        path: ["allowedOptions"],
      });
    }
    if (
      specification.dataType === "measurement" &&
      specification.allowedUnits.length === 0
    ) {
      context.addIssue({
        code: "custom",
        message: "A measurement custom field requires an exact unit allowlist.",
        path: ["allowedUnits"],
      });
    }
    if (
      specification.dataType !== "measurement" &&
      (specification.allowedUnits.length > 0 ||
        specification.permittedUnitConversions.length > 0)
    ) {
      context.addIssue({
        code: "custom",
        message: "Only a measurement custom field may define units.",
        path: ["allowedUnits"],
      });
    }
    const allowedUnits = new Set(specification.allowedUnits);
    const canonicalUnits = new Set<string>();
    for (const unit of specification.allowedUnits) {
      const canonicalUnit = unit.normalize("NFKC").replace(/\s+/gu, " ").trim();
      if (canonicalUnit !== unit || canonicalUnits.has(canonicalUnit)) {
        context.addIssue({
          code: "custom",
          message:
            "Allowed units must be unique exact NFKC strings with bounded whitespace; unit case is clinically significant.",
          path: ["allowedUnits"],
        });
      }
      canonicalUnits.add(canonicalUnit);
    }
    for (const conversion of specification.permittedUnitConversions) {
      if (
        !allowedUnits.has(conversion.from) ||
        !allowedUnits.has(conversion.to)
      ) {
        context.addIssue({
          code: "custom",
          message: "Every permitted conversion must use allowlisted units.",
          path: ["permittedUnitConversions"],
        });
      }
    }
    if (specification.permittedUnitConversions.length > 0) {
      context.addIssue({
        code: "custom",
        message:
          "Automatic unit conversion is not supported in scalar v1; list only exact encounter units.",
        path: ["permittedUnitConversions"],
      });
    }
    if (
      specification.numericRange !== null &&
      specification.dataType !== "number" &&
      specification.dataType !== "measurement"
    ) {
      context.addIssue({
        code: "custom",
        message: "Only numbers and measurements may define a numeric range.",
        path: ["numericRange"],
      });
    }
    if (
      specification.numericRange !== null &&
      specification.numericRange.minimum !== null &&
      specification.numericRange.maximum !== null &&
      specification.numericRange.minimum > specification.numericRange.maximum
    ) {
      context.addIssue({
        code: "custom",
        message: "The numeric minimum cannot exceed the maximum.",
        path: ["numericRange"],
      });
    }
    if (
      specification.maximumLength !== null &&
      specification.dataType !== "narrative_text"
    ) {
      context.addIssue({
        code: "custom",
        message: "Only narrative text uses maximumLength in scalar v1.",
        path: ["maximumLength"],
      });
    }
    if (
      specification.polarityPolicy.allowExplicitDenial !==
      (specification.polarityPolicy.exactDeniedOutput !== null)
    ) {
      context.addIssue({
        code: "custom",
        message:
          "Explicit denial requires one physician-certified exact denied output; otherwise it must be disabled.",
        path: ["polarityPolicy"],
      });
    }
    if (
      specification.dataType === "measurement" &&
      specification.polarityPolicy.allowExplicitDenial
    ) {
      context.addIssue({
        code: "custom",
        message:
          "Scalar v1 does not support an exact denied measurement because a unit-bound negative representation is not yet defined. Leave denial disabled or create a non-measurement field.",
        path: ["polarityPolicy"],
      });
    }
    if (specification.unknownPolicy === "not_documented") {
      context.addIssue({
        code: "custom",
        message:
          "Scalar v1 cannot certify a generic not-documented value without an exact field-specific output; choose blank or requires input.",
        path: ["unknownPolicy"],
      });
    }
    if (
      specification.evidenceRequirements.acceptedEvidenceQualities.length !== 1 ||
      specification.evidenceRequirements.acceptedEvidenceQualities[0] !==
        "direct"
    ) {
      context.addIssue({
        code: "custom",
        message:
          "Scalar v1 supports direct evidence only; unclear evidence always requires physician review.",
        path: ["evidenceRequirements", "acceptedEvidenceQualities"],
      });
    }

    if (specification.allowedTemporalities.length !== 1) {
      context.addIssue({
        code: "custom",
        message:
          "Scalar v1 requires one fixed temporality per custom field; create separate fields for different temporal scopes.",
        path: ["allowedTemporalities"],
      });
    }
    if (specification.allowedTemporalities.includes("unknown")) {
      context.addIssue({
        code: "custom",
        message:
          "Scalar v1 cannot certify an unknown time scope; choose current, historical, or planned and prove it in every example.",
        path: ["allowedTemporalities"],
      });
    }
    if (specification.allowedLateralities.length !== 1) {
      context.addIssue({
        code: "custom",
        message:
          "Scalar v1 requires one fixed laterality per custom field; create separate fields for different sides or scopes.",
        path: ["allowedLateralities"],
      });
    }
    if (specification.allowedLateralities.includes("unknown")) {
      context.addIssue({
        code: "custom",
        message:
          "Scalar v1 cannot certify unknown laterality; choose a fixed side/scope or not-applicable and prove it in every example.",
        path: ["allowedLateralities"],
      });
    }
    const fixedTemporality = specification.allowedTemporalities[0];
    const fixedLaterality = specification.allowedLateralities[0];
    for (const rawCue of specification.approvedEvidenceCues) {
      const cue = rawCue.normalize("NFKC").replace(/\s+/gu, " ").toLowerCase();
      const hasHistorical =
        /\b(?:historical|history\s+of|previously|prior|past)\b/iu.test(cue);
      const hasPlanned =
        /\b(?:planned|plan(?:ned)?|scheduled)\b/iu.test(cue);
      const temporalCueValid =
        fixedTemporality === "current"
          ? !hasHistorical && !hasPlanned
          : fixedTemporality === "historical"
            ? hasHistorical && !hasPlanned
            : fixedTemporality === "planned"
              ? hasPlanned && !hasHistorical
              : false;
      if (!temporalCueValid) {
        context.addIssue({
          code: "custom",
          message:
            "Every evidence cue must carry the exact certified time scope; historical/planned fields need that word in the cue, while current cues cannot contain a conflicting scope.",
          path: ["approvedEvidenceCues"],
        });
      }
      const cueLateralities = [
        /\bleft\b/iu.test(cue) ? "left" : null,
        /\bright\b/iu.test(cue) ? "right" : null,
        /\b(?:bilateral|both\s+sides?)\b/iu.test(cue) ? "bilateral" : null,
        /\bmidline\b/iu.test(cue) ? "midline" : null,
      ].filter(Boolean);
      const lateralityCueValid =
        fixedLaterality === "not_applicable"
          ? cueLateralities.length === 0
          : fixedLaterality !== undefined &&
            cueLateralities.length === 1 &&
            cueLateralities[0] === fixedLaterality;
      if (!lateralityCueValid) {
        context.addIssue({
          code: "custom",
          message:
            "Every evidence cue must carry the exact certified side (left, right, bilateral, or midline); not-applicable cues cannot contain a side marker.",
          path: ["approvedEvidenceCues"],
        });
      }
    }

    const supportedPositiveExamples =
      specification.positiveSyntheticExamples.filter(
        (example) => (example.expectedStatus ?? "supported") === "supported",
      );
    if (specification.dataType === "single_select") {
      for (const option of specification.allowedOptions) {
        const denialCoversOption =
          specification.polarityPolicy.allowExplicitDenial &&
          option.value === specification.polarityPolicy.exactDeniedOutput &&
          specification.positiveSyntheticExamples.some(
            (example) =>
              example.expectedStatus === "explicitly_denied" &&
              example.expectedValue === option.value,
          );
        if (
          !denialCoversOption &&
          !supportedPositiveExamples.some(
            (example) => example.expectedValue === option.value,
          )
        ) {
          context.addIssue({
            code: "custom",
            message: `Every exact single-select option needs a positive synthetic example; ${option.displayText} is untested.`,
            path: ["positiveSyntheticExamples"],
          });
        }
      }
    }
    if (specification.dataType === "measurement") {
      for (const unit of specification.allowedUnits) {
        if (
          !supportedPositiveExamples.some(
            (example) => example.expectedUnit === unit,
          )
        ) {
          context.addIssue({
            code: "custom",
            message: `Every allowed measurement unit needs a positive synthetic example; ${unit} is untested.`,
            path: ["positiveSyntheticExamples"],
          });
        }
      }
    }
    const denialExamples = specification.positiveSyntheticExamples.filter(
      (example) => example.expectedStatus === "explicitly_denied",
    );
    if (specification.polarityPolicy.allowExplicitDenial) {
      if (
        denialExamples.length === 0 ||
        denialExamples.some(
          (example) =>
            example.expectedValue !==
              specification.polarityPolicy.exactDeniedOutput ||
            example.expectedUnit !== null,
        )
      ) {
        context.addIssue({
          code: "custom",
          message:
            "An enabled denial policy requires a positive synthetic example whose expected status is explicitly_denied and whose value is the exact certified denied output.",
          path: ["positiveSyntheticExamples"],
        });
      }
    } else if (denialExamples.length > 0) {
      context.addIssue({
        code: "custom",
        message:
          "A denial example is not allowed when explicit denial is disabled.",
        path: ["positiveSyntheticExamples"],
      });
    }

    const valueMatchesType = (
      value: z.infer<typeof CustomScalarValueSchema>,
      unit: string | null,
    ): boolean => {
      switch (specification.dataType) {
        case "narrative_text":
          return (
            typeof value === "string" &&
            unit === null &&
            value.length > 0 &&
            value.length <= (specification.maximumLength ?? 4_000)
          );
        case "number":
          return (
            typeof value === "number" &&
            Number.isFinite(value) &&
            unit === null &&
            (specification.numericRange?.minimum === null ||
              specification.numericRange?.minimum === undefined ||
              value >= specification.numericRange.minimum) &&
            (specification.numericRange?.maximum === null ||
              specification.numericRange?.maximum === undefined ||
              value <= specification.numericRange.maximum)
          );
        case "measurement":
          return (
            typeof value === "number" &&
            Number.isFinite(value) &&
            unit !== null &&
            specification.allowedUnits.includes(unit) &&
            (specification.numericRange?.minimum === null ||
              specification.numericRange?.minimum === undefined ||
              value >= specification.numericRange.minimum) &&
            (specification.numericRange?.maximum === null ||
              specification.numericRange?.maximum === undefined ||
              value <= specification.numericRange.maximum)
          );
        case "date": {
          if (typeof value !== "string" || unit !== null) return false;
          const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
          if (!match) return false;
          const date = new Date(
            Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
          );
          return (
            date.getUTCFullYear() === Number(match[1]) &&
            date.getUTCMonth() === Number(match[2]) - 1 &&
            date.getUTCDate() === Number(match[3])
          );
        }
        case "boolean":
          return typeof value === "boolean" && unit === null;
        case "single_select":
          return (
            typeof value === "string" &&
            unit === null &&
            specification.allowedOptions.some(
              (option) => option.value === value,
            )
          );
      }
    };
    const isReservedSyntheticDate = (value: unknown): boolean =>
      typeof value === "string" &&
      /^2099-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$/u.test(value);

    specification.positiveSyntheticExamples.forEach((example, index) => {
      if (!valueMatchesType(example.expectedValue, example.expectedUnit)) {
        context.addIssue({
          code: "custom",
          message:
            "A positive synthetic result must exactly match the certified field type, options, unit, and range.",
          path: ["positiveSyntheticExamples", index],
        });
      }
      if (
        specification.dataType === "date" &&
        !isReservedSyntheticDate(example.expectedValue)
      ) {
        context.addIssue({
          code: "custom",
          message:
            "Date certification examples must use the reserved synthetic year 2099; real/current dates are rejected before persistence.",
          path: ["positiveSyntheticExamples", index, "expectedValue"],
        });
      }
    });
    specification.negativeSyntheticExamples.forEach((example, index) => {
      if (
        example.prohibitedValue !== null &&
        !valueMatchesType(
          example.prohibitedValue,
          specification.dataType === "measurement"
            ? specification.allowedUnits[0] ?? null
            : null,
        )
      ) {
        context.addIssue({
          code: "custom",
          message:
            "A prohibited synthetic value must match the certified scalar type.",
          path: ["negativeSyntheticExamples", index, "prohibitedValue"],
        });
      }
      if (
        specification.dataType === "date" &&
        example.prohibitedValue !== null &&
        !isReservedSyntheticDate(example.prohibitedValue)
      ) {
        context.addIssue({
          code: "custom",
          message:
            "Date certification examples must use the reserved synthetic year 2099.",
          path: ["negativeSyntheticExamples", index, "prohibitedValue"],
        });
      }
    });
    specification.ambiguitySyntheticExamples.forEach((example, index) => {
      if (
        example.possibleValues.some(
          (value) =>
            !valueMatchesType(
              value,
              specification.dataType === "measurement"
                ? specification.allowedUnits[0] ?? null
                : null,
            ),
        )
      ) {
        context.addIssue({
          code: "custom",
          message:
            "Every ambiguity example value must match the certified scalar type.",
          path: ["ambiguitySyntheticExamples", index, "possibleValues"],
        });
      }
      if (
        specification.dataType === "date" &&
        example.possibleValues.some((value) => !isReservedSyntheticDate(value))
      ) {
        context.addIssue({
          code: "custom",
          message:
            "Date ambiguity examples must use only reserved synthetic year 2099 values.",
          path: ["ambiguitySyntheticExamples", index, "possibleValues"],
        });
      }
    });
    if (
      specification.polarityPolicy.exactDeniedOutput !== null &&
      !valueMatchesType(
        specification.polarityPolicy.exactDeniedOutput,
        specification.dataType === "measurement"
          ? specification.allowedUnits[0] ?? null
          : null,
      )
    ) {
      context.addIssue({
        code: "custom",
        message:
          "The exact negative output must match the certified scalar type, option, unit, and range.",
        path: ["polarityPolicy", "exactDeniedOutput"],
      });
    }
    if (
      specification.dataType === "single_select" &&
      specification.polarityPolicy.exactDeniedOutput !== null &&
      (typeof specification.polarityPolicy.exactDeniedOutput !== "string" ||
        !optionValues.has(specification.polarityPolicy.exactDeniedOutput))
    ) {
      context.addIssue({
        code: "custom",
        message:
          "A denied single-select output must be one exact allowed option.",
        path: ["polarityPolicy", "exactDeniedOutput"],
      });
    }
  });

export type TemplateFieldSpecificationContent = z.infer<
  typeof TemplateFieldSpecificationContentSchema
>;

export class TemplateFieldSpecificationSetLimitError extends Error {
  readonly code = "TT_CUSTOM_SPECIFICATION_SET_LIMIT";

  constructor() {
    super(
      "The custom-field specification set exceeds the safe-alpha field, example, or synthetic-text limit.",
    );
    this.name = "TemplateFieldSpecificationSetLimitError";
  }
}

/** Exact physician-authored strings persisted in a specification and/or sent
 * to the extraction provider. Labels are generated by the server and are not
 * included here. */
export function templateFieldSpecificationAuthoredText(
  specification: TemplateFieldSpecificationContent,
): string[] {
  return [
    specification.physicianName,
    specification.physicianDescription,
    ...specification.approvedEvidenceCues,
    ...specification.allowedOptions.flatMap((option) => [
      option.value,
      option.displayText,
    ]),
    ...specification.allowedUnits,
    ...specification.permittedUnitConversions.flatMap((conversion) => [
      conversion.from,
      conversion.to,
    ]),
    ...specification.positiveSyntheticExamples.flatMap((example) => [
      example.exampleId,
      example.syntheticEvidence,
      String(example.expectedValue),
      ...(example.expectedUnit === null ? [] : [example.expectedUnit]),
    ]),
    ...specification.negativeSyntheticExamples.flatMap((example) => [
      example.exampleId,
      example.syntheticEvidence,
      example.reason,
      ...(example.prohibitedValue === null
        ? []
        : [String(example.prohibitedValue)]),
    ]),
    ...specification.ambiguitySyntheticExamples.flatMap((example) => [
      example.exampleId,
      example.syntheticEvidence,
      example.reason,
      ...example.possibleValues.map(String),
    ]),
    ...(specification.polarityPolicy.exactDeniedOutput === null
      ? []
      : [String(specification.polarityPolicy.exactDeniedOutput)]),
  ];
}

/** Enforces one shared operational bound before any privacy or extraction
 * provider call. This supplements per-field Zod limits with a whole-template
 * cap and is intentionally reusable at save and execution boundaries. */
export function assertTemplateFieldSpecificationSetWithinLimits(
  specifications: readonly TemplateFieldSpecificationContent[],
): void {
  const examples = specifications.flatMap((specification) => [
    ...specification.positiveSyntheticExamples,
    ...specification.negativeSyntheticExamples,
    ...specification.ambiguitySyntheticExamples,
  ]);
  const textCharacters = specifications
    .flatMap(templateFieldSpecificationAuthoredText)
    .reduce((total, value) => total + value.length, 0);
  if (
    specifications.length > TEMPLATE_TWIN_CUSTOM_FIELD_LIMIT ||
    examples.length > TEMPLATE_TWIN_CUSTOM_EXAMPLE_LIMIT ||
    textCharacters > TEMPLATE_TWIN_CUSTOM_EXAMPLE_TEXT_LIMIT
  ) {
    throw new TemplateFieldSpecificationSetLimitError();
  }
}

export const PhysicianFieldCertificationSchema = z
  .object({
    status: z.literal("certified"),
    certifiedByUserId: z.string().min(1).max(160),
    certifiedAt: z.string().datetime(),
    contentSha256: z.string().regex(SHA256),
    syntheticCoverageSha256: z.string().regex(SHA256),
  })
  .strict();

export const CertifiedTemplateFieldSpecificationSchema =
  TemplateFieldSpecificationContentSchema.and(
    z
      .object({
        certification: PhysicianFieldCertificationSchema,
      })
      .strict(),
  );
export type CertifiedTemplateFieldSpecification = z.infer<
  typeof CertifiedTemplateFieldSpecificationSchema
>;
