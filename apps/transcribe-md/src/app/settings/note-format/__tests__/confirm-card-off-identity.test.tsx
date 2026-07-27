/** Flag OFF, the confirm card must be the card that shipped. Rendered and
 *  compared as HTML — a claim about a diff is not a diff. */
import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { ConfirmCard } from '@/app/settings/note-format/upload-flow';

const base = {
  name: 'Vein Clinic Op Note',
  sectionCount: 6,
  headerFieldCount: 3,
  nativeCandidate: true,
  busy: false,
  certError: null,
  saveError: null,
  onConfirm: () => {}, onRetryCert: () => {}, onAdvanced: () => {}, onCancel: () => {},
};

describe('confirm card, flag OFF', () => {
  it('renders the markdown sample exactly as before', () => {
    const html = renderToStaticMarkup(
      <ConfirmCard {...base} docPreview={false} sample={null}
        sampleMarkdown={'## SUBJECTIVE\nSample text.'} sampleFailed={false} />);
    expect(html).toContain('SAMPLE — SYNTHETIC PATIENT, NOT A REAL VISIT');
    expect(html).toContain('qm-ux-sample-pre');
    expect(html).toContain('qm-ux-sample"');       // the old wrapper class
    expect(html).not.toContain('qm-npv');           // no new surface
    // (the eyebrow has always read "YOUR FORMAT" — assert the LABEL only)
    expect(html).not.toContain('YOUR FORM<');
    expect(html).not.toContain('YOUR FORM —');
  });

  it('the loading and failure copy are the old copy', () => {
    const loading = renderToStaticMarkup(
      <ConfirmCard {...base} docPreview={false} sample={null}
        sampleMarkdown={null} sampleFailed={false} />);
    expect(loading).toContain('Filling in a sample…');
    expect(loading).not.toContain('Opening your form');

    const failed = renderToStaticMarkup(
      <ConfirmCard {...base} docPreview={false} sample={null}
        sampleMarkdown={''} sampleFailed={true} />);
    expect(failed).toContain('render a sample just now');
  });

  it('flag ON swaps in the document surface', () => {
    const html = renderToStaticMarkup(
      <ConfirmCard {...base} docPreview sample={{ kind: 'pdf', data: 'AAA', reason: null }}
        sampleMarkdown={null} sampleFailed={false} />);
    expect(html).toContain('YOUR FORM — SAMPLE ANSWERS, NOT A REAL VISIT');
    expect(html).not.toContain('qm-ux-sample-pre');
  });
});
