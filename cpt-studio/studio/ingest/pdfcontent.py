"""What a PDF page's content streams paint, for extraction (ARCHITECTURE 5.1).

Three questions about a page, answered by walking its content stream and the
form XObjects it draws, with the current transformation matrix tracked:

- **Optional content.** Marked content ``/OC <name> BDC ... EMC``, and form or
  image XObjects carrying ``/OC``, whose groups the document's default
  configuration hides (PDF 32000-1 8.11: ``/D`` with ``/BaseState``, ``/ON``,
  ``/OFF``; ``/AS`` view usage; membership dictionaries with ``/P`` or
  ``/VE``) are not shown, so their text is not current documentation.
  ``extraction_page`` returns a copy of the page whose content omits the
  text-showing operators and XObjects inside hidden content; graphics- and
  text-state operators are kept, as a viewer keeps executing them.
- **Symbol fonts.** A simple symbol font in the resources of the page or of a
  form it draws is replaced, in the copy extraction reads, by one that maps
  its glyphs to the characters they show (studio.ingest.pdffonts).
- **Painted images.** Each visible image placement (image XObjects and inline
  images, inside forms too) as a bounding box clipped to the page, so a scan
  split into bands adds up; and the largest image's pixel count.
- **Integrity.** Every FlateDecode stream the page's text depends on — its
  content streams, the form XObjects it draws and their fonts' ToUnicode and
  encoding CMaps — must decompress completely, checksum included. pypdf
  decodes a truncated stream silently into a shorter one, so a stream that
  does not reach its end marks the page damaged. The images are listed too:
  a page read with OCR is damaged when one of its images is cut short (a
  Flate image that does not decompress completely, a JPEG without its
  end-of-image marker).

Importable without Django (the extraction child imports it).
"""
from __future__ import annotations

import functools
import zlib
from dataclasses import dataclass, field
from itertools import pairwise

from pypdf import PageObject
from pypdf.filters import ASCII85Decode, ASCIIHexDecode
from pypdf.generic import ArrayObject, ContentStream, DictionaryObject, NameObject, StreamObject

from .pdffonts import mapped_simple_font

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
MAX_FORM_DEPTH = 12  # a form nested deeper is assumed to paint an image over its whole bounding box
UNIT_SQUARE = (0.0, 0.0, 1.0, 1.0)  # an image occupies the unit square of its CTM
# An image placed at under 20 pixels per inch (400 per square inch) cannot hold
# readable text: a stretched background colour or watermark tile, not a scan.
MIN_SCAN_PIXELS_PER_SQUARE_INCH = 400
MAX_EXPRESSION_DEPTH = 32
MAX_STRICT_OUTPUT_BYTES = 75_000_000  # pypdf's own zlib output limit
MAX_UNION_RECTANGLES = 400
REPLACEMENT_SUFFIX = '_cpt_visible'

TEXT_SHOWING = frozenset({b'Tj', b'TJ', b"'", b'"'})
FLATE = frozenset({'/FlateDecode', '/Fl'})
ASCII_HEX = frozenset({'/ASCIIHexDecode', '/AHx'})
ASCII_85 = frozenset({'/ASCII85Decode', '/A85'})
DCT = frozenset({'/DCTDecode', '/DCT'})


def resolved(value):
    return value.get_object() if hasattr(value, 'get_object') else value


def as_list(value) -> list:
    value = resolved(value)
    if value is None:
        return []
    return list(value) if isinstance(value, (list, ArrayObject)) else [value]


def object_key(value):
    """A stable identity for an indirect object (its reference), else the Python object's id."""
    target = resolved(value)
    reference = getattr(target, 'indirect_reference', None)
    if reference is not None:
        return reference.idnum, reference.generation
    return id(target)


def number(value, default: float = 0.0) -> float:
    try:
        return float(resolved(value))
    except (TypeError, ValueError):
        return default


def raw_entry(dictionary, key):
    """``dictionary[key]`` without resolving it (an IndirectObject stays one), or None."""
    return dictionary.raw_get(key) if isinstance(dictionary, DictionaryObject) and key in dictionary else None


# --- optional content ---------------------------------------------------------------

