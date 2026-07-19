import { describe, expect, it } from "vitest";

import { createTemplateTwinEncounterSourceReceipt } from "../canonical-encounter-source";
import { buildRoleLabeledTranscript } from "../canonical-encounter-source";
import { assessTemplateTwinEncounterEvidence } from "../encounter-evidence-verification";
import { projectEncounterFacts } from "../encounter-facts";
import { buildCanonicalCustomConceptEvidence } from "../custom-concepts";
import {
  TemplateTwinFillManifestSchema,
  type TemplateTwinFillManifest,
} from "../ir";

const SOURCE = "Synthetic patient denies fever.";

function manifestFor(
  mode: "text" | "dictation" | "conversation",
  contextText = SOURCE,
): TemplateTwinFillManifest {
  const facts = projectEncounterFacts({
    mode,
    contextText,
    entities: {
      chief_complaint: {
        statement: "denies fever",
        evidence_quote: SOURCE,
      },
    },
  });
  return TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    soapVersion: 1,
    soapSha256: "a".repeat(64),
    compiledVersionId: "synthetic-compiled",
    noteTemplateId: "synthetic-template",
    noteTemplateVersion: 1,
    compilerVersion: "synthetic-compiler",
    resolverVersion: "synthetic-resolver",
    resolverModelVersion: null,
    rendererVersion: "synthetic-renderer",
    encounterSourceReceipt: createTemplateTwinEncounterSourceReceipt({
      mode,
      contextText,
    }),
    fieldIntentsSha256: null,
    customExampleProofSha256: null,
    customExtraction: null,
    facts,
    fields: [],
    validation: {
      valid: true,
      issues: [],
      checkedAt: "2026-07-19T06:00:00.000Z",
      validatorVersion: "synthetic-validator",
    },
    counts: {
      filled: 0,
      needsReview: 0,
      notMentioned: 0,
      conflicts: 0,
      criticalUnresolved: 0,
    },
  });
}

function typedVisit(rawTextInput: string | null = SOURCE) {
  return {
    inputMode: "text_notes",
    rawTextInput,
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
  };
}

