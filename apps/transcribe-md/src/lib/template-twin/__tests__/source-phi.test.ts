import { describe, expect, it, vi } from 'vitest';

import {
  buildSyntheticDocx,
  syntheticOpc,
} from '../../note-template-docx/__tests__/synthetic-docx';
import {
  assertTemplateTwinSourcePhiFree,
  TemplateTwinPhiRejectedError,
  TemplateTwinPhiScanUnavailableError,
} from '../source-phi';

const cleanDocument = syntheticOpc.documentXml.replaceAll('2026-01-01', 'Date');

describe('Template Twin immutable-source PHI gate', () => {
  it('uses the existing model architecture after deterministic extraction', async () => {
    const complete = vi.fn().mockResolvedValue({
      phiFields: [],
      anyUncertain: false,
    });
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({ documentXml: cleanDocument }),
        practiceId: 'practice_1',
        userId: 'doctor_1',
        client: { complete } as never,
      }),
    ).resolves.toBeUndefined();
    expect(complete).toHaveBeenCalledOnce();
    expect(complete.mock.calls[0]?.[0]).toMatchObject({
      provider: 'anthropic',
      purpose: 'tm_template_phi_scan',
      temperature: 0,
    });
  });

  it('rejects structured patient-specific values before the model call', async () => {
    const complete = vi.fn();
    const documentXml = cleanDocument.replace(
      'Synthetic clinical template',
      'Encounter 2026-07-15',
    );
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({ documentXml }),
        practiceId: 'practice_1',
        userId: 'doctor_1',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiRejectedError);
    expect(complete).not.toHaveBeenCalled();
  });

  it('fails closed when the independent model scan is uncertain or unavailable', async () => {
    const source = await buildSyntheticDocx({ documentXml: cleanDocument });
    await expect(
      assertTemplateTwinSourcePhiFree({
        source,
        practiceId: 'practice_1',
        userId: 'doctor_1',
        client: {
          complete: vi.fn().mockResolvedValue({
            phiFields: [],
            anyUncertain: true,
          }),
        } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiRejectedError);

    await expect(
      assertTemplateTwinSourcePhiFree({
        source,
        practiceId: 'practice_1',
        userId: 'doctor_1',
        client: { complete: vi.fn().mockRejectedValue(new Error('synthetic outage')) } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiScanUnavailableError);
  });
});