class OptionalContent:
    """Which optional content the document's default configuration shows."""

    def __init__(self, root):
        self.hidden: set = set()
        properties = resolved(root.get('/OCProperties')) if isinstance(root, dict) else None
        self.active = isinstance(properties, dict)
        if not self.active:
            return
        config = resolved(properties.get('/D'))
        config = config if isinstance(config, dict) else {}
        groups = {object_key(group) for group in as_list(properties.get('/OCGs'))}
        on = {object_key(group) for group in as_list(config.get('/ON'))}
        off = {object_key(group) for group in as_list(config.get('/OFF'))}
        hidden = groups - on if resolved(config.get('/BaseState')) == '/OFF' else set()
        self.hidden = hidden | off  # a group listed both ON and OFF ends OFF
        for application in as_list(config.get('/AS')):
            self._apply_view_usage(resolved(application))

    def _apply_view_usage(self, application) -> None:
        """An /AS entry for the View event sets its groups from their /Usage /View /ViewState."""
        if not isinstance(application, dict) or resolved(application.get('/Event')) != '/View':
            return
        if '/View' not in [resolved(item) for item in as_list(application.get('/Category'))]:
            return
        for group in as_list(application.get('/OCGs')):
            target = resolved(group)
            usage = resolved(target.get('/Usage')) if isinstance(target, dict) else None
            view = resolved(usage.get('/View')) if isinstance(usage, dict) else None
            state = resolved(view.get('/ViewState')) if isinstance(view, dict) else None
            if state == '/OFF':
                self.hidden.add(object_key(group))
            elif state == '/ON':
                self.hidden.discard(object_key(group))

    def visible(self, entry, depth: int = 0) -> bool:
        """Whether content marked with ``entry`` (an OCG or OCMD, or a reference to one) is shown.

        Without /OCProperties optional content is ignored and everything is
        shown; an entry that resolves to neither a group nor a membership
        dictionary is shown, as viewers show it.
        """
        if not self.active or entry is None or depth > MAX_EXPRESSION_DEPTH:
            return True
        target = resolved(entry)
        if not isinstance(target, dict):
            return True
        if resolved(target.get('/Type')) != '/OCMD':
            return object_key(entry) not in self.hidden
        if target.get('/VE') is not None:
            return self._expression(target.get('/VE'), depth + 1)
        states = [object_key(group) not in self.hidden for group in as_list(target.get('/OCGs'))
                  if isinstance(resolved(group), dict)]
        if not states:
            return True
        policy = resolved(target.get('/P'))
        if policy == '/AllOn':
            return all(states)
        if policy == '/AnyOff':
            return not all(states)
        if policy == '/AllOff':
            return not any(states)
        return any(states)  # /AnyOn, the default

    def _expression(self, expression, depth: int) -> bool:
        if depth > MAX_EXPRESSION_DEPTH:
            return True
        target = resolved(expression)
        if isinstance(target, dict):
            return object_key(expression) not in self.hidden
        items = list(target) if isinstance(target, (list, ArrayObject)) else []
        if not items:
            return True
        operator = resolved(items[0])
        values = [self._expression(operand, depth + 1) for operand in items[1:]]
        if operator == '/Not':
            return not values[0] if values else True
        if operator == '/And':
            return all(values)
        if operator == '/Or':
            return any(values) if values else True
        return True


# --- geometry -----------------------------------------------------------------------

