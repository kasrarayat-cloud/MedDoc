import { readFileSync } from 'node:fs';
import path from 'node:path';

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

  it('does NOT reject a clinic-address ZIP that lives inside a dropdown option (options are format, not PHI)', async () => {
    // The real WM_IOV template carries a clinic address "…, CA 92604" as an
    // "Address" dropdown option — enumerated format reused across every patient,
    // not patient PHI. Its 5-digit ZIP matches the deterministic long-id detector;
    // the gate must NEUTRALISE {{one of}} option lists before that check (mirroring
    // the note-format PHI gate) so a legit letterhead template still reaches the
    // model scan. Before the fix the deterministic check threw BEFORE the model
    // call (complete never invoked). With a clean model scan it must resolve.
    const complete = vi.fn().mockResolvedValue({ phiFields: [], anyUncertain: false });
    const bytes = new Uint8Array(
      readFileSync(path.resolve(process.cwd(), '../../WM IOV Template.docx')),
    );
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: bytes,
        practiceId: 'practice_1',
        userId: 'doctor_1',
        client: { complete } as never,
      }),
    ).resolves.toBeUndefined();
    expect(complete).toHaveBeenCalledOnce();
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
