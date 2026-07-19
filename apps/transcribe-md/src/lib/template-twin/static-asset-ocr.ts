import { constants as fsConstants } from 'node:fs';
import { access, stat } from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';

import type { LocalStaticAssetOcr } from './static-assets';

const EXECUTABLE_ENV = 'TEMPLATE_TWIN_LOCAL_OCR_EXECUTABLE';
const VERSION_TIMEOUT_MS = 5_000;
const OCR_TIMEOUT_MS = 20_000;
const MAX_DIAGNOSTIC_BYTES = 8 * 1024;
const MAX_INPUT_BYTES = 5 * 1024 * 1024;

export type TemplateTwinLocalOcrReadiness =
  | {
      readonly ready: true;
      readonly code: 'TT_STATIC_ASSET_LOCAL_OCR_READY';
      readonly message: string;
      readonly engineVersion: string;
      readonly ocr: LocalStaticAssetOcr;
    }
  | {
      readonly ready: false;
      readonly code:
        | 'TT_STATIC_ASSET_LOCAL_OCR_NOT_CONFIGURED'
        | 'TT_STATIC_ASSET_LOCAL_OCR_UNAVAILABLE';
      readonly message: string;
    };

interface ProcessResult {
  readonly exitCode: number | null;
  readonly timedOut: boolean;
  readonly stdout: Uint8Array;
  readonly stderr: Uint8Array;
  readonly outputLimitExceeded: boolean;
}

type LocalProcessRunner = (input: {
  executable: string;
  args: readonly string[];
  stdin?: Uint8Array;
  timeoutMs: number;
  maxStdoutBytes: number;
}) => Promise<ProcessResult>;

/**
 * Resolve the only safe-alpha OCR implementation. Nothing is installed or
 * downloaded here: an operator must explicitly configure an absolute path to
 * an already-installed local Tesseract executable. Missing or unhealthy OCR
 * is a readiness blocker, never a reason to skip image inspection.
 */
export async function configuredTemplateTwinLocalOcr(input: {
  executablePath?: string | null;
  runner?: LocalProcessRunner;
} = {}): Promise<TemplateTwinLocalOcrReadiness> {
  const configured = (
    input.executablePath ?? process.env[EXECUTABLE_ENV] ?? ''
  ).trim();
  if (!configured) {
    return {
      ready: false,
      code: 'TT_STATIC_ASSET_LOCAL_OCR_NOT_CONFIGURED',
      message:
        'Static-image review is blocked until a bounded local OCR executable is configured.',
    };
  }
  if (!path.isAbsolute(configured)) {
    return unavailable();
  }
  if (!input.runner) {
    try {
      const info = await stat(configured);
      if (!info.isFile()) return unavailable();
      await access(configured, fsConstants.X_OK);
    } catch {
      return unavailable();
    }
  }
  const runner = input.runner ?? runLocalProcess;
  let versionResult: ProcessResult;
  try {
    versionResult = await runner({
      executable: configured,
      args: ['--version'],
      timeoutMs: VERSION_TIMEOUT_MS,
      maxStdoutBytes: MAX_DIAGNOSTIC_BYTES,
    });
  } catch {
    return unavailable();
  }
  const engineVersion = tesseractVersion(versionResult);
  if (!engineVersion) return unavailable();

  const ocr: LocalStaticAssetOcr = {
    async scan(request) {
      if (
        request.mimeType !== 'image/png' ||
        request.bytes.byteLength < 1 ||
        request.bytes.byteLength > MAX_INPUT_BYTES ||
        request.maxCharacters < 1 ||
        request.maxCharacters > 10_000
      ) {
        throw new Error('TT_STATIC_ASSET_OCR_INPUT_INVALID');
      }
      const result = await runner({
        executable: configured,
        args: ['stdin', 'stdout', '--dpi', '300', '-l', 'eng'],
        stdin: request.bytes,
        timeoutMs: OCR_TIMEOUT_MS,
        maxStdoutBytes: request.maxCharacters * 4 + 4,
      });
      if (
        result.exitCode !== 0 ||
        result.timedOut ||
        result.outputLimitExceeded ||
        result.stderr.byteLength > MAX_DIAGNOSTIC_BYTES
      ) {
        throw new Error('TT_STATIC_ASSET_OCR_EXECUTION_FAILED');
      }
      const text = new TextDecoder('utf-8', { fatal: true }).decode(
        result.stdout,
      );
      if (text.length > request.maxCharacters) {
        throw new Error('TT_STATIC_ASSET_OCR_OUTPUT_LIMIT');
      }
      return {
        local: true,
        complete: true,
        engineVersion,
        text,
      };
    },
  };
  return {
    ready: true,
    code: 'TT_STATIC_ASSET_LOCAL_OCR_READY',
    message: 'Bounded local image-text inspection is available.',
    engineVersion,
    ocr,
  };
}

function unavailable(): TemplateTwinLocalOcrReadiness {
  return {
    ready: false,
    code: 'TT_STATIC_ASSET_LOCAL_OCR_UNAVAILABLE',
    message:
      'The configured local OCR executable is unavailable or failed its readiness check.',
  };
}

function tesseractVersion(result: ProcessResult): string | null {
  if (
    result.exitCode !== 0 ||
    result.timedOut ||
    result.outputLimitExceeded ||
    result.stderr.byteLength > MAX_DIAGNOSTIC_BYTES
  ) {
    return null;
  }
  let text: string;
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(result.stdout);
  } catch {
    return null;
  }
  const match = text.match(/^tesseract\s+([0-9]+(?:\.[0-9A-Za-z-]+){1,4})/i);
  return match ? `tesseract/${match[1]}` : null;
}

async function runLocalProcess(input: {
  executable: string;
  args: readonly string[];
  stdin?: Uint8Array;
  timeoutMs: number;
  maxStdoutBytes: number;
}): Promise<ProcessResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(input.executable, [...input.args], {
      shell: false,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'] as const,
      env: {
        NODE_ENV: process.env.NODE_ENV,
        LANG: 'C.UTF-8',
        PATH: process.env.PATH,
        TESSDATA_PREFIX: process.env.TESSDATA_PREFIX,
      },
    });
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    let stdoutBytes = 0;
    let stderrBytes = 0;
    let timedOut = false;
    let outputLimitExceeded = false;
    let settled = false;
    const finish = (result: ProcessResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill('SIGKILL');
    }, input.timeoutMs);
    child.once('error', (error: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(error);
    });
    child.stdout.on('data', (chunk: Buffer) => {
      stdoutBytes += chunk.byteLength;
      if (stdoutBytes > input.maxStdoutBytes) {
        outputLimitExceeded = true;
        child.kill('SIGKILL');
        return;
      }
      stdout.push(Buffer.from(chunk));
    });
    child.stderr.on('data', (chunk: Buffer) => {
      stderrBytes += chunk.byteLength;
      if (stderrBytes > MAX_DIAGNOSTIC_BYTES) {
        outputLimitExceeded = true;
        child.kill('SIGKILL');
        return;
      }
      stderr.push(Buffer.from(chunk));
    });
    child.once('close', (exitCode: number | null) => {
      finish({
        exitCode,
        timedOut,
        outputLimitExceeded,
        stdout: Uint8Array.from(Buffer.concat(stdout)),
        stderr: Uint8Array.from(Buffer.concat(stderr)),
      });
    });
    if (input.stdin) child.stdin.end(Buffer.from(input.stdin));
    else child.stdin.end();
  });
}
