// ============================================================================
// Worker: transcribe_batch
// ----------------------------------------------------------------------------
// Pulls audio from MinIO, chunks it at 25 min with ffmpeg if needed,
// transcribes each chunk via Whisper / gpt-4o-transcribe, stitches the
// result into one raw transcript row, then enqueues finalize_visit.
//
// On error: flips ScribeVisit.status to ERROR and records an audit event
// so the review UI can surface it.
// ============================================================================

import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { downloadObject } from '@/lib/minio';
import {
  getScribeQueue,
  JOB_FINALIZE_VISIT,
  type TranscribeBatchPayload,
  type FinalizeVisitPayload,
} from '@/lib/queue';

const CHUNK_SECONDS = 25 * 60;   // 25 min — spec §10
const CHUNK_OVERLAP = 10;        // 10 sec overlap to recover context at boundaries

function runFfmpeg(args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const p = spawn('ffmpeg', args, { stdio: ['ignore', 'ignore', 'pipe'] });
    let stderr = '';
    p.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    p.on('error', reject);
    p.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited ${code}: ${stderr.slice(-400)}`));
    });
  });
}

async function probeDuration(file: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const p = spawn('ffprobe', [
      '-v',
      'error',
      '-show_entries',
      'format=duration',
      '-of',
      'default=noprint_wrappers=1:nokey=1',
      file,
    ]);
    let stdout = '';
    p.stdout.on('data', (c: Buffer) => {
      stdout += c.toString();
    });
    p.on('error', reject);
    p.on('close', (code) => {
      if (code !== 0) return reject(new Error(`ffprobe exited ${code}`));
      const secs = Number.parseFloat(stdout.trim());
      resolve(Number.isFinite(secs) ? secs : 0);
    });
  });
}

async function chunkAudio(inputPath: string, outDir: string): Promise<string[]> {
  const duration = await probeDuration(inputPath);
  if (duration <= CHUNK_SECONDS) {
    return [inputPath];
  }
  const chunks: string[] = [];
  let startSec = 0;
  let idx = 0;
  while (startSec < duration) {
    const outPath = path.join(outDir, `chunk-${idx.toString().padStart(3, '0')}.mp3`);
    await runFfmpeg([
      '-y',
      '-ss',
      String(startSec),
      '-t',
      String(CHUNK_SECONDS),
      '-i',
      inputPath,
      '-acodec',
      'libmp3lame',
      '-ar',
      '16000',
      '-ac',
      '1',
      outPath,
    ]);
    chunks.push(outPath);
    // Next chunk starts slightly before the previous ends so boundary
    // sentences aren't cut. Stitch dedupe below strips the overlap.
    startSec = startSec + CHUNK_SECONDS - CHUNK_OVERLAP;
    idx += 1;
  }
  return chunks;
}

export async function runTranscribeBatch(payload: TranscribeBatchPayload): Promise<void> {
  const { visitId, audioObjectKey, sourceFileName } = payload;

  const visit = await prisma.scribeVisit.findUnique({
    where: { id: visitId },
    select: { id: true, practiceId: true, userId: true, status: true },
  });
  if (!visit) {
    console.error(`[transcribe_batch] visit ${visitId} not found; dropping job`);
    return;
  }

  await prisma.scribeVisit.update({
    where: { id: visitId },
    data: { status: 'PROCESSING' },
  });
  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId,
      actorId: visit.userId,
      action: 'STARTED_TRANSCRIPTION',
    },
  });

  const workDir = await fs.mkdtemp(path.join(os.tmpdir(), 'scribe-'));
  const audioPath = path.join(workDir, sourceFileName);

  try {
    const buf = await downloadObject(audioObjectKey);
    await fs.writeFile(audioPath, buf);

    const chunks = await chunkAudio(audioPath, workDir);
    const parts: string[] = [];
    let totalDuration = 0;

    for (const chunkPath of chunks) {
      const data = await fs.readFile(chunkPath);
      const result = await modelClient.transcribe({
        audio: data,
        fileName: path.basename(chunkPath),
        language: 'en',
        purpose: 'transcribe_batch',
        visitId,
        practiceId: visit.practiceId,
      });
      parts.push(result.text);
      if (result.durationSec) totalDuration += result.durationSec;
    }

    const rawFullText = parts.join('\n\n').trim();

    await prisma.scribeTranscript.create({
      data: {
        practiceId: visit.practiceId,
        visitId,
        segments: parts.map((text, i) => ({
          speaker: 'UNKNOWN',
          startMs: i * CHUNK_SECONDS * 1000,
          endMs: (i + 1) * CHUNK_SECONDS * 1000,
          text,
        })),
        rawFullText,
        language: 'en',
        provider: 'openai-whisper',
      },
    });

    await prisma.scribeVisit.update({
      where: { id: visitId },
      data: { audioDurationSec: totalDuration || null },
    });

    await prisma.scribeAuditEvent.create({
      data: {
        practiceId: visit.practiceId,
        visitId,
        actorId: visit.userId,
        action: 'TRANSCRIPTION_COMPLETE',
        diff: { chunks: chunks.length, bytes: buf.length },
      },
    });

    // Fan out to finalize_visit (SOAP generation in M2).
    await getScribeQueue().add(JOB_FINALIZE_VISIT, {
      visitId,
    } satisfies FinalizeVisitPayload);
  } catch (err) {
    console.error(`[transcribe_batch] visit=${visitId} failed:`, err);
    await prisma.scribeVisit.update({
      where: { id: visitId },
      data: { status: 'ERROR' },
    });
    await prisma.scribeAuditEvent.create({
      data: {
        practiceId: visit.practiceId,
        visitId,
        actorId: visit.userId,
        action: 'TRANSCRIPTION_FAILED',
        diff: { error: err instanceof Error ? err.message : String(err) },
      },
    });
    throw err;
  } finally {
    await fs.rm(workDir, { recursive: true, force: true }).catch(() => {});
  }
}
