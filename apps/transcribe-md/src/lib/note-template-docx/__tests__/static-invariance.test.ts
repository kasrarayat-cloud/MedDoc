import JSZip from 'jszip';
import { describe, expect, it } from 'vitest';

import { compileTemplateDocx } from '../compiler';
import {
  TemplateDocxRenderError,
  verifyRenderedTemplateDocx,
} from '../roundtrip-verify';
import { buildSyntheticDocx } from './synthetic-docx';

describe('Template Twin renderer static-region invariance', () => {
  it('rejects a valid DOCX whose static content changed outside the approved patch plan', async () => {
    const source = await buildSyntheticDocx();
    const ir = compileTemplateDocx(source);
    const zip = await JSZip.loadAsync(source);
    const original = await zip.file('word/document.xml')!.async('string');
    zip.file(
      'word/document.xml',
      original.replace(
        'Synthetic clinical template',
        'Unapproved synthetic static edit',
      ),
    );
    const tampered = await zip.generateAsync({
      type: 'nodebuffer',
      compression: 'DEFLATE',
    });

    expect(() =>
      verifyRenderedTemplateDocx({
        source,
        output: tampered,
        ir,
        plan: { parts: [], fields: [] },
      }),
    ).toThrowError(
      expect.objectContaining<Partial<TemplateDocxRenderError>>({
        code: 'STATIC_INVARIANCE_FAILED',
      }),
    );
  });

  it('rejects an output with a new package entry even when all original entries survive', async () => {
    const source = await buildSyntheticDocx();
    const ir = compileTemplateDocx(source);
    const zip = await JSZip.loadAsync(source);
    zip.file('word/unapproved-synthetic.xml', '<synthetic/>');
    const tampered = await zip.generateAsync({ type: 'nodebuffer' });

    expect(() =>
      verifyRenderedTemplateDocx({
        source,
        output: tampered,
        ir,
        plan: { parts: [], fields: [] },
      }),
    ).toThrowError(
      expect.objectContaining<Partial<TemplateDocxRenderError>>({
        code: 'STATIC_INVARIANCE_FAILED',
      }),
    );
  });

  it('rejects an unapproved table-grid mutation during round-trip verification', async () => {
    const source = await buildSyntheticDocx();
    const ir = compileTemplateDocx(source);
    const zip = await JSZip.loadAsync(source);
    const original = await zip.file('word/document.xml')!.async('string');
    zip.file(
      'word/document.xml',
      original.replace('<w:gridCol w:w="2800"/>', '<w:gridCol w:w="2801"/>'),
    );
    const tampered = await zip.generateAsync({ type: 'nodebuffer' });

    expect(() =>
      verifyRenderedTemplateDocx({
        source,
        output: tampered,
        ir,
        plan: { parts: [], fields: [] },
      }),
    ).toThrowError(
      expect.objectContaining<Partial<TemplateDocxRenderError>>({
        code: 'STATIC_INVARIANCE_FAILED',
      }),
    );
  });
});
