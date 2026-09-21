"""Recording charge limit: the displayed maximum is binding, duration is measured and credit held before any paid request,
over-limit recordings are explained first, estimates that prove short are absorbed, and usable transcripts are delivered.

All data is synthetic. No provider, payment or console request leaves the test database.
"""
import importlib.util
import json
import os
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core import audio
from core.billing import reconcile_usage
from core.jobs import cancel, coverage_note, enqueue, reap_abandoned_voice_uploads, run_one, transcription_quote
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, Job, LedgerEntry, Membership, PlatformCost, Reservation, Usage, User, Wallet
from core.security import private_path
from exercised import requires_input
from core.tests.audio_fixtures import wav_bytes, wav_with_two_data_chunks
from core.tests.test_billing_boundary import LIVE, BoundaryFixture, deepgram
from core.tests.test_billing_policy import STORAGES

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'audio'
STANDARD_ENV = {'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.006', 'QUILLMD_DEEPGRAM_RATE_PER_SECOND': '', 'QUILLMD_VOICE_MAX_COST': '0.20',
                'QUILLMD_PROVIDER_DISCOUNT_RATE': '0', 'DEEPGRAM_API_KEY': 'synthetic-placeholder-not-a-key'}
# $60 per minute makes a one-second recording cost more than the $0.30 displayed limit, so the over-limit path is cheap to reach.
EXPENSIVE_ENV = dict(STANDARD_ENV, QUILLMD_DEEPGRAM_RATE_PER_MINUTE='60')
TRANSCRIPT = 'Synthetic transcript: patient reports a mild headache.'


class DurationIsMeasuredFromTheAudio(SimpleTestCase):
    def test_every_supported_format_measures_about_three_seconds_and_never_less(self):
        for name in ('tone-3s.wav', 'tone-3s.mp3', 'tone-3s.m4a', 'tone-3s-fragmented.m4a', 'tone-3s.webm', 'tone-3s-live.webm'):
            with self.subTest(name=name):
                seconds = audio.measure((FIXTURES / name).read_bytes())
                self.assertGreaterEqual(seconds, Decimal('3.0'))
                self.assertLessEqual(seconds, Decimal('3.2'))

    def test_wav_length_is_exact(self):
        self.assertEqual(audio.measure(wav_bytes(seconds=7, tag='exact')), Decimal('7.000'))

    def test_unmeasurable_input_is_refused_before_anything_is_sent(self):
        wav = wav_bytes(seconds=1, tag='compressed')
        compressed = wav[:20] + (2).to_bytes(2, 'little') + wav[22:]  # ADPCM tag: average byte rate only
        for data in (b'', b'RIFF synthetic test audio only', b'not audio at all', compressed, b'ID3\x04\x00\x00\x00\x00\x00\x00' + b'\x13\x37' * 400,
                     b'\x1aE\xdf\xa3' + b'\x00' * 64, b'\x00\x00\x00\x18ftypM4A ' + b'\x00' * 32):
            with self.subTest(data=data[:24]), self.assertRaises(audio.UnmeasurableRecording):
                audio.measure(data)

    def test_a_header_cannot_understate_an_mp4_recording(self):
        """Each AAC frame decodes to 1024 samples; a sample table claiming smaller deltas cannot shorten the measured length."""
        data = bytearray((FIXTURES / 'tone-3s.m4a').read_bytes())
        at = data.find(b'stts') + 4 + 8  # first (count, delta) entry
        count = int.from_bytes(data[at:at + 4], 'big')
        data[at + 4:at + 8] = (1).to_bytes(4, 'big')
        self.assertGreater(count, 10)
        self.assertGreaterEqual(audio.measure(bytes(data)), Decimal('2.9'))


def chunk_at(data, name):
    """Offset of the named box's payload (after size and type) in an MP4 file."""
    at = data.find(name)
    assert at >= 4, name
    return at + 4


class HeadersCannotUnderstateALength(SimpleTestCase):
    """A duration is what a decoder plays. A header a decoder ignores must never shorten it; a header that disagrees is refused."""

    def test_a_wav_byte_rate_that_disagrees_with_its_samples_is_refused(self):
        wav = bytearray(wav_bytes(seconds=30, tag='forged-rate'))
        self.assertEqual(audio.measure(bytes(wav)), Decimal('30.000'))
        wav[28:32] = (8000 * 1000).to_bytes(4, 'little')  # byte-rate field x1000: the decoder still plays 30 s
        with self.assertRaises(audio.UnmeasurableRecording):
            audio.measure(bytes(wav))

    def test_a_wav_data_size_smaller_than_its_samples_cannot_shorten_it(self):
        wav = bytearray(wav_bytes(seconds=30, tag='short-size'))
        at = wav.find(b'data') + 4
        wav[at:at + 4] = (80).to_bytes(4, 'little')
        self.assertEqual(audio.measure(bytes(wav)), Decimal('30.000'))

    def test_malformed_structures_are_refusals_not_errors(self):
        import struct
        truncated_fmt = b'RIFF' + struct.pack('<I', 100) + b'WAVE' + b'fmt ' + struct.pack('<I', 16) + b'\x01\x00\x02\x00\x44\xac\x00\x00\x10\xb1'
        for data in (truncated_fmt, wav_bytes(seconds=1, tag='cut')[:30], (FIXTURES / 'tone-3s.m4a').read_bytes()[:400],
                     (FIXTURES / 'tone-3s.webm').read_bytes()[:90]):
            with self.subTest(size=len(data)), self.assertRaises(audio.UnmeasurableRecording):
                audio.measure(data)
        with patch('core.audio.matroska', return_value=audio.Bounds(Decimal('1e40'), Decimal('1e40'))), self.assertRaises(audio.UnmeasurableRecording):
            audio.measure(b'\x1aE\xdf\xa3' + b'\x00' * 16)

    def test_an_mp4_timescale_or_sample_table_cannot_shorten_an_aac_recording(self):
        for name in ('tone-3s.m4a', 'tone-3s-fragmented.m4a'):
            original = (FIXTURES / name).read_bytes()
            data = bytearray(original)
            at = chunk_at(data, b'mdhd') + 12  # version 0: flags, creation, modification, then the timescale
            data[at:at + 4] = (int.from_bytes(data[at:at + 4], 'big') * 10).to_bytes(4, 'big')
            with self.subTest(name=name, forged='timescale x10'):
                self.assertGreaterEqual(audio.measure(bytes(data)), audio.measure(original))
        data = bytearray((FIXTURES / 'tone-3s.m4a').read_bytes())
        at = chunk_at(data, b'stts') + 8
        data[at:at + 4] = (1).to_bytes(4, 'big')  # the sample table claims one access unit; stsz still lists them all
        self.assertGreaterEqual(audio.measure(bytes(data)), Decimal('3.0'))

    def test_mp4_audio_that_is_not_plain_aac_is_refused(self):
        original = (FIXTURES / 'tone-3s.m4a').read_bytes()
        renamed = original.replace(b'mp4a', b'Opus', 1)
        data = bytearray(original)
        esds = data.find(b'esds')
        end = esds - 4 + int.from_bytes(data[esds - 4:esds], 'big')
        es = audio.descriptor(data, esds + 8, end)
        config = audio.descriptor(data, es[1] + 3, es[2])
        specific = audio.descriptor(data, config[1] + 13, config[2])
        data[specific[1]] = (23 << 3) | (data[specific[1]] & 7)  # AAC-LD: 480/512 samples per frame
        for forged in (renamed, bytes(data)):
            with self.subTest(size=len(forged)), self.assertRaises(audio.UnmeasurableRecording):
                audio.measure(forged)

    def test_webm_opus_is_measured_from_its_packets_whatever_the_timestamp_scale(self):
        original = (FIXTURES / 'tone-3s.webm').read_bytes()
        at = original.find(b'\x2a\xd7\xb1')
        size, _, value = audio.vint(original, at + 3, False)
        tiny = bytearray(original); tiny[value:value + size] = (1).to_bytes(size, 'big')
        self.assertGreaterEqual(audio.measure(bytes(tiny)), Decimal('3.0'))
        zero = bytearray(original); zero[value:value + size] = bytes(size)
        with self.assertRaises(audio.UnmeasurableRecording):
            audio.measure(bytes(zero))

    def test_webm_audio_that_is_not_unlaced_opus_is_refused(self):
        original = (FIXTURES / 'tone-3s.webm').read_bytes()
        vorbis = original.replace(b'A_OPUS', b'A_OPUX', 1)
        laced = bytearray(original)
        block = laced.find(b'\xa3', laced.find(b'\x1f\x43\xb6\x75'))
        size, _, body = audio.vint(laced, block + 1, False)
        _, _, after_track = audio.vint(laced, body, False)
        laced[after_track + 2] |= 0x02  # Xiph lacing on the first block
        for forged, reason in ((vorbis, 'WebM audio that is not Opus'), (bytes(laced), 'laced WebM audio')):
            with self.subTest(reason=reason), self.assertRaisesMessage(audio.UnmeasurableRecording, reason):
                audio.measure(forged)

    def test_mp3_bytes_that_are_not_standard_frames_cannot_shorten_it(self):
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        middle = len(original) // 2
        # An early 'TAG' used to end the walk; only a real trailing ID3v1 tag does now.
        planted = original[:middle] + b'TAG' + bytes(125) + original[middle:]
        self.assertGreaterEqual(audio.measure(planted), audio.measure(original))
        with self.assertRaises(audio.UnmeasurableRecording):
            audio.measure(original + bytes(range(256)) * 80)  # 20 KB that is not audio frames


