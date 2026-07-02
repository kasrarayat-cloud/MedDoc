import { describe, expect, it } from 'vitest';

import { parseNoteSections } from '@/lib/parse-note-sections';
import { parseSoapSections } from '@/lib/parse-soap-sections';

const CLASSIC = `## Subjective
Reports headache.

## Objective
BP 120/80.

## Assessment
Tension headache.

## Plan
Hydration, follow up in 2 weeks.`;

const CUSTOM = `## Reason for Visit
HTN follow-up.

## History
Home BP 150/90.

## Examination
Heart RRR.

## Impression & Plan
1. HTN — increase lisinopril.

## Follow-Up
4 weeks.`;

const IMAGING = `## Exam
Venous duplex.

## Indication
Varicose veins.

## Technique
Standing, reverse Trendelenburg.

## Comparison
No prior study is available for comparison.

## Findings
### Right
GSV 3.8 mm, no reflux.
### Left
GSV 6.1 mm, reflux 4.2 s.

## Impression
1. Left GSV incompetence.`;

describe('parseNoteSections', () => {
  it('is render-identical to parseSoapSections for classic SOAP notes', () => {
    const legacy = parseSoapSections(CLASSIC);
    const next = parseNoteSections(CLASSIC);
    expect(next).toHaveLength(4);
    next.forEach((s, i) => {
      expect(s.label).toBe(legacy[i].label);
      expect(s.body).toBe(legacy[i].body);
      expect(s.soapKey).toBe(legacy[i].key);
      expect(s.letter).toBe(legacy[i].key);
    });
  });

  it('keeps classic-SOAP semantics: missing section renders empty, preamble dropped, trailing text appended to Plan', () => {
    const partial = 'preamble line\n## Subjective\nhi\n## Plan\ndo x\ntrailing';
    const legacy = parseSoapSections(partial);
    const next = parseNoteSections(partial);
    expect(next.map((s) => s.body)).toEqual(legacy.map((s) => s.body));
    expect(next.map((s) => s.label)).toEqual(['Subjective', 'Objective', 'Assessment', 'Plan']);
  });

  it('renders every custom heading verbatim, in order, with content (finding F-1)', () => {
    const next = parseNoteSections(CUSTOM);
    expect(next.map((s) => s.label)).toEqual([
      'Reason for Visit', 'History', 'Examination', 'Impression & Plan', 'Follow-Up',
    ]);
    expect(next[0].body).toContain('HTN follow-up');
    expect(next[3].body).toContain('increase lisinopril');
    expect(next.every((s) => s.soapKey === null)).toBe(true);
    expect(next.map((s) => s.letter)).toEqual(['1', '2', '3', '4', '5']);
  });

  it('renders imaging reports (### laterality blocks stay inside Findings... they are level-3 headings, so they split)', () => {
    const next = parseNoteSections(IMAGING);
    const labels = next.map((s) => s.label);
    expect(labels[0]).toBe('Exam');
    expect(labels).toContain('Findings');
    expect(labels).toContain('Impression');
    // no content lost anywhere
    const all = next.map((s) => s.body).join('\n');
    expect(all).toContain('6.1 mm, reflux 4.2 s');
    expect(all).toContain('Left GSV incompetence');
  });

  it('mixed notes keep canonical keys on SOAP headings and null on custom ones', () => {
    const mixed = '## Reason for Visit\nx\n## Assessment\ny\n## Plan\nz';
    const next = parseNoteSections(mixed);
    expect(next.map((s) => s.soapKey)).toEqual([null, 'A', 'P']);
    expect(next.map((s) => s.letter)).toEqual(['1', 'A', 'P']);
  });

  it('duplicate headings each get their own section with distinct ids', () => {
    const dup = '## Notes\nfirst\n## Notes\nsecond';
    const next = parseNoteSections(dup);
    expect(next).toHaveLength(2);
    expect(next[0].id).not.toBe(next[1].id);
    expect(next[1].body).toBe('second');
  });

  it('heading-less notes render as a single readable Note section', () => {
    const next = parseNoteSections('just plain text\nsecond line');
    expect(next).toHaveLength(1);
    expect(next[0].label).toBe('Note');
    expect(next[0].body).toContain('second line');
  });

  it('blank input renders the four empty SOAP scaffolds (legacy behavior)', () => {
    const next = parseNoteSections('');
    expect(next.map((s) => s.label)).toEqual(['Subjective', 'Objective', 'Assessment', 'Plan']);
    expect(next.every((s) => s.body === '')).toBe(true);
  });
});
