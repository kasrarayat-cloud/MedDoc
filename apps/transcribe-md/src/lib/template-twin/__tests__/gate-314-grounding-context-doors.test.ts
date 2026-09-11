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
//
// ⚠️ #314 v3 — ONE MODE, ONE ANSWER. Round two found the worker and the doors
// disagreeing on a CONVERSATION total (the worker refused it through L3's role
// labels, every door grounded it), so encounter-facts now refuses a
// conversation total outright. That refusal is only the same everywhere if
// every path hands the fill the visit's REAL mode, so the worker's fill step and
// each of the four doors is driven for a text, a dictation AND a conversation
// visit, and its captured `inputMode` is asserted with the total it yields.
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
import { runTemplateTwinFillStep } from '@/worker/template-twin-fill-step';
import type { EncounterInputMode } from '../encounter-facts';

const VISIT = 'visit-314';
const PRACTICE = 'prac-1';
const TOTAL_QUOTE = 'Total time 45 minutes.';
const ENTITIES = { total_time_minutes: { minutes: 45, evidence_quote: TOTAL_QUOTE } };

// #314 v3 — a CONVERSATION visit, finding 0's shape: the doctor states the total
// as the first sentence of an utterance. The worker's L3 reads it through role
// labels ("[Doctor #0, 3:05]: …"); every door reads the plain `transcriptText`.
const SPOKEN_TOTAL = 'Total time was 45 minutes.';
const CONVERSATION_ENTITIES = { total_time_minutes: { minutes: 45, evidence_quote: SPOKEN_TOTAL } };
const UTTERANCES = [
  { speaker: 1, start: 173, end: 175, confidence: 0.99, channel: 0, transcript: 'No, that makes sense.', words: [] },
  { speaker: 0, start: 185, end: 187, confidence: 0.99, channel: 0, transcript: SPOKEN_TOTAL, words: [] },
];
const SPEAKERS = {
  '0': { role: 'doctor', confidence: 0.95, reasoning: 'synthetic fixture' },
  '1': { role: 'patient', confidence: 0.95, reasoning: 'synthetic fixture' },
};
const PLAIN_CONVERSATION = UTTERANCES.map((u) => u.transcript).join(' ');
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