def ape_tag(items, header=True):
    """A standard APEv2 tag (optional header, items, footer)."""
    import struct
    body = b''.join(struct.pack('<II', len(value), 0) + key + b'\x00' + value for key, value in items)
    size = len(body) + 32
    footer = b'APETAGEX' + struct.pack('<IIII', 2000, size, len(items), 0x80000000 if header else 0) + bytes(8)
    head = b'APETAGEX' + struct.pack('<IIII', 2000, size, len(items), 0xA0000000) + bytes(8)
    return (head if header else b'') + body + footer


class LegitimateTaggedRecordingsMeasureTheirAudio(SimpleTestCase):
    """Real files carry metadata; it must neither be refused nor lengthen the measurement (a false incomplete marker)."""

    def test_quicktime_layout_aac_is_measured(self):
        self.assertEqual(audio.measure((FIXTURES / 'tone-3s-quicktime.m4a').read_bytes()), Decimal('3.072'))

    def test_mp3_trailing_tags_are_metadata_not_audio(self):
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        plain = audio.measure(original)
        cover = bytes(range(256)) * 80  # 20 KB of 'cover art' that is not audio frames
        id3v1 = b'TAG' + bytes(125)
        id3v2_footer = b'ID3\x04\x00\x10\x00\x00\x00\x0a' + b'X' * 10 + b'3DI\x04\x00\x10\x00\x00\x00\x0a'
        for name, tagged in (('ape comment', original + ape_tag([(b'Comment', b'dictation ' * 200)]) + id3v1),
                             ('ape cover', original + ape_tag([(b'Cover Art (Front)', cover)], header=False)),
                             ('appended id3v2', original + id3v2_footer + id3v1)):
            with self.subTest(name=name):
                self.assertEqual(audio.measure(tagged), plain)

    def test_audio_hidden_inside_a_tag_still_counts(self):
        """A decoder plays frames it finds inside a trailing tag (ffmpeg decodes all 60 s of audio hidden in an APE tag, even
        as single frames separated by junk), so every frame there counts."""
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        frames, position = [], 0
        while position < len(original):
            frame = audio.mp3_frame(original, position)
            if frame and frame[0] >= 4:
                frames.append(original[position:position + frame[0]]); position += frame[0]
            else:
                position += 1
        head = b''.join(frames[:2])
        for chain in (1, 3, len(frames)):
            body = b''.join(b''.join(frames[i:i + chain]) + b'\x00' for i in range(2, len(frames), chain))
            with self.subTest(chain=chain):
                self.assertGreaterEqual(audio.measure(head + ape_tag([(b'Comment', body)])), audio.measure(original) - Decimal('0.1'))

    def test_wav_metadata_chunks_after_the_samples_are_not_audio(self):
        import struct
        wav = wav_bytes(seconds=30, tag='tagged-wav')
        tag = b'ID3\x03\x00\x00' + bytes(4) + bytes(80000)
        tagged = bytearray(wav + b'id3 ' + struct.pack('<I', len(tag)) + tag)
        tagged[4:8] = struct.pack('<I', len(tagged) - 8)
        self.assertEqual(audio.measure(bytes(tagged)), Decimal('30.000'))

    def test_a_header_a_decoder_rejects_as_id3_hides_nothing(self):
        """ffmpeg treats 'ID3' with a 0xFF version, a 0xFF revision or a non-syncsafe size as junk and decodes what follows."""
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        size = len(original) - 200
        syncsafe = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
        for header in (b'ID3\xff\x00\x00' + syncsafe, b'ID3\x03\xff\x00' + syncsafe, b'ID3\x03\x00\x00' + bytes([syncsafe[0] | 0x80]) + syncsafe[1:]):
            with self.subTest(header=header[:6]):
                self.assertGreaterEqual(audio.measure(header + original), audio.measure(original) - Decimal('0.1'))

    def test_consecutive_leading_id3_tags_and_lyrics3_are_metadata(self):
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        plain = audio.measure(original)

        def id3(payload):
            n = len(payload)
            return b'ID3\x03\x00\x00' + bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F]) + payload

        self.assertEqual(audio.measure(id3(b'TIT2' + bytes(20)) + id3(bytes(40000)) + original), plain)
        lyrics = b'LYRICSBEGIN' + b'LYR00300' + b'la ' * 100
        self.assertEqual(audio.measure(original + lyrics + b'%06d' % len(lyrics) + b'LYRICS200' + b'TAG' + bytes(125)), plain)

    def test_stray_headers_of_other_layouts_neither_count_nor_hide_frames(self):
        """A cover can hold frame-sync patterns of other layouts; a decoder rejects them, and so must the walk, without jumping
        over frames a decoder would still play."""
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        stray = bytes([0xFF, 0xFB, 0xE8, 0x00])  # MPEG-1 Layer III, 32 kHz, 320 kbps: claims 1,440 bytes
        # Image noise: sync patterns whose sample rates keep changing (44.1, 48 and 32 kHz), as in a real PNG cover.
        noise = [bytes([0xFF, 0xFB, 0x90 | (rate << 2), 0x00]) for rate in (0, 1, 2)]
        # A few stray syncs (a small cover) are counted, so they can never hide audio; the measurement only grows.
        few = b''.join(noise[i % 3] + bytes(range(97)) for i in range(audio.STRAY_FRAMES_IN_TAGS))
        self.assertGreaterEqual(audio.measure(original + ape_tag([(b'Cover Art (Front)', few)])), audio.measure(original))
        # Beyond the allowance the tags could hold real audio, so the file is refused rather than under-measured.
        many = b''.join(noise[i % 3] + bytes(range(97)) for i in range(audio.STRAY_FRAMES_IN_TAGS + 1))
        with self.assertRaisesMessage(audio.UnmeasurableRecording, 'tags contain audio frames'):
            audio.measure(original + ape_tag([(b'Cover Art (Front)', many)]))
        # A stream of MPEG-2.5 8 kHz frames (72 bytes, 0.072 s each) with a stray header before every 19 frames.
        frame = bytes([0xFF, 0xE3, 0x18, 0xC0]) + bytes(68)
        stream = b''.join((stray if i % 19 == 0 else b'') + frame for i in range(400))
        self.assertGreaterEqual(audio.measure(frame * 3 + stream), Decimal('0.072') * 403 - Decimal('0.1'))

    def test_a_layout_a_decoder_switches_to_still_counts(self):
        """Frames of a second layout separated by junk: a decoder follows the new layout once several agree."""
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        frame = bytes([0xFF, 0xE3, 0x18, 0xC0]) + bytes(68)
        head = original[:original.find(b'\xff', 10) + 2000]
        self.assertGreaterEqual(audio.measure(head + (frame + b'\x00') * 200), Decimal('0.072') * 200)

    def test_wav_audio_in_a_later_data_chunk_counts_and_other_chunks_do_not(self):
        import struct
        wav = wav_bytes(seconds=30, tag='later-data')
        at = wav.find(b'data')
        fmt, body = wav[12:at], wav[at + 8:]

        def riff(*chunks):
            inner = b'WAVE' + fmt + b''.join(chunks)
            return b'RIFF' + struct.pack('<I', len(inner)) + inner

        def chunk(tag, payload, pad=True):
            return tag + struct.pack('<I', len(payload)) + payload + (b'\x00' if pad and len(payload) & 1 else b'')

        cover = chunk(b'id3 ', bytes(100000))
        self.assertGreaterEqual(audio.measure(riff(chunk(b'data', body[:8000]), chunk(b'LIST', b'INFO'), chunk(b'data', body[8000:]))), Decimal('30.000'))
        for pad in (False, True):  # writers disagree on the pad byte after an odd-length chunk
            with self.subTest(pad=pad):
                self.assertEqual(audio.measure(riff(chunk(b'data', body), chunk(b'LIST', b'INFOISFT\x07\x00\x00\x00ffmpeg\x00', pad=pad), cover)), Decimal('30.000'))
        self.assertEqual(audio.measure(riff(chunk(b'data', body[:-1], pad=False), cover)), Decimal('30.000'))  # 29.999875 s, not +12.5 s of cover
        self.assertLessEqual(audio.measure(riff(chunk(b'data', body), cover) + b'TAG' + bytes(125)), Decimal('30.100'))

    def test_a_wav_with_two_format_chunks_is_refused(self):
        """ffmpeg follows the first format chunk; a second one could make the samples look 12 times shorter."""
        import struct
        wav = wav_bytes(seconds=10, tag='two-fmt')
        at = wav.find(b'data')
        second = b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, 48000, 96000, 2, 16)
        inner = b'WAVE' + wav[12:at] + second + wav[at:]
        with self.assertRaisesMessage(audio.UnmeasurableRecording, 'more than one format chunk'):
            audio.measure(b'RIFF' + struct.pack('<I', len(inner)) + inner)

    def test_an_mp4_edit_list_that_plays_longer_than_the_samples_counts(self):
        """A decoder plays every edit, so repeated or extended edits lengthen what it plays."""
        data = bytearray((FIXTURES / 'tone-3s.m4a').read_bytes())
        at = data.find(b'elst') + 4 + 8  # version/flags, entry count, then the first segment duration (movie timescale)
        duration = int.from_bytes(data[at:at + 4], 'big')
        data[at:at + 4] = (duration * 24).to_bytes(4, 'big')
        self.assertGreaterEqual(audio.measure(bytes(data)), Decimal(duration * 24) / 1000)

    def test_frames_of_alternating_layouts_hidden_in_tags_are_refused(self):
        """A decoder plays real frames of any layout; many headers of other layouts inside a tag are refused, not excused."""
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        low = bytes([0xFF, 0xE3, 0x18, 0xC0]) + bytes(68)  # MPEG-2.5, 8 kHz
        high = bytes([0xFF, 0xF3, 0x18, 0xC0]) + bytes(68)  # MPEG-2, 16 kHz... another layout
        hidden = b''.join(low + b'\x00' + high + b'\x00' for _ in range(100))
        with self.assertRaisesMessage(audio.UnmeasurableRecording, 'tags contain audio frames'):
            audio.measure(original + ape_tag([(b'Comment', hidden)]))

    def test_bytes_that_are_not_stream_frames_are_costed_at_the_lowest_bitrate(self):
        """Frames of alternating layouts are never established, so their bytes are non-frame bytes: costed at 8 kbps (1 ms per
        byte), not at the stream's own higher rate, they can never be priced below the audio they could hold."""
        # A high-bitrate stream (MPEG-1 Layer III, 44.1 kHz, 320 kbps: 1,044 bytes, 0.026 s per frame), so its own rate would
        # price the hidden bytes about 40 times too low.
        original = (bytes([0xFF, 0xFB, 0xE0, 0xC0]) + bytes(1040)) * 100
        low = bytes([0xFF, 0xE3, 0x18, 0xC0]) + bytes(68)   # MPEG-2.5 8 kHz, 72 bytes, 0.072 s
        high = bytes([0xFF, 0xF3, 0x18, 0xC0]) + bytes(32)  # MPEG-2 16 kHz, 36 bytes, 0.036 s
        hidden = (low + b'\x00' + high + b'\x00') * 100    # 11,000 bytes, 10.8 s a decoder could play
        self.assertGreaterEqual(audio.measure(original + hidden), audio.measure(original) + Decimal('10.8') - Decimal('0.1'))

    def test_apple_lossless_is_refused_with_a_message_that_names_it(self):
        renamed = (FIXTURES / 'tone-3s.m4a').read_bytes().replace(b'mp4a', b'alac', 1)
        with self.assertRaisesMessage(audio.UnmeasurableRecording, 'not Apple Lossless'):
            audio.measure(renamed)


