import JSZip from 'jszip';
import { describe, expect, it } from 'vitest';

import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../../template-twin/ir';
import {
  ORDINARY_PLACEHOLDER_TOKEN_PROFILE,
  compileTemplateDocx,
} from '../compiler';
import { inspectDocxPackage } from '../package-security';
import { readbackTemplateDocxOutput } from '../output-readback';
import { renderTemplateDocx } from '../renderer';
import {
  buildOfficeExpectedValueManifest,
  buildOfficeVisibleStaticManifestFromDocxBytes,
  compareOfficeVisibleStaticManifests,
  readOfficeSavedDocxFieldsQa,
} from '../office-roundtrip-qa';
import {
  validActualManifest,
  validExpectedManifest,
} from '../office-docx-byte-readback';
import { buildSyntheticDocx } from './synthetic-docx';

const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const FACT_ID = `ttfact_${'a'.repeat(24)}`;
const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-07-16T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};
const STATIC_HEADER = `<w:hdr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic header</w:t></w:r></w:p></w:hdr>`;
const STATIC_FOOTER = `<w:ftr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic footer</w:t></w:r></w:p></w:ftr>`;

function documentXml(body: string): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="${W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>${body}<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr></w:body></w:document>`;
}

async function sourceDocx(
  body: string,
  extraEntries: Record<string, string> = {},
): Promise<Buffer> {
  return buildSyntheticDocx({
    documentXml: documentXml(body),
    extraEntries: {
      'word/header1.xml': STATIC_HEADER,
      'word/footer1.xml': STATIC_FOOTER,
      ...extraEntries,
    },
  });
}

function placeholderFields(ir: TemplateDocIR): TemplateField[] {
  return ir.fields.filter(
    (field) => field.rendererBinding.bindingType === 'ordinary_placeholder',
  );
}

function resolution(
  field: TemplateField,
  value: string | null,
): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: value === null ? 'not_mentioned' : 'supported',
    value,
    sourceFactIds: value === null ? [] : [FACT_ID],
    evidenceAnchorIds: value === null ? [] : ['synthetic-placeholder-anchor'],
    selectedOptionOrdinal: null,
    reasonCode: value === null ? 'synthetic_unresolved' : 'synthetic_supported',
    clinicianReviewed: false,
  });
}

async function renderValues(
  source: Buffer,
  values: readonly (string | null)[],
) {
  const ir = compileTemplateDocx(source);
  const fields = placeholderFields(ir);
  expect(fields).toHaveLength(values.length);
  const resolutions = fields.map((field, index) =>
    resolution(field, values[index] ?? null),
  );
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions,
    validation: VALIDATION,
  });
  return { source, ir, fields, resolutions, rendered };
}

async function mutateDocument(
  bytes: Uint8Array,
  mutate: (xml: string) => string,
): Promise<Buffer> {
  const zip = await JSZip.loadAsync(bytes);
  const entry = zip.file('word/document.xml');
  if (!entry) throw new Error('Missing synthetic document part.');
  const before = await entry.async('string');
  const after = mutate(before);
  if (after === before) throw new Error('Synthetic mutation was a no-op.');
  zip.file('word/document.xml', after);
  return zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
}

function expectStrictMismatch(
  fixture: Awaited<ReturnType<typeof renderValues>>,
  output: Uint8Array,
): void {
  expect(() =>
    readbackTemplateDocxOutput({
      source: fixture.source,
      output,
      ir: fixture.ir,
      resolutions: fixture.resolutions,
    }),
  ).toThrowError(expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }));
}

function deterministicText(length: number): string {
  const alphabet =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let state = 0x5a17c9e3;
  let output = '';
  for (let index = 0; index < length; index += 1) {
    state = (Math.imul(state, 1_664_525) + 1_013_904_223) >>> 0;
    output += alphabet[state % alphabet.length];
  }
  return output;
}

