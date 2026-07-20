import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

vi.mock('../provider-ownership', () => ({
  requireTemplateTwinProviderOwnershipContext: vi.fn(),
  runTemplateTwinOwnedModelComplete: vi.fn(
    async (input: {
      args: unknown;
      client: { complete(args: unknown): Promise<unknown> };
    }) => input.client.complete(input.args),
  ),
}));

import {
  buildSyntheticDocx,
  syntheticOpc,
} from '../../note-template-docx/__tests__/synthetic-docx';
import { inspectDocxPackage } from '../../note-template-docx';
import {
  TemplateTwinAuxiliaryPartUnsupportedError,
  assertStandardWordAuxiliaryPartsUnchanged,
  inspectStandardWordAuxiliaryParts,
} from '../auxiliary-parts';
import {
  TemplateTwinPhiRejectedError,
  TemplateTwinSourcePrivacyUnsupportedError,
  assertTemplateTwinSourcePhiFree,
} from '../source-phi';

const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const R =
  'http://schemas.openxmlformats.org/officeDocument/2006/relationships';

const GLOSSARY_CONTENT_TYPES = [
  '<Override PartName="/word/glossary/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.glossary+xml"/>',
  '<Override PartName="/word/glossary/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>',
  '<Override PartName="/word/glossary/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>',
  '<Override PartName="/word/glossary/webSettings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml"/>',
  '<Override PartName="/word/glossary/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>',
].join('');

const GLOSSARY_RELATIONSHIPS = `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rSettings" Type="${R}/settings" Target="settings.xml"/>
  <Relationship Id="rStyles" Type="${R}/styles" Target="styles.xml"/>
  <Relationship Id="rWeb" Type="${R}/webSettings" Target="webSettings.xml"/>
  <Relationship Id="rFonts" Type="${R}/fontTable" Target="fontTable.xml"/>
</Relationships>`;

function glossaryDocument(inner = '<w:docParts/>'): string {
  return `<w:glossaryDocument xmlns:w="${W}">${inner}</w:glossaryDocument>`;
}

async function glossaryDocx(options: {
  glossary?: string;
  glossaryRelationships?: string;
  contentTypes?: string;
  extraEntries?: Record<string, string | Uint8Array>;
} = {}): Promise<Uint8Array> {
  return buildSyntheticDocx({
    documentXml: syntheticOpc.documentXml.replaceAll('2026-01-01', 'Date'),
    contentTypes: (options.contentTypes ?? syntheticOpc.contentTypes).replace(
      '</Types>',
      `${GLOSSARY_CONTENT_TYPES}</Types>`,
    ),
    documentRelationships: syntheticOpc.documentRelationships.replace(
      '</Relationships>',
      `<Relationship Id="rGlossary" Type="${R}/glossaryDocument" Target="glossary/document.xml"/></Relationships>`,
    ),
    extraEntries: {
      'word/glossary/document.xml':
        options.glossary ?? glossaryDocument(),
      'word/glossary/settings.xml': `<w:settings xmlns:w="${W}"/>`,
      'word/glossary/styles.xml': `<w:styles xmlns:w="${W}"/>`,
      'word/glossary/webSettings.xml': `<w:webSettings xmlns:w="${W}"/>`,
      'word/glossary/fontTable.xml': `<w:fonts xmlns:w="${W}"/>`,
      'word/glossary/_rels/document.xml.rels':
        options.glossaryRelationships ?? GLOSSARY_RELATIONSHIPS,
      ...options.extraEntries,
    },
  });
}