class LengthBoundsSeparateChargingFromDisclosure(SimpleTestCase):
    """Two numbers: the conservative length the charge limit is priced from, and the length the file certainly holds. A
    statement that part of a recording was not transcribed may only rest on the second."""

    def test_every_fixture_reports_consistent_bounds(self):
        for name in ('tone-3s.wav', 'tone-3s.mp3', 'tone-3s.m4a', 'tone-3s-fragmented.m4a', 'tone-3s-quicktime.m4a',
                     'tone-3s.webm', 'tone-3s-live.webm'):
            with self.subTest(name=name):
                bounds = audio.measure_bounds((FIXTURES / name).read_bytes())
                self.assertLessEqual(bounds.confirmed, bounds.measured)
                self.assertLessEqual(bounds.measured - bounds.confirmed, Decimal('0.1'))
                self.assertEqual(audio.measure((FIXTURES / name).read_bytes()), bounds.measured)

    def test_bytes_that_might_be_audio_raise_the_priced_length_but_not_the_confirmed_one(self):
        import struct
        wav = wav_bytes(seconds=30, tag='bounds')
        at = wav.find(b'data') + 4
        declared = int.from_bytes(wav[at:at + 4], 'little')
        tail = bytearray(wav + bytes(8000))  # 1 s of bytes that are not chunk headers
        tail[4:8] = struct.pack('<I', len(tail) - 8)
        bounds = audio.measure_bounds(bytes(tail))
        self.assertEqual(bounds.confirmed, Decimal('30.000'))   # the declared samples
        self.assertEqual(bounds.measured, Decimal('31.000'))    # plus what a decoder might read on
        self.assertEqual(declared, 240000)

    def test_frames_of_alternating_layouts_in_tags_cannot_shorten_a_recording(self):
        """Measured against ffmpeg: 64 such pairs decoded 6.717 s while the old rule measured 2.412 s."""
        original = (FIXTURES / 'tone-3s.mp3').read_bytes()
        low = bytes([0xFF, 0xE3, 0x18, 0xC0]) + bytes(68)   # MPEG-2.5 8 kHz, 0.072 s
        high = bytes([0xFF, 0xF3, 0x18, 0xC0]) + bytes(32)  # MPEG-2 16 kHz, 0.036 s
        head = original[:original.find(b'\xff', 10) + 400]
        pairs = 4
        hidden = (low + b'\x00' + high + b'\x00') * pairs
        # Within the allowance every hidden frame counts, so the measurement cannot fall below what they hold.
        self.assertGreaterEqual(audio.measure(head + ape_tag([(b'Comment', hidden)])), Decimal('0.108') * pairs)
        with self.assertRaisesMessage(audio.UnmeasurableRecording, 'tags contain audio frames'):
            audio.measure(head + ape_tag([(b'Comment', (low + b'\x00' + high + b'\x00') * 32)]))

    def test_the_marker_reads_the_SUBMITTED_length_not_a_floor_over_decoder_ambiguity(self):
        """The floor is a lower bound over what some decoder might play; it is not evidence about the submission.

        Measured on real files: a WAV whose chunks are 1 s then 9 s SUBMITTS 9 s and floors at 1 s. Judging coverage by
        the floor called that recording complete when the provider returned 1 s — eight seconds silently lost. Coverage
        is now judged against what ffprobe says is in the payload that was actually POSTed.
        """
        from types import SimpleNamespace
        submitted = lambda seconds, **rest: SimpleNamespace(config={
            'recording_seconds': '60', 'submitted_seconds': seconds, 'submission_status': 'determined', **rest})
        # Transcribed in full against the submitted audio, and the payload holds what the recording measured: no claim.
        self.assertEqual(coverage_note(submitted('60'), {'duration_seconds': '60.1'}), '')
        # ⚠️ THIS CASE USED TO ASSERT SILENCE AND NOW ASSERTS A DISCLOSURE, and the change is the point. A payload of
        # 30 s taken from a recording measured at 60 s is transcribed in full BY THE PROVIDER and still has half the
        # recording missing before the request was made. The old assertion was true about the provider and silent
        # about the loss, which is exactly the structural gap this arm closes.
        pre_submission_loss = coverage_note(submitted('30'), {'duration_seconds': '30.1'})
        self.assertIn('could be read as audio', pre_submission_loss)
        self.assertIn('0:30', pre_submission_loss)
        self.assertIn('1:00', pre_submission_loss)
        self.assertNotIn('was not transcribed', pre_submission_loss, 'the provider must not be blamed for our own loss')
        # Materially short of the submitted audio: disclosed, naming the submitted length.
        short = coverage_note(submitted('60'), {'duration_seconds': '30.1'})
        self.assertIn('was not', short)
        self.assertIn('of audio submitted', short)
        # THE CASE THE FLOOR GOT WRONG: floor 1 s, submitted 9 s, provider returned 1 s.
        floored = SimpleNamespace(config={'recording_seconds': '10', 'recording_seconds_confirmed': '1',
                                          'submitted_seconds': '9', 'submission_status': 'determined'})
        note = coverage_note(floored, {'duration_seconds': '1.0'})
        self.assertIn('was not', note, 'eight missing seconds must not be hidden by a 1 s floor')

    def test_an_undetermined_submission_is_reported_as_unknown_never_as_complete(self):
        """Several audio streams, or a payload ffprobe cannot describe: coverage is UNKNOWN, not complete."""
        from types import SimpleNamespace
        for status, detail in (('ambiguous', '2 audio streams'), ('unprobeable', 'ffprobe is not installed')):
            with self.subTest(status=status):
                job = SimpleNamespace(config={'recording_seconds': '60', 'submitted_seconds': '',
                                              'submission_status': status, 'submission_detail': detail})
                note = coverage_note(job, {'duration_seconds': '30'})
                self.assertIn('UNKNOWN', note)
                self.assertIn(detail, note)
                self.assertNotIn('incomplete', note)
        # Older jobs recorded before the submission was measured also report unknown rather than a false claim.
        legacy = SimpleNamespace(config={'recording_seconds': '60'})
        self.assertIn('UNKNOWN', coverage_note(legacy, {'duration_seconds': '30.1'}))


