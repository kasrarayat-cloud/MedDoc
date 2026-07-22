import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks: the twin fill-step must never touch a real DB / real fill engine here.
// vi.hoisted so the factory refs are initialised before the hoisted vi.mock calls.
const { findUnique, processTemplateTwinVisit } = vi.hoisted(() => ({
  findUnique: vi.fn(),
  processTemplateTwinVisit: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: { templateTwinCompiledVersion: { findUnique } },
}));
vi.mock('@/lib/template-twin/fill-engine', () => ({ processTemplateTwinVisit }));

import { runTemplateTwinFillStep } from '../template-twin-fill-step';

const INPUT = {
  visitId: 'visit-1',
  practiceId: 'practice-1',
  doctorId: 'doctor-1',
  noteTemplateId: 'tmpl-1',
  noteTemplateVersion: 1,
  inputMode: 'text_notes',
  contextText: 'raw bullets',
  entities: { chief_complaint: null },
  generatedNote: 'FINDINGS\nThe generated note body.',
};

describe('runTemplateTwinFillStep — flag-gated + fail-safe', () => {
  beforeEach(() => {
    findUnique.mockReset();
    processTemplateTwinVisit.mockReset();
    delete process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX;
  });
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX;
  });

  it('flag OFF: no-op — skipped, zero DB / fill calls (worker behavior unchanged)', async () => {
    const r = await runTemplateTwinFillStep(INPUT);
    expect(r).toEqual({ status: 'skipped', reason: 'flag_off' });
    expect(findUnique).not.toHaveBeenCalled();
    expect(processTemplateTwinVisit).not.toHaveBeenCalled();
  });

  it('flag ON, not a certified twin: skipped without running the fill/claim', async () => {
    process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';
    findUnique.mockResolvedValue({ certificationStatus: 'NEEDS_CONFIRMATION' });
    const r = await runTemplateTwinFillStep(INPUT);
    expect(r).toEqual({ status: 'skipped', reason: 'not_certified_twin' });
    expect(processTemplateTwinVisit).not.toHaveBeenCalled();
  });

  it('flag ON, certified twin: runs the fill and reports round-trip', async () => {
    process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';
    findUnique.mockResolvedValue({ certificationStatus: 'CERTIFIED' });
    processTemplateTwinVisit.mockResolvedValue({ render: { verification: { verified: true } } });
    const r = await runTemplateTwinFillStep(INPUT);
    expect(r).toEqual({ status: 'filled', roundTripVerified: true });
    expect(processTemplateTwinVisit).toHaveBeenCalledOnce();
    // input mode mapped text_notes -> text; generated note threaded to the fill
    expect(processTemplateTwinVisit.mock.calls[0][0]).toMatchObject({
      inputMode: 'text',
      visitId: 'visit-1',
      generatedNote: 'FINDINGS\nThe generated note body.',
    });
  });

  it('FAIL-SAFE: a fill failure NEVER throws — returns failed, visit can proceed', async () => {
    process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';
    findUnique.mockResolvedValue({ certificationStatus: 'CERTIFIED' });
    processTemplateTwinVisit.mockRejectedValue(new Error('SOURCE_ARTIFACT_UNAVAILABLE'));
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const r = await runTemplateTwinFillStep(INPUT);
    expect(r).toEqual({ status: 'failed', reason: 'SOURCE_ARTIFACT_UNAVAILABLE' });
    expect(warn).toHaveBeenCalled(); // logged + surfaced
    warn.mockRestore();
  });

  it('input-mode mapping: voice_dictation -> dictation, audio_upload -> conversation', async () => {
    process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';
    findUnique.mockResolvedValue({ certificationStatus: 'CERTIFIED' });
    processTemplateTwinVisit.mockResolvedValue({ render: null });
    await runTemplateTwinFillStep({ ...INPUT, inputMode: 'voice_dictation' });
    expect(processTemplateTwinVisit.mock.calls.at(-1)![0]).toMatchObject({ inputMode: 'dictation' });
    await runTemplateTwinFillStep({ ...INPUT, inputMode: 'audio_upload' });
    expect(processTemplateTwinVisit.mock.calls.at(-1)![0]).toMatchObject({ inputMode: 'conversation' });
  });
});
