// ============================================================================
// The splice must be surgical. Every one of these is a way a doctor's note
// could be quietly rewritten by an edit they did not make.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { readNoteSection, spliceNoteSection } from '../splice-note-section';

const NOTE = [
  '## TECHNIQUE',
  'A duplex study was performed.',
  '',
  '## FINDINGS',
  'Right Leg:',
  'GSV patent.',
  '',
  '## IMPRESSION',
  'Reflux positive.',
].join('\n');

describe('spliceNoteSection', () => {
  it('replaces one body and leaves every other byte alone', () => {
    const r = spliceNoteSection(NOTE, 'FINDINGS', 'Left Leg:\nSSV patent.');
    expect(r).not.toBeNull();
    expect(r!.text).toBe(
      [
        '## TECHNIQUE',
        'A duplex study was performed.',
        '',
        '## FINDINGS',
        'Left Leg:',
        'SSV patent.',
        '',
        '## IMPRESSION',
        'Reflux positive.',
      ].join('\n'),
    );
    expect(r!.previousBody).toBe('Right Leg:\nGSV patent.');
  });

  it('keeps the blank line before the next heading (no reflow on every save)', () => {
    const r = spliceNoteSection(NOTE, 'TECHNIQUE', 'Changed.');
    expect(r!.text).toContain('Changed.\n\n## FINDINGS');
  });

  it('handles the LAST section, which has no following heading', () => {
    const r = spliceNoteSection(NOTE, 'IMPRESSION', 'No reflux.');
    expect(r!.text.endsWith('## IMPRESSION\nNo reflux.')).toBe(true);
  });

  it('matches headings loosely — case and punctuation drift', () => {
    expect(spliceNoteSection(NOTE, 'findings', 'x')).not.toBeNull();
    expect(spliceNoteSection(NOTE, 'Findings:', 'x')).not.toBeNull();
  });

  it('REFUSES an unknown heading rather than appending somewhere', () => {
    expect(spliceNoteSection(NOTE, 'ASSESSMENT', 'x')).toBeNull();
  });

  it('REFUSES a DUPLICATE heading — we cannot know which one was edited', () => {
    const dup = `${NOTE}\n\n## FINDINGS\nSecond one.`;
    expect(spliceNoteSection(dup, 'FINDINGS', 'x')).toBeNull();
  });

  it('an empty body clears the section without eating the heading', () => {
    const r = spliceNoteSection(NOTE, 'FINDINGS', '');
    expect(r!.text).toContain('## FINDINGS\n\n## IMPRESSION');
  });

  it('round-trips: writing back what was read changes nothing', () => {
    for (const label of ['TECHNIQUE', 'FINDINGS', 'IMPRESSION']) {
      const body = readNoteSection(NOTE, label);
      expect(body).not.toBeNull();
      expect(spliceNoteSection(NOTE, label, body!)!.text).toBe(NOTE);
    }
  });

  it('leaves a preamble above the first heading intact', () => {
    const withPreamble = `Patient seen today.\n\n${NOTE}`;
    const r = spliceNoteSection(withPreamble, 'TECHNIQUE', 'Changed.');
    expect(r!.text.startsWith('Patient seen today.\n\n## TECHNIQUE')).toBe(true);
  });

  it('does not treat a "#" inside body text as a heading', () => {
    const n = '## FINDINGS\nSee item #3 below.\n\n## IMPRESSION\nOK.';
    const r = spliceNoteSection(n, 'FINDINGS', 'Rewritten.');
    expect(r!.text).toBe('## FINDINGS\nRewritten.\n\n## IMPRESSION\nOK.');
  });

  it('readNoteSection returns the body verbatim, not a normalised copy', () => {
    const n = '## FINDINGS\n  indented line\ttab\n\n## X\ny';
    expect(readNoteSection(n, 'FINDINGS')).toBe('  indented line\ttab');
  });
});

describe('line endings', () => {
  const CRLF = '## FINDINGS\r\nGSV patent.\r\n\r\n## IMPRESSION\r\nReflux.';

  it('a CRLF note comes back CRLF', () => {
    const r = spliceNoteSection(CRLF, 'FINDINGS', 'Rewritten.');
    expect(r!.text).toBe('## FINDINGS\r\nRewritten.\r\n\r\n## IMPRESSION\r\nReflux.');
  });

  it('reads a CRLF body WITHOUT the carriage return', () => {
    // A textarea normalises to LF, so handing back a body with '\r' made every
    // save look like a change: a version burned, the cache dropped, and one
    // section left with different line endings from the rest of the note.
    expect(readNoteSection(CRLF, 'FINDINGS')).toBe('GSV patent.');
  });

  it('round-trips a CRLF note byte-for-byte', () => {
    const body = readNoteSection(CRLF, 'FINDINGS')!;
    expect(spliceNoteSection(CRLF, 'FINDINGS', body)!.text).toBe(CRLF);
  });
});