describe('safe standard Word glossary/auxiliary inspection', () => {
  it('recognizes all six existing WM IOV glossary parts without inspecting or approving its media', () => {
    const fixture = resolve(
      process.cwd(),
      process.cwd().endsWith('/apps/transcribe-md')
        ? '../../WM IOV Template.docx'
        : 'WM IOV Template.docx',
    );
    const manifest = inspectStandardWordAuxiliaryParts(
      inspectDocxPackage(readFileSync(fixture)),
    );
    expect(manifest.parts).toHaveLength(6);
    expect(manifest.parts.map((part) => part.partName)).toEqual([
      'word/glossary/_rels/document.xml.rels',
      'word/glossary/document.xml',
      'word/glossary/fontTable.xml',
      'word/glossary/settings.xml',
      'word/glossary/styles.xml',
      'word/glossary/webSettings.xml',
    ]);
  });

  it('admits exactly the six bounded standard parts and fingerprints each byte stream', async () => {
    const source = await glossaryDocx();
    const manifest = inspectStandardWordAuxiliaryParts(
      inspectDocxPackage(source),
    );
    expect(manifest.parts).toHaveLength(6);
    expect(manifest.parts.map((part) => part.partName)).toEqual([
      'word/glossary/_rels/document.xml.rels',
      'word/glossary/document.xml',
      'word/glossary/fontTable.xml',
      'word/glossary/settings.xml',
      'word/glossary/styles.xml',
      'word/glossary/webSettings.xml',
    ]);
    expect(manifest.parts.every((part) => /^[a-f0-9]{64}$/.test(part.sha256))).toBe(
      true,
    );

    const complete = vi.fn().mockResolvedValue({
      phiFields: [],
      anyUncertain: false,
    });
    await expect(
      assertTemplateTwinSourcePhiFree({
        source,
        practiceId: 'practice_synthetic',
        userId: 'doctor_synthetic',
        client: { complete } as never,
      }),
    ).resolves.toMatchObject({
      auxiliaryPartCount: 6,
      auxiliaryInspectionProfileVersion:
        'template-twin-word-auxiliary-safe-v1',
    });
  });

  it('scans glossary visible text and rejects patient-shaped content before a model call', async () => {
    const complete = vi.fn();
    const source = await glossaryDocx({
      glossary: glossaryDocument(
        '<w:docParts><w:docPart><w:docPartBody><w:p><w:r><w:t>deleted.patient@example.test</w:t></w:r></w:p></w:docPartBody></w:docPart></w:docParts>',
      ),
    });
    await expect(
      assertTemplateTwinSourcePhiFree({
        source,
        practiceId: 'practice_synthetic',
        userId: 'doctor_synthetic',
        client: { complete } as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinPhiRejectedError);
    expect(complete).not.toHaveBeenCalled();
  });

  it('fails closed on tracked-deleted glossary text, active fields, and compatibility branches', async () => {
    const trackedDeleted = await glossaryDocx({
      glossary: glossaryDocument(
        '<w:docParts><w:docPart><w:docPartBody><w:p><w:del><w:r><w:delText>deleted.patient@example.test</w:delText></w:r></w:del></w:p></w:docPartBody></w:docPart></w:docParts>',
      ),
    });
    expect(() => inspectDocxPackage(trackedDeleted)).toThrowError(
      expect.objectContaining({
        name: 'TemplateDocxError',
        code: 'XML_HIDDEN_CONTENT_UNSUPPORTED',
      }),
    );

    for (const inner of [
      '<w:docParts><w:docPart><w:docPartBody><w:p><w:fldSimple w:instr="PAGE"/></w:p></w:docPartBody></w:docPart></w:docParts>',
      '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"><mc:Choice Requires="w"><w:docParts/></mc:Choice></mc:AlternateContent>',
    ]) {
      const inspected = inspectDocxPackage(
        await glossaryDocx({ glossary: glossaryDocument(inner) }),
      );
      expect(() => inspectStandardWordAuxiliaryParts(inspected)).toThrow(
        TemplateTwinAuxiliaryPartUnsupportedError,
      );
    }
  });

  it('rejects namespace shadowing, unexpected parts, custom XML, and excessive auxiliary bytes', async () => {
    const variants = [
      await glossaryDocx({
        glossary:
          '<evil:glossaryDocument xmlns:evil="https://synthetic.test/not-word"/>',
      }),
      await glossaryDocx({
        extraEntries: {
          'word/glossary/custom.xml': '<root/>',
        },
      }),
      await glossaryDocx({
        extraEntries: {
          'customXml/item1.xml': '<root>synthetic</root>',
        },
      }),
      await glossaryDocx({
        glossary: glossaryDocument(
          `<w:docParts><w:docPart><w:docPartBody><w:p><w:r><w:t>${'x'.repeat(270_000)}</w:t></w:r></w:p></w:docPartBody></w:docPart></w:docParts>`,
        ),
      }),
    ];
    for (const source of variants) {
      await expect(
        assertTemplateTwinSourcePhiFree({
          source,
          practiceId: 'practice_synthetic',
          userId: 'doctor_synthetic',
          client: { complete: vi.fn() } as never,
        }),
      ).rejects.toSatisfy(
        (error: unknown) =>
          error instanceof TemplateTwinSourcePrivacyUnsupportedError ||
          (error instanceof Error && error.name === 'TemplateDocxError'),
      );
    }
  });

  it.each([
    [
      'glossary document',
      'word/glossary/document.xml',
      `<w:glossaryDocument xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil"><evil:payload/></w:glossaryDocument>`,
    ],
    [
      'settings',
      'word/glossary/settings.xml',
      `<w:settings xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil"><evil:payload/></w:settings>`,
    ],
    [
      'styles',
      'word/glossary/styles.xml',
      `<w:styles xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil"><evil:payload/></w:styles>`,
    ],
    [
      'web settings',
      'word/glossary/webSettings.xml',
      `<w:webSettings xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil"><evil:payload/></w:webSettings>`,
    ],
    [
      'font table',
      'word/glossary/fontTable.xml',
      `<w:fonts xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil"><evil:payload/></w:fonts>`,
    ],
  ])('rejects a foreign-namespace descendant in %s', async (_label, partName, xml) => {
    const source = await glossaryDocx({
      ...(partName === 'word/glossary/document.xml'
        ? { glossary: xml }
        : { extraEntries: { [partName]: xml } }),
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(source)),
    ).toThrowError(/TT_AUXILIARY_ELEMENT_OR_NAMESPACE_UNSUPPORTED/);
  });

  it.each([
    [
      'glossary document',
      'word/glossary/document.xml',
      `<w:glossaryDocument xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil" evil:payload="synthetic"/>`,
    ],
    [
      'settings',
      'word/glossary/settings.xml',
      `<w:settings xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil" evil:payload="synthetic"/>`,
    ],
    [
      'styles',
      'word/glossary/styles.xml',
      `<w:styles xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil" evil:payload="synthetic"/>`,
    ],
    [
      'web settings',
      'word/glossary/webSettings.xml',
      `<w:webSettings xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil" evil:payload="synthetic"/>`,
    ],
    [
      'font table',
      'word/glossary/fontTable.xml',
      `<w:fonts xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil" evil:payload="synthetic"/>`,
    ],
  ])('rejects a foreign-namespace attribute in %s', async (_label, partName, xml) => {
    const source = await glossaryDocx({
      ...(partName === 'word/glossary/document.xml'
        ? { glossary: xml }
        : { extraEntries: { [partName]: xml } }),
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(source)),
    ).toThrowError(/TT_AUXILIARY_ATTRIBUTE_OR_NAMESPACE_UNSUPPORTED/);
  });

  it('rejects a namespace-shadowed allowed attribute and a foreign ignorable namespace', async () => {
    const shadowed = await glossaryDocx({
      extraEntries: {
        'word/glossary/settings.xml': `<w:settings xmlns:w="${W}" xmlns:evil="https://synthetic.test/evil"><w:view w:val="print" evil:val="payload"/></w:settings>`,
      },
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(shadowed)),
    ).toThrowError(/TT_AUXILIARY_ATTRIBUTE_OR_NAMESPACE_UNSUPPORTED/);

    const foreignIgnorable = await glossaryDocx({
      extraEntries: {
        'word/glossary/settings.xml': `<w:settings xmlns:w="${W}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:evil="https://synthetic.test/evil" mc:Ignorable="evil"/>`,
      },
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(foreignIgnorable)),
    ).toThrowError(/TT_AUXILIARY_IGNORABLE_NAMESPACE_UNSUPPORTED/);
  });

  it('rejects unknown Word elements and non-text-element character data', async () => {
    const unknownWordElement = await glossaryDocx({
      extraEntries: {
        'word/glossary/settings.xml': `<w:settings xmlns:w="${W}"><w:syntheticUnknown/></w:settings>`,
      },
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(unknownWordElement)),
    ).toThrowError(/TT_AUXILIARY_ELEMENT_OR_NAMESPACE_UNSUPPORTED/);

    const unexpectedText = await glossaryDocx({
      extraEntries: {
        'word/glossary/settings.xml': `<w:settings xmlns:w="${W}">synthetic hidden text</w:settings>`,
      },
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(unexpectedText)),
    ).toThrowError(/TT_AUXILIARY_TEXT_PLACEMENT_UNSUPPORTED/);
  });

  it.each([
    [
      'glossary document text outside a building-block body',
      'word/glossary/document.xml',
      `<w:glossaryDocument xmlns:w="${W}"><w:t>synthetic</w:t></w:glossaryDocument>`,
    ],
    [
      'settings rsid outside rsids',
      'word/glossary/settings.xml',
      `<w:settings xmlns:w="${W}"><w:rsid w:val="00000001"/></w:settings>`,
    ],
    [
      'styles cell margin outside table properties',
      'word/glossary/styles.xml',
      `<w:styles xmlns:w="${W}"><w:top w:type="dxa" w:w="0"/></w:styles>`,
    ],
    [
      'nested web setting',
      'word/glossary/webSettings.xml',
      `<w:webSettings xmlns:w="${W}"><w:allowPNG><w:optimizeForBrowser/></w:allowPNG></w:webSettings>`,
    ],
    [
      'font signature outside a font record',
      'word/glossary/fontTable.xml',
      `<w:fonts xmlns:w="${W}"><w:sig w:usb0="0"/></w:fonts>`,
    ],
  ])('rejects known content in an uncertified structural location: %s', async (_label, partName, xml) => {
    const source = await glossaryDocx({
      ...(partName === 'word/glossary/document.xml'
        ? { glossary: xml }
        : { extraEntries: { [partName]: xml } }),
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(source)),
    ).toThrowError(/TT_AUXILIARY_ELEMENT_PLACEMENT_UNSUPPORTED/);
  });

  it('rejects extra and namespace-shadowed relationship attributes', async () => {
    const extraAttribute = GLOSSARY_RELATIONSHIPS.replace(
      '<Relationship Id="rSettings"',
      '<Relationship TargetMode="Internal" Id="rSettings"',
    );
    const extraSource = await glossaryDocx({
      glossaryRelationships: extraAttribute,
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(extraSource)),
    ).toThrowError(/TT_AUXILIARY_ATTRIBUTE_OR_NAMESPACE_UNSUPPORTED/);

    const shadowedAttribute = GLOSSARY_RELATIONSHIPS.replace(
      '<Relationships ',
      '<Relationships xmlns:evil="https://synthetic.test/evil" ',
    ).replace(
      '<Relationship Id="rSettings"',
      '<Relationship evil:Target="settings.xml" Id="rSettings"',
    );
    const shadowedSource = await glossaryDocx({
      glossaryRelationships: shadowedAttribute,
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(
        inspectDocxPackage(shadowedSource),
      ),
    ).toThrow();
  });

  it('rejects external and malformed relationship graphs', async () => {
    const external = GLOSSARY_RELATIONSHIPS.replace(
      '</Relationships>',
      `<Relationship Id="remote" Type="${R}/hyperlink" Target="https://synthetic.test" TargetMode="External"/></Relationships>`,
    );
    const externalSource = await glossaryDocx({
      glossaryRelationships: external,
    });
    expect(() => inspectDocxPackage(externalSource)).toThrow();

    const missingStyles = GLOSSARY_RELATIONSHIPS.replace(
      /\s*<Relationship Id="rStyles"[^>]+\/>/,
      '',
    );
    const malformedSource = await glossaryDocx({
      glossaryRelationships: missingStyles,
    });
    expect(() =>
      inspectStandardWordAuxiliaryParts(inspectDocxPackage(malformedSource)),
    ).toThrow(TemplateTwinAuxiliaryPartUnsupportedError);
  });

  it('detects any post-certification mutation independently', async () => {
    const certified = inspectStandardWordAuxiliaryParts(
      inspectDocxPackage(await glossaryDocx()),
    );
    const changed = inspectDocxPackage(
      await glossaryDocx({
        extraEntries: {
          'word/glossary/styles.xml': `<w:styles xmlns:w="${W}"><w:style w:type="paragraph" w:styleId="Synthetic"/></w:styles>`,
        },
      }),
    );
    expect(() =>
      assertStandardWordAuxiliaryPartsUnchanged({ certified, completed: changed }),
    ).toThrowError(/TT_AUXILIARY_STATIC_MUTATION_DETECTED/);
  });
});