def multiply(m, n):
    """m x n for PDF matrices [a b c d e f]."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2, c * a2 + d * c2, c * b2 + d * d2,
            e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


def transformed_box(box, ctm) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    a, b, c, d, e, f = ctm
    points = [(x * a + y * c + e, x * b + y * d + f) for x in (x0, x1) for y in (y0, y1)]
    return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))


def page_box(page) -> tuple[float, float, float, float]:
    """The visible page area: the crop box within the media box, in default user space."""
    try:
        media = [float(v) for v in page.mediabox]
        crop = [float(v) for v in page.cropbox]
    except Exception:  # an unreadable box: assume US letter
        return 0.0, 0.0, 612.0, 792.0
    mx0, mx1 = sorted((media[0], media[2]))
    my0, my1 = sorted((media[1], media[3]))
    cx0, cx1 = sorted((crop[0], crop[2]))
    cy0, cy1 = sorted((crop[1], crop[3]))
    box = (max(mx0, cx0), max(my0, cy0), min(mx1, cx1), min(my1, cy1))
    return box if box[2] > box[0] and box[3] > box[1] else (mx0, my0, mx1, my1)


def clip(rect, box):
    x0, y0, x1, y1 = max(rect[0], box[0]), max(rect[1], box[1]), min(rect[2], box[2]), min(rect[3], box[3])
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def area(box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def union_area(rects) -> float:
    """Area of the union of axis-aligned rectangles (summed, an over-estimate, past MAX_UNION_RECTANGLES)."""
    if len(rects) > MAX_UNION_RECTANGLES:
        return sum(area(rect) for rect in rects)
    xs = sorted({x for rect in rects for x in (rect[0], rect[2])})
    total = 0.0
    for left, right in pairwise(xs):
        spans = sorted((rect[1], rect[3]) for rect in rects if rect[0] <= left and rect[2] >= right)
        covered, start, end = 0.0, None, None
        for low, high in spans:
            if start is not None and low <= end:
                end = max(end, high)
                continue
            if start is not None:
                covered += end - start
            start, end = low, high
        if start is not None:
            covered += end - start
        total += covered * (right - left)
    return total


# --- walking a page -----------------------------------------------------------------

@dataclass
class PageContent:
    operations: list | None = None  # the page's operations, hidden content dropped; None if unparseable
    resources: DictionaryObject | None = None  # resources naming the filtered forms, when there are any
    hidden_text: bool = False  # hidden optional content showed text, which was dropped
    placements: list = field(default_factory=list)  # (CTM, pixels or None) of each visible image, page space
    images: list = field(default_factory=list)  # the visible image XObjects, each once
    damaged: bool = False
    box: tuple = (0.0, 0.0, 612.0, 792.0)

    @property
    def largest_image_pixels(self) -> int:
        return max((pixels for _, pixels in self.placements if pixels is not None), default=0)

    @functools.cached_property
    def image_coverage(self) -> float:
        """The share of the page that images dense enough to hold text cover (their union, clipped)."""
        rects = []
        for ctm, pixels in self.placements:
            square_inches = abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]) / (72 * 72)  # the unit square, placed
            sparse = pixels is not None and pixels < MIN_SCAN_PIXELS_PER_SQUARE_INCH * square_inches
            if square_inches <= 0 or sparse:
                continue
            rect = clip(transformed_box(UNIT_SQUARE, ctm), self.box)
            if rect:
                rects.append(rect)
        page_area = area(self.box)
        return min(1.0, union_area(rects) / page_area) if page_area > 0 else 0.0


@dataclass
class _Form:
    replacement: ContentStream | None  # a copy without its hidden content, when it had any
    placements: list  # (CTM in the form's own space, pixels or None) of the images it paints


class _Walker:
    def __init__(self, reader, optional: OptionalContent, box):
        self.reader = reader
        self.optional = optional
        self.content = PageContent(box=box)
        self.forms: dict[tuple, _Form] = {}  # each form is walked once; its images are re-placed per use
        self.active: set[int] = set()  # forms being walked: a form that draws itself is not walked again
        self.checked: set[int] = set()
        self.font_copies: dict[int, DictionaryObject | None] = {}  # id(font) -> its glyph-mapped copy, or None

    def page(self, page) -> PageContent:
        resources = resolved(page.get('/Resources'))
        resources = resources if isinstance(resources, DictionaryObject) else DictionaryObject()
        for stream in as_list(page.get('/Contents')):
            self.check_stream(resolved(stream))
        try:
            # 'bytes' keeps string operands as stored, as pypdf's own extractor parses them.
            contents = resolved(page.get('/Contents'))
            operations = list(ContentStream(contents, self.reader, 'bytes').operations) if contents is not None else []
        except (MemoryError, RecursionError):
            raise
        except Exception:  # an unparseable content stream: the page has no readable text layer
            self.content.damaged = True
            return self.content
        self.check_fonts(resources)
        kept, replaced, _ = self.walk(operations, resources, IDENTITY, 0, self.content.placements)
        self.content.operations = kept
        fonts = self.mapped_fonts(resources)
        if replaced or fonts:
            self.content.resources = with_replacements(resources, replaced, fonts)
        return self.content

    def walk(self, operations, resources, ctm, depth: int, placements: list) -> tuple[list, dict, bool]:
        """(kept operations, {XObject name: filtered form}, changed) for one content stream; the images it
        paints are added to ``placements``."""
        kept: list = []
        replaced: dict = {}
        changed = False
        saved: list = []
        marked: list[bool] = []  # per open BMC/BDC: whether it hides what it encloses
        properties = resolved(resources.get('/Properties'))
        xobjects = resolved(resources.get('/XObject'))
        for operands, operator in operations:
            hidden = any(marked)
            if operator in (b'BMC', b'BDC'):
                marked.append(operator == b'BDC' and not self.marked_visible(operands, properties))
                if hidden or marked[-1]:
                    changed = True
                    continue
            elif operator == b'EMC':
                closing = marked.pop() if marked else False
                if hidden or closing:
                    continue
            elif operator == b'q':
                saved.append(ctm)
            elif operator == b'Q':
                ctm = saved.pop() if saved else ctm
            elif operator == b'cm' and len(operands) == 6:
                ctm = multiply(tuple(number(v) for v in operands), ctm)
            elif operator in TEXT_SHOWING and hidden:
                changed = True
                self.content.hidden_text = self.content.hidden_text or shows_text(operands)
                kept.extend(state_only(operator, operands))
                continue
            elif operator == b'INLINE IMAGE':
                if hidden:
                    changed = True
                    continue
                settings = operands.get('settings', {}) if isinstance(operands, dict) else {}
                placements.append((ctm, pixel_count(settings.get('/W', settings.get('/Width')),
                                                    settings.get('/H', settings.get('/Height')))))
            elif operator == b'Do' and operands:
                action, replacement = self.draw(operands[0], xobjects, resources, ctm, depth, hidden, placements)
                if action == 'drop':
                    changed = True
                    continue
                if action == 'replace':
                    changed = True
                    replaced[operands[0]] = replacement
                    kept.append(([NameObject(operands[0] + REPLACEMENT_SUFFIX)], b'Do'))
                    continue
            kept.append((operands, operator))
        return kept, replaced, changed

    def marked_visible(self, operands, properties) -> bool:
        if len(operands) < 2 or resolved(operands[0]) != '/OC':
            return True
        entry = operands[1]
        if isinstance(entry, NameObject):
            entry = raw_entry(properties, entry)
        return self.optional.visible(entry)

    def draw(self, name, xobjects, resources, ctm, depth, hidden, placements):
        """('keep' | 'drop' | 'replace', replacement form) for one ``Do``."""
        xobject = resolved(raw_entry(xobjects, name))
        if not isinstance(xobject, StreamObject):
            return 'keep', None
        subtype = resolved(xobject.get('/Subtype'))
        if hidden or not self.optional.visible(raw_entry(xobject, '/OC')):
            if subtype == '/Form':
                self.content.hidden_text = self.content.hidden_text or self.form_shows_text(xobject)
            return 'drop', None
        if subtype == '/Image':
            placements.append((ctm, pixel_count(xobject.get('/Width'), xobject.get('/Height'))))
            if all(image is not xobject for image in self.content.images):
                self.content.images.append(xobject)
            return 'keep', None
        if subtype != '/Form':
            return 'keep', None
        matrix = [number(v) for v in as_list(xobject.get('/Matrix'))]
        form_ctm = multiply(tuple(matrix), ctm) if len(matrix) == 6 else ctm
        if depth >= MAX_FORM_DEPTH or id(xobject) in self.active:
            bbox = [number(v) for v in as_list(xobject.get('/BBox'))]
            if len(bbox) == 4:  # not looked into: assume it paints a dense image over its whole box
                x0, x1 = sorted((bbox[0], bbox[2]))
                y0, y1 = sorted((bbox[1], bbox[3]))
                placements.append((multiply((x1 - x0, 0.0, 0.0, y1 - y0, x0, y0), form_ctm), None))
            return 'keep', None
        form = self.form(xobject, resources, depth + 1)
        placements.extend((multiply(local, form_ctm), pixels) for local, pixels in form.placements)
        return ('replace', form.replacement) if form.replacement is not None else ('keep', None)

    def form(self, xobject, parent_resources, depth) -> _Form:
        """Walk a form XObject once (in its own space); later uses re-place what it paints."""
        own = resolved(xobject.get('/Resources'))
        resources = own if isinstance(own, DictionaryObject) else parent_resources
        key = (id(xobject), id(resources))
        if key in self.forms:
            return self.forms[key]
        self.check_stream(xobject)
        self.check_fonts(resources)
        try:
            operations = list(ContentStream(xobject, self.reader, 'bytes').operations)
        except (MemoryError, RecursionError):
            raise
        except Exception:
            self.content.damaged = True
            operations = []
        placements: list = []
        self.active.add(id(xobject))
        try:
            kept, replaced, changed = self.walk(operations, resources, IDENTITY, depth, placements)
        finally:
            self.active.discard(id(xobject))
        replacement = None
        fonts = self.mapped_fonts(resources)
        if changed or fonts:
            replacement = ContentStream(None, self.reader)
            for name in xobject:
                if name not in ('/Filter', '/DecodeParms', '/Length', '/Resources'):
                    replacement[NameObject(name)] = xobject.raw_get(name)
            replacement[NameObject('/Resources')] = with_replacements(resources, replaced, fonts)
            replacement.operations = kept
        self.forms[key] = _Form(replacement, placements)
        return self.forms[key]

    def form_shows_text(self, xobject) -> bool:
        """Whether a hidden form shows any text: only to name the exclusion in a message."""
        try:
            return any(operator in TEXT_SHOWING and shows_text(operands)
                       for operands, operator in ContentStream(xobject, self.reader, 'bytes').operations)
        except Exception:  # an unreadable form that is hidden anyway
            return False

    def check_stream(self, stream) -> None:
        if isinstance(stream, StreamObject) and id(stream) not in self.checked:
            self.checked.add(id(stream))
            if stream_damaged(stream):
                self.content.damaged = True

    def check_fonts(self, resources) -> None:
        fonts = resolved(resources.get('/Font'))
        if not isinstance(fonts, DictionaryObject):
            return
        for key in list(fonts):
            font = resolved(fonts.raw_get(key))
            if isinstance(font, DictionaryObject):
                for entry in ('/ToUnicode', '/Encoding'):
                    self.check_stream(resolved(font.get(entry)))

    def mapped_fonts(self, resources) -> dict:
        """{font name: its glyph-mapped copy} for the simple symbol fonts ``resources`` names."""
        fonts = resolved(resources.get('/Font'))
        if not isinstance(fonts, DictionaryObject):
            return {}
        mapped = {}
        for key in list(fonts):
            font = resolved(fonts.raw_get(key))
            if not isinstance(font, DictionaryObject):
                continue
            if id(font) not in self.font_copies:
                self.font_copies[id(font)] = mapped_simple_font(font)
            if self.font_copies[id(font)] is not None:
                mapped[key] = self.font_copies[id(font)]
        return mapped


def pixel_count(width, height) -> int:
    return max(0, int(number(width))) * max(0, int(number(height)))


def with_replacements(resources, replaced: dict, fonts: dict | None = None) -> DictionaryObject:
    """A copy of ``resources`` whose XObject table also names each filtered form, and whose font table
    names each glyph-mapped symbol font in place of the original."""
    copy = DictionaryObject({NameObject(key): resources.raw_get(key) for key in resources})
    table = resolved(resources.get('/XObject'))
    entries = DictionaryObject({NameObject(key): table.raw_get(key) for key in table}) \
        if isinstance(table, DictionaryObject) else DictionaryObject()
    for name, form in replaced.items():
        entries[NameObject(name + REPLACEMENT_SUFFIX)] = form
    copy[NameObject('/XObject')] = entries
    if fonts:
        font_table = resolved(resources.get('/Font'))
        names = DictionaryObject({NameObject(key): font_table.raw_get(key) for key in font_table})
        for name, font in fonts.items():
            names[NameObject(name)] = font
        copy[NameObject('/Font')] = names
    return copy


def shows_text(operands) -> bool:
    """Whether a text-showing operator's operands hold any non-blank string."""
    for operand in operands:
        items = operand if isinstance(operand, (list, ArrayObject)) else [operand]
        for item in items:
            if isinstance(item, (str, bytes)) and not isinstance(item, NameObject):
                text = item.decode('latin-1') if isinstance(item, bytes) else item
                if text.strip():
                    return True
    return False


