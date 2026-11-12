"""Parser-independent active-content scan of a PDF's raw bytes (finding P1, 2026-10-31).

⚠️ THIS SCAN IS THE GUARANTEE. The pypdf walk in engine.py is a second, independent layer and
must never again be the only one. pypdf reads only what its cross-reference chain points at,
and it recovers silently, even with strict=True: it DROPS a cross-reference section it cannot
read, re-locates an object by regex taking the FIRST match in the file, swaps in a different
catalog when the trailer's /Root is not one, and never looks inside stream data. A viewer that
reads the same bytes differently can then run a script the walk never saw, and the original
was served back byte for byte (docs/rebuild/pypdf-6.21.4.md, P1).

So this module does not ask any parser what the document is. It tokenizes the WHOLE file the
way a PDF lexer does and applies the active-content policy to every dictionary it can find:
every revision, unreferenced objects, trailers, bytes before the header and after %%EOF,
objects hidden inside comments, strings or the data of other streams, and the decoded contents
of every object stream. It never needs to know which revision is current or what is reachable:
a dictionary that carries an action is refused wherever it is, because SOME reader of the
original may reach it. Whatever it cannot decode completely is refused as unreadable, and so is
every stream it cannot be sure it read as every reader does: a stream object malformed
anywhere, decoding parameters from a malformed or self-contradicting dictionary (readers pair
such entries differently, so no one decoding is THE content), and a dictionary followed by
"stream" that the scan did not read as a stream's start.

The policy is exactly the engine's (the forbidden keys, /Type /EmbeddedFile, the active
annotation subtypes) plus action types named by /S, and /Encrypt as a key anywhere: encryption
is refused, never decrypted. Where readers disagree, the scan takes every reading:

- every value of a duplicated /Type, /Subtype or /S is judged (pypdf refuses duplicates and
  pdf.js keeps the last);
- a MALFORMED object (a value where a key belongs, a key without its value, a keyword no reader
  takes as a value, an R that ends no "N G R", a broken number or string) is judged on every
  policy name in it, at any depth and inside its strings, because a lenient reader re-pairs
  whatever follows the error;
- a policy name standing outside every container is refused, because a reader that skips junk
  up to the next whitespace runs a malformed dictionary past its end and takes such names for
  its entries.

The last two came from differential fuzzing against lenient pypdf. Three views are combined,
so that no one tokenizer disagreement can hide a key:

1. the sequential tokenization of every byte, skipping only stream data;
2. a one-object parse at EVERY "obj" and "trailer" keyword that view did not read as syntax
   (inside a comment, a string or another stream's data, or glued to its numbers as in
   "5 0obj"), because a reader that seeks to an xref offset, or rebuilds the table by
   searching, starts reading exactly there;
3. a byte-pattern pass: the long forbidden names anywhere outside ordinary stream data, in
   any spelling (#xx escapes, inside strings and comments), and the short ones and /Encrypt
   wherever they are shaped like a key (followed by a dictionary or a reference, /JS also by
   a string, /XFA also by an array).

Every bound is explicit (MAX_* below) and refuses as unreadable; nothing is truncated quietly.
⚠️ EVERY PASS IS LINEAR IN THE FILE AND EVERY STEP IS CHARGED to one work budget that grows with
the file: a pass that re-reads bytes is either memoized so that it does not, or charged for every
byte it re-reads (2026-11-01: a 10 KB file of predictor parameters, one long number token, one
line of comments and names each ran a 10 MiB-capable scan past the worker's 12 s while charged a
few units; test_pdf_active_content.ScanCost replays them).
Only the standard library is used, imported when the worker imports engine.py, BEFORE Landlock:
nothing in the application tree is readable after isolation.
"""

from __future__ import annotations

import base64
import binascii
from bisect import bisect_right
import re
import zlib

__all__ = ["Refusal", "scan", "FORBIDDEN_KEYS", "ACTIVE_ANNOTATIONS", "ACTION_TYPES"]

#: Exactly engine._scan_pdf's forbidden keys, without the slash.
FORBIDDEN_KEYS = frozenset((
    b"JavaScript", b"JS", b"OpenAction", b"AA", b"A", b"EmbeddedFiles", b"EmbeddedFile", b"EF",
    b"Launch", b"RichMediaContent", b"XFA", b"URI", b"SubmitForm", b"ImportData"))
#: Exactly pdf_inspect's refused annotation subtypes.
ACTIVE_ANNOTATIONS = frozenset((b"FileAttachment", b"RichMedia", b"Movie", b"Sound", b"Screen", b"3D"))
#: /S values that make a dictionary an action. Added with the raw scan so that an action is
#: refused even where the key that reaches it (/A, /AA, /OpenAction, /Next) cannot be read.
#: Measured over the ordinary corpus: no verdict change on 6.21.1, 6.21.2 or 6.21.4.
#: ⚠️ /Rendition, /Movie and /Sound added 2026-11-01 (COV-RENDITION): an unreferenced
#: << /S /Rendition >> was accepted while MuPDF reports it as an action (its own forbidden /S set
#: names /Rendition). No trigger reached it, so nothing could run it; it is refused anyway because
#: this module refuses an action dictionary wherever it is. The ordinary corpus is unchanged.
ACTION_TYPES = frozenset((b"JavaScript", b"Launch", b"SubmitForm", b"ImportData", b"RichMediaExecute",
                          b"GoToR", b"GoToE", b"URI", b"Rendition", b"Movie", b"Sound"))
#: Searched for in any position outside ordinary stream data, strings and comments included.
LONG_NAMES = (b"JavaScript", b"OpenAction", b"EmbeddedFiles", b"EmbeddedFile", b"Launch",
              b"RichMediaContent", b"SubmitForm", b"ImportData")

MAX_DECODED = 64 * 1024 * 1024        # decoded object-stream and xref-stream bytes, all together
#: ONE budget for everything the scan does, so that no mix of shapes can add up. A unit is about a
#: microsecond of CPU: a token or a skipped run is one unit; an escaped name, a closed dictionary
#: and a stream cost more; 3 bytes through a byte-by-byte decoder (LZW, RunLength, ASCII85, a
#: predictor row other than Up), one Up row, 64 bytes into or out of a decoder, 3 slashes for the
#: pattern pass, and SCAN_BYTES bytes crossed by any search that is not one of the scan's fixed
#: whole-buffer passes are one unit each. The weights are measured
#: (docs/rebuild/security-readiness.md).
#: ⚠️ THE BUDGET GROWS WITH THE FILE: MAX_WORK units for any file plus one per BYTES_PER_WORK
#: bytes, so that it bounds what a file costs for its size, not how large an ordinary file may
#: be. A fixed 1,000,000 refused a 5.9 MiB graph of 97,000 small objects (2026-11-01); a 10 MiB
#: file now has 3,621,440 units, about 3.5 s of CPU on that host, against the worker's 12 s.
MAX_WORK = 1_000_000
BYTES_PER_WORK = 4
SCAN_BYTES = 256
MAX_GAP_MEMO = 1 << 17                # line ends whose following gap is remembered, per buffer
MAX_HIDDEN_ANCHORS = 20_000           # "obj"/"trailer" keywords outside the sequential view's syntax
MAX_ANCHOR_BYTES = 32 * 1024 * 1024   # bytes re-read by one-object parses at those anchors
MAX_OBJECT_STREAMS = 2_000            # object-stream decodings
MAX_DEPTH = 256                       # dictionary/array nesting
MAX_STREAM_NESTING = 4                # object streams inside decoded object streams
MAX_DEFINITIONS = 150_000             # object definitions kept (the pypdf walk refuses 100,000 objects)
MAX_VARIANTS = 8                      # distinct definitions of one object, and decodings of one stream

_WHITESPACE = b"\x00\t\n\x0c\r "
_DELIMITING = frozenset(b"\x00\t\n\x0c\r ()<>[]{}/%")   # bytes that end a regular token
#: What may stand right before an "obj" or "trailer" keyword that some reader still reads as one:
#: pdf.js ends a number at its first non-number character, so "5 0obj" is a header there.
_BEFORE_KEYWORD = _DELIMITING | frozenset(b"0123456789.+-")
_REG = rb"[^\x00\t\n\x0c\r ()<>\[\]{}/%]"            # a PDF "regular" character
# ⚠️ EVERY REPEATED GROUP BELOW IS POSSESSIVE (*+, ++). Python's regex engine otherwise keeps
# backtracking state for each repetition of a group: a 60 MiB run of "1 " took 6.5 s and 5.5 GB.
_GAPS = rb"(?:[\x00\t\n\x0c\r ]+|%[^\r\n]*)*+"         # whitespace and comments, possibly none

