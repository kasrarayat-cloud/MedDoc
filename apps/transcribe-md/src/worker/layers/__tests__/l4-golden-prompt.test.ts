// ============================================================================
// L4 GOLDEN prompt-equivalence — the Phase 1 hard gate.
// ----------------------------------------------------------------------------
// The non-negotiable guarantee: after L4 is refactored to BUILD its prompt
// from the resolved NoteTemplate, the prompt produced for the SYSTEM-DEFAULT
// template must be BYTE-IDENTICAL to the prompt L4 produced before Phase 1.
//
// The SYSTEM prompt is deterministic (delimiterSystemSuffix is fixed text), so
// it is asserted byte-for-byte. The USER prompt only varies in the random
// wrapAsData suffix (the unchanged injection mechanism), so its suffix is
// normalized before the byte assertion.
//
// Capture protocol: this test was first run against the PRE-refactor L4, which
// WROTE the golden fixtures (today's exact bytes). Subsequent runs (post-
// refactor) COMPARE against those committed fixtures. To intentionally
// re-baseline, delete the files in __fixtures__/ and re-run.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

// Real wrapAsData / delimiterSystemSuffix (only completeText is stubbed) so the
// captured prompt is exactly what production builds.
vi.mock("@meddoc/ai", async () => {
  const actual =
    await vi.importActual<typeof import("@meddoc/ai")>("@meddoc/ai");
  return {
    ...actual,
    modelClient: { complete: vi.fn(), completeText: mocks.modelCompleteText },
  };
});
vi.mock("@meddoc/db", () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/worker/worker-audit", () => ({ logWorkerAudit: mocks.logAudit }));
vi.mock("@/worker/staging-qa-mutation-fence", () => ({
  updateTemplateTwinSyntheticQaClaimBoundVisit: (input: {
    visitId: string;
    data: unknown;
  }) => mocks.prismaUpdate({ where: { id: input.visitId }, data: input.data }),
}));

import { runLayer4GenerateSoap, type Layer4Input } from "../04-generate-soap";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIX_DIR = path.join(HERE, "__fixtures__");
const SYS_GOLDEN = path.join(FIX_DIR, "l4-system-default.system.golden.txt");
const USER_GOLDEN = path.join(FIX_DIR, "l4-system-default.user.golden.txt");

const GOOD_SOAP = `## Subjective
Patient reports headache for 3 days.

## Objective
Vitals stable.

## Assessment
Tension-type headache.

## Plan
1. Trial ibuprofen 400 mg PRN.`;

// FIXED system-default scenario — no audio alert, no interpreter, stable
// entities + transcript. The only nondeterminism is the wrapAsData suffix.
const GOLDEN_INPUT: Layer4Input = {
  visitId: "golden-visit",
  practiceId: "golden-practice",
  userId: "golden-doctor",
  specialty: "primary-care",
  roleLabeledTranscript:
    "Doctor #0: What brings you in?\nPatient #1: A headache for three days.",
  entities: {
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
  } as unknown as Layer4Input["entities"],
  audioConfidenceStats: null,
  interpreterMode: false,
};

const normalizeSuffix = (s: string): string =>
  s.replace(/transcript_[0-9a-f]{16}/g, "transcript_HEX");

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({ id: "golden-visit" });
  mocks.logAudit.mockResolvedValue(undefined);
});
afterEach(() => vi.restoreAllMocks());

describe("L4 GOLDEN prompt-equivalence (system-default path)", () => {
  it("builds a SYSTEM prompt byte-identical to the pre-Phase-1 golden", async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: GOOD_SOAP });
    await runLayer4GenerateSoap(GOLDEN_INPUT);
    const { system } = mocks.modelCompleteText.mock.calls[0][0];

    if (!existsSync(SYS_GOLDEN)) {
      // CI must never self-baseline — a missing fixture there means the
      // committed golden was lost, NOT that we should re-snapshot whatever
      // the current code emits (that would silently pass on a stale baseline).
      if (process.env.CI) {
        throw new Error(
          "Golden SYSTEM fixture missing in CI — refusing to self-baseline. " +
            "Commit __fixtures__/l4-system-default.system.golden.txt.",
        );
      }
      mkdirSync(FIX_DIR, { recursive: true });
      writeFileSync(SYS_GOLDEN, system, "utf8");
    }
    expect(system).toBe(readFileSync(SYS_GOLDEN, "utf8"));
  });

  it("builds a USER prompt byte-identical to the golden (delimiter suffix normalized)", async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: GOOD_SOAP });
    await runLayer4GenerateSoap(GOLDEN_INPUT);
    const { user } = mocks.modelCompleteText.mock.calls[0][0];
    const userNorm = normalizeSuffix(user);

    if (!existsSync(USER_GOLDEN)) {
      if (process.env.CI) {
        throw new Error(
          "Golden USER fixture missing in CI — refusing to self-baseline. " +
            "Commit __fixtures__/l4-system-default.user.golden.txt.",
        );
      }
      mkdirSync(FIX_DIR, { recursive: true });
      writeFileSync(USER_GOLDEN, userNorm, "utf8");
    }
    expect(userNorm).toBe(readFileSync(USER_GOLDEN, "utf8"));
  });
});
