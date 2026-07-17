export class TemplateTwinStagingQaRequestError extends Error {
  constructor(readonly code: "REQUEST_TOO_LARGE" | "INVALID_JSON") {
    super(
      code === "REQUEST_TOO_LARGE"
        ? "The synthetic QA request is too large."
        : "The synthetic QA request is malformed.",
    );
    this.name = "TemplateTwinStagingQaRequestError";
  }
}

/** Read actual streamed bytes under a hard ceiling before JSON.parse. */
export async function readBoundedTemplateTwinStagingQaJson(
  request: Request,
  maxBytes: number,
): Promise<unknown> {
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1) {
    throw new TypeError("maxBytes must be a positive safe integer");
  }
  const contentType = request.headers
    .get("content-type")
    ?.split(";")[0]
    ?.trim();
  if (contentType !== "application/json" || !request.body) {
    throw new TemplateTwinStagingQaRequestError("INVALID_JSON");
  }
  const claimed = request.headers.get("content-length");
  if (claimed) {
    const parsed = Number(claimed);
    if (!Number.isSafeInteger(parsed) || parsed < 0) {
      throw new TemplateTwinStagingQaRequestError("INVALID_JSON");
    }
    if (parsed > maxBytes) {
      throw new TemplateTwinStagingQaRequestError("REQUEST_TOO_LARGE");
    }
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      total += chunk.value.byteLength;
      if (total > maxBytes) {
        await reader.cancel();
        throw new TemplateTwinStagingQaRequestError("REQUEST_TOO_LARGE");
      }
      chunks.push(chunk.value);
    }
  } catch (error) {
    if (error instanceof TemplateTwinStagingQaRequestError) throw error;
    throw new TemplateTwinStagingQaRequestError("INVALID_JSON");
  } finally {
    reader.releaseLock();
  }

  try {
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new TemplateTwinStagingQaRequestError("INVALID_JSON");
  }
}
