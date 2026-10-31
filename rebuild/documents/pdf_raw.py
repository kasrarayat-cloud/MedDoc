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
original may reach it. Whatever it cannot decode completely is refused as unreadable.

The policy is exactly the engine's (the forbidden keys, /Type /EmbeddedFile, the active
annotation subtypes) plus action types named by /S. Three views are combined, so that no one
tokenizer disagreement can hide a key:

1. the sequential tokenization of every byte, skipping only stream data;
2. a one-object parse at EVERY "obj" and "trailer" keyword that view did not read as syntax
   (inside a comment, a string or another stream's data), because a reader that seeks to an
   xref offset, or rebuilds the table by searching, starts reading exactly there;
3. a byte-pattern pass: the long forbidden names anywhere outside ordinary stream data, in
   any spelling (#xx escapes, inside strings and comments), and the short ones wherever they
   are shaped like a key (followed by a dictionary or a reference, /JS also by a string).

Every bound is explicit (MAX_* below) and refuses as unreadable; nothing is truncated quietly.
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
ACTION_TYPES = frozenset((b"JavaScript", b"Launch", b"SubmitForm", b"ImportData", b"RichMediaExecute",
                          b"GoToR", b"GoToE", b"URI"))
#: Searched for in any position outside ordinary stream data, strings and comments included.
LONG_NAMES = (b"JavaScript", b"OpenAction", b"EmbeddedFiles", b"EmbeddedFile", b"Launch",
              b"RichMediaContent", b"SubmitForm", b"ImportData")

MAX_DECODED = 64 * 1024 * 1024        # decoded object-stream and xref-stream bytes, all together
#: ONE budget for everything the scan does in Python, so that no mix of shapes can add up: a
#: token or a skipped run is one unit; an escaped name, a closed dictionary and a stream cost
#: more; 3 bytes through a byte-by-byte decoder (LZW, RunLength, ASCII85, a predictor row other
#: than Up), one Up row, 64 decoded bytes and 3 slashes for the pattern pass are one unit each.
#: The weights are measured (docs/rebuild/security-readiness.md): one unit is 0.6-1.8 us, so
#: the whole scan stays under ~2 s of CPU on any 10 MiB file. The ordinary corpus uses at most
#: about 2,000 units.
MAX_WORK = 1_000_000
MAX_HIDDEN_ANCHORS = 20_000           # "obj"/"trailer" keywords outside the sequential view's syntax
MAX_ANCHOR_BYTES = 32 * 1024 * 1024   # bytes re-read by one-object parses at those anchors
MAX_OBJECT_STREAMS = 2_000            # object-stream decodings
MAX_DEPTH = 256                       # dictionary/array nesting
MAX_STREAM_NESTING = 4                # object streams inside decoded object streams
MAX_DEFINITIONS = 150_000             # object definitions kept (the pypdf walk refuses 100,000 objects)
MAX_VARIANTS = 8                      # decodings of one object stream whose parameters are ambiguous

_WHITESPACE = b"\x00\t\n\x0c\r "
_DELIMITING = frozenset(b"\x00\t\n\x0c\r ()<>[]{}/%")   # bytes that end a regular token
#: What may stand right before an "obj" or "trailer" keyword that some reader still reads as one:
#: pdf.js ends a number at its first non-number character, so "5 0obj" is a header there.
_BEFORE_KEYWORD = _DELIMITING | frozenset(b"0123456789.+-")
_REG = rb"[^\x00\t\n\x0c\r ()<>\[\]{}/%]"            # a PDF "regular" character
# ⚠️ EVERY REPEATED GROUP BELOW IS POSSESSIVE (*+, ++). Python's regex engine otherwise keeps
# backtracking state for each repetition of a group: a 60 MiB run of "1 " took 6.5 s and 5.5 GB.
_GAPS = rb"(?:[\x00\t\n\x0c\r ]+|%[^\r\n]*)*+"         # whitespace and comments, possibly none
_GAPS1 = rb"(?:[\x00\t\n\x0c\r ]+|%[^\r\n]*)++"        # at least one

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
_REF_TAIL = re.compile(_GAPS1 + rb"(\d{1,10})" + _GAPS1 + rb"R(?!" + _REG + rb")")
_STREAM_NEXT = re.compile(_GAPS + rb"stream(?!" + _REG + rb")")
_HEADER_BEFORE = re.compile(rb"(\d{1,10})[\x00\t\n\x0c\r ]+(\d{1,5})[\x00\t\n\x0c\r ]*\Z")
# The keyword first: a leading lookbehind would defeat the literal search (1.45 s on 10 MiB).
# The byte before it is checked by the caller.
_OBJ_ANCHOR = re.compile(rb"obj(?!" + _REG + rb")")
_TRAILER_ANCHOR = re.compile(rb"trailer(?!" + _REG + rb")")
_ENDOBJ = re.compile(rb"endobj")
_INT = re.compile(_GAPS + rb"(\d{1,10})(?!" + _REG + rb")")
# Runs that carry nothing for the policy are skipped with one character-class search each
# (5 ns/byte; a possessive group costs 28): the contents of an array whose items are not needed
# (names in arrays are never keys), integers at top level, and a classic xref table's body.
_ARRAY_STOP = re.compile(rb"[()<>\[\]{}%]")
_INT_STOP = re.compile(rb"[^0-9\x00\t\n\x0c\r ]")
_XREF_STOP = re.compile(rb"[^0-9fn\x00\t\n\x0c\r ]")
_EOL = re.compile(rb"[\r\n]")
_DIGITS = re.compile(rb"\d{1,18}")
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


_KEY_SHAPED = _GAPS + rb"(?:<<|\d{1,10}" + _GAPS1 + rb"\d{1,10}" + _GAPS + rb"R(?!" + _REG + rb"))"
_BACKUP_LONG = re.compile(_names(LONG_NAMES))
_BACKUP_SHORT = re.compile(
    _names((b"A", b"AA", b"EF", b"URI", b"Encrypt")) + rb"(?=" + _KEY_SHAPED + rb")"
    rb"|" + _names((b"JS",)) + rb"(?=" + _KEY_SHAPED + rb"|" + _GAPS + rb"[(<])"
    rb"|" + _names((b"XFA",)) + rb"(?=" + _KEY_SHAPED + rb"|" + _GAPS + rb"\[)")

# What a name means to the policy, looked up once per name token.
_KEY = 1          # forbidden as a dictionary key
_ENCRYPT = 2      # /Encrypt as a key
_EMBEDDED = 4     # /EmbeddedFile, refused as the value of /Type
_ANNOT = 8        # refused as the value of /Subtype
_ACTION = 16      # refused as the value of /S
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


class _Scanner:
    def __init__(self, data):
        self.data = data
        self.work = MAX_WORK
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
        self.stats = {"hidden_anchors": 0, "object_streams": 0}

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
        if known is None:
            self.definitions[key] = summary
        elif isinstance(known, list):
            if summary not in known:
                known.append(summary)
        elif known != summary:
            self.definitions[key] = [known, summary]

    def _definitions(self, number, generation):
        known = self.definitions.get(number << 16 | (generation & 0xFFFF))
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
        while start < end and buf[start] == 0x20:
            start += 1
        if buf.startswith(b"\r\n", start):
            start += 2
        elif start < end and buf[start] in (0x0A, 0x0D):
            start += 1
        length = kept.get(b"Length") if kept else None
        if length is not None and length[0] == "i":
            stop = start + length[1]
            if stop <= end:
                at = stop
                while at < end and buf[at] in _WHITESPACE:
                    at += 1
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
                        frame = _Frame(c == 0x3C, keep, holder, start)
                        stack.append(frame)
                        last_dict = None
                        ints = []
                        if frame.items is None and not frame.is_dict:
                            self.work = work
                            pos = self._skip_array(buf, pos, end)
                            work = self.work
                        continue
                    if c == 0x3E and pos - start == 2:            # >>
                        if not stack:
                            continue
                        if not stack[-1].is_dict:
                            value = _JUNK
                        else:
                            frame = stack.pop()
                            value = self._close_dict(frame)
                            work -= 1
                            start = frame.start
                            if frame.obj is not None:
                                self._define(frame.obj, value)
                    elif c == 0x5D:                              # ]
                        if not stack:
                            continue
                        if stack[-1].is_dict:
                            value = _JUNK
                        else:
                            frame = stack.pop()
                            value = ("a", tuple(frame.items) if frame.items is not None else None)
                            start = frame.start
                            if frame.obj is not None:
                                self._define(frame.obj, value)
                    else:                                        # { } ) or a single >
                        if not stack:
                            last_dict = None
                            ints = []
                            continue
                        value = _JUNK
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
                                frame.bad = True
                            continue
                        if frame.items is not None:
                            self._append(frame, value)
                        continue
                elif k == 3 or k == 4:
                    value = _STR
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
                                    frame.bad = True
                            elif frame.items is not None:
                                self._append(frame, ("i", int(tok)))
                            continue
                        if one or obj_open:
                            ref = _REF_TAIL.match(buf, pos, end)
                            value = ("r", int(tok), int(ref.group(1))) if ref is not None else ("i", int(tok))
                            if ref is not None:
                                pos = ref.end()
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
                    if tok in (b"true", b"false", b"null") or tok[0] in b"+-.0123456789":
                        value = _SCALAR
                    elif stack:
                        frame = stack[-1]
                        if tok == b"R":
                            if frame.is_dict:
                                if frame.state == 3:
                                    self._keep(frame, ("r", frame.n1, frame.n2))
                                    frame.state = 0
                                else:
                                    frame.bad = True
                            elif frame.items is not None:
                                items = frame.items
                                if len(items) >= 2 and items[-1][0] == "i" and items[-2][0] == "i":
                                    generation = items.pop()[1]
                                    items[-1] = ("r", items[-1][1], generation)
                        elif frame.is_dict:
                            frame.bad = True
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
                                self._add_stream(buf, last_dict, data_start, stop, last_obj, depth)
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
                            frame.bad = True                     # a value where a key belongs
                            frame.state = 0
                    elif frame.items is not None:
                        self._append(frame, value)
                    else:
                        self.work = work
                        pos = self._skip_array(buf, pos, end)
                        work = self.work
                    continue
                if one:
                    if value[0] == "d":
                        after = _STREAM_NEXT.match(buf, pos, end)
                        if after is not None:
                            data_start, stop, resume = self._stream_data(buf, after.end(), end, value[1])
                            self.work = work
                            self._add_stream(buf, value, data_start, stop, None, depth)
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
            while stack:
                frame = stack.pop()
                if frame.is_dict:
                    result = self._close_dict(frame)
                    if frame.obj is not None:
                        self._define(frame.obj, result)
                else:
                    result = ("a", None)
            return (result if one else None), pos
        finally:
            self.work = work

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

        def ordinary_data(at):
            index = bisect_right(starts, at) - 1
            return (index >= 0 and at < regions[index][1]
                    and not any(a <= at < b for a, b in ranges))

        for m in _BACKUP_LONG.finditer(buf):
            if not ordinary_data(m.start()):
                raise Refusal("active", "forbidden name in the raw bytes")
        for m in _BACKUP_SHORT.finditer(buf):
            if not ordinary_data(m.start()):
                if _unescape(m.group(0)) == b"/Encrypt":
                    raise Refusal("encrypted", "/Encrypt shaped like a key in the raw bytes")
                raise Refusal("active", "forbidden key shaped like a key in the raw bytes")

    # ---------------------------------------------------------------- object streams
    def _resolve(self, value, seen=()):
        """Every value a reference may denote. ALL definitions count: readers disagree on which wins."""
        if value is None or value[0] != "r":
            return [value]
        key = (value[1], value[2])
        if key in seen or len(seen) > 8:
            raise _unreadable("reference loop in stream parameters")
        found = self._definitions(*key)
        if not found:
            return None
        out = []
        for item in found:
            resolved = self._resolve(item, seen + (key,))
            if resolved is None:
                return None
            out.extend(each for each in resolved if each not in out)
        return out

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
        out = []
        for chain, parm_value in pairs:
            filters = self._resolve(chain)
            parms = self._resolve(parm_value)
            if filters is None or parms is None:
                return None
            for each in filters:
                names = self._name_list(each)
                for parm in parms:
                    variant = tuple(zip(names, self._parm_list(parm, len(names))))
                    if variant not in out:
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
            if min(w) < 0 or max(w) > 8 or sum(w) == 0:
                continue
            try:
                variants = self._variants(stream.kept)
                stop = self._extent(stream)
                if not variants or stop is None:
                    continue
                for variant in variants:
                    data = self._decode(stream.buf[stream.start:stop], variant)
                    row = sum(w)
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
            for stream in list(self.streams):
                if not self._is_object_stream(stream, containers):
                    continue
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
        for _index in range(min(n, len(content))):
            number = _INT.match(content, pos, first)
            offset = number and _INT.match(content, number.end(), first)
            if not offset:
                break
            pos = offset.end()
            at = first + int(offset.group(1))
            token = _TOKEN.match(content, at) if at < len(content) else None
            if token is not None and token.start(token.lastindex) in values:
                # Already read as syntax by the walk above: the same tokens from the same place.
                self._define((int(number.group(1)), 0), values[token.start(token.lastindex)])
            elif at < len(content):
                summary, stop = self._walk(content, at, len(content), "one", depth)
                self.anchor_bytes += max(0, stop - at)
                if self.anchor_bytes > MAX_ANCHOR_BYTES:
                    raise _Limit("hidden-object budget")
                self._define((int(number.group(1)), 0), summary)

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
        low = int.from_bytes(b"\x7f" * width, "big")
        high = int.from_bytes(b"\x80" * width, "big")
        prior = bytearray(width)
        at = 0
        while at < len(data):
            kind = data[at]
            row = bytearray(data[at + 1:at + 1 + width])
            at += width + 1
            size = len(row)
            if kind == 2 and size == width:
                self._charge(1)
                a = int.from_bytes(row, "big")
                b = int.from_bytes(prior, "big")
                row = bytearray((((a & low) + (b & low)) ^ ((a ^ b) & high)).to_bytes(width, "big"))
            elif kind != 0:
                self._spend_slow(size)
                if kind == 1:
                    for i in range(step, size):
                        row[i] = (row[i] + row[i - step]) & 255
                elif kind == 2:
                    for i in range(size):
                        row[i] = (row[i] + prior[i]) & 255
                elif kind == 3:
                    for i in range(size):
                        row[i] = (row[i] + (((row[i - step] if i >= step else 0) + prior[i]) >> 1)) & 255
                elif kind == 4:
                    for i in range(size):
                        left = row[i - step] if i >= step else 0
                        up = prior[i]
                        corner = prior[i - step] if i >= step else 0
                        guess = left + up - corner
                        pa, pb, pc = abs(guess - left), abs(guess - up), abs(guess - corner)
                        row[i] = (row[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
                else:
                    raise _unreadable("invalid PNG predictor row")
            out += row
            prior = row if size == width else row + bytearray(width - size)
        return bytes(out)

    # ---------------------------------------------------------------- entry
    def run(self):
        data = self.data
        self._walk(data, 0, len(data), "file")
        self._anchors()
        self._patterns(data, self.regions, self.hidden_ranges)
        self._object_streams()


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
            stats.update(scanner.stats, work=MAX_WORK - scanner.work, decoded=scanner.decoded,
                         slow=scanner.slow, anchor_bytes=scanner.anchor_bytes, streams=len(scanner.streams),
                         regions=len(scanner.regions))
