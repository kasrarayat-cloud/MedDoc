/**
 * RULING #179(1) — THE ROS LEXICON IS CLOSED, AND THE SYMPTOM MUST BELONG TO
 * ITS OWN SYSTEM.
 *
 * ⚠️ THE LAST OF FOUR UNARMED #179 PARTS. Deleting the membership refinement —
 * `if (!allowed.includes(item.finding))` — redded **0 of 5922**. The guard was
 * present, commented, and proved by nothing.
 *
 * WHAT IT PREVENTS, in the schema's own words: a per-field enum cannot express
 * this, because the legal set DEPENDS on `system`. Without the refinement the
 * schema admits `{ system: 'cardiovascular', finding: 'heartburn' }` and the
 * projector emits `ros.cardiovascular.heartburn` — a concept the registry
 * admits by pattern and **no clause can honestly cover**. It would be a
 * finding filed under an organ system the doctor never said it about.
 *
 * Driven through the SHIPPED `ExtractedEntities` schema, not a reconstruction.
 */
import { describe, it, expect, vi } from 'vitest';

// ⚠️ THE SAME TWO MOCKS THE SIBLING ROS TEST CARRIES, AND FOR THE SAME REASON.
// `03-extract-entities` imports `@/lib/audit`, whose graph reaches next-auth
// and fails to resolve `next/server` under vitest. Without these the file does
// not IMPORT, and "no tests" is not a pass — it is an arm that never ran.
vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { ExtractedEntities } from '../03-extract-entities';
import { ROS_SYSTEMS, symptomsFor, ROS_OTHER } from '@/lib/template-twin/ros-lexicon';

const MINIMAL = { chief_complaint: null, hpi: null };

function withRos(system: string, finding: string) {
  return ExtractedEntities.safeParse({
    ...MINIMAL,
    ros: [
      {
        system,
        finding,
        polarity: 'affirmed',
        evidence_quote: 'synthetic evidence for the arm',
      },
    ],
  });
}

describe('#179(1) — the ROS lexicon is closed and per-system', () => {
  it('NON-VACUITY: a symptom that BELONGS to its system parses', () => {
    // Without this every rejection below is equally consistent with a schema
    // that rejects all ROS entries, which would blank the section entirely.
    const system = ROS_SYSTEMS.find((s) => symptomsFor(s).some((x) => x !== ROS_OTHER));
    expect(system, 'the lexicon must have at least one addressable symptom').toBeTruthy();
    const finding = symptomsFor(system as string).find((x) => x !== ROS_OTHER) as string;
    const r = withRos(system as string, finding);
    expect(r.success, `${system}/${finding} should parse: ${JSON.stringify(r.error?.issues?.[0])}`).toBe(true);
  });

  it('⚠️ a symptom from a DIFFERENT system is REJECTED', () => {
    // The exact case the schema comment names. `heartburn` is real and
    // `cardiovascular` is real; the PAIR is the lie.
    const gi = ROS_SYSTEMS.find((s) => symptomsFor(s).includes('heartburn'));
    expect(gi, 'the lexicon should carry heartburn somewhere').toBeTruthy();
    expect(gi).not.toBe('cardiovascular');
    expect(withRos('cardiovascular', 'heartburn').success).toBe(false);
  });

  it('an INVENTED symptom is rejected, in every system', () => {
    for (const s of ROS_SYSTEMS) {
      expect(withRos(s, 'definitely_not_a_symptom').success, s).toBe(false);
    }
  });

  it('an INVENTED SYSTEM is rejected — the enum is closed too', () => {
    expect(withRos('phrenology', 'heartburn').success).toBe(false);
  });

  it('the refusal NAMES the allowed set, so the retry loop can act on it', () => {
    // A schema that refuses without saying what was legal turns a recoverable
    // retry into a guess.
    const r = withRos('cardiovascular', 'heartburn');
    expect(r.success).toBe(false);
    const msg = r.success ? '' : r.error.issues.map((i) => i.message).join(' | ');
    expect(msg).toContain('heartburn');
    expect(msg).toContain('cardiovascular');
    expect(msg.length, 'the message must enumerate the legal findings').toBeGreaterThan(40);
  });

  it('the lexicon is the size the ruling claims — one definition, not a copy', () => {
    // #179(1): 13 systems, 72 addressable symptoms, plus `other`. Asserted
    // against the SHIPPED lexicon so a silent edit to either side is visible.
    expect(ROS_SYSTEMS.length).toBe(13);
    const addressable = ROS_SYSTEMS.reduce(
      (n, s) => n + symptomsFor(s).filter((x) => x !== ROS_OTHER).length,
      0,
    );
    expect(addressable).toBe(72);
  });
});