class QuoteArithmetic(SimpleTestCase):
    def config(self, **values):
        base = {'voice_rate_minute': '0.006', 'voice_rate_second': '', 'voice_max_cost': '0.20', 'discount_rate': '0', 'pricing_version': 'test'}
        base.update(values)
        return base

    def test_limit_includes_the_margin_and_rounds_up_to_a_cent(self):
        quote = transcription_quote(Decimal('60'), self.config())
        # (60 × 1.02 + 2) s × $0.0001/s = $0.00632 cost → × 1.5 = $0.00948 → rounded up to $0.01.
        self.assertEqual(quote['charge_limit'], '0.01'); self.assertTrue(quote['within_standard'])
        self.assertEqual(quote['standard_limit'], '0.30')

    def test_the_length_that_fits_the_displayed_limit_is_consistent_with_the_quote(self):
        quote = transcription_quote(Decimal('0'), self.config())
        fits = Decimal(quote['fits_seconds'])
        self.assertTrue(transcription_quote(fits, self.config())['within_standard'])
        self.assertFalse(transcription_quote(fits + 60, self.config())['within_standard'])

    def test_a_zero_rate_costs_and_holds_nothing(self):
        self.assertEqual(transcription_quote(Decimal('30'), self.config(voice_rate_minute='0'))['charge_limit'], '0')

    def test_the_quote_reads_the_same_rate_rule_settlement_does(self):
        """With both rates configured, settlement prices by the per-minute rate; the quote must too, or its check is not the charge."""
        both = self.config(voice_rate_minute='0.0077', voice_rate_second='0.00001')
        self.assertEqual(transcription_quote(Decimal('1800'), both), transcription_quote(Decimal('1800'), self.config(voice_rate_minute='0.0077')))
        self.assertFalse(transcription_quote(Decimal('1800'), both)['within_standard'])
        seconds_only = self.config(voice_rate_minute='', voice_rate_second='0.0001')
        self.assertEqual(transcription_quote(Decimal('60'), seconds_only)['charge_limit'], '0.01')

    def test_the_displayed_limit_is_the_enforced_one_to_the_cent(self):
        """$0.25 x 1.5 = $0.375 is shown and enforced as $0.37: never a displayed amount above the enforced one."""
        config = self.config(voice_max_cost='0.25', voice_rate_minute='0.0043')
        quote = transcription_quote(Decimal('0'), config)
        self.assertEqual(quote['standard_limit'], '0.37')
        fits = Decimal(quote['fits_seconds'])
        self.assertTrue(transcription_quote(fits, config)['within_standard'])
        self.assertLessEqual(Decimal(transcription_quote(fits, config)['charge_limit']), Decimal('0.37'))
        self.assertFalse(transcription_quote(fits + 60, config)['within_standard'])


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class RecordingChargeLimit(BoundaryFixture, TestCase):
    def upload(self, env, tag='rec', seconds=1, client=None):
        client = client or self.client
        with patch.dict(os.environ, env):
            page = client.get(f'/encounters/{self.encounter.pk}/')
            return client.post(f'/encounters/{self.encounter.pk}/voice/', {
                'audio': SimpleUploadedFile(f'{tag}.wav', wav_bytes(seconds=seconds, tag=tag), content_type='audio/wav'),
                'consent': 'on', 'usage_quote': page.context['usage_quote']})

    def approve(self, response, decision='approve', env=EXPENSIVE_ENV, client=None):
        with patch.dict(os.environ, env):
            return (client or self.client).post(f'/encounters/{self.encounter.pk}/voice/approve/',
                                               {'approval': response.context['approval'], 'decision': decision})

    def process(self, response_or_job, env=STANDARD_ENV, **provider):
        job = response_or_job if isinstance(response_or_job, Job) else Job.objects.get(encounter=self.encounter, state='queued')
        with patch.dict(os.environ, env), patch('core.jobs.httpx.post', **provider) as post:
            self.assertTrue(run_one())
        job.refresh_from_db()
        return job, post

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_within_the_displayed_limit_it_holds_its_own_exact_limit_and_is_processed(self):
        response = self.upload(STANDARD_ENV)
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        self.assertEqual(job.config['limit_basis'], 'standard'); self.assertEqual(job.config['recording_seconds'], '1.000')
        self.assertEqual(Decimal(job.config['charge_limit']), Decimal('0.01'))
        self.assertEqual(sum(r.amount for r in Reservation.objects.filter(job=job)), Decimal('0.01'))
        job, post = self.process(job, return_value=deepgram(TRANSCRIPT, 'dg_limit_within', duration=1))
        self.assertEqual(post.call_count, 1); self.assertEqual(job.state, 'succeeded')
        usage = Usage.objects.get(job=job); self.assertEqual(usage.charged_cost, usage.actual_cost * Decimal('1.5'))
        self.assertFalse(PlatformCost.objects.exists()); self.assertTrue(audit_report()['all_checks_pass'])

    def test_the_voice_form_states_the_limit_and_the_length_that_fits(self):
        with patch.dict(os.environ, STANDARD_ENV):
            page = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertContains(page, 'Limit $0.30 per recording, which fits recordings up to')
        self.assertContains(page, 'never more than the limit')

    def test_over_the_limit_nothing_is_sent_and_the_choice_is_explained_first(self):
        with patch('core.jobs.httpx.post') as post:
            response = self.upload(EXPENSIVE_ENV)
        self.assertEqual(response.status_code, 409); self.assertEqual(post.call_count, 0)
        self.assertFalse(Job.objects.filter(kind='transcription').exists()); self.assertFalse(Reservation.objects.exists())
        self.assertContains(response, 'Nothing was sent', status_code=409)
        self.assertContains(response, 'Approve a limit of $4.53 and transcribe', status_code=409)
        self.assertContains(response, 'Upload a shorter segment instead', status_code=409)
        self.assertTrue(AuditEvent.objects.filter(action='voice.over_limit_quoted', target=str(self.encounter.pk)).exists())
        kept = list(private_path('audio').iterdir()); self.assertEqual(len(kept), 1)  # the upload is kept for the decision

    def test_an_approved_higher_limit_is_held_exactly_and_charged_at_most(self):
        response = self.upload(EXPENSIVE_ENV)
        approved = self.approve(response)
        self.assertEqual(approved.status_code, 302)
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        self.assertEqual(job.config['limit_basis'], 'approved'); self.assertEqual(job.config['charge_limit'], '4.53')
        self.assertEqual(sum(r.amount for r in Reservation.objects.filter(job=job)), Decimal('4.53'))
        self.assertTrue(AuditEvent.objects.filter(action='voice.limit_approved', target=str(job.pk)).exists())
        job, _ = self.process(job, env=EXPENSIVE_ENV, return_value=deepgram(TRANSCRIPT, 'dg_limit_approved', duration=1))
        usage = Usage.objects.get(job=job)
        self.assertEqual(usage.actual_cost, Decimal('1')); self.assertEqual(usage.charged_cost, Decimal('1.5'))
        self.assertEqual(self.balances(), (Decimal('8.5'), Decimal('0'))); self.assertTrue(audit_report()['all_checks_pass'])

    def test_choosing_a_shorter_segment_sends_nothing_and_removes_the_upload(self):
        response = self.upload(EXPENSIVE_ENV)
        declined = self.approve(response, decision='shorter')
        self.assertEqual(declined.status_code, 302)
        self.assertFalse(Job.objects.filter(kind='transcription').exists()); self.assertEqual(list(private_path('audio').iterdir()), [])

    def test_an_approval_is_bound_to_its_user_document_version_and_recording(self):
        response = self.upload(EXPENSIVE_ENV)
        # Another clinician of the same department cannot spend this doctor's approval.
        other = User.objects.create_user(username='limit-other', email='limit-other@synthetic.invalid', verified_at=timezone.now())
        Membership.objects.create(user=other, department=self.encounter.department, role='clinician')
        from django.test import Client
        stranger = Client(); stranger.force_login(other)
        self.assertEqual(self.approve(response, client=stranger).status_code, 403)
        # A forged approval is refused.
        with patch.dict(os.environ, EXPENSIVE_ENV):
            forged = self.client.post(f'/encounters/{self.encounter.pk}/voice/approve/', {'approval': response.context['approval'] + 'x', 'decision': 'approve'})
        self.assertEqual(forged.status_code, 302)
        # A changed recording is refused.
        path = next(private_path('audio').iterdir()); original = path.read_bytes()
        path.write_bytes(wav_bytes(seconds=1, tag='swapped'))
        self.approve(response)
        self.assertFalse(Job.objects.filter(kind='transcription').exists())
        path.write_bytes(original)
        # A changed document version is refused.
        type(self.encounter).objects.filter(pk=self.encounter.pk).update(revision=self.encounter.revision + 1)
        self.approve(response)
        self.assertFalse(Job.objects.filter(kind='transcription').exists()); self.assertFalse(Reservation.objects.exists())

    def test_another_department_cannot_use_the_approval_endpoint(self):
        response = self.upload(EXPENSIVE_ENV)
        other_scope = self.make_scope('limit-foreign')
        from django.test import Client
        foreign = Client(); foreign.force_login(other_scope[0])
        self.assertEqual(self.approve(response, client=foreign).status_code, 404)

    def test_insufficient_credit_is_explained_before_anything_is_sent(self):
        Wallet.objects.filter(pk=self.promo.pk).update(balance=Decimal('1'))
        LedgerEntry.objects.none()
        response = self.upload(EXPENSIVE_ENV)
        self.assertContains(response, 'Your available balance is below this limit', status_code=409)
        self.assertNotContains(response, 'Approve a limit of', status_code=409)
        with patch.dict(os.environ, EXPENSIVE_ENV), patch('core.jobs.httpx.post') as post:
            self.approve(response)
        self.assertEqual(post.call_count, 0); self.assertFalse(Job.objects.filter(kind='transcription').exists())
        Wallet.objects.filter(pk=self.promo.pk).update(balance=Decimal('0.001'))
        with patch('core.jobs.httpx.post') as post:
            self.upload(STANDARD_ENV, tag='cheap')
        self.assertEqual(post.call_count, 0); self.assertFalse(Job.objects.filter(kind='transcription').exists())
        messages = [str(m) for m in self.client.get(f'/encounters/{self.encounter.pk}/').context['messages']]
        self.assertTrue(any('needs up to $0.01 held' in m for m in messages), messages)

    def test_a_recording_longer_than_the_hard_maximum_is_refused_and_not_kept(self):
        env = dict(STANDARD_ENV, QUILLMD_VOICE_MAX_MINUTES='0.01')
        with patch('core.jobs.httpx.post') as post:
            response = self.upload(env)
        self.assertEqual(response.status_code, 302); self.assertEqual(post.call_count, 0)
        self.assertFalse(Job.objects.filter(kind='transcription').exists()); self.assertEqual(list(private_path('audio').iterdir()), [])

    def test_cancelling_an_approved_request_releases_the_whole_limit(self):
        self.approve(self.upload(EXPENSIVE_ENV))
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        self.promo.refresh_from_db(); self.assertEqual(self.promo.reserved, Decimal('4.53'))
        cancel(job, self.user)
        self.promo.refresh_from_db(); self.assertEqual(self.promo.reserved, 0); self.assertEqual(self.promo.balance, Decimal('10'))
        self.assertFalse(Usage.objects.filter(job=job).exists()); self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_provider_failure_holds_the_limit_and_a_retry_is_charged_once(self):
        response = self.upload(EXPENSIVE_ENV)
        self.approve(response)
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        job, _ = self.process(job, env=EXPENSIVE_ENV, side_effect=TimeoutError('synthetic provider timeout'))
        self.assertEqual(job.state, 'reconciliation'); self.promo.refresh_from_db(); self.assertEqual(self.promo.reserved, Decimal('4.53'))
        # An unusable transcript after settlement is a platform failure: absorbed, and the key is freed for a retry.
        second = self.upload(STANDARD_ENV, tag='retry')
        self.assertIn('pending job', ' '.join(str(m) for m in self.client.get(f'/encounters/{self.encounter.pk}/').context['messages']))
        Job.objects.filter(pk=job.pk).update(state='failed', error='Resolved by administrator: no provider cost evidenced.',
                                             request_key=job.request_key + ':failed:' + job.pk.hex)
        from core.billing import release
        release(job)
        retry = self.upload(STANDARD_ENV, tag='retry')
        fresh = Job.objects.get(encounter=self.encounter, state='queued')
        fresh, _ = self.process(fresh, return_value=deepgram(None, 'dg_limit_unusable', duration=1))
        self.assertTrue(fresh.error.startswith('platform_failure: ')); self.assertTrue(LedgerEntry.objects.filter(job=fresh, kind='absorbed').exists())
        again = self.upload(STANDARD_ENV, tag='retry')
        final = Job.objects.get(encounter=self.encounter, state='queued')
        final, _ = self.process(final, return_value=deepgram(TRANSCRIPT, 'dg_limit_retry_ok', duration=1))
        self.assertEqual(final.state, 'succeeded')
        charged = Usage.objects.get(job=final).charged_cost
        self.assertEqual(self.balances(), (Decimal('10') - charged, Decimal('0'))); self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_short_provider_duration_is_labelled_incomplete_never_silently_truncated(self):
        needs_the_submission_probe(self)
        self.upload(STANDARD_ENV, seconds=60, tag='partial')
        job, _ = self.process(None or Job.objects.get(encounter=self.encounter, state='queued'),
                              return_value=deepgram(TRANSCRIPT, 'dg_limit_partial', duration=20))
        self.assertEqual(job.state, 'succeeded')
        self.encounter.refresh_from_db()
        self.assertNotIn(TRANSCRIPT, self.encounter.notes)
        stored = json.loads(private_path(job.result_path).read_text())['transcript']
        self.assertContains(self.client.get(f'/encounters/{self.encounter.pk}/'), 'Transcription incomplete')
        applied = self.client.post(f'/encounters/{self.encounter.pk}/notes/', {
            'revision': self.encounter.revision, 'transcript_job': str(job.pk), 'corrected_transcript': stored,
            'transcript_mode': 'append', 'transcript_reviewed': 'on'})
        self.assertEqual(applied.status_code, 302)
        self.encounter.refresh_from_db()
        self.assertIn(TRANSCRIPT, self.encounter.notes)
        # The marker names what was SUBMITTED, not the priced ceiling: ffprobe measures the payload that is POSTed.
        self.assertIn('[Transcription incomplete: the provider processed 0:20 of the 1:00 of audio submitted; 0:40 was not '
                      'transcribed.]', self.encounter.notes)

    def test_a_duplicate_submission_is_one_job_and_one_hold(self):
        self.upload(STANDARD_ENV, tag='same')
        self.upload(STANDARD_ENV, tag='same')
        self.assertEqual(Job.objects.filter(kind='transcription').count(), 1); self.assertEqual(Reservation.objects.count(), 1)

    def test_reconciliation_never_raises_the_customer_charge_above_the_limit(self):
        self.upload(STANDARD_ENV, tag='reconcile')
        job, _ = self.process(Job.objects.get(encounter=self.encounter, state='queued'),
                              return_value=deepgram(TRANSCRIPT, 'dg_limit_reconcile', duration=6000))
        usage = Usage.objects.get(job=job)
        self.assertEqual(usage.charged_cost, Decimal('0.01')); self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_over_limit').amount, Decimal('0.89'))
        row = reconcile_usage(usage, Decimal('0.8'), 'INV-SYNTH-LIMIT', self.user)
        self.assertEqual(row.charge_delta, 0); self.assertEqual(row.over_limit_delta, Decimal('0.3'))
        self.assertFalse(LedgerEntry.objects.filter(kind='reconciliation').exists())
        self.assertEqual(self.balances(), (Decimal('9.99'), Decimal('0')))
        report = audit_report(); self.assertTrue(report['all_checks_pass'])

    def test_notes_with_no_room_refuse_before_anything_is_sent_and_hide_the_recorder(self):
        full = 'N' * (50000 - 2)  # the notes plus a blank line leave no room for a single character
        type(self.encounter).objects.filter(pk=self.encounter.pk).update(notes=full)
        with patch.dict(os.environ, STANDARD_ENV):
            page = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertContains(page, 'data-voice-notes-full'); self.assertNotContains(page, 'data-voice-form')
        with patch('core.jobs.httpx.post') as post:
            self.upload(STANDARD_ENV, tag='full-notes')
        self.assertEqual(post.call_count, 0); self.assertFalse(Job.objects.filter(kind='transcription').exists())
        self.assertFalse(Reservation.objects.exists())
        type(self.encounter).objects.filter(pk=self.encounter.pk).update(notes=full[:-1])  # one character of room: accepted
        self.upload(STANDARD_ENV, tag='one-char-room')
        self.assertTrue(Job.objects.filter(kind='transcription').exists())

    def test_welcome_credit_is_unchanged_by_the_limit(self):
        self.assertEqual(self.balances(), (Decimal('10'), Decimal('0')))
        self.assertEqual(LedgerEntry.objects.filter(wallet=self.promo, kind='welcome').count(), 1)

    def test_any_missing_audio_beyond_two_seconds_is_marked_in_the_notes_and_the_download(self):
        needs_the_submission_probe(self)
        # Five minutes: the old 3% + 1 s tolerance let 10 s go unmarked here.
        for tag, duration, marked in (('miss-3s', 297, True), ('miss-1s', 299, False)):
            with self.subTest(tag=tag):
                self.upload(STANDARD_ENV, seconds=300, tag=tag)
                job, _ = self.process(Job.objects.get(encounter=self.encounter, state='queued'),
                                      return_value=deepgram(TRANSCRIPT, 'dg_' + tag, duration=duration))
                self.encounter.refresh_from_db()
                stored = json.loads(private_path(job.result_path).read_text())['transcript']
                marker = ('[Transcription incomplete: the provider processed 4:57 of the 5:00 of audio submitted; 0:03 was '
                          'not transcribed.]')
                self.assertEqual(marker in stored, marked); self.assertTrue(stored.startswith(TRANSCRIPT))
                applied = self.client.post(f'/encounters/{self.encounter.pk}/notes/', {
                    'revision': self.encounter.revision, 'transcript_job': str(job.pk), 'corrected_transcript': stored,
                    'transcript_mode': 'append', 'transcript_reviewed': 'on'})
                self.assertEqual(applied.status_code, 302)
                self.encounter.refresh_from_db()
                self.assertEqual(self.encounter.notes.count('[Transcription incomplete'), 1)  # the 3 s run's marker; none for 1 s

    def test_the_limit_page_says_whether_the_balance_covers_it_never_the_amount(self):
        response = self.upload(EXPENSIVE_ENV, tag='covers')
        self.assertContains(response, 'Covers this limit', status_code=409)
        self.assertNotContains(response, '$10', status_code=409); self.assertNotContains(response, 'Available balance $', status_code=409)
        Wallet.objects.filter(pk=self.promo.pk).update(balance=Decimal('1'))
        response = self.upload(EXPENSIVE_ENV, tag='does-not-cover')
        self.assertContains(response, 'Does not cover this limit', status_code=409)
        Wallet.objects.filter(pk=self.promo.pk).update(balance=Decimal('0.001'))
        self.upload(STANDARD_ENV, tag='refused')
        messages = [str(m) for m in self.client.get(f'/encounters/{self.encounter.pk}/').context['messages']]
        refusal = [m for m in messages if 'needs up to $0.01 held' in m]
        self.assertTrue(refusal, messages); self.assertNotIn('0.001', refusal[0]); self.assertNotIn('is available', refusal[0])

    def test_a_shorter_segment_never_removes_a_recording_an_approval_queued(self):
        response = self.upload(EXPENSIVE_ENV, tag='approved-then-shorter')
        self.approve(response)
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        self.approve(response, decision='shorter')
        self.assertTrue(private_path(job.input_path).is_file())
        messages = [str(m) for m in self.client.get(f'/encounters/{self.encounter.pk}/').context['messages']]
        self.assertTrue(any('already approved and queued' in m for m in messages), messages)
        self.assertFalse(any('Nothing was sent' in m for m in messages), messages)

    def test_an_expired_quote_cannot_be_approved_but_its_upload_can_still_be_removed(self):
        response = self.upload(EXPENSIVE_ENV, tag='expired')
        later = time.time() + 1801
        with patch('django.core.signing.time.time', return_value=later):
            self.approve(response)
            self.assertFalse(Job.objects.filter(kind='transcription').exists())
            self.assertEqual(len(list(private_path('audio').iterdir())), 1)
            self.approve(response, decision='shorter')
        self.assertEqual(list(private_path('audio').iterdir()), [])

    def test_an_approval_whose_recording_vanished_is_refused_not_an_error(self):
        response = self.upload(EXPENSIVE_ENV, tag='vanishing')
        # The file disappears after the view's hash check and before enqueue reads it (a concurrent "shorter" decision).
        with patch('core.jobs.private_path', return_value=Path('/nonexistent/quillmd-vanished.wav')):
            answer = self.approve(response)
        self.assertEqual(answer.status_code, 302); self.assertFalse(Job.objects.filter(kind='transcription').exists())
        self.assertFalse(Reservation.objects.exists())
        messages = [str(m) for m in self.client.get(f'/encounters/{self.encounter.pk}/').context['messages']]
        self.assertTrue(any('no longer available' in m for m in messages), messages)

    def test_uploads_nobody_approved_are_removed_after_the_approval_window(self):
        abandoned = self.upload(EXPENSIVE_ENV, tag='abandoned')
        approved = self.upload(EXPENSIVE_ENV, tag='approved-and-kept')
        self.approve(approved)
        kept_by_job = Job.objects.get(encounter=self.encounter, kind='transcription').input_path
        self.assertEqual(len(list(private_path('audio').iterdir())), 2)
        self.assertEqual(reap_abandoned_voice_uploads(), 0)  # still inside the window
        with patch('core.jobs.timezone.now', return_value=timezone.now() + timedelta(minutes=41)):
            self.assertEqual(reap_abandoned_voice_uploads(), 1)
            self.assertEqual(reap_abandoned_voice_uploads(), 0)
        self.assertEqual([p.name for p in private_path('audio').iterdir()], [Path(kept_by_job).name])
        self.assertEqual(AuditEvent.objects.filter(action='voice.over_limit_upload_removed').count(), 1)
        self.assertIsNotNone(abandoned.context['approval'])

    def test_the_backup_invariant_accepts_a_capped_charge_and_refuses_an_unexplained_one(self):
        from django.db import connection
        spec = importlib.util.spec_from_file_location('backup_restore', Path(__file__).resolve().parents[2] / 'ops' / 'backup_restore.py')
        backup = importlib.util.module_from_spec(spec); spec.loader.exec_module(backup)
        self.upload(STANDARD_ENV, tag='capped')
        job, _ = self.process(Job.objects.get(encounter=self.encounter, state='queued'),
                              return_value=deepgram(TRANSCRIPT, 'dg_limit_capped_invariant', duration=6000))
        self.assertTrue(PlatformCost.objects.filter(job=job, kind='absorbed_over_limit').exists())
        with connection.cursor() as cursor:
            cursor.execute(backup.INVARIANTS['usage_multiplier']); self.assertEqual(cursor.fetchone()[0], 0)
        stray = Job.objects.create(encounter=self.encounter, user=self.user, kind='transcription', revision=self.encounter.revision,
                                   request_key='synthetic-invariant-stray', config={})
        Usage.objects.create(job=stray, user=self.user, department=self.encounter.department, organization=self.encounter.department.organization,
                             payer=f'user:{self.user.pk}', provider='deepgram:nova-3-medical', units={}, rates={},
                             actual_cost=Decimal('1'), charged_cost=Decimal('0.5'), simulated=False)
        with connection.cursor() as cursor:
            cursor.execute(backup.INVARIANTS['usage_multiplier']); self.assertEqual(cursor.fetchone()[0], 1)


