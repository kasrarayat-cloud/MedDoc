// ============================================================================
// OWNER FINDING — the certified operative note exported BLANK Preoperative
// Diagnosis and Description of Procedure although the dictation had both.
// ----------------------------------------------------------------------------
// Measured (codes/counts only): L3 under-populated the `procedure` object on the
// visit — only findings/recommendations — so procedure.preop_diagnosis and
// procedure.description had NO fact, and the twin fields resolved
// `not_mentioned / fact_not_mentioned` and rendered blank. The mapping and the
// resolver were correct; the miss was L3 CLASSIFICATION: the indication
// ("personal history of adenomatous colon polyps") was routed to history, and
// the time-out / procedural narrative never became `procedure.description`.
//
// The fix strengthens the L3 extraction guidance for exactly those two
// sub-fields. This gate pins that guidance to the exported prompt string so it
// cannot silently regress — a terse bullet is what produced the miss. It is a
// guidance gate, not a model eval; the real-model behaviour is exercised on QA.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

// 03-extract-entities imports the AI + db barrels at module load; stub them so
// the exported guidance const can be read without the worker runtime (mirrors
// 03-extract-entities.test.ts).
vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: vi.fn() } };
});
vi.mock('@meddoc/db', () => ({ default: { transcribeVisit: { update: vi.fn() } } }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { COMMON_CATEGORIES } from '../03-extract-entities';

describe('L3 operative-note guidance — preop_diagnosis and description', () => {
  it('NON-VACUITY — the procedure sub-field guidance is present', () => {
    expect(COMMON_CATEGORIES).toContain('procedure');
    expect(COMMON_CATEGORIES).toContain('preop_diagnosis');
    expect(COMMON_CATEGORIES).toContain('description');
    expect(COMMON_CATEGORIES.length).toBeGreaterThan(200);
  });

  it('⚠️ preop_diagnosis guidance routes a HISTORY/indication phrasing into the field', () => {
    // The exact miss: "personal history of ..." was classified as history and
    // preop_diagnosis left empty. The guidance must tell the model to POPULATE
    // preop_diagnosis for an operative note even when the phrase reads as history.
    const g = COMMON_CATEGORIES;
    expect(g).toMatch(/preop_diagnosis[\s\S]{0,400}history/i);
    expect(g).toMatch(/preop_diagnosis[\s\S]{0,500}(POPULATE|indication IS the preop)/);
    // and it must NOT tell the model to leave it empty when it looks like history
    expect(g).toMatch(/do not drop it|even when the same phrase also reads/i);
  });

  it('⚠️ description guidance captures the FULL operative narrative (time-out), not just the procedure name', () => {
    const g = COMMON_CATEGORIES;
    // Distinctive phrases unique to the operative-description guidance.
    expect(g).toContain('FULL operative');
    expect(g).toContain('time-out');
    expect(g).toContain('running procedural narrative');
    // discrete vital VALUES still go to measurements — the narrative belongs here
    expect(g).toContain('still go to measurements');
  });
});