_TOKEN = re.compile(
    rb"[\x00\t\n\x0c\r ]*(?:"
    rb"(%[^\r\n]*)"                       # 1 comment
    rb"|(<<|>>|[\[\]{})>])"               # 2 structure, or a stray delimiter
    rb"|(<[^>]*>?)"                       # 3 hex string: every reader ends it at the first '>'
    rb"|(\((?:[^()\\]++|\\[\s\S])*+\))"   # 4 literal string without nested parentheses
    rb"|(\()"                             # 5 literal string with nesting: balanced by hand
    rb"|/(" + _REG + rb"*)"               # 6 name
    rb"|(" + _REG + rb"+)"                # 7 number or keyword
    rb")")
_STRING_SPECIAL = re.compile(rb"[()\\]")
# ⚠️ GAPS BETWEEN TOKENS ARE CROSSED BY _gap_end, MEMOIZED AND CHARGED. A regex look-ahead across
# whitespace and comments is free to the budget, and from an anchor at the end of a comment line
# it crosses every following comment line: 900,000 such lines took more than 30 s.
_SPACE = re.compile(rb"[\x00\t\n\x0c\r ]*")
_INLINE_SPACE = re.compile(rb"[\x00\t\x0c ]*")         # whitespace that does not end a line
_SPACES_ONLY = re.compile(rb" *")
_UINT = re.compile(rb"\d{1,10}")
_HEADER_BEFORE = re.compile(rb"(\d{1,10})[\x00\t\n\x0c\r ]+(\d{1,5})[\x00\t\n\x0c\r ]*\Z")
# The keyword first: a leading lookbehind would defeat the literal search (1.45 s on 10 MiB).
# The byte before it is checked by the caller.
_OBJ_ANCHOR = re.compile(rb"obj(?!" + _REG + rb")")
_TRAILER_ANCHOR = re.compile(rb"trailer(?!" + _REG + rb")")
_ENDOBJ = re.compile(rb"endobj")
#: A whole run of whitespace and comments (_unread_streams crosses each run once).
_GAP_RUN = re.compile(_GAPS)
_INT = re.compile(_GAPS + rb"(\d{1,10})(?!" + _REG + rb")")
# Runs that carry nothing for the policy are skipped with one character-class search each
# (5 ns/byte; a possessive group costs 28): the contents of an array whose items are not needed
# (a name in an array is never a key of a well-formed object; each skipped run is remembered and
# judged with the rest if its object turns out malformed: _judge_object), integers at top level,
# and a classic xref table's body.
_ARRAY_STOP = re.compile(rb"[()<>\[\]{}%]")
_INT_STOP = re.compile(rb"[^0-9\x00\t\n\x0c\r ]")
_XREF_STOP = re.compile(rb"[^0-9fn\x00\t\n\x0c\r ]")
_EOL = re.compile(rb"[\r\n]")
_DIGITS = re.compile(rb"\d{1,18}")
# ⚠️ A NUMBER IS MATCHED POSSESSIVELY. "\d+\.?\d*" backtracks over every split of a digit run
# before failing at a non-digit: one 64,000-digit token followed by "x" took 30 s for one unit.
#: A whole token that is a number. "333\xe7389" is not: pdf.js reads 333 and then junk.
_NUMBER_BODY = rb"[+-]?(?:\d++(?:\.\d*+)?|\.\d++)"
_NUMBER = re.compile(_NUMBER_BODY + rb"\Z")
_HEX_JUNK = re.compile(rb"[^0-9A-Fa-f\x00\t\n\x0c\r ]")
_HEADER = re.compile(rb"[\x00\t\n\x0c\r ]+(\d{1,10})[\x00\t\n\x0c\r ]+(obj)(?!" + _REG + rb")")


_HEX_PAIRS = {bytes((a, b)): bytes((int(chr(a) + chr(b), 16),))
              for a in b"0123456789abcdefABCDEF" for b in b"0123456789abcdefABCDEF"}


def _unescape(raw):
    """Decode #xx in a name. An invalid escape keeps its '#', as in pdf.js and pypdf, so it can
    never spell a forbidden name in one reader and not in another."""
    if 0x23 not in raw:
        return raw
    parts = raw.split(b"#")
    out = [parts[0]]
    for part in parts[1:]:
        decoded = _HEX_PAIRS.get(part[:2])
        out.append(decoded + part[2:] if decoded is not None else b"#" + part)
    return b"".join(out)


def _spelled(name):
    """A pattern for `name` that also matches every #xx spelling of each character."""
    parts = []
    for byte in name:
        hexes = b"".join(b"[" + bytes((c,)).upper() + bytes((c,)).lower() + b"]" if chr(c).isalpha()
                         else bytes((c,)) for c in b"%02x" % byte)
        parts.append(b"(?:" + re.escape(bytes((byte,))) + b"|#" + hexes + b")")
    return b"".join(parts)


def _names(names):
    return (b"/(?:" + b"|".join(_spelled(n) for n in sorted(names, key=len, reverse=True))
            + b")(?!" + _REG + b")")


_BACKUP_LONG = re.compile(_names(LONG_NAMES))
#: Every name the policy can refuse, as a key or as the value of /Type, /Subtype or /S.
_POLICY_NAMES = re.compile(_names(FORBIDDEN_KEYS | ACTIVE_ANNOTATIONS | ACTION_TYPES | {b"Encrypt"}))
#: A token inside an array that no reader takes as a value: not a number, R, true, false or null.
#: (The number is possessive here too: the same 32,000-digit run took 16 s.)
_ARRAY_JUNK = re.compile(rb"(?<![^\x00\t\n\x0c\r ()<>\[\]{}%])(?!(?:" + _NUMBER_BODY + rb"|R|true|false|null)(?!"
                         + _REG + rb"))" + _REG + rb"++")
#: An "R" token, and the "N G " that must stand right before it. ⚠️ AN R THAT ENDS NO "N G R" IS
#: JUNK, NOT NOTHING: PDFium ends an array at a keyword it cannot read and reads the rest into
#: the enclosing dictionary, and lenient pypdf does the same after its error (found by fuzzing:
#: "/W [ 48 [ 722 R 556 ] ... /Subtype /FileAttachment ... ]" became a font's subtype).
_R_TOKEN = re.compile(rb"(?<![^\x00\t\n\x0c\r ()<>\[\]{}%])R(?!" + _REG + rb")")
_REF_BEFORE = re.compile(rb"(?<![^\x00\t\n\x0c\r ()<>\[\]{}%])\d{1,10}[\x00\t\n\x0c\r ]+\d{1,10}[\x00\t\n\x0c\r ]+\Z")
#: Short keys count only where they are shaped like a key (judged in _key_shaped).
_BACKUP_SHORT = re.compile(_names((b"A", b"AA", b"EF", b"URI", b"Encrypt", b"JS", b"XFA")))

# What a name means to the policy, looked up once per name token.
_KEY = 1          # forbidden as a dictionary key
_ENCRYPT = 2      # /Encrypt as a key
_EMBEDDED = 4     # /EmbeddedFile, refused as the value of /Type
_ANNOT = 8        # refused as the value of /Subtype
_ACTION = 16      # refused as the value of /S
_POLICY = _KEY | _ENCRYPT | _EMBEDDED | _ANNOT | _ACTION
_HAS_N, _HAS_FIRST, _HAS_OBJSTM, _HAS_W = 32, 64, 128, 256
_NAME_BITS = {}
for _name in FORBIDDEN_KEYS:
    _NAME_BITS[_name] = _NAME_BITS.get(_name, 0) | _KEY
for _name in ACTIVE_ANNOTATIONS:
    _NAME_BITS[_name] = _NAME_BITS.get(_name, 0) | _ANNOT
for _name in ACTION_TYPES:
    _NAME_BITS[_name] = _NAME_BITS.get(_name, 0) | _ACTION
_NAME_BITS[b"EmbeddedFile"] |= _EMBEDDED
_NAME_BITS.update({b"Encrypt": _ENCRYPT, b"N": _HAS_N, b"First": _HAS_FIRST, b"ObjStm": _HAS_OBJSTM,
                   b"W": _HAS_W})
#: Dictionary entries remembered with their values; everything else is only policy-checked.
#: /F and /DP are kept because pdf.js reads them as /Filter and /DecodeParms of a stream.
_KEPT = frozenset((b"Type", b"Subtype", b"S", b"Length", b"Filter", b"DecodeParms", b"F", b"DP", b"N",
                   b"First", b"W", b"Predictor", b"Colors", b"BitsPerComponent", b"Columns", b"EarlyChange"))
_KEPT_CONTAINERS = frozenset((b"Filter", b"DecodeParms", b"F", b"DP", b"W"))
#: Every value of these keys is judged, not only the first: readers disagree on which duplicate wins.
_VALUE_BITS = {b"Type": _EMBEDDED, b"Subtype": _ANNOT, b"S": _ACTION}
#: Marks a dictionary that defines one of its kept entries twice with different values.
_CONFLICT = object()
#: Marks a dictionary whose key/value pairing broke: its kept entries are one pairing of several.
_MALFORMED = object()
#: Stands for an object defined in more than MAX_VARIANTS different ways.
_AMBIGUOUS = object()
_MAX_ITEMS = 64
_STR = ("s",)
_SCALAR = ("x",)
_JUNK = ("j",)


