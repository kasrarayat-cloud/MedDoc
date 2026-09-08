// ============================================================================
// REVIEW-DEFAULTS — THE INSERT DOOR, DRIVEN. OWNER RULING #204.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE THE DOOR HAD ZERO EXECUTABLE COVERAGE AND THREE
// WHOLE-FILE STRING READS STANDING IN FOR IT. Measured on `432bd450` before a
// line of it was written — each mutation asserting its own application by
// byte-delta first:
//
//   door's `scaffolded`/text refusal deleted          -> 78 passed, NOT CAUGHT
//   door's SCAFFOLD_INSERTABLE_KINDS refusal deleted  -> 78 passed, NOT CAUGHT
//   door's `clinicalConcept` refusal deleted          -> 78 passed, NOT CAUGHT
//   ALL THREE deleted at once                         -> 78 passed, NOT CAUGHT
//   CONTROL: the OFFER's omit clause deleted          -> 5 failed  (RED)
//
// The harness was never broken. It was not pointed at the door.
//
// ⚠️ AND THE ARMS HERE ASSERT BEHAVIOUR, NOT SPELLING. Ruling #204 forbids the
// two shapes that produced the false coverage above: a body-slice read of the
// source, and a literal-spelling regex over it. Both were demonstrated to fail
// in BOTH directions — three re-introduced defects passed a `not.toMatch` arm
// (a double-quoted `=== "omit"`, a destructured local, an `includes` form) and
// two FALSE REDS fired on prose alone. So nothing below reads this file's
// subject as text. Every arm calls the door and looks at what it DID: whether
// the override row was written, whether the audit row was emitted, and what the
// doctor was told.
//
// WHAT IS DELIBERATELY REAL vs MOCKED, because that choice is the whole gate:
//   · REAL   `scaffoldDefaultOfferable` — the offer's own predicate. If the
//            door and the offer stop sharing one definition, these arms move.
//   · MOCKED `readAndPrepareTemplateTwinFill` — the per-visit RESOLUTION is the
//            input under test, so it is supplied directly. Mocking the resolver
//            instead would test the resolver.
//   · REAL   everything else in the door's own module.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';

const visitFindFirst = vi.fn();
const templateFindFirst = vi.fn();
const overrideUpsert = vi.fn();
const overrideDeleteMany = vi.fn();
const defFindUnique = vi.fn();
const invalidate = vi.fn();
const audit = vi.fn();
const readAndPrepare = vi.fn();
const lockedVisit = vi.fn();

// ⚠️ `$transaction` RUNS THE REAL CALLBACK, and `$queryRaw` answers the
// FOR UPDATE re-read. The door now re-asserts the visit's status at the write,
// under a lock, because it performs two full fills between reading the status
// and writing — so a sign can land in the window. A mock that stubbed the
// transaction away would make every arm below pass without the re-check ever
// running, which is the vacuity this file exists to avoid.
//
// ⚠️ AND THE TRANSACTIONAL CLIENT IS A **DIFFERENT OBJECT** — ROUND FIVE.
// This read `$transaction: (fn) => fn(db)`, handing the callback the SAME
// client. `tx.templateTwinFieldOverride.upsert` and
// `prisma.templateTwinFieldOverride.upsert` were then literally the same
// function, so rewriting `tx.` to `prisma.` — which takes the write OUT of the
// transaction and out from under the `FOR UPDATE` — was **97/97 green**. The
// lock would still be taken, still block, and protect nothing, because the
// write it is supposed to serialise would be on another connection.
//
// A harness whose two clients are one object cannot see the only mistake that
// matters here.
const onTx = { upsert: false, deleteMany: false, queryRaw: false };

const db: Record<string, unknown> = {
  transcribeVisit: { findFirst: (...a: unknown[]) => visitFindFirst(...a) },
  noteTemplate: { findFirst: (...a: unknown[]) => templateFindFirst(...a) },
  templateTwinFieldOverride: {
    upsert: (...a: unknown[]) => overrideUpsert(...a),
    deleteMany: (...a: unknown[]) => overrideDeleteMany(...a),
  },
  templateTwinFieldDefinition: { findUnique: (...a: unknown[]) => defFindUnique(...a) },
  $queryRaw: (...a: unknown[]) => lockedVisit(...a),
};

/** The client the callback is handed. Same behaviour, different identity. */
const tx: Record<string, unknown> = {
  ...db,
  templateTwinFieldOverride: {
    upsert: (...a: unknown[]) => {
      onTx.upsert = true;
      return overrideUpsert(...a);
    },
    deleteMany: (...a: unknown[]) => {
      onTx.deleteMany = true;
      return overrideDeleteMany(...a);
    },
  },
  $queryRaw: (...a: unknown[]) => {
    onTx.queryRaw = true;
    return lockedVisit(...a);
  },
};
db.$transaction = (fn: (client: unknown) => unknown) => fn(tx);

vi.mock('@meddoc/db', () => ({ default: db }));
vi.mock('@/lib/auth', () => ({
  requireSession: async () => ({ user: { id: 'requester-1', practiceId: 'prac-1' } }),
}));
vi.mock('@/lib/audit', () => ({ logAudit: (...a: unknown[]) => audit(...a) }));
vi.mock('@/lib/practice-scope', () => ({
  visitByIdScope: (id: string, practiceId: string) => ({ id, practiceId }),
  asPracticeId: (p: string) => p,
}));
vi.mock('@/lib/docx-preview/fill-cache', () => ({
  invalidateVisitFills: (...a: unknown[]) => invalidate(...a),
}));
vi.mock('@/lib/template-twin/fill-engine', () => ({
  readAndPrepareTemplateTwinFill: (...a: unknown[]) => readAndPrepare(...a),
}));

const VISIT = 'visit-1';

// ⚠️ THE IR IS COMPILED FROM THE TRACKED FIXTURE AND THEN MUTATED — NOT
// HAND-WRITTEN. `TemplateDocIRSchema` is `.strict()` over ~30 top-level and
// per-field properties; a hand-built object encodes the AUTHOR'S GUESS of that
// shape and goes stale the moment the compiler moves. So the real compiler
// produces the field and this file changes exactly the two properties under
// test.
//
// ⚠️ AND THE FIXTURE CANNOT DRIVE THIS DOOR UNMUTATED, WHICH IS THE POINT.
// `WM IOV Template.docx` compiles to 80 fields — 52 `narrative_text`, 28
// `single_select` — and **ZERO** are `scaffolded`, ZERO carry `scaffoldText`.
// Measured, not assumed. Production is the same shape: 0 of 185 fields across
// all four compiled versions. A fixture that cannot reach the code under test
// is not a fixture for it, and that is why every earlier arm on this door was a
// string read.
const BASE_IR = compileTemplateDocx(
  new Uint8Array(readFileSync(path.resolve(process.cwd(), '../../WM IOV Template.docx'))),
) as unknown as { fields: Array<Record<string, unknown>> };