type Mode = 'text_notes' | 'voice_dictation' | 'audio_upload';
const entitiesFor = (mode: Mode) => (mode === 'audio_upload' ? CONVERSATION_ENTITIES : ENTITIES);
function rowFor(mode: Mode): Record<string, unknown> {
  return {
    id: VISIT,
    status: 'READY',
    signedAt: null,
    userId: 'author-1',
    practiceId: PRACTICE,
    inputMode: mode,
    // ⚠️ NULL FOR A TYPED VISIT, AS IN PRODUCTION — the whole of D6.
    transcriptText: mode === 'text_notes' ? null : mode === 'voice_dictation' ? DICTATED : PLAIN_CONVERSATION,
    rawTextInput: mode === 'text_notes' ? TYPED : null,
    entities: entitiesFor(mode),
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
// ⚠️ gate-172: a `kind` predicate matches MANY fields, so the choice is made
// with an EXPLICIT COUNT, never an unscoped `find`. The fixture carries 52
// narrative controls (measured 2026-09-11); a changed fixture reds here instead
// of silently moving this arm onto a different field.
function scaffoldTarget(): string {
  const narrative = BASE_IR.fields.filter((f) => f.kind === 'narrative_text');
  expect(narrative.length, "the WM IOV fixture's narrative-control count moved").toBe(52);
  return narrative[0]!.fieldId as string;
}
const FIELD = scaffoldTarget();
const IR = {
  ...BASE_IR,
  fields: BASE_IR.fields.map((f) =>
    f.fieldId === FIELD ? { ...f, scaffolded: true, scaffoldText: 'No acute findings.' } : f,
  ),
};

/** What the WORKER hands the fill: the real L3 context, through the worker's own call. */
async function workerFillContext(row: Record<string, unknown>): Promise<string> {
  h.modelComplete.mockResolvedValueOnce({ ...EMPTY_BUT_VALID, ...(row.entities as object) });
  const base = { visitId: VISIT, practiceId: PRACTICE, userId: 'author-1' };
  const l3 =
    row.inputMode === 'text_notes'
      ? await runLayer3ExtractEntities({ ...base, mode: 'text', rawText: row.rawTextInput as string })
      : row.inputMode === 'voice_dictation'
        ? await runLayer3ExtractEntities({ ...base, mode: 'dictation', dictationText: row.transcriptText as string })
        : await runLayer3ExtractEntities({
            ...base,
            mode: 'conversation',
            utterances: UTTERANCES as never,
            speakerMap: SPEAKERS as never,
          });
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

/** What a path handed the fill engine: the two inputs grounding depends on. */
type FillInput = { inputMode?: unknown; contextText?: unknown };
const inputOf = (call: unknown[] | undefined): FillInput => (call?.[0] as FillInput | undefined) ?? {};

const DOORS: Array<[string, () => Promise<FillInput>]> = [
  [
    'sign-freeze (the sign-time re-fill)',
    async () => {
      await freezeNativeManifestForSigning({ visitId: VISIT, practiceId: PRACTICE });
      expect(h.processFill, 'the freeze never reached its re-fill').toHaveBeenCalledTimes(1);
      return inputOf(h.processFill.mock.calls[0]);
    },
  ],
  [
    'native-export (the on-demand export fill)',
    async () => {
      await loadOrComputeNativeTemplateDocxForVisit(VISIT, PRACTICE);
      expect(h.processFill, 'the export never reached its fill').toHaveBeenCalledTimes(1);
      return inputOf(h.processFill.mock.calls[0]);
    },
  ],
  [
    'preview-visit-document (the pre-sign preview)',
    async () => {
      await previewVisitDocumentAction(VISIT, 'word');
      expect(h.readAndPrepare, 'the preview never reached its fill').toHaveBeenCalledTimes(1);
      return inputOf(h.readAndPrepare.mock.calls[0]);
    },
  ],
  [
    'set-template-control (a control edit)',
    async () => {
      await insertScaffoldDefaultAction(VISIT, FIELD);
      expect(h.readAndPrepare, 'the control edit never reached its fill').toHaveBeenCalled();
      return inputOf(h.readAndPrepare.mock.calls[0]);
    },
  ],
];

/** The WORKER's first fill, driven through its real fill step (flag on, engine mocked). */
async function driveWorker(): Promise<FillInput> {
  const row = h.row!;
  const contextText = await workerFillContext(row);
  h.processFill.mockResolvedValueOnce({ render: null });
  vi.stubEnv('NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX', 'true');
  try {
    const result = await runTemplateTwinFillStep({
      visitId: VISIT,
      tenantPracticeId: PRACTICE,
      authorUserId: 'author-1',
      noteTemplateId: 'tpl-1',
      noteTemplateVersion: 3,
      inputMode: row.inputMode as string,
      contextText,
      entities: row.entities,
      generatedNote: 'A note.',
    });
    expect(result.status, 'the worker never reached its fill').toBe('filled');
  } finally {
    vi.unstubAllEnvs();
  }
  expect(h.processFill, 'the worker filled more than once').toHaveBeenCalledTimes(1);
  return inputOf(h.processFill.mock.calls[0]);
}

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
    const door = (await drive()).contextText;
    expect(door, 'the door handed the fill a different text from the worker').toBe(worker);
    expect(door, 'NON-VACUITY: an empty context would also "match" an empty worker').not.toBe('');
    // …and so the worker's total survives every re-fill.
    expect(totalsAt(mode, door as string), 'the door would blank the total the worker filled').toEqual(['45']);
  });
});

