import type {
  CustomScalarDataType,
  CustomScalarValue,
  TemplateFieldSpecificationContent,
} from "./specification";

function defaultScalar(dataType: CustomScalarDataType): CustomScalarValue {
  if (dataType === "boolean") return true;
  if (dataType === "number" || dataType === "measurement") return 1;
  if (dataType === "date") return "2099-01-15";
  return "Synthetic supported value";
}

function ambiguityValues(
  specification: TemplateFieldSpecificationContent,
): CustomScalarValue[] {
  if (specification.dataType === "single_select") {
    return specification.allowedOptions.slice(0, 2).map(({ value }) => value);
  }
  if (specification.dataType === "boolean") return [true, false];
  if (
    specification.dataType === "number" ||
    specification.dataType === "measurement"
  ) {
    const first = inRangeDefault(specification);
    const maximum = specification.numericRange?.maximum;
    const minimum = specification.numericRange?.minimum;
    const higher = first + 1;
    if (maximum === null || maximum === undefined || higher <= maximum) {
      return [first, higher];
    }
    const lower = first - 1;
    return minimum === null || minimum === undefined || lower >= minimum
      ? [first, lower]
      : [first];
  }
  if (specification.dataType === "date") {
    return ["2099-01-15", "2099-01-16"];
  }
  return ["Synthetic option A", "Synthetic option B"];
}

function inRangeDefault(
  specification: TemplateFieldSpecificationContent,
): number {
  const minimum = specification.numericRange?.minimum;
  const maximum = specification.numericRange?.maximum;
  if (minimum !== null && minimum !== undefined) return minimum;
  if (maximum !== null && maximum !== undefined && maximum < 1) return maximum;
  return 1;
}

function ambiguityEvidence(
  specification: TemplateFieldSpecificationContent,
  possibleValues: readonly CustomScalarValue[],
): string {
  const cue = specification.approvedEvidenceCues[0] ?? "certified field";
  const unit =
    specification.dataType === "measurement"
      ? ` ${specification.allowedUnits[0] ?? "unit"}`
      : "";
  return `Synthetic example: ${cue} is ${possibleValues
    .map((value) => `${String(value)}${unit}`)
    .join(" or ")}.`;
}

function ambiguityValuesRemainValid(
  specification: TemplateFieldSpecificationContent,
  values: readonly CustomScalarValue[],
): boolean {
  if (values.length === 0) return false;
  if (specification.dataType === "single_select") {
    return values.every(
      (value) =>
        typeof value === "string" &&
        specification.allowedOptions.some((option) => option.value === value),
    );
  }
  if (
    specification.dataType === "number" ||
    specification.dataType === "measurement"
  ) {
    return values.every(
      (value) =>
        typeof value === "number" &&
        (specification.numericRange?.minimum === null ||
          specification.numericRange?.minimum === undefined ||
          value >= specification.numericRange.minimum) &&
        (specification.numericRange?.maximum === null ||
          specification.numericRange?.maximum === undefined ||
          value <= specification.numericRange.maximum),
    );
  }
  if (specification.dataType === "boolean") {
    return values.every((value) => typeof value === "boolean");
  }
  return values.every((value) => typeof value === "string");
}

/** Keeps the physician-editable corpus exhaustive when options, units, or a
 * denial policy changes. Existing matching evidence is preserved; removed
 * policy values are removed rather than silently repurposed. */
export function synchronizeCustomSyntheticExamples(
  specification: TemplateFieldSpecificationContent,
): TemplateFieldSpecificationContent {
  const cue = specification.approvedEvidenceCues[0] ?? "certified field";
  const existingSupported = specification.positiveSyntheticExamples.filter(
    (example) => (example.expectedStatus ?? "supported") === "supported",
  );
  const desired: Array<{
    value: CustomScalarValue;
    unit: string | null;
    id: string;
  }> =
    specification.dataType === "single_select"
      ? specification.allowedOptions
          .filter(
            ({ value }) =>
              !(
                specification.polarityPolicy.allowExplicitDenial &&
                value === specification.polarityPolicy.exactDeniedOutput
              ),
          )
          .map(({ ordinal, value }) => ({
            value,
            unit: null,
            id: `positive-option-${ordinal}`,
          }))
      : specification.dataType === "measurement"
        ? specification.allowedUnits.map((unit, index) => ({
            value:
              existingSupported.find((example) => example.expectedUnit === unit)
                ?.expectedValue ?? inRangeDefault(specification),
            unit,
            id: `positive-unit-${index}`,
          }))
        : [
            {
              value:
                existingSupported[0]?.expectedValue ??
                defaultScalar(specification.dataType),
              unit: null,
              id: existingSupported[0]?.exampleId ?? "positive-1",
            },
          ];
  const positives: TemplateFieldSpecificationContent["positiveSyntheticExamples"] = desired.map(({ value, unit, id }) => {
    const existing = existingSupported.find(
      (example) =>
        example.expectedValue === value && example.expectedUnit === unit,
    );
    return {
      exampleId: existing?.exampleId ?? id,
      syntheticEvidence:
        existing?.syntheticEvidence ??
        `Synthetic example: ${cue} is ${String(value)}${unit ? ` ${unit}` : ""}.`,
      expectedValue: value,
      expectedUnit: unit,
      expectedStatus: "supported" as const,
    };
  });
  if (
    specification.polarityPolicy.allowExplicitDenial &&
    specification.polarityPolicy.exactDeniedOutput !== null
  ) {
    const existingDenial = specification.positiveSyntheticExamples.find(
      (example) => example.expectedStatus === "explicitly_denied",
    );
    positives.push({
      exampleId: existingDenial?.exampleId ?? "positive-explicit-denial",
      syntheticEvidence:
        existingDenial?.syntheticEvidence ?? `Synthetic example: no ${cue}.`,
      expectedValue: specification.polarityPolicy.exactDeniedOutput,
      expectedUnit: null,
      expectedStatus: "explicitly_denied",
    });
  }
  const existingPossibleValues =
    specification.ambiguitySyntheticExamples[0]?.possibleValues ?? [];
  const possibleValues = ambiguityValuesRemainValid(
    specification,
    existingPossibleValues,
  )
    ? existingPossibleValues
    : ambiguityValues(specification);
  const ambiguity = specification.ambiguitySyntheticExamples[0];
  const preservesAmbiguityEvidence =
    ambiguity !== undefined &&
    JSON.stringify(existingPossibleValues) === JSON.stringify(possibleValues);
  return {
    ...specification,
    positiveSyntheticExamples: positives,
    negativeSyntheticExamples:
      specification.negativeSyntheticExamples.length > 0
        ? specification.negativeSyntheticExamples
        : [
            {
              exampleId: "negative-1",
              syntheticEvidence:
                "Synthetic example: an unrelated encounter detail is documented.",
              prohibitedValue: null,
              reason: "The certified evidence cue is absent.",
            },
          ],
    ambiguitySyntheticExamples: [
      {
        exampleId: ambiguity?.exampleId ?? "ambiguous-1",
        syntheticEvidence:
          (preservesAmbiguityEvidence ? ambiguity.syntheticEvidence : null) ??
          ambiguityEvidence(specification, possibleValues),
        possibleValues,
        reason:
          ambiguity?.reason ?? "Two exact values remain explicitly possible.",
      },
    ],
  };
}

export function defaultCustomAmbiguityEvidence(
  specification: TemplateFieldSpecificationContent,
  possibleValues: readonly CustomScalarValue[],
): string {
  return ambiguityEvidence(specification, possibleValues);
}
