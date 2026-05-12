// ============================================================================
// VisitFailedView copy-helper tests (2026-05-12 prod-fix).
// ----------------------------------------------------------------------------
// Pins the (failureCategory × failed-layer × inputMode) → copy table so a
// future refactor can't silently regress to the pre-fix "Connection issue"
// + WiFi-off-for-everything shape that triggered the prod fix.
//
// The brief's explicit copy contract is asserted per-row:
//   - L6 polish transient → "couldn't finalize the polish step" body
//   - L1 transcription transient → "couldn't transcribe the audio" body
//   - L7 automation transient → "couldn't auto-generate codes" body
//   - PipelineRejectError (audio-too-short) permanent → Mic icon + recording
//     copy, NOT FileX + "audio corrupt"
//   - text_notes permanent → FileText icon + note-text copy, NOT
//     "audio file may be corrupted" (deep-audit G11)
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  AlertTriangle,
  Cloud,
  FileText,
  FileX,
  Mic,
  RefreshCw,
  Wrench,
} from 'lucide-react';

import {
  detectFailedLayer,
  failureCopyFor,
} from '@/app/visits/[id]/visit-failed-copy';

describe('detectFailedLayer', () => {
  it.each([
    [
      'Processing failed during polish. Try retrying this visit, or contact support if it keeps failing.',
      'polish',
    ],
    [
      'Processing failed during transcription. The audio file may be corrupt or in an unsupported format — please re-upload to try again.',
      'transcription',
    ],
    [
      'Processing failed during entity extraction. The audio file may be corrupt or in an unsupported format — please re-upload to try again.',
      'entity_extraction',
    ],
    [
      'Processing failed during SOAP drafting. The audio file may be corrupt or in an unsupported format — please re-upload to try again.',
      'soap_drafting',
    ],
    [
      'Processing failed during clinical audit. Try retrying this visit, or contact support if it keeps failing.',
      'clinical_audit',
    ],
    [
      'Processing failed during speaker identification. Our transcription provider is temporarily unavailable; please try again in a few minutes.',
      'speaker_identification',
    ],
    [
      'Processing failed during codes / Rx / referrals generation. Try retrying this visit, or contact support if it keeps failing.',
      'automation',
    ],
  ])('parses %s → %s', (reason, expected) => {
    expect(detectFailedLayer(reason, 'audio_upload')).toBe(expected);
  });

  it('detects PipelineRejectError audio-too-short shape', () => {
    expect(
      detectFailedLayer(
        'Recording is 1.0s; need at least 3s of audio. Re-record with the conversation captured.',
        'voice_dictation',
      ),
    ).toBe('audio_input_invalid');
  });

  it('detects audio-empty / silent shapes', () => {
    expect(
      detectFailedLayer('Audio file too short — must be at least 3s.', 'audio_upload'),
    ).toBe('audio_input_invalid');
    expect(
      detectFailedLayer('Audio duration empty after decode.', 'audio_upload'),
    ).toBe('audio_input_invalid');
  });

  it('detects text_notes input-too-short on the text_notes path', () => {
    expect(
      detectFailedLayer('Notes too short — need substantive visit content.', 'text_notes'),
    ).toBe('transcript_input_invalid');
  });

  it('returns null for unknown reason text', () => {
    expect(detectFailedLayer('Bizarre error nobody planned for.', 'audio_upload')).toBe(
      null,
    );
  });

  it('returns null for null/undefined reason', () => {
    expect(detectFailedLayer(null, 'audio_upload')).toBe(null);
    expect(detectFailedLayer(undefined, 'voice_dictation')).toBe(null);
  });
});

describe('failureCopyFor — permanent failures', () => {
  it('PipelineRejectError audio-too-short → Mic icon + recording copy (NOT FileX)', () => {
    const copy = failureCopyFor({
      failureCategory: 'permanent',
      reviewReason: 'Recording is 1.0s; need at least 3s of audio. Re-record with the conversation captured.',
      inputMode: 'voice_dictation',
    });
    expect(copy.Icon).toBe(Mic);
    expect(copy.headline).toMatch(/Recording can/);
    expect(copy.ctaHref).toBe('/visits/new');
    expect(copy.ctaLabel).toMatch(/Start a new visit/);
    // Critical: must NOT pretend it's a network issue
    expect(copy.headline).not.toMatch(/Connection/);
  });

  it('text_notes permanent → FileText icon + note-text copy (G11 fix)', () => {
    const copy = failureCopyFor({
      failureCategory: 'permanent',
      reviewReason:
        'Processing failed during entity extraction. The audio file may be corrupt or in an unsupported format — please re-upload to try again.',
      inputMode: 'text_notes',
    });
    expect(copy.Icon).toBe(FileText);
    expect(copy.headline).toMatch(/Notes can/);
    // Must NOT say "audio" anywhere — this is the deep-audit G11
    // misleading-copy regression we are explicitly fixing.
    expect(copy.body.toLowerCase()).not.toContain('audio');
    expect(copy.ctaHref).toBe('/visits/new');
  });

  it('audio permanent (catch-all) → FileX + audio-corrupt copy', () => {
    const copy = failureCopyFor({
      failureCategory: 'permanent',
      reviewReason: 'Audio decode failed — unsupported container.',
      inputMode: 'audio_upload',
    });
    expect(copy.Icon).toBe(FileX);
    expect(copy.headline).toMatch(/process this audio/);
    expect(copy.body).toMatch(/MP3, WAV, M4A, or WebM/);
    expect(copy.ctaHref).toBe('/visits/new');
  });
});

