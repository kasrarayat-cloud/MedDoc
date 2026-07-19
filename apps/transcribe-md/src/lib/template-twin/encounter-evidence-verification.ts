import {
  encounterEvidenceAnchorId,
  uniqueExactEncounterEvidenceOffset,
} from "./encounter-facts";
import {
  TemplateTwinFillManifestSchema,
  type EncounterFact,
  type TemplateTwinFillManifest,
} from "./ir";
/*
 * Keep parsing at the call boundary: route transactions often hold JSON as
 * `unknown`, and no caller may turn an unchecked cast into authorization.
 */
import { isSupportedTemplateTwinConcept } from "./supported-concepts";
import {
  reconstructTemplateTwinEncounterSource,
  type ReconstructableTemplateTwinVisitSource,
} from "./canonical-encounter-source";
import { buildCanonicalCustomEvidenceAnchors } from "./custom-concepts/canonical-evidence-anchors";

export type TemplateTwinEncounterEvidenceFailureCode =
  | "ENCOUNTER_SOURCE_RECEIPT_MISSING"
  | "ENCOUNTER_SOURCE_UNAVAILABLE"
  | "ENCOUNTER_SOURCE_RECEIPT_MISMATCH"
  | "ENCOUNTER_EVIDENCE_OFFSET_INVALID"
  | "ENCOUNTER_EVIDENCE_QUOTE_MISMATCH"
  | "ENCOUNTER_EVIDENCE_QUOTE_AMBIGUOUS"
  | "ENCOUNTER_EVIDENCE_ANCHOR_MISMATCH";

export type TemplateTwinEncounterEvidenceAssessment =
  | { valid: true; failureCodes: readonly [] }
  | {
      valid: false;
      failureCodes: readonly TemplateTwinEncounterEvidenceFailureCode[];
    };

function sameReceipt(
  left: TemplateTwinFillManifest["encounterSourceReceipt"],
  right: NonNullable<TemplateTwinFillManifest["encounterSourceReceipt"]>,
): boolean {
  return Boolean(
    left &&
    left.receiptVersion === right.receiptVersion &&
    left.mode === right.mode &&
    left.canonicalSourceSha256 === right.canonicalSourceSha256 &&
    left.canonicalSourceLength === right.canonicalSourceLength,
  );
}

function assessCoreFact(input: {
  fact: EncounterFact;
  mode: NonNullable<TemplateTwinFillManifest["encounterSourceReceipt"]>["mode"];
  contextText: string;
  add: (code: TemplateTwinEncounterEvidenceFailureCode) => void;
}): void {
  const { fact, contextText, add } = input;
  const offsets = fact.sourceTranscriptOffsets;
  if (
    !offsets ||
    offsets.start < 0 ||
    offsets.end <= offsets.start ||
    offsets.end > contextText.length
  ) {
    add("ENCOUNTER_EVIDENCE_OFFSET_INVALID");
    if (!uniqueExactEncounterEvidenceOffset(contextText, fact.evidenceQuote)) {
      add("ENCOUNTER_EVIDENCE_QUOTE_AMBIGUOUS");
    }
    return;
  }
  if (contextText.slice(offsets.start, offsets.end) !== fact.evidenceQuote) {
    add("ENCOUNTER_EVIDENCE_QUOTE_MISMATCH");
  }
  const unique = uniqueExactEncounterEvidenceOffset(
    contextText,
    fact.evidenceQuote,
  );
  if (!unique) {
    add("ENCOUNTER_EVIDENCE_QUOTE_AMBIGUOUS");
    return;
  }
  if (unique.start !== offsets.start || unique.end !== offsets.end) {
    add("ENCOUNTER_EVIDENCE_OFFSET_INVALID");
  }
  const expectedAnchorId = encounterEvidenceAnchorId({
    mode: input.mode,
    contextText,
    quote: fact.evidenceQuote,
    offsets,
    timestamp: fact.audioTimestampSeconds,
  });
  if (
    fact.evidenceAnchorIds.length !== 1 ||
    fact.evidenceAnchorIds[0] !== expectedAnchorId
  ) {
    add("ENCOUNTER_EVIDENCE_ANCHOR_MISMATCH");
  }
}

