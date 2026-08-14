// ============================================================================
// GATE — the L6b STATIC-REGION ARM: the doctor's assembled bytes survive the
// POLISHER, or the polish is rejected, loudly (ruling #106(g), SPEC §4.3a(a)).
// ----------------------------------------------------------------------------
// ⚠️ WHY IT CANNOT BE COVERED BY THE L4 TESTS. `06-polish.ts` calls a model that
// rewrites the WHOLE note. Statics protected at L4 were still re-writable here,
// so a fix that stopped at L4 would look right and still paraphrase the
// doctor's paragraph. That is #106(g)(1), and this file is its red-and-green
// proof.
//
// ⚠️ AND THE VERIFIER ABOVE CANNOT SEE THIS CLASS, which is the argument for a
// separate arm rather than a stricter prompt: "500 milliseconds" → "0.5
// seconds" adds no clinical content, removes none and flips no negation, so the
// fidelity verifier calls it rewording — correctly, for the question it is
// asked. The doctor's form is a different question.
//
// ⚠️ THE FIXTURE IS SANITIZED, PER SPEC §4.3a(e).
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  completeText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
  applyAdditiveReviewState: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: vi.fn(), completeText: mocks.completeText } };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/worker/finalize-review-state', () => ({
  applyAdditiveReviewState: mocks.applyAdditiveReviewState,
}));

import { runLayer6Polish, type Layer6Input } from '../06-polish';
import {
  resetStaticDivergenceCounts,
  staticDivergenceCount,
} from '@/worker/note-templates/static-divergence-counter';
import type { ResolvedNoteTemplate } from '@/worker/note-templates/build-soap-prompt';
import type { NoteTemplateSection } from '@/worker/note-templates/system-default-template';

const TECHNIQUE_TEXT =
  'A duplex Doppler color flow ultrasound study was performed in the upright ' +
  'position. This study documents reflux as lasting more than 500 milliseconds ' +
  'in either the saphenous veins or the perforator veins.';

function section(
  over: Partial<NoteTemplateSection> & { key: string; label: string; order: number }
): NoteTemplateSection {
  return {
    formatHint: 'prose',
    styleInstructions: null,
    defaultText: null,
    defaultTextMode: 'omit_unless_supported',
    ...over,
  } as NoteTemplateSection;
}

const TECHNIQUE_STATIC = section({
  key: 'technique',
  label: 'TECHNIQUE',
  order: 2,
  defaultText: TECHNIQUE_TEXT,
  defaultTextMode: 'always_include',
});
const TECHNIQUE_SCAFFOLD = { ...TECHNIQUE_STATIC, defaultTextMode: 'scaffold_confirm' } as NoteTemplateSection;
const EXAM = section({ key: 'exam', label: 'EXAM', order: 1 });

const template = (sections: NoteTemplateSection[]): ResolvedNoteTemplate => ({
  id: 'tmpl_test',
  version: 3,
  isSystemDefault: false,
  sections,
  styleProfile: {} as never,
});

const DRAFT = ['## EXAM', 'Bilateral.', '', '## TECHNIQUE', TECHNIQUE_TEXT].join('\n');

const CRITIQUE = {
  issues: [
    {
      severity: 'minor' as const,
      location: 'EXAM',
      description: 'Wording is clumsy.',
      suggested_fix: 'Reword the exam line more clearly.',
    },
  ],
  overall_quality: 'medium' as const,
  safe_to_sign_without_review: true,
};

const input = (t: ResolvedNoteTemplate): Layer6Input => ({
  visitId: 'v1',
  practiceId: 'p1',
  userId: 'd1',
  soapDraft: DRAFT,
  critique: CRITIQUE,
  noteTemplate: t,
});

/** Answers `tm_polish` with `polished`, and always passes the fidelity
 *  verifier — so the ONLY thing that can reject is the static arm. */
function wire(polished: string) {
  mocks.completeText.mockImplementation(
    async (args: { purpose: string }) =>
      args.purpose === 'tm_polish'
        ? { text: polished }
        : { text: '{"violations":[]}' }
  );
}

const auditRows = () =>
  mocks.logAudit.mock.calls
    .map((c) => c[0])
    .filter((r) => r.action === 'L6_FABRICATION_REJECTED');

beforeEach(() => {
  vi.clearAllMocks();
  resetStaticDivergenceCounts();
  mocks.prismaUpdate.mockResolvedValue({ id: 'v1' });
  mocks.logAudit.mockResolvedValue(undefined);
  mocks.applyAdditiveReviewState.mockResolvedValue(undefined);
});
afterEach(() => vi.restoreAllMocks());

