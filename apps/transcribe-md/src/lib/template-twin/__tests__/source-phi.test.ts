import { afterEach, describe, expect, it, vi } from 'vitest';
import { createHash } from 'node:crypto';

import {
  buildSyntheticDocx,
  syntheticOpc,
} from '../../note-template-docx/__tests__/synthetic-docx';
import { TemplateDocxError } from '../../note-template-docx';
import {
  assertTemplateTwinSourcePhiFree,
  TemplateTwinPhiRejectedError,
  TemplateTwinPhiScanUnavailableError,
  TemplateTwinSourcePrivacyUnsupportedError,
} from '../source-phi';

const cleanDocument = syntheticOpc.documentXml.replaceAll('2026-01-01', 'Date');

afterEach(() => {
  delete process.env.TEMPLATE_TWIN_APPROVED_STATIC_ASSETS_BY_PRACTICE_JSON;
  delete process.env.TEMPLATE_TWIN_APPROVED_STATIC_ASSET_SHA256;
});

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
    ).resolves.toMatchObject({
      profileVersion: 'template-twin-source-phi-safe-alpha-v1',
      approvedStaticAssetCount: 0,
      approvedStaticAssetUsedCount: 0,
    });
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

  it.each([
    {
      name: 'tracked-deleted text',
      documentXml: cleanDocument.replace(
        '<w:sectPr>',
        '<w:p><w:del><w:r><w:delText>deleted&#46;patient&#64;example.test</w:delText></w:r></w:del></w:p><w:sectPr>',
      ),
      extraEntries: {},
    },
    {
      name: 'drawing alternative text',
      documentXml: cleanDocument.replace(
        '<w:sectPr>',
        '<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><wp:docPr id="1" name="Synthetic" descr="hidden.patient@example.test"/></wp:inline></w:drawing></w:r></w:p><w:sectPr>',
      ),
      extraEntries: {},
    },
    {
      name: 'document metadata',
      documentXml: cleanDocument,
      extraEntries: {
        'docProps/core.xml':
          '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>metadata.patient@example.test</dc:creator></cp:coreProperties>',
      },
    },
  ] as Array<{
    name: string;
    documentXml: string;
    extraEntries: Record<string, string | Uint8Array>;
  }>)('rejects PHI hidden in $name before immutable storage', async ({
    documentXml,
    extraEntries,
  }) => {
    const complete = vi.fn();
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({ documentXml, extraEntries }),
        practiceId: 'practice_1',
        userId: 'doctor_1',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiRejectedError);
    expect(complete).not.toHaveBeenCalled();
  });

  it('rejects custom XML and unapproved media without claiming they were scanned', async () => {
    const complete = vi.fn();
    for (const extraEntries of [
      { 'customXml/item1.xml': '<root>synthetic</root>' },
      { 'word/media/image1.png': new Uint8Array([1, 2, 3, 4]) },
    ] as Array<Record<string, string | Uint8Array>>) {
      await expect(
        assertTemplateTwinSourcePhiFree({
          source: await buildSyntheticDocx({
            documentXml: cleanDocument,
            extraEntries,
          }),
          practiceId: 'practice_1',
          userId: 'doctor_1',
          client: { complete } as never,
        }),
      ).rejects.toBeInstanceOf(TemplateTwinSourcePrivacyUnsupportedError);
    }
    expect(complete).not.toHaveBeenCalled();
  });

  it('allows only a byte-exact administratively approved static asset', async () => {
    const asset = new Uint8Array([1, 2, 3, 4]);
    const digest = createHash('sha256').update(asset).digest('hex');
    const complete = vi.fn().mockResolvedValue({
      phiFields: [],
      anyUncertain: false,
    });
    process.env.TEMPLATE_TWIN_APPROVED_STATIC_ASSETS_BY_PRACTICE_JSON =
      JSON.stringify({ practice_1: [digest] });
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({
          documentXml: cleanDocument,
          extraEntries: { 'word/media/image1.png': asset },
        }),
        practiceId: 'practice_1',
        userId: 'doctor_1',
        client: { complete } as never,
      }),
    ).resolves.toMatchObject({
      approvedStaticAssetCount: 1,
      approvedStaticAssetUsedCount: 1,
      approvedStaticAssetPolicySha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      approvedStaticAssetUsageSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
    });
    expect(complete).toHaveBeenCalledOnce();
  });

  it('scopes configured static-asset approvals to one exact practice', async () => {
    const asset = new Uint8Array([5, 6, 7, 8]);
    const digest = createHash('sha256').update(asset).digest('hex');
    process.env.TEMPLATE_TWIN_APPROVED_STATIC_ASSETS_BY_PRACTICE_JSON =
      JSON.stringify({ practice_alpha: [digest] });
    const source = await buildSyntheticDocx({
      documentXml: cleanDocument,
      extraEntries: { 'word/media/image1.png': asset },
    });
    const complete = vi.fn().mockResolvedValue({
      phiFields: [],
      anyUncertain: false,
    });

    await expect(
      assertTemplateTwinSourcePhiFree({
        source,
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete } as never,
      }),
    ).resolves.toMatchObject({
      approvedStaticAssetCount: 1,
      approvedStaticAssetUsedCount: 1,
    });
    await expect(
      assertTemplateTwinSourcePhiFree({
        source,
        practiceId: 'practice_beta',
        userId: 'doctor_beta',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSourcePrivacyUnsupportedError);
  });

  it('rejects identifier-bearing media paths even for approved bytes', async () => {
    const asset = new Uint8Array([9, 10, 11, 12]);
    const digest = createHash('sha256').update(asset).digest('hex');
    process.env.TEMPLATE_TWIN_APPROVED_STATIC_ASSETS_BY_PRACTICE_JSON =
      JSON.stringify({ practice_alpha: [digest] });
    const complete = vi.fn();
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({
          documentXml: cleanDocument,
          extraEntries: { 'word/media/patient-example.png': asset },
        }),
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSourcePrivacyUnsupportedError);
    expect(complete).not.toHaveBeenCalled();
  });

  it('does not honor the former global cross-tenant media allowlist', async () => {
    const asset = new Uint8Array([13, 14, 15, 16]);
    const digest = createHash('sha256').update(asset).digest('hex');
    process.env.TEMPLATE_TWIN_APPROVED_STATIC_ASSET_SHA256 = digest;
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({
          documentXml: cleanDocument,
          extraEntries: { 'word/media/image1.png': asset },
        }),
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete: vi.fn() } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSourcePrivacyUnsupportedError);
  });

  it('rejects identifier-bearing OOXML part names before the model call', async () => {
    const complete = vi.fn();
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({
          documentXml: cleanDocument,
          extraEntries: {
            'word/headerpatient-example.xml':
              '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
          },
        }),
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateDocxError);
    expect(complete).not.toHaveBeenCalled();
  });

  it('scans preserved relationship identifiers and targets for hidden PHI', async () => {
    const complete = vi.fn();
    const documentRelationships = syntheticOpc.documentRelationships.replace(
      'Id="rIdHeader"',
      'Id="hidden.patient@example.test"',
    );
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({
          documentXml: cleanDocument,
          documentRelationships,
        }),
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiRejectedError);
    expect(complete).not.toHaveBeenCalled();
  });

  it('scans relationship types and content types for hidden identifiers', async () => {
    const complete = vi.fn();
    const documentRelationships = syntheticOpc.documentRelationships.replace(
      'relationships/header',
      'relationships/header/patient-123456789',
    );
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({
          documentXml: cleanDocument,
          documentRelationships,
        }),
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiRejectedError);
    expect(complete).not.toHaveBeenCalled();

    const contentTypes = syntheticOpc.contentTypes.replace(
      'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml',
      'application/vnd.patient-123456789+xml',
    );
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({
          documentXml: cleanDocument,
          contentTypes,
        }),
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiRejectedError);
    expect(complete).not.toHaveBeenCalled();
  });

  it('scans unknown and foreign-namespaced attribute values', async () => {
    const complete = vi.fn();
    const documentXml = cleanDocument
      .replace(
        '<w:document ',
        '<w:document xmlns:synthetic="https://synthetic.test/metadata" ',
      )
      .replace(
        '<w:body>',
        '<w:body synthetic:patient="hidden.patient@example.test">',
      );
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({ documentXml }),
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiRejectedError);
    expect(complete).not.toHaveBeenCalled();
  });

  it('fails closed on malformed practice-scoped asset approval configuration', async () => {
    process.env.TEMPLATE_TWIN_APPROVED_STATIC_ASSETS_BY_PRACTICE_JSON =
      '{not-valid-json';
    await expect(
      assertTemplateTwinSourcePhiFree({
        source: await buildSyntheticDocx({ documentXml: cleanDocument }),
        practiceId: 'practice_alpha',
        userId: 'doctor_alpha',
        client: { complete: vi.fn() } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiScanUnavailableError);
  });
});
