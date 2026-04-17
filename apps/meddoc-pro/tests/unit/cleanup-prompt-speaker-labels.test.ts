// ============================================================================
// cleanup-transcript.md — speaker-label handling
// ----------------------------------------------------------------------------
// Meta-test: verifies the prompt the finalize_visit worker loads has the
// guidance needed so Claude can handle BOTH inputs:
//   - Whisper batch (not diarized, UNKNOWN prefix)
//   - Deepgram live (diarized, speaker_0 / speaker_1 prefixes)
//
// The live eval against real audio + Deepgram is deferred to M7
// (user decision D10). This keeps a fast CI-runnable guardrail so
// the prompt can't silently lose the mapping clause.
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';

const PROMPT_PATH = path.join(
  __dirname,
  '..',
  '..',
  '..',
  'scribe',
  'src',
  'server',
  'prompts',
  'cleanup-transcript.md'
);

describe('cleanup-transcript prompt', () => {
  const prompt = fs.readFileSync(PROMPT_PATH, 'utf8');

  it('mentions Deepgram and its speaker_N label convention', () => {
    expect(prompt).toMatch(/deepgram/i);
    expect(prompt).toMatch(/speaker_0/);
    expect(prompt).toMatch(/speaker_1/);
  });

  it('instructs Claude to map neutral labels to CLINICIAN / PATIENT / OTHER', () => {
    expect(prompt).toMatch(/CLINICIAN/);
    expect(prompt).toMatch(/PATIENT/);
    expect(prompt).toMatch(/OTHER/);
    // The mapping must be explicit, not left to implication.
    expect(prompt.toLowerCase()).toMatch(/map|mapping/);
  });

  it('keeps Whisper (non-diarized) handling so batch pipeline still works', () => {
    expect(prompt).toMatch(/whisper/i);
    // Either UNKNOWN or "not diarized" language must be present.
    expect(prompt.toLowerCase()).toMatch(/unknown|not\s+been\s+diarized|not\s+diarized/);
  });

  it('requires consistent speaker mapping across the transcript', () => {
    // Once Claude decides speaker_0 == CLINICIAN, it must stay consistent.
    expect(prompt.toLowerCase()).toMatch(/consistent/);
  });
});
