// ============================================================================
// L4 inaudible-span hardening — prompt contract + hedge-survival chain
// (2026-06-11; hallucination-reconciliation follow-up, PR #304's L4 RED).
// ----------------------------------------------------------------------------
// Pins the three defense layers end-to-end with mocked models:
//   1. the immutable SOAP prompt carries the unclear-span / no-exam-reframe /
//      no-garble-normalization rules on EVERY visit (custom templates can't
//      weaken them — they ride SAFETY.globalRules);
//   2. the marked transcript ("[unclear in recording]") actually reaches the
//      L4 and L5 prompts;
//   3. a hedge emitted by L4 SURVIVES the chain to the final note (L5 clean
//      critique → L6 passthrough never strips it).
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  modelComplete: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("@meddoc/ai", async () => {
  const actual =
    await vi.importActual<typeof import("@meddoc/ai")>("@meddoc/ai");
  return {
    ...actual,
    modelClient: {
      complete: mocks.modelComplete,
      completeText: mocks.modelCompleteText,
    },
  };
});

vi.mock("@meddoc/db", () => ({
  default: {
    $queryRaw: vi.fn().mockResolvedValue([
      { id: "u1", practiceId: "p1", email: "synthetic@example.test" },
    ]),
    transcribeVisit: { update: mocks.prismaUpdate },
  },
}));

vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/worker/worker-audit", () => ({ logWorkerAudit: mocks.logAudit }));
vi.mock("@/worker/staging-qa-mutation-fence", () => ({
  updateTemplateTwinSyntheticQaClaimBoundVisit: (input: {
    visitId: string;
    data: unknown;
  }) => mocks.prismaUpdate({ where: { id: input.visitId }, data: input.data }),
}));

import { runLayer4GenerateSoap } from "../04-generate-soap";
import { runLayer5SelfCritique } from "../05-self-critique";
import { runLayer6Polish } from "../06-polish";
import { UNCLEAR_MARKER } from "../transcript-clarity";
import { buildSoapSystemPrompt } from "../../note-templates/build-soap-prompt";
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from "../../note-templates/system-default-template";

const MARKED_TRANSCRIPT = [
  "[Doctor #0, 0:10]: So we will send you across that prescription.",
  `[Doctor #0, 0:14]: it's called ${UNCLEAR_MARKER} one tablet three times a day.`,
  "[Patient #1, 0:20]: it is quite sore when I press on it.",
].join("\n");

const EMPTY_ENTITIES = {
  chief_complaint: null,
  hpi: null,
  past_medical_history: [],
  medications: [],
  allergies: [],
  family_history: [],
  social_history: {},
  ros: [],
  exam_findings: [],
  tests_mentioned: [],
  assessment_discussed: [],
  plan_discussed: [],
};

const HEDGED_SOAP = `## Subjective
Per patient, quite sore when pressing on the area.

## Objective
Formal exam not documented in this encounter.

## Assessment
Symptom under evaluation.

## Plan
1. Prescribed ${UNCLEAR_MARKER} — one tablet three times a day [clarify with patient].`;

function l4Input(overrides: Record<string, unknown> = {}) {
  return {
    visitId: "vis-ih",
    practiceId: "p1",
    userId: "u1",
    specialty: "primary-care",
    roleLabeledTranscript: MARKED_TRANSCRIPT,
    entities: EMPTY_ENTITIES,
    audioConfidenceStats: null,
    interpreterMode: false,
    ...overrides,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({ id: "vis-ih" });
  mocks.logAudit.mockResolvedValue(undefined);
  mocks.modelCompleteText.mockResolvedValue({ text: HEDGED_SOAP });
  mocks.modelComplete.mockResolvedValue({
    issues: [],
    overall_quality: "high",
    safe_to_sign_without_review: true,
  });
});

describe("immutable prompt contract (rides SAFETY.globalRules on every visit)", () => {
  const system = buildSoapSystemPrompt(SYSTEM_DEFAULT_NOTE_TEMPLATE, {
    specialty: "primary-care",
    specialtyGuidanceText: null,
    audioQualityAlert: null,
    interpreterAlert: null,
  });

  it("carries the unclear-span rule (never assert over a marker)", () => {
    expect(system).toMatch(
      /"\[unclear in recording\]" in the transcript means/,
    );
    expect(system).toMatch(
      /Never[\s\S]{0,20}assert a medication, dose, diagnosis, finding, or proper name/,
    );
  });

  it("carries the no-exam-reframe rule (patient-reported stays Subjective)", () => {
    expect(system).toMatch(
      /Never present patient-reported sensations as examination findings/,
    );
    expect(system).toMatch(/tender to palpation/);
  });

  it("carries the no-garble-normalization rule (no closest-real-term substitution)", () => {
    expect(system).toMatch(
      /Never normalize an unfamiliar, garbled, or partial term/,
    );
  });
});

describe("the marked transcript reaches the model layers", () => {
  it("L4 user prompt contains the [unclear in recording] marker", async () => {
    await runLayer4GenerateSoap(l4Input());
    const { user, system } = mocks.modelCompleteText.mock.calls[0][0];
    expect(user).toContain(UNCLEAR_MARKER);
    expect(system).toMatch(
      /Never normalize an unfamiliar, garbled, or partial term/,
    );
  });

  it("L5 prompt sees the marker AND the rubric carries the 3b unclear-span check", async () => {
    await runLayer5SelfCritique(l4Input({ soapDraft: HEDGED_SOAP }));
    const callArgs = mocks.modelComplete.mock.calls[0][0];
    const allText = JSON.stringify(callArgs);
    expect(allText).toContain("unclear in recording");
    expect(allText).toMatch(/only transcript support overlaps/);
  });
});

describe("hedge survival — the marker reaches the FINAL note", () => {
  it("L4 hedge → clean L5 critique → L6 passthrough keeps the marker verbatim", async () => {
    const soapDraft = await runLayer4GenerateSoap(l4Input());
    expect(soapDraft).toContain(UNCLEAR_MARKER);

    const critique = await runLayer5SelfCritique(l4Input({ soapDraft }));
    const polished = await runLayer6Polish({
      visitId: "vis-ih",
      practiceId: "p1",
      userId: "u1",
      soapDraft,
      critique,
    });

    // Passthrough branch (no fixable issues) — the hedge must survive
    // verbatim; no layer may strip or resolve it.
    expect(polished.soapFinal).toContain(UNCLEAR_MARKER);
    expect(polished.soapFinal).toBe(soapDraft);
    expect(polished.polishRejected).toBe(false);
  });
});