describe('failureCopyFor — provider_down', () => {
  it('returns Cloud icon + wait-5-10 hint', () => {
    const copy = failureCopyFor({
      failureCategory: 'provider_down',
      reviewReason: 'Processing failed during transcription. Our transcription provider is temporarily unavailable; please try again in a few minutes.',
      inputMode: 'audio_upload',
    });
    expect(copy.Icon).toBe(Cloud);
    expect(copy.headline).toMatch(/Service temporarily unavailable/);
    expect(copy.hint).toBeTruthy();
    expect(copy.ctaHref).toBeUndefined();
  });
});

describe('failureCopyFor — transient failures (the prod-fix core)', () => {
  it('L6 polish transient → Wrench icon + "couldn\'t finalize the polish step" body (NOT WiFi-off + "Connection issue")', () => {
    const copy = failureCopyFor({
      failureCategory: 'transient',
      reviewReason: 'Processing failed during polish. Try retrying this visit, or contact support if it keeps failing.',
      inputMode: 'audio_upload',
    });
    expect(copy.Icon).toBe(Wrench);
    expect(copy.headline).toMatch(/Couldn’t finalize this visit|Couldn't finalize this visit/);
    expect(copy.body).toMatch(/polish step/);
    expect(copy.body).toMatch(/audio \+ draft are saved/);
    // Critical: no WiFi-off, no "Connection issue"
    expect(copy.headline).not.toMatch(/Connection/);
  });

  it('L1 transcription transient → Mic icon + "couldn\'t transcribe the audio" body', () => {
    const copy = failureCopyFor({
      failureCategory: 'transient',
      reviewReason: 'Processing failed during transcription. Try retrying this visit, or contact support if it keeps failing.',
      inputMode: 'audio_upload',
    });
    expect(copy.Icon).toBe(Mic);
    expect(copy.body).toMatch(/couldn’t transcribe|couldn't transcribe/);
    expect(copy.body).toMatch(/audio is saved/);
    expect(copy.headline).not.toMatch(/Connection/);
  });

  it('L7 automation transient → Wrench + "couldn\'t auto-generate codes / Rx" body', () => {
    const copy = failureCopyFor({
      failureCategory: 'transient',
      reviewReason: 'Processing failed during codes / Rx / referrals generation. Try retrying this visit.',
      inputMode: 'audio_upload',
    });
    expect(copy.Icon).toBe(Wrench);
    expect(copy.headline).toMatch(/Couldn’t finalize coding|Couldn't finalize coding/);
    expect(copy.body).toMatch(/auto-generate codes/);
  });

  it('L4 soap_drafting transient → Wrench + "couldn\'t draft the note" body', () => {
    const copy = failureCopyFor({
      failureCategory: 'transient',
      reviewReason: 'Processing failed during SOAP drafting. Try retrying this visit, or contact support if it keeps failing.',
      inputMode: 'voice_dictation',
    });
    expect(copy.Icon).toBe(Wrench);
    expect(copy.body).toMatch(/couldn’t draft the note|couldn't draft the note/);
    expect(copy.body).toMatch(/transcript is saved/);
  });

  it('unknown-layer transient → AlertTriangle generic interrupted copy (NOT WiFi-off)', () => {
    const copy = failureCopyFor({
      failureCategory: 'transient',
      reviewReason: 'Some genuinely-unknown failure shape that does not match any layer phrase.',
      inputMode: 'audio_upload',
    });
    expect(copy.Icon).toBe(AlertTriangle);
    expect(copy.headline).toMatch(/Processing interrupted/);
    expect(copy.headline).not.toMatch(/Connection/);
  });
});

describe('failureCopyFor — null / unknown category', () => {
  it('null category → RefreshCw + generic copy (pre-categorization rows)', () => {
    const copy = failureCopyFor({
      failureCategory: null,
      reviewReason: null,
      inputMode: null,
    });
    expect(copy.Icon).toBe(RefreshCw);
    expect(copy.headline).toMatch(/Processing failed/);
  });

  it('undefined category → RefreshCw fallback', () => {
    const copy = failureCopyFor({
      failureCategory: undefined,
      reviewReason: undefined,
      inputMode: undefined,
    });
    expect(copy.Icon).toBe(RefreshCw);
  });
});

describe('failureCopyFor — the WiFi-off + Connection-issue template is gone', () => {
  it('no input combination produces a "Connection issue" headline', () => {
    // Sweep the cartesian product of (category × layer × inputMode) and
    // assert "Connection issue" never appears in any rendered headline.
    // This is the regression-guard that the prod-fix's load-bearing
    // outcome (kill the WiFi-off-for-everything pattern) holds.
    const categories: Array<'transient' | 'permanent' | 'provider_down' | null> = [
      'transient',
      'permanent',
      'provider_down',
      null,
    ];
    const reasons = [
      'Processing failed during polish.',
      'Processing failed during transcription.',
      'Processing failed during entity extraction.',
      'Processing failed during SOAP drafting.',
      'Processing failed during clinical audit.',
      'Processing failed during codes / Rx / referrals generation.',
      'Recording is 1.0s; need at least 3s of audio.',
      'Audio decode failed — unsupported container.',
      null,
    ];
    const modes: Array<'audio_upload' | 'voice_dictation' | 'text_notes'> = [
      'audio_upload',
      'voice_dictation',
      'text_notes',
    ];
    for (const failureCategory of categories) {
      for (const reviewReason of reasons) {
        for (const inputMode of modes) {
          const copy = failureCopyFor({
            failureCategory,
            reviewReason,
            inputMode,
          });
          expect(copy.headline, `${failureCategory}/${reviewReason}/${inputMode}`).not.toMatch(
            /Connection issue/i,
          );
        }
      }
    }
  });
});
