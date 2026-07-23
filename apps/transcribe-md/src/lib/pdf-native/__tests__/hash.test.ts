import { describe, expect, it } from 'vitest';
import { canvasHash, templateStructureHash } from '../hash';

describe('canvasHash', () => {
  it('is stable + differs on any byte change', () => {
    const a = Buffer.from('%PDF-1.4 form bytes');
    expect(canvasHash(a)).toBe(canvasHash(Buffer.from('%PDF-1.4 form bytes')));
    expect(canvasHash(a)).not.toBe(canvasHash(Buffer.from('%PDF-1.4 form byteS')));
    expect(canvasHash(a)).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe('templateStructureHash', () => {
  const sections = [
    { label: 'PROCEDURE:' },
    { label: 'PREOPERATIVE DIAGNOSIS:' },
    { label: 'RECOMMENDATIONS:' },
  ];
  const header = [
    { label: 'PATIENT NAME:', order: 1 },
    { label: 'DATE OF SURGERY:', order: 2 },
  ];

  it('is identical for byte-identical forms (a re-upload carries the cert forward)', () => {
    expect(templateStructureHash(sections, header)).toBe(templateStructureHash(sections, header));
  });

  it('ignores label casing/whitespace/trailing colon (same parsed form)', () => {
    const variant = [{ label: 'procedure' }, { label: 'Preoperative Diagnosis' }, { label: '  RECOMMENDATIONS ' }];
    expect(templateStructureHash(variant, header)).toBe(templateStructureHash(sections, header));
  });

  it('changes when a labeled field is added / removed / renamed (material change → re-cert)', () => {
    const base = templateStructureHash(sections, header);
    expect(templateStructureHash([...sections, { label: 'FINDINGS:' }], header)).not.toBe(base);
    expect(templateStructureHash(sections.slice(0, 2), header)).not.toBe(base);
    expect(templateStructureHash([{ label: 'OPERATION:' }, ...sections.slice(1)], header)).not.toBe(base);
    expect(templateStructureHash(sections, [{ label: 'MRN:', order: 1 }, header[1]])).not.toBe(base);
  });
});