const NARRATIVE = BASE_IR.fields.find((f) => f.kind === 'narrative_text')!;
const SELECT = BASE_IR.fields.find((f) => f.kind === 'single_select')!;
const FIELD = NARRATIVE.fieldId as string;
/** A DIFFERENT field, placed FIRST in every manifest — see `manifest()`. */
const DECOY = BASE_IR.fields.find((f) => f.fieldId !== FIELD)!.fieldId as string;
/** Distinctive on purpose: an empty object would match a blanked argument. */
const ENTITIES = { probe: 'entities-fixture', findings: ['x'] };

/** The compiled IR with ONE field overridden — everything else stays real. */
function irWith(over: Record<string, unknown>, targetId: string = FIELD) {
  return {
    ...BASE_IR,
    fields: BASE_IR.fields.map((f) =>
      f.fieldId === targetId ? { ...f, ...over } : f,
    ),
  };
}

/** The default under test: the compiler marked it scaffolded and it has text. */
const SCAFFOLDED = { scaffolded: true, scaffoldText: 'No acute findings.' };

/**
 * A manifest whose FIRST entry is a DECOY for a different field.
 *
 * ⚠️ ROUND THREE FOUND THIS. Every manifest here used to carry exactly ONE
 * field, so `fields.find(f => f.fieldId === fieldId)` and `fields[0]` were
 * indistinguishable: replacing the lookup with `[0]` stayed green on the gate
 * suite, on all 5812 tests, and under tsc. In production that gates every
 * insert on whichever field is first in the manifest — on the tracked fixture
 * an administrative header that resolves `not_mentioned` on essentially every
 * visit — so the door would admit an insert on ANY field, including one whose
 * omit fired.
 *
 * The decoy is deliberately ADMISSIBLE-looking, so a door reading the wrong
 * entry gets a permissive answer and the arm reds.
 *
 * ⚠️ IT ALSO CARRIES `render`, WHICH IS NOT DECORATION. The door refuses when
 * the fill produced no document; a mock without it tests the refusal, not the
 * path.
 */
function manifest(target: Record<string, unknown>) {
  return {
    prepared: {
      render: { document: new Uint8Array([1, 2, 3]) },
      manifest: {
        fields: [{ ...resolution({}), fieldId: DECOY }, target],
      },
    },
  };
}

/** One per-field resolution, as `prepared.manifest.fields` carries it. */
function resolution(over: Record<string, unknown> = {}) {
  return {
    fieldId: FIELD,
    status: 'not_mentioned',
    value: null,
    sourceFactIds: [],
    evidenceAnchorIds: [],
    selectedOptionOrdinal: null,
    reasonCode: 'no_supporting_evidence',
    clinicianReviewed: false,
    ...over,
  };
}

function primeVisit(over: Record<string, unknown> = {}) {
  visitFindFirst.mockResolvedValue({
    id: VISIT,
    status: 'READY',
    noteTemplateId: 'tpl-1',
    noteTemplateVersion: 3,
    userId: 'author-1',
    inputMode: 'voice_dictation',
    transcriptText: 'transcript',
    entities: ENTITIES,
    soapFinal: 'A note.',
    createdAt: new Date('2026-09-06T00:00:00Z'),
    // ⚠️ DELIBERATELY DIFFERENT FROM THE SESSION'S `prac-1`.
    //
    // `resolveCertifiedTwinField` FILTERS `transcribe_visits."practiceId"` with
    // the SESSION's practice and RETURNS `visit.user.practiceId` — two different
    // columns. While the fixture used one value for both, an arm asserting the
    // lock's bound parameter could not tell them apart, and the insert door
    // shipped for an hour passing the RETURNED one into a lock that filters the
    // FILTERED one.
    //
    // A fixture that gives two distinct things the same value cannot witness
    // them being confused.
    //
    // ⚠️ AND THERE ARE **THREE** VALUES HERE, NOT TWO — RULING #267. The split
    // above separated the SESSION's practice from the AUTHOR's and stopped
    // there, so `transcribe_visits."practiceId"` — the VISIT'S OWN TENANT, and
    // the column every attached row is stamped with — was still borrowing one
    // of the other two. That is the same disease one input over, and it is why
    // `SF-1` survived the split that was supposed to end it.
    //
    // The three, and they are three different questions:
    //   · `prac-1`            the SESSION's practice   — may this actor act?
    //   · `visit-tenant-7`    the VISIT'S tenant       — what owns this chart?
    //   · `author-practice-9` the AUTHOR's practice    — whose form fills it?
    //
    // ⚠️ THE TENANT IS DELIBERATELY **NOT** `prac-1`, even though production
    // scoping makes them equal for any visit a door can reach. A fixture that
    // reproduces the coincidence cannot witness the code depending on it — and
    // the door's own comment already records that the equality is "a property
    // of the data, not of the code".
    practiceId: 'visit-tenant-7',
    user: { practiceId: 'author-practice-9' },
    ...over,
  });
}

function primeTemplate(ir: unknown = irWith(SCAFFOLDED)) {
  templateFindFirst.mockResolvedValue({
    templateTwinCompiledVersion: {
      id: 'cv-1',
      certificationStatus: 'CERTIFIED',
      compiledDocumentIr: ir,
    },
  });
}

async function insert(fieldId: string = FIELD) {
  const mod = await import('../set-template-control');
  return mod.insertScaffoldDefaultAction(VISIT, fieldId);
}

beforeEach(() => {
  onTx.upsert = false;
  onTx.deleteMany = false;
  onTx.queryRaw = false;
  vi.clearAllMocks();
  primeVisit();
  primeTemplate();
  defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: 'assessment' } });
  readAndPrepare.mockResolvedValue(manifest(resolution()));
  overrideUpsert.mockResolvedValue({});
  lockedVisit.mockResolvedValue([{ status: 'READY', signedAt: null }]);
});