describe("Template Twin encounter evidence revalidation", () => {
  it("accepts equivalent typed and voice-dictation facts against their exact sources", () => {
    const typed = manifestFor("text");
    const voice = manifestFor("dictation");

    expect(
      assessTemplateTwinEncounterEvidence({
        visit: typedVisit(),
        manifest: typed,
      }),
    ).toEqual({ valid: true, failureCodes: [] });
    expect(
      assessTemplateTwinEncounterEvidence({
        visit: {
          inputMode: "voice_dictation",
          transcriptText: SOURCE,
          rawTextInput: null,
          transcriptRaw: null,
          speakerMap: null,
        },
        manifest: voice,
      }),
    ).toEqual({ valid: true, failureCodes: [] });
    expect(
      typed.facts.map(({ value, polarity }) => ({ value, polarity })),
    ).toEqual(voice.facts.map(({ value, polarity }) => ({ value, polarity })));
  });

  it("reconstructs the exact role-labelled conversation source from persisted utterances", () => {
    const utterances = [
      {
        start: 12,
        end: 14,
        confidence: 0.99,
        channel: 0,
        transcript: SOURCE,
        words: [],
        speaker: 0,
      },
    ];
    const speakerMap = { "0": { role: "doctor" as const } };
    const contextText = buildRoleLabeledTranscript(utterances, speakerMap);
    const manifest = manifestFor("conversation", contextText);

    expect(
      assessTemplateTwinEncounterEvidence({
        visit: {
          inputMode: "audio_upload",
          rawTextInput: null,
          transcriptText: SOURCE,
          transcriptRaw: { results: { utterances } },
          speakerMap,
        },
        manifest,
      }),
    ).toEqual({ valid: true, failureCodes: [] });
  });

  it("rejects a tampered immutable source receipt hash", () => {
    const manifest = structuredClone(manifestFor("text"));
    manifest.encounterSourceReceipt!.canonicalSourceSha256 = "b".repeat(64);

    expect(
      assessTemplateTwinEncounterEvidence({ visit: typedVisit(), manifest }),
    ).toMatchObject({
      valid: false,
      failureCodes: expect.arrayContaining([
        "ENCOUNTER_SOURCE_RECEIPT_MISMATCH",
      ]),
    });
  });

  it("rejects a legacy or tampered manifest with no source receipt", () => {
    const manifest = structuredClone(manifestFor("text"));
    manifest.encounterSourceReceipt = null;

    expect(
      assessTemplateTwinEncounterEvidence({ visit: typedVisit(), manifest }),
    ).toMatchObject({
      valid: false,
      failureCodes: expect.arrayContaining([
        "ENCOUNTER_SOURCE_RECEIPT_MISSING",
      ]),
    });
  });

  it.each([
    [
      "offset",
      (manifest: TemplateTwinFillManifest) => {
        manifest.facts[0]!.sourceTranscriptOffsets = {
          start: 1,
          end: SOURCE.length,
        };
      },
      "ENCOUNTER_EVIDENCE_OFFSET_INVALID",
    ],
    [
      "quote",
      (manifest: TemplateTwinFillManifest) => {
        manifest.facts[0]!.evidenceQuote = "Synthetic patient reports fever.";
      },
      "ENCOUNTER_EVIDENCE_QUOTE_MISMATCH",
    ],
    [
      "anchor identity",
      (manifest: TemplateTwinFillManifest) => {
        manifest.facts[0]!.evidenceAnchorIds = [
          "ttev_000000000000000000000000",
        ];
      },
      "ENCOUNTER_EVIDENCE_ANCHOR_MISMATCH",
    ],
  ] as const)("rejects a tampered %s", (_label, tamper, expectedCode) => {
    const manifest = structuredClone(manifestFor("text"));
    tamper(manifest);

    expect(
      assessTemplateTwinEncounterEvidence({ visit: typedVisit(), manifest }),
    ).toMatchObject({
      valid: false,
      failureCodes: expect.arrayContaining([expectedCode]),
    });
  });

  it("rejects duplicate exact quotes as clinically ambiguous", () => {
    const duplicateSource = `${SOURCE} ${SOURCE}`;
    const manifest = manifestFor("text", duplicateSource);

    expect(
      assessTemplateTwinEncounterEvidence({
        visit: typedVisit(duplicateSource),
        manifest,
      }),
    ).toMatchObject({
      valid: false,
      failureCodes: expect.arrayContaining([
        "ENCOUNTER_EVIDENCE_QUOTE_AMBIGUOUS",
      ]),
    });
  });

  it("rejects duplicated custom-concept anchor identities", () => {
    const evidence = buildCanonicalCustomConceptEvidence({
      mode: "text",
      contextText: SOURCE,
    });
    const anchor = evidence.anchors[0]!;
    const manifest = structuredClone(manifestFor("text"));
    manifest.facts[0]!.concept = `ttcustom_${"a".repeat(24)}`;
    manifest.facts[0]!.evidenceAnchorIds = [
      anchor.evidenceAnchorId,
      anchor.evidenceAnchorId,
    ];
    manifest.facts[0]!.evidenceQuote = `${anchor.quote} … ${anchor.quote}`;
    manifest.facts[0]!.sourceTranscriptOffsets = null;

    expect(
      assessTemplateTwinEncounterEvidence({ visit: typedVisit(), manifest }),
    ).toMatchObject({
      valid: false,
      failureCodes: expect.arrayContaining([
        "ENCOUNTER_EVIDENCE_ANCHOR_MISMATCH",
      ]),
    });
  });

  it("rejects a missing canonical visit source", () => {
    expect(
      assessTemplateTwinEncounterEvidence({
        visit: typedVisit(null),
        manifest: manifestFor("text"),
      }),
    ).toMatchObject({
      valid: false,
      failureCodes: expect.arrayContaining(["ENCOUNTER_SOURCE_UNAVAILABLE"]),
    });
  });
});