class Refusal(Exception):
    """kind is 'active', 'annotation', 'encrypted' or 'unreadable'; `reason` is for tests and logs only."""

    def __init__(self, kind, reason):
        super().__init__(reason)
        self.kind = kind
        self.reason = reason


class _Limit(Refusal):
    """A work bound was reached: always fatal, never treated as one undecodable stream."""

    def __init__(self, reason):
        super().__init__("unreadable", reason)


def _unreadable(reason):
    return Refusal("unreadable", reason)


def _refuse_name(bits, where):
    """The refusal for a policy name that some reader may take as a key, by what it names."""
    if bits & _ENCRYPT:
        raise Refusal("encrypted", "/Encrypt " + where)
    if bits & _ANNOT and not bits & _KEY:
        raise Refusal("annotation", "active annotation subtype " + where)
    raise Refusal("active", "forbidden name " + where)


class _Frame:
    __slots__ = ("is_dict", "state", "key", "kept", "key_bits", "any_bits", "value_bits", "bad", "n1", "n2",
                 "items", "keep", "obj", "start")

    def __init__(self, is_dict, keep, obj, start):
        self.is_dict = is_dict
        self.state = 0          # dictionaries: 0 key expected, 1 value expected, 2 and 3 integers seen
        self.key = None
        self.kept = None
        self.key_bits = 0       # policy bits of names in key position
        self.any_bits = 0       # policy bits of every name at this level
        self.value_bits = 0     # refused values of /Type, /Subtype or /S, from any of their definitions
        self.bad = False        # key/value pairing broke: every name at this level is judged
        self.n1 = self.n2 = None
        self.items = [] if keep and not is_dict else None
        self.keep = keep
        self.obj = obj          # the (number, generation) this container is the value of
        self.start = start


class _Stream:
    __slots__ = ("buf", "kept", "bits", "start", "end", "obj", "depth", "decoded")

    def __init__(self, buf, kept, bits, start, end, obj, depth):
        self.buf, self.kept, self.bits, self.start, self.end = buf, kept or {}, bits, start, end
        self.obj, self.depth, self.decoded = obj, depth, None


def budget(size):
    """The work units a file of `size` bytes may use (MAX_WORK's comment says why it grows)."""
    return MAX_WORK + size // BYTES_PER_WORK


