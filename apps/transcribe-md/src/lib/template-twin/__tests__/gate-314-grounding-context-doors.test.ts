// ============================================================================
// #314 v2 — ONE GROUNDING CONTEXT, FIVE READERS.
// ----------------------------------------------------------------------------
// D6, the widest defect in v1: the worker grounded a text_notes visit's total
// against `rawTextInput` (what L3 read), while every re-fill door passed
// `visit.transcriptText ?? ''` — and `transcriptText` is NULL for every typed
// visit (55 of 58 in production, 2026-09-10). So the preview, the sign-time
// re-fill, the export and a control edit would all BLANK a total the worker
// filled.
//
// THE ARM, AND HOW FAR IT REACHES — stated, not implied:
//   · THE DOORS ARE DRIVEN. Each of the four real door functions runs against a
//     prisma mock that HONOURS `select`: a column the door did not select is
//     absent from the row it gets back, exactly as with the real client. So a
//     door that forgets `rawTextInput: true` gets '' and the arm reds. The fill
//     engine is mocked and its input captured — the arm is about what the door
//     HANDS the engine.
//   · THE WORKER'S L3 CONTEXT IS REAL: `runLayer3ExtractEntities` runs with only
//     the model call mocked, and its returned `contextText` is the text L3 read.
//   · THE WORKER ITSELF IS NOT DRIVEN — `worker.ts` is a BullMQ process with no
//     seam. Its fill context is the same `groundingContextFor` call, asserted on
//     its SOURCE below, and fed here with the values the worker holds at that
//     line. That is a string read, and it is labelled as one.
// ============================================================================
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => {
  /** A prisma `select` applied to a full row — what the real client returns. */
  const projectRow = (
    row: Record<string, unknown>,
    select: Record<string, unknown>,
  ): Record<string, unknown> => {
    const out: Record<string, unknown> = {};
    for (const [key, spec] of Object.entries(select)) {
      if (spec === true) {
        if (key in row) out[key] = row[key];
        continue;
      }
      if (spec && typeof spec === 'object' && 'select' in spec) {
        const child = row[key];
        out[key] =
          child == null
            ? child
            : projectRow(child as Record<string, unknown>, (spec as { select: Record<string, unknown> }).select);
      }
    }
    return out;
  };
  return {
    projectRow,
    row: null as Record<string, unknown> | null,
    manifestFindFirst: vi.fn(),
    compiledFindUnique: vi.fn(),
    templateFindFirst: vi.fn(),
    defFindUnique: vi.fn(),
    processFill: vi.fn(),
    readAndPrepare: vi.fn(),
    modelComplete: vi.fn(),
  };
});

vi.mock('@meddoc/db', () => {
  const db: Record<string, unknown> = {
    transcribeVisit: {
      findFirst: async (args: { select?: Record<string, unknown> }) =>
        h.row && args?.select ? h.projectRow(h.row, args.select) : null,
      update: async () => ({}),
    },
    templateTwinFillManifest: { findFirst: (...a: unknown[]) => h.manifestFindFirst(...a) },
    templateTwinFieldOverride: {
      findMany: async () => [],
      upsert: async () => ({}),
      deleteMany: async () => ({ count: 0 }),
    },
    templateTwinCompiledVersion: { findUnique: (...a: unknown[]) => h.compiledFindUnique(...a) },
    noteTemplate: { findFirst: (...a: unknown[]) => h.templateFindFirst(...a) },
    templateTwinFieldDefinition: { findUnique: (...a: unknown[]) => h.defFindUnique(...a) },
    $queryRaw: async () => [{ status: 'READY', signedAt: null }],
  };
  db.$transaction = (fn: (client: unknown) => unknown) => fn(db);
  return { default: db };
});
vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: (...a: unknown[]) => h.modelComplete(...a) } };
});
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
vi.mock('@/lib/auth', () => ({
  requireSession: async () => ({ user: { id: 'requester-1', practiceId: 'prac-1' } }),
}));
vi.mock('@/lib/practice-scope', () => ({
  visitByIdScope: (id: string, practiceId: string) => ({ id, practiceId }),
  asPracticeId: (p: string) => p,
}));
vi.mock('@/lib/docx-preview/fill-cache', () => ({
  readCachedFill: async () => null,
  writeCachedFill: async () => undefined,
  invalidateVisitFills: async () => undefined,
}));
vi.mock('@/lib/docx-preview/convert', () => ({
  convertDocxToPdf: async () => ({ pdf: null, reason: 'mocked' }),
}));
vi.mock('@/lib/docx-generator', () => ({ generateVisitDocx: async () => Buffer.from('') }));
vi.mock('@/lib/visit-export-server', () => ({ loadVisitExportData: async () => null }));
vi.mock('@/lib/template-twin/fill-engine', () => ({
  processTemplateTwinVisit: (...a: unknown[]) => h.processFill(...a),
  readAndPrepareTemplateTwinFill: (...a: unknown[]) => h.readAndPrepare(...a),
  TemplateTwinFillError: class TemplateTwinFillError extends Error {},
}));

