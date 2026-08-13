// ============================================================================
// GATE — the slot-values wire format, and the two copies of its sentinel
// (ruling #106(a), SPEC §4.3a).
// ----------------------------------------------------------------------------
// ⚠️ THE SENTINEL EXISTS TWICE AND THIS FILE IS WHY THAT IS SAFE. `packages/ai`
// cannot import from `apps/transcribe-md`, so the mocked `tm_soap_draft` carries
// its own copy of the token. If the two ever drift, the mock stops recognising
// the prompt, returns no fills, and every slot renders empty — which is
// INDISTINGUISHABLE from a transcript that supported nothing. That failure has
// no symptom, so it is pinned here instead.
// ============================================================================
import { describe, expect, it } from 'vitest';
import {
  MOCK_SLOT_VALUES_CLOSE,
  MOCK_SLOT_VALUES_OPEN,
  MOCK_SYSTEM_COMPOSED_MARKER,
} from '@meddoc/ai';

import { segmentSection } from '../section-assembly';
import {
  extractSlotFills,
  renderStaticSectionRequest,
  SLOT_VALUES_CLOSE,
  SLOT_VALUES_DIRECTIVE,
  SLOT_VALUES_OPEN,
} from '../slot-fill-protocol';
import type { NoteTemplateSection } from '../system-default-template';

const SECTION = {
  key: 'technique',
  label: 'TECHNIQUE',
  order: 1,
  formatHint: 'prose',
  styleInstructions: null,
  defaultText:
    'Study of the {{one of: deep and superficial | superficial}} venous ' +
    'systems, documenting reflux over 500 milliseconds.',
  defaultTextMode: 'always_include',
} as NoteTemplateSection;

const block = (json: string) => `${SLOT_VALUES_OPEN}\n${json}\n${SLOT_VALUES_CLOSE}`;

describe('⚠️ THE TWO COPIES OF THE SENTINEL AGREE', () => {
  it('open token', () => expect(MOCK_SLOT_VALUES_OPEN).toBe(SLOT_VALUES_OPEN));
  it('close token', () => expect(MOCK_SLOT_VALUES_CLOSE).toBe(SLOT_VALUES_CLOSE));
  it('the system-composed marker the mock looks for is the one the prompt writes', () => {
    expect(renderStaticSectionRequest(SECTION, segmentSection(SECTION.defaultText ?? '')).join('\n'))
      .toContain(MOCK_SYSTEM_COMPOSED_MARKER);
  });
  it('the directive names the sentinels it asks for', () => {
    expect(SLOT_VALUES_DIRECTIVE).toContain(SLOT_VALUES_OPEN);
    expect(SLOT_VALUES_DIRECTIVE).toContain(SLOT_VALUES_CLOSE);
  });
});

describe('renderStaticSectionRequest — the model is told the shape, never the bytes', () => {
  const lines = segmentSection(SECTION.defaultText ?? '');
  const rendered = renderStaticSectionRequest(SECTION, lines).join('\n');

  it('⚠️ DOES NOT CARRY THE DOCTOR\'S PROSE — the whole point of #106(a)', () => {
    expect(rendered).not.toContain('500 milliseconds');
    expect(rendered).not.toContain('venous');
  });

  it('names the section key and every slot with its own menu', () => {
    expect(rendered).toContain('under the key "technique"');
    expect(rendered).toContain('s0 — one of: deep and superficial | superficial');
  });

  it('says the section has no slots when it has none', () => {
    const fixed = { ...SECTION, defaultText: 'Clinical correlation is required.' } as NoteTemplateSection;
    const out = renderStaticSectionRequest(fixed, segmentSection(fixed.defaultText ?? '')).join('\n');
    expect(out).toContain('no fillable slots');
    expect(out).not.toContain('Clinical correlation');
  });
});

describe('extractSlotFills — reading the answer, fail-closed at every turn', () => {
  it('parses a well-formed block and strips it from the note', () => {
    const raw = `## A\nbody\n\n${block('{"technique":{"s0":"superficial"}}')}`;
    const out = extractSlotFills(raw);
    expect(out.error).toBeNull();
    expect(out.fills).toEqual({ technique: { s0: 'superficial' } });
    expect(out.text).toBe('## A\nbody');
    expect(out.text).not.toContain(SLOT_VALUES_OPEN);
  });

  it('⚠️ THE LAST BLOCK WINS — a model that shows the format first is read by its answer', () => {
    const raw = [
      '## A',
      'here is the shape you asked for:',
      block('{"technique":{"s0":"deep and superficial"}}'),
      'and here is my real answer:',
      block('{"technique":{"s0":"superficial"}}'),
    ].join('\n');
    expect(extractSlotFills(raw).fills).toEqual({ technique: { s0: 'superficial' } });
  });

  it('no block at all → no fills, note untouched, named reason', () => {
    const out = extractSlotFills('## A\nbody');
    expect(out.fills).toEqual({});
    expect(out.text).toBe('## A\nbody');
    expect(out.error).toBe('slot_block_absent');
  });

  it('unterminated block → no fills, and the protocol text is STILL removed', () => {
    const out = extractSlotFills(`## A\nbody\n${SLOT_VALUES_OPEN}\n{"a":`);
    expect(out.fills).toEqual({});
    expect(out.error).toBe('slot_block_unterminated');
    expect(out.text).not.toContain(SLOT_VALUES_OPEN);
    expect(out.text).not.toContain('{"a":');
  });

  it('not JSON → no fills, named reason, block removed', () => {
    const out = extractSlotFills(`## A\nbody\n${block('sorry, I could not answer')}`);
    expect(out.fills).toEqual({});
    expect(out.error).toBe('slot_block_not_json');
    expect(out.text).toBe('## A\nbody');
  });

  it('a JSON ARRAY is not an answer', () => {
    const out = extractSlotFills(block('["superficial"]'));
    expect(out.error).toBe('slot_block_not_an_object');
    expect(out.fills).toEqual({});
  });

  it('drops non-string and empty values — an unfilled slot is the safe reading', () => {
    const out = extractSlotFills(
      block('{"t":{"a":"ok","b":null,"c":3,"d":{"nested":"x"},"e":"","f":["y"]}}')
    );
    expect(out.fills).toEqual({ t: { a: 'ok' } });
  });

  it('a non-object section value yields an empty section rather than throwing', () => {
    expect(extractSlotFills(block('{"t":"just a string"}')).fills).toEqual({ t: {} });
  });

  it('an empty answer is a valid answer', () => {
    const out = extractSlotFills(block('{}'));
    expect(out.error).toBeNull();
    expect(out.fills).toEqual({});
  });
});