def state_only(operator, operands) -> list:
    """The text-state effect of a hidden text-showing operator, without the showing."""
    if operator == b"'":
        return [([], b'T*')]
    if operator == b'"' and len(operands) >= 2:
        return [([operands[0]], b'Tw'), ([operands[1]], b'Tc'), ([], b'T*')]
    return []


def visible_form(xobject, reader, optional: OptionalContent, resources) -> tuple[StreamObject, bool, bool]:
    """(the form to read — a copy without its hidden optional content when it has any, damaged,
    hidden text dropped) for a form XObject read on its own, such as an annotation appearance."""
    walker = _Walker(reader, optional, (0.0, 0.0, 0.0, 0.0))
    form = walker.form(xobject, resources if isinstance(resources, DictionaryObject) else DictionaryObject(), 0)
    target = form.replacement if form.replacement is not None else xobject
    return target, walker.content.damaged, walker.content.hidden_text


def analyse_page(page, reader, optional: OptionalContent) -> PageContent:
    """Walk ``page``: visible images, hidden optional content and damaged streams."""
    return _Walker(reader, optional, page_box(page)).page(page)


def extraction_page(page, content: PageContent) -> PageObject:
    """A copy of ``page`` holding the operations already parsed (hidden content dropped).

    pypdf extracts text from a ContentStream it is given without parsing it
    again; forms that held hidden content are reached under their new names.
    """
    copy = PageObject(page.pdf)
    for key in page:
        copy[NameObject(key)] = page.raw_get(key)
    stream = ContentStream(None, page.pdf)
    stream.operations = content.operations or []
    copy[NameObject('/Contents')] = stream
    if content.resources is not None:
        copy[NameObject('/Resources')] = content.resources
    return copy