describe('ROUND FOUR — the four guards nothing was watching', () => {
  // Each of these was reported by round four as "deleting it leaves the suite
  // green". Each arm below is paired with a mutation in the commit message
  // showing it now REDS. #204's clause: deleting a guard must red.

  it('the insert INVALIDATES the fill cache — or the doctor cannot see their own insert', async () => {
    // ⚠️ WITHOUT THIS THE INSERT IS INVISIBLE FOR UP TO THE 30-MINUTE TTL.
    // `insertableDefaults` lives inside the cached payload, so a warm entry
    // serves the pre-insert list — the doctor clicks, the row lands, and the
    // form does not change. Ruling #203 is about the same cache and the same
    // failure mode one layer up.
    await insert();
    expect(invalidate).toHaveBeenCalledWith(VISIT);
  });

  it('the UNDO invalidates it too — the same defect in the other direction', async () => {
    const mod = await import('../set-template-control');
    overrideDeleteMany.mockResolvedValue({ count: 1 });
    await mod.undoScaffoldDefaultAction(VISIT, FIELD);
    expect(invalidate).toHaveBeenCalledWith(VISIT);
  });

  it("UNDO deletes ONLY the scaffold_default row — a dropdown correction is not collateral", async () => {
    // ⚠️ THE KIND SCOPE IS THE WHOLE ARM. One row per (visitId, fieldId), and a
    // doctor may have made a DROPDOWN correction on the same field. An undo that
    // dropped the kind predicate would delete the clinician's own choice while
    // reporting that it undid an inserted default.
    const mod = await import('../set-template-control');
    overrideDeleteMany.mockResolvedValue({ count: 1 });
    await mod.undoScaffoldDefaultAction(VISIT, FIELD);
    expect(overrideDeleteMany).toHaveBeenCalledWith({
      where: { visitId: VISIT, fieldId: FIELD, overrideKind: 'scaffold_default' },
    });
  });

  it('UNDO writes its OWN audit action, not the insert one', async () => {
    // #194's product claim is that a default reaching a note is a HUMAN act. A
    // trail that cannot tell an insert from its reversal counts a retracted
    // assertion as an assertion, which is what the second enum value was bought
    // for. `gate-review-defaults-insert.test.ts:24` still says these rows are
    // "asserted NOWHERE executable" — they are now.
    const mod = await import('../set-template-control');
    overrideDeleteMany.mockResolvedValue({ count: 1 });
    await mod.undoScaffoldDefaultAction(VISIT, FIELD);
    expect(audit).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'DEFAULT_INSERT_UNDONE' }),
    );
    expect(audit).not.toHaveBeenCalledWith(
      expect.objectContaining({ action: 'DEFAULT_INSERTED_BY_DOCTOR' }),
    );
  });

  it('the door REFUSES a soft-deleted or archived visit — asserted on the query', async () => {
    // ⚠️ REPORTED AS "removing it leaves 133/133 green". Asserted on the WHERE
    // the door issues rather than on an outcome, because a deleted visit is not
    // reachable through the mocked findFirst — the filter is the guard, and the
    // filter is what must not disappear.
    await insert();
    const w = (visitFindFirst.mock.calls[0][0] as { where: Record<string, unknown> }).where;
    expect(w).toMatchObject({ deletedAt: null, archivedAt: null });
  });
});

