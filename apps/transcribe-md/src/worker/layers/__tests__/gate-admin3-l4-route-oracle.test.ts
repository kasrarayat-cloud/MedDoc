// ============================================================================
// ORACLE — L4 ROUTES EVERY SPECIALTY EXACTLY AS THE FROZEN LITERAL DID
// ADMIN-3 PR-1, ruling #197.
// ----------------------------------------------------------------------------
// The claim under refutation: "identical output for every input in both flag
// states". This drives the REAL `runLayer4GenerateSoap` (model mocked) over
// the whole derived specialty universe, in three flag states and both
// evidence-anchor states, and checks — per run — which prompt builder ran,
// with which template, and that the system prompt sent to the model is that
// builder's own output. The builders are spies that CALL THROUGH to the real
// implementations, so the prompt text is unchanged; nothing here re-derives
// a prompt.
//
// Expected route = frozen 6fcd21d0 rule: imaging iff the flag is exactly
// 'true' AND the id is exactly 'ultrasound'.
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: vi.fn(), completeText: mocks.modelCompleteText } };
});
vi.mock('@meddoc/db', () => ({
  default: {
    $executeRaw: vi.fn().mockResolvedValue(1),
    transcribeVisit: { update: mocks.prismaUpdate },
  },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/worker/note-templates/build-ultrasound-prompt', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@/worker/note-templates/build-ultrasound-prompt')>();
  return { ...actual, buildUltrasoundSystemPrompt: vi.fn(actual.buildUltrasoundSystemPrompt) };
});
vi.mock('@/worker/note-templates/build-soap-prompt', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/worker/note-templates/build-soap-prompt')>();
  return { ...actual, buildSoapSystemPrompt: vi.fn(actual.buildSoapSystemPrompt) };
});

import { runLayer4GenerateSoap, type Layer4Input } from '../04-generate-soap';
import { buildUltrasoundSystemPrompt } from '@/worker/note-templates/build-ultrasound-prompt';
import {
  buildSoapSystemPrompt,
  type ResolvedNoteTemplate,
} from '@/worker/note-templates/build-soap-prompt';
import { ULTRASOUND_REPORT_TEMPLATE } from '@/worker/note-templates/ultrasound-report-template';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '@/worker/note-templates/system-default-template';
import {
  STRING_UNIVERSE,
  frozen,
  restoreUltrasoundFlag,
  setUltrasoundFlag,
  show,
} from '../../../../../../packages/shared/src/__test-support__/report-kind-oracle';

const usSpy = vi.mocked(buildUltrasoundSystemPrompt);
const soapSpy = vi.mocked(buildSoapSystemPrompt);

const CUSTOM: ResolvedNoteTemplate = {
  ...(SYSTEM_DEFAULT_NOTE_TEMPLATE as ResolvedNoteTemplate),
  id: 'tmpl_custom_route_oracle',
  isSystemDefault: false,
};

const input = (specialty: string, noteTemplate?: ResolvedNoteTemplate): Layer4Input =>
  ({
    visitId: 'v1',
    practiceId: 'p1',
    userId: 'd1',
    specialty,
    roleLabeledTranscript: 'Doctor #0: Findings are unremarkable.\nPatient #1: Okay.',
    entities: {} as unknown as Layer4Input['entities'],
    audioConfidenceStats: null,
    interpreterMode: false,
    noteTemplate,
  }) as Layer4Input;

type Route = 'imaging' | 'soap';

async function routeOf(
  specialty: string,
  noteTemplate?: ResolvedNoteTemplate
): Promise<{ route: Route | string; problems: string[] }> {
  usSpy.mockClear();
  soapSpy.mockClear();
  mocks.modelCompleteText.mockClear();
  mocks.modelCompleteText.mockResolvedValue({ text: '## Subjective\nUnremarkable.' });
  mocks.prismaUpdate.mockResolvedValue({ id: 'v1' });
  await runLayer4GenerateSoap(input(specialty, noteTemplate));

  const problems: string[] = [];
  const us = usSpy.mock.calls.length;
  const soap = soapSpy.mock.calls.length;
  const route: Route | string =
    us >= 1 && soap === 0 ? 'imaging' : soap >= 1 && us === 0 ? 'soap' : `both/neither us=${us} soap=${soap}`;

  const spy = route === 'imaging' ? usSpy : route === 'soap' ? soapSpy : null;
  if (spy) {
    const [tpl, opts] = spy.mock.calls[0]!;
    const wantId =
      noteTemplate && !noteTemplate.isSystemDefault
        ? noteTemplate.id
        : route === 'imaging'
          ? ULTRASOUND_REPORT_TEMPLATE.id
          : SYSTEM_DEFAULT_NOTE_TEMPLATE.id;
    if (tpl.id !== wantId) problems.push(`template ${tpl.id} != ${wantId}`);
    if (route === 'imaging' && opts.specialtyGuidanceText !== null) {
      problems.push('imaging route carried SOAP specialty guidance');
    }
    const sent = mocks.modelCompleteText.mock.calls[0]?.[0]?.system as string | undefined;
    const built = spy.mock.results[0]?.value as string;
    if (!sent || !sent.startsWith(built)) {
      problems.push('the system prompt sent is not the builder\'s own output');
    }
  }
  return { route, problems };
}

const ROUTE_FLAGS: readonly (string | undefined)[] = [undefined, 'true', 'false', 'TRUE'];

describe.each([
  ['anchors OFF', ''],
  ['anchors ON (production)', 'true'],
])('%s', (_a, anchors) => {
  beforeEach(() => {
    vi.stubEnv('TRANSCRIBE_MD_EVIDENCE_ANCHORS', anchors);
    mocks.logAudit.mockResolvedValue(undefined);
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    restoreUltrasoundFlag();
  });

  describe.each(ROUTE_FLAGS.map((v) => [show(v), v] as const))(
    'NEXT_PUBLIC_ULTRASOUND_SPECIALTY = %s',
    (_f, flag) => {
      it(
        'every specialty string takes the frozen route, with the frozen template and builder',
        async () => {
          setUltrasoundFlag(flag);
          const wrong: string[] = [];
          let imagingRuns = 0;
          for (const s of STRING_UNIVERSE) {
            const want: Route = !frozen.emApplies(s) ? 'imaging' : 'soap';
            const { route, problems } = await routeOf(s);
            if (route === 'imaging') imagingRuns++;
            if (route !== want || problems.length) {
              wrong.push(`${show(s)}: ${route} (want ${want}) ${problems.join('; ')}`);
            }
          }
          expect(wrong).toEqual([]);
          // Not vacuous: with the flag on, exactly the ultrasound run imaged.
          expect(imagingRuns).toBe(frozen.flag() ? 1 : 0);
        },
        60_000
      );

      it('a doctor\'s custom template is honoured on BOTH routes, exactly as before', async () => {
        setUltrasoundFlag(flag);
        for (const s of ['ultrasound', 'Ultrasound', 'primary-care', 'vascular-surgery']) {
          const want: Route = !frozen.emApplies(s) ? 'imaging' : 'soap';
          const { route, problems } = await routeOf(s, CUSTOM);
          expect(`${s}: ${route} ${problems.join('; ')}`.trim()).toBe(`${s}: ${want}`);
        }
      });
    }
  );
});
