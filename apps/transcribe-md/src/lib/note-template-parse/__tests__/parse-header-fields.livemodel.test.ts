// @vitest-environment node
// ============================================================================
// Real-model parse integration (operator-only, CI-excluded).
// Proves the FULL parseNoteToTemplate captures the operative-note header fields
// (PATIENT NAME / DOB / ID / DATE OF SURGERY / SURGEON) end-to-end: the LLM
// produces the body sections, the deterministic capture pulls the header LABELS
// from the region above the first clinical heading, and the PHI gate does not
// reject. Self-skips unless PARSE_LIVE_MODEL=1 (spends real tokens).
//   PARSE_LIVE_MODEL=1 npx vitest run src/lib/note-template-parse/__tests__/parse-header-fields.livemodel.test.ts
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

const LIVE = process.env.PARSE_LIVE_MODEL === '1';
const KEY = process.env.ANTHROPIC_API_KEY;

// parseNoteToTemplate is stateless, but the shared modelClient may touch the DB
// singleton for call logging — stub it so no DB is needed.
vi.mock('@meddoc/db', () => ({ default: { aiCall: { create: async () => ({}) } } }));

import { parseNoteToTemplate } from '../parse-note-to-template';

const OP_NOTE = `COMMAND HEALTH SURGICAL CENTER
OPERATIVE NOTE

PATIENT NAME: ______________________________
PATIENT DOB: ______________________________
PATIENT ID #: ______________________________
DATE OF SURGERY: ______________________________
SURGEON: ______________________________

PROCEDURE:
Name the procedure performed, concise clinical phrasing.

PREOPERATIVE DIAGNOSIS:
State the preoperative diagnosis succinctly.

POSTOPERATIVE FINDINGS:
Summarize intraoperative and postoperative findings.

CONSENT:
Document that consent was obtained and risks, benefits, and alternatives were discussed.

DESCRIPTION OF PROCEDURE:
Narrate the procedure in chronological detail, past tense.

RECOMMENDATIONS:
State postoperative recommendations and follow-up.`;

describe.skipIf(!LIVE || !KEY)('parseNoteToTemplate — header fields (real model)', () => {
  it('captures the operative header fields (labels only) while parsing the body', async () => {
    const res = await parseNoteToTemplate(OP_NOTE, { practiceId: 'p', userId: 'u' });
    expect(res.rejected).toBe(false);
    if (res.rejected) return;

    const hf = res.template.styleProfile.headerFields ?? [];
    // eslint-disable-next-line no-console
    console.log('\nheaderFields:', JSON.stringify(hf), '\nsections:', res.template.sections.map((s) => s.label));

    expect(hf.map((f) => f.key)).toEqual([
      'patient_name',
      'patient_dob',
      'patient_id',
      'date_of_surgery',
      'surgeon',
    ]);
    // Labels only — no values, no blanks-run absorbed, no digits.
    const labels = hf.map((f) => f.label).join(' | ');
    expect(labels).not.toMatch(/_{2,}|\d/);
    // The 6 body sections still parsed (form shape preserved).
    expect(res.template.sections.length).toBeGreaterThanOrEqual(6);
  }, 120_000);
});
