// ============================================================================
// The verifier is AUDIT-ONLY — the contract, pinned.
// ----------------------------------------------------------------------------
// The anchored-suggestion lane is gone. What replaced it is narrow and worth
// stating precisely, because "we removed the safety lane" and "we stopped
// checking" are very different changes and only the first one happened:
//
//   1. The verifier STILL RUNS and still judges every claim.
//   2. Nothing it finds becomes pending state — no suggestedClaims, no cards,
//      no Accept/Dismiss. Every generated line reaches the draft the physician
//      reviews and signs.
//   3. What it found is recorded as ANCHOR_FLAGS_RECORDED, category counts
//      only — visitId + {reason: n} — so the audit stream stays PHI-free.
//
// The fixture that matters most here is the SYNTHETIC CONTRADICTION: a claim
// that flatly contradicts the transcript must still be DETECTED and counted.
// If that ever stops firing, the verifier has quietly become a no-op and the
// audit stream is decoration.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { complete: vi.fn(), completeText: mocks.modelCompleteText },
  };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { Prisma } from '@prisma/client';
import { runAnchorVerify } from '../04b-anchor-verify';
import { runLayer4GenerateSoap } from '../04-generate-soap';
import { specialtyGuidance } from '../../prompts/specialty-guidance';

const TRANSCRIPT = [
  '[Doctor #0, 0:10]: any chest pain at all?',
  '[Patient #1, 0:20]: no chest pain, none whatsoever.',
  '[Doctor #0, 0:30]: take 500 milligrams twice daily for three days.',
].join('\n');

const IDS = { visitId: 'vis-audit-only', practiceId: 'p1', userId: 'u1' };

const L4_INPUT = {
  ...IDS,
  specialty: 'primary-care',
  roleLabeledTranscript: TRANSCRIPT,
  entities: {} as never,
  audioConfidenceStats: null,
};

function entailAll() {
  mocks.modelCompleteText.mockImplementation(
    async (args: { purpose?: string; user?: string }) => {
      if (args?.purpose === 'tm_anchor_entailment') {
        const n = ((args.user ?? '').match(/^CLAIM \d+:/gm) ?? []).length;
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

beforeEach(() => {
  vi.clearAllMocks();
  process.env.TRANSCRIBE_MD_EVIDENCE_ANCHORS = 'true';
  delete process.env.MOCK_AI_CALLS;
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.logAudit.mockResolvedValue(undefined);
});

describe('audit-only — the verifier still detects, it just no longer edits', () => {
  it('SYNTHETIC CONTRADICTION: a claim opposing the transcript is still caught', async () => {
    entailAll();
    // The transcript says "no chest pain, none whatsoever". The draft asserts
    // the opposite and anchors it to that very span. An approving entailment
    // mock cannot rescue it — polarity is a DETERMINISTIC override.
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nPatient reports crushing chest pain. ⟦A:"no chest pain, none whatsoever."⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.suggestions).toHaveLength(1);
    expect(r.suggestions[0].reason).toBe('negation_mismatch');
    // Still DETECTED — and now also still SERVED, because audit-only means the
    // physician sees everything and the finding goes to the audit log.
    expect(r.fullBody).toContain('crushing chest pain');
    expect(r.fullBody).not.toContain('⟦');
  });

  it('fullBody carries every line; body (the old lane shape) still filters', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Assessment\nLikely olecranon bursitis.',
      roleLabeledTranscript: TRANSCRIPT,
    });
    // The two differ on purpose — `body` keeps the demotion machinery honest
    // and pinned; `fullBody` is what ships to the physician.
    expect(r.body).not.toContain('bursitis');
    expect(r.fullBody).toContain('bursitis');
  });

  it('writes ANCHOR_FLAGS_RECORDED with CATEGORY COUNTS and no note text', async () => {
    mocks.modelCompleteText.mockImplementation(
      async (args: { purpose?: string; user?: string }) => {
        if (args?.purpose === 'tm_soap_draft') {
          return {
            text: [
              '## Subjective',
              'Patient reports crushing chest pain. ⟦A:"no chest pain, none whatsoever."⟧',
              'Likely olecranon bursitis.',
              '',
              '## Plan',
              '1. Take 500 milligrams twice daily for three days. ⟦A:"take 500 milligrams twice daily for three days."⟧',
            ].join('\n'),
          };
        }
        if (args?.purpose === 'tm_anchor_entailment') {
          const n = ((args.user ?? '').match(/^CLAIM \d+:/gm) ?? []).length;
          return {
            text: JSON.stringify({
              verdicts: Array.from({ length: n }, (_, i) => ({ i, entailed: true })),
            }),
          };
        }
        throw new Error('unexpected');
      }
    );

    await runLayer4GenerateSoap(L4_INPUT as never);

    const call = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((a) => a?.action === 'ANCHOR_FLAGS_RECORDED');
    expect(call, 'the verifier must record what it found').toBeTruthy();
    expect(call.targetId).toBe(IDS.visitId);
    expect(call.metadata.visitId).toBe(IDS.visitId);
    expect(call.metadata.flagCount).toBeGreaterThan(0);
    expect(call.metadata.categories).toMatchObject({ negation_mismatch: 1 });

    // PHI DISCIPLINE: the row carries counts, never content. Nothing in the
    // serialized metadata may echo a line of the note.
    const serialized = JSON.stringify(call.metadata);
    expect(serialized).not.toContain('chest pain');
    expect(serialized).not.toContain('bursitis');
  });

  it('NO pending-suggestion state is ever persisted — the column is cleared', async () => {
    entailAll();
    mocks.modelCompleteText.mockImplementation(
      async (args: { purpose?: string; user?: string }) => {
        if (args?.purpose === 'tm_soap_draft') {
          return { text: '## Assessment\nLikely olecranon bursitis.' };
        }
        if (args?.purpose === 'tm_anchor_entailment') {
          const n = ((args.user ?? '').match(/^CLAIM \d+:/gm) ?? []).length;
          return {
            text: JSON.stringify({
              verdicts: Array.from({ length: n }, (_, i) => ({ i, entailed: true })),
            }),
          };
        }
        throw new Error('unexpected');
      }
    );

    const out = await runLayer4GenerateSoap(L4_INPUT as never);
    const data = mocks.prismaUpdate.mock.calls[0][0].data;
    // Actively CLEARED, not merely absent: a visit re-run must not keep a lane
    // pointing at a superseded draft.
    expect(data.suggestedClaims).toBe(Prisma.DbNull);
    // …and the content the lane used to quarantine is in the note.
    expect(out).toContain('bursitis');
  });
});