describe("ROUND FOUR — round one's defect cannot come back, asserted as BEHAVIOUR", () => {
  // ⚠️ #204's CLAUSE ASKED FOR EXECUTABLE COVERAGE AND THIS IS THE MISSING HALF.
  // Round four demonstrated that round one's defect — a STATIC refusal on
  // `mapping.unmentionedPolicy === 'omit'`, a CONFIRM-TIME property deciding a
  // PER-VISIT question — could be re-introduced with the gate files green.
  //
  // The arm that exists in `gate-review-defaults-omit-door.test.ts` is a
  // whole-file `not.toContain('unmentionedPolicy: true')`. It happens to red
  // when the defect is re-introduced by widening THAT select with THAT spelling
  // — measured — but it is a string read standing in for behaviour, and any
  // other route to the property (a second query, a join, reading it off the IR)
  // walks past it.
  //
  // This arm drives the REAL action with a field whose mapping carries
  // `unmentionedPolicy: 'omit'` and asserts the door ADMITS it, because the
  // per-visit resolution says the field is blank. Spelling-independent: it fails
  // for any door that consults the static policy, however it obtains it.

  it('a field whose mapping says `omit` is still ADMITTED when the visit leaves it blank', async () => {
    defFindUnique.mockResolvedValue({
      mapping: { clinicalConcept: 'assessment', unmentionedPolicy: 'omit' },
    });
    readAndPrepare.mockResolvedValue(manifest(resolution({ reasonCode: 'no_supporting_evidence' })));
    const res = await insert();
    expect(res.ok, res.error).toBe(true);
    expect(overrideUpsert).toHaveBeenCalledTimes(1);
  });

  it('⚠️ THE CONTROL — the SAME omit mapping is REFUSED when the visit actually omitted it', async () => {
    // Without this, the arm above passes for a door that admits everything. The
    // per-visit answer is what decides, and here it says the field WAS omitted.
    defFindUnique.mockResolvedValue({
      mapping: { clinicalConcept: 'assessment', unmentionedPolicy: 'omit' },
    });
    readAndPrepare.mockResolvedValue(
      manifest(resolution({ reasonCode: 'omitted_unsupported_default' })),
    );
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('the door never READS the static policy — asserted on the query it issues', async () => {
    // Complements the two behavioural arms: the door must not even fetch the
    // column, so a future edit cannot quietly start consulting it.
    await insert();
    const sel = defFindUnique.mock.calls[0][0] as { select?: { mapping?: { select?: object } } };
    expect(Object.keys(sel.select?.mapping?.select ?? {})).toEqual(['clinicalConcept']);
  });
});

describe('ROUND FOUR — a sign landing in the window cannot be written over', () => {
  // ⚠️ THE WINDOW IS SECONDS WIDE AND THIS CHANGE MADE IT WIDER. The status is
  // read at the top of the action; the write happens after TWO full fills (each
  // an object-storage read, a docx-to-text pass and a render) — the second added
  // by the post-write simulation above. Round four found the door never
  // re-checked. What lands in that window is a SIGN, and a signed visit shows no
  // panel: no panel, no Undo button, and the row is permanent.

  it('⚠️ NON-VACUITY — the re-read really happens, and it takes the row LOCK', async () => {
    await insert();
    expect(lockedVisit, 'the door never re-read the visit at the write').toHaveBeenCalledTimes(1);
    const sql = String((lockedVisit.mock.calls[0][0] as { join?: unknown; raw?: unknown[] } & TemplateStringsArray).raw?.join('') ?? '');
    expect(sql).toMatch(/FOR UPDATE/);
    expect(sql).toMatch(/transcribe_visits/);
  });

  it('⚠️ THE LOCKED RE-READ CARRIES THE RESOLVER\'S WHOLE PREDICATE — not just the id', async () => {
    // RULING #253. It was `WHERE "id" = $1` and nothing else, while every caller
    // reached it through a resolver scoped on `practiceId`, `deletedAt IS NULL`
    // and `archivedAt IS NULL`. So the guard re-asserted `status` on a row whose
    // TENANCY and LIFECYCLE it had not re-asserted: a visit soft-deleted or
    // archived inside the very window this lock exists for was still written to.
    //
    // ⚠️ A LOCK THAT RE-CHECKS ONE OF THREE PREDICATES IS NOT A RE-CHECK.
    //
    // Asserted on the QUERY ACTUALLY SENT and its bound parameters — not on the
    // source text. Ruling #251 retires source reading as proof of behaviour, and
    // what a caller hands the driver is behaviour.
    await insert();
    const call = lockedVisit.mock.calls[0];
    const sql = String((call[0] as { strings?: string[] }).strings?.join('?') ?? call[0]);
    const params = call.slice(1);

    expect(sql).toMatch(/FOR UPDATE/);
    expect(sql, 'the locked read does not re-assert tenancy').toMatch(/"practiceId"/);
    expect(sql, 'the locked read does not re-assert the soft-delete').toMatch(/"deletedAt"\s+IS NULL/);
    expect(sql, 'the locked read does not re-assert the archive').toMatch(/"archivedAt"\s+IS NULL/);
    // ⚠️ AND THE PRACTICE IS BOUND, not interpolated or defaulted — a predicate
    // naming the column while binding nothing would satisfy the three above.
    //
    // ⚠️ THE **VISIT'S** TENANT — RULING #267, AND THIS ARM'S TITLE MOVED WITH
    // IT. It used to say "the SESSION's practice, not the visit author's", and
    // that was the best available answer while the fixture had only two values.
    // With three, the honest one is neither: the lock re-asserts
    // `transcribe_visits."practiceId"`, the VISIT'S OWN tenant, which is the
    // same column the resolver filtered and the same value every attached row
    // is stamped with. One derivation, one source.
    //
    // ⚠️ IN PRODUCTION THIS EQUALS THE SESSION'S PRACTICE BY CONSTRUCTION —
    // `visitByIdScope` filters on this very column — so the change is invisible
    // on real data and the fixture is deliberately built so it is NOT. A test
    // that reproduces the coincidence cannot see the code resting on it.
    //
    // Binding the AUTHOR's practice (`author-practice-9`) would re-assert the
    // right column with the wrong value — not a narrower check, a different
    // one — and it fails CLOSED, telling the doctor their visit is no longer
    // available.
    expect(
      params,
      'the locked read did not bind the visit id and the SESSION practice the ' +
        'resolver filtered with',
    ).toEqual([VISIT, 'visit-tenant-7']);
    expect(
      params,
      'the lock bound the visit AUTHOR practice — a different column from the ' +
        'one it filters',
    ).not.toContain('author-practice-9');
  });

  it('⚠️ THE WRITE HAPPENS ON THE **LOCKED** CONNECTION — kills `tx.` -> `prisma.`', async () => {
    // ROUND FIVE, AND IT WAS A FALSE GREEN OF THE HARNESS, NOT OF THE DOOR.
    // `$transaction` used to hand the callback the same client object, so
    // rewriting `tx.templateTwinFieldOverride.upsert` to
    // `prisma.templateTwinFieldOverride.upsert` was 97/97 green — a change that
    // takes the write out of the transaction and out from under the lock, while
    // every existing arm (including the two above, which only read the SQL
    // text) keeps passing. The lock would still be taken, still block, and
    // guard nothing.
    //
    // ⚠️ THE SQL-TEXT ARMS ABOVE CANNOT SEE THIS BY CONSTRUCTION. They assert
    // the statement SAYS `FOR UPDATE`; this asserts the statement and the write
    // are on ONE connection, which is the only thing that makes it a lock.
    const res = await insert();
    expect(res.ok).toBe(true);
    expect(onTx.queryRaw, 'the FOR UPDATE re-read ran OUTSIDE the transaction').toBe(true);
    expect(
      onTx.upsert,
      'the override was written on the top-level client, NOT the transactional ' +
        'one — the FOR UPDATE above locks a row this write never touches',
    ).toBe(true);
  });

  it('REFUSES when the visit was SIGNED while the form was being checked', async () => {
    lockedVisit.mockResolvedValue([{ status: 'SIGNED', signedAt: new Date() }]);
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/signed while your form was being checked/);
    expect(overrideUpsert, 'a row was written onto a signed visit').not.toHaveBeenCalled();
    expect(audit, 'an audit row claims a doctor act on a signed record').not.toHaveBeenCalled();
  });

  it('⚠️ BOTH SPELLINGS — `signedAt` alone is enough, even with status still READY', async () => {
    // The door says `status === 'SIGNED'`, the offer says `signedAt`. They agree
    // in production today and the sign route sets both atomically — but a guard
    // that trusts that is resting on a coincidence it does not assert.
    lockedVisit.mockResolvedValue([{ status: 'READY', signedAt: new Date() }]);
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  // ⚠️ THE REFUSAL NAMES ITS OWN CAUSE — ROUND FIVE.
  // These two arms asserted only `ok === false`, so the door could give ALL of
  // its refusals one message and stay green. It did: a re-queued or deleted
  // visit was told "this visit was signed while your form was being checked",
  // which is FALSE, and false in the actionable direction — the doctor goes
  // looking for a signature that does not exist.
  //
  // ⚠️ A refusal that names the WRONG cause is worse than a vague one.
  it('REFUSES when the visit left READY in the window — and does NOT claim it was signed', async () => {
    lockedVisit.mockResolvedValue([{ status: 'PROCESSING', signedAt: null }]);
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
    expect(res.error).toMatch(/back into processing/);
    expect(
      res.error,
      'a re-queued visit was reported to the doctor as SIGNED',
    ).not.toMatch(/signed/i);
  });

  it('REFUSES when the visit vanished in the window — and does NOT claim it was signed', async () => {
    lockedVisit.mockResolvedValue([]);
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
    expect(res.error).toMatch(/no longer available/);
    expect(
      res.error,
      'a deleted visit was reported to the doctor as SIGNED',
    ).not.toMatch(/signed/i);
  });

  it('⚠️ THE THREE CAUSES GIVE THREE DIFFERENT MESSAGES — no two collide', async () => {
    const seen = new Map<string, string>();
    for (const [cause, row] of [
      ['signed', [{ status: 'SIGNED', signedAt: new Date() }]],
      ['not_ready', [{ status: 'PROCESSING', signedAt: null }]],
      ['gone', []],
    ] as const) {
      lockedVisit.mockResolvedValue(row);
      const res = await insert();
      expect(res.ok).toBe(false);
      seen.set(cause, res.error!);
    }
    expect(new Set(seen.values()).size, `two causes share one message: ${[...seen].map(([k, v]) => `${k}=${v}`).join(' | ')}`).toBe(3);
  });

  it('⚠️ THE CONTROL — still READY at the write, so it WRITES', async () => {
    // Without this the four arms above pass for a door that refuses everything.
    lockedVisit.mockResolvedValue([{ status: 'READY', signedAt: null }]);
    const res = await insert();
    expect(res.ok, res.error).toBe(true);
    expect(overrideUpsert).toHaveBeenCalledTimes(1);
  });
});

describe('ROUND FOUR — the door judges the POST-write fill, not the pre-write one', () => {
  // ⚠️ THE DEFECT THIS CLOSES WAS FOUND BY TWO INDEPENDENT LENSES, AND IT IS
  // CLINICAL-HARM. The pre-write fill is computed from the rows in the database,
  // so it cannot see the row the door is about to add. An insert onto a
  // `rowPrototype` narrative_text field (writer stores a SCALAR, the validator
  // demands a ROW ARRAY) or onto a `laterality: 'required'` mapping makes
  // `finalizeTemplateTwinFill` return `render: null` for the WHOLE fill — the
  // offer returns `miss('no_render')`, the surface draws no panel, and WITH NO
  // PANEL THERE IS NO UNDO BUTTON. The row is permanent and the document never
  // renders again.
  //
  // These arms drive the REAL action and separate the two fills by the one
  // thing that differs between them: whether `simulateOverrides` is present.

  it('⚠️ NON-VACUITY — the door really does drive a SECOND fill, carrying the pending row', async () => {
    await insert();
    const calls = readAndPrepare.mock.calls.map((c) => c[0] as Record<string, unknown>);
    expect(calls.length, 'the door drove only one fill — the post-write check is absent').toBe(2);
    expect(calls[0].simulateOverrides, 'the FIRST fill must be the real, pre-write state').toBeUndefined();
    // ⚠️ `expect.any(String)` WAS THE HOLE — ROUND FIVE.
    //
    // The simulated row's text was pinned only as "a string", so the door could
    // VALIDATE one text and WRITE another with every gate green. The second
    // fill is the thing that decides whether the row is admissible; if it judges
    // text A and the upsert stores text B, the whole post-write simulation is
    // answering about a document that will never exist.
    //
    // So it is pinned three ways: to the field's OWN scaffoldText, to the exact
    // value the door actually upserts, and by requiring the two to be equal.
    expect(calls[1].simulateOverrides).toEqual([
      {
        fieldId: FIELD,
        overrideKind: 'scaffold_default',
        insertedText: SCAFFOLDED.scaffoldText,
        selectedOptionOrdinal: null,
      },
    ]);

    const written = (overrideUpsert.mock.calls[0][0] as {
      create: { insertedText: string };
    }).create.insertedText;
    expect(
      (calls[1].simulateOverrides as { insertedText: string }[])[0].insertedText,
      'the door validated one text and wrote another — the simulation judged a ' +
        'document that will never exist',
    ).toBe(written);
    expect(written).toBe(SCAFFOLDED.scaffoldText);
  });

  it('the two fills differ ONLY by the pending row — a drifted second copy would show here', async () => {
    await insert();
    const [a, b] = readAndPrepare.mock.calls.map((c) => ({ ...(c[0] as Record<string, unknown>) }));
    delete (b as Record<string, unknown>).simulateOverrides;
    expect(b).toEqual(a);
  });

  it('REFUSES when the write would make the document unrenderable — and writes NOTHING', async () => {
    // renders today; would not render with the pending row
    readAndPrepare.mockImplementation((input: Record<string, unknown>) =>
      Promise.resolve(
        input.simulateOverrides
          ? { prepared: { render: null, manifest: { fields: [resolution()] } } }
          : manifest(resolution()),
      ),
    );
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/would stop your form from being produced/);
    expect(overrideUpsert, 'a row was written for an insert that breaks the document').not.toHaveBeenCalled();
    expect(audit, 'an audit row asserts a doctor act that did not happen').not.toHaveBeenCalled();
  });

  it('⚠️ THE CONTROL — the SAME refusal path admits when the post-write fill DOES render', async () => {
    // Identical wiring, opposite answer. Without this the arm above passes for
    // any door that refuses everything.
    readAndPrepare.mockImplementation(() => Promise.resolve(manifest(resolution())));
    const res = await insert();
    expect(res.ok, res.error).toBe(true);
    expect(overrideUpsert).toHaveBeenCalledTimes(1);
  });
});

describe('#204 — the door consults the PER-VISIT resolution', () => {
  it('⚠️ NON-VACUITY FIRST — on a blank, unomitted visit the door ADMITS and writes', async () => {
    const res = await insert();
    expect(res.ok, res.error).toBe(true);
    expect(overrideUpsert).toHaveBeenCalledTimes(1);
    expect(audit).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'DEFAULT_INSERTED_BY_DOCTOR' }),
    );
  });

  it('⚠️ THE WRITE PAYLOAD IS ASSERTED — not merely that a write happened', async () => {
    // ⚠️ ROUND THREE: the door's upsert payload was never checked, so
    // `overrideKind: 'scaffold_default'` -> `'option_choice'` stayed GREEN — and
    // undo's deleteMany filters on that exact kind, so the doctor could not
    // remove a default they had just inserted and the row stayed an input to
    // every future fill. `insertedText -> ''` and a constant `overriddenBy`
    // were green too.
    await insert();
    expect(overrideUpsert).toHaveBeenCalledTimes(1);
    const arg = overrideUpsert.mock.calls[0][0] as {
      where: unknown;
      create: Record<string, unknown>;
      update: Record<string, unknown>;
    };
    expect(arg.where).toEqual({ visitId_fieldId: { visitId: VISIT, fieldId: FIELD } });
    expect(arg.create).toMatchObject({
      visitId: VISIT,
      fieldId: FIELD,
      overrideKind: 'scaffold_default',
      insertedText: 'No acute findings.',
      overriddenBy: 'requester-1',
    });
    // The UPDATE arm must clear the option columns, or the row satisfies
    // neither arm of the kind-shape CHECK and the database refuses it.
    expect(arg.update).toMatchObject({
      overrideKind: 'scaffold_default',
      insertedText: 'No acute findings.',
      selectedOptionOrdinal: null,
      optionValue: null,
    });
  });

  it('⚠️ INSERT THEN UNDO — the round trip the two doors must agree on', async () => {
    // ⚠️ ROUND THREE: `undoScaffoldDefaultAction` had ZERO executable coverage
    // anywhere in the repo, which made C3 ("undo needs no gate") unfalsifiable.
    // This drives the real pair against a store that honours the where clause,
    // so a mismatched `overrideKind` on either side reds here.
    const rows: Array<Record<string, unknown>> = [];
    overrideUpsert.mockImplementation(async (a: {
      where: { visitId_fieldId: { visitId: string; fieldId: string } };
      create: Record<string, unknown>;
    }) => {
      rows.push({ ...a.create, ...a.where.visitId_fieldId });
      return a.create;
    });
    overrideDeleteMany.mockImplementation(async (a: { where: Record<string, unknown> }) => {
      const before = rows.length;
      for (let i = rows.length - 1; i >= 0; i--) {
        if (Object.entries(a.where).every(([k, v]) => rows[i][k] === v)) rows.splice(i, 1);
      }
      return { count: before - rows.length };
    });

    const ins = await insert();
    expect(ins.ok, ins.error).toBe(true);
    expect(rows).toHaveLength(1);

    const mod = await import('../set-template-control');
    const undone = await mod.undoScaffoldDefaultAction(VISIT, FIELD);
    expect(
      undone.ok,
      `undo could not find the row the insert wrote: ${undone.error}`,
    ).toBe(true);
    expect(rows, 'the row survived the undo').toHaveLength(0);
  });

  it('⚠️ THE RULED CASE — the omit FIRED on this visit, so the door REFUSES', async () => {
    readAndPrepare.mockResolvedValue(manifest(resolution({ reasonCode: 'omitted_unsupported_default' })));
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert, 'the door wrote an override the offer would not have shown').not.toHaveBeenCalled();
    expect(audit, 'an audit row asserting a claim the doctor was never shown').not.toHaveBeenCalled();
  });

  it('⚠️ AND ONLY ON THIS VISIT — the SAME field with the omit NOT fired is admitted', async () => {
    // The pair is the point: identical field, identical mapping, differing ONLY
    // by the per-visit reasonCode. Round one refused BOTH (a confirm-time
    // property answering a per-visit question); round two admitted both.
    readAndPrepare.mockResolvedValue(manifest(resolution({ reasonCode: 'no_supporting_evidence' })));
    await expect(insert()).resolves.toMatchObject({ ok: true });
  });

  it('⚠️ A RE-INSERT OVER THIS DOCTOR’S OWN DEFAULT IS STILL ADMITTED', async () => {
    // The offer keeps such a field listed via `inserted ||`, so a door gating on
    // `scaffoldDefaultOfferable` alone would refuse a state the panel offers.
    readAndPrepare.mockResolvedValue(manifest(resolution({
              status: 'supported',
              value: 'No acute findings.',
              reasonCode: 'clinician_scaffold_default',
            })));
    await expect(insert()).resolves.toMatchObject({ ok: true });
  });

  it('⚠️ A DICTATED FIELD IS NOT BLANK, so the door refuses', async () => {
    readAndPrepare.mockResolvedValue(manifest(resolution({ status: 'supported', value: 'Dictated text.', reasonCode: 'evidence_supported' })));
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });
});

