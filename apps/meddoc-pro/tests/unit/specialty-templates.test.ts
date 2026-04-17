// ============================================================================
// Specialty templates — YAML shape + required fields
// ----------------------------------------------------------------------------
// M5 adds 7 new specialties alongside primary-care. These tests are a
// cheap guardrail so clinical advisors can PR a YAML without accidentally
// landing a malformed template:
//
//   1. Every *.yaml in apps/scribe/specialties/ parses as YAML
//   2. Each has all required keys the seed script expects
//   3. slug / version / clinicalReviewStatus values are in-spec
//   4. Psychiatry's system prompt still contains the SAFETY CLAUSE
//      (locked in so nobody deletes it during a later edit)
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';
import { describe, it, expect } from 'vitest';

const SPECIALTIES_DIR = path.resolve(
  __dirname,
  '..',
  '..',
  '..',
  'scribe',
  'specialties'
);

interface ParsedTemplate {
  file: string;
  data: Record<string, unknown>;
}

function loadAll(): ParsedTemplate[] {
  const files = fs.readdirSync(SPECIALTIES_DIR).filter((f) => f.endsWith('.yaml'));
  return files.map((file) => {
    const raw = fs.readFileSync(path.join(SPECIALTIES_DIR, file), 'utf8');
    return { file, data: yaml.load(raw) as Record<string, unknown> };
  });
}

const EXPECTED_SLUGS = [
  'primary-care',
  'internal-medicine',
  'cardiology',
  'dermatology',
  'psychiatry',
  'pediatrics',
  'orthopedics',
  'ob-gyn',
];

describe('specialty templates', () => {
  const all = loadAll();

  it('ships 8 templates (primary-care + the 7 M5 specialties)', () => {
    expect(all).toHaveLength(8);
    const slugs = all.map((t) => t.data.slug as string).sort();
    expect(slugs).toEqual([...EXPECTED_SLUGS].sort());
  });

  it.each(EXPECTED_SLUGS)('%s has every required field the seeder expects', (slug) => {
    const tmpl = all.find((t) => t.data.slug === slug);
    expect(tmpl, `slug=${slug} must exist`).toBeDefined();
    const d = tmpl!.data;
    // Fields the seeder will blow up on if missing.
    expect(typeof d.slug).toBe('string');
    expect(typeof d.displayName).toBe('string');
    expect(typeof d.version).toBe('string');
    expect(d.requiredExamElements).toBeTruthy();
    expect(d.soapSchema).toBeTruthy();
    expect(typeof d.systemPrompt).toBe('string');
    // M5 — optional on the seeder side but every template in this repo
    // should carry a (possibly empty) CPT hints list for consistency.
    expect(Array.isArray(d.defaultIcd10Hints)).toBe(true);
    expect(Array.isArray(d.defaultCptHints)).toBe(true);
    expect(Array.isArray(d.defaultFormularyHints)).toBe(true);
  });

  it.each(EXPECTED_SLUGS)('%s uses a valid clinicalReviewStatus', (slug) => {
    const tmpl = all.find((t) => t.data.slug === slug)!;
    const s = tmpl.data.clinicalReviewStatus as string | undefined;
    // If the field is present, it must be one of the three enum values.
    // All M5 templates ship as draft — a specialist review flips this.
    if (s !== undefined) {
      expect(['draft', 'specialist_reviewed', 'production']).toContain(s);
    }
  });

  it('required_exam_elements sits at 4-6 items per D7 (informational, not flag-spam)', () => {
    for (const { file, data } of all) {
      const list = data.requiredExamElements as unknown[];
      expect(Array.isArray(list), `${file} requiredExamElements must be array`).toBe(
        true
      );
      expect(list.length, `${file} has ${list.length} required exam elements`)
        .toBeGreaterThanOrEqual(4);
      expect(list.length).toBeLessThanOrEqual(6);
    }
  });

  it('soap_schema has the four top-level sections on every template', () => {
    for (const { file, data } of all) {
      const schema = data.soapSchema as Record<string, unknown>;
      expect(schema, `${file} soapSchema must be object`).toBeDefined();
      for (const section of ['subjective', 'objective', 'assessment', 'plan']) {
        expect(
          schema[section],
          `${file} soapSchema.${section} must be defined`
        ).toBeDefined();
      }
    }
  });

  it('psychiatry SAFETY CLAUSE is present and intact', () => {
    const psych = all.find((t) => t.data.slug === 'psychiatry')!;
    const prompt = psych.data.systemPrompt as string;
    // If someone deletes or softens this, CI should catch it. These
    // phrases are the teeth of the clause.
    expect(prompt).toContain('SAFETY CLAUSE');
    expect(prompt).toContain('NON-NEGOTIABLE');
    expect(prompt).toContain('requires_immediate_follow_up: true');
    expect(prompt).toContain('988');
    // The prompt must explicitly instruct "never minimise" in some form —
    // phrasing was "NEVER minimise, soften, or omit".
    expect(prompt.toLowerCase()).toMatch(/never.*(minimise|minimize|soften|omit)/);
  });

  it('primary-care was bumped to v1.1.0 (M5 content change)', () => {
    const pc = all.find((t) => t.data.slug === 'primary-care')!;
    expect(pc.data.version).toBe('1.1.0');
    expect((pc.data.defaultCptHints as unknown[]).length).toBeGreaterThan(0);
  });
});
