// ============================================================================
// sourceType must survive write -> read. THE TEST THAT WOULD HAVE CAUGHT IT.
// ----------------------------------------------------------------------------
// sourceType was added to the Zod schema and the proposer, but there was no
// COLUMN. Every mapping round-tripped through the database and came back as
// 'extraction', so the manual carve-outs in the certification gate were inert
// code — and two ten-minute certification runs were burned before anyone
// checked the persistence path.
//
// These assertions trace the field end-to-end statically: schema -> persisted
// column -> update payload -> read projection. A break anywhere in that chain
// makes the carve-outs silently dead again, which looks exactly like a
// certification bug and is not one.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { SemanticMappingSchema } from '../ir';
import { classifyFieldSource } from '../concept-registry';

const read = (rel: string) => {
  const { readFileSync } = require('node:fs') as typeof import('node:fs');
  const { join } = require('node:path') as typeof import('node:path');
  return readFileSync(join(__dirname, '..', rel), 'utf-8');
};
const readRepo = (rel: string) => {
  const { readFileSync } = require('node:fs') as typeof import('node:fs');
  const { join } = require('node:path') as typeof import('node:path');
  return readFileSync(join(__dirname, '..', '..', '..', '..', '..', '..', rel), 'utf-8');
};

const BASE = {
  fieldId: `ttf_${'a'.repeat(24)}`,
  clinicalConcept: null,
  expectedDataType: 'single_select' as const,
  polarityBehavior: 'value_only' as const,
  temporality: 'current' as const,
  laterality: 'optional' as const,
  unitPolicy: 'not_applicable' as const,
  approvedSynonyms: [],
  required: false,
  blankPolicy: 'blank' as const,
  unknownPolicy: 'blank' as const,
  practiceDefault: null,
  status: 'certified' as const,
};

describe('schema', () => {
  it('accepts and preserves a manual classification', () => {
    const parsed = SemanticMappingSchema.parse({ ...BASE, sourceType: 'manual' });
    expect(parsed.sourceType).toBe('manual');
  });

  it('defaults to extraction when absent', () => {
    const parsed = SemanticMappingSchema.parse({ ...BASE });
    expect(parsed.sourceType).toBe('extraction');
  });

  it('a manual mapping is valid with a NULL concept', () => {
    // The whole point: nothing can know the technologist on shift, so there is
    // no evidence to cite and no concept to carry.
    const parsed = SemanticMappingSchema.parse({
      ...BASE,
      sourceType: 'manual',
      clinicalConcept: null,
    });
    expect(parsed.clinicalConcept).toBeNull();
  });
});

describe('classification', () => {
  it.each([
    ['ULTRASOUND TECHNOLOGIST: Choose an item.', 'manual'],
    ['REFERRING PHYSICIAN: Choose an item.', 'manual'],
    ['MACHINE: Choose an item.', 'manual'],
    ['LOCATION: Choose an item.', 'manual'],
    ['Address', 'manual'],
    ['GSV at the SFJ', 'extraction'],
    ['SIDE OF EXAM: Choose an item.', 'extraction'],
    ['CLINICAL INDICATIONS: Choose an item.', 'extraction'],
  ])('%s -> %s', (label, want) => {
    expect(classifyFieldSource(label)).toBe(want);
  });
});

describe('the persistence chain — every link', () => {
  it('1. the COLUMN exists in the prisma model', () => {
    const schema = readRepo('packages/db/prisma/schema.prisma');
    const model = /model TemplateTwinSemanticMapping \{[\s\S]*?\n\}/.exec(schema)?.[0] ?? '';
    expect(model, 'no sourceType column — classification is lost on write').toMatch(
      /sourceType\s+String\s+@default\("extraction"\)/,
    );
  });

  it('2. the UPDATE payload writes it', () => {
    const src = read('certification-lifecycle.ts');
    expect(src, 'updateTemplateTwinMappings does not persist sourceType').toContain(
      'sourceType: mapping.sourceType,',
    );
  });

  it('3. the READ projection selects and parses it', () => {
    const src = read('certification-lifecycle.ts');
    expect(src).toContain('sourceType: true,');
    expect(src, 'fromPersistedMapping drops sourceType — it reads back as extraction').toContain(
      'sourceType: row.sourceType,',
    );
  });

  it('4. the WORKSPACE projection carries it to the review surface', () => {
    const src = read('workspace-read.ts');
    expect(src).toContain('sourceType: true,');
    expect(src).toContain('sourceType: row.sourceType,');
  });

  it('5. both gate checks honour the manual carve-out', () => {
    const src = read('certification-lifecycle.ts');
    // fieldsReady, and the mapping-update validation.
    expect(src).toContain("mapping.sourceType === 'manual'");
    expect(src).toContain("mapping.sourceType !== 'manual'");
  });
});