describe("#267 — the CHART owns the note: one tenant, from the visit's own row", () => {
  it('⚠️ the STORED row carries the VISIT tenant — not the author, not the requester', async () => {
    // ⚠️ THIS IS `SF-1`, AND IT IS THE HALF THE SPLIT FIXTURE DID NOT CLOSE.
    // `8cc89b7c` fixed the value handed to the LOCK and #260 ratified it; the
    // value the ROW IS STAMPED WITH was left reading `visit.user.practiceId`.
    // Three sources for one fact, two of which agree on production data.
    await insert();
    expect(overrideUpsert).toHaveBeenCalledTimes(1);
    const created = (overrideUpsert.mock.calls[0][0] as { create: { practiceId: string } }).create;
    expect(
      created.practiceId,
      'the override row is stamped with a practice that is not the visit tenant',
    ).toBe('visit-tenant-7');
    // POSITIVE CONTROL ON THE FIXTURE ITSELF: all three values must be
    // DISTINCT, or this assertion passes by coincidence rather than by the code
    // being right. #267's own words: a fixture that gives two distinct things
    // the same value cannot witness them being confused.
    expect(new Set(['prac-1', 'visit-tenant-7', 'author-practice-9']).size).toBe(3);
  });

  it("⚠️ the WRITE and the sign-time FREEZE agree — the defect was that they did not", async () => {
    // ⚠️ THE ARM THAT MAKES `SF-1` UNABLE TO RECUR, and it is deliberately
    // about the AGREEMENT rather than about either value. `sign-freeze.ts`
    // reads `{ visitId, practiceId }` where `practiceId` is the value the SIGN
    // route was scoped with — the visit's tenant. If the write is ever stamped
    // with anything else, the freeze computes `overridesSha256` over an empty
    // set and freezes a document without the doctor's own inserted default,
    // silently, on a signed clinical record.
    //
    // Asserted against the READER'S predicate rather than against a literal:
    // a literal here would be a fourth restatement of the same fact, and this
    // whole ruling exists because there were three.
    const freeze = readFileSync(
      path.join(__dirname, '..', '..', 'lib', 'template-twin', 'sign-freeze.ts'),
      'utf8',
    );
    expect(
      freeze,
      'sign-freeze no longer scopes the override read by { visitId, practiceId }',
    ).toContain('where: { visitId, practiceId }');

    await insert();
    const created = (overrideUpsert.mock.calls[0][0] as { create: { practiceId: string } }).create;
    // The lock's bound tenant IS the freeze's tenant — same column, same value.
    const lockParams = lockedVisit.mock.calls[0].slice(1);
    expect(
      created.practiceId,
      'the row is stamped with a practice the lock did not assert — the SF-1 shape',
    ).toBe(lockParams[1]);
  });
});