// ⚠️ #314 v3 — THE REFUSAL LIVES IN ONE PLACE, SO THE MODE MUST ARRIVE THERE
// INTACT. Each path is driven and its captured `inputMode` is fed, with its
// captured context, to the real projector. A path that mapped an audio_upload
// visit to 'dictation' (or dropped `inputMode` from its select) would ground
// the conversation total the others refuse.
const EXPECTED: Record<Mode, { mode: EncounterInputMode; totals: string[] }> = {
  text_notes: { mode: 'text', totals: ['45'] },
  voice_dictation: { mode: 'dictation', totals: ['45'] },
  audio_upload: { mode: 'conversation', totals: [] },
};
const PATHS: Array<[string, () => Promise<FillInput>]> = [
  ['worker (the first fill, through runTemplateTwinFillStep)', driveWorker],
  ...DOORS,
];
const totalsFrom = (got: FillInput, mode: Mode) =>
  projectEncounterFacts({
    mode: got.inputMode as EncounterInputMode,
    contextText: got.contextText as string,
    entities: entitiesFor(mode) as unknown as Parameters<typeof projectEncounterFacts>[0]['entities'],
  })
    .filter((f) => f.concept === 'total_time_minutes')
    .map((f) => f.value);

describe.each<Mode>(['text_notes', 'voice_dictation', 'audio_upload'])(
  '#314 v3 · a %s visit — FIVE PATHS, ONE MODE, ONE ANSWER',
  (mode) => {
    it.each(PATHS)("%s hands the fill the visit's REAL mode, and yields the same total", async (_path, drive) => {
      h.row = rowFor(mode);
      const got = await drive();
      expect(got.inputMode, 'this path mapped the visit to the wrong encounter mode').toBe(EXPECTED[mode].mode);
      expect(typeof got.contextText, 'NON-VACUITY: the path handed over no context').toBe('string');
      expect(totalsFrom(got, mode), 'this path disagrees with the others about the total').toEqual(
        EXPECTED[mode].totals,
      );
    });
  },
);

describe('#314 v3 · a conversation total is refused BECAUSE of the mode, not the text', () => {
  it("OPPOSITE ANSWER — the doors' conversation context grounds the same total in any other mode", () => {
    const context = groundingContextFor({ inputMode: 'audio_upload', rawTextInput: null, transcriptText: PLAIN_CONVERSATION });
    const at = (m: EncounterInputMode) =>
      totalsFrom({ inputMode: m, contextText: context }, 'audio_upload');
    expect(at('conversation')).toEqual([]);
    expect(at('dictation')).toEqual(['45']);
    expect(at('text')).toEqual(['45']);
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

  // The CONTEXT is unchanged for every other fact. Only the conversation TOTAL
  // is refused, in encounter-facts (v3); persisting L3's labelled context so the
  // doors can read it is the proper fix, and it is FILED.
  it("⚠️ NAMED RESIDUAL — conversation keeps TODAY'S context on both sides (its total is refused in encounter-facts)", () => {
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

  // ⚠️ ADVISORY, AND ARMED AS A STRING READ. The divergence line changes no fill
  // — it is the only signal that the shared rule and L3's own context drifted
  // for a text or dictation visit. The worker has no seam, so the line's
  // presence and its condition are pinned on source. Residual: for a
  // conversation visit it cannot fire, because `groundingContextFor` returns
  // the L3 text itself; v3 refuses that total instead.
  it("the worker's grounding-context divergence line is present, and fires on the divergence alone", () => {
    expect(code('src/worker.ts')).toMatch(
      /if \(fillContextText !== contextText\) \{\s*console\.warn\(\s*`\[transcribe-md-worker\] template-twin grounding context diverges from the L3 context visit=\$\{visitId\} mode=\$\{visit\.inputMode\}`\s*\);\s*\}/,
    );
  });

  // ⚠️ #314 v2 moved the preview cache key to v8 because the same note at the
  // same soapVersion renders a different billing line. Production runs v7, so a
  // key equal to the running one (or below it) would serve a warm pre-#314
  // preview. The #203 arm only asks for >= 7, which v7 passes.
  it('the preview cache key is PAST the v7 that production runs', () => {
    const cache = readFileSync(path.resolve(process.cwd(), 'src/lib/docx-preview/fill-cache.ts'), 'utf8');
    const m = cache.match(/const KEY_VERSION = 'v(\d+)';/);
    expect(m, 'KEY_VERSION did not parse — this arm proves nothing until it does').not.toBeNull();
    expect(Number((m as RegExpMatchArray)[1]), "KEY_VERSION must be above production's 'v7'").toBeGreaterThanOrEqual(8);
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
