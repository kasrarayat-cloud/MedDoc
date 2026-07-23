// ============================================================================
// L6 structure-preservation — REAL MODEL proof (operator-only, CI-excluded).
// ----------------------------------------------------------------------------
// Proves the KUK operative-note fix end-to-end at the layer: a doctor-uploaded
// OPERATIVE NOTE template + a sparse op-note draft (surgical sections empty,
// clinic content under RECOMMENDATIONS) + a fixable critique must yield a note
// STILL in operative structure — NOT reverted to Subjective/Objective/
// Assessment/Plan. Runs the actual runLayer6Polish prompt construction against
// the real Anthropic API; DB/audit are stubbed exactly like 06-polish.test.ts.
//
// Self-skips unless L6_LIVE_MODEL=1 (spends real tokens). Never runs in CI.
//   npx vitest run src/worker/layers/__tests__/06-polish.livemodel.test.ts
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const LIVE = process.env.L6_LIVE_MODEL === '1';
const KEY = process.env.ANTHROPIC_API_KEY;

const mocks = vi.hoisted(() => ({
  prismaUpdate: vi.fn(),
  applyAdditiveReviewState: vi.fn(),
  logAudit: vi.fn(),
}));

interface CompleteTextArgs {
  purpose?: string;
  model: string;
  maxTokens?: number;
  temperature?: number;
  system: string;
  user: string;
}
interface AnthropicResponse {
  content?: Array<{ text?: string }>;
  error?: { message?: string };
}

async function realCompleteText(args: CompleteTextArgs): Promise<{ text: string }> {
  // Short-circuit the L6b fidelity gate to a clean verdict — isolate structure.
  if (args.purpose === 'tm_polish_gate') return { text: '{"violations":[]}' };
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': process.env.ANTHROPIC_API_KEY as string,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: args.model,
      max_tokens: args.maxTokens ?? 4096,
      temperature: args.temperature ?? 0.1,
      system: args.system,
      messages: [{ role: 'user', content: args.user }],
    }),
  });
  const j = (await res.json()) as AnthropicResponse;
  if (j.error) throw new Error(j.error.message);
  return { text: (j.content ?? []).map((c) => c.text ?? '').join('') };
}

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: vi.fn(), completeText: realCompleteText } };
});
vi.mock('@meddoc/db', () => ({ default: { transcribeVisit: { update: mocks.prismaUpdate } } }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/worker/finalize-review-state', () => ({
  applyAdditiveReviewState: mocks.applyAdditiveReviewState,
}));

import { runLayer6Polish, type Layer6Input } from '../06-polish';
import type { ResolvedNoteTemplate } from '../../note-templates/build-soap-prompt';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '../../note-templates/system-default-template';

const OP_NOTE_TEMPLATE: ResolvedNoteTemplate = {
  id: 'tmpl_opnote',
  version: 1,
  isSystemDefault: false,
  styleProfile: { tense: null, tone: 'concise', abbreviations: null, preamble: '', globalRules: [] },
  sections: [
    ['PROCEDURE:', 'proc'],
    ['PREOPERATIVE DIAGNOSIS:', 'preop'],
    ['POSTOPERATIVE FINDINGS:', 'postop'],
    ['CONSENT:', 'consent'],
    ['DESCRIPTION OF PROCEDURE:', 'desc'],
    ['RECOMMENDATIONS:', 'recs'],
  ].map(([label, key], i) => ({
    key,
    label,
    order: i + 1,
    formatHint: 'prose',
    styleInstructions: null,
    defaultText: null,
    defaultTextMode: 'omit_unless_supported',
  })),
};

// Realistic KUK shape: the surgical sections were emptied by the L4 anchored
// verifier, which leaves the set-aside placeholder (NOT a truly-empty section).
const SET_ASIDE = `_[All AI-drafted content for this section was set aside for your review — see the suggestions below and adopt before signing.]_`;
const SPARSE_OP_DRAFT = `## PROCEDURE:
${SET_ASIDE}

## PREOPERATIVE DIAGNOSIS:
${SET_ASIDE}

## POSTOPERATIVE FINDINGS:
${SET_ASIDE}

## CONSENT:
${SET_ASIDE}

## DESCRIPTION OF PROCEDURE:
${SET_ASIDE}

## RECOMMENDATIONS:
Status post laparoscopic sleeve gastrectomy at 6 weeks. Continue advancing to regular-texture diet; protein goal 60-80 g daily. Daily multivitamin compliance emphasized. Follow up in 3 months.`;

