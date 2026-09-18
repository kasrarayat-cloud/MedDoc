"""Recording duration measured before any paid transcription request.

Pure Python, bounded by the 15 MB upload limit and explicit iteration caps; no media library or subprocess touches
the untrusted file. A duration is what a decoder would play, never a header field a decoder ignores (a header could
understate the length and so the charge limit):

  WAV (PCM or float)  the samples / (sample rate x block size): every byte after the data header, unless the declared data
                      size is followed by well-formed chunks to the end of the file; an inconsistent byte-rate field is refused
  MP3                 the sum of every MPEG audio frame's samples anywhere after a leading ID3v2 tag (a decoder plays frames
                      inside trailing tags too); trailing ID3v1, APEv2 and ID3v2 tags excuse only their own non-frame bytes;
                      other non-frame bytes count at the lowest bitrate seen, and a file that is mostly not frames is refused
  MP4 / M4A           AAC only: every access unit (the larger of stts and stsz, plus fragments) x its frame length, at the
                      sample rate of the stream's own AudioSpecificConfig, never the container timescale alone; an edit
                      list that plays longer (repeated or extended edits) counts in full, plus one frame per edit
  WebM / Matroska     Opus only: the sum of every packet's duration from its table of contents (and the block timestamps,
                      if larger); laced blocks, non-Opus audio and blocks before the track list are refused

Anything else raises UnmeasurableRecording: without a duration the charge limit cannot be confirmed, so nothing is sent.
"""
from decimal import Decimal
import struct

from django.core.exceptions import ValidationError

MAX_BYTES = 15 * 1024 * 1024
MAX_ITEMS = 400000
MAX_SECONDS = Decimal(24 * 3600)
MP3_STEPS = 1500000  # frames plus resynchronised bytes; a 60-minute recording at the lowest bitrate is about 100,000 frames


class UnmeasurableRecording(ValidationError):
    """The recording's length could not be determined, so its charge limit cannot be confirmed before processing."""


def refuse(detail):
    raise UnmeasurableRecording('The length of this recording could not be determined (' + detail + '), so its charge '
                                'cannot be confirmed. Nothing was sent for transcription. Record in the browser, or upload PCM WAV, MP3, '
                                'AAC M4A (not Apple Lossless) or Opus WebM audio.')


def measure(data):
    """Duration in seconds (Decimal) of an uploaded recording's bytes."""
    if not data:
        refuse('empty file')
    if len(data) > MAX_BYTES:
        refuse('larger than 15 MB')
    try:
        if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
            seconds = wav(data)
        elif data[:4] == b'\x1aE\xdf\xa3':
            seconds = matroska(data)
        elif data[4:8] == b'ftyp':
            seconds = mp4(data)
        elif data[:3] == b'ID3' or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
            seconds = mp3(data)
        else:
            refuse('unsupported format')
        if not seconds or seconds <= 0:
            refuse('no audio found')
        if seconds > MAX_SECONDS:
            refuse('implausible length')
        return seconds.quantize(Decimal('0.001'))
    except UnmeasurableRecording:
        raise
    except (struct.error, IndexError, KeyError, ValueError, OverflowError, ArithmeticError, RecursionError):
        # A malformed or truncated structure is a refusal like any other, never an unhandled error.
        refuse('unreadable structure')