describe('#204 — the fill is asked the SAME question the preview asks', () => {
  it('⚠️ THE VISIT’S OWN DOCTOR, not the requester', async () => {
    await insert();
    // ⚠️ TWO FILLS NOW, NOT ONE — AND THE COUNT IS STILL ASSERTED. Round four
    // added a POST-write simulation, so the door drives the fill twice: once on
    // the real state, once with the pending row merged in. This arm was written
    // when there was one, and it is CORRECTED rather than loosened: a bare
    // `toHaveBeenCalled()` would stop noticing a third fill appearing, and the
    // whole point of the original assertion was that the door asks the preview's
    // question exactly once per state.
    expect(readAndPrepare).toHaveBeenCalledTimes(2);
    // ⚠️ EVERY ARGUMENT THAT DECIDES THE ANSWER, NOT A CONVENIENT SUBSET.
    // Round three: this block checked 6 of 12 and none of the four that move
    // the outcome. Blanking `contextText`, `entities`, the `inputMode` ternary
    // or `visitDate` each stayed GREEN across all 5812 tests and tsc — while in
    // production an empty transcript yields no facts, so
    // `unmentionedScaffold = conceptUnmatched && reason === undefined &&
    // facts.length > 0` is false and `omitted_unsupported_default` is NEVER
    // emitted. The door would then admit every omit field it exists to refuse,
    // silently, because it asked a different question from the preview.
    const call = readAndPrepare.mock.calls[0][0] as Record<string, unknown>;
    expect(call).toMatchObject({
      visitId: VISIT,
      doctorId: 'author-1',
      // ⚠️ THE **VISIT'S TENANT** — RULING #267, AND THIS IS THE THIRD ANSWER
      // THIS ONE LINE HAS HAD. It was `prac-1` while the fixture conflated
      // everything; then `author-practice-9` when the split separated the
      // session from the author; it is `visit-tenant-7` now, because the
      // question was never "whose practice is this?" but "what does this row
      // belong to?", and the answer to that is the CHART.
      //
      // ⚠️ THE PREVIOUS ANSWER WAS THE `SF-1` DEFECT, and it was measured: the
      // fill and the preview scoped by the AUTHOR's practice while
      // `sign-freeze.ts` reads the override table with the TENANT's. For a
      // locum — practice B seeing practice A's patient, which the schema names
      // as the reason this column exists — the doctor inserted a default,
      // watched it appear in the preview, and signed a document without it.
      //
      // ⚠️ THE **ACTOR** IS A DIFFERENT AXIS AND HAS NOT MOVED: `doctorId` is
      // still the visit's own doctor rather than the requester, one line above.
      // Tenant and actor are two questions, and this arm's title — "the visit's
      // own doctor, not the requester" — is about the second. #267 is about the
      // first, and it says: not the author either. The visit's.
      practiceId: 'visit-tenant-7',
      noteTemplateId: 'tpl-1',
      noteTemplateVersion: 3,
      generatedNote: 'A note.',
      inputMode: 'dictation',
      contextText: 'transcript',
      resolverModelVersion: null,
    });
    // ⚠️ THIS ASSERTION WAS VACUOUS ON ITS FIRST WRITING —
    // `toBe(x ?? call.entities)` is trivially true whenever `x` is undefined,
    // and blanking `entities` in the door stayed GREEN. It now compares against
    // the distinctive object the fixture primed.
    expect(call.entities, 'the resolver was fed a different entity set').toEqual(ENTITIES);
    expect(call.visitDate, 'visitDate must be the ENCOUNTER date, not now').toEqual(
      new Date('2026-09-06T00:00:00Z'),
    );
    expect(call.validationNow, 'validationNow must be supplied').toBeInstanceOf(Date);
    // The door must not silently stop passing one of these.
    for (const k of ['inputMode', 'contextText', 'entities', 'visitDate', 'validationNow']) {
      expect(Object.keys(call), `${k} is no longer passed to the fill`).toContain(k);
    }
  });

  it('⚠️ FAIL-CLOSED — a throwing fill REFUSES rather than writing', async () => {
    readAndPrepare.mockRejectedValue(new Error('storage down'));
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert, 'a write went through on a resolution nobody obtained').not.toHaveBeenCalled();
    expect(audit).not.toHaveBeenCalled();
  });

  it('⚠️ NO DOCUMENT, NO WRITE — a fill that rendered nothing is refused', async () => {
    // Round three, two lenses: one blocking validation issue anywhere in the
    // fill makes `render` null for the WHOLE document. The offer then shows no
    // panel at all — so there is no offer, no field, and no Undo button — while
    // the door wrote the row and the audit claim anyway.
    readAndPrepare.mockResolvedValue({
      prepared: { render: null, manifest: { fields: [resolution()] } },
    });
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert, 'a row was written for a document that does not render').not.toHaveBeenCalled();
    expect(audit).not.toHaveBeenCalled();
  });

  it('⚠️ NOT READY, NOT WRITABLE — the eight in-flight statuses are refused', async () => {
    // The offer refuses every status but READY (and signed, which the door
    // refuses outright). Reachable in ordinary use: the manual retry route
    // sets a READY visit back to QUEUED and LEAVES soapFinal in place, so the
    // door's fill would resolve against a stale note.
    for (const status of [
      'QUEUED', 'TRANSCRIBING', 'EXTRACTING', 'DRAFTING',
      'CRITIQUING', 'POLISHING', 'AUTOMATING', 'FAILED',
    ]) {
      vi.clearAllMocks();
      primeVisit({ status });
      primeTemplate();
      defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: 'assessment' } });
      readAndPrepare.mockResolvedValue(manifest(resolution()));
      const res = await insert();
      expect(res.ok, `status ${status} was admitted`).toBe(false);
      expect(overrideUpsert, `status ${status} wrote an override row`).not.toHaveBeenCalled();
      expect(audit, `status ${status} emitted an audit claim`).not.toHaveBeenCalled();
    }
  });

  it('⚠️ NO NOTE, NO FILL — the door refuses before paying for one', async () => {
    primeVisit({ soapFinal: null });
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(readAndPrepare, 'a fill was computed for a visit with no note').not.toHaveBeenCalled();
  });
});

