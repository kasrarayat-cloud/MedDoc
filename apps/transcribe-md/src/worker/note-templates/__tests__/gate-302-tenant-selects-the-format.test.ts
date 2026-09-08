// ============================================================================
// #302 — THE CHART'S PRACTICE SELECTS THE FORMAT.
// ----------------------------------------------------------------------------
// #287 ruled that the tenant "scopes the visit AND selects/validates the
// template". Only the VALIDATION half was applied: `fill-engine.ts` rejected a
// template the tenant did not own while `worker.ts` still SELECTED one by
// `doctorId`. Two ends of one decision, on two axes.
//
// ⚠️ THE HALF-APPLICATION WAS WORSE THAN NEITHER HALF. On `main` both ends sat
// on the author and AGREED: a locum's visit rendered the wrong practice's form —
// wrong, and recoverable. Split, it produced no document at all, a false
// explanation, and (before the read-only pre-check) an irreversible pin.
//
// ⚠️ AND THE AUTHOR IS STILL TRIED FIRST, DELIBERATELY. Production is 58 of 58
// visits whose author practice equals the tenant, so for every visit that exists
// today the doctor's own template IS the tenant's and this ordering changes
// nothing. The tenant arm is reached only when they differ.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { selectTemplate } from '../resolve-active-template';

const A = 'practice-A-owns-the-chart';
const B = 'practice-B-the-locums-own';
const LOCUM = 'user-locum-from-B';
const HOST = 'user-doctor-at-A';

type T = Parameters<typeof selectTemplate>[0][number];

const tpl = (over: Partial<T>): T =>
  ({
    id: 'x',
    doctorId: null,
    practiceId: null,
    status: 'active',
    encounterType: null,
    isSystemDefault: false,
    version: 1,
    updatedAt: new Date('2026-01-01T00:00:00Z'),
    ...over,
  }) as T;

const SYSTEM = tpl({ id: 'sys', isSystemDefault: true, doctorId: null, practiceId: null });

describe('#302 — a locum visit renders the CHART practice’s format', () => {
  it("⚠️ THE TENANT'S ACTIVE TEMPLATE WINS when the author has none in this practice", () => {
    const tenantTpl = tpl({ id: 'tpl-A', practiceId: A, doctorId: HOST });
    const locumTpl = tpl({ id: 'tpl-B', practiceId: B, doctorId: LOCUM });

    const picked = selectTemplate([locumTpl, tenantTpl, SYSTEM], {
      doctorId: LOCUM,
      tenantPracticeId: A,
    });

    expect(picked.id, "the locum's own practice supplied the form for A's chart").toBe('tpl-A');
  });

  it('⚠️ AND THE AUTHOR STILL WINS IN THEIR OWN PRACTICE — the 58/58 case does not move', () => {
    // POSITIVE CONTROL for the ordering. Without it the arm above is satisfied
    // by a selector that ALWAYS prefers the tenant, which would re-point every
    // existing visit at whichever of a practice's templates sorted first.
    const mine = tpl({ id: 'tpl-mine', practiceId: A, doctorId: HOST });
    const colleague = tpl({ id: 'tpl-colleague', practiceId: A, doctorId: 'someone-else' });

    const picked = selectTemplate([colleague, mine, SYSTEM], {
      doctorId: HOST,
      tenantPracticeId: A,
    });
    expect(picked.id, "a doctor's own format was displaced by a colleague's").toBe('tpl-mine');
  });

  it('⚠️ A TENANT WITH NO ACTIVE TEMPLATE FALLS TO THE SYSTEM DEFAULT — never another practice’s', () => {
    // The second half of #302's arm. The tenant has nothing active; the locum
    // has a perfectly good template in B. It must NOT be chosen — that is the
    // wrong-practice document `main` produced.
    const locumTpl = tpl({ id: 'tpl-B', practiceId: B, doctorId: LOCUM });
    const inactiveAtA = tpl({ id: 'tpl-A-draft', practiceId: A, doctorId: HOST, status: 'draft' });

    const picked = selectTemplate([locumTpl, inactiveAtA, SYSTEM], {
      doctorId: 'nobody-with-a-template',
      tenantPracticeId: A,
    });
    expect(
      picked.id,
      "a template from ANOTHER practice was selected for A's chart",
    ).toBe('sys');
  });

  it('encounterType is honoured within the tenant, not across practices', () => {
    const tenantUltrasound = tpl({
      id: 'tpl-A-us',
      practiceId: A,
      doctorId: HOST,
      encounterType: 'ultrasound',
    });
    const locumUltrasound = tpl({
      id: 'tpl-B-us',
      practiceId: B,
      doctorId: LOCUM,
      encounterType: 'ultrasound',
    });

    const picked = selectTemplate([locumUltrasound, tenantUltrasound, SYSTEM], {
      doctorId: LOCUM,
      tenantPracticeId: A,
      encounterType: 'ultrasound',
    });
    expect(picked.id).toBe('tpl-A-us');
  });

  it('⚠️ WITHOUT a tenant the behaviour is EXACTLY as before — the non-worker callers', () => {
    // Settings previews and sample renders resolve a doctor's own format and
    // have no tenant to give. Passing none must change nothing, or this ruling
    // silently re-points surfaces it never named.
    const mine = tpl({ id: 'tpl-mine', doctorId: HOST, practiceId: A });
    const other = tpl({ id: 'tpl-other', doctorId: LOCUM, practiceId: B });

    expect(selectTemplate([other, mine, SYSTEM], { doctorId: HOST }).id).toBe('tpl-mine');
    expect(selectTemplate([other, mine, SYSTEM], { doctorId: 'nobody' }).id).toBe('sys');
  });
});
