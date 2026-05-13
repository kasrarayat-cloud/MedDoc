#!/usr/bin/env python3
"""Synthesize TTS audio for each scenario.

For each scenario in scenarios.ts (parsed via a sidecar JSON manifest),
generates a single-voice English MP3 via OpenAI TTS. Output:
/opt/meddoc-pro/.local/cross-input-mode-audio/{tag}.mp3

Voice: 'onyx' (deep, deliberate — sounds plausibly like a doctor
dictating, not a marketing voiceover).

Idempotent: skips scenarios whose audio file already exists. Re-run
after editing scenarios.ts to refresh changed scripts (delete the
specific {tag}.mp3 first if you want to force regeneration).
"""
import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

OUT_DIR = Path('/opt/meddoc-pro/.local/cross-input-mode-audio')
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_api_key() -> str:
    with open('/opt/meddoc-pro/.env') as f:
        for line in f:
            if line.startswith('OPENAI_API_KEY='):
                return line.strip().split('=', 1)[1]
    raise RuntimeError('OPENAI_API_KEY missing from /opt/meddoc-pro/.env')


def synth(api_key: str, voice: str, text: str, out_path: Path) -> None:
    body = json.dumps({
        'model': 'tts-1',
        'voice': voice,
        'input': text,
        'response_format': 'mp3',
        'speed': 1.0,
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.openai.com/v1/audio/speech',
        data=body,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        out_path.write_bytes(resp.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--manifest', required=True,
        help='Path to JSON file mapping {tag: {voice, text}} (built by harness via tsx → JSON.stringify).',
    )
    parser.add_argument('--force', action='store_true', help='Regenerate all even if files exist.')
    args = parser.parse_args()

    api_key = load_api_key()
    manifest = json.loads(Path(args.manifest).read_text())

    total = len(manifest)
    print(f'[synth] {total} scenarios; output → {OUT_DIR}')
    chars_synthesized = 0
    skipped = 0
    for i, (tag, entry) in enumerate(manifest.items(), start=1):
        out = OUT_DIR / f'{tag}.mp3'
        if out.exists() and not args.force:
            print(f'[synth] {i:2d}/{total} {tag}: SKIP (exists, {out.stat().st_size // 1024} KB)')
            skipped += 1
            continue
        text = entry['text']
        voice = entry.get('voice', 'onyx')
        print(f'[synth] {i:2d}/{total} {tag}: synth via {voice} ({len(text)} chars)')
        for attempt in range(3):
            try:
                synth(api_key, voice, text, out)
                chars_synthesized += len(text)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f'  retry after {e}')
                time.sleep(2)

    cost_estimate = chars_synthesized / 1_000_000 * 15
    print(f'\n[synth] done. {total - skipped} new, {skipped} skipped.')
    print(f'[synth] estimated TTS cost: ${cost_estimate:.4f}')


if __name__ == '__main__':
    main()