describe('⚠️ RED — the polisher normalises the doctor\'s paragraph', () => {
  const PARAPHRASED = DRAFT.replace('500 milliseconds', '0.5 seconds');

  it('rejects the polish and serves the draft, so the bytes survive', async () => {
    wire(PARAPHRASED);
    const out = await runLayer6Polish(input(template([EXAM, TECHNIQUE_STATIC])));
    expect(out.polishRejected).toBe(true);
    expect(out.soapFinal).toBe(DRAFT);
    expect(out.soapFinal).toContain('500 milliseconds');
    expect(out.soapFinal).not.toContain('0.5 seconds');
  });

  it('NAMES the section in the doctor-facing reason', async () => {
    wire(PARAPHRASED);
    const out = await runLayer6Polish(input(template([EXAM, TECHNIQUE_STATIC])));
    expect(out.reviewReason).toContain('TECHNIQUE');
    expect(out.reviewReason).toContain('your own form');
    expect(out.needsReview).toBe(true);
  });

  it('logs the NAMED reason and the template, per #106(g)(4)', async () => {
    wire(PARAPHRASED);
    await runLayer6Polish(input(template([EXAM, TECHNIQUE_STATIC])));
    const rows = auditRows();
    expect(rows).toHaveLength(1);
    expect(rows[0].metadata.gateError).toBe('static_region_diverged');
    expect(rows[0].metadata.divergedSections).toEqual(['technique']);
    expect(rows[0].metadata.noteTemplateId).toBe('tmpl_test');
    expect(rows[0].metadata.noteTemplateVersion).toBe(3);
    expect(rows[0].metadata.regionsChecked).toBe(1);
  });

  // ⚠️ READ BACK, not merely called. `logAudit` is fire-and-forget by design,
  // so asserting the call asserts the call. The counter is the part something
  // can actually read.
  it('increments the PER-TEMPLATE counter, and it is readable', async () => {
    wire(PARAPHRASED);
    expect(staticDivergenceCount('tmpl_test')).toBe(0);
    await runLayer6Polish(input(template([EXAM, TECHNIQUE_STATIC])));
    expect(staticDivergenceCount('tmpl_test')).toBe(1);
    await runLayer6Polish(input(template([EXAM, TECHNIQUE_STATIC])));
    expect(staticDivergenceCount('tmpl_test')).toBe(2);
    expect(staticDivergenceCount('some-other-template')).toBe(0);
  });

  it('catches a SILENT DELETION of the whole region, not only a reword', async () => {
    wire('## EXAM\nBilateral, reworded.\n\n## TECHNIQUE\n');
    const out = await runLayer6Polish(input(template([EXAM, TECHNIQUE_STATIC])));
    expect(out.polishRejected).toBe(true);
    expect(out.soapFinal).toBe(DRAFT);
  });
});

describe('⚠️ GREEN — the half everybody skips: it must also LET POLISH THROUGH', () => {
  it('accepts a polish that leaves the static region byte-identical', async () => {
    wire(DRAFT.replace('Bilateral.', 'Bilateral lower extremity.'));
    const out = await runLayer6Polish(input(template([EXAM, TECHNIQUE_STATIC])));
    expect(out.polishRejected).toBe(false);
    expect(out.soapFinal).toContain('Bilateral lower extremity.');
    expect(out.soapFinal).toContain('500 milliseconds');
    expect(auditRows()).toHaveLength(0);
    expect(staticDivergenceCount('tmpl_test')).toBe(0);
  });

  it('is INERT for a template with no always_include section', async () => {
    // The same paraphrase, against a template whose TECHNIQUE is still a
    // scaffold: nothing is assembled, so there is nothing to guard, and today's
    // behaviour is unchanged.
    wire(DRAFT.replace('500 milliseconds', '0.5 seconds'));
    const out = await runLayer6Polish(input(template([EXAM, TECHNIQUE_SCAFFOLD])));
    expect(out.polishRejected).toBe(false);
    expect(out.soapFinal).toContain('0.5 seconds');
    expect(auditRows()).toHaveLength(0);
  });

  it('never runs at all when there is no polish model call', async () => {
    wire('unused');
    const out = await runLayer6Polish({
      ...input(template([EXAM, TECHNIQUE_STATIC])),
      critique: { issues: [], overall_quality: 'high', safe_to_sign_without_review: true },
    });
    expect(mocks.completeText).not.toHaveBeenCalled();
    expect(out.soapFinal).toBe(DRAFT);
    expect(out.polishRejected).toBe(false);
  });
});

describe('the fidelity verdict still owns its own class', () => {
  it('a verifier violation rejects with the ORIGINAL reason, not the static one', async () => {
    mocks.completeText.mockImplementation(async (args: { purpose: string }) =>
      args.purpose === 'tm_polish'
        ? { text: DRAFT.replace('Bilateral.', 'Bilateral, and started aspirin 81 mg.') }
        : { text: '{"violations":[{"kind":"addition","summary":"new medication"}]}' }
    );
    const out = await runLayer6Polish(input(template([EXAM, TECHNIQUE_STATIC])));
    expect(out.polishRejected).toBe(true);
    expect(out.reviewReason).toContain('fabrication gate');
    expect(out.reviewReason).not.toContain('your own form');
    expect(auditRows()[0].metadata.gateError).toBeNull();
    expect(staticDivergenceCount('tmpl_test')).toBe(0);
  });
});
