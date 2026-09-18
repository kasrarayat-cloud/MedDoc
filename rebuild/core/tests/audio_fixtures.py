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
