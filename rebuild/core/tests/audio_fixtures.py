"""Real, distinct synthetic recordings for tests: the duration check measures every upload before any provider request."""
import hashlib
import io
import wave


def wav_bytes(seconds=1, tag=''):
    """PCM WAV (8 kHz, 8-bit, mono) of an exact length whose samples depend on `tag`, so each tag hashes differently."""
    rate = 8000
    seed = hashlib.sha256(tag.encode()).digest()
    frames = bytes(120 + seed[index % 32] % 16 for index in range(int(rate * seconds)))
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(1)
        output.setframerate(rate)
        output.writeframes(frames)
    return buffer.getvalue()


def wav_with_two_data_chunks(first_seconds, second_seconds, second_declares_zero=False):
    """A WAV whose samples are split across two `data` chunks, separated by a LIST chunk.

    Measured against ffmpeg: it plays exactly ONE of them — the last — so 9 s + 1 s decodes to 1 s and 1 s + 9 s to 9 s.
    The certified length may therefore never assume both are played.
    """
    import struct
    rate, block = 8000, 1
    first = bytes(120 + (index % 16) for index in range(int(rate * first_seconds)))
    second = bytes(200 - (index % 16) for index in range(int(rate * second_seconds)))
    listing = b'LIST' + struct.pack('<I', 4) + b'INFO'
    declared = 0 if second_declares_zero else len(second)
    body = (b'WAVE'
            + b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * block, block, 8)
            + b'data' + struct.pack('<I', len(first)) + first
            + listing
            + b'data' + struct.pack('<I', declared) + second)
    return b'RIFF' + struct.pack('<I', len(body)) + body