# --- integrity ----------------------------------------------------------------------

def stream_damaged(stream) -> bool:
    """Whether ``stream`` fails a strict decode: an incomplete or corrupt Flate stream, an ASCII
    filter without its end marker, or a JPEG that does not reach its end-of-image marker. Filters
    this cannot check strictly (LZW, RunLength, CCITT, JBIG2, JPEG 2000) are left to pypdf, whose
    decoding warnings are watched separately."""
    try:
        filters = [resolved(item) for item in as_list(stream.get('/Filter'))]
        data = stream._data  # the stored bytes: decrypted, still encoded
    except Exception:
        return True
    if not filters or not isinstance(data, bytes) or not data.strip(b'\x00\t\n\x0c\r '):
        return False  # unfiltered, or empty: nothing a decoder could lose
    for name in filters:
        if name in FLATE:
            complete, data = inflate_strict(data)
            if not complete:
                return True
        elif name in DCT:
            return not jpeg_complete(data)
        elif name in ASCII_HEX or name in ASCII_85:
            if (b'>' if name in ASCII_HEX else b'~>') not in data:
                return True
            try:
                data = (ASCIIHexDecode if name in ASCII_HEX else ASCII85Decode).decode(data)
            except Exception:
                return True
        else:
            return False
    return False


def jpeg_complete(data: bytes) -> bool:
    """Whether a JPEG reaches its end-of-image marker: segments are walked by their lengths (so an
    EXIF thumbnail's own EOI is skipped) and entropy-coded data is scanned for the next marker
    (0xFF followed by a stuffed 0x00, a restart marker or fill is still data). Bytes after EOI are
    allowed, as some cameras append them."""
    if not data.startswith(b'\xff\xd8'):
        return False
    position, size = 2, len(data)
    while position < size:
        if data[position] != 0xFF:
            return False
        while position < size and data[position] == 0xFF:  # fill bytes before a marker
            position += 1
        if position >= size:
            return False
        marker = data[position]
        position += 1
        if marker == 0xD9:  # EOI
            return True
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # markers without a length
            continue
        if position + 2 > size:
            return False
        length = int.from_bytes(data[position:position + 2], 'big')
        if length < 2 or position + length > size:
            return False
        position += length
        if marker == 0xDA:  # start of scan: entropy-coded data runs to the next real marker
            while True:
                position = data.find(b'\xff', position)
                if position < 0 or position + 1 >= size:
                    return False
                following = data[position + 1]
                if following == 0x00 or 0xD0 <= following <= 0xD7:
                    position += 2
                elif following == 0xFF:
                    position += 1
                else:
                    break
    return False


def inflate_strict(data: bytes) -> tuple[bool, bytes]:
    """(complete, output): complete only when the zlib stream ends and its checksum matches."""
    decompressor = zlib.decompressobj()
    try:
        output = decompressor.decompress(data, MAX_STRICT_OUTPUT_BYTES)
    except zlib.error:
        return False, b''
    if decompressor.unconsumed_tail:  # past the output limit: completeness cannot be shown
        return False, b''
    return decompressor.eof, output