function assessCustomFact(input: {
  fact: EncounterFact;
  canonicalAnchorById: ReadonlyMap<
    string,
    {
      quote: string;
      sourceTranscriptOffsets: { start: number; end: number };
    }
  >;
  add: (code: TemplateTwinEncounterEvidenceFailureCode) => void;
}): void {
  if (
    new Set(input.fact.evidenceAnchorIds).size !==
    input.fact.evidenceAnchorIds.length
  ) {
    input.add("ENCOUNTER_EVIDENCE_ANCHOR_MISMATCH");
    return;
  }
  const anchors = input.fact.evidenceAnchorIds.map((id) =>
    input.canonicalAnchorById.get(id),
  );
  if (anchors.some((anchor) => !anchor)) {
    input.add("ENCOUNTER_EVIDENCE_ANCHOR_MISMATCH");
    return;
  }
  const present = anchors.filter(
    (
      anchor,
    ): anchor is {
      quote: string;
      sourceTranscriptOffsets: { start: number; end: number };
    } => Boolean(anchor),
  );
  if (
    present.map((anchor) => anchor.quote).join(" … ") !==
    input.fact.evidenceQuote
  ) {
    input.add("ENCOUNTER_EVIDENCE_QUOTE_MISMATCH");
  }
  if (present.length === 1) {
    const expected = present[0]!.sourceTranscriptOffsets;
    const actual = input.fact.sourceTranscriptOffsets;
    if (
      !actual ||
      actual.start !== expected.start ||
      actual.end !== expected.end
    ) {
      input.add("ENCOUNTER_EVIDENCE_OFFSET_INVALID");
    }
  } else if (input.fact.sourceTranscriptOffsets !== null) {
    input.add("ENCOUNTER_EVIDENCE_OFFSET_INVALID");
  }
}

/**
 * Reconstructs the exact Layer-3 source and independently proves every
 * provider-derived fact against it. Persisted offsets and anchor IDs are
 * treated only as claims to verify.
 */
export function assessTemplateTwinEncounterEvidence(input: {
  visit: ReconstructableTemplateTwinVisitSource;
  manifest: TemplateTwinFillManifest;
}): TemplateTwinEncounterEvidenceAssessment {
  const failureCodes: TemplateTwinEncounterEvidenceFailureCode[] = [];
  const add = (code: TemplateTwinEncounterEvidenceFailureCode): void => {
    if (!failureCodes.includes(code)) failureCodes.push(code);
  };
  if (!input.manifest.encounterSourceReceipt) {
    add("ENCOUNTER_SOURCE_RECEIPT_MISSING");
  }
  const source = reconstructTemplateTwinEncounterSource(input.visit);
  if (!source.ok) {
    add("ENCOUNTER_SOURCE_UNAVAILABLE");
    return { valid: false, failureCodes };
  }
  if (!sameReceipt(input.manifest.encounterSourceReceipt, source.receipt)) {
    add("ENCOUNTER_SOURCE_RECEIPT_MISMATCH");
  }

  const customFacts = input.manifest.facts.filter(
    (fact) =>
      fact.sourceType === "encounter_evidence" &&
      !isSupportedTemplateTwinConcept(fact.concept),
  );
  let canonicalAnchorById = new Map<
    string,
    {
      quote: string;
      sourceTranscriptOffsets: { start: number; end: number };
    }
  >();
  if (customFacts.length > 0) {
    const customAnchors = buildCanonicalCustomEvidenceAnchors({
      mode: source.mode,
      contextText: source.contextText,
    });
    if (!customAnchors.ok) {
      add("ENCOUNTER_SOURCE_UNAVAILABLE");
    } else {
      canonicalAnchorById = new Map(
        customAnchors.anchors.map((anchor) => [
          anchor.evidenceAnchorId,
          {
            quote: anchor.quote,
            sourceTranscriptOffsets: anchor.sourceTranscriptOffsets,
          },
        ]),
      );
    }
  }

  for (const fact of input.manifest.facts) {
    if (fact.sourceType !== "encounter_evidence") continue;
    if (isSupportedTemplateTwinConcept(fact.concept)) {
      assessCoreFact({
        fact,
        mode: source.mode,
        contextText: source.contextText,
        add,
      });
    } else {
      assessCustomFact({ fact, canonicalAnchorById, add });
    }
  }
  return failureCodes.length === 0
    ? { valid: true, failureCodes: [] }
    : { valid: false, failureCodes };
}

export function templateTwinEncounterEvidenceIsValid(input: {
  visit: ReconstructableTemplateTwinVisitSource;
  manifest: TemplateTwinFillManifest;
}): boolean {
  return assessTemplateTwinEncounterEvidence(input).valid;
}

export function persistedTemplateTwinEncounterEvidenceIsValid(input: {
  visit: ReconstructableTemplateTwinVisitSource;
  manifest: unknown;
}): boolean {
  const parsed = TemplateTwinFillManifestSchema.safeParse(input.manifest);
  return (
    parsed.success &&
    assessTemplateTwinEncounterEvidence({
      visit: input.visit,
      manifest: parsed.data,
    }).valid
  );
}