describe.skipIf(!LIVE || !KEY)('L6 real-model structure preservation', () => {
  beforeEach(() => {
    mocks.prismaUpdate.mockResolvedValue({ id: 'probe' });
    mocks.applyAdditiveReviewState.mockResolvedValue(undefined);
    mocks.logAudit.mockResolvedValue(undefined);
  });

  it('keeps a sparse OPERATIVE NOTE in operative structure — does NOT revert to SOAP', async () => {
    const result = await runLayer6Polish({
      visitId: 'probe-visit',
      practiceId: 'probe-practice',
      userId: 'probe-user',
      soapDraft: SPARSE_OP_DRAFT,
      critique: {
        issues: [
          {
            severity: 'major',
            location: 'RECOMMENDATIONS:',
            // A REMOVAL fix — short-circuits isAdditiveFix to non-additive so the
            // MODEL branch actually fires (a pure-additive fix would passthrough
            // and return the draft verbatim, never exercising the prompt).
            description: 'the diet advice restates the protein goal verbosely',
            suggested_fix: 'remove the redundant words so the diet line is concise',
          },
        ],
        overall_quality: 'medium',
        safe_to_sign_without_review: false,
      },
      noteTemplate: OP_NOTE_TEMPLATE,
    } as Layer6Input);

    const note = result.soapFinal;
    console.log('\n--- L6 output headings ---\n' + (note.match(/^##\s+.+$/gm) || []).join('\n'));

    // No SOAP reversion (the bug)…
    expect(note).not.toMatch(/##\s+Subjective/i);
    expect(note).not.toMatch(/##\s+Assessment/i);
    // …and every required operative heading survives (set-aside placeholders keep
    // the sections non-empty, so the model retains them; export renders the
    // placeholders as "Not documented.").
    for (const label of OP_NOTE_TEMPLATE.sections.map((s) => s.label)) {
      expect(note).toContain(`## ${label}`);
    }
  }, 120_000);

  it('does NOT leak a refusal preamble when a critique fix conflicts with the lock (the prod leak)', async () => {
    const result = await runLayer6Polish({
      visitId: 'probe-conflict',
      practiceId: 'probe-practice',
      userId: 'probe-user',
      soapDraft: SPARSE_OP_DRAFT,
      critique: {
        issues: [
          {
            severity: 'major',
            location: 'PROCEDURE:',
            // Directly conflicts with the structure lock — the model must
            // silently skip it, NOT explain its refusal into the note body.
            description: 'the note should use SOAP sections for a clinic visit',
            suggested_fix:
              'remove the operative headings and reorganize the note into Subjective, Objective, Assessment, and Plan',
          },
        ],
        overall_quality: 'medium',
        safe_to_sign_without_review: false,
      },
      noteTemplate: OP_NOTE_TEMPLATE,
    } as Layer6Input);

    const note = result.soapFinal;
    // The note must START with a heading — no leading prose/refusal preamble.
    expect(note.trimStart()).toMatch(/^##\s/);
    expect(note).not.toMatch(/I cannot apply|cannot be applied|my (immutable|formatting) rules/i);
    // …and the operative structure held (no SOAP reversion).
    expect(note).toMatch(/##\s+PROCEDURE:/i);
    expect(note).not.toMatch(/##\s+Subjective/i);
  }, 120_000);

  // Ultrasound control (the "ultrasound unchanged" rail): a non-customizing
  // imaging doctor reaches L6 with the SOAP default template while the draft
  // carries the ultrasound REPORT headings. The lock is gated OFF for the
  // default, so polish must keep the imaging structure — NOT force SOAP.
  const IMAGING_DRAFT = `## Exam
Bilateral lower extremity venous duplex, reflux.

## Indication
Leg heaviness and visible varicosities.

## Technique
Standing reflux evaluation with distal augmentation.

## Comparison
None.

## Findings
Right GSV incompetent at the SFJ, reflux 3.4 s. Left GSV competent.

## Impression
Right great saphenous vein incompetence; left within normal limits.`;

  it('does NOT force SOAP onto an ULTRASOUND report draft carried with the default template', async () => {
    const result = await runLayer6Polish({
      visitId: 'probe-us',
      practiceId: 'probe-practice',
      userId: 'probe-user',
      soapDraft: IMAGING_DRAFT,
      critique: {
        issues: [
          {
            severity: 'major',
            location: 'Impression',
            description: 'the impression is wordy',
            suggested_fix: 'remove redundant words to keep the impression concise',
          },
        ],
        overall_quality: 'medium',
        safe_to_sign_without_review: false,
      },
      noteTemplate: SYSTEM_DEFAULT_NOTE_TEMPLATE,
    } as Layer6Input);

    const note = result.soapFinal;
    console.log('\n--- ultrasound-control output headings ---\n' + (note.match(/^##\s+.+$/gm) || []).join('\n'));
    expect(note).toMatch(/##\s+Findings/i);
    expect(note).toMatch(/##\s+Impression/i);
    expect(note).not.toMatch(/##\s+Subjective/i);
    expect(note).not.toMatch(/##\s+Assessment/i);
  }, 120_000);
});
