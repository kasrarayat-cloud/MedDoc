// ============================================================================
// Anchored verifier — ULTRASOUND measurement guard (deterministic, no spend).
// ----------------------------------------------------------------------------
// The accuracy promise for imaging reports is that a drifted MEASUREMENT
// (reflux time in s, vein diameter in mm) is caught the same way drifted SOAP
// vitals are: the verifier's deterministic digit override demotes any claim
// whose digits are not present in its anchored transcript span — and it does
// so EVEN WHEN the entailment judge approves the claim (the override cannot be
// overruled by the model). The verifier is section-agnostic, so this works on
// the ultrasound report's Findings exactly as on a SOAP Objective.
// Entailment is mocked to APPROVE EVERYTHING; anything still demoted is the
// deterministic digit guard.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));
vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: vi.fn(), completeText: mocks.modelCompleteText } };
});
vi.mock('@meddoc/db', () => ({
  default: {
    $queryRaw: vi.fn().mockResolvedValue([
      { id: 'u1', practiceId: 'p1', email: 'synthetic@example.test' },
    ]),
    transcribeVisit: { update: mocks.prismaUpdate },
  },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runAnchorVerify } from '../04b-anchor-verify';

const IDS = { visitId: 'vis-us', practiceId: 'p1', userId: 'u1' };

// Approve EVERY claim at the entailment stage → only the deterministic digit
// override can still demote.
function entailAll() {
  mocks.modelCompleteText.mockImplementation(
    async (args: { purpose?: string; user?: string }) => {
      if (args?.purpose === 'tm_anchor_entailment') {
        const n = (args.user?.match(/^CLAIM \d+:/gm) ?? []).length;
        return {
          text: JSON.stringify({
            verdicts: Array.from({ length: n }, (_, i) => ({ i, entailed: true })),
          }),
        };
      }
      throw new Error(`unexpected purpose ${args?.purpose}`);
    }
  );
}

// Digits as a real ASR transcript renders measurements.
const TRANSCRIPT = [
  '[Doctor #0, 0:10]: Right GSV measures 6.1 mm at the SFJ with reflux of 3.2 seconds.',
  '[Doctor #0, 0:25]: Left common femoral vein is patent and fully compressible, no reflux.',
].join('\n');
const SPAN = 'Right GSV measures 6.1 mm at the SFJ with reflux of 3.2 seconds.';

beforeEach(() => {
  vi.clearAllMocks();
  process.env.TRANSCRIBE_MD_EVIDENCE_ANCHORS = 'true';
  delete process.env.MOCK_AI_CALLS;
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.logAudit.mockResolvedValue(undefined);
});

describe('ultrasound measurement guard (deterministic)', () => {
  it('a DRIFTED reflux time is demoted even with an approving entailment judge', async () => {
    entailAll();
    // Dictation said 3.2 s; the draft asserts 4.8 s — the digits 4.8 are NOT
    // in the anchored span, so the deterministic override demotes it.
    const res = await runAnchorVerify({
      ...IDS,
      anchoredDraft: `## Findings\nRight GSV reflux time is 4.8 s at the SFJ. ⟦A:"${SPAN}"⟧`,
      roleLabeledTranscript: TRANSCRIPT,
    });
    // The drifted-measurement claim must NOT survive in the body.
    expect(res.body).not.toContain('4.8');
    expect(res.suggestions.length).toBeGreaterThan(0);
  });

  it('a CORRECT measurement (digits present in the span) survives in the body', async () => {
    entailAll();
    const res = await runAnchorVerify({
      ...IDS,
      anchoredDraft: `## Findings\nRight GSV is 6.1 mm at the SFJ. ⟦A:"${SPAN}"⟧`,
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(res.body).toContain('6.1');
  });
});
