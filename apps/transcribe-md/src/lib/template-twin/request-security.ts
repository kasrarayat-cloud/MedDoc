/** Same-origin check for cookie-authenticated JSON/multipart mutation routes. */
export function isSameOriginTemplateTwinMutation(request: Request): boolean {
  const fetchSite = request.headers.get('sec-fetch-site');
  if (fetchSite === 'cross-site') return false;

  const claimed = request.headers.get('origin') ?? request.headers.get('referer');
  if (!claimed) return false;

  try {
    const claimedUrl = new URL(claimed);
    const requestUrl = new URL(request.url);
    const host =
      request.headers.get('x-forwarded-host')?.split(',')[0]?.trim() ||
      request.headers.get('host') ||
      requestUrl.host;
    const protocol =
      request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim() ||
      requestUrl.protocol.replace(':', '');
    return claimedUrl.host === host && claimedUrl.protocol === `${protocol}:`;
  } catch {
    return false;
  }
}

export class TemplateTwinMultipartError extends Error {
  readonly code: 'MULTIPART_TOO_LARGE' | 'MULTIPART_INVALID';

  constructor(code: TemplateTwinMultipartError['code']) {
    super(
      code === 'MULTIPART_TOO_LARGE'
        ? 'The multipart request exceeds the supported size.'
        : 'The multipart request is malformed.',
    );
    this.name = 'TemplateTwinMultipartError';
    this.code = code;
  }
}

/**
 * Reads the request stream with a hard byte ceiling before invoking a
 * multipart parser. This does not trust Content-Length and therefore covers
 * missing, lying, and chunked transfer metadata.
 */
export async function boundedMultipartFormData(
  request: Request,
  maxBytes: number,
): Promise<FormData> {
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1) {
    throw new TypeError('maxBytes must be a positive safe integer');
  }
  const contentType = request.headers.get('content-type') ?? '';
  if (!/^multipart\/form-data\s*;/i.test(contentType) || !/\bboundary=/i.test(contentType)) {
    throw new TemplateTwinMultipartError('MULTIPART_INVALID');
  }
  if (!request.body) throw new TemplateTwinMultipartError('MULTIPART_INVALID');

  const chunks: Uint8Array[] = [];
  let total = 0;
  const reader = request.body.getReader();
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      total += next.value.byteLength;
      if (total > maxBytes) {
        await reader.cancel();
        throw new TemplateTwinMultipartError('MULTIPART_TOO_LARGE');
      }
      chunks.push(next.value);
    }
  } catch (error) {
    if (error instanceof TemplateTwinMultipartError) throw error;
    throw new TemplateTwinMultipartError('MULTIPART_INVALID');
  } finally {
    reader.releaseLock();
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return await new Response(bytes, {
      headers: { 'content-type': contentType },
    }).formData();
  } catch {
    throw new TemplateTwinMultipartError('MULTIPART_INVALID');
  }
}

export function isMultipartFile(value: FormDataEntryValue | null): value is File {
  return Boolean(
    value &&
      typeof value === 'object' &&
      typeof (value as File).name === 'string' &&
      Number.isSafeInteger((value as File).size) &&
      typeof (value as File).arrayBuffer === 'function',
  );
}