import { compileTemplateDocx } from '@/lib/note-template-docx';
import { previewVisitDocumentAction } from '@/actions/preview-visit-document';
import { insertScaffoldDefaultAction } from '@/actions/set-template-control';
import { runLayer3ExtractEntities } from '@/worker/layers/03-extract-entities';
import { projectEncounterFacts } from '../encounter-facts';
import { groundingContextFor } from '../grounding-context';
import { loadOrComputeNativeTemplateDocxForVisit } from '../native-export';
import { freezeNativeManifestForSigning } from '../sign-freeze';

const VISIT = 'visit-314';
const PRACTICE = 'prac-1';
const TOTAL_QUOTE = 'Total time 45 minutes.';
const ENTITIES = { total_time_minutes: { minutes: 45, evidence_quote: TOTAL_QUOTE } };
const EMPTY_BUT_VALID = {
  chief_complaint: null,
  hpi: null,
  past_medical_history: [],
  medications: [],
  allergies: [],
  family_history: [],
  social_history: {},
  ros: [],
  exam_findings: [],
  tests_mentioned: [],
  assessment_discussed: [],
  plan_discussed: [],
};

// ⚠️ LEADING AND TRAILING WHITESPACE ON PURPOSE: L3 trims, so a door that did
// not would ground against a different string. And the typed total is REFLOWED
// across a line break, the shape v1's `includes()` refused.
const TYPED = '  Chief complaint: dysphagia.\nTotal time\n45 minutes.\nFollow up in two weeks.\n';
const DICTATED = '  Patient seen for dysphagia. Total time 45 minutes. Follow up in two weeks. ';

type Mode = 'text_notes' | 'voice_dictation';
function rowFor(mode: Mode): Record<string, unknown> {
  return {
    id: VISIT,
    status: 'READY',
    signedAt: null,
    userId: 'author-1',
    practiceId: PRACTICE,
    inputMode: mode,
    // ⚠️ NULL FOR A TYPED VISIT, AS IN PRODUCTION — the whole of D6.
    transcriptText: mode === 'text_notes' ? null : DICTATED,
    rawTextInput: mode === 'text_notes' ? TYPED : null,
    entities: ENTITIES,
    soapFinal: 'A note.',
    soapVersion: 2,
    noteTemplateId: 'tpl-1',
    noteTemplateVersion: 3,
    createdAt: new Date('2026-09-10T00:00:00Z'),
    frozenFillManifestId: null,
    deletedAt: null,
    archivedAt: null,
    user: { practiceId: PRACTICE },
    patient: { updatedAt: new Date('2026-09-01T00:00:00Z') },
  };
}

// The set-template-control door needs a CERTIFIED form with a scaffolded field
// to reach its fill. Compiled from the tracked BLANK fixture, one field marked
// scaffolded — the same construction gate-review-defaults-door-executable uses.
const BASE_IR = compileTemplateDocx(
  new Uint8Array(readFileSync(path.resolve(process.cwd(), '../../WM IOV Template.docx'))),
) as unknown as { fields: Array<Record<string, unknown>> };
const FIELD = BASE_IR.fields.find((f) => f.kind === 'narrative_text')!.fieldId as string;
const IR = {
  ...BASE_IR,
  fields: BASE_IR.fields.map((f) =>
    f.fieldId === FIELD ? { ...f, scaffolded: true, scaffoldText: 'No acute findings.' } : f,
  ),
};

/** What the WORKER hands the fill: the real L3 context, through the worker's own call. */
async function workerFillContext(row: Record<string, unknown>): Promise<string> {
  h.modelComplete.mockResolvedValueOnce({ ...EMPTY_BUT_VALID, ...ENTITIES });
  const base = { visitId: VISIT, practiceId: PRACTICE, userId: 'author-1' };
  const l3 =
    row.inputMode === 'text_notes'
      ? await runLayer3ExtractEntities({ ...base, mode: 'text', rawText: row.rawTextInput as string })
      : await runLayer3ExtractEntities({ ...base, mode: 'dictation', dictationText: row.transcriptText as string });
  // worker.ts, verbatim in shape (asserted on its source below): `rawTextInput`
  // from the job's visit row; `dictationTranscript` is the L1b transcript for a
  // dictation and null otherwise; the L3 context rides as the conversation text.
  const fill = groundingContextFor(
    {
      inputMode: row.inputMode as string,
      rawTextInput: row.rawTextInput as string | null,
      transcriptText: row.inputMode === 'voice_dictation' ? (row.transcriptText as string) : null,
    },
    { conversationTranscript: l3.contextText },
  );
  // The worker logs a divergence rather than trusting it; here it must not occur.
  expect(fill, 'the worker would log a grounding-context divergence').toBe(l3.contextText);
  return fill;
}

