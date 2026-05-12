// ============================================================================
// VisitFailedView copy helper — pure derivation of icon + headline +
// body + CTA shape from the visit row's failure metadata.
// ----------------------------------------------------------------------------
// Pre-fix, VisitFailedView used a single WiFi-off icon + "Connection
// issue" template for any `failureCategory='transient'` visit, regardless
// of which pipeline layer threw. That conflates two distinct failure
// shapes:
//
//   1. A client-side network failure (browser → server unreachable). The
//      visit ROW never represents this case — by the time the row exists
//      with status=FAILED, the server already saw the upload + ran the
//      pipeline; whatever broke happened ON the server. So a WiFi icon
//      on this surface is always wrong: client-side network failures
//      are caught in the retry handler's fetch() try/catch and surfaced
//      as a sonner toast, not the row's UI.
//
//   2. A server-side pipeline failure (Anthropic 5xx, rate-limit, layer
//      validator throw, transcript-shape problem, etc.). Today's
//      `transient` branch was rendering this case as "Connection issue"
//      + WiFi-off — misleading the doctor about where to look.
//
// This helper branches on (failureCategory, parsed-failed-layer, inputMode)
// and returns layer-aware copy. The PipelineRejectError shape (audio-too-
// short, transcript empty) carries its own actionable humanReason in the
// visit's reviewReason, which we surface verbatim above the helper-body.
//
// Brief-driven copy contract (preserved from the prod-fix prompt):
//   - L6 polish: "We drafted your note but couldn't finalize the polishing
//                 step. Your audio + draft are saved — try again."
//   - L1 transcription: "We couldn't transcribe the audio. Try re-uploading
//                       or recording again."
//   - L7 coding: "We finalized your note but couldn't auto-code. You can
//                sign as-is or retry to regenerate codes."
//
// inputMode awareness: text_notes failures must NOT say "audio file may
// be corrupt" — the deep-audit G11 finding showed this misleading the
// operator on visits with no audio at all.
// ============================================================================

import type { ComponentType, ReactNode } from 'react';
import {
  AlertTriangle,
  Cloud,
  FileText,
  FileX,
  Mic,
  RefreshCw,
  Wrench,
} from 'lucide-react';

export type VisitFailedInputMode =
  | 'audio_upload'
  | 'voice_dictation'
  | 'text_notes';

export type VisitFailedCategory =
  | 'transient'
  | 'permanent'
  | 'provider_down'
  | null
  | undefined;

export interface VisitFailedCopy {
  /** lucide icon component */
  Icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean }>;
  /** H2 headline (≤45 chars) */
  headline: string;
  /** Default body copy — overridden by the row's reviewReason when present.
   *  Kept short (≤180 chars) so the row's reviewReason can carry the
   *  load-bearing operator-facing detail. */
  body: string;
  /** Primary CTA label. */
  ctaLabel: string;
  /** When set, the primary CTA navigates rather than POSTing /retry.
   *  Used for permanent failures where the same input will fail the
   *  same way (re-upload required). */
  ctaHref?: string;
  /** Optional grey-text hint above the CTA row (e.g. wait-x-minutes). */
  hint?: ReactNode;
}

/** Detect which pipeline layer threw the failure by pattern-matching the
 *  worker's `buildUserFacingFailureReason()` output. The worker writes
 *  reasons of the shape "Processing failed during ${phrase}." where
 *  phrase ∈ { setup, transcription, speaker identification, entity
 *  extraction, SOAP drafting, clinical audit, polish, codes / Rx /
 *  referrals generation, finalization, processing }. PipelineRejectError
 *  (e.g. "Recording is 1.0s; need at least 3s of audio.") doesn't match
 *  the phrase pattern and is detected separately. */
export type FailedLayerHint =
  | 'transcription'
  | 'speaker_identification'
  | 'entity_extraction'
  | 'soap_drafting'
  | 'clinical_audit'
  | 'polish'
  | 'automation'
  | 'audio_input_invalid'
  | 'transcript_input_invalid'
  | null;

const PHRASE_TO_LAYER: ReadonlyArray<readonly [RegExp, FailedLayerHint]> = [
  [/processing failed during transcription/i, 'transcription'],
  [/processing failed during speaker identification/i, 'speaker_identification'],
  [/processing failed during entity extraction/i, 'entity_extraction'],
  [/processing failed during soap drafting/i, 'soap_drafting'],
  [/processing failed during clinical audit/i, 'clinical_audit'],
  [/processing failed during polish/i, 'polish'],
  [/processing failed during codes \/ rx \/ referrals generation/i, 'automation'],
];

