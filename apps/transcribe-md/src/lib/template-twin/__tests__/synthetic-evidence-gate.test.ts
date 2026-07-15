import type { ModelClient } from '@meddoc/ai';
import { describe, expect, it, vi } from 'vitest';

import {
  assertTemplateTwinSyntheticEvidencePhiFree,
  TemplateTwinSyntheticEvidenceRejectedError,
  TemplateTwinSyntheticEvidenceScanUnavailableError,
} from '../synthetic-evidence-gate';

const BASE = {
  practiceId: 'practice-synthetic-gate',
  userId: 'doctor-synthetic-gate',
};

function client(result: unknown) {
  const complete = vi.fn().mockResolvedValue(result);
  return {
    complete,
    value: { complete } as unknown as Pick<ModelClient, 'complete'>,
  };
}

describe('Template Twin synthetic evidence privacy gate', () => {
  it('accepts explicitly synthetic identifier-free evidence after the independent scan', async () => {
    const safe = client({
      directIdentifierClasses: [],
      appearsExplicitlySynthetic: true,
      anyUncertain: false,
    });

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText:
          'Synthetic test only. The fictional patient reports mock wrist discomfort.',
        client: safe.value,
      }),
    ).resolves.toBeUndefined();

    expect(safe.complete).toHaveBeenCalledWith(
      expect.objectContaining({
        purpose: 'tm_template_synthetic_phi_scan',
        provider: 'anthropic',
        visitId: null,
      }),
    );
  });

  it('rejects text that is not explicitly marked as synthetic before model egress', async () => {
    const safe = client({
      directIdentifierClasses: [],
      appearsExplicitlySynthetic: true,
      anyUncertain: false,
    });

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText: 'The patient reports wrist discomfort and uses a brace.',
        client: safe.value,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
    expect(safe.complete).not.toHaveBeenCalled();
  });

  it('rejects structured identifiers deterministically before model egress', async () => {
    const safe = client({
      directIdentifierClasses: [],
      appearsExplicitlySynthetic: true,
      anyUncertain: false,
    });

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText:
          'Synthetic test only. Contact example.person@synthetic.test about wrist discomfort.',
        client: safe.value,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
    expect(safe.complete).not.toHaveBeenCalled();
  });

  it('fails closed when the independent scan flags identifiers or uncertainty', async () => {
    const unsafe = client({
      directIdentifierClasses: ['patient-name'],
      appearsExplicitlySynthetic: true,
      anyUncertain: true,
    });

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText:
          'Synthetic example case with wrist discomfort and no contact information.',
        client: unsafe.value,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
  });

  it('fails closed when the privacy provider is unavailable', async () => {
    const complete = vi.fn().mockRejectedValue(new Error('synthetic outage'));

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText:
          'Synthetic example case with wrist discomfort and no identifiers.',
        client: {
          complete,
        } as unknown as Pick<ModelClient, 'complete'>,
      }),
    ).rejects.toBeInstanceOf(
      TemplateTwinSyntheticEvidenceScanUnavailableError,
    );
  });
});
