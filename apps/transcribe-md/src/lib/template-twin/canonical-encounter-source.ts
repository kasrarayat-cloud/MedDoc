import { createHash } from "node:crypto";

import type { DeepgramUtterance } from "@meddoc/ai";

import { markUnclearTranscript } from "@/worker/layers/transcript-clarity";

import type { TemplateTwinEncounterSourceReceipt } from "./ir";

export const TEMPLATE_TWIN_ENCOUNTER_SOURCE_RECEIPT_VERSION =
  "template-twin-encounter-source-v1" as const;

export type TemplateTwinEncounterInputMode =
  | "conversation"
  | "dictation"
  | "text";

export interface ReconstructableTemplateTwinVisitSource {
  inputMode?: string | null;
  rawTextInput?: string | null;
  transcriptText?: string | null;
  transcriptRaw?: unknown;
  speakerMap?: unknown;
}

export type ReconstructedTemplateTwinEncounterSource =
  | {
      ok: true;
      mode: TemplateTwinEncounterInputMode;
      contextText: string;
      receipt: TemplateTwinEncounterSourceReceipt;
    }
  | {
      ok: false;
      code:
        | "SOURCE_MODE_UNSUPPORTED"
        | "SOURCE_TEXT_MISSING"
        | "SOURCE_TRANSCRIPT_MALFORMED"
        | "SOURCE_SPEAKER_MAP_MALFORMED";
    };

type SpeakerRole = "doctor" | "patient" | "family" | "other" | "unknown";
type CanonicalSpeakerMap = Record<string, { role: SpeakerRole }>;

const SPEAKER_ROLES = new Set<SpeakerRole>([
  "doctor",
  "patient",
  "family",
  "other",
  "unknown",
]);

function sha256Utf8(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function finiteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function parseWords(value: unknown): DeepgramUtterance["words"] | null {
  if (value === undefined) return [];
  if (!Array.isArray(value)) return null;
  const words: DeepgramUtterance["words"] = [];
  for (const candidate of value) {
    if (
      !isRecord(candidate) ||
      typeof candidate.word !== "string" ||
      !finiteNumber(candidate.start) ||
      !finiteNumber(candidate.end) ||
      !finiteNumber(candidate.confidence) ||
      (candidate.punctuated_word !== undefined &&
        typeof candidate.punctuated_word !== "string") ||
      (candidate.speaker !== undefined && !finiteNumber(candidate.speaker))
    ) {
      return null;
    }
    words.push({
      word: candidate.word,
      start: candidate.start,
      end: candidate.end,
      confidence: candidate.confidence,
      ...(candidate.speaker === undefined
        ? {}
        : { speaker: candidate.speaker }),
      ...(candidate.punctuated_word === undefined
        ? {}
        : { punctuated_word: candidate.punctuated_word }),
    });
  }
  return words;
}

function parseUtterances(value: unknown): DeepgramUtterance[] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const utterances: DeepgramUtterance[] = [];
  for (const candidate of value) {
    if (
      !isRecord(candidate) ||
      typeof candidate.transcript !== "string" ||
      !candidate.transcript.trim() ||
      !finiteNumber(candidate.start) ||
      !finiteNumber(candidate.end) ||
      !finiteNumber(candidate.confidence) ||
      !finiteNumber(candidate.channel) ||
      (candidate.speaker !== undefined && !finiteNumber(candidate.speaker)) ||
      (candidate.id !== undefined && typeof candidate.id !== "string")
    ) {
      return null;
    }
    const words = parseWords(candidate.words);
    if (!words) return null;
    utterances.push({
      start: candidate.start,
      end: candidate.end,
      confidence: candidate.confidence,
      channel: candidate.channel,
      transcript: candidate.transcript,
      words,
      ...(candidate.speaker === undefined
        ? {}
        : { speaker: candidate.speaker }),
      ...(candidate.id === undefined ? {} : { id: candidate.id }),
    });
  }
  return utterances;
}

function parseSpeakerMap(value: unknown): CanonicalSpeakerMap | null {
  if (!isRecord(value)) return null;
  const parsed: CanonicalSpeakerMap = {};
  for (const [speakerId, candidate] of Object.entries(value)) {
    if (
      !/^\d+$/.test(speakerId) ||
      !isRecord(candidate) ||
      typeof candidate.role !== "string" ||
      !SPEAKER_ROLES.has(candidate.role as SpeakerRole)
    ) {
      return null;
    }
    parsed[speakerId] = { role: candidate.role as SpeakerRole };
  }
  return parsed;
}

