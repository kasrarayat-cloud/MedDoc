import { afterEach, describe, expect, it, vi } from 'vitest';

import { configuredTemplateTwinLocalOcr } from '../static-asset-ocr';

afterEach(() => {
  delete process.env.TEMPLATE_TWIN_LOCAL_OCR_EXECUTABLE;
});

describe('configured local static-asset OCR', () => {
  it('is explicitly blocked when no absolute local executable is configured', async () => {
    await expect(
      configuredTemplateTwinLocalOcr({ executablePath: '' }),
    ).resolves.toMatchObject({
      ready: false,
      code: 'TT_STATIC_ASSET_LOCAL_OCR_NOT_CONFIGURED',
    });
    await expect(
      configuredTemplateTwinLocalOcr({ executablePath: 'tesseract' }),
    ).resolves.toMatchObject({
      ready: false,
      code: 'TT_STATIC_ASSET_LOCAL_OCR_UNAVAILABLE',
    });
  });

  it('uses a bounded shell-free local Tesseract process and reports its exact version', async () => {
    const runner = vi
      .fn()
      .mockResolvedValueOnce({
        exitCode: 0,
        timedOut: false,
        outputLimitExceeded: false,
        stdout: new TextEncoder().encode('tesseract 5.3.4\n'),
        stderr: new Uint8Array(),
      })
      .mockResolvedValueOnce({
        exitCode: 0,
        timedOut: false,
        outputLimitExceeded: false,
        stdout: new TextEncoder().encode('Synthetic Clinic'),
        stderr: new Uint8Array(),
      });
    const readiness = await configuredTemplateTwinLocalOcr({
      executablePath: '/synthetic/bin/tesseract',
      runner,
    });
    expect(readiness).toMatchObject({
      ready: true,
      engineVersion: 'tesseract/5.3.4',
    });
    if (!readiness.ready) throw new Error('Synthetic OCR should be ready.');
    await expect(
      readiness.ocr.scan({
        bytes: Uint8Array.from([1, 2, 3]),
        mimeType: 'image/png',
        width: 1,
        height: 1,
        maxCharacters: 100,
      }),
    ).resolves.toEqual({
      local: true,
      complete: true,
      engineVersion: 'tesseract/5.3.4',
      text: 'Synthetic Clinic',
    });
    expect(runner.mock.calls[1]?.[0]).toMatchObject({
      executable: '/synthetic/bin/tesseract',
      args: ['stdin', 'stdout', '--dpi', '300', '-l', 'eng'],
      stdin: Uint8Array.from([1, 2, 3]),
      timeoutMs: 20_000,
      maxStdoutBytes: 404,
    });
  });

  it('fails the OCR operation on timeout or output overflow', async () => {
    const runner = vi
      .fn()
      .mockResolvedValueOnce({
        exitCode: 0,
        timedOut: false,
        outputLimitExceeded: false,
        stdout: new TextEncoder().encode('tesseract 5.3.4\n'),
        stderr: new Uint8Array(),
      })
      .mockResolvedValueOnce({
        exitCode: null,
        timedOut: true,
        outputLimitExceeded: true,
        stdout: new Uint8Array(),
        stderr: new Uint8Array(),
      });
    const readiness = await configuredTemplateTwinLocalOcr({
      executablePath: '/synthetic/bin/tesseract',
      runner,
    });
    if (!readiness.ready) throw new Error('Synthetic OCR should be ready.');
    await expect(
      readiness.ocr.scan({
        bytes: Uint8Array.from([1]),
        mimeType: 'image/png',
        width: 1,
        height: 1,
        maxCharacters: 100,
      }),
    ).rejects.toThrow('TT_STATIC_ASSET_OCR_EXECUTION_FAILED');
  });
});
