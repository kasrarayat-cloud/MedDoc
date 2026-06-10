// ============================================================================
// previewNoteTemplateAction — live sample-note preview generator
// ----------------------------------------------------------------------------
// Pins the load-bearing properties:
//   - the REAL prompt builder is fed the doctor's template (its section
//     headings appear in the system prompt), and the IMMUTABLE safety preamble
//     is always present (confirm-not-fabricate can't be weakened);
//   - the result is cached by template CONTENT — identical content = one model
//     call; edited content = a fresh call;
//   - invalid / PHI-bearing drafts are refused (same posture as save);
//   - it NEVER persists a visit (Option B: no layer wrappers, no prisma write).
// The model call itself is stubbed (we assert on the prompt + caching, not the
// model); the synthetic transcript/entities are the only generation input.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';
// Real class (the @meddoc/ai mock below spreads ...actual).
import { AnthropicRefusalError } from '@meddoc/ai';

const h = vi.hoisted(() => ({
  completeText: vi.fn(),
  visitUpdate: vi.fn(),
  store: new Map<string, string>(),
}));
const completeText = h.completeText;
const visitUpdate = h.visitUpdate;
const store = h.store;

// Keep wrapAsData / delimiterSystemSuffix REAL (pure) — override only the model.
vi.mock('@meddoc/ai', async (orig) => {
  const actual = await orig<typeof import('@meddoc/ai')>();
  return { ...actual, modelClient: { completeText: h.completeText, complete: vi.fn() } };
});
// The action doesn't use prisma; the transitive entities-schema import pulls
// @meddoc/db. Stub it + a transcribeVisit.update spy to prove it's never hit.
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: h.visitUpdate } },
}));
vi.mock('@/lib/auth', () => ({
  requireSession: vi.fn().mockResolvedValue({ user: { id: 'u1', practiceId: 'p1' } }),
}));
// The entities-schema module (03-extract-entities) transitively imports
// @/lib/audit → next-auth, which vitest can't resolve. The action never logs
// an audit; stub it (same pattern as the rx-warning-audit test).
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
// In-memory Redis so the REAL cache module (content-hash key) is exercised.
vi.mock('@/lib/queue', () => ({
  getSharedRedisConnection: () => ({
    get: async (k: string) => h.store.get(k) ?? null,
    set: async (k: string, v: string) => { h.store.set(k, v); },
  }),
}));

import { previewNoteTemplateAction } from '@/actions/preview-note-template';
import { SAMPLE_PREVIEW_ENTITIES } from '@/worker/note-templates/sample-preview-transcript';
import { ExtractedEntities } from '@/worker/layers/03-extract-entities';

const CUSTOM_LABEL = 'My Custom Plan Section';

function draft(overrides: Record<string, unknown> = {}) {
  return {
    name: 'Cardiology follow-up',
    encounterType: null,
    sections: [
      { key: 'subjective', label: 'Subjective', order: 1, formatHint: 'prose', styleInstructions: null, defaultText: null },
      { key: 'plan', label: CUSTOM_LABEL, order: 2, formatHint: 'bullets', styleInstructions: null, defaultText: null },
    ],
    styleProfile: { tense: 'past', tone: 'concise', abbreviations: 'expand' },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  store.clear();
  completeText.mockResolvedValue({ text: '## Subjective\nSample.\n## ' + CUSTOM_LABEL + '\n- Sample plan.' });
});

describe('SAMPLE_PREVIEW_ENTITIES fixture', () => {
  it('is a valid ExtractedEntities object', () => {
    expect(() => ExtractedEntities.parse(SAMPLE_PREVIEW_ENTITIES)).not.toThrow();
  });
});

describe('previewNoteTemplateAction', () => {
  it('feeds the REAL prompt builder the template structure + the immutable safety preamble', async () => {
    const res = await previewNoteTemplateAction(draft());
    expect(res.ok).toBe(true);
    expect(completeText).toHaveBeenCalledTimes(1);
    const sys = completeText.mock.calls[0][0].system as string;
    // the doctor's custom section heading made it into the real prompt
    expect(sys).toContain(`## ${CUSTOM_LABEL}`);
    // the immutable confirm-not-fabricate guardrails are present + the call is
    // stateless (no visit row)
    expect(sys.toLowerCase()).toMatch(/do not (invent|fabricate)/);
    expect(completeText.mock.calls[0][0].visitId).toBeNull();
    expect(completeText.mock.calls[0][0].practiceId).toBe('p1');
  });

  it('NEVER persists a visit', async () => {
    await previewNoteTemplateAction(draft());
    expect(visitUpdate).not.toHaveBeenCalled();
  });

  it('caches by content — identical draft = ONE model call', async () => {
    const a = await previewNoteTemplateAction(draft());
    const b = await previewNoteTemplateAction(draft());
    expect(a.ok && b.ok).toBe(true);
    expect(completeText).toHaveBeenCalledTimes(1); // second served from cache
    if (b.ok) expect(b.cached).toBe(true);
  });

  it('regenerates when the template content changes (cache miss)', async () => {
    await previewNoteTemplateAction(draft());
    await previewNoteTemplateAction(draft({ name: 'A different name' }));
    expect(completeText).toHaveBeenCalledTimes(2);
  });

  it('refuses an invalid draft with a friendly message (no model call)', async () => {
    const res = await previewNoteTemplateAction(draft({ name: '' }));
    expect(res.ok).toBe(false);
    expect(completeText).not.toHaveBeenCalled();
  });

  it('refuses a PHI-bearing structural field (same as save) — no model call', async () => {
    // An SSN-shaped literal in a section label is structural PHI → reject.
    const res = await previewNoteTemplateAction(
      draft({
        sections: [
          { key: 's1', label: 'Patient 123-45-6789 notes', order: 1, formatHint: 'prose', styleInstructions: null, defaultText: null },
        ],
      }),
    );
    expect(res.ok).toBe(false);
    expect(completeText).not.toHaveBeenCalled();
  });

  it('degrades to { ok:false } (never throws) when the model call fails', async () => {
    completeText.mockRejectedValueOnce(new Error('model down'));
    const res = await previewNoteTemplateAction(draft());
    expect(res.ok).toBe(false);
  });

  it('Q1 #09.1: a content-policy refusal degrades to { ok:false } — never blocks parse/save/activate', async () => {
    completeText.mockRejectedValueOnce(
      new AnthropicRefusalError('claude-opus-4-8', 'tm_soap_draft')
    );
    const res = await previewNoteTemplateAction(draft());
    expect(res.ok).toBe(false);
  });
});
