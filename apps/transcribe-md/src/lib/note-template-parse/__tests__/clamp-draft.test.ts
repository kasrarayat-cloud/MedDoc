// ============================================================================
// clampDraftToLimits — a verbose LLM-generated value must never break review/
// save (the "Too big: expected string to have <=60 characters" incident). The
// engine clamps the draft to TEMPLATE_FIELD_LIMITS before it leaves the parse.
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  clampDraftToLimits,
  TEMPLATE_FIELD_LIMITS as LIM,
  type ParsedTemplateDraft,
} from '../note-template-schema';

function makeDraft(
  over: Partial<{ name: string; tense: string | null; label: string; key: string }> = {},
): ParsedTemplateDraft {
  return {
    name: over.name ?? 'Ortho follow-up',
    encounterType: 'orthopedics',
    sections: [
      {
        key: over.key ?? 'subjective',
        label: over.label ?? 'Subjective',
        order: 1,
        formatHint: 'prose',
        styleInstructions: null,
        defaultText: null,
        defaultTextMode: 'omit_unless_supported',
      },
    ],
    styleProfile: {
      tense: over.tense === undefined ? 'past' : over.tense,
      tone: 'concise',
      abbreviations: null,
    },
  };
}

describe('clampDraftToLimits', () => {
  it('clamps an over-long generated tense to the cap (the Dr. A "Too big" case)', () => {
    const longTense =
      'Past tense throughout the history and examination sections, switching to present tense for the assessment and plan and all patient instructions';
    expect(longTense.length).toBeGreaterThan(LIM.tense);
    const d = clampDraftToLimits(makeDraft({ tense: longTense }));
    expect(d.styleProfile.tense).not.toBeNull();
    expect(d.styleProfile.tense!.length).toBeLessThanOrEqual(LIM.tense);
  });

  it('clamps an over-long name + section key/label to their caps', () => {
    const d = clampDraftToLimits(
      makeDraft({
        name: 'N'.repeat(LIM.name + 50),
        label: 'L'.repeat(LIM.label + 50),
        key: 'k'.repeat(LIM.key + 50),
      }),
    );
    expect(d.name.length).toBe(LIM.name);
    expect(d.sections[0].label.length).toBe(LIM.label);
    expect(d.sections[0].key.length).toBe(LIM.key);
  });

  it('leaves within-limit values intact and preserves null fields', () => {
    const d = clampDraftToLimits(makeDraft({ name: 'Cardiology consult', tense: null }));
    expect(d.name).toBe('Cardiology consult');
    expect(d.styleProfile.tense).toBeNull();
    expect(d.sections[0].styleInstructions).toBeNull();
    expect(d.sections[0].defaultText).toBeNull();
  });
});
