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

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { findFirst: (...a: unknown[]) => visitFindFirst(...a) },
    noteTemplate: { findFirst: (...a: unknown[]) => templateFindFirst(...a) },
    templateTwinFieldOverride: {
      upsert: (...a: unknown[]) => overrideUpsert(...a),
      deleteMany: (...a: unknown[]) => overrideDeleteMany(...a),
    },
    templateTwinFieldDefinition: { findUnique: (...a: unknown[]) => defFindUnique(...a) },
  },
}));
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
    user: { practiceId: 'prac-1' },
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
  vi.clearAllMocks();
  primeVisit();
  primeTemplate();
  defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: 'assessment' } });
  readAndPrepare.mockResolvedValue(manifest(resolution()));
  overrideUpsert.mockResolvedValue({});
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

describe('#204 — the fill is asked the SAME question the preview asks', () => {
  it('⚠️ THE VISIT’S OWN DOCTOR, not the requester', async () => {
    await insert();
    expect(readAndPrepare).toHaveBeenCalledTimes(1);
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
      practiceId: 'prac-1',
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

  it('a SIGNED visit is refused before anything else', async () => {
    primeVisit({ status: 'SIGNED' });
    const res = await insert();
    expect(res.ok).toBe(false);
    expect(readAndPrepare).not.toHaveBeenCalled();
    expect(overrideUpsert).not.toHaveBeenCalled();
  });
});