class BoundsAfterTheSecondRefutationPass(SimpleTestCase):
    """Every case here is one a refutation lens demonstrated against ffmpeg as the decoder of record."""

    def test_a_wav_split_across_two_data_chunks_certifies_only_the_smaller_one(self):
        """ffmpeg plays ONE data chunk: 9 s + 1 s decodes to 1 s, 1 s + 9 s to 9 s, 5 s + 5 s to 5 s.

        Summing them certified 10 s in all three, which marked a complete transcript incomplete.
        """
        for first, second, floor in ((9, 1, 1), (1, 9, 1), (5, 5, 5)):
            with self.subTest(first=first, second=second):
                bounds = audio.measure_bounds(wav_with_two_data_chunks(first, second))
                self.assertEqual(bounds.confirmed, Decimal(floor))
                self.assertEqual(bounds.measured, Decimal(first + second))

    def test_a_zero_length_trailing_data_chunk_is_not_priced_twice(self):
        """It runs to the end of the file, so counting it AND the bytes after it charged the same samples twice."""
        bounds = audio.measure_bounds(wav_with_two_data_chunks(1, 9, second_declares_zero=True))
        self.assertEqual(bounds.measured, Decimal(10))

    def test_an_ordinary_single_chunk_wav_is_unchanged(self):
        bounds = audio.measure_bounds(wav_bytes(3, 'unchanged'))
        self.assertEqual((bounds.confirmed, bounds.measured), (Decimal(3), Decimal(3)))

    def test_the_two_bounds_round_away_from_each_other(self):
        """The priced bound may never round below a decoder, and the certified bound never above it."""
        from decimal import ROUND_CEILING, ROUND_FLOOR
        source = (Path(__file__).resolve().parents[1] / 'audio.py').read_text()
        self.assertIn("rounding=ROUND_FLOOR", source)
        self.assertIn("rounding=ROUND_CEILING", source)
        self.assertEqual(Decimal('10.0004').quantize(Decimal('0.001'), rounding=ROUND_CEILING), Decimal('10.001'))
        self.assertEqual(Decimal('10.0006').quantize(Decimal('0.001'), rounding=ROUND_FLOOR), Decimal('10.000'))

    def test_the_certified_length_never_exceeds_the_priced_one(self):
        for name in ('tone-3s.wav', 'tone-3s.mp3', 'tone-3s.m4a', 'tone-3s.webm', 'tone-3s-fragmented.m4a',
                     'tone-3s-quicktime.m4a', 'tone-3s-live.webm'):
            with self.subTest(fixture=name):
                bounds = audio.measure_bounds((FIXTURES / name).read_bytes())
                self.assertLessEqual(bounds.confirmed, bounds.measured)
                self.assertGreater(bounds.confirmed, Decimal(0))