function formatRoleLabeledLine(
  utterance: DeepgramUtterance,
  speakerMap: CanonicalSpeakerMap,
): string {
  const speakerKey =
    typeof utterance.speaker === "number"
      ? String(utterance.speaker)
      : "unknown";
  const role = speakerMap[speakerKey]?.role ?? "unknown";
  const displayRole = role.charAt(0).toUpperCase() + role.slice(1);
  const timestamp = Math.max(0, Math.floor(utterance.start ?? 0));
  const minutes = Math.floor(timestamp / 60);
  const seconds = (timestamp % 60).toString().padStart(2, "0");
  return `[${displayRole} #${speakerKey}, ${minutes}:${seconds}]: ${markUnclearTranscript(utterance)}`;
}

/**
 * The single canonical conversation formatter used by Layer 3 and by every
 * Template Twin evidence gate. Keeping both callers on this pure function is
 * what makes a receipt reproducible after the worker has exited.
 */
export function buildRoleLabeledTranscript(
  utterances: DeepgramUtterance[],
  speakerMap: CanonicalSpeakerMap,
): string {
  return utterances
    .map((utterance) => formatRoleLabeledLine(utterance, speakerMap))
    .join("\n");
}

export function createTemplateTwinEncounterSourceReceipt(input: {
  mode: TemplateTwinEncounterInputMode;
  contextText: string;
}): TemplateTwinEncounterSourceReceipt {
  return {
    receiptVersion: TEMPLATE_TWIN_ENCOUNTER_SOURCE_RECEIPT_VERSION,
    mode: input.mode,
    canonicalSourceSha256: sha256Utf8(input.contextText),
    canonicalSourceLength: input.contextText.length,
  };
}

/** Rebuild exactly the string passed to Layer 3 without any provider call. */
export function reconstructTemplateTwinEncounterSource(
  visit: ReconstructableTemplateTwinVisitSource,
): ReconstructedTemplateTwinEncounterSource {
  if (visit.inputMode === "text_notes") {
    if (typeof visit.rawTextInput !== "string" || !visit.rawTextInput.trim()) {
      return { ok: false, code: "SOURCE_TEXT_MISSING" };
    }
    const contextText = visit.rawTextInput.trim();
    return {
      ok: true,
      mode: "text",
      contextText,
      receipt: createTemplateTwinEncounterSourceReceipt({
        mode: "text",
        contextText,
      }),
    };
  }

  if (visit.inputMode === "voice_dictation") {
    if (
      typeof visit.transcriptText !== "string" ||
      !visit.transcriptText.trim()
    ) {
      return { ok: false, code: "SOURCE_TEXT_MISSING" };
    }
    const contextText = visit.transcriptText.trim();
    return {
      ok: true,
      mode: "dictation",
      contextText,
      receipt: createTemplateTwinEncounterSourceReceipt({
        mode: "dictation",
        contextText,
      }),
    };
  }

  if (visit.inputMode === "audio_upload") {
    if (!isRecord(visit.transcriptRaw)) {
      return { ok: false, code: "SOURCE_TRANSCRIPT_MALFORMED" };
    }
    const results = visit.transcriptRaw.results;
    if (!isRecord(results)) {
      return { ok: false, code: "SOURCE_TRANSCRIPT_MALFORMED" };
    }
    const utterances = parseUtterances(results.utterances);
    if (!utterances) {
      return { ok: false, code: "SOURCE_TRANSCRIPT_MALFORMED" };
    }
    const speakerMap = parseSpeakerMap(visit.speakerMap);
    if (!speakerMap) {
      return { ok: false, code: "SOURCE_SPEAKER_MAP_MALFORMED" };
    }
    const contextText = buildRoleLabeledTranscript(utterances, speakerMap);
    if (!contextText) {
      return { ok: false, code: "SOURCE_TEXT_MISSING" };
    }
    return {
      ok: true,
      mode: "conversation",
      contextText,
      receipt: createTemplateTwinEncounterSourceReceipt({
        mode: "conversation",
        contextText,
      }),
    };
  }

  return { ok: false, code: "SOURCE_MODE_UNSUPPORTED" };
}