describe('the static guards — each REFUSES, and each is now driven', () => {
  it('a field the compiler did not mark scaffolded', async () => {
    primeTemplate(irWith({ ...SCAFFOLDED, scaffolded: false }));
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('a scaffolded field carrying only whitespace', async () => {
    primeTemplate(irWith({ ...SCAFFOLDED, scaffoldText: '   ' }));
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('⚠️ A CONSTRAINED CONTROL — free text into one BLOCKS the whole document', async () => {
    primeTemplate(irWith(SCAFFOLDED, SELECT.fieldId as string));
    // ⚠️ TARGETS THE SELECT FIELD. Driving the narrative field here would still
    // refuse — on the `scaffolded` guard, because only SELECT was mutated — and
    // the arm would pass having never exercised the kind guard at all.
    const res = await insert(SELECT.fieldId as string);
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('a field with no clinical concept — the fill declines it forever', async () => {
    defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: null } });
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ THESE TWO ARMS EXIST BECAUSE THE OBVIOUS ONES COULD NOT RED, AND THE
  // REASON IS WORTH STATING RATHER THAN PAPERING OVER.
  //
  // `scaffoldDefaultOfferable` re-checks the SAME three properties the door's
  // static guards check — `scaffolded`, non-empty `scaffoldText`, and an
  // insertable `kind`. So deleting the door's own guard does NOT change the
  // decision: the request falls through to the shared predicate, which refuses
  // it anyway. Measured — deleting either guard left 91 tests green.
  //
  // That is defence in depth, not dead code. What it costs is the DOCTOR'S
  // MESSAGE: the door's guards say "has no default of yours to insert" and "is
  // a fixed control on this form", while the shared fallback can only say "is
  // not blank on this visit" — which, for a field that was never scaffolded, is
  // simply untrue.
  //
  // ⚠️ SO THE ASSERTION IS THAT THE ANSWERS DIFFER, NOT WHAT THEY SAY. Pinning
  // the exact wording would be a literal-spelling assertion by another route,
  // and #204 forbids that class. Two refusals collapsing to ONE message is the
  // observable consequence of the guard being gone.
  it('⚠️ THE DOOR ANSWERS IN ITS OWN WORDS — a never-scaffolded field is not "not blank"', async () => {
    primeTemplate(irWith({ ...SCAFFOLDED, scaffolded: false }));
    const notScaffolded = await insert();

    vi.clearAllMocks();
    primeVisit();
    primeTemplate();
    defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: 'assessment' } });
    readAndPrepare.mockResolvedValue(manifest(resolution({ status: 'supported', value: 'Dictated.', reasonCode: 'evidence_supported' })));
    const notBlank = await insert();

    expect(notScaffolded.ok).toBe(false);
    expect(notBlank.ok).toBe(false);
    expect(
      notScaffolded.error,
      'both refusals collapsed to one message — the door is answering from the shared predicate, not its own guard',
    ).not.toBe(notBlank.error);
  });

  it('⚠️ AND A CONSTRAINED CONTROL GETS ITS OWN ANSWER TOO', async () => {
    primeTemplate(irWith(SCAFFOLDED, SELECT.fieldId as string));
    const constrained = await insert(SELECT.fieldId as string);

    vi.clearAllMocks();
    primeVisit();
    primeTemplate();
    defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: 'assessment' } });
    readAndPrepare.mockResolvedValue(manifest(resolution({ status: 'supported', value: 'Dictated.', reasonCode: 'evidence_supported' })));
    const notBlank = await insert();

    expect(constrained.ok).toBe(false);
    // ⚠️ COMPARE THE REASONS, NOT THE SENTENCES. Every refusal is
    // `${label} <reason>`, and these two arms necessarily use DIFFERENT fields —
    // a constrained control and a narrative one — so the raw strings always
    // differ by the label alone. An earlier version of this arm compared them
    // directly and passed for exactly that reason, with the guard deleted:
    // "Address is not blank..." vs "GSV at the SFJ is not blank...".
    // A vacuous assertion that reads like a real one.
    const reason = (r: { error?: string; label?: string }) =>
      (r.error ?? '').replace(r.label ?? '', '').trim();
    expect(
      reason(constrained),
      'the kind refusal collapsed into the generic reason — the door lost its own guard',
    ).not.toBe(reason(notBlank));
  });

  it('a SIGNED visit is refused before anything else — BY THE SIGN-FREEZE GUARD', async () => {
    // ⚠️ THIS ARM USED TO PASS WITH THE SIGN-FREEZE GUARD DELETED, and round
    // four caught it. It asserted only that the door refused and did no fill —
    // which the READY guard, added a commit later and sitting BEFORE the fill,
    // satisfies on its own. Measured: deleting `if (visit.status === 'SIGNED')`
    // left the file 37/37 GREEN. The arm named one guard and watched another.
    //
    // The two produce DIFFERENT messages, and that is the discriminator:
    //   sign-freeze  "This visit is signed — its document is frozen…"
    //   READY        "<label> cannot take a default while this visit is still
    //                 being prepared."
    // A doctor told the wrong one of those is told something false about their
    // own record, so the message is worth asserting for its own sake as well.
    primeVisit({ status: 'SIGNED' });
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/signed .* frozen/);
    expect(res.error).not.toMatch(/still being prepared/);
    expect(readAndPrepare).not.toHaveBeenCalled();
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('⚠️ THE CONTROL — a NON-signed, non-READY visit gets the OTHER message', async () => {
    // Without this the arm above passes for a door that emits the sign-freeze
    // message for every non-READY state, which would be the same defect
    // pointing the other way.
    primeVisit({ status: 'PROCESSING' });
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/still being prepared/);
    expect(res.error).not.toMatch(/signed .* frozen/);
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ROUND FIVE — THE UNDO DOOR WAS THE THIRD WRITER, AND IT HAD NO LOCK AT ALL.
  // Round four closed the sign window on the INSERT door. The undo door stayed
  // a bare `deleteMany` reached after a status read, a second query and a full
  // IR parse — a window seconds wide, on a delete.
  // ══════════════════════════════════════════════════════════════════════════
  it('⚠️ UNDO WRITES ON THE **LOCKED** CONNECTION', async () => {
    const mod = await import('../set-template-control');
    overrideDeleteMany.mockResolvedValue({ count: 1 });
    const res = await mod.undoScaffoldDefaultAction(VISIT, FIELD);
    expect(res.ok).toBe(true);
    expect(onTx.queryRaw, 'the FOR UPDATE re-read ran OUTSIDE the transaction').toBe(true);
    expect(onTx.deleteMany, 'the delete ran on the top-level client, not the locked one').toBe(true);
  });

  it('⚠️ UNDO REFUSES when the visit was SIGNED in its window', async () => {
    lockedVisit.mockResolvedValue([{ status: 'SIGNED', signedAt: new Date() }]);
    overrideDeleteMany.mockResolvedValue({ count: 1 });
    const mod = await import('../set-template-control');
    const res = await mod.undoScaffoldDefaultAction(VISIT, FIELD);
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/signed while your form was being checked/);
    expect(
      overrideDeleteMany,
      'the doctor\'s row was deleted against a record that had just been signed',
    ).not.toHaveBeenCalled();
  });

  it('⚠️ …and a REFUSED undo is distinguishable from "nothing was inserted"', async () => {
    // Two different facts, and conflating them tells the doctor the wrong thing:
    // `count === 0` means there was no row; the lock's refusal means there WAS
    // one and the visit moved underneath. Round five filed the sibling of this
    // as its own finding — four causes behind one message.
    lockedVisit.mockResolvedValue([{ status: 'SIGNED', signedAt: new Date() }]);
    const mod = await import('../set-template-control');
    const refused = await mod.undoScaffoldDefaultAction(VISIT, FIELD);

    lockedVisit.mockResolvedValue([{ status: 'READY', signedAt: null }]);
    overrideDeleteMany.mockResolvedValue({ count: 0 });
    const absent = await mod.undoScaffoldDefaultAction(VISIT, FIELD);

    expect(refused.ok).toBe(false);
    expect(absent.ok).toBe(false);
    expect(refused.error).not.toBe(absent.error);
    expect(absent.error).toMatch(/not currently inserted/);
  });
});
