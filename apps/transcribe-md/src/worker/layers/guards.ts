// ============================================================================
// Round 3 PR-D — pipeline-entry guards (audit A06-P0-001)
// ----------------------------------------------------------------------------
// Deterministic floor for the AI pipeline: refuse to generate a SOAP from
// an audio/transcript that can't possibly support one. Closes the
// "empty audio → fabricated SOAP" hole the audit found ("enforced by
// Claude prompt obedience only; one model-drift away from disaster").
//
// PipelineRejectError is the canonical signal the worker's catch block
// reads. error-categorize.ts maps it to ErrorCategory='permanent' (no
// point retrying — same audio, same outcome). worker.ts's
// buildUserFacingFailureReason() reads the humanReason off the error
// directly, so the doctor sees the precise reason in the visit's
// review banner instead of a generic "processing failed".
//
// Each rejection emits an audit row (PIPELINE_REJECTED_*) so the admin
// dashboard + forensics can reconstruct exactly why visits landed in
// needsReview.
// ============================================================================

import { logWorkerAudit } from "@/worker/worker-audit";

/** Audio shorter than this is rejected outright (Guard A). 3s is enough
 *  for the shortest legitimate dictation ("Patient stable, follow up in
 *  six weeks"); anything shorter is overwhelmingly accidental taps. */
export const MIN_AUDIO_DURATION_SEC = 3;

/** Transcripts shorter than this are rejected (Guard B). 10 words covers
 *  even the most terse dictation; fewer means Deepgram heard a cough or
 *  silence and any Claude SOAP would be cloth-from-thin-air. */
export const MIN_TRANSCRIPT_WORD_COUNT = 10;

/**
 * Custom error type so the worker's catch block can distinguish
 * pipeline-rejection (deterministic, never-retry, doctor-actionable)
 * from generic upstream failures.
 */
export class PipelineRejectError extends Error {
  /** Stable machine-readable reason. Used by audit metadata + tests. */
  public readonly reasonCode:
    | "audio_too_short"
    | "transcript_too_short"
    | "fabrication_flagged";
  /** Human-readable; rendered as the visit's reviewReason banner. */
  public readonly humanReason: string;

  constructor(
    reasonCode:
      | "audio_too_short"
      | "transcript_too_short"
      | "fabrication_flagged",
    humanReason: string,
  ) {
    super(humanReason);
    this.name = "PipelineRejectError";
    this.reasonCode = reasonCode;
    this.humanReason = humanReason;
  }
}

export function isPipelineRejectError(
  err: unknown,
): err is PipelineRejectError {
  return (
    err instanceof Error &&
    err.name === "PipelineRejectError" &&
    typeof (err as PipelineRejectError).reasonCode === "string"
  );
}

/** Word counter — splits on Unicode whitespace and drops empties.
 *  Same heuristic Deepgram uses internally for `words[]` length, so
 *  the count matches the per-utterance word totals reviewers see. */
export function countWords(text: string): number {
  if (!text) return 0;
  return text.split(/\s+/).filter(Boolean).length;
}

/**
 * Round 3 PR-D — A06-P0-001 empty-transcript guard.
 *
 * Run after Layer 1 (or Layer 1b) writes audioDurationSec +
 * transcriptText to the visit row. Throws PipelineRejectError if the
 * inputs can't support a SOAP. Emits an audit row in either case so
 * the dashboard can reason about pipeline rejections separately from
 * upstream failures.
 *
 * Order matters: Guard A (duration) before Guard B (word count). A
 * 0-second clip never has words, but the duration error is more
 * actionable for the doctor ("re-record longer") than the word-count
 * error ("re-record with audible speech").
 */
export async function assertSufficientTranscript(input: {
  visitId: string;
  practiceId: string;
  userId: string | null;
  durationSec: number;
  transcriptText: string;
}): Promise<void> {
  // Guard A — audio duration.
  if (
    !Number.isFinite(input.durationSec) ||
    input.durationSec < MIN_AUDIO_DURATION_SEC
  ) {
    const durFmt = Number.isFinite(input.durationSec)
      ? input.durationSec.toFixed(1)
      : "unknown";
    await logWorkerAudit({
      action: "PIPELINE_REJECTED_TOO_SHORT",
      targetId: input.visitId,
      targetType: "TranscribeVisit",
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      errorCode: "audio_too_short",
      metadata: {
        durationSec: input.durationSec,
        threshold: MIN_AUDIO_DURATION_SEC,
      },
    });
    throw new PipelineRejectError(
      "audio_too_short",
      `Recording is ${durFmt}s; need at least ${MIN_AUDIO_DURATION_SEC}s of audio. Re-record with the conversation captured.`,
    );
  }

  // Guard B — transcript word count.
  const wordCount = countWords(input.transcriptText);
  if (wordCount < MIN_TRANSCRIPT_WORD_COUNT) {
    await logWorkerAudit({
      action: "PIPELINE_REJECTED_INSUFFICIENT_TRANSCRIPT",
      targetId: input.visitId,
      targetType: "TranscribeVisit",
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      errorCode: "transcript_too_short",
      metadata: {
        wordCount,
        threshold: MIN_TRANSCRIPT_WORD_COUNT,
        durationSec: input.durationSec,
      },
    });
    throw new PipelineRejectError(
      "transcript_too_short",
      `Transcript has ${wordCount} word${wordCount === 1 ? "" : "s"}; pipeline halted to prevent fabricated SOAP. Re-record with audible speech.`,
    );
  }
}