def needs_the_submission_probe(test):
    """Skip loudly when the host cannot measure the submitted payload.

    These assertions are about the INCOMPLETE marker, which is only reachable when the submission is
    determined. Without ffprobe the application correctly degrades to 'coverage UNKNOWN', so the test
    would be measuring the degraded path while claiming to measure the real one.
    """
    import shutil
    if shutil.which('ffprobe') is None:
        test.skipTest('Incomplete-marker path NOT EXERCISED: ffprobe is not on PATH, so every '
                      'submission degrades to UNKNOWN. No claim is made about this path from this run.')


class CoverageIsJudgedAgainstWhatWasActuallySubmitted(SimpleTestCase):
    """The fixtures every earlier pass found awkward, measured by ffprobe against the submitted payload.

    ⚠️ These assert a relationship between three numbers, not that any one of them is 'the' duration:
    the priced ceiling is never below the submission, and the completeness judgement uses the
    submission. Where the payload does not determine what a decoder processes, the answer is UNKNOWN.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import shutil
        cls.have_ffprobe = shutil.which('ffprobe') is not None

    def setUp(self):
        # A HOST CAPABILITY, not a fixture: its absence is a property of the machine, so this reports
        # NOT EXERCISED and says why. requires_input is for inputs the test itself controls — using it
        # here turned 'this host lacks ffprobe' into 'the code is broken', which is crying wolf.
        if not self.have_ffprobe:
            self.skipTest('Submission measurement NOT EXERCISED: ffprobe is not on PATH. No claim is '
                          'made about the submitted-payload path from this run.')

    def probe(self, data, suffix):
        import tempfile
        from core.media import probe_submission
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(data); path = handle.name
        self.addCleanup(lambda: __import__('os').unlink(path))
        return probe_submission(path)

    def test_a_split_wav_reports_the_chunk_a_decoder_reaches_not_their_sum_and_not_the_smallest(self):
        for first, second, expected in ((9, 1, 1), (1, 9, 9), (5, 5, 5)):
            with self.subTest(first=first, second=second):
                submission = self.probe(wav_with_two_data_chunks(first, second), '.wav')
                bounds = audio.measure_bounds(wav_with_two_data_chunks(first, second))
                self.assertEqual(submission.audio_streams, 1)
                self.assertFalse(submission.ambiguous, submission.reasons)
                self.assertAlmostEqual(float(submission.selected_seconds), expected, places=1)
                # The priced ceiling is never below what was submitted. That is the invariant that matters for money.
                self.assertGreaterEqual(bounds.measured, submission.selected_seconds)

    def test_the_floor_can_sit_below_the_submitted_audio_which_is_why_it_cannot_judge_coverage(self):
        data = wav_with_two_data_chunks(1, 9)
        submission = self.probe(data, '.wav')
        bounds = audio.measure_bounds(data)
        self.assertAlmostEqual(float(submission.selected_seconds), 9, places=1)
        self.assertLess(bounds.confirmed, submission.selected_seconds,
                        'this is the exact shape that made a floor-based completeness claim wrong')

    def test_a_zero_length_trailing_chunk_is_still_measurable_as_a_submission(self):
        submission = self.probe(wav_with_two_data_chunks(1, 9, second_declares_zero=True), '.wav')
        self.assertEqual(submission.audio_streams, 1)
        self.assertGreater(submission.selected_seconds, 0)

    def test_a_truncated_payload_is_measured_or_refused_but_never_silently_assumed_whole(self):
        whole = wav_bytes(6, 'truncation')
        submission = self.probe(whole[:len(whole) // 2], '.wav')
        self.assertLess(submission.selected_seconds, 6)

    def test_provider_truncation_is_disclosed_against_the_submission(self):
        from types import SimpleNamespace
        job = SimpleNamespace(config={'recording_seconds': '600', 'submitted_seconds': '600',
                                      'submission_status': 'determined'})
        note = coverage_note(job, {'duration_seconds': '120'})
        self.assertIn('of audio submitted', note)
        self.assertIn('8:00 was not', note)

    def test_a_retry_that_finally_succeeds_is_judged_on_its_own_returned_duration(self):
        """Each attempt is judged against the same submission; a short first answer does not taint a full second one."""
        from types import SimpleNamespace
        job = SimpleNamespace(config={'recording_seconds': '60', 'submitted_seconds': '60',
                                      'submission_status': 'determined'})
        self.assertIn('was not', coverage_note(job, {'duration_seconds': '10'}))
        self.assertEqual(coverage_note(job, {'duration_seconds': '60'}), '')

    def test_matching_durations_produce_no_claim_at_all(self):
        """Silence here is the absence of a claim. It is not, and must never be rendered as, proof of completeness."""
        from types import SimpleNamespace
        job = SimpleNamespace(config={'recording_seconds': '60', 'submitted_seconds': '60',
                                      'submission_status': 'determined'})
        self.assertEqual(coverage_note(job, {'duration_seconds': '60'}), '')
        source = (Path(__file__).resolve().parents[1] / 'jobs.py').read_text()
        self.assertIn('NOT PROOF THAT EVERY SPOKEN WORD WAS TRANSCRIBED', source.upper())


class WhatTheSubmissionRefutationFound(SimpleTestCase):
    """Three defects the refutation pass demonstrated on the finished diff, each reproduced here."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import shutil
        cls.tools = shutil.which('ffprobe') and shutil.which('ffmpeg')

    def setUp(self):
        if not self.tools:
            self.skipTest('Refutation fixtures NOT EXERCISED: ffmpeg and ffprobe are not both on PATH. '
                          'No claim is made about these three defects from this run.')

    def build(self, *args):
        import subprocess, tempfile, os
        handle = tempfile.NamedTemporaryFile(suffix=args[-1], delete=False); handle.close()
        self.addCleanup(lambda p=handle.name: os.path.exists(p) and os.unlink(p))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *args[:-1], handle.name], check=True, timeout=120)
        return handle.name

    def test_a_single_track_webm_is_determined_not_unknown(self):
        """THE PRIMARY PATH. The browser records audio/webm;codecs=opus and no Matroska variant emits a
        per-stream duration — so treating that as ambiguity put a false 'coverage UNKNOWN' on every
        ordinary recording, advising a re-export that could not help because it was already one track."""
        from core.media import probe_submission
        path = self.build('-f', 'lavfi', '-i', 'sine=frequency=440:duration=6', '-c:a', 'libopus', '-b:a', '24k', '.webm')
        submission = probe_submission(path, ceiling_seconds=Decimal('7'))
        self.assertEqual(submission.audio_streams, 1)
        self.assertFalse(submission.ambiguous, submission.reasons)
        self.assertGreater(submission.selected_seconds, Decimal('5'))

    def test_two_tracks_are_still_ambiguous_and_for_the_stated_reason(self):
        from core.media import probe_submission
        source = self.build('-f', 'lavfi', '-i', 'sine=frequency=440:duration=6', '.wav')
        path = self.build('-i', source, '-map', '0:a', '-map', '0:a', '-c:a', 'libopus', '-b:a', '24k', '.webm')
        submission = probe_submission(path, ceiling_seconds=Decimal('99'))
        self.assertTrue(submission.ambiguous)
        self.assertIn('2 audio streams', ' '.join(submission.reasons))

    def test_a_declared_duration_the_bytes_cannot_support_is_refused_not_believed(self):
        """An inflated Xing/Info frame count made a COMPLETE transcription report an hour of data loss.

        ffprobe reads the container's DECLARED duration; for MP3 that is the header field core/audio.py
        refuses to trust because a decoder ignores it. The conservative ceiling is the cross-check.
        """
        from core.media import probe_submission
        self.assertFalse(probe_submission(
            self.build('-f', 'lavfi', '-i', 'sine=frequency=440:duration=6', '-c:a', 'libmp3lame', '.mp3'),
            ceiling_seconds=Decimal('7')).ambiguous)
        honest = self.build('-f', 'lavfi', '-i', 'sine=frequency=440:duration=6', '-c:a', 'libmp3lame', '.mp3')
        submission = probe_submission(honest, ceiling_seconds=Decimal('1'))  # a ceiling the payload exceeds
        self.assertTrue(submission.ambiguous)
        self.assertIn('not trustworthy', ' '.join(submission.reasons))

    def test_an_untrustworthy_declaration_reports_unknown_rather_than_accusing_the_provider(self):
        from types import SimpleNamespace
        job = SimpleNamespace(config={'recording_seconds': '10', 'submitted_seconds': '3600',
                                      'submission_status': 'ambiguous',
                                      'submission_detail': 'declared duration is not trustworthy'})
        note = coverage_note(job, {'duration_seconds': '10'})
        self.assertIn('UNKNOWN', note)
        self.assertNotIn('was not transcribed', note)

    def test_the_probe_child_is_given_an_address_space_ceiling(self):
        """MAX_AUDIO_STREAMS is only checkable after the parse, so a hand-built container declaring a
        thousand tracks costs hundreds of MB before it is rejected — on the doctor's request path."""
        from core import media
        self.assertTrue(callable(media._bound_child))
        self.assertGreater(media.PROBE_ADDRESS_SPACE_BYTES, 0)
        source = (Path(__file__).resolve().parents[1] / 'media.py').read_text()
        self.assertIn('preexec_fn=_bound_child', source)
        self.assertIn('RLIMIT_AS', source)

    def test_the_unknown_note_no_longer_prescribes_a_fix_that_cannot_be_applied(self):
        source = (Path(__file__).resolve().parents[1] / 'jobs.py').read_text()
        self.assertNotIn('Re-export the recording as a single track', source)