class _Scanner:
    def __init__(self, data):
        self.data = data
        self.budget = budget(len(data))
        self.work = self.budget
        self.decoded = 0
        self.slow = 0
        self.anchor_bytes = 0
        self.definitions = {}       # (number << 16 | generation) -> a definition, or a list of them
        self.definition_count = 0
        self.streams = []
        self.stream_at = {}         # (id(buffer), data start) -> stream: one entry however it was found
        self.canonical_obj = set()  # "obj" keywords the sequential view read as syntax
        self.canonical_trailer = set()
        self.regions = []           # the file's stream-data spans in the sequential view
        self.hidden_ranges = []     # spans of objects found at hidden anchors inside stream data
        self.stream_starts = set()  # "stream" keywords in the file read as a stream's start
        self.stats = {"hidden_anchors": 0, "object_streams": 0}
        # What _gap_end remembers about the buffer it last crossed gaps in (see there).
        self._gap_buf = None
        self._gap_limit = -1
        self._gap_from = {}         # a position asked about -> where the gap from it ends
        self._gap_memo = {}         # a line end -> where the gap from it ends
        self._gap_lines = []        # (from, line end): the last few comment lines searched
        self._shaped = {}           # (gap end, name class) -> _key_shaped's answer
        self._refs = {}             # gap end -> _ref_after's answer from there

    # ---------------------------------------------------------------- policy
    def _close_dict(self, frame):
        if frame.state == 2:                        # a trailing integer value
            self._keep(frame, ("i", frame.n1))
            frame.state = 0
        kept = frame.kept or {}
        if frame.bad or frame.state != 0:
            # The pairing is ambiguous, so some reader may take any name at this level as a key.
            bits = frame.any_bits
            if bits & _ENCRYPT:
                raise Refusal("encrypted", "/Encrypt in a malformed dictionary")
            if bits & _ANNOT:
                raise Refusal("annotation", "active annotation subtype in a malformed dictionary")
            if bits & (_KEY | _EMBEDDED | _ACTION):
                raise Refusal("active", "forbidden name in a malformed dictionary")
            kept[_MALFORMED] = True
            return ("d", kept, bits)
        if frame.key_bits & _ENCRYPT:
            raise Refusal("encrypted", "/Encrypt key")
        if frame.key_bits & _KEY:
            raise Refusal("active", "forbidden key")
        if frame.value_bits & _EMBEDDED:
            raise Refusal("active", "/Type /EmbeddedFile")
        if frame.value_bits & _ANNOT:
            raise Refusal("annotation", "active annotation subtype")
        if frame.value_bits & _ACTION:
            raise Refusal("active", "action type")
        return ("d", kept, frame.any_bits)

    @staticmethod
    def _keep(frame, value):
        key = frame.key
        if key in _KEPT:
            kept = frame.kept
            if kept is None:
                kept = frame.kept = {}
            if key not in kept:
                kept[key] = value
            elif kept[key] != value:
                kept[_CONFLICT] = True       # pypdf refuses duplicates; pdf.js keeps the last
            if value[0] == "n" and key in _VALUE_BITS:
                frame.value_bits |= _NAME_BITS.get(value[1], 0) & _VALUE_BITS[key]

    def _define(self, obj, summary):
        """Remember a definition that a stream parameter may refer to (scalars and strings never are)."""
        if obj is None or summary is None or summary[0] in "sxj":
            return
        self.definition_count += 1
        if self.definition_count > MAX_DEFINITIONS:
            raise _Limit("too many object definitions")
        key = obj[0] << 16 | (obj[1] & 0xFFFF)
        known = self.definitions.get(key)
        # ⚠️ THE SAME SUMMARY IS RECOGNISED BY IDENTITY FIRST. An object stream's index can name one
        # already-read value thousands of times, and comparing it structurally with each other
        # definition first took 7 s for 2 units an entry. A summary that is new was parsed, and
        # charged, token by token; comparing it with at most MAX_VARIANTS others costs no more.
        if known is None:
            self.definitions[key] = summary
        elif known is _AMBIGUOUS or known is summary:
            return
        elif isinstance(known, list):
            if not any(item is summary for item in known) and summary not in known:
                if len(known) >= MAX_VARIANTS:
                    self.definitions[key] = _AMBIGUOUS
                else:
                    known.append(summary)
        elif known != summary:
            self.definitions[key] = [known, summary]

    def _definitions(self, number, generation):
        known = self.definitions.get(number << 16 | (generation & 0xFFFF))
        if known is _AMBIGUOUS:
            raise _unreadable("a stream parameter is defined in too many ways")
        return known if known is None or isinstance(known, list) else [known]

    # ---------------------------------------------------------------- tokenizer
    def _string_end(self, buf, pos, end):
        depth = 0
        search = _STRING_SPECIAL.search
        while True:
            m = search(buf, pos, end)
            if m is None:
                return end
            self.work -= 1
            if self.work < 0:
                raise _Limit("work limit")
            at = m.start()
            c = buf[at]
            if c == 0x5C:
                pos = at + 2
            elif c == 0x28:
                depth += 1
                pos = at + 1
            else:
                depth -= 1
                pos = at + 1
                if depth == 0:
                    return pos

    @staticmethod
    def _stream_data(buf, after_keyword, end, kept):
        """Where stream data starts and ends, and where syntax resumes.

        A direct /Length counts when "endstream" follows it; otherwise the data ends at the first
        "endstream". Either way those bytes are never read as syntax here: an object hidden in
        them is found by its own "obj" keyword instead (_anchors).
        """
        start = after_keyword
        spaces = _SPACES_ONLY.match(buf, start, end)
        start = spaces.end()
        if buf.startswith(b"\r\n", start):
            start += 2
        elif start < end and buf[start] in (0x0A, 0x0D):
            start += 1
        length = kept.get(b"Length") if kept else None
        if length is not None and length[0] == "i":
            stop = start + length[1]
            if stop <= end:
                at = _SPACE.match(buf, stop, end).end()
                if buf.startswith(b"endstream", at):
                    return start, stop, at + 9
        found = buf.find(b"endstream", start, end)
        if found < 0:
            return start, end, end
        stop = found
        if stop > start and buf[stop - 1] == 0x0A:
            stop -= 1
        if stop > start and buf[stop - 1] == 0x0D:
            stop -= 1
        return start, stop, found + 9

    def _add_stream(self, buf, summary, start, stop, obj, depth):
        self._charge(4)     # measured: a stream costs about four tokenizer steps
        key = (id(buf), start)
        stream = self.stream_at.get(key)
        if stream is None:
            stream = _Stream(buf, summary[1], summary[2], start, stop, obj, depth)
            self.stream_at[key] = stream
            self.streams.append(stream)
        elif stream.obj is None:
            stream.obj = obj
        return stream

    def _walk(self, buf, pos, end, mode, depth=0, values=None):
        """Tokenize buf[pos:end].

        mode "file" (the whole file) and "decoded" (a whole decoded object stream) read every
        token; "one" reads a single value, the way a reader does at an object's offset. In
        "decoded" mode `values` receives {token start: summary} of each top-level container
        and name, so that objects at their header offsets need not be parsed twice.
        Returns (the value's summary in "one" mode, else None; the position reached).
        """
        match = _TOKEN.match
        name_bits = _NAME_BITS
        kept_keys = _KEPT
        stack = []
        is_file = mode == "file"
        one = mode == "one"
        ints = []            # the last two consecutive top-level integers: the "N G" of a header
        obj = None           # the object whose header was just read (file mode)
        obj_open = False     # its value has not been read yet
        last_dict = None     # a dictionary that just completed at top level, for "stream"
        last_obj = None
        # ⚠️ ONE MALFORMED TOKEN ANYWHERE IN AN OBJECT AND EVERY NAME IN IT IS JUDGED. A lenient
        # reader that meets junk inside an array gives up on the array and on its dictionary and
        # reads the rest as entries of the enclosing dictionary: lenient pypdf took glyph names
        # after a stray "r" in /Differences for keys, and an inserted "/Subtype /FileAttachment"
        # after a corrupt number in /W for an annotation subtype (found by differential fuzzing).
        top_start, top_junk, top_runs, top_named = None, False, [], False
        work = self.work
        try:
            while True:
                m = match(buf, pos, end)
                if m is None:
                    pos = end
                    break
                k = m.lastindex
                pos = m.end()
                work -= 1
                if work < 0:
                    raise _Limit("work limit")
                if k == 1:
                    continue
                start = m.start(k)
                if k == 2:
                    c = buf[start]
                    if c == 0x3C or c == 0x5B:                  # << or [
                        if len(stack) >= MAX_DEPTH:
                            raise _Limit("nesting depth")
                        if stack:
                            parent = stack[-1]
                            keep = parent.keep if not parent.is_dict else parent.key in _KEPT_CONTAINERS
                            holder = None
                        else:
                            keep = True
                            holder = obj if obj_open else None
                            obj_open = False
                            top_start, top_junk, top_runs, top_named = start, False, [], False
                        frame = _Frame(c == 0x3C, keep, holder, start)
                        stack.append(frame)
                        last_dict = None
                        ints = []
                        if frame.items is None and not frame.is_dict:
                            self.work = work
                            skipped = pos
                            pos = self._skip_array(buf, pos, end)
                            if pos > skipped:
                                top_runs.append((skipped, pos))
                                if not top_named:
                                    top_named = self._names_in(buf, skipped, pos)
                            work = self.work
                        continue
                    if c == 0x3E and pos - start == 2:            # >>
                        if not stack:
                            continue
                        if not stack[-1].is_dict:
                            value = _JUNK
                            top_junk = True
                        else:
                            frame = stack.pop()
                            value = self._close_dict(frame)
                            if _MALFORMED in value[1]:
                                top_junk = True      # e.g. a key without its value: pdf.js reads on
                            work -= 1
                            start = frame.start
                            if frame.obj is not None:
                                self._define(frame.obj, value)
                            if not stack:
                                self.work = work
                                self._judge_object(buf, top_start, pos, top_junk, top_runs, top_named)
                                work = self.work
                    elif c == 0x5D:                              # ]
                        if not stack:
                            continue
                        if stack[-1].is_dict:
                            value = _JUNK
                            top_junk = True
                        else:
                            frame = stack.pop()
                            value = ("a", tuple(frame.items) if frame.items is not None else None)
                            start = frame.start
                            if frame.obj is not None:
                                self._define(frame.obj, value)
                            if not stack:
                                self.work = work
                                self._judge_object(buf, top_start, pos, top_junk, top_runs, top_named)
                                work = self.work
                    else:                                        # { } ) or a single >
                        if not stack:
                            last_dict = None
                            ints = []
                            continue
                        value = _JUNK
                        top_junk = True
                elif k == 6:
                    raw = m.group(6)
                    if 0x23 in raw:
                        raw = _unescape(raw)
                        work -= 1
                    value = ("n", raw)
                    if stack:
                        frame = stack[-1]
                        if frame.is_dict:
                            bits = name_bits.get(raw, 0)
                            frame.any_bits |= bits
                            if bits & _POLICY:
                                top_named = True
                            state = frame.state
                            if state == 0:
                                frame.key = raw
                                frame.key_bits |= bits
                                frame.state = 1
                            elif state == 1:
                                if frame.key in kept_keys:
                                    self._keep(frame, value)
                                frame.state = 0
                            elif state == 2:                     # the integer was the value
                                self._keep(frame, ("i", frame.n1))
                                frame.key = raw
                                frame.key_bits |= bits
                                frame.state = 1
                            else:                                # two integers and no R
                                frame.bad = top_junk = True
                            continue
                        if name_bits.get(raw, 0) & _POLICY:
                            top_named = True
                        if frame.items is not None:
                            self._append(frame, value)
                        continue
                    # ⚠️ A POLICY NAME OUTSIDE EVERY CONTAINER IS REFUSED, whether it stands between
                    # objects or is an object's whole value. Lenient pypdf skips an unreadable token
                    # up to the next WHITESPACE, so junk glued to ">>" carries a dictionary past its
                    # end, and it reads the names that follow as entries until an "endobj": fuzzing
                    # found "1023/Subtype /FileAttachment" after startxref read into a trailer.
                    bits = name_bits.get(raw, 0)
                    if bits & _POLICY:
                        _refuse_name(bits, "outside every container")
                elif k == 3 or k == 4:
                    value = _STR
                    if k == 3 and stack and (buf[pos - 1] != 0x3E or _HEX_JUNK.search(buf, start + 1, pos - 1)):
                        top_junk = True                    # unterminated, or not hexadecimal
                elif k == 5:
                    self.work = work        # helpers charge self.work: hand the count over and back
                    pos = self._string_end(buf, start, end)
                    work = self.work
                    value = _STR
                else:
                    tok = m.group(7)
                    if tok.isdigit() and len(tok) <= 18:
                        if stack:
                            frame = stack[-1]
                            if frame.is_dict:
                                state = frame.state
                                if state == 1:
                                    frame.n1 = int(tok)
                                    frame.state = 2
                                elif state == 2:
                                    frame.n2 = int(tok)
                                    frame.state = 3
                                else:
                                    frame.bad = top_junk = True
                            elif frame.items is not None:
                                self._append(frame, ("i", int(tok)))
                            continue
                        if one or obj_open:
                            self.work = work
                            ref = self._ref_after(buf, pos, end)
                            work = self.work
                            value = ("r", int(tok), ref[0]) if ref is not None else ("i", int(tok))
                            if ref is not None:
                                pos = ref[1]
                            if one:
                                return value, pos
                            self._define(obj, value)
                            obj_open = False
                            continue
                        # Top-level integers matter only as the last two before "obj". The usual
                        # "N G obj" is read in one match; anything else as a run of integers.
                        header = _HEADER.match(buf, pos, end) if is_file else None
                        if header is not None:
                            obj = (int(tok), int(header.group(1)))
                            obj_open = True
                            self.canonical_obj.add(header.start(2))
                            pos = header.end()
                            last_dict = None
                            ints = []
                            continue
                        pos = self._skip_class(buf, pos, end, _INT_STOP)
                        found = [int(n) for n in _DIGITS.findall(buf, max(start, pos - 48), pos)[-2:]]
                        ints = (ints + found)[-2:] if len(found) == 1 else found
                        last_dict = None
                        continue
                    if tok in (b"true", b"false", b"null") or _NUMBER.match(tok):
                        value = _SCALAR
                    elif stack:
                        frame = stack[-1]
                        if tok == b"R":
                            if frame.is_dict:
                                if frame.state == 3:
                                    self._keep(frame, ("r", frame.n1, frame.n2))
                                    frame.state = 0
                                else:
                                    frame.bad = top_junk = True
                            elif frame.items is not None:
                                items = frame.items
                                if len(items) >= 2 and items[-1][0] == "i" and items[-2][0] == "i":
                                    generation = items.pop()[1]
                                    items[-1] = ("r", items[-1][1], generation)
                                else:
                                    top_junk = True              # an R that ends no "N G R"
                            elif not _REF_BEFORE.search(buf, max(0, start - 32), start):
                                top_junk = True                  # the same, past the kept items
                        elif frame.is_dict:
                            frame.bad = top_junk = True
                        else:
                            top_junk = True                       # a keyword no reader takes as a value
                        continue
                    else:                                        # a keyword at top level
                        if one:
                            return None, start
                        if tok == b"obj" and is_file:
                            self.canonical_obj.add(start)
                            obj = (ints[0], ints[1]) if len(ints) == 2 else None
                            obj_open = obj is not None
                        elif tok == b"stream":
                            if last_dict is not None:
                                data_start, stop, resume = self._stream_data(buf, pos, end, last_dict[1])
                                self.work = work
                                # top_junk and top_runs still describe last_dict: no top-level
                                # container has opened since it closed.
                                self._refuse_malformed_stream(buf, last_dict, top_junk, top_runs)
                                self._add_stream(buf, last_dict, data_start, stop, last_obj, depth)
                                if is_file:
                                    self.stream_starts.add(start)
                                work = self.work
                                if is_file:
                                    self.regions.append((data_start, stop))
                                pos = resume
                        elif tok == b"endobj":
                            obj, obj_open = None, False
                        elif tok == b"xref":
                            body = pos
                            pos = self._skip_class(buf, pos, end, _XREF_STOP)
                            last_dict = None
                            ints = [int(n) for n in _DIGITS.findall(buf, max(body, pos - 48), pos)[-2:]]
                            continue
                        elif tok == b"trailer":
                            if is_file:
                                self.canonical_trailer.add(start)
                            obj, obj_open = None, False
                        last_dict = None
                        ints = []
                        continue
                # A complete value: hand it to the enclosing container, or to the top level.
                if stack:
                    frame = stack[-1]
                    if frame.is_dict:
                        state = frame.state
                        if state == 1:
                            if frame.key in kept_keys:
                                self._keep(frame, value)
                            frame.state = 0
                        else:
                            if state == 2:
                                self._keep(frame, ("i", frame.n1))
                            frame.bad = top_junk = True          # a value where a key belongs
                            frame.state = 0
                    elif frame.items is not None:
                        self._append(frame, value)
                    else:
                        self.work = work
                        skipped = pos
                        pos = self._skip_array(buf, pos, end)
                        if pos > skipped:
                            top_runs.append((skipped, pos))
                            if not top_named:
                                top_named = self._names_in(buf, skipped, pos)
                        work = self.work
                    continue
                if one:
                    if value[0] == "d":
                        self.work = work
                        after = self._gap_end(buf, pos, end)
                        work = self.work
                        if buf.startswith(b"stream", after) and (after + 6 == end or buf[after + 6] in _DELIMITING):
                            data_start, stop, resume = self._stream_data(buf, after + 6, end, value[1])
                            self.work = work
                            self._refuse_malformed_stream(buf, value, top_junk, top_runs)
                            self._add_stream(buf, value, data_start, stop, None, depth)
                            if buf is self.data:
                                self.stream_starts.add(after)
                            work = self.work
                            return value, resume
                    return value, pos
                if values is not None and value[0] in "dan":
                    values[start] = value
                if obj_open:
                    if value[0] == "n":
                        self._define(obj, value)
                    obj_open = False
                if value[0] == "d":
                    last_dict, last_obj = value, obj
                else:
                    last_dict = None
                ints = []
            # End of the buffer: judge every container still open (a truncated file included).
            result = None
            if stack:
                top_junk = True                                   # an object that never closes
            while stack:
                frame = stack.pop()
                if frame.is_dict:
                    result = self._close_dict(frame)
                    if frame.obj is not None:
                        self._define(frame.obj, result)
                else:
                    result = ("a", None)
                if not stack:
                    self.work = work
                    self._judge_object(buf, top_start, end, top_junk, top_runs, top_named)
                    work = self.work
            return (result if one else None), pos
        finally:
            self.work = work

    def _names_in(self, buf, start, stop):
        """Does a skipped array run hold a name the policy could refuse? (Charged by its slashes.)"""
        self._charge(buf.count(b"/", start, stop) // 3)
        return _POLICY_NAMES.search(buf, start, stop) is not None

    def _judge_object(self, buf, start, stop, junk, runs, named):
        """A malformed object is refused when it holds any policy name, at any depth, in any role,
        inside its strings included: a malformed string is where a lenient reader's tokens and
        this scan's part ways."""
        if not junk and (not named or not self._runs_junk(buf, runs)):
            return
        self._charge((stop - start) // 64 + buf.count(b"/", start, stop) // 3)
        m = _POLICY_NAMES.search(buf, start, stop)
        if m is not None:
            _refuse_name(_NAME_BITS.get(_unescape(m.group(0))[1:], 0), "in a malformed object")

    def _refuse_malformed_stream(self, buf, summary, junk, runs):
        """⚠️ A STREAM OBJECT THAT IS MALFORMED ANYWHERE IS REFUSED AS UNREADABLE: which entries a
        reader keeps, and where it ends the dictionary, cannot be known. Fuzzing found both: after
        the junk "o" in "/Length 29 0 o /N 9 /First 57 /Filter /FlateDecode" this scan kept no
        more entries and "decoded" the compressed bytes as they were, while pdf.js and pypdf
        re-paired the entries, inflated the data and read a link with a URI action; and lenient
        pypdf, skipping junk up to the next whitespace, ran a form XObject's dictionary through
        its data and read an /OpenAction there. No ordinary file of the corpus has such a stream."""
        if junk or _MALFORMED in summary[1] or self._runs_junk(buf, runs):
            raise _unreadable("a stream object is malformed")

    def _runs_junk(self, buf, runs):
        """Does a skipped array run hold a token no reader takes as an array item?"""
        for a, b in runs:
            self._charge((b - a) // 16 + 1)
            if _ARRAY_JUNK.search(buf, a, b) or self._stray_r(buf, a, b):
                return True
        return False

    def _stray_r(self, buf, start, stop):
        """Does a skipped run hold an R that ends no "N G R"? One charged step per R."""
        for m in _R_TOKEN.finditer(buf, start, stop):
            self._charge(1)
            if _REF_BEFORE.search(buf, max(start, m.start() - 32), m.start()) is None:
                return True
        return False

    def _gap_end(self, buf, pos, end):
        """Past whitespace and comments, as a lexer skips them.

        ⚠️ LINEAR HOWEVER OFTEN IT IS ASKED. It is asked after every short policy name in the raw
        bytes, after integers and after dictionaries, from anchors that may sit anywhere, and a gap
        can run over many lines: 40,000 names on ONE comment line took 19 s when each crossed the
        rest of the line, and 10,000 anchors on one line in stream data took 64 s. So the end of a
        comment line, once found, answers for every position on that line; where the gap goes from
        a line end on is remembered, so each line end is crossed from once per buffer; and every
        comment and every SCAN_BYTES bytes crossed are charged, memo or not. (`end` is always the
        buffer's length: every walk reads to the end of its buffer.)
        """
        if buf is not self._gap_buf or end != self._gap_limit:
            self._gap_buf, self._gap_limit = buf, end
            self._gap_memo, self._gap_from, self._gap_lines, self._shaped, self._refs = {}, {}, [], {}, {}
        self._charge(1)
        found = self._gap_from.get(pos)
        if found is None:
            found = self._gap_cross(buf, pos, end)
            if len(self._gap_from) < MAX_GAP_MEMO:
                self._gap_from[pos] = found
        return found

    def _gap_cross(self, buf, pos, end):
        stop = _INLINE_SPACE.match(buf, pos, end).end()
        self._charge((stop - pos) // SCAN_BYTES)
        if stop >= end:
            return end
        c = buf[stop]
        if c == 0x25:                                   # a comment runs to the end of its line
            key = self._line_end(buf, stop, end, True)
        elif c == 0x0A or c == 0x0D:
            key = stop
        else:
            return stop
        if key >= end:
            return end
        memo = self._gap_memo
        found = memo.get(key)
        if found is not None:
            return found
        path, at = [key], key
        room = max(0, MAX_GAP_MEMO - len(memo))
        while True:
            at_next = _SPACE.match(buf, at, end).end()
            self._charge(1 + (at_next - at) // SCAN_BYTES)
            if at_next >= end or buf[at_next] != 0x25:
                found = at_next
                break
            at = self._line_end(buf, at_next, end, False)
            if at >= end:
                found = end
                break
            known = memo.get(at)
            if known is not None:
                found = known
                break
            if len(path) < room:
                path.append(at)
        for key in path[:room]:
            memo[key] = found
        return found

    def _line_end(self, buf, at, end, remember):
        """The first CR or LF at or after `at` (or `end`), charged by the bytes searched. The last few
        comment lines searched from a gap's start are remembered: every position on them shares it."""
        lines = self._gap_lines
        for start, line_end in lines:
            if start <= at <= line_end:
                return line_end
        eol = _EOL.search(buf, at, end)
        line_end = eol.start() if eol is not None else end
        self._charge(1 + (line_end - at) // SCAN_BYTES)
        if remember:
            lines[:] = [(at, line_end)] + [line for line in lines if line[1] != line_end][:3]
        return line_end

    def _ref_after(self, buf, pos, end):
        """(generation, end) when "G R" follows an integer that ended at `pos`, as pdf.js reads it."""
        at = self._gap_end(buf, pos, end)
        if at == pos:
            return None
        if at in self._refs:                # where the gap ends decides the rest
            return self._refs[at]
        result = None
        generation = _UINT.match(buf, at, end)
        if generation is not None:
            after = self._gap_end(buf, generation.end(), end)
            if buf.startswith(b"R", after) and (after + 1 == end or buf[after + 1] in _DELIMITING):
                result = int(generation.group()), after + 1
        if len(self._refs) < MAX_GAP_MEMO:
            self._refs[at] = result
        return result

    def _key_shaped(self, buf, pos, name):
        """Is what follows a name a dictionary, a reference or (for /JS) a string, /XFA an array?"""
        end = len(buf)
        at = self._gap_end(buf, pos, end)
        key = (at, name if name in (b"JS", b"XFA") else b"")
        known = self._shaped.get(key)
        if known is not None:
            return known
        shaped = buf.startswith(b"<<", at) or (name == b"JS" and buf[at:at + 1] in (b"(", b"<")) \
            or (name == b"XFA" and buf[at:at + 1] == b"[")
        if not shaped:
            number = _UINT.match(buf, at, end)
            shaped = (number is not None and (number.end() == end or buf[number.end()] in _DELIMITING)
                      and self._ref_after(buf, number.end(), end) is not None)
        if len(self._shaped) < MAX_GAP_MEMO:
            self._shaped[key] = shaped
        return shaped

    def _skip_array(self, buf, pos, end):
        """To the next delimiter that can matter inside an array: comments are crossed, not stopped at."""
        while True:
            stop = _ARRAY_STOP.search(buf, pos, end)
            if stop is None:
                return end
            at = stop.start()
            if buf[at] != 0x25:
                return at
            eol = _EOL.search(buf, at, end)
            if eol is None:
                return end
            pos = eol.start()
            self.work -= 1
            if self.work < 0:
                raise _Limit("work limit")

    @staticmethod
    def _skip_class(buf, pos, end, stop_class):
        """Across a run of the allowed bytes, ending on a token boundary."""
        stop = stop_class.search(buf, pos, end)
        at = stop.start() if stop is not None else end
        if at < end and buf[at] not in _DELIMITING and buf[at - 1] not in _DELIMITING:
            # The run's last token is glued to a regular character ("12abc"): end the run before it.
            cut = max(buf.rfind(white, pos, at) for white in (b"\x00", b"\t", b"\n", b"\x0c", b"\r", b" "))
            at = cut + 1 if cut >= 0 else pos
        return at

    @staticmethod
    def _append(frame, value):
        if len(frame.items) >= _MAX_ITEMS:
            frame.items = None
        else:
            frame.items.append(value)

    # ---------------------------------------------------------------- hidden anchors
    def _anchors(self):
        """A one-object parse at every "obj" and "trailer" the sequential view did not read as syntax."""
        data = self.data
        end = len(data)
        starts = [r[0] for r in self.regions]
        endobjs = None
        # Every "obj" and "trailer" is a step below, canonical or not ("endobj" included).
        self._charge((data.count(b"obj") + data.count(b"trailer")) // 4)
        for pattern, canonical in ((_OBJ_ANCHOR, self.canonical_obj), (_TRAILER_ANCHOR, self.canonical_trailer)):
            for m in pattern.finditer(data):
                at = m.start()
                if at in canonical or at > 0 and data[at - 1] not in _BEFORE_KEYWORD:
                    continue
                self.stats["hidden_anchors"] += 1
                if self.stats["hidden_anchors"] > MAX_HIDDEN_ANCHORS:
                    raise _Limit("too many hidden objects")
                obj = None
                if pattern is _OBJ_ANCHOR:
                    header = _HEADER_BEFORE.search(data, max(0, at - 32), at)
                    if header is not None:
                        obj = (int(header.group(1)), int(header.group(2)))
                count = len(self.streams)
                summary, stop = self._walk(data, m.end(), end, "one")
                self.anchor_bytes += max(0, stop - m.end())
                if self.anchor_bytes > MAX_ANCHOR_BYTES:
                    raise _Limit("hidden-object budget")
                self._define(obj, summary)
                if obj is not None and len(self.streams) > count and self.streams[-1].obj is None:
                    self.streams[-1].obj = obj
                # Inside stream data the byte-pattern pass ignores short keys; this object's own
                # bytes, to the next "endobj" at least, get that pass after all.
                index = bisect_right(starts, at) - 1
                if index >= 0 and at < self.regions[index][1]:
                    if endobjs is None:
                        self._charge(data.count(b"endobj") // 8)
                        endobjs = [e.start() for e in _ENDOBJ.finditer(data)]
                    following = bisect_right(endobjs, stop)
                    limit = endobjs[following] + 6 if following < len(endobjs) else end
                    self.hidden_ranges.append((at, max(stop, min(limit, self.regions[index][1]))))

    # ---------------------------------------------------------------- byte-pattern pass
    def _patterns(self, buf, regions, ranges):
        """Long names anywhere outside ordinary stream data; key-shaped short names likewise."""
        # Each "/" costs the pattern search 0.14-0.28 us: charged before searching, so a file of
        # slashes is refused as too complex instead of taking seconds.
        self._charge(buf.count(b"/") // 3)
        starts = [r[0] for r in regions]
        merged = []
        for a, b in sorted(ranges):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        hidden_starts = [r[0] for r in merged]

        def ordinary_data(at):
            index = bisect_right(starts, at) - 1
            if index < 0 or at >= regions[index][1]:
                return False
            index = bisect_right(hidden_starts, at) - 1
            return index < 0 or at >= merged[index][1]

        for m in _BACKUP_LONG.finditer(buf):
            if not ordinary_data(m.start()):
                raise Refusal("active", "forbidden name in the raw bytes")
        for m in _BACKUP_SHORT.finditer(buf):
            if ordinary_data(m.start()):
                continue
            name = _unescape(m.group(0))[1:]
            if self._key_shaped(buf, m.end(), name):
                if name == b"Encrypt":
                    raise Refusal("encrypted", "/Encrypt shaped like a key in the raw bytes")
                raise Refusal("active", "forbidden key shaped like a key in the raw bytes")

    # ---------------------------------------------------------------- object streams
    def _resolve(self, value):
        """Every value a reference may denote. ALL definitions count: readers disagree on which wins."""
        if value is None or value[0] != "r":
            return [value]
        self._charge(1)
        found = self._definitions(value[1], value[2])
        if not found or any(item[0] == "r" for item in found):
            # Unresolved, or a reference to a reference: neither pdf.js nor pypdf follows that.
            return None
        return list(found)                      # at most MAX_VARIANTS, already distinct

    def _variants(self, kept):
        """Every filter chain a reader may apply, or None while a reference is unresolved.

        pypdf reads /Filter with /DecodeParms; MuPDF falls back to /F and /DP when those are
        absent; pdf.js PREFERS /F and /DP when present. Each pairing is decoded and checked.
        """
        def first(a, b):
            return kept.get(a) if a in kept else kept.get(b)

        pairs = []
        for pair in ((kept.get(b"Filter"), kept.get(b"DecodeParms")),
                     (first(b"Filter", b"F"), first(b"DecodeParms", b"DP")),
                     (first(b"F", b"Filter"), first(b"DP", b"DecodeParms"))):
            if pair not in pairs:
                pairs.append(pair)
        out, seen = [], set()
        for chain, parm_value in pairs:
            filters = self._resolve(chain)
            parms = self._resolve(parm_value)
            if filters is None or parms is None:
                return None
            for each in filters:
                names = self._name_list(each)
                for parm in parms:
                    # Up to 3 pairings x 8 definitions x 8 x 64 filters: charged per filter, every round.
                    self._charge(1 + len(names))
                    variant = tuple(zip(names, self._parm_list(parm, len(names))))
                    if variant not in seen:
                        seen.add(variant)
                        out.append(variant)
        return out

    def _name_list(self, chain):
        if chain is None or chain[0] != "n" and chain[0] != "a":
            return []           # no filter, or one no reader can apply: the data is read as is
        if chain[0] == "n":
            return [chain[1]]
        if chain[1] is None:
            raise _unreadable("filter list too long")
        names = []
        for item in chain[1]:
            resolved = self._resolve(item)
            if resolved is None or len(resolved) != 1 or resolved[0] is None or resolved[0][0] != "n":
                raise _unreadable("ambiguous or invalid filter name")
            names.append(resolved[0][1])
        return names

    def _parm_list(self, parm, count):
        if parm is not None and parm[0] == "d":
            return [self._parm_ints(parm[1])] + [None] * max(0, count - 1)
        if parm is not None and parm[0] == "a":
            if parm[1] is None:
                raise _unreadable("parameter list too long")
            out = []
            for item in parm[1][:count]:
                resolved = self._resolve(item)
                if resolved is None or len(resolved) != 1:
                    raise _unreadable("ambiguous or invalid /DecodeParms")
                entry = resolved[0]
                out.append(self._parm_ints(entry[1]) if entry is not None and entry[0] == "d" else None)
            return out + [None] * (count - len(out))
        return [None] * count

    def _parm_ints(self, kept):
        if _MALFORMED in kept or _CONFLICT in kept:
            raise _unreadable("a decode parameter dictionary is malformed or defines an entry twice")
        out = []
        for key in (b"BitsPerComponent", b"Colors", b"Columns", b"EarlyChange", b"Predictor"):
            if key in kept:
                value = self._int(kept[key])
                if value is None:
                    raise _unreadable("ambiguous or invalid decode parameter")
                out.append((key, value))
        return tuple(out)       # hashable: a variant is remembered once it has been checked

    def _int(self, value):
        resolved = self._resolve(value)
        if resolved is None or len(resolved) != 1 or resolved[0] is None or resolved[0][0] != "i":
            return None
        return resolved[0][1]

    def _extent(self, stream):
        """The longest data span any reader may use, or None while /Length is unresolved.

        Every decoder here streams: a reader that stops earlier sees a prefix of what is checked.
        """
        stops = [stream.end]
        values = self._resolve(stream.kept.get(b"Length"))
        if values is None:
            return None
        for value in values:
            if value is not None and value[0] == "i":
                stops.append(min(stream.start + value[1], len(stream.buf)))
        return max(stops)

    def _is_object_stream(self, stream, containers):
        bits = stream.bits
        return (stream.kept.get(b"Type") == ("n", b"ObjStm") or bits & _HAS_OBJSTM
                or (bits & _HAS_N and bits & _HAS_FIRST)
                or (stream.obj is not None and stream.obj[1] == 0 and stream.obj[0] in containers))

    def _containers(self):
        """Object numbers any cross-reference stream names as a container, however it is defective."""
        found = set()
        for stream in list(self.streams):
            kind = stream.kept.get(b"Type")
            if not (stream.bits & _HAS_W or kind is not None and kind[0] == "n" and kind[1].lower() == b"xref"):
                continue
            if _CONFLICT in stream.kept:
                continue        # ambiguous: names nothing; /N and /First identify object streams anyway
            widths = stream.kept.get(b"W")
            if widths is None or widths[0] != "a" or widths[1] is None or len(widths[1]) < 3:
                continue
            w = [item[1] if item[0] == "i" else -1 for item in widths[1][:3]]
            if min(w) < 0 or max(w) > 8 or sum(w) == 0 or w[0] == 0:
                continue                # with no type field every row is type 1: no container named
            try:
                variants = self._variants(stream.kept)
                stop = self._extent(stream)
                if not variants or stop is None:
                    continue
                for variant in variants:
                    data = self._decode(stream.buf[stream.start:stop], variant)
                    row = sum(w)
                    self._charge(len(data) // row // 2 + 1)
                    for at in range(0, len(data) - row + 1, row):
                        if (int.from_bytes(data[at:at + w[0]], "big") if w[0] else 1) == 2:
                            found.add(int.from_bytes(data[at + w[0]:at + w[0] + w[1]], "big"))
            except _Limit:
                raise
            except Refusal:
                continue        # names nothing; /N and /First identify object streams anyway
        return found

    def _object_streams(self):
        containers = self._containers()
        for _round in range(MAX_STREAM_NESTING + 8):
            progress = pending = False
            self._charge(1 + len(self.streams) // 8)      # every round looks at every stream
            for stream in list(self.streams):
                if not self._is_object_stream(stream, containers):
                    continue
                self._charge(1)
                if stream.depth >= MAX_STREAM_NESTING:
                    raise _unreadable("object streams nested too deeply")
                if _CONFLICT in stream.kept:
                    raise _unreadable("an object stream dictionary defines an entry twice")
                variants = self._variants(stream.kept)
                stop = self._extent(stream)
                if variants is None or stop is None:
                    pending = True
                    continue
                if len(variants) > MAX_VARIANTS:
                    raise _unreadable("too many ways to decode an object stream")
                if stream.decoded is None:
                    stream.decoded = set()
                for variant in variants:
                    if (stop, variant) in stream.decoded:
                        continue
                    stream.decoded.add((stop, variant))
                    if self.stats["object_streams"] >= MAX_OBJECT_STREAMS:
                        raise _Limit("too many object streams")
                    content = self._decode(stream.buf[stream.start:stop], variant)
                    self._scan_content(content, stream)
                    progress = True
            if not progress:
                if pending:
                    raise _unreadable("object stream parameters cannot be resolved")
                return
        raise _unreadable("object stream parameters keep changing")

    def _scan_content(self, content, stream):
        """A decoded object stream: every token, every object at its header offset, every pattern."""
        self.stats["object_streams"] += 1
        self._patterns(content, (), ())
        depth = stream.depth + 1
        values = {}
        self._walk(content, 0, len(content), "decoded", depth, values)
        n, first = self._int(stream.kept.get(b"N")), self._int(stream.kept.get(b"First"))
        if n is None or first is None or not 0 <= first <= len(content):
            return
        pos = 0
        # ⚠️ ONE READING PER OFFSET, AND THE BYTES CROSSED TO REACH IT ARE COUNTED. 500 entries
        # naming one offset behind 8 MiB of spaces re-crossed them 500 times (12 s, 2 units each).
        read = {}
        for _index in range(min(n, len(content))):
            self._charge(2)
            number = _INT.match(content, pos, first)
            offset = number and _INT.match(content, number.end(), first)
            if not offset:
                break
            pos = offset.end()
            at = first + int(offset.group(1))
            if at >= len(content):
                continue
            if at not in read:
                token = _TOKEN.match(content, at)
                if token is not None and token.start(token.lastindex) in values:
                    # Already read as syntax by the walk above: the same tokens from the same place.
                    summary, stop = values[token.start(token.lastindex)], token.end()
                else:
                    summary, stop = self._walk(content, at, len(content), "one", depth)
                self.anchor_bytes += max(0, stop - at)
                if self.anchor_bytes > MAX_ANCHOR_BYTES:
                    raise _Limit("hidden-object budget")
                read[at] = summary
            self._define((int(number.group(1)), 0), read[at])

    # ---------------------------------------------------------------- decoding
    def _spend(self, size):
        self.decoded += size
        if self.decoded > MAX_DECODED:
            raise _Limit("decoded size limit")
        self._charge(size // 64)

    def _spend_slow(self, size):
        self.slow += size
        self._charge(size // 3 + 1)

    def _charge(self, units):
        self.work -= units
        if self.work < 0:
            raise _Limit("work limit")

    def _decode(self, data, variant):
        for name, parms in variant:
            # ⚠️ EVERY FILTER IS CHARGED FOR ITS INPUT, not only for what it outputs: zlib takes
            # 11 ns a byte through empty fixed-Huffman blocks that output nothing, and streams
            # found at hidden anchors can share one such run of data.
            self._charge(1 + len(data) // 64)
            parms = dict(parms or ())
            if name in (b"FlateDecode", b"Fl"):
                data = self._predict(self._inflate(data), parms)
            elif name in (b"LZWDecode", b"LZW"):
                data = self._predict(self._lzw(data, parms.get(b"EarlyChange", 1)), parms)
            elif name in (b"ASCIIHexDecode", b"AHx"):
                data = self._hex(data)
            elif name in (b"ASCII85Decode", b"A85"):
                data = self._a85(data)
            elif name in (b"RunLengthDecode", b"RL"):
                data = self._runlength(data)
            else:
                # /Crypt, an image codec or an unknown name: what a reader would see cannot be known.
                raise _unreadable("unsupported filter")
        return data

    def _inflate(self, data):
        room = MAX_DECODED - self.decoded
        inflater = zlib.decompressobj()
        try:
            out = inflater.decompress(data, room + 1)
        except zlib.error as exc:
            raise _unreadable("corrupt Flate data") from exc
        if len(out) > room or inflater.unconsumed_tail:
            raise _Limit("decoded size limit")
        self._spend(len(out))
        return out

    def _hex(self, data):
        end = data.find(b">")
        body = (data if end < 0 else data[:end]).translate(None, _WHITESPACE)
        if len(body) % 2:
            body += b"0"
        try:
            out = binascii.unhexlify(body)
        except (binascii.Error, ValueError) as exc:
            raise _unreadable("invalid ASCIIHex data") from exc
        self._spend(len(out))
        return out

    def _a85(self, data):
        self._spend_slow(len(data))
        end = data.find(b"~>")
        body = (data if end < 0 else data[:end]).translate(None, _WHITESPACE)
        if body.startswith(b"<~"):
            body = body[2:]
        try:
            out = base64.a85decode(body)
        except ValueError as exc:
            raise _unreadable("invalid ASCII85 data") from exc
        self._spend(len(out))
        return out

    def _runlength(self, data):
        self._spend_slow(len(data))
        room = MAX_DECODED - self.decoded
        out = bytearray()
        at, size = 0, len(data)
        while at < size:
            code = data[at]
            if code == 128:
                break
            if code < 128:
                out += data[at + 1:at + 2 + code]
                at += code + 2
            else:
                out += data[at + 1:at + 2] * (257 - code)
                at += 2
            if len(out) > room:
                raise _Limit("decoded size limit")
        self._spend(len(out))
        return bytes(out)

    def _lzw(self, data, early):
        self._spend_slow(len(data))
        early = early if early in (0, 1) else 1
        room = MAX_DECODED - self.decoded
        out = bytearray()
        table = [bytes((i,)) for i in range(256)] + [b"", b""]
        width, previous, buffer, bits = 9, None, 0, 0
        for byte in data:
            buffer = ((buffer << 8) | byte) & 0xFFFFFF
            bits += 8
            while bits >= width:
                bits -= width
                code = (buffer >> bits) & ((1 << width) - 1)
                if code == 256:
                    del table[258:]
                    width, previous = 9, None
                    continue
                if code == 257:
                    self._spend(len(out))
                    return bytes(out)
                if code < len(table):
                    entry = table[code]
                elif code == len(table) and previous is not None:
                    entry = previous + previous[:1]
                else:
                    raise _unreadable("invalid LZW code")
                out += entry
                if len(out) > room:
                    raise _Limit("decoded size limit")
                if previous is not None and len(table) < 4096:
                    table.append(previous + entry[:1])
                    if len(table) + early in (512, 1024, 2048):
                        width += 1
                previous = entry
        self._spend(len(out))
        return bytes(out)

    def _predict(self, data, parms):
        predictor = parms.get(b"Predictor", 1)
        if predictor <= 1:
            return data
        colors = parms.get(b"Colors", 1)
        bpc = parms.get(b"BitsPerComponent", 8)
        columns = parms.get(b"Columns", 1)
        if not (1 <= colors <= 32 and bpc in (1, 2, 4, 8, 16) and 1 <= columns <= 1 << 20):
            raise _unreadable("invalid predictor parameters")
        width = (columns * colors * bpc + 7) // 8
        step = max(1, colors * bpc // 8)
        out = bytearray()
        if predictor == 2:
            if bpc != 8:
                raise _unreadable("unsupported TIFF predictor depth")
            self._spend_slow(len(data))
            for at in range(0, len(data), width):
                row = bytearray(data[at:at + width])
                for i in range(step, len(row)):
                    row[i] = (row[i] + row[i - step]) & 255
                out += row
            return bytes(out)
        if predictor < 10:
            raise _unreadable("unsupported predictor")
        # "Up" rows, what cross-reference streams use, are computed as whole-row integers: each
        # byte plus the one above it, modulo 256. Adding only the low seven bits of every byte
        # cannot carry into the next byte; the top bits are XORed in after. The other row types
        # run byte by byte in Python and are charged per byte.
        # ⚠️ NOTHING IS SIZED BY THE DECLARED ROW WIDTH, ONLY BY THE DATA: /Columns 1048576 with 32
        # colours of 16 bits declares 64 MiB rows, and allocating three of them for one byte of
        # data, for one unit, let 30 such streams in a 10 KB file run past 12 s. The row above the
        # first is zeros (no row); a short row can only be the last one; the masks are built for
        # the first full Up row, whose bytes were already charged when they were decoded.
        low = high = prior = None
        at = 0
        while at < len(data):
            self._charge(1)                         # every row, whatever its type
            kind = data[at]
            row = bytearray(data[at + 1:at + 1 + width])
            at += width + 1
            size = len(row)
            if kind == 2 and size == width:
                if prior is not None:               # Up on the first row adds zeros
                    if low is None:
                        low = int.from_bytes(b"\x7f" * width, "big")
                        high = int.from_bytes(b"\x80" * width, "big")
                    a = int.from_bytes(row, "big")
                    b = int.from_bytes(prior, "big")
                    row = bytearray((((a & low) + (b & low)) ^ ((a ^ b) & high)).to_bytes(width, "big"))
            elif kind != 0:
                self._spend_slow(size)
                above = prior if prior is not None else bytes(size)
                if kind == 1:
                    for i in range(step, size):
                        row[i] = (row[i] + row[i - step]) & 255
                elif kind == 2:
                    for i in range(size):
                        row[i] = (row[i] + above[i]) & 255
                elif kind == 3:
                    for i in range(size):
                        row[i] = (row[i] + (((row[i - step] if i >= step else 0) + above[i]) >> 1)) & 255
                elif kind == 4:
                    for i in range(size):
                        left = row[i - step] if i >= step else 0
                        up = above[i]
                        corner = above[i - step] if i >= step else 0
                        guess = left + up - corner
                        pa, pb, pc = abs(guess - left), abs(guess - up), abs(guess - corner)
                        row[i] = (row[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
                else:
                    raise _unreadable("invalid PNG predictor row")
            out += row
            prior = row
        return bytes(out)

    # ---------------------------------------------------------------- entry
    def _unread_streams(self):
        """⚠️ EVERY STREAM SOME READER CAN START MUST BE ONE THIS SCAN READ. pdf.js and PDFium skip any
        token where a key belongs that is not a name, a "[", "<<" or "(" included, and PDFium then
        reads a string's contents as entries; this scan opens the container. Fuzzing found "[" put
        before /Length, and "29 0[ R", hide an object stream's start inside an array that never
        closed here: its data was never decoded, and pdf.js read a link with a URI action from it.

        Every ">>" is followed past whitespace and comments to see whether "stream" comes next.
        ⚠️ IN ONE PASS: a regex search from each ">>" crosses the whole run of comments after it,
        and a stream of 24,000 lines of "%>>" took more than 30 s for 477 units. So each run is
        crossed once. A later ">>" inside that run is inside one of its comments: from there the gap
        either stops on that comment's line, or reaches the line's end and then goes on exactly as
        the run did, so it ends where the run ends.

        ⚠️ AND A RUN THAT ENDS AT A STREAM THIS SCAN READ IS NOT SEARCHED AGAIN (DELTA-1,
        2026-11-01). The ">>" inside its comments are comment text, so every lexer skips them on its
        way to that stream. The first one-pass version tested each of them too, and refused as
        unreadable "<< ... >>\\n% >> stream\\nstream" — a commented ">> stream" just before a stream it
        had read — which the earlier non-overlapping regex search accepted, because a match never
        restarts inside an earlier match. That search's rule is kept exactly: a ">>" inside a run
        that ends at a stream it read is skipped; inside any other run it is still tested, so a
        commented ">> stream" with no read stream after the run is refused as before."""
        data = self.data
        size = len(data)
        starts = self.stream_starts
        run_end = -1
        read_until = -1     # the end of the last run that ended at a stream this scan read
        at = data.find(b">>")
        while at >= 0:
            self._charge(1)
            if at < read_until:
                at = data.find(b">>", at + 1)
                continue
            after = at + 2
            inside = after < run_end
            if inside:
                stop = _INLINE_SPACE.match(data, after).end()
                gap_end = run_end if stop >= size or data[stop] in b"\r\n%" else stop
            else:
                gap_end = run_end = _GAP_RUN.match(data, after).end()
                self._charge((gap_end - after) // SCAN_BYTES)
            if data.startswith(b"stream", gap_end) and (gap_end + 6 == size or data[gap_end + 6] in _DELIMITING):
                if gap_end not in starts:
                    raise _unreadable("a stream whose dictionary could not be read")
                if not inside:
                    read_until = gap_end
            at = data.find(b">>", at + 1)

    def run(self):
        data = self.data
        self._walk(data, 0, len(data), "file")
        self._anchors()
        self._patterns(data, self.regions, self.hidden_ranges)
        self._object_streams()
        self._unread_streams()


def scan(data, stats=None):
    """Raise Refusal unless no reader of these exact bytes can reach active content.

    `stats`, when a dict is given, receives the work counters (tests and measurement only).
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("scan() takes the file's bytes")
    scanner = _Scanner(bytes(data))
    try:
        scanner.run()
    except MemoryError as exc:
        raise _Limit("memory") from exc
    finally:
        if stats is not None:
            stats.update(scanner.stats, work=scanner.budget - scanner.work, budget=scanner.budget,
                         decoded=scanner.decoded,
                         slow=scanner.slow, anchor_bytes=scanner.anchor_bytes, streams=len(scanner.streams),
                         regions=len(scanner.regions))