# ── WAV ────────────────────────────────────────────────────────────────────
def wav(data):
    position, fmt, start = 12, None, None
    for _ in range(64):
        if position + 8 > len(data):
            break
        chunk, length = data[position:position + 4], struct.unpack('<I', data[position + 4:position + 8])[0]
        body = position + 8
        if chunk == b'fmt ':
            if length < 16 or body + 16 > len(data):
                refuse('WAV format chunk truncated')
            if fmt is not None:
                refuse('WAV with more than one format chunk')  # decoders disagree on which one applies
            fmt = struct.unpack('<HHIIHH', data[body:body + 16])
        elif chunk == b'data':
            start, declared = body, length
            break
        position = body + length + (length & 1)
    if fmt is None or start is None:
        refuse('WAV without format or audio data')
    # A decoder plays the declared data and then looks for further 'data' chunks (ffmpeg does: 29 s hidden in a second data
    # chunk after a LIST chunk decodes), so those count; other chunks (LIST, id3, cue…) are metadata. An absent or oversized
    # declared size means the samples run to the end of the file.
    size = len(data) - start
    if declared not in (0, 0xFFFFFFFF) and declared <= size:
        later, unparsed = trailing_chunks(data, start + declared)
        size = declared + later + unparsed  # bytes that are not chunk headers could be samples a decoder reads on
    tag, channels, rate, byte_rate, block, bits = fmt
    # A decoder plays the samples at rate x block bytes per second whatever the byte-rate field says, and may read past a
    # declared data size, so both come from the samples: every byte after the data header, at rate x block.
    if (tag not in (1, 3, 0xFFFE) or not 1 <= channels <= 8 or not 4000 <= rate <= 384000 or bits not in (8, 16, 24, 32, 64)
            or block != channels * (bits // 8) or byte_rate != rate * block):
        refuse('compressed, inconsistent or invalid WAV encoding')
    return Decimal(size) / Decimal(rate * block)


def trailing_chunks(data, position):
    """After the first data chunk ends at position: (bytes of later 'data' chunks, bytes that are not chunk headers). A decoder
    plays later data chunks (ffmpeg does); other chunks (LIST, id3, cue…) are metadata. Writers disagree on the pad byte after
    an odd-length chunk, so each header is looked for at both alignments."""
    later = 0
    for _ in range(4096):
        for at in (position, position + 1):
            if at + 8 <= len(data) and all(32 <= c <= 126 for c in data[at:at + 4]):
                break
        else:
            return later, max(0, len(data) - position)
        tag, length = data[at:at + 4], struct.unpack('<I', data[at + 4:at + 8])[0]
        if tag == b'data':
            later += min(length, len(data) - at - 8)
        position = at + 8 + length
        if position >= len(data):
            return later, 0
    refuse('WAV with too many chunks')


# ── MP3 ────────────────────────────────────────────────────────────────────
BITRATES = {
    (3, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
    (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_frame(data, position):
    """(length, samples, rate) of a valid MPEG audio frame header at position, else None."""
    if position + 4 > len(data):
        return None
    header = struct.unpack('>I', data[position:position + 4])[0]
    if header >> 21 != 0x7FF:
        return None
    version, layer = (header >> 19) & 3, (header >> 17) & 3
    bitrate_index, rate_index, padding = (header >> 12) & 15, (header >> 10) & 3, (header >> 9) & 1
    if version == 1 or layer == 0 or bitrate_index in (0, 15) or rate_index == 3:
        return None
    family = 3 if version == 3 else 2
    bitrate = BITRATES[(family, layer)][bitrate_index] * 1000
    rate = RATES[version][rate_index]
    if layer == 3:  # Layer I
        return (12 * bitrate // rate + padding) * 4, 384, rate
    samples = 1152 if (layer == 2 or version == 3) else 576
    return samples // 8 * bitrate // rate + padding, samples, rate


def mp3(data):
    position = 0
    # Only a header a decoder accepts as ID3v2 is skipped (ffmpeg's ff_id3v2_match: version and revision not 0xFF, a syncsafe
    # size); otherwise the bytes are walked like any other, so a fake tag cannot hide frames. Consecutive tags are all skipped.
    for _ in range(8):
        header = data[position:position + 10]
        if not (len(header) == 10 and header[:3] == b'ID3' and header[3] != 0xFF and header[4] != 0xFF and not any(b & 0x80 for b in header[6:10])):
            break
        size = header[6] << 21 | header[7] << 14 | header[8] << 7 | header[9]
        position += 10 + size + (10 if header[5] & 0x10 else 0)
    start = position
    end = tags_start(data, start)
    seconds, frames, before_tags, steps, slowest, strays_in_tags = Decimal(0), 0, 0, 0, Decimal(0), 0
    current, pending = None, []
    # The walk follows a decoder: frames of the stream's layout (samples per frame, sample rate) count wherever they are, junk
    # between them and trailing tags included (ffmpeg plays frames hidden in an APE tag, one frame at a time). A header of
    # another layout never makes the walk jump over bytes a decoder would still read: it establishes a new layout only as a run
    # of three adjacent frames, or once three such headers agree, and is otherwise a stray (a PNG cover holds many).

    def count(frame, at):
        nonlocal seconds, frames, before_tags, slowest
        length, samples, rate = frame
        seconds += Decimal(samples) / Decimal(rate)
        frames += 1
        if at < end:
            slowest = max(slowest, Decimal(samples) / Decimal(rate) / Decimal(length))
            before_tags += max(0, min(at + length, end) - at)

    while position < len(data):
        steps += 1
        if steps > MP3_STEPS:
            refuse('MP3 too complex to measure')  # an unscanned remainder could hold frames a decoder plays
        frame = mp3_frame(data, position)
        if frame and frame[0] >= 4:
            layout = frame[1:]
            if layout == current or adjacent_run(data, position, layout) >= 3:
                current, pending = layout, []
                count(frame, position)
                position += frame[0]
                continue
            # A decoder's parser starts over whenever a header disagrees with the previous one, so agreement must be consecutive.
            pending = (pending if pending and pending[0][0][1:] == layout else []) + [(frame, position)]
            if position >= end:
                strays_in_tags += 1
            if len(pending) >= 3:
                current = layout
                for f, at in pending:
                    count(f, at)
                pending = []
        position += 1  # resynchronise byte by byte
    if current is None:
        for f, at in pending:  # a recording too short to establish a layout: its frames still count
            count(f, at)
    # A decoder plays any real frame it finds, whatever its layout; stray syncs in cover art only fail at the payload, which
    # is not decoded here. So headers of other layouts inside tags are bounded (a 400 KB PNG cover holds about 55): beyond
    # that the tags could be hiding audio, and the file is refused.
    if strays_in_tags > 64:
        refuse('MP3 whose tags contain audio frames')
    # Recognised trailing tags excuse only their own non-frame bytes. Other bytes before them that are not standard frames
    # (free-format frames, unknown data) could still be decoded, so they are bounded and counted at the lowest bitrate seen.
    uncounted = end - start - before_tags
    if frames < 2 or uncounted > max(16384, (end - start) // 50):
        refuse('MP3 that is not made of standard audio frames')
    return seconds + Decimal(max(uncounted, 0)) * slowest


def adjacent_run(data, position, layout):
    """How many frames of this layout follow one another from position, up to three."""
    run = 0
    while run < 3:
        frame = mp3_frame(data, position)
        if not frame or frame[0] < 4 or frame[1:] != layout:
            break
        run += 1
        position += frame[0]
    return run


def tags_start(data, start):
    """Where the audio ends: ID3v1, APEv2 and footer-marked ID3v2 tags are stripped from the end of the file."""
    end = len(data)
    for _ in range(4):
        if end - start >= 128 and data[end - 128:end - 125] == b'TAG':
            end -= 128
        elif end - start >= 32 and data[end - 32:end - 24] == b'APETAGEX':
            size, _, flags = struct.unpack('<III', data[end - 20:end - 8])
            total = size + (32 if flags & 0x80000000 else 0)
            if size < 32 or total > end - start:
                break
            end -= total
        elif end - start >= 15 and data[end - 9:end] == b'LYRICS200' and data[end - 15:end - 9].isdigit():
            size = int(data[end - 15:end - 9]) + 15
            if size > end - start:
                break
            end -= size
        elif end - start >= 10 and data[end - 10:end - 7] == b'3DI':
            size = (data[end - 4] & 0x7F) << 21 | (data[end - 3] & 0x7F) << 14 | (data[end - 2] & 0x7F) << 7 | (data[end - 1] & 0x7F)
            if size + 20 > end - start:
                break
            end -= size + 20
        else:
            break
    return end


# ── MP4 / M4A ──────────────────────────────────────────────────────────────
CONTAINERS = {b'moov', b'trak', b'mdia', b'minf', b'stbl', b'moof', b'traf', b'mvex', b'edts', b'dinf'}


def boxes(data, start, end, depth, sink, counter):
    position = start
    while position + 8 <= end:
        counter[0] += 1
        if counter[0] > MAX_ITEMS or depth > 8:
            refuse('MP4 structure too complex')
        size, kind = struct.unpack('>I4s', data[position:position + 8])
        header = 8
        if size == 1:
            if position + 16 > end:
                break
            size = struct.unpack('>Q', data[position + 8:position + 16])[0]
            header = 16
        elif size == 0:
            size = end - position
        if size < header or position + size > end:
            break
        body = (position + header, position + size)
        sink(kind, body, depth)
        if kind in CONTAINERS:
            boxes(data, body[0], body[1], depth + 1, sink, counter)
        position += size


def mp4(data):
    tracks, fragments, trex, current, movie = {}, {}, {}, {}, {'timescale': 0}

    def sink(kind, body, depth):
        start, end = body
        payload = data[start:end]
        if kind == b'trak':
            current['track'] = {'id': None, 'handler': None, 'timescale': 0, 'stts_seconds_units': 0, 'samples': 0, 'stsz_samples': 0,
                                'codec': None, 'aac': None, 'edit_units': 0, 'edits': 0, 'end': end}
            tracks[start] = current['track']
            return
        track = current.get('track')
        if track is not None and start >= track['end']:
            track = current['track'] = None
        if kind == b'tkhd' and track is not None and len(payload) >= 24:
            track['id'] = struct.unpack('>I', payload[20:24] if payload[0] == 1 else payload[12:16])[0]
        elif kind == b'hdlr' and track is not None and len(payload) >= 12 and track['handler'] is None:
            # The media handler (mdia/hdlr) precedes minf; QuickTime files also carry a data handler inside minf, which must
            # not overwrite it.
            track['handler'] = payload[8:12]
        elif kind == b'mvhd' and len(payload) >= 24:
            movie['timescale'] = struct.unpack('>I', payload[20:24] if payload[0] == 1 else payload[12:16])[0]
        elif kind == b'elst' and track is not None and len(payload) >= 8:
            # A decoder plays each edit in turn and can repeat media, so the edits' total can exceed the samples.
            count, wide = struct.unpack('>I', payload[4:8])[0], payload[0] == 1
            size = 20 if wide else 12
            if count > MAX_ITEMS or 8 + count * size > len(payload):
                refuse('MP4 edit list invalid')
            for index in range(count):
                at = 8 + index * size
                track['edit_units'] += struct.unpack('>Q' if wide else '>I', payload[at:at + (8 if wide else 4)])[0]
            track['edits'] += count
        elif kind == b'mdhd' and track is not None and len(payload) >= 24:
            track['timescale'] = struct.unpack('>I', payload[20:24] if payload[0] == 1 else payload[12:16])[0]
        elif kind == b'stsd' and track is not None and len(payload) >= 16:
            track['codec'] = payload[12:16]
            if track['codec'] == b'mp4a':
                track['aac'] = aac_parameters(payload[8:])
        elif kind == b'stsz' and track is not None and len(payload) >= 12:
            track['stsz_samples'] = struct.unpack('>I', payload[8:12])[0]
        elif kind == b'stts' and track is not None and len(payload) >= 8:
            count = struct.unpack('>I', payload[4:8])[0]
            if count > MAX_ITEMS or 8 + count * 8 > len(payload):
                refuse('MP4 sample table invalid')
            for index in range(count):
                samples, delta = struct.unpack('>II', payload[8 + index * 8:16 + index * 8])
                track['stts_seconds_units'] += samples * delta
                track['samples'] += samples
        elif kind == b'trex' and len(payload) >= 16:
            track_id, _, duration = struct.unpack('>III', payload[4:16])
            trex[track_id] = duration
        elif kind == b'tfhd' and len(payload) >= 8:
            flags = int.from_bytes(payload[1:4], 'big')
            track_id = struct.unpack('>I', payload[4:8])[0]
            offset = 8 + (8 if flags & 0x01 else 0) + (4 if flags & 0x02 else 0)
            default = struct.unpack('>I', payload[offset:offset + 4])[0] if flags & 0x08 and offset + 4 <= len(payload) else None
            current['fragment'] = (track_id, default)
        elif kind == b'trun' and len(payload) >= 8 and current.get('fragment'):
            flags = int.from_bytes(payload[1:4], 'big')
            count = struct.unpack('>I', payload[4:8])[0]
            if count > MAX_ITEMS:
                refuse('MP4 fragment too large')
            offset = 8 + (4 if flags & 0x001 else 0) + (4 if flags & 0x004 else 0)
            per = sum(4 for bit in (0x100, 0x200, 0x400, 0x800) if flags & bit)
            track_id, default = current['fragment']
            total = 0
            for index in range(count):
                if flags & 0x100:
                    at = offset + index * per
                    if at + 4 > len(payload):
                        refuse('MP4 fragment truncated')
                    total += struct.unpack('>I', payload[at:at + 4])[0]
                else:
                    total += default if default is not None else trex.get(track_id, 0)
            entry = fragments.setdefault(track_id, [0, 0])
            entry[0] += total
            entry[1] += count

    boxes(data, 0, len(data), 0, sink, [0])
    audio = [t for t in tracks.values() if t['handler'] == b'soun']
    if not audio:
        refuse('MP4 without an audio track')
    best = Decimal(0)
    for track in audio:
        # Only AAC is measured: its access units decode to a fixed frame length at the rate its own configuration states,
        # which a decoder uses whatever the container's timescale or sample table claims.
        if track['codec'] != b'mp4a' or track['aac'] is None:
            refuse('MP4 audio that is not AAC')
        rate, frame = track['aac']
        units = track['stts_seconds_units']
        samples = max(track['samples'], track['stsz_samples'])
        if track['id'] in fragments:
            units += fragments[track['id']][0]
            samples += fragments[track['id']][1]
        seconds = Decimal(samples * frame) / Decimal(rate)
        if track['timescale']:
            seconds = max(seconds, Decimal(units) / Decimal(track['timescale']))
        if track['edit_units']:
            if not movie['timescale']:
                refuse('MP4 edit list without a movie timescale')
            # Each edit decodes whole access units, so allow one frame per edit (measured: ffmpeg plays 0.0155 s more per edit).
            seconds = max(seconds, Decimal(track['edit_units']) / Decimal(movie['timescale']) + Decimal(track['edits'] * frame) / Decimal(rate))
        best = max(best, seconds)
    return best


AAC_RATES = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350]


def descriptor(data, position, end):
    """(tag, body start, body end) of an MPEG-4 descriptor, or None."""
    if position >= end:
        return None
    tag, position, size = data[position], position + 1, 0
    for _ in range(4):
        if position >= end:
            return None
        byte = data[position]
        position += 1
        size = size << 7 | byte & 0x7F
        if not byte & 0x80:
            break
    return (tag, position, position + size) if position + size <= end else None


def aac_parameters(entries):
    """(core sample rate, samples per access unit) from the first sample entry's esds, or None when it is not MPEG-4 AAC."""
    if len(entries) < 36:
        return None
    size = struct.unpack('>I', entries[0:4])[0]
    entry = entries[:min(size, len(entries))]
    version = struct.unpack('>H', entry[16:18])[0]
    children = 36 + {0: 0, 1: 16, 2: 36}.get(version, 0)
    found = []

    def find(kind, body, depth):
        if kind == b'esds' and not found:
            found.append(entry[body[0]:body[1]])

    boxes(entry, children, len(entry), 0, find, [0])
    if not found:
        wave = entry.find(b'wave', children)  # QuickTime v1 keeps esds inside a 'wave' box
        if wave >= 4:
            boxes(entry, wave + 4, len(entry), 0, find, [0])
    if not found or len(found[0]) < 5:
        return None
    esds = found[0]
    es = descriptor(esds, 4, len(esds))
    if not es or es[0] != 0x03:
        return None
    flags, position = esds[es[1] + 2], es[1] + 3
    if flags & 0x80:  # depends-on stream id
        position += 2
    if flags & 0x40:  # URL: length byte, then the URL
        position += 1 + esds[position]
    if flags & 0x20:  # OCR stream id
        position += 2
    config = descriptor(esds, position, es[2])
    if not config or config[0] != 0x04 or esds[config[1]] != 0x40:  # 0x40: MPEG-4 audio
        return None
    specific = descriptor(esds, config[1] + 13, config[2])
    if not specific or specific[0] != 0x05:
        return None
    bits = BitReader(esds[specific[1]:specific[2]])

    def object_type():
        value = bits.read(5)
        return 32 + bits.read(6) if value == 31 else value

    def frequency():
        index = bits.read(4)
        return bits.read(24) if index == 15 else AAC_RATES[index]

    kind, rate = object_type(), frequency()
    bits.read(4)  # channel configuration
    if kind in (5, 29):  # SBR / parametric stereo wrap an AAC core; the frame length follows the core rate
        frequency()
        kind = object_type()
    if kind not in (1, 2, 4) or not 7350 <= rate <= 96000:
        return None  # AAC-LD/ELD and other object types use other frame lengths; they are not measured
    return rate, 960 if bits.read(1) else 1024


class BitReader:
    def __init__(self, data):
        self.data, self.position = data, 0

    def read(self, count):
        value = 0
        for _ in range(count):
            value = value << 1 | self.data[self.position >> 3] >> (7 - (self.position & 7)) & 1
            self.position += 1
        return value


# ── WebM / Matroska ────────────────────────────────────────────────────────
SEGMENT, CLUSTER, INFO, TRACKS = 0x18538067, 0x1F43B675, 0x1549A966, 0x1654AE6B
LEVEL1 = {CLUSTER, INFO, TRACKS, 0x1C53BB6B, 0x114D9B74, 0x1254C367, 0x1043A770, 0x1941A469}
MASTERS = {SEGMENT, CLUSTER, INFO, TRACKS, 0xAE, 0xA0}


def vint(data, position, keep_marker):
    if position >= len(data):
        return None, None, position
    first = data[position]
    length = next((n for n in range(1, 9) if first & (0x80 >> (n - 1))), None)
    if length is None or position + length > len(data):
        return None, None, position
    value = int.from_bytes(data[position:position + length], 'big')
    unknown = False
    if not keep_marker:
        value &= (1 << (7 * length)) - 1
        unknown = value == (1 << (7 * length)) - 1
    return value, unknown, position + length


def opus_packet_seconds(packet):
    if not packet:
        return Decimal(0)
    config, code = packet[0] >> 3, packet[0] & 3
    if config < 12:
        size = [Decimal('0.010'), Decimal('0.020'), Decimal('0.040'), Decimal('0.060')][config & 3]
    elif config < 16:
        size = [Decimal('0.010'), Decimal('0.020')][config & 1]
    else:
        size = [Decimal('0.0025'), Decimal('0.005'), Decimal('0.010'), Decimal('0.020')][config & 3]
    frames = 1 if code == 0 else 2 if code in (1, 2) else (packet[1] & 0x3F if len(packet) > 1 else 0)
    return size * frames


def matroska(data):
    state = {'scale': 1000000, 'audio': set(), 'opus': set(), 'track': {}, 'cluster': 0, 'first': None, 'last': None,
             'deltas': [], 'opus_seconds': Decimal(0), 'blocks': 0, 'laced': False, 'tracks_seen': False}
    counter = [0]

    def block(payload):
        track, _, at = vint(payload, 0, False)
        if track is None or at + 3 > len(payload):
            return
        if not state['tracks_seen']:
            refuse('WebM audio before its track list')
        if track not in state['audio']:
            return
        relative = struct.unpack('>h', payload[at:at + 2])[0]
        flags = payload[at + 2]
        stamp = state['cluster'] + relative
        if state['last'] is not None and stamp >= state['last']:
            state['deltas'].append(stamp - state['last'])
        state['first'] = stamp if state['first'] is None else min(state['first'], stamp)
        state['last'] = stamp if state['last'] is None else max(state['last'], stamp)
        state['blocks'] += 1
        if flags & 0x06:
            state['laced'] = True
        elif track in state['opus']:
            state['opus_seconds'] += opus_packet_seconds(payload[at + 3:])

    def walk(start, end, parent):
        position = start
        while position < end:
            counter[0] += 1
            if counter[0] > MAX_ITEMS:
                refuse('WebM structure too complex')
            element, _, after_id = vint(data, position, True)
            size, unknown, body = vint(data, after_id, False)
            if element is None or size is None:
                return position
            if parent == CLUSTER and element in LEVEL1:
                return position  # an unknown-size cluster ends where the next top-level element begins
            stop = end if unknown else min(body + size, end)
            if element in MASTERS:
                if element == TRACKS:
                    state['tracks_seen'] = True
                if element == 0xAE:
                    state['track'] = {}
                if element == CLUSTER:
                    state['cluster'] = 0
                stop = walk(body, stop, element) if unknown else (walk(body, stop, element), stop)[1]
                if element == 0xAE:
                    number, kind, codec = state['track'].get('number'), state['track'].get('type'), state['track'].get('codec')
                    if number is not None and kind == 2:
                        state['audio'].add(number)
                        if codec == b'A_OPUS':
                            state['opus'].add(number)
                position = stop
                continue
            value = data[body:stop]
            if element == 0x2AD7B1:
                state['scale'] = int.from_bytes(value, 'big')
                if not 1 <= state['scale'] <= 1000000000:
                    refuse('WebM timestamp scale out of range')
            elif element == 0xE7:
                state['cluster'] = int.from_bytes(value, 'big')
            elif element == 0xD7:
                state['track']['number'] = int.from_bytes(value, 'big')
            elif element == 0x83:
                state['track']['type'] = int.from_bytes(value, 'big')
            elif element == 0x86:
                state['track']['codec'] = bytes(value)
            elif element in (0xA3, 0xA1):
                block(value)
            position = stop
        return position

    walk(0, len(data), None)
    # Only unlaced Opus is measured: each packet's table of contents states exactly what a decoder plays, whatever the
    # timestamps or the timestamp scale claim. Browser recordings are unlaced Opus.
    if not state['audio'] or state['audio'] - state['opus']:
        refuse('WebM audio that is not Opus')
    if state['laced']:
        refuse('laced WebM audio')
    if not state['blocks'] or state['opus_seconds'] <= 0:
        refuse('WebM without audio blocks')
    tail = sorted(state['deltas'])[len(state['deltas']) // 2] if state['deltas'] else 0
    by_time = Decimal(state['last'] - state['first'] + tail) * Decimal(state['scale']) / Decimal(1000000000)
    return max(by_time, state['opus_seconds'])
