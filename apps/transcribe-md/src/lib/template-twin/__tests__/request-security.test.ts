import { describe, expect, it } from 'vitest';

import {
  boundedMultipartFormData,
  isMultipartFile,
  TemplateTwinMultipartError,
} from '../request-security';

async function multipartBytes(size = 32): Promise<{
  bytes: Uint8Array;
  contentType: string;
}> {
  const form = new FormData();
  form.set(
    'file',
    new File([new Uint8Array(size).fill(65)], 'synthetic.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }),
  );
  const request = new Request('https://app.synthetic.test/upload', {
    method: 'POST',
    body: form,
  });
  return {
    bytes: new Uint8Array(await request.arrayBuffer()),
    contentType: request.headers.get('content-type')!,
  };
}

function streamedRequest(
  bytes: Uint8Array,
  contentType: string,
  contentLength?: string,
): Request {
  const midpoint = Math.max(1, Math.floor(bytes.length / 2));
  const chunks = [bytes.slice(0, midpoint), bytes.slice(midpoint)];
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      const chunk = chunks.shift();
      if (chunk) controller.enqueue(chunk);
      else controller.close();
    },
  });
  const headers = new Headers({ 'content-type': contentType });
  if (contentLength !== undefined) headers.set('content-length', contentLength);
  return new Request('https://app.synthetic.test/upload', {
    method: 'POST',
    headers,
    body,
    duplex: 'half',
  } as RequestInit & { duplex: 'half' });
}

describe('Template Twin bounded multipart parsing', () => {
  it('parses a chunked request without Content-Length under the actual limit', async () => {
    const { bytes, contentType } = await multipartBytes();
    const parsed = await boundedMultipartFormData(
      streamedRequest(bytes, contentType),
      bytes.length,
    );
    expect(isMultipartFile(parsed.get('file'))).toBe(true);
  });

  it('rejects the actual bytes when Content-Length is missing or lies', async () => {
    const { bytes, contentType } = await multipartBytes(128);
    for (const request of [
      streamedRequest(bytes, contentType),
      streamedRequest(bytes, contentType, '1'),
    ]) {
      await expect(
        boundedMultipartFormData(request, bytes.length - 1),
      ).rejects.toMatchObject({
        code: 'MULTIPART_TOO_LARGE',
      } satisfies Partial<TemplateTwinMultipartError>);
    }
  });

  it('rejects missing boundaries and malformed bodies', async () => {
    await expect(
      boundedMultipartFormData(
        new Request('https://app.synthetic.test/upload', {
          method: 'POST',
          headers: { 'content-type': 'multipart/form-data' },
          body: 'synthetic',
        }),
        1024,
      ),
    ).rejects.toMatchObject({
      code: 'MULTIPART_INVALID',
    } satisfies Partial<TemplateTwinMultipartError>);
  });
});