const contextOf = (call: unknown[] | undefined): unknown => (call?.[0] as { contextText?: unknown })?.contextText;

const DOORS: Array<[string, () => Promise<unknown>]> = [
  [
    'sign-freeze (the sign-time re-fill)',
    async () => {
      await freezeNativeManifestForSigning({ visitId: VISIT, practiceId: PRACTICE });
      expect(h.processFill, 'the freeze never reached its re-fill').toHaveBeenCalledTimes(1);
      return contextOf(h.processFill.mock.calls[0]);
    },
  ],
  [
    'native-export (the on-demand export fill)',
    async () => {
      await loadOrComputeNativeTemplateDocxForVisit(VISIT, PRACTICE);
      expect(h.processFill, 'the export never reached its fill').toHaveBeenCalledTimes(1);
      return contextOf(h.processFill.mock.calls[0]);
    },
  ],
  [
    'preview-visit-document (the pre-sign preview)',
    async () => {
      await previewVisitDocumentAction(VISIT, 'word');
      expect(h.readAndPrepare, 'the preview never reached its fill').toHaveBeenCalledTimes(1);
      return contextOf(h.readAndPrepare.mock.calls[0]);
    },
  ],
  [
    'set-template-control (a control edit)',
    async () => {
      await insertScaffoldDefaultAction(VISIT, FIELD);
      expect(h.readAndPrepare, 'the control edit never reached its fill').toHaveBeenCalled();
      return contextOf(h.readAndPrepare.mock.calls[0]);
    },
  ],
];

beforeEach(() => {
  vi.clearAllMocks();
  h.row = null;
  // The sign-freeze read carries the visit's fill columns (`entities`) and must
  // look STALE so the freeze re-fills. Every other manifest read — the export's
  // cached lookup, the freeze's post-fill re-read — finds nothing.
  h.manifestFindFirst.mockImplementation(async (args: { select?: { visit?: { select?: Record<string, unknown> } } }) => {
    const visitSelect = args?.select?.visit?.select;
    if (!h.row || !visitSelect || !('entities' in visitSelect)) return null;
    return {
      id: 'manifest-1',
      noteSha256: 'a-note-this-is-not',
      overridesSha256: null,
      updatedAt: new Date('2026-09-02T00:00:00Z'),
      visit: h.projectRow(h.row, visitSelect),
    };
  });
  h.compiledFindUnique.mockResolvedValue({ id: 'cv-1', certificationStatus: 'CERTIFIED', compiledDocumentIr: IR });
  h.templateFindFirst.mockResolvedValue({
    templateTwinCompiledVersion: { id: 'cv-1', certificationStatus: 'CERTIFIED', compiledDocumentIr: IR },
  });
  h.defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: 'assessment' } });
  h.processFill.mockResolvedValue(undefined);
  h.readAndPrepare.mockResolvedValue({ prepared: { render: null, manifest: { fields: [] } } });
});

const totalsAt = (mode: Mode, contextText: string) =>
  projectEncounterFacts({
    mode: mode === 'text_notes' ? 'text' : 'dictation',
    contextText,
    entities: ENTITIES as unknown as Parameters<typeof projectEncounterFacts>[0]['entities'],
  })
    .filter((f) => f.concept === 'total_time_minutes')
    .map((f) => f.value);

describe.each<Mode>(['text_notes', 'voice_dictation'])('#314 v2 · a %s visit — FOUR DOORS, ONE CONTEXT', (mode) => {
  it.each(DOORS)('%s grounds against exactly the text the worker grounded against', async (_door, drive) => {
    h.row = rowFor(mode);
    const worker = await workerFillContext(h.row);
    const door = await drive();
    expect(door, 'the door handed the fill a different text from the worker').toBe(worker);
    expect(door, 'NON-VACUITY: an empty context would also "match" an empty worker').not.toBe('');
    // …and so the worker's total survives every re-fill.
    expect(totalsAt(mode, door as string), 'the door would blank the total the worker filled').toEqual(['45']);
  });
});

