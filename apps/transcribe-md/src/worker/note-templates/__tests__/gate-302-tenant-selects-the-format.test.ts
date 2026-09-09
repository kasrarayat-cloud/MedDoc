import { readFileSync } from 'node:fs';
import { join } from 'node:path';
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

// ════════════════════════════════════════════════════════════════════════════
// ⚠️ THE TWO QUERIES IN `worker.ts` THAT THE PURE-SELECTOR ARMS CANNOT SEE.
//
// Everything above drives `selectTemplate`, which is pure. The defects a
// refutation lens found were in the two PRISMA queries around it, and no arm in
// this repo drove either — `src/worker.ts` is in `gate-practice-scope`'s
// SYSTEM_PATHS, so that gate does not require its reads to be scoped and passed
// while a locum's practice-B form was reachable for practice A's chart.
//
// These read SOURCE rather than behaviour, deliberately: making them
// behavioural would mean extracting a helper, and a fix that ADDS a path earns
// another adversarial round under the exit rule. A deletion and a narrowing do
// not.
// ════════════════════════════════════════════════════════════════════════════
describe('#302 — the worker\'s own queries, not just the selector', () => {
  const WORKER = readFileSync(
    join(__dirname, '..', '..', '..', 'worker.ts'),
    'utf8',
  );

  /** The balanced `{...}` block that follows `marker`. */
  const blockAfter = (marker: string): string => {
    const at = WORKER.indexOf(marker);
    expect(at, `anchor not found in worker.ts: ${marker}`).toBeGreaterThan(-1);
    const open = WORKER.indexOf('{', at);
    let depth = 0;
    for (let i = open; i < WORKER.length; i++) {
      if (WORKER[i] === '{') depth++;
      else if (WORKER[i] === '}' && --depth === 0) return WORKER.slice(open, i + 1);
    }
    throw new Error(`unbalanced block after ${marker}`);
  };

  it('⚠️ THE EXPLICIT PER-VISIT PICK IS TENANT-SCOPED — `OR` IS A DISJUNCTION', () => {
    const where = blockAfter('const picked = visit.noteTemplateId');
    // POSITIVE CONTROL: the block really is the query, not some other brace.
    expect(where).toContain('id: visit.noteTemplateId');
    expect(where, 'the pick must admit the tenant\'s templates').toContain(
      'practiceId: visit.practiceId',
    );
    // THE FINDING: a bare author disjunct beside the tenant one is satisfied by
    // `doctorId` ALONE, so a locum's out-of-tenant template is picked and the
    // resolver — which #302 fixed — is never reached.
    expect(
      /\{\s*doctorId:/.test(where),
      'worker.ts admits a template by `doctorId` alone in the per-visit pick. ' +
        '`OR` is a disjunction: a locum from practice B naming their own ' +
        'template fills practice A\'s chart with B\'s format, and `picked ??` ' +
        'short-circuits past resolveActiveTemplate entirely. Every in-scope ' +
        'doctor-owned template already matches the practice disjunct — the T7 ' +
        'migration enforces practice-IFF-doctor — so this can only ADD ' +
        'out-of-scope rows.',
    ).toBe(false);
  });

  it('⚠️ THE FALLBACK BANNER PROBE IS TENANT-SCOPED — OR IT WARNS ABOUT ANOTHER PRACTICE\'S FORM', () => {
    const where = blockAfter('prisma.noteTemplate.count(');
    // POSITIVE CONTROL: this is the applicable-template probe and not another count.
    expect(where).toContain("isSystemDefault: false");
    expect(where).toContain('encounterType: visit.specialty');
    expect(
      where,
      'the probe explains why the SYSTEM DEFAULT was used. Unscoped it counts ' +
        'the author\'s templates at OTHER practices, so a locum correctly ' +
        'rendering the tenant\'s standard layout is told they have an ' +
        'activated format that was not applied — a false banner on the note ' +
        'they are about to sign, which the code\'s own comment calls the ' +
        'fastest way to teach a clinician to ignore the banner that matters.',
    ).toContain('practiceId: visit.practiceId');
  });
});
