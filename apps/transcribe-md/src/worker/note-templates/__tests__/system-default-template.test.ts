// ============================================================================
// System-default template — faithfulness + anti-drift tests (Phase 0).
// ----------------------------------------------------------------------------
// The additive guarantee for Phase 1 rests on this: the seeded system-default
// template must encode EXACTLY the SOAP format L4 emits today. These tests pin
// it three ways:
//   1. structural — a note built from the template's headings passes the live
//      `validateSoapStructure` contract L4 itself uses.
//   2. content    — the template carries L4's section directives + global
//      guardrails (fixture comparison).
//   3. drift      — the distinctive directive phrases still exist in
//      04-generate-soap.ts (L4 drift), AND the migration's seeded JSON
//      deep-equals this TS constant (SQL↔TS drift).
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateSoapStructure } from '../../layers/soap-structure-validator';
import {
  SYSTEM_DEFAULT_NOTE_TEMPLATE,
  SYSTEM_DEFAULT_TEMPLATE_ID,
  type NoteTemplateSection,
} from '../system-default-template';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// Phase 1: L4 no longer hard-codes the prompt — the canonical pre-Phase-1
// prompt now lives in the golden fixture, which the golden test locks against
// builder(system-default). We guard the template's directives against THAT.
const GOLDEN_SYS = path.resolve(
  HERE,
  '../../layers/__tests__/__fixtures__/l4-system-default.system.golden.txt'
);
const MIGRATIONS_DIR = path.resolve(
  HERE,
  '../../../../../../packages/db/prisma/migrations'
);

const sections = SYSTEM_DEFAULT_NOTE_TEMPLATE.sections;
const byKey = (k: string): NoteTemplateSection =>
  sections.find((s) => s.key === k)!;

describe('system-default template — identity', () => {
  it('is the singleton system default (stable id, no doctor, active, v1)', () => {
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.id).toBe(SYSTEM_DEFAULT_TEMPLATE_ID);
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.doctorId).toBeNull();
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.isSystemDefault).toBe(true);
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.status).toBe('active');
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.version).toBe(1);
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.encounterType).toBeNull();
  });
});

describe('system-default template — encodes the 4 L4 SOAP sections in order', () => {
  it('has exactly subjective/objective/assessment/plan, ordered 1..4', () => {
    expect(sections.map((s) => s.key)).toEqual([
      'subjective',
      'objective',
      'assessment',
      'plan',
    ]);
    expect(sections.map((s) => s.order)).toEqual([1, 2, 3, 4]);
    expect(sections.map((s) => s.label)).toEqual([
      'Subjective',
      'Objective',
      'Assessment',
      'Plan',
    ]);
  });

  it("a note built from the template's headings passes the LIVE L4 structure validator", () => {
    // This couples the template to the exact contract L4 enforces post-
    // generation. Drop/rename a section here → this fails, same as L4 would.
    const note =
      sections
        .map((s) => `## ${s.label}\n\nPlaceholder content for ${s.label}.`)
        .join('\n\n') + '\n';
    const result = validateSoapStructure(note);
    expect(result.ok).toBe(true);
    expect(result.missingSections).toEqual([]);
  });

  it('every section is omit_unless_supported with no scaffold text (no fabrication)', () => {
    for (const s of sections) {
      expect(s.defaultTextMode).toBe('omit_unless_supported');
      expect(s.defaultText).toBeNull();
    }
  });
});

describe('system-default template — carries L4 directives + global guardrails', () => {
  it('Subjective encodes the bolded sub-fields + the ROS fallback line', () => {
    const s = byKey('subjective').styleInstructions ?? '';
    expect(s).toContain('**Chief Complaint:**');
    expect(s).toContain('**HPI:**');
    expect(s).toContain('**PMH:**');
    expect(s).toContain('**Medications:**');
    expect(s).toContain('**Allergies:**');
    expect(s).toContain('**Family History:**');
    expect(s).toContain('**Social History:**');
    expect(s).toContain('ROS not formally documented in this encounter');
  });

  it('Objective encodes the no-exam fallback line', () => {
    // Phrase chosen to not span L4's line-wrap (".. in this\nencounter.").
    expect(byKey('objective').styleInstructions).toContain(
      'Formal exam not documented in this'
    );
  });

  it('Plan is a numbered list covering the L4 plan items', () => {
    expect(byKey('plan').formatHint).toBe('numbered');
    expect(byKey('plan').styleInstructions).toContain('patient education');
  });

  it('style profile carries the verbatim L4 global guardrails', () => {
    const rules = SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile.globalRules.join('\n');
    expect(rules).toContain('Do NOT invent clinical findings');
    expect(rules).toContain('Per patient,');
    expect(rules).toContain('[clarify with patient]');
    expect(rules).toContain('Output ONLY the SOAP note markdown');
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile.tone).toBe('professional medical');
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile.preamble).toContain(
      'senior clinician writing a SOAP note'
    );
  });
});

describe('system-default template — drift guards', () => {
  it('the canonical golden prompt contains the directives this template mirrors', () => {
    // Phase 1: L4 builds its prompt FROM this template, so the golden
    // fixture (the locked pre-Phase-1 prompt) is the canonical snapshot. Each
    // phrase is contiguous within a single golden line (no wrap span), so a
    // raw substring check is reliable. The golden test separately proves
    // builder(system-default) === this golden, so together these guarantee
    // the template still reproduces every safety directive.
    const golden = readFileSync(GOLDEN_SYS, 'utf8');
    const required = [
      '## Subjective',
      '## Objective',
      '## Assessment',
      '## Plan',
      '**Chief Complaint:**',
      'ROS not formally documented in this encounter',
      'Formal exam not documented in this',
      'Per patient',
      '[clarify with patient]',
      'Output ONLY the SOAP note markdown',
      'Do NOT invent clinical findings',
      'Numbered list: diagnostics ordered',
    ];
    for (const phrase of required) {
      expect(golden, `golden prompt no longer contains: "${phrase}"`).toContain(
        phrase
      );
    }
  });

  it("the migration's seeded JSON deep-equals this TS source of truth", () => {
    // Phase 1 re-synced the seed content (byte-exact wrapping), so the
    // effective seeded JSON is the resync migration's UPDATE — that's what
    // must match the constant now.
    const dir = readdirSync(MIGRATIONS_DIR).find((d) =>
      d.endsWith('_resync_system_default_template_phase1')
    );
    expect(dir, 'resync_system_default_template_phase1 migration dir not found').toBeTruthy();
    const sql = readFileSync(
      path.join(MIGRATIONS_DIR, dir!, 'migration.sql'),
      'utf8'
    );

    // Each JSONB literal sits on its own marked line: `@seed:<name> */ '...'::jsonb`.
    // SQL doubles single quotes ('') — undo that before JSON.parse.
    const extract = (marker: string): unknown => {
      // Match `@seed:<marker> */ ... '<json>'::jsonb` — `[^']*` skips any
      // column assignment (e.g. `"sections" = `) between the marker and the
      // opening quote of the JSONB literal.
      const re = new RegExp(`@seed:${marker} \\*/[^']*'(.*)'::jsonb`);
      const m = sql.match(re);
      expect(m, `seed marker @seed:${marker} not found in migration.sql`).toBeTruthy();
      return JSON.parse(m![1].replace(/''/g, "'"));
    };

    expect(extract('sections')).toEqual(SYSTEM_DEFAULT_NOTE_TEMPLATE.sections);
    expect(extract('styleProfile')).toEqual(SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile);
  });
});