describe('#314 v2 · D6 as it was, pinned', () => {
  it("⚠️ the OLD door expression, `transcriptText ?? ''`, is '' on a typed visit — and blanks the total", () => {
    const row = rowFor('text_notes');
    const old = (row.transcriptText as string | null) ?? '';
    expect(old).toBe('');
    expect(totalsAt('text_notes', old)).toEqual([]);
    // …while the same visit, grounded the v2 way, keeps it.
    expect(totalsAt('text_notes', groundingContextFor(row as never))).toEqual(['45']);
  });

  it('CONTROL — the select-honouring mock really withholds an unselected column', () => {
    const projected = h.projectRow(rowFor('text_notes'), { inputMode: true, transcriptText: true });
    expect(projected).not.toHaveProperty('rawTextInput');
    expect(groundingContextFor(projected as never)).toBe('');
  });
});

describe('#314 v2 · the shared rule itself', () => {
  it('text_notes -> rawTextInput, trimmed; voice_dictation -> transcriptText, trimmed', () => {
    expect(groundingContextFor({ inputMode: 'text_notes', rawTextInput: '  a \n', transcriptText: 'IGNORED' })).toBe('a');
    expect(groundingContextFor({ inputMode: 'voice_dictation', rawTextInput: 'IGNORED', transcriptText: ' b ' })).toBe('b');
    // A mode never borrows the other column.
    expect(groundingContextFor({ inputMode: 'text_notes', rawTextInput: null, transcriptText: 'x' })).toBe('');
    expect(groundingContextFor({ inputMode: 'voice_dictation', rawTextInput: 'x', transcriptText: null })).toBe('');
  });

  it("⚠️ NAMED RESIDUAL — conversation keeps TODAY'S behaviour on both sides", () => {
    const visit = { inputMode: 'audio_upload', rawTextInput: null, transcriptText: 'plain deepgram text' };
    // The doors have only transcriptText, untrimmed, exactly as before v2…
    expect(groundingContextFor(visit)).toBe('plain deepgram text');
    // …and the worker still passes the role-labelled transcript L3 read.
    expect(groundingContextFor(visit, { conversationTranscript: 'Doctor: role-labelled' })).toBe('Doctor: role-labelled');
  });
});

/** Source text with comments removed, so a rule cannot be satisfied by prose. */
function code(rel: string): string {
  return readFileSync(path.resolve(process.cwd(), rel), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) {
      if (name === '__tests__' || name === 'node_modules') continue;
      out.push(...sourceFiles(p));
    } else if (/\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name)) {
      out.push(p);
    }
  }
  return out;
}

describe('#314 v2 · the rule has FIVE readers and no sixth copy — asserted on source', () => {
  it("the worker's fill context is the shared call, fed the values L3 read (a STRING read — the worker has no seam)", () => {
    const src = code('src/worker.ts');
    expect(src).toMatch(
      /groundingContextFor\(\s*\{\s*inputMode: visit\.inputMode,\s*rawTextInput: visit\.rawTextInput,\s*transcriptText: dictationTranscript,\s*\},\s*\{ conversationTranscript: contextText \},?\s*\)/,
    );
    expect(src).toContain('dictationTranscript = dictationText;');
    expect(src).toMatch(/runTemplateTwinFillStep\(\{[\s\S]{0,400}?contextText: fillContextText,/);
  });

  it('every caller of the fill engine derives its context through groundingContextFor — and there are exactly four doors', () => {
    const root = path.resolve(process.cwd(), 'src');
    const callers = sourceFiles(root)
      .map((p) => [path.relative(process.cwd(), p), code(path.relative(process.cwd(), p))] as const)
      .filter(([rel, src]) =>
        /\b(?:processTemplateTwinVisit|readAndPrepareTemplateTwinFill)\(/.test(src) &&
        // the engine itself, and the worker's pass-through (asserted above)
        !rel.endsWith('template-twin/fill-engine.ts') &&
        !rel.endsWith('worker/template-twin-fill-step.ts'),
      );
    expect(callers.map(([rel]) => rel).sort()).toEqual([
      'src/actions/preview-visit-document.ts',
      'src/actions/set-template-control.ts',
      'src/lib/template-twin/native-export.ts',
      'src/lib/template-twin/sign-freeze.ts',
    ]);
    for (const [rel, src] of callers) {
      expect(src, `${rel} derives its own context`).toMatch(/contextText: groundingContextFor\(/);
    }
  });

  it('⚠️ no source file hands a fill a context built from a column directly', () => {
    const offenders = sourceFiles(path.resolve(process.cwd(), 'src'))
      .map((p) => path.relative(process.cwd(), p))
      .filter((rel) => /contextText:\s*[^,\n]*\b(?:transcriptText|rawTextInput)\b/.test(code(rel)));
    expect(offenders).toEqual([]);
  });
});