export function detectFailedLayer(
  reviewReason: string | null | undefined,
  inputMode: VisitFailedInputMode | string | null | undefined,
): FailedLayerHint {
  if (!reviewReason) return null;
  // PipelineRejectError shapes — these are input-data rejections, not
  // mid-pipeline LLM failures. The phrase pattern doesn't match.
  if (/recording is \d/i.test(reviewReason)) return 'audio_input_invalid';
  if (/audio (?:duration|file).*(?:too short|too long|empty|silent)/i.test(reviewReason)) {
    return 'audio_input_invalid';
  }
  if (
    inputMode === 'text_notes' &&
    /(?:text|notes).*(?:too short|empty)/i.test(reviewReason)
  ) {
    return 'transcript_input_invalid';
  }
  for (const [pat, layer] of PHRASE_TO_LAYER) {
    if (pat.test(reviewReason)) return layer;
  }
  return null;
}

export function failureCopyFor(args: {
  failureCategory: VisitFailedCategory;
  reviewReason: string | null | undefined;
  inputMode: VisitFailedInputMode | string | null | undefined;
}): VisitFailedCopy {
  const layer = detectFailedLayer(args.reviewReason, args.inputMode);
  const inputMode = args.inputMode;
  const isText = inputMode === 'text_notes';

  // ── Permanent: the input is wrong; same input will fail again ────────
  if (args.failureCategory === 'permanent') {
    // Audio-specific input rejections (PipelineRejectError humanReason).
    if (layer === 'audio_input_invalid') {
      return {
        Icon: Mic,
        headline: 'Recording can’t be used',
        body:
          'The recording was too short, silent, or in an unsupported format. Re-record with the conversation captured.',
        ctaHref: '/visits/new',
        ctaLabel: 'Start a new visit',
      };
    }
    // Text-input rejections (or any permanent failure on a text_notes visit
    // — the audio-corrupt copy is misleading there per deep-audit G11).
    if (layer === 'transcript_input_invalid' || isText) {
      return {
        Icon: FileText,
        headline: 'Notes can’t be used',
        body:
          'The note text was empty or otherwise rejected by the pipeline. Re-enter the notes with the visit content and try again.',
        ctaHref: '/visits/new',
        ctaLabel: 'Start a new visit',
      };
    }
    // Audio-corrupt / unsupported-format catch-all (audio inputs).
    return {
      Icon: FileX,
      headline: 'Couldn’t process this audio',
      body:
        'The audio file may be corrupted or in an unsupported format. Re-upload using MP3, WAV, M4A, or WebM.',
      ctaHref: '/visits/new',
      ctaLabel: 'Upload new audio',
    };
  }

  // ── Provider down: known upstream outage, retry in a few minutes ─────
  if (args.failureCategory === 'provider_down') {
    return {
      Icon: Cloud,
      headline: 'Service temporarily unavailable',
      body:
        "Our transcription service is having an outage. We're aware and working on it. Please try again in 5–10 minutes.",
      ctaLabel: 'Try again',
      hint: 'Best to wait a few minutes before retrying.',
    };
  }

  // ── Transient: server-side blip / timeout. Layer-specific copy so the
  //    doctor knows what was lost and what was preserved. ──
  if (args.failureCategory === 'transient') {
    switch (layer) {
      case 'transcription':
      case 'speaker_identification':
        return {
          Icon: Mic,
          headline: 'Processing interrupted',
          body:
            'We couldn’t transcribe the audio on this attempt. Your audio is saved — try again, or re-upload if it keeps failing.',
          ctaLabel: 'Try again',
        };
      case 'entity_extraction':
      case 'soap_drafting':
        return {
          Icon: Wrench,
          headline: 'Processing interrupted',
          body:
            'We transcribed the audio but couldn’t draft the note on this attempt. Your transcript is saved — try again.',
          ctaLabel: 'Try again',
        };
      case 'clinical_audit':
      case 'polish':
        return {
          Icon: Wrench,
          headline: 'Couldn’t finalize this visit',
          body:
            'We drafted your note but couldn’t finalize the polish step. Your audio + draft are saved — try again.',
          ctaLabel: 'Try again',
        };
      case 'automation':
        // Note: with G9 (PR #224) live, an L7 fan-out failure no longer
        // transitions to status=FAILED — it lands READY + needsReview.
        // This branch is the legacy path + any future regression.
        return {
          Icon: Wrench,
          headline: 'Couldn’t finalize coding',
          body:
            'We finalized your note but couldn’t auto-generate codes / Rx. Open the visit to sign as-is or retry to regenerate.',
          ctaLabel: 'Try again',
        };
      default:
        // Unknown layer + transient = unclassified server-side blip.
        return {
          Icon: AlertTriangle,
          headline: 'Processing interrupted',
          body:
            'Something went wrong while generating your note. Try again — this usually works on the second attempt.',
          ctaLabel: 'Try again',
        };
    }
  }

  // ── Null / unknown category: pre-categorization rows + future shapes.
  //    Keep the original generic copy so existing FAILED rows that
  //    pre-date the categorizer don't suddenly look misclassified.
  return {
    Icon: RefreshCw,
    headline: 'Processing failed',
    body:
      'Something went wrong while generating your note. You can re-upload the audio to try again.',
    ctaLabel: 'Try again',
  };
}