describe(ORDINARY_PLACEHOLDER_TOKEN_PROFILE, () => {
  it.each([
    ['angle', '<<insert clinical detail>>'],
    ['square', '[[clinical detail]]'],
    ['curly', '{{clinical detail}}'],
    ['underscore', '________'],
  ] as const)(
    'compiles a bounded %s token as physician-confirmation required',
    async (syntax, token) => {
      const ir = compileTemplateDocx(
        await sourceDocx(
          `<w:p><w:r><w:t>Finding: ${token.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')}</w:t></w:r></w:p>`,
        ),
      );
      const fields = placeholderFields(ir);

      expect(ir.unsupported).toEqual([]);
      expect(fields).toHaveLength(1);
      expect(fields[0]).toMatchObject({
        detectionStatus: 'needs_confirmation',
        clinicallyMaterial: true,
        rendererBinding: {
          bindingType: 'ordinary_placeholder',
          bindingProfile: ORDINARY_PLACEHOLDER_TOKEN_PROFILE,
          ordinaryPlaceholder: {
            contractVersion: 'ordinary-placeholder-token-binding/1.0.0',
            tokenSyntax: syntax,
            clinicalMappingStatus: 'needs_confirmation',
            staticPrefixLength: 9,
            staticSuffixLength: 0,
          },
        },
      });
    },
  );

  it('reconstructs one exact token split across adjacent Word runs and text nodes', async () => {
    const source = await sourceDocx(
      '<w:p><w:r><w:t>Before &lt;&lt;insert </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>clinical</w:t><w:t> detail&gt;&gt; after</w:t></w:r></w:p>',
    );
    const ir = compileTemplateDocx(source);
    const field = placeholderFields(ir)[0]!;

    expect(ir.unsupported).toEqual([]);
    expect(field.rendererBinding.ordinaryPlaceholder).toMatchObject({
      span: {
        startTextNodeIndex: 0,
        endTextNodeIndex: 2,
        paragraphTextNodeCount: 3,
      },
      staticPrefixLength: 7,
      staticSuffixLength: 6,
    });
    const fixture = await renderValues(source, ['Unicode 左 & <safe>']);
    const xml = inspectDocxPackage(fixture.rendered.document)
      .zip.entries.get('word/document.xml')!
      .bytes.toString('utf8');
    expect(xml).toContain(
      '<w:t>Before Unicode 左 &amp; &lt;safe&gt;</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t></w:t><w:t xml:space="preserve"> after</w:t>',
    );
    expect(fixture.rendered.verification.fields[0]).toMatchObject({
      disposition: 'rendered',
      occurrences: 1,
      bindingEvidence: {
        status: 'verified',
        outputBindingProfile: ORDINARY_PLACEHOLDER_TOKEN_PROFILE,
      },
    });
  });

  it('preserves static boundary whitespace exposed by split-run replacement', async () => {
    const fixture = await renderValues(
      await sourceDocx(
        '<w:p><w:r><w:t>Finding: [[split</w:t></w:r><w:r><w:t> token]] (reviewed).</w:t></w:r></w:p>',
      ),
      ['synthetic value'],
    );
    const xml = inspectDocxPackage(fixture.rendered.document)
      .zip.entries.get('word/document.xml')!
      .bytes.toString('utf8');

    expect(xml).toContain(
      '<w:t>Finding: synthetic value</w:t></w:r><w:r><w:t xml:space="preserve"> (reviewed).</w:t>',
    );
    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: fixture.rendered.document,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).not.toThrow();
  });

  it('keeps repeated visible tokens distinct by certified part and path', async () => {
    const fixture = await renderValues(
      await sourceDocx(
        '<w:p><w:r><w:t>First: [[same label]]</w:t></w:r></w:p><w:p><w:r><w:t>Second: [[same label]]</w:t></w:r></w:p>',
      ),
      ['first evidence', 'second evidence'],
    );
    expect(fixture.fields[0]!.rendererBinding.canonicalPath).not.toBe(
      fixture.fields[1]!.rendererBinding.canonicalPath,
    );
    expect(fixture.rendered.verification.fields).toHaveLength(2);
  });

  it('accepts distinct standalone tokens that legitimately render the same value', async () => {
    const fixture = await renderValues(
      await sourceDocx(
        '<w:p><w:r><w:t>[[first]]</w:t></w:r></w:p><w:p><w:r><w:t>[[second]]</w:t></w:r></w:p>',
      ),
      ['same value', 'same value'],
    );
    expect(fixture.fields).toHaveLength(2);
    expect(fixture.fields[0]!.rendererBinding.canonicalPath).not.toBe(
      fixture.fields[1]!.rendererBinding.canonicalPath,
    );
    expect(fixture.rendered.verification.fields).toHaveLength(2);
    expect(
      fixture.rendered.verification.fields.every(
        (field) => field.bindingEvidence?.status === 'verified',
      ),
    ).toBe(true);
  });

  it('supports exact tokens in tables, headers, and footers without crossing story boundaries', async () => {
    const source = await sourceDocx(
      '<w:tbl><w:tblGrid><w:gridCol w:w="3000"/></w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Cell: {{table value}}</w:t></w:r></w:p></w:tc></w:tr></w:tbl>',
      {
        'word/header1.xml': `<w:hdr xmlns:w="${W}"><w:p><w:r><w:t>Header: [[header value]]</w:t></w:r></w:p></w:hdr>`,
        'word/footer1.xml': `<w:ftr xmlns:w="${W}"><w:p><w:r><w:t>Footer: &lt;&lt;footer value&gt;&gt;</w:t></w:r></w:p></w:ftr>`,
      },
    );
    const ir = compileTemplateDocx(source);
    expect(
      placeholderFields(ir)
        .map((field) => field.rendererBinding.partName)
        .sort(),
    ).toEqual(['word/document.xml', 'word/footer1.xml', 'word/header1.xml']);
    expect(ir.unsupported).toEqual([]);
    const rendered = await renderValues(source, [
      'table evidence',
      'header evidence',
      'footer evidence',
    ]);
    expect(rendered.rendered.verification.fields).toHaveLength(3);
  });

  it.each([
    [
      'partial token',
      '<w:p><w:r><w:t>Finding: &lt;&lt;insert detail</w:t></w:r></w:p>',
    ],
    [
      'two fill regions',
      '<w:p><w:r><w:t>[[first]] and [[second]]</w:t></w:r></w:p>',
    ],
    [
      'bookmark crossing',
      '<w:p><w:bookmarkStart w:id="1" w:name="Synthetic"/><w:r><w:t>[[detail]]</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>',
    ],
    [
      'field crossing',
      '<w:p><w:r><w:fldChar w:fldCharType="begin"/><w:t>[[detail]]</w:t><w:fldChar w:fldCharType="end"/></w:r></w:p>',
    ],
    [
      'drawing adjacency',
      '<w:p><w:r><w:drawing/><w:t>[[detail]]</w:t></w:r></w:p>',
    ],
    [
      'raw character data outside Word text',
      '<w:p>unexpected<w:r><w:t>[[detail]]</w:t></w:r></w:p>',
    ],
    [
      'embedded underscore sequence',
      '<w:p><w:r><w:t>code___name</w:t></w:r></w:p>',
    ],
  ])('keeps %s certification-blocked', async (_name, paragraph) => {
    const ir = compileTemplateDocx(await sourceDocx(paragraph));
    expect(placeholderFields(ir)).toEqual([]);
    expect(ir.unsupported).toContainEqual(
      expect.objectContaining({
        code: 'UNBOUND_ORDINARY_PLACEHOLDER',
        blocksCertification: true,
      }),
    );
  });

  it('rejects unresolved tracked revisions at package admission', async () => {
    const source = await sourceDocx(
      '<w:p><w:ins w:id="1" w:author="Synthetic"><w:r><w:t>[[detail]]</w:t></w:r></w:ins></w:p>',
    );

    expect(() => compileTemplateDocx(source)).toThrowError(
      expect.objectContaining({ code: 'XML_HIDDEN_CONTENT_UNSUPPORTED' }),
    );
  });

  it('preserves an unresolved token byte-for-byte and proves the disposition', async () => {
    const fixture = await renderValues(
      await sourceDocx('<w:p><w:r><w:t>Finding: [[detail]]</w:t></w:r></w:p>'),
      [null],
    );
    expect(fixture.rendered.document.equals(fixture.source)).toBe(true);
    expect(fixture.rendered.verification.fields[0]).toMatchObject({
      disposition: 'preserved_unresolved',
      occurrences: 1,
    });
  });

  it('renders the maximum approved length and rejects overflow or boundary whitespace', async () => {
    await expect(
      renderValues(
        await sourceDocx('<w:p><w:r><w:t>[[detail]]</w:t></w:r></w:p>'),
        [deterministicText(32_767)],
      ),
    ).resolves.toBeDefined();
    await expect(
      renderValues(
        await sourceDocx('<w:p><w:r><w:t>[[detail]]</w:t></w:r></w:p>'),
        [deterministicText(32_768)],
      ),
    ).rejects.toMatchObject({ code: 'FIELD_VALUE_TOO_LARGE' });
    await expect(
      renderValues(
        await sourceDocx('<w:p><w:r><w:t>[[detail]]</w:t></w:r></w:p>'),
        [' unsafe boundary '],
      ),
    ).rejects.toMatchObject({ code: 'FIELD_VALUE_INVALID' });
  });

  it('rejects moved, duplicated, changed-context, partial, and outside-slot output tampering', async () => {
    const fixture = await renderValues(
      await sourceDocx(
        '<w:p><w:r><w:t>Static lead</w:t></w:r></w:p><w:p><w:r><w:t>Before [[detail]] after</w:t></w:r></w:p>',
      ),
      ['verified value'],
    );
    const renderedParagraph =
      '<w:p><w:r><w:t>Before verified value after</w:t></w:r></w:p>';
    const mutations = [
      (xml: string) =>
        xml.replace(
          '<w:p><w:r><w:t>Static lead</w:t></w:r></w:p>',
          `<w:p><w:r><w:t>Inserted</w:t></w:r></w:p><w:p><w:r><w:t>Static lead</w:t></w:r></w:p>`,
        ),
      (xml: string) =>
        xml.replace(
          renderedParagraph,
          `${renderedParagraph}${renderedParagraph}`,
        ),
      (xml: string) =>
        xml.replace(
          'Before verified value after',
          'Changed verified value after',
        ),
      (xml: string) => xml.replace('verified value', 'verified'),
      (xml: string) =>
        xml.replace(
          'verified value after',
          'verified value after verified value',
        ),
    ];
    for (const mutation of mutations) {
      expectStrictMismatch(
        fixture,
        await mutateDocument(fixture.rendered.document, mutation),
      );
    }
  });

  it('rejects swapped values and stale source-token certification', async () => {
    const fixture = await renderValues(
      await sourceDocx(
        '<w:p><w:r><w:t>First: [[alpha]]</w:t></w:r></w:p><w:p><w:r><w:t>Second: [[beta]]</w:t></w:r></w:p>',
      ),
      ['value one', 'value two'],
    );
    const swapped = await mutateDocument(fixture.rendered.document, (xml) =>
      xml
        .replace('value one', '__SWAP__')
        .replace('value two', 'value one')
        .replace('__SWAP__', 'value two'),
    );
    expectStrictMismatch(fixture, swapped);

    const staleSource = await mutateDocument(fixture.source, (xml) =>
      xml.replace('[[alpha]]', '[[changed]]'),
    );
    await expect(
      renderTemplateDocx({
        source: staleSource,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
        validation: VALIDATION,
      }),
    ).rejects.toMatchObject({ code: 'SOURCE_IR_MISMATCH' });
  });

  it('rejects a changed certified binding ordinal before rendering', async () => {
    const source = await sourceDocx(
      '<w:p><w:r><w:t>First: [[alpha]]</w:t></w:r></w:p><w:p><w:r><w:t>Second: [[beta]]</w:t></w:r></w:p>',
    );
    const ir = compileTemplateDocx(source);
    const fields = placeholderFields(ir);
    const tampered = structuredClone(ir);
    tampered.fields[0]!.rendererBinding.ordinal =
      tampered.fields[1]!.rendererBinding.ordinal;

    await expect(
      renderTemplateDocx({
        source,
        ir: tampered,
        resolutions: fields.map((field) =>
          resolution(field, 'synthetic value'),
        ),
        validation: VALIDATION,
      }),
    ).rejects.toMatchObject({ code: 'SOURCE_IR_MISMATCH' });
  });

  it('proves semantic survival after an Office-style run normalization without weakening strict v2', async () => {
    const fixture = await renderValues(
      await sourceDocx(
        '<w:p><w:r><w:t>Before [[de</w:t></w:r><w:r><w:t>tail]] after</w:t></w:r></w:p>',
      ),
      ['synthetic normal'],
    );
    const expected = buildOfficeExpectedValueManifest({
      syntheticOnly: true,
      sourceDocxBytes: fixture.source,
      rendererOutputDocxBytes: fixture.rendered.document,
      ir: fixture.ir,
      resolutions: fixture.resolutions,
    });
    expect(validExpectedManifest(expected)).toBe(true);

    const officeNormalized = await mutateDocument(
      fixture.rendered.document,
      (xml) =>
        xml.replace(
          '<w:p><w:r><w:t>Before synthetic normal</w:t></w:r><w:r><w:t xml:space="preserve"> after</w:t></w:r></w:p>',
          '<w:p><w:r><w:t>Before synthetic normal after</w:t></w:r></w:p>',
        ),
    );
    expectStrictMismatch(fixture, officeNormalized);

    const actual = readOfficeSavedDocxFieldsQa({
      syntheticOnly: true,
      officeSavedDocxBytes: officeNormalized,
      expected,
    });
    expect(validActualManifest(actual, expected)).toBe(true);
    expect(actual).toMatchObject({
      ambiguousBindingCount: 0,
      unexpectedBindingCount: 0,
      fields: [
        {
          controlKind: 'ordinary_placeholder_text',
          actualOccurrences: 1,
          actualValueSha256: expected.fields[0]!.expectedValueSha256,
          actualControlStateSha256:
            expected.fields[0]!.expectedControlStateSha256,
        },
      ],
    });

    const beforeStatic = buildOfficeVisibleStaticManifestFromDocxBytes({
      syntheticOnly: true,
      docxBytes: fixture.rendered.document,
      expected,
    });
    const afterStatic = buildOfficeVisibleStaticManifestFromDocxBytes({
      syntheticOnly: true,
      docxBytes: officeNormalized,
      expected,
    });
    expect(
      compareOfficeVisibleStaticManifests(
        beforeStatic.manifest,
        afterStatic.manifest,
      ),
    ).toMatchObject({
      aggregateVisibleContentMatches: true,
      aggregateStructureMatches: true,
    });
  });

  it('fails QA-only readback when Office output duplicates or changes a placeholder region', async () => {
    const fixture = await renderValues(
      await sourceDocx('<w:p><w:r><w:t>Finding: [[detail]]</w:t></w:r></w:p>'),
      ['synthetic finding'],
    );
    const expected = buildOfficeExpectedValueManifest({
      syntheticOnly: true,
      sourceDocxBytes: fixture.source,
      rendererOutputDocxBytes: fixture.rendered.document,
      ir: fixture.ir,
      resolutions: fixture.resolutions,
    });
    const renderedParagraph =
      '<w:p><w:r><w:t>Finding: synthetic finding</w:t></w:r></w:p>';
    const duplicated = await mutateDocument(fixture.rendered.document, (xml) =>
      xml.replace(
        renderedParagraph,
        `${renderedParagraph}${renderedParagraph}`,
      ),
    );
    const duplicateReadback = readOfficeSavedDocxFieldsQa({
      syntheticOnly: true,
      officeSavedDocxBytes: duplicated,
      expected,
    });
    expect(duplicateReadback).toMatchObject({
      fields: [],
      ambiguousBindingCount: 1,
    });
    expect(validActualManifest(duplicateReadback, expected)).toBe(false);

    const changedContext = await mutateDocument(
      fixture.rendered.document,
      (xml) =>
        xml.replace('Finding: synthetic finding', 'Changed: synthetic finding'),
    );
    const changedReadback = readOfficeSavedDocxFieldsQa({
      syntheticOnly: true,
      officeSavedDocxBytes: changedContext,
      expected,
    });
    expect(changedReadback).toMatchObject({
      fields: [],
      ambiguousBindingCount: 1,
    });
    expect(validActualManifest(changedReadback, expected)).toBe(false);
  });
});
