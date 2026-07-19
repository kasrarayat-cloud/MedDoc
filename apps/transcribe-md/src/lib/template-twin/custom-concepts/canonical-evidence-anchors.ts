import { createHash } from "node:crypto";

export const TEMPLATE_TWIN_CUSTOM_EVIDENCE_MAX_CONTEXT_CHARS = 80_000;

export type CanonicalCustomEvidenceAnchorResult =
  | {
      ok: true;
      anchors: Array<{
        evidenceAnchorId: string;
        quote: string;
        sourceTranscriptOffsets: { start: number; end: number };
      }>;
    }
  | {
      ok: false;
      code: "CONTEXT_LENGTH_INVALID" | "ANCHOR_SET_INVALID";
    };

function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableJson(item)).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

/** Provider-free canonical sentence/line anchors shared by extraction and gates. */
export function buildCanonicalCustomEvidenceAnchors(input: {
  mode: "conversation" | "dictation" | "text";
  contextText: string;
}): CanonicalCustomEvidenceAnchorResult {
  if (
    input.contextText.length === 0 ||
    input.contextText.length > TEMPLATE_TWIN_CUSTOM_EVIDENCE_MAX_CONTEXT_CHARS
  ) {
    return { ok: false, code: "CONTEXT_LENGTH_INVALID" };
  }

  const spans: Array<{ start: number; end: number }> = [];
  const appendBounded = (rawStart: number, rawEnd: number): void => {
    let start = rawStart;
    let end = rawEnd;
    while (start < end && /\s/u.test(input.contextText[start] ?? ""))
      start += 1;
    while (end > start && /\s/u.test(input.contextText[end - 1] ?? ""))
      end -= 1;
    while (end - start > 4_000) {
      const hardEnd = start + 4_000;
      const window = input.contextText.slice(start, hardEnd);
      const whitespace = Math.max(
        window.lastIndexOf(" "),
        window.lastIndexOf("\t"),
      );
      const chunkEnd = whitespace > 0 ? start + whitespace : hardEnd;
      spans.push({ start, end: chunkEnd });
      start = chunkEnd;
      while (start < end && /\s/u.test(input.contextText[start] ?? "")) {
        start += 1;
      }
    }
    if (start < end) spans.push({ start, end });
  };

  const boundary = /(?:[.!?]+(?=\s|$)|\n+)/gu;
  let cursor = 0;
  for (const match of input.contextText.matchAll(boundary)) {
    const boundaryStart = match.index;
    const boundaryEnd = boundaryStart + match[0].length;
    appendBounded(cursor, boundaryEnd);
    cursor = boundaryEnd;
  }
  appendBounded(cursor, input.contextText.length);
  if (spans.length === 0 || spans.length > 500) {
    return { ok: false, code: "ANCHOR_SET_INVALID" };
  }

  return {
    ok: true,
    anchors: spans.map(({ start, end }) => {
      const quote = input.contextText.slice(start, end);
      return {
        evidenceAnchorId: `ttev_${sha256(
          stableJson({ mode: input.mode, start, end, quote }),
        ).slice(0, 24)}`,
        quote,
        sourceTranscriptOffsets: { start, end },
      };
    }),
  };
}
