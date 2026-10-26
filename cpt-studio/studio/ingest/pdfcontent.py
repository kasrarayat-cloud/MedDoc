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
- **Text a viewer does not show.** Text is judged where it lands on the
  page, at every depth: each form XObject is walked once per placement, in
  page space. Text drawn wholly outside the visible page area (the crop box
  within the media box) or wholly outside what its clipping region shows (the
  boxes of the forms drawing it, and its clipping paths: rectangles exactly,
  other paths as polygons with curves flattened) is not shown by any viewer:
  its text-showing operators are dropped, keeping their state effects, and
  the page is flagged (offpage_text, clipped_text). Positions follow the text
  and line matrices and the text state (PDF 32000-1 9.3-9.4), with glyph
  widths from the font; a form XObject whose bounding box lies wholly outside
  the page is dropped. Where whether text shows cannot be decided exactly it
  is kept and the page is flagged (obscured_text): text painted in white with
  nothing painted under it, text a later opaque fill or image covers (over
  the band every glyph inks, for at least a glyph's width), text inside a
  clipping path too complex to follow, and pages past the work limits.
  Invisible text (render mode 3 or 7, or no opacity) is read as the layer of
  what the page paints under it (OCR text over its scan) and named when
  nothing is; zero-size text is named. Text a thin line crosses through the
  middle of its glyphs is struck through: kept and flagged (struck_text),
  whether the line is drawn after it or, ending within an em of it, before.
- **Symbol fonts.** A simple symbol font in the resources of the page or of a
  form it draws is replaced, in the copy extraction reads, by one that maps
  its glyphs to the characters they show (studio.ingest.pdffonts).
- **Painted images.** Each visible image placement (image XObjects and inline
  images, inside forms too) as a bounding box clipped to the page, so a scan
  split into bands adds up; and the largest image's pixel count. The images
  a displayed annotation's appearance paints are added by pdfannots, placed
  as viewers place the appearance.
- **Integrity.** Every stream the page's text depends on — its content
  streams, the form XObjects it draws and their fonts' ToUnicode and encoding
  CMaps — must decode to the end its filters declare (Flate with its
  checksum, LZW to its end-of-data code, RunLength to its end-of-data byte,
  the ASCII filters to their end markers). pypdf decodes a truncated stream
  silently into a shorter one, so a stream that does not reach its end marks
  the page damaged. The images are listed too: a page read with OCR is
  damaged when one of its images is cut short (Flate followed to its end
  whatever its size, a JPEG or JPEG 2000 image without its end marker, JBIG2
  segments that run past the data, Group 4 fax data without its
  end-of-block pattern, Group 3 fax data with fewer EOL codes than rows),
  and unverified when its encoding cannot be checked (a filter this cannot
  check, fax data declared without an end-of-block pattern, a JBIG2 segment
  of unknown length, an image that inflates far past its declared size).

Importable without Django (the extraction child imports it).
"""
from __future__ import annotations

import bisect
import dataclasses
import functools
import math
import re
import zlib
from dataclasses import dataclass, field
from itertools import pairwise

from pypdf import PageObject, get_configuration
from pypdf.filters import ASCII85Decode, ASCIIHexDecode
from pypdf._text_extraction import get_text_operands
from pypdf.generic import ArrayObject, ContentStream, DictionaryObject, NameObject, StreamObject
from pypdf.generic._font import Font

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
TEXT_STATE = frozenset({b'BT', b'Tf', b'Tc', b'Tw', b'Tz', b'TL', b'Ts', b'Td', b'TD', b'Tm', b'T*'})
ORIENTATIONS = (0, 90, 180, 270)
# A generous box around a run of glyphs, in font sizes: the descent, the ascent, and the margin by which the
# whole run must clear the page box before it counts as outside it.
GLYPH_DESCENT, GLYPH_ASCENT, OUTSIDE_MARGIN = 0.3, 1.0, 1.0
UNKNOWN_GLYPH_WIDTH = 1000  # glyph-space units, for text in a font that cannot be read: one em per glyph
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
    if b == 0 and c == 0:  # no rotation or skew: the same values, computed directly
        xa, xb, ya, yb = x0 * a + e, x1 * a + e, y0 * d + f, y1 * d + f
        return min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)
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


# --- what a page paints: clipping, colour and opacity ------------------------------------

# A colour is white when every DeviceGray / RGB component is at least this (every CMYK component at most 1 - it).
WHITE_LEVEL = 0.99
# The band of a line of glyphs that every letter and digit inks: from CORE_LOW to CORE_HIGH font sizes above the
# baseline. An opaque paint that covers that band over COVER_WIDTH font sizes along the baseline hides a glyph.
CORE_LOW, CORE_HIGH, COVER_WIDTH = 0.1, 0.6, 0.6
# Text painted with less opacity than this shows nothing, like invisible text (render mode 3).
MIN_ALPHA = 0.05
# A line painted over text strikes it through when it is no thicker than STRIKE_THICKNESS font sizes, meets the
# band STRIKE_LOW to STRIKE_HIGH font sizes above the baseline (fonts put their strikeout at about 0.25; underlines
# lie below the baseline, overlines near the cap height), and runs along STRIKE_SPAN font sizes (or the whole run).
STRIKE_LOW, STRIKE_HIGH, STRIKE_THICKNESS, STRIKE_SPAN = 0.15, 0.5, 0.35, 1.2
# A line drawn before the text strikes it only when it ends within STRIKE_REACH font sizes of the run (a ruled or
# grid line running past the text is not a strike-through; some producers draw their strike line first).
STRIKE_REACH = 1.0
CURVE_STEPS = 8  # straight pieces per Bézier curve of a clipping path
MAX_PATH_POINTS = 512  # a clipping path with more points is not followed: text inside its bounds is named
GRID_CELLS = 32  # cells per side of the page-space index of what has been painted
MAX_GRID_SPAN = 256  # an item spanning more cells is kept apart and examined by every query
MAX_PAINT_CHECKS = 250_000  # index entries examined per page; past it, what shows is not decided: the page is named
MAX_SHAPE_CHECKS = 1_000_000  # clipping-path edges tested per page; past it, paths are not followed: text is named
MAX_FORM_WALKS = 5_000  # form placements walked per page when pypdf's own limit cannot be read (form_walk_limit)
NORMAL_BLENDS = frozenset({'/Normal', '/Compatible'})
PATH_OPERATORS = frozenset({b'm', b'l', b'c', b'v', b'y', b'h', b're'})
FILLS = frozenset({b'f', b'F', b'f*', b'B', b'B*', b'b', b'b*'})
STROKES = frozenset({b'S', b's', b'B', b'B*', b'b', b'b*'})
PAINTING = FILLS | STROKES | {b'n'}
COLOUR_OPERATORS = frozenset({b'g', b'G', b'rg', b'RG', b'k', b'K', b'cs', b'CS', b'sc', b'scn', b'SC', b'SCN'})
WHITE, COLOUR, UNKNOWN = 'white', 'colour', 'unknown'  # what a paint's colour is known to be
COLOUR_SPACES = {'/DeviceGray': 1, '/G': 1, '/CalGray': 1, '/DeviceRGB': 3, '/RGB': 3, '/CalRGB': 3,
                 '/DeviceCMYK': 4, '/CMYK': 4}


def form_walk_limit() -> int:
    """How many form XObjects pypdf enters per page while extracting text (its configuration): it reads none past
    them, so none past them is walked."""
    try:
        return int(get_configuration().xform_maximum_invocations_per_extraction)
    except Exception:
        return MAX_FORM_WALKS


def colour_class(components, count) -> str:
    """WHITE, COLOUR or UNKNOWN for colour components in a space of ``count`` components (None: unknown)."""
    try:
        values = [float(resolved(value)) for value in components]
    except (TypeError, ValueError):
        return UNKNOWN
    if count is None or len(values) != count:
        return UNKNOWN
    if count == 4:
        return WHITE if all(value <= 1 - WHITE_LEVEL for value in values) else COLOUR
    return WHITE if all(value >= WHITE_LEVEL for value in values) else COLOUR


def rectilinear(m) -> bool:
    """Whether matrix ``m`` maps axis-aligned rectangles to axis-aligned rectangles."""
    a, b, c, d = m[:4]
    return (abs(b) < 1e-9 and abs(c) < 1e-9) or (abs(a) < 1e-9 and abs(d) < 1e-9)


def _inverse(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    return (d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det)


def _apply(m, x, y) -> tuple[float, float]:
    return x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5]


def _segment_meets(rect, p, q) -> bool:
    """Whether the segment p-q meets the closed rectangle ``rect`` (Liang-Barsky)."""
    x0, y0, x1, y1 = rect
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for edge_p, edge_q in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if edge_p == 0:
            if edge_q < 0:
                return False
            continue
        t = edge_q / edge_p
        if edge_p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def _inside(point, rings, even_odd: bool) -> bool:
    """Whether ``point`` lies inside the closed polygon ``rings`` under the non-zero or even-odd rule."""
    x, y = point
    winding = 0
    for ring in rings:
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            if ay <= y < by and (bx - ax) * (y - ay) - (x - ax) * (by - ay) > 0:
                winding += 1
            elif by <= y < ay and (bx - ax) * (y - ay) - (x - ax) * (by - ay) < 0:
                winding -= 1
    return winding % 2 == 1 if even_odd else winding != 0


def _apart(rect, rings, even_odd: bool) -> bool:
    """Whether the rectangle ``rect`` and the polygon ``rings`` have no point in common."""
    for ring in rings:
        for p, q in zip(ring, ring[1:] + ring[:1]):
            if _segment_meets(rect, p, q):
                return False
    centre = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
    return not _inside(centre, rings, even_odd)


@dataclass(frozen=True)
class _Clip:
    """The area content is clipped to, in page space: a rectangle (the page box, the boxes of the forms being
    drawn and rectangular clipping paths, intersected), polygons for the other clipping paths, and whether a path
    was too complex to follow."""
    rect: tuple
    shapes: tuple = ()  # ((rings, even_odd), ...)
    unknown: bool = False

    def narrowed(self, rect, shape=None, unknown: bool = False) -> '_Clip':
        x0, y0, x1, y1 = max(self.rect[0], rect[0]), max(self.rect[1], rect[1]), \
            min(self.rect[2], rect[2]), min(self.rect[3], rect[3])
        return _Clip((x0, y0, max(x0, x1), max(y0, y1)), self.shapes + ((shape,) if shape else ()),
                     self.unknown or unknown)


class _Path:
    """The current path, in page space: rings of points (curves flattened), at most MAX_PATH_POINTS of them
    kept, and the exact bounds of every point."""

    def __init__(self):
        self.rings: list[list[tuple[float, float]]] = []
        self.points = 0
        self.start = None
        self.last = None
        self.edges = None  # (x0, y0, x1, y1) of every point
        self.curved = False  # a curve was flattened into it

    def _bound(self, point) -> None:
        x, y = point
        self.edges = (x, y, x, y) if self.edges is None else (min(self.edges[0], x), min(self.edges[1], y),
                                                              max(self.edges[2], x), max(self.edges[3], y))
        self.last = point
        self.points += 1

    def move(self, point) -> None:
        self._bound(point)
        self.start = point
        if self.points <= MAX_PATH_POINTS:
            self.rings.append([point])

    def line(self, point) -> None:
        if self.start is None:
            self.move(point)
            return
        self._bound(point)
        if self.points <= MAX_PATH_POINTS and self.rings:
            self.rings[-1].append(point)

    def curve(self, current, c1, c2, end) -> None:
        self.curved = True
        for step in range(1, CURVE_STEPS + 1):
            t = step / CURVE_STEPS
            u = 1 - t
            self.line((u * u * u * current[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * end[0],
                       u * u * u * current[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * end[1]))

    def rectangle(self, corners) -> None:
        self.move(corners[0])
        for corner in corners[1:]:
            self.line(corner)
        self.start = self.last = corners[0]  # 're' leaves the current point at its origin

    @property
    def current(self):
        return self.last

    def bounds(self) -> tuple | None:
        return self.edges

    def rect(self) -> tuple | None:
        """The path's area when it is exactly one axis-aligned rectangle (by 're' or by four sides), else None."""
        if len(self.rings) != 1 or self.points > MAX_PATH_POINTS:
            return None
        ring = self.rings[0]
        if len(ring) == 5 and ring[4] == ring[0]:
            ring = ring[:4]
        if len(ring) != 4:
            return None
        if any(abs(p[0] - q[0]) > 1e-6 and abs(p[1] - q[1]) > 1e-6 for p, q in zip(ring, ring[1:] + ring[:1])):
            return None  # a side that is neither horizontal nor vertical
        x0, y0, x1, y1 = self.edges
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


@dataclass
class _Graphics:
    """The part of the graphics state the walker follows (saved by q, restored by Q)."""
    ctm: tuple
    clip: _Clip
    text: '_TextState'
    fill: str = COLOUR  # black
    stroke: str = COLOUR
    fill_space: int | None = 1
    stroke_space: int | None = 1
    fill_alpha: float = 1.0
    stroke_alpha: float = 1.0
    soft_mask: bool = False
    normal_blend: bool = True
    line_width: float = 1.0

    def copy(self) -> '_Graphics':
        return dataclasses.replace(self, text=dataclasses.replace(self.text))

    @property
    def fill_opaque(self) -> bool:
        return self.fill_alpha >= 1 and not self.soft_mask and self.normal_blend

    @property
    def stroke_opaque(self) -> bool:
        return self.stroke_alpha >= 1 and not self.soft_mask and self.normal_blend


class _Grid:
    """A page-space index of rectangles: each item is filed under the cells its rectangle meets."""

    def __init__(self, box):
        self.x0, self.y0 = box[0], box[1]
        self.dx = max((box[2] - box[0]) / GRID_CELLS, 1e-6)
        self.dy = max((box[3] - box[1]) / GRID_CELLS, 1e-6)
        self.cells: dict[tuple[int, int], list] = {}
        self.wide: list = []

    def _span(self, rect) -> tuple[int, int, int, int]:
        def index(value, origin, step):
            return min(GRID_CELLS - 1, max(0, int((value - origin) // step)))
        return (index(rect[0], self.x0, self.dx), index(rect[1], self.y0, self.dy),
                index(rect[2], self.x0, self.dx), index(rect[3], self.y0, self.dy))

    def add(self, rect, item) -> None:
        i0, j0, i1, j1 = self._span(rect)
        if (i1 - i0 + 1) * (j1 - j0 + 1) > MAX_GRID_SPAN:
            self.wide.append(item)
            return
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                self.cells.setdefault((i, j), []).append(item)

    def near(self, rect):
        """The items whose cells meet ``rect``'s, each once (with a count of the entries examined)."""
        yield from self.wide
        i0, j0, i1, j1 = self._span(rect)
        if (i1 - i0 + 1) * (j1 - j0 + 1) > len(self.cells):
            buckets = [items for (i, j), items in self.cells.items() if i0 <= i <= i1 and j0 <= j <= j1]
        else:
            buckets = [self.cells[(i, j)] for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)
                       if (i, j) in self.cells]
        seen = set()
        for items in buckets:
            for item in items:
                if id(item) not in seen:
                    seen.add(id(item))
                    yield item


# Fill-in characters: an opaque area over them hides no text (a field laid on an underscore line). Dots, dashes and
# middle dots are fill-in only as a rule of three or more (dot leaders, a dashed line), never one in a word or number.
_ING_FILL = frozenset('_\u2017\uff3f')
_ING_RULES = frozenset('.\u2026-\u2010\u2011\u2012\u2013\u2014\u2015\u00b7')


def _ING_widths_known(font) -> bool:
    """Whether the pypdf ``font`` measures its glyphs from the font itself (/Widths, a standard font's metrics, a CID
    font's /W): not a simple font without /Widths, which pypdf measures with one default width, nor a Type3 font,
    whose widths its own font matrix scales."""
    return font is not None and font.sub_type != 'Type3' and any(key != 'default' for key in font.character_widths)


def _ING_glyphs(font, string) -> list:
    """(the character it shows, whether word spacing applies to it, its width in thousandths of an em) of each glyph
    of ``string`` in the pypdf ``font``, as pypdf decodes and measures it (get_text_operands, get_display_str)."""
    if isinstance(string, str):
        text, raw = string, ''
    elif isinstance(font.encoding, str):
        try:
            text = string.decode(font.encoding, 'surrogatepass')
        except UnicodeDecodeError:
            text = string.decode(font.encoding, 'surrogateescape')
        raw = ''
    else:
        text = ''.join(font.encoding.get(code, chr(code)) for code in string)
        raw = ''.join(chr(code) for code in string)
    measured = raw or text
    out = []
    for index, char in enumerate(text):
        key = measured[index] if index < len(measured) else char
        width = font.space_width if key == font.space_char else font.get_text_width(key)
        out.append((font.character_map.get(char, char), char == ' ', width))
    return out


@dataclass(frozen=True)
class _Run:
    """The glyphs of one text-showing operator: where they lie, in text space and on the page."""
    box: tuple  # page space: generous bounds of the glyphs (descent 0.3, ascent 1.0 font sizes)
    margin: float  # one font size in page space: by how much a run must clear an edge to count as beyond it
    place: tuple  # text space (the text matrix at the run's start) to page space
    low: float  # the run's extent along the baseline, text space
    high: float
    rise: float
    size: float
    width: float  # COVER_WIDTH font sizes along the baseline, text space (horizontal scaling applied)
    # (start, end) along the baseline, text space, of each string the operator shows (the first one's start is where
    # the operator is, or left of it); then where its first glyph that is not whitespace starts, as drawn (past the
    # TJ numbers and the strings of spaces before it), and where its last one ends, one whitespace glyph's advance among
    # those it opens or closes with (0 when none, or when it cannot be read glyph by glyph: then the first starts where
    # the string does and the last ends at its end), whether whitespace glyphs open it, and the widest gap a run of
    # whitespace glyphs inside it shows less one glyph (0 when none, or when it cannot be read glyph by glyph)
    spans: tuple = ()
    font: object = field(default=None, compare=False)  # the pypdf Font that measures its strings (None: unknown)
    strings: tuple = field(default=(), compare=False)  # (start along the baseline, string) of each string it shows
    spacing: tuple = (0.0, 0.0, 1.0)  # character spacing, word spacing and horizontal scale it was shown with

    @functools.cached_property
    def letters(self) -> tuple | None:
        """The stretches of the run's glyphs that are not fill-in characters (_ING_FILL, and rules of three or more
        _ING_RULES), what an opaque area must cover to hide text, as (where each starts, (start, end) along the
        baseline in text space, sorted, the longest's length). None when the run has no fill-in character, or cannot
        be read glyph by glyph: the whole run counts, as before."""
        if not self.strings or not _ING_widths_known(self.font):
            return None
        char_spacing, word_spacing, scale = self.spacing
        glyphs = []  # (start, end, kind): kind 'fill', 'rule' or 'letter'
        for start, string in self.strings:
            try:
                decoded = _ING_glyphs(self.font, string)
            except Exception:
                return None
            x = start
            for shown, spaced, width in decoded:
                advance = (width / 1000 * self.size + char_spacing + (word_spacing if spaced else 0.0)) * scale
                kind = ('fill' if shown in _ING_FILL or shown.isspace() else 'rule' if shown in _ING_RULES
                        else 'letter')
                glyphs.append((min(x, x + advance), max(x, x + advance), kind))
                x += advance
        kinds = [kind for _, _, kind in glyphs]
        for index, kind in enumerate(kinds):  # a dot or a dash is a rule only among three or more
            if kind == 'rule':
                end = index
                while end < len(kinds) and kinds[end] == 'rule':
                    end += 1
                if end - index < 3:
                    kinds[index:end] = ['letter'] * (end - index)
                else:
                    kinds[index:end] = ['fill'] * (end - index)
        if 'fill' not in kinds:
            return None
        stretches: list = []
        previous = None
        for (low, high, _), kind in zip(glyphs, kinds):
            if kind != 'letter':
                previous = None
                continue
            if previous is None:
                stretches.append([low, high])
                previous = stretches[-1]
            else:
                previous[0], previous[1] = min(previous[0], low), max(previous[1], high)
        stretches.sort()
        longest = max((high - low for low, high in stretches), default=0.0)
        return [low for low, _ in stretches], [tuple(stretch) for stretch in stretches], longest

    def hides_letters(self, x0: float, x1: float) -> bool:
        """Whether [x0, x1] along the baseline (text space) covers a stretch of the run's letters over COVER_WIDTH font
        sizes, or the whole stretch (letters: the stretches indexed by where they start)."""
        starts, stretches, longest = self.letters
        for index in range(bisect.bisect_left(starts, x0 - longest), bisect.bisect_left(starts, x1)):
            start, end = stretches[index]
            covered = min(x1, end) - max(x0, start)
            if covered > 0 and covered >= min(end - start, self.width) - 1e-9:
                return True
        return False

    @property
    def core(self) -> tuple:
        return (self.low, self.rise + CORE_LOW * self.size, self.high, self.rise + CORE_HIGH * self.size)

    @functools.cached_property
    def page_core(self) -> tuple:
        return transformed_box(self.core, self.place)

    def struck_by(self, rect, before: bool = False) -> bool:
        """Whether the page-space rectangle ``rect``, a line painted over the run (or under it, ``before``),
        strikes it through."""
        back = _inverse(self.place)
        if back is None or not rectilinear(self.place):
            return False
        x0, y0, x1, y1 = transformed_box(rect, back)
        if y1 - y0 > STRIKE_THICKNESS * self.size:
            return False
        reach = STRIKE_REACH * self.width / COVER_WIDTH
        if before and (x0 < self.low - reach or x1 > self.high + reach):
            return False
        if y1 <= self.rise + STRIKE_LOW * self.size or y0 >= self.rise + STRIKE_HIGH * self.size:
            return False
        overlap = min(x1, self.high) - max(x0, self.low)
        span = self.width * STRIKE_SPAN / COVER_WIDTH  # STRIKE_SPAN font sizes, horizontal scaling applied
        return overlap > 0 and overlap >= min(self.high - self.low, span) - 1e-9

    def covered_by(self, rect) -> bool:
        """Whether the opaque page-space rectangle ``rect`` hides at least one glyph of the run: it covers the
        band every glyph inks, over at least COVER_WIDTH font sizes along the baseline (or the whole run). In a run
        with fill-in characters (an underscore line, dot leaders) it must do so over the run's letters: a white field
        laid on a fill-in line hides no text."""
        back = _inverse(self.place)
        if back is None or not rectilinear(self.place):
            core = self.page_core
            return rect[0] <= core[0] and rect[1] <= core[1] and rect[2] >= core[2] and rect[3] >= core[3]
        x0, y0, x1, y1 = transformed_box(rect, back)
        low, bottom, high, top = self.core
        if y0 > bottom or y1 < top:
            return False
        overlap = min(x1, high) - max(x0, low)
        if not (overlap > 0 and overlap >= min(high - low, self.width) - 1e-9):
            return False
        return self.letters is None or self.hides_letters(x0, x1)


class _Paint:
    """What a page has painted so far, in drawing order and page space, to judge whether text drawn on it shows:
    text painted in white over nothing, or text an opaque fill or image painted later covers, may not be shown.
    Invisible text (render mode 3, or no opacity) shows nothing itself: it is read as the layer of what is painted
    under it (OCR text over its scan, drawn before or after it), and named when nothing is."""

    def __init__(self, box):
        self.box = box
        self.runs: list = []  # runs of shown text not yet filed in the index (filed when a later paint asks)
        self.text: _Grid | None = None  # the runs of shown text
        self.backdrop = _Grid(box)  # bounds of everything painted in a colour that is not (known to be) white
        self.unseen: list = []  # runs of invisible text, judged against all the page paints (finish)
        self.checks = 0
        self.obscured = False
        self.struck = False  # a line was painted through shown text
        self.lines = _Grid(box)  # thin horizontal lines painted so far, for text drawn over them

    def _text(self) -> _Grid:
        if self.text is None:
            self.text = _Grid(self.box)
        for run in self.runs:
            self.text.add(run.page_core, run)
        self.runs = []
        return self.text

    def _near(self, grid, rect):
        for item in grid.near(rect):
            self.checks += 1
            if self.checks > MAX_PAINT_CHECKS:
                self.obscured = True  # too much to decide: named, not guessed
                return
            yield item

    def shown_text(self, run: _Run, white: bool) -> None:
        core = run.page_core if white else None
        if white and not self.obscured and not any(clip(core, rect) is not None
                                                   for rect in self._near(self.backdrop, core)):
            self.obscured = True
        if self.lines.cells or self.lines.wide:
            band = run.page_core
            if not self.struck and any(run.struck_by(rect, before=True) for rect in self._near(self.lines, band)):
                self.struck = True
        self.runs.append(run)

    def invisible(self, run: _Run) -> None:
        self.unseen.append(run)

    def finish(self) -> None:
        """Invisible text over nothing the page paints, before or after it, describes nothing shown: named."""
        for run in self.unseen:
            if self.obscured:
                break
            core = run.page_core
            if not any(clip(core, rect) is not None for rect in self._near(self.backdrop, core)):
                self.obscured = True
        self.unseen = []

    def painted(self, bounds, colour: str) -> None:
        if bounds is not None and colour != WHITE:
            self.backdrop.add(bounds, bounds)

    def line(self, rect) -> None:
        """A thin horizontal line painted over what was drawn before it (and under what is drawn after)."""
        if rect is None or self.struck:
            return
        if any(run.struck_by(rect) for run in self._near(self._text(), rect)):
            self.struck = True
            return
        self.lines.add(rect, rect)

    def opaque(self, rect) -> None:
        """An opaque rectangle painted over what was drawn before it."""
        if rect is None or self.obscured:
            return
        if any(run.covered_by(rect) for run in self._near(self._text(), rect)):
            self.obscured = True

    def covers_text(self, rects) -> bool | None:
        """Whether one of ``rects`` (opaque page-space areas painted over the page later) covers shown text; None
        when there was too much to decide."""
        text = self._text()
        for rect in rects:
            if any(run.covered_by(rect) for run in self._near(text, rect)):
                return True
            if self.checks > MAX_PAINT_CHECKS:
                return None
        return False


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
    offpage_text: bool = False  # text drawn wholly outside the visible page area, which was dropped
    clipped_text: bool = False  # text drawn wholly outside what its clipping path or form box shows, dropped
    obscured_text: bool = False  # text kept that a viewer may not show (see _Paint, and paths not followed)
    struck_text: bool = False  # text kept that a line painted over it strikes through
    paint: _Paint | None = field(default=None, repr=False, compare=False)
    # (baseline, start, end, font size, where its first and last glyphs that draw something start and end, one
    # whitespace glyph's advance among those it opens or closes with, whether whitespace opens it, the widest gap
    # padding inside it shows less a word space) in page space of each string an upright text operator the page shows
    # draws, in drawing order: where text ends, which the text layer does not say (pdf.py reads the gaps around check
    # boxes, and where printed boxes are drawn)
    ink: list = field(default_factory=list, repr=False, compare=False)

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

    def covered_by(self, rects) -> bool:
        """Whether opaque areas painted over the page after its content (``rects``, page space: annotation
        appearances) cover glyphs of its shown text. When that cannot be decided the page's text is named as
        possibly not shown (obscured_text) instead."""
        if not rects or self.paint is None:
            return False
        covered = self.paint.covers_text(rects)
        if covered is None:
            self.obscured_text = True
        return bool(covered)


@dataclass
class _Form:
    replacement: ContentStream | None  # a copy without its hidden content, when it had any
    placements: list  # (CTM in the form's own space, pixels or None) of the images it paints
    covers: list = field(default_factory=list)  # opaque rectangles it paints, in its own space


@dataclass
class _TextState:
    """The text-state parameters that are part of the graphics state (saved by q, restored by Q). ``font`` is the
    font dictionary Tf selected, so that a form drawn with the state measures with the same font."""
    font: object = None
    size: float = 0.0
    char_spacing: float = 0.0
    word_spacing: float = 0.0
    scale: float = 1.0
    leading: float = 0.0
    rise: float = 0.0
    mode: int = 0  # the text rendering mode (Tr)


class _TextPlacement:
    """Where a content stream draws its text (PDF 32000-1 9.3-9.4), in page space."""

    def __init__(self, resources, fonts: dict, graphics: _Graphics, measured: dict | None = None,
                 trims: dict | None = None):
        table = resolved(resources.get('/Font'))
        self.table = table if isinstance(table, DictionaryObject) else DictionaryObject()
        self.fonts = fonts  # id(font dict) -> pypdf Font, or None when it cannot be read
        self.measured = {} if measured is None else measured  # (id(font dict), string) -> (glyphs, spaces, widths)
        self.trims = {} if trims is None else trims  # (id(font dict), string) -> its whitespace ends (_I2_trim)
        self.graphics = graphics
        self.matrix = self.line = IDENTITY
        self.nothing = False  # the last run drew nothing: a zero font size, or a matrix that flattens it

    @property
    def state(self) -> _TextState:
        return self.graphics.text

    def apply(self, operator, operands) -> None:
        state = self.state
        if operator == b'BT':
            self.matrix = self.line = IDENTITY
        elif operator == b'Tf' and len(operands) >= 2:
            name = operands[0]
            font = resolved(self.table.raw_get(name)) if isinstance(name, str) and name in self.table else None
            state.font, state.size = (font if isinstance(font, DictionaryObject) else None), number(operands[1])
        elif operator in (b'Tc', b'Tw', b'Tz', b'TL', b'Ts', b'Tr') and operands:
            value = number(operands[0])
            if operator == b'Tc':
                state.char_spacing = value
            elif operator == b'Tw':
                state.word_spacing = value
            elif operator == b'Tz':
                state.scale = value / 100
            elif operator == b'TL':
                state.leading = value
            elif operator == b'Tr':
                state.mode = int(value)
            else:
                state.rise = value
        elif operator in (b'Td', b'TD') and len(operands) >= 2:
            if operator == b'TD':
                state.leading = -number(operands[1])
            self.move(number(operands[0]), number(operands[1]))
        elif operator == b'Tm' and len(operands) == 6:
            self.matrix = self.line = tuple(number(v) for v in operands)
        elif operator == b'T*':
            self.move(0.0, -state.leading)

    def move(self, tx: float, ty: float) -> None:
        self.matrix = self.line = multiply((1.0, 0.0, 0.0, 1.0, tx, ty), self.line)

    def run(self, operator, operands) -> _Run | None:
        """Apply a text-showing operator: where what it shows lies, or None when there is nothing to measure
        it by (no font size, a degenerate matrix)."""
        state = self.state
        if operator == b"'":
            self.move(0.0, -state.leading)
            items = list(operands[:1])
        elif operator == b'"':
            if len(operands) >= 2:
                state.word_spacing, state.char_spacing = number(operands[0]), number(operands[1])
            self.move(0.0, -state.leading)
            items = list(operands[2:3])
        elif operator == b'TJ':
            items = list(operands[0]) if operands and isinstance(operands[0], (list, ArrayObject)) else []
        else:
            items = list(operands[:1])
        start = self.matrix
        x = low = high = 0.0
        spans, strings = [], []
        for item in items:
            if isinstance(item, (bytes, str)):
                before = x
                x += self.advance(item)
                strings.append((before, item))
                if self.inked(item):  # a string of spaces draws nothing; the first is placed where the operator is
                    lead, trail, space, inner = self._I2_trim(item)
                    # its glyphs are drawn where the TJ's numbers and the strings before it put them: its first glyph
                    # that draws past its own opening whitespace, wherever the span itself is said to start
                    spans.append((before if spans else min(before, 0.0), x, before + lead, x - trail, space,
                                  lead > 0.0, inner))
            else:  # a TJ adjustment, in thousandths of a text-space unit, moves the next glyph left
                x -= number(item) / 1000 * state.size * state.scale
            low, high = min(low, x), max(high, x)
        self.matrix = multiply((1.0, 0.0, 0.0, 1.0, x, 0.0), start)
        size = state.size
        place = multiply(start, self.graphics.ctm)
        scale = math.sqrt(abs(place[0] * place[3] - place[1] * place[2]))
        self.nothing = size == 0 or scale == 0
        if size <= 0 or scale <= 0:  # nothing drawn, or mirrored text (a negative size): not measured
            return None
        box = transformed_box((low, state.rise - GLYPH_DESCENT * size, high, state.rise + GLYPH_ASCENT * size), place)
        return _Run(box, OUTSIDE_MARGIN * size * scale, place, low, high, state.rise, size,
                    COVER_WIDTH * size * abs(state.scale), tuple(spans), self.font(), tuple(strings),
                    (state.char_spacing, state.word_spacing, state.scale))

    def advance(self, string) -> float:
        """How far ``string`` moves the text position, in text-space units (each string measured once per font: a
        form drawn many times shows the same strings)."""
        state = self.state
        key = (id(state.font), bytes(string) if isinstance(string, bytes) else string)
        if key not in self.measured:
            font = self.font()
            if font is None:
                self.measured[key] = (len(string), 0, UNKNOWN_GLYPH_WIDTH * len(string))
            else:
                try:
                    text, _, widths = get_text_operands([string], list(IDENTITY), list(IDENTITY), font, ORIENTATIONS)
                except Exception:
                    text, widths = '', UNKNOWN_GLYPH_WIDTH * len(string)
                self.measured[key] = (max(len(text), 1 if string else 0), text.count(' '), widths)
        glyphs, spaces, widths = self.measured[key]
        return (widths / 1000 * state.size + glyphs * state.char_spacing + spaces * state.word_spacing) * state.scale

    def _I2_trim(self, string) -> tuple[float, float, float, float]:
        """(the advance of the whitespace glyphs ``string`` opens with, of those it closes with, of one of them, and the
        widest run of whitespace glyphs between two glyphs that draw something, less one of its glyphs: the gap padding
        inside it shows, a word space allowed), in text space as advance measures it: where its first and last glyphs
        that draw something lie, so a gap padded with spaces is read as the gap it shows, at its ends or inside it.
        (0, 0, 0, 0) when its font gives no widths, when it cannot be read glyph by glyph, or when every glyph is
        whitespace. Read once per font and string (only the ends are kept, and each distinct run inside it as its glyph
        count, its spaces, its width and its widest glyphs)."""
        state = self.state
        key = (id(state.font), bytes(string) if isinstance(string, bytes) else string)
        if key not in self.trims:
            ends = None
            font = self.font()
            if _ING_widths_known(font):
                try:
                    glyphs = _ING_glyphs(font, string)
                except Exception:
                    glyphs = []
                first = next((k for k, glyph in enumerate(glyphs) if not glyph[0].isspace()), None)
                if first is not None:
                    last = next(k for k in range(len(glyphs) - 1, -1, -1) if not glyphs[k][0].isspace())
                    runs, run = set(), []
                    for shown, spaced, width in glyphs[first:last + 1]:
                        if shown.isspace():
                            run.append((width, spaced))
                        elif run:
                            if len(run) > 1:  # one whitespace glyph alone is a word space, never a gap
                                runs.add((len(run), sum(1 for _, s in run if s), sum(w for w, _ in run),
                                          max((w for w, s in run if s), default=-1.0),
                                          max((w for w, s in run if not s), default=-1.0)))
                            run = []
                    ends = (tuple((width, spaced) for _, spaced, width in glyphs[:first]),
                            tuple((width, spaced) for _, spaced, width in glyphs[last + 1:]),
                            tuple(runs))
            self.trims[key] = ends if ends and (ends[0] or ends[1] or ends[2]) else None
        ends = self.trims[key]
        if ends is None:
            return 0.0, 0.0, 0.0, 0.0
        advances = [[(width / 1000 * state.size + state.char_spacing + (state.word_spacing if spaced else 0.0))
                     * state.scale for width, spaced in end] for end in ends[:2]]
        inner = 0.0
        for count, spaced, total, widest_spaced, widest_other in ends[2]:
            padded = ((total / 1000 * state.size + count * state.char_spacing + spaced * state.word_spacing)
                      * state.scale)
            one = max((widest_spaced / 1000 * state.size + state.char_spacing + state.word_spacing) * state.scale
                      if spaced else -math.inf,
                      (widest_other / 1000 * state.size + state.char_spacing) * state.scale
                      if count > spaced else -math.inf)
            inner = max(inner, padded - one)
        return sum(advances[0]), sum(advances[1]), max(advances[0] + advances[1], default=0.0), inner

    def inked(self, string) -> bool:
        """Whether ``string`` (measured by advance) shows anything but spaces."""
        glyphs, spaces, _ = self.measured[(id(self.state.font), bytes(string) if isinstance(string, bytes) else string)]
        return glyphs > spaces

    def font(self):
        font = self.state.font
        if not isinstance(font, DictionaryObject):
            return None
        if id(font) not in self.fonts:
            try:
                self.fonts[id(font)] = Font.from_font_resource(font)
            except Exception:
                self.fonts[id(font)] = None
        return self.fonts[id(font)]


class _Walker:
    def __init__(self, reader, optional: OptionalContent, box, positions: bool = False):
        self.reader = reader
        self.optional = optional
        self.content = PageContent(box=box)
        # The page's own walk: text is judged where it lands on the page, at every depth (forms are walked once
        # per placement, in page space), and what is painted is followed. An appearance is walked in its own space.
        self.positions = positions
        self.paint = _Paint(box) if positions else None
        self.content.paint = self.paint
        self.text_fonts: dict = {}  # id(font dict) -> pypdf Font, for measuring text
        self.measured: dict = {}  # (id(font dict), string) -> its measure (_TextPlacement.advance)
        self._I2_trims: dict = {}  # (id(font dict), string) -> its whitespace ends (_TextPlacement._I2_trim)
        self.shape_checks = 0  # clipping-path edges tested (MAX_SHAPE_CHECKS)
        self.forms: dict[tuple, _Form] = {}  # own-space walks: each form once; its images are re-placed per use
        self.parsed: dict[int, list] = {}  # id(form) -> its operations, parsed once
        self.variants: dict[tuple, ContentStream] = {}  # (form, resources, changes) -> its filtered copy
        self.walks = 0
        self.walk_limit = form_walk_limit()
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
        graphics = _Graphics(IDENTITY, _Clip(self.content.box), _TextState())
        kept, replaced, _, _ = self.walk(operations, resources, graphics, 0, self.content.placements, [])
        self.content.operations = kept
        self.paint.finish()
        self.content.obscured_text = self.content.obscured_text or self.paint.obscured
        self.content.struck_text = self.paint.struck
        fonts = self.mapped_fonts(resources)
        if replaced or fonts:
            self.content.resources = with_replacements(resources, replaced, fonts)
        return self.content

    def walk(self, operations, resources, graphics: _Graphics, depth: int, placements: list,
             covers: list) -> tuple[list, dict, bool, tuple]:
        """(kept operations, {new XObject name: filtered form}, changed, changes) for one content stream, drawn
        with ``graphics`` (copied: the caller's state is not changed). The images it paints are added to
        ``placements`` and the opaque rectangles to ``covers`` (both in the space the walk starts in); ``changes``
        names each operation not kept as it was, so equal filtered copies can be shared."""
        graphics = graphics.copy()
        kept: list = []
        replaced: dict = {}
        names: dict[int, str] = {}  # id(filtered form) -> its name in this stream's resources
        changes: list = []
        saved: list = []
        marked: list[bool] = []  # per open BMC/BDC: whether it hides what it encloses
        properties = resolved(resources.get('/Properties'))
        xobjects = resolved(resources.get('/XObject'))
        text = _TextPlacement(resources, self.text_fonts, graphics, self.measured, self._I2_trims)
        path, pending = _Path(), None
        for index, (operands, operator) in enumerate(operations):
            hidden = any(marked)
            if operator in (b'BMC', b'BDC'):
                marked.append(operator == b'BDC' and not self.marked_visible(operands, properties))
                if hidden or marked[-1]:
                    changes.append(index)
                    continue
            elif operator == b'EMC':
                closing = marked.pop() if marked else False
                if hidden or closing:
                    changes.append(index)
                    continue
            elif operator == b'q':
                saved.append(graphics.copy())
            elif operator == b'Q':
                if saved:
                    graphics = saved.pop()
                    text.graphics = graphics
            elif operator == b'cm' and len(operands) == 6:
                graphics.ctm = multiply(tuple(number(v) for v in operands), graphics.ctm)
            elif operator in TEXT_SHOWING:
                run = text.run(operator, operands) if self.positions else None
                verdict = self.judge(run, graphics) if not hidden else None
                if hidden or verdict in ('offpage', 'clipped'):
                    changes.append(index)
                    if hidden:
                        self.content.hidden_text = self.content.hidden_text or shows_text(operands)
                    elif verdict == 'offpage':
                        self.content.offpage_text = self.content.offpage_text or shows_text(operands)
                    else:
                        self.content.clipped_text = self.content.clipped_text or shows_text(operands)
                    kept.extend(state_only(operator, operands))
                    continue
                if self.positions and run is not None and shows_text(operands):
                    self.shown(run, graphics, verdict)
                elif self.positions and text.nothing and shows_text(operands):
                    self.paint.obscured = True  # zero-size glyphs show nothing: kept, named
            elif operator in TEXT_STATE or operator == b'Tr':
                text.apply(operator, operands)
            elif operator in PATH_OPERATORS:
                path = self.build(path, operator, operands, graphics)
            elif operator in PAINTING:
                if not hidden:
                    self.painted(path, operator, graphics, covers)
                if pending is not None:
                    graphics.clip = self.clipped(graphics.clip, path, pending)
                path, pending = _Path(), None
            elif operator in (b'W', b'W*'):
                pending = operator == b'W*'
            elif operator in COLOUR_OPERATORS:
                self.colour(operator, operands, graphics, resources)
            elif operator == b'gs' and operands:
                self.state_dictionary(operands[0], resources, graphics)
            elif operator == b'w' and operands:
                graphics.line_width = abs(number(operands[0], 1.0))
            elif operator == b'sh':
                if self.positions and not hidden:
                    self.paint.painted(graphics.clip.rect, UNKNOWN)
            elif operator == b'INLINE IMAGE':
                if hidden:
                    changes.append(index)
                    continue
                settings = operands.get('settings', {}) if isinstance(operands, dict) else {}
                placements.append((graphics.ctm, pixel_count(settings.get('/W', settings.get('/Width')),
                                                             settings.get('/H', settings.get('/Height')))))
                mask = is_true(settings.get('/IM', settings.get('/ImageMask')))
                self.image_painted(graphics, opaque=not mask, covers=covers,
                                   colour=graphics.fill if mask else UNKNOWN)
            elif operator == b'Do' and operands:
                action, replacement = self.draw(operands[0], xobjects, resources, graphics, depth, hidden, placements,
                                                covers)
                if action == 'drop':
                    changes.append(index)
                    continue
                if action == 'replace':
                    name = names.get(id(replacement))
                    if name is None:
                        taken = sum(1 for other in names.values() if other.startswith(operands[0] + REPLACEMENT_SUFFIX))
                        name = operands[0] + REPLACEMENT_SUFFIX + (str(taken + 1) if taken else '')
                        names[id(replacement)] = name
                        replaced[name] = replacement
                    changes.append((index, id(replacement)))
                    kept.append(([NameObject(name)], b'Do'))
                    continue
            kept.append((operands, operator))
        return kept, replaced, bool(changes), tuple(changes)

    # Text ------------------------------------------------------------------------
    def judge(self, run: _Run | None, graphics: _Graphics) -> str:
        """'offpage', 'clipped', 'unknown' (inside a clipping path this did not follow) or 'shown'."""
        if not self.positions or run is None:
            return 'shown'  # nothing to measure it by: keep it
        x0, y0, x1, y1 = run.box
        margin = run.margin
        reach = (x0 - margin, y0 - margin, x1 + margin, y1 + margin)
        if clip(reach, self.content.box) is None:
            return 'offpage'
        area = graphics.clip
        if clip(reach, area.rect) is None:
            return 'clipped'
        undecided = area.unknown
        for rings, even_odd in area.shapes:
            cost = sum(len(ring) for ring in rings)
            if self.shape_checks + cost > MAX_SHAPE_CHECKS:
                undecided = True  # too many edges to test: not followed, named
                continue
            self.shape_checks += cost
            if _apart(reach, rings, even_odd):
                return 'clipped'
        return 'unknown' if undecided else 'shown'

    def shown(self, run: _Run, graphics: _Graphics, verdict: str) -> None:
        a, b, c, d, e, f = run.place
        if a > 0 and d > 0 and abs(b) <= 0.01 * a and abs(c) <= 0.01 * d and _ING_widths_known(run.font):
            # upright, as pdf._origin reads pieces, and measured by the font's own widths
            self.content.ink.extend((f, e + start * a, e + end * a, run.size * d, e + low * a, e + high * a, space * a,
                                     opens, inner * a) for start, end, low, high, space, opens, inner in run.spans)
        mode = graphics.text.mode
        if verdict == 'unknown':
            self.paint.obscured = True
        fill, stroke = mode in (0, 2, 4, 6), mode in (1, 2, 5, 6)  # modes 3 and 7 paint neither
        if not ((fill and graphics.fill_alpha >= MIN_ALPHA) or (stroke and graphics.stroke_alpha >= MIN_ALPHA)):
            self.paint.invisible(run)  # read as the layer of what is painted under it (OCR text over its scan)
            return
        white = (not fill or graphics.fill == WHITE) and (not stroke or graphics.stroke == WHITE)
        self.paint.shown_text(run, white)

    # Paths, colour and painting ------------------------------------------------------
    def build(self, path: _Path, operator, operands, graphics: _Graphics) -> _Path:
        values = [number(v) for v in operands]
        ctm = graphics.ctm
        if operator == b're' and len(values) == 4:
            x, y, w, h = values
            path.rectangle([_apply(ctm, x, y), _apply(ctm, x + w, y), _apply(ctm, x + w, y + h),
                            _apply(ctm, x, y + h)])
        elif operator == b'm' and len(values) == 2:
            path.move(_apply(ctm, *values))
        elif operator == b'l' and len(values) == 2:
            path.line(_apply(ctm, *values))
        elif operator in (b'c', b'v', b'y') and path.current is not None:
            current = path.current
            if operator == b'c' and len(values) == 6:
                c1, c2, end = _apply(ctm, *values[0:2]), _apply(ctm, *values[2:4]), _apply(ctm, *values[4:6])
            elif operator == b'v' and len(values) == 4:
                c1, c2, end = current, _apply(ctm, *values[0:2]), _apply(ctm, *values[2:4])
            elif operator == b'y' and len(values) == 4:
                c1, c2, end = _apply(ctm, *values[0:2]), _apply(ctm, *values[2:4]), _apply(ctm, *values[2:4])
            else:
                return path
            path.curve(current, c1, c2, end)
        elif operator == b'h' and path.start is not None:
            path.line(path.start)
        return path

    def clipped(self, area: _Clip, path: _Path, even_odd: bool) -> _Clip:
        bounds = path.bounds()
        if bounds is None:  # an empty clipping path shows nothing
            return area.narrowed((0.0, 0.0, 0.0, 0.0))
        rect = path.rect()
        if rect is not None:
            return area.narrowed(rect)
        if path.points > MAX_PATH_POINTS:
            return area.narrowed(bounds, unknown=True)
        return area.narrowed(bounds, shape=(tuple(tuple(ring) for ring in path.rings if len(ring) > 1), even_odd))

    def painted(self, path: _Path, operator, graphics: _Graphics, covers: list) -> None:
        if operator not in FILLS and operator not in STROKES:
            return
        bounds = path.bounds()
        if bounds is None:
            return
        area = graphics.clip.rect
        if operator in FILLS:
            rect = path.rect()
            if graphics.fill_opaque and rect is not None and not graphics.clip.shapes:
                inside = clip(rect, area)
                if inside is not None:
                    if self.positions:
                        self.paint.opaque(inside)
                    else:
                        covers.append(inside)
            if self.positions:
                self.paint.painted(clip(bounds, area), graphics.fill)
                if rect is not None and graphics.fill_alpha >= MIN_ALPHA and not graphics.clip.shapes:
                    self.paint.line(clip(rect, area))
        if operator in STROKES and self.positions:
            half = graphics.line_width * math.sqrt(abs(graphics.ctm[0] * graphics.ctm[3]
                                                       - graphics.ctm[1] * graphics.ctm[2])) / 2
            self.paint.painted(clip((bounds[0] - half, bounds[1] - half, bounds[2] + half, bounds[3] + half), area),
                               graphics.stroke)
            if not path.curved and graphics.stroke_alpha >= MIN_ALPHA and not graphics.clip.shapes:
                for ring in path.rings:  # each straight horizontal segment, as the band its stroke paints
                    for (px, py), (qx, qy) in zip(ring, ring[1:]):
                        if abs(py - qy) <= 0.01 * abs(px - qx):
                            self.paint.line(clip((min(px, qx), min(py, qy) - half, max(px, qx), max(py, qy) + half),
                                                 area))

    def image_painted(self, graphics: _Graphics, *, opaque: bool, covers: list, colour: str = UNKNOWN) -> None:
        box = transformed_box(UNIT_SQUARE, graphics.ctm)
        inside = clip(box, graphics.clip.rect)
        if inside is None:
            return
        if opaque and graphics.fill_opaque and rectilinear(graphics.ctm) and not graphics.clip.shapes:
            if self.positions:
                self.paint.opaque(inside)
            else:
                covers.append(inside)
        if self.positions:
            self.paint.painted(inside, colour)

    def colour(self, operator, operands, graphics: _Graphics, resources) -> None:
        stroke = operator in (b'G', b'RG', b'K', b'CS', b'SC', b'SCN')
        if operator in (b'g', b'G', b'rg', b'RG', b'k', b'K'):
            count = {b'g': 1, b'G': 1, b'rg': 3, b'RG': 3, b'k': 4, b'K': 4}[operator]
            value, space = colour_class(operands, count), count
        elif operator in (b'cs', b'CS'):
            space = self.colour_space(operands[0] if operands else None, resources)
            value = COLOUR if space is not None else UNKNOWN  # each space's initial colour is black
        else:  # sc, scn, SC, SCN in the current space (a pattern's name, or an unknown space: unknown)
            space = graphics.stroke_space if stroke else graphics.fill_space
            value = colour_class(operands, space) if all(not isinstance(v, str) for v in operands) else UNKNOWN
        if stroke:
            graphics.stroke, graphics.stroke_space = value, space
        else:
            graphics.fill, graphics.fill_space = value, space

    def colour_space(self, name, resources) -> int | None:
        """The number of components of a DeviceGray / RGB / CMYK-like colour space, else None."""
        space = resolved(name)
        if isinstance(space, str) and space not in COLOUR_SPACES:
            table = resolved(resources.get('/ColorSpace'))
            space = resolved(raw_entry(table, space)) if isinstance(table, DictionaryObject) else None
        if isinstance(space, str):
            return COLOUR_SPACES.get(space)
        items = as_list(space)
        family = resolved(items[0]) if items else None
        if family == '/ICCBased' and len(items) > 1:
            profile = resolved(items[1])
            count = int(number(profile.get('/N'), 0)) if isinstance(profile, DictionaryObject) else 0
            return count if count in (1, 3, 4) else None
        return {'/CalGray': 1, '/CalRGB': 3}.get(family)

    def state_dictionary(self, name, resources, graphics: _Graphics) -> None:
        table = resolved(resources.get('/ExtGState'))
        entry = resolved(raw_entry(table, name)) if isinstance(table, DictionaryObject) else None
        if not isinstance(entry, DictionaryObject):
            return
        if '/ca' in entry:
            graphics.fill_alpha = number(entry.get('/ca'), 1.0)
        if '/CA' in entry:
            graphics.stroke_alpha = number(entry.get('/CA'), 1.0)
        if '/SMask' in entry:
            graphics.soft_mask = resolved(entry.get('/SMask')) != '/None'
        if '/BM' in entry:
            blends = [resolved(item) for item in as_list(entry.get('/BM'))]
            graphics.normal_blend = bool(blends) and blends[0] in NORMAL_BLENDS
        if '/LW' in entry:
            graphics.line_width = abs(number(entry.get('/LW'), graphics.line_width))

    # Forms and images --------------------------------------------------------------
    def marked_visible(self, operands, properties) -> bool:
        if len(operands) < 2 or resolved(operands[0]) != '/OC':
            return True
        entry = operands[1]
        if isinstance(entry, NameObject):
            entry = raw_entry(properties, entry)
        return self.optional.visible(entry)

    def draw(self, name, xobjects, resources, graphics: _Graphics, depth, hidden, placements, covers):
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
            placements.append((graphics.ctm, pixel_count(xobject.get('/Width'), xobject.get('/Height'))))
            if all(image is not xobject for image in self.content.images):
                self.content.images.append(xobject)
            masked = (is_true(xobject.get('/ImageMask')) or '/SMask' in xobject or '/Mask' in xobject
                      or '/SMaskInData' in xobject)
            self.image_painted(graphics, opaque=not masked, covers=covers,
                               colour=graphics.fill if is_true(xobject.get('/ImageMask')) else UNKNOWN)
            return 'keep', None
        if subtype != '/Form':
            return 'keep', None
        matrix = [number(v) for v in as_list(xobject.get('/Matrix'))]
        form_ctm = multiply(tuple(matrix), graphics.ctm) if len(matrix) == 6 else graphics.ctm
        if self.positions and self.form_outside(xobject, form_ctm):
            self.content.offpage_text = self.content.offpage_text or self.form_shows_text(xobject)
            return 'drop', None
        if depth >= MAX_FORM_DEPTH or id(xobject) in self.active:
            bbox = [number(v) for v in as_list(xobject.get('/BBox'))]
            if len(bbox) == 4:  # not looked into: assume it paints a dense image over its whole box
                x0, x1 = sorted((bbox[0], bbox[2]))
                y0, y1 = sorted((bbox[1], bbox[3]))
                placements.append((multiply((x1 - x0, 0.0, 0.0, y1 - y0, x0, y0), form_ctm), None))
            if self.positions and id(xobject) not in self.active and self.form_shows_text(xobject):
                self.paint.obscured = True  # pypdf reads its text, which is not judged here: named
            return 'keep', None
        if self.positions:
            if self.walks >= self.walk_limit:
                # pypdf enters the forms kept here, in the same order, and stops at the same count: it reads none
                # past this one, and the page is named as drawing more forms than the extractor reads.
                return 'keep', None
            return self.placed_form(xobject, resources, graphics, form_ctm, depth + 1, placements, covers)
        form = self.form(xobject, resources, depth + 1)
        placements.extend((multiply(local, form_ctm), pixels) for local, pixels in form.placements)
        covers.extend(transformed_box(rect, form_ctm) for rect in form.covers if rectilinear(form_ctm))
        return ('replace', form.replacement) if form.replacement is not None else ('keep', None)

    def placed_form(self, xobject, parent_resources, graphics: _Graphics, form_ctm, depth, placements, covers):
        """Walk a form where it is placed, in page space, inside its box: its text is judged where it lands."""
        own = resolved(xobject.get('/Resources'))
        resources = own if isinstance(own, DictionaryObject) else parent_resources
        operations = self.operations(xobject)
        self.check_fonts(resources)
        self.walks += 1
        inner = graphics.copy()
        inner.ctm = form_ctm
        bbox = [number(v) for v in as_list(xobject.get('/BBox'))]
        if len(bbox) == 4:
            x0, x1 = sorted((bbox[0], bbox[2]))
            y0, y1 = sorted((bbox[1], bbox[3]))
            corners = [_apply(form_ctm, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            box = transformed_box((x0, y0, x1, y1), form_ctm)
            inner.clip = inner.clip.narrowed(box) if rectilinear(form_ctm) else \
                inner.clip.narrowed(box, shape=((tuple(corners),), False))
        self.active.add(id(xobject))
        try:
            kept, replaced, changed, changes = self.walk(operations, resources, inner, depth, placements, covers)
        finally:
            self.active.discard(id(xobject))
        fonts = self.mapped_fonts(resources)
        if not changed and not fonts:
            return 'keep', None
        key = (id(xobject), id(resources), changes)
        if key not in self.variants:
            self.variants[key] = self.filtered(xobject, kept, resources, replaced, fonts)
        return 'replace', self.variants[key]

    def operations(self, xobject) -> list:
        if id(xobject) not in self.parsed:
            self.check_stream(xobject)
            try:
                self.parsed[id(xobject)] = list(ContentStream(xobject, self.reader, 'bytes').operations)
            except (MemoryError, RecursionError):
                raise
            except Exception:
                self.content.damaged = True
                self.parsed[id(xobject)] = []
        return self.parsed[id(xobject)]

    def filtered(self, xobject, kept, resources, replaced, fonts) -> ContentStream:
        replacement = ContentStream(None, self.reader)
        for name in xobject:
            if name not in ('/Filter', '/DecodeParms', '/Length', '/Resources'):
                replacement[NameObject(name)] = xobject.raw_get(name)
        replacement[NameObject('/Resources')] = with_replacements(resources, replaced, fonts)
        replacement.operations = kept
        return replacement

    def form(self, xobject, parent_resources, depth) -> _Form:
        """Walk a form XObject once (in its own space); later uses re-place what it paints."""
        own = resolved(xobject.get('/Resources'))
        resources = own if isinstance(own, DictionaryObject) else parent_resources
        key = (id(xobject), id(resources))
        if key in self.forms:
            return self.forms[key]
        operations = self.operations(xobject)
        self.check_fonts(resources)
        placements: list = []
        covers: list = []
        self.active.add(id(xobject))
        try:
            graphics = _Graphics(IDENTITY, _Clip((-math.inf, -math.inf, math.inf, math.inf)), _TextState())
            kept, replaced, changed, _ = self.walk(operations, resources, graphics, depth, placements, covers)
        finally:
            self.active.discard(id(xobject))
        replacement = None
        fonts = self.mapped_fonts(resources)
        if changed or fonts:
            replacement = self.filtered(xobject, kept, resources, replaced, fonts)
        self.forms[key] = _Form(replacement, placements, covers)
        return self.forms[key]

    def form_shows_text(self, xobject) -> bool:
        return form_shows_text(xobject, self.reader)

    def form_outside(self, xobject, form_ctm) -> bool:
        """Whether a form's bounding box, which clips all it draws, lies wholly outside the page box."""
        bbox = [number(v) for v in as_list(xobject.get('/BBox'))]
        if len(bbox) != 4:
            return False
        x0, x1 = sorted((bbox[0], bbox[2]))
        y0, y1 = sorted((bbox[1], bbox[3]))
        return clip(transformed_box((x0, y0, x1, y1), form_ctm), self.content.box) is None

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


def is_true(value) -> bool:
    value = resolved(value)
    return getattr(value, 'value', value) is True


def pixel_count(width, height) -> int:
    return max(0, int(number(width))) * max(0, int(number(height)))


def with_replacements(resources, replaced: dict, fonts: dict | None = None) -> DictionaryObject:
    """A copy of ``resources`` whose XObject table also names each filtered form (under the name ``replaced``
    gives it), and whose font table names each glyph-mapped symbol font in place of the original."""
    copy = DictionaryObject({NameObject(key): resources.raw_get(key) for key in resources})
    table = resolved(resources.get('/XObject'))
    entries = DictionaryObject({NameObject(key): table.raw_get(key) for key in table}) \
        if isinstance(table, DictionaryObject) else DictionaryObject()
    for name, form in replaced.items():
        entries[NameObject(name)] = form
    copy[NameObject('/XObject')] = entries
    if fonts:
        font_table = resolved(resources.get('/Font'))
        names = DictionaryObject({NameObject(key): font_table.raw_get(key) for key in font_table})
        for name, font in fonts.items():
            names[NameObject(name)] = font
        copy[NameObject('/Font')] = names
    return copy


def form_shows_text(xobject, reader) -> bool:
    """Whether a hidden form shows any text: only to name the exclusion in a message."""
    try:
        return any(operator in TEXT_SHOWING and shows_text(operands)
                   for operands, operator in ContentStream(xobject, reader, 'bytes').operations)
    except Exception:  # an unreadable form that is hidden anyway
        return False


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


@dataclass(frozen=True)
class VisibleForm:
    """A form XObject read on its own, such as an annotation appearance."""
    stream: StreamObject  # the form to read: a copy without its hidden optional content when it has any
    damaged: bool
    hidden_text: bool  # hidden optional content inside it showed text, which was dropped
    placements: list  # (CTM in the form's own space, before its /Matrix; pixels or None) of each image it paints
    images: list  # the image XObjects it paints, each once
    covers: tuple = ()  # the opaque rectangles it paints (fills and images), in its own space, before its /Matrix


def visible_form(xobject, reader, optional: OptionalContent, resources) -> VisibleForm:
    walker = _Walker(reader, optional, (0.0, 0.0, 0.0, 0.0))
    form = walker.form(xobject, resources if isinstance(resources, DictionaryObject) else DictionaryObject(), 0)
    target = form.replacement if form.replacement is not None else xobject
    return VisibleForm(target, walker.content.damaged, walker.content.hidden_text, list(form.placements),
                       list(walker.content.images), tuple(form.covers))


def appearance_matrix(stream, rect) -> tuple | None:
    """The matrix that draws an annotation appearance on the page (PDF 32000-1 12.5.5): its /Matrix, then the
    mapping of its transformed /BBox onto the annotation's /Rect; None when either is unusable."""
    bbox = [number(v) for v in as_list(stream.get('/BBox'))]
    if len(bbox) != 4 or rect is None:
        return None
    values = [number(v) for v in as_list(stream.get('/Matrix'))]
    matrix = tuple(values) if len(values) == 6 else IDENTITY
    x0, x1 = sorted((bbox[0], bbox[2]))
    y0, y1 = sorted((bbox[1], bbox[3]))
    tx0, ty0, tx1, ty1 = transformed_box((x0, y0, x1, y1), matrix)
    if tx1 <= tx0 or ty1 <= ty0:
        return None
    sx, sy = (rect[2] - rect[0]) / (tx1 - tx0), (rect[3] - rect[1]) / (ty1 - ty0)
    return multiply(matrix, (sx, 0.0, 0.0, sy, rect[0] - tx0 * sx, rect[1] - ty0 * sy))


def analyse_page(page, reader, optional: OptionalContent) -> PageContent:
    """Walk ``page``: visible images, hidden optional content, text outside the page and damaged streams."""
    return _Walker(reader, optional, page_box(page), positions=True).page(page)


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

OK, DAMAGED, UNVERIFIED, TOO_LARGE = 'ok', 'damaged', 'unverified', 'too large'
LZW = frozenset({'/LZWDecode', '/LZW'})
RUN_LENGTH = frozenset({'/RunLengthDecode', '/RL'})
CCITT = frozenset({'/CCITTFaxDecode', '/CCF'})
JBIG2 = frozenset({'/JBIG2Decode'})
JPX = frozenset({'/JPXDecode'})
INFLATE_CHUNK = 1 << 20
# An image's stream is followed to its end through at most this many decoded bytes: its declared size times
# the factor (for four 8-bit components, an upper bound), within the floor and ceiling. Past it, the image is
# too large to check (a decompression bomb cannot run the check long); output volume alone is never damage.
IMAGE_INFLATE_FACTOR, IMAGE_INFLATE_FLOOR, IMAGE_INFLATE_CEILING = 4, 64 * 1024 * 1024, 1024 * 1024 * 1024
LZW_WIDEN = {9: 512, 10: 1024, 11: 2048}  # the table size at which the code width grows (less EarlyChange)
FAX_G4_END = re.compile(r'0{11,}10{11,}1$')  # EOFB: two EOL codes (T.6)
FAX_G3_END = {False: re.compile(r'(?:0{11,}1){6}$'), True: re.compile(r'(?:0{11,}11){6}$')}  # RTC: six EOLs
FAX_EOL = re.compile(r'0{11,}1')


def stream_damaged(stream) -> bool:
    """Whether a stream the page's text depends on (its content, a form, a font's CMap, an object stream) fails
    a strict decode. pypdf decodes these itself and reads one that does not reach its end silently short."""
    return stream_state(stream, image=False) == DAMAGED


def image_state(stream) -> str:
    """OK, DAMAGED or UNVERIFIED for an image on a page read with OCR. pypdf never decodes these and the
    renderer draws one cut short as far as it goes, so each must be seen to end."""
    return stream_state(stream, image=True)


def stream_state(stream, *, image: bool) -> str:
    """OK, DAMAGED or UNVERIFIED (images only: a filter, or a size, this cannot check).

    Every filter must reach the end its encoding declares: Flate its stream end and checksum, LZW its
    end-of-data code (with every code one the table holds), RunLength its end-of-data byte, the ASCII filters
    their end markers, a JPEG its end-of-image marker, JPEG 2000 its end-of-codestream marker, JBIG2 a whole
    number of complete segments, and CCITT its end-of-block pattern (EOFB for Group 4; for Group 3 its RTC, or
    an EOL code for every row).
    For a stream the text depends on, output beyond pypdf's own limit is damage (pypdf reads no further); a
    filter this cannot check is left to pypdf, whose decoding warnings are watched separately.
    """
    try:
        filters = [resolved(item) for item in as_list(stream.get('/Filter'))]
        parameters = as_list(stream.get('/DecodeParms'))
        data = stream._data  # the stored bytes: decrypted, still encoded
    except Exception:
        return DAMAGED
    if not filters or not isinstance(data, bytes) or not data.strip(b'\x00\t\n\x0c\r '):
        return OK  # unfiltered, or empty: nothing a decoder could lose
    for index, name in enumerate(filters):
        params = resolved(parameters[index]) if index < len(parameters) else None
        params = params if isinstance(params, DictionaryObject) else DictionaryObject()
        last = index == len(filters) - 1
        if name in FLATE and image and last:
            return inflate_complete(data, image_budget(stream))
        if name in FLATE or name in LZW or name in RUN_LENGTH:
            if name in FLATE:
                state, data = inflate_strict(data)
            elif name in LZW:
                state, data = lzw_strict(data, int(number(params.get('/EarlyChange'), 1)), keep=not last)
            else:
                state, data = run_length_strict(data, keep=not last)
            if state == TOO_LARGE:
                return UNVERIFIED if image else DAMAGED
            if state != OK:
                return DAMAGED
        elif name in ASCII_HEX or name in ASCII_85:
            if (b'>' if name in ASCII_HEX else b'~>') not in data:
                return DAMAGED
            try:
                data = (ASCIIHexDecode if name in ASCII_HEX else ASCII85Decode).decode(data)
            except Exception:
                return DAMAGED
        elif name in DCT:
            return OK if jpeg_complete(data) else DAMAGED
        elif name in JPX:
            return OK if jpx_complete(data) else DAMAGED
        elif name in JBIG2:
            return jbig2_state(data, resolved(params.get('/JBIG2Globals')))
        elif name in CCITT:
            return ccitt_state(data, params, int(number(stream.get('/Height'), 0)))
        else:
            return UNVERIFIED if image else OK
    return OK


def image_budget(stream) -> int:
    width, height = max(0.0, number(stream.get('/Width'))), max(0.0, number(stream.get('/Height')))
    bits = max(8.0, number(stream.get('/BitsPerComponent'), 8))
    declared = width * height * 4 * bits / 8 + height  # four components, plus a predictor byte per row
    return int(min(IMAGE_INFLATE_CEILING, max(IMAGE_INFLATE_FLOOR, IMAGE_INFLATE_FACTOR * declared)))


def inflate_strict(data: bytes) -> tuple[str, bytes]:
    """(OK | DAMAGED | TOO_LARGE, output): OK only when the zlib stream ends and its checksum matches within
    pypdf's own output limit."""
    decompressor = zlib.decompressobj()
    try:
        output = decompressor.decompress(data, MAX_STRICT_OUTPUT_BYTES)
    except zlib.error:
        return DAMAGED, b''
    if decompressor.unconsumed_tail:  # past the output limit: pypdf reads no further either
        return TOO_LARGE, b''
    return (OK if decompressor.eof else DAMAGED), output


def inflate_complete(data: bytes, budget: int) -> str:
    """OK when the zlib stream reaches its end (checksum included), DAMAGED on a zlib error or when the data
    ends first, UNVERIFIED when more than ``budget`` bytes come out before either. The output is discarded."""
    decompressor = zlib.decompressobj()
    pending, produced = data, 0
    try:
        while not decompressor.eof:
            produced += len(decompressor.decompress(pending, INFLATE_CHUNK))
            pending = decompressor.unconsumed_tail
            if decompressor.eof:
                break
            if produced > budget:
                return UNVERIFIED
            if not pending:  # all input taken: what zlib still holds, then the verdict
                while not decompressor.eof:
                    more = decompressor.decompress(b'', INFLATE_CHUNK)
                    if not more:
                        break
                    produced += len(more)
                    if produced > budget:
                        return UNVERIFIED
                break
    except zlib.error:
        return DAMAGED
    return OK if decompressor.eof else DAMAGED


def lzw_strict(data: bytes, early_change: int = 1, *, keep: bool = True) -> tuple[str, bytes]:
    """(OK | DAMAGED | TOO_LARGE, output) for an LZWDecode stream (PDF 32000-1 7.4.4), decoded with pypdf's
    table rules. OK only when the end-of-data code (257) is read before the data runs out and every code is
    one the table holds; pypdf itself stops silently when the data runs out."""
    early = 1 if early_change else 0
    table = [bytes((code,)) for code in range(256)] + [b'', b'']
    width, widen = 9, LZW_WIDEN[9] - early
    buffer = bits = position = produced = 0
    size = len(data)
    previous = None
    out = bytearray()
    while True:
        while bits < width:
            if position >= size:
                return DAMAGED, b''  # the data ends before its end-of-data code
            buffer = ((buffer << 8) | data[position]) & 0xFFFFFF
            position += 1
            bits += 8
        bits -= width
        code = (buffer >> bits) & ((1 << width) - 1)
        if code == 256:
            del table[258:]
            width, widen, previous = 9, LZW_WIDEN[9] - early, None
            continue
        if code == 257:
            return OK, bytes(out)
        if previous is None:  # the first code, or the first after a clear-table code: a single byte
            if code >= 256:
                return DAMAGED, b''
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            if len(table) < 4096:
                table.append(table[previous] + entry[:1])
        elif code == len(table) and len(table) < 4096:  # the code being defined: the previous string, extended
            entry = table[previous] + table[previous][:1]
            table.append(entry)
        else:
            return DAMAGED, b''  # a code the table does not hold
        produced += len(entry)
        if keep:
            if produced > MAX_STRICT_OUTPUT_BYTES:
                return TOO_LARGE, b''
            out += entry
        previous = code
        if width < 12 and len(table) >= widen:
            width += 1
            widen = LZW_WIDEN.get(width, 4096) - early


def run_length_strict(data: bytes, *, keep: bool = True) -> tuple[str, bytes]:
    """(OK | DAMAGED | TOO_LARGE, output) for a RunLengthDecode stream: every run whole, then the EOD byte."""
    out = bytearray()
    position, size, produced = 0, len(data), 0
    while position < size:
        length = data[position]
        position += 1
        if length == 128:
            return OK, bytes(out)
        if length < 128:
            if position + length + 1 > size:
                return DAMAGED, b''
            piece = data[position:position + length + 1]
            position += length + 1
        else:
            if position >= size:
                return DAMAGED, b''
            piece = data[position:position + 1] * (257 - length)
            position += 1
        produced += len(piece)
        if keep:
            if produced > MAX_STRICT_OUTPUT_BYTES:
                return TOO_LARGE, b''
            out += piece
    return DAMAGED, b''  # no end-of-data byte


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


def jpx_complete(data: bytes) -> bool:
    """Whether a JPEG 2000 image (a raw codestream, or a JP2 file's contiguous codestream box) reaches its
    end-of-codestream marker (FFD9), which cannot occur inside the coded data. Padding after it is allowed."""
    if data.startswith(b'\xff\x4f'):  # SOC: a raw codestream
        return data.rstrip(b'\x00\t\n\r ').endswith(b'\xff\xd9')
    position, size = 0, len(data)
    while position + 8 <= size:
        length, kind, header = int.from_bytes(data[position:position + 4], 'big'), data[position + 4:position + 8], 8
        if length == 1:
            if position + 16 > size:
                return False
            length, header = int.from_bytes(data[position + 8:position + 16], 'big'), 16
        elif length == 0:  # the box runs to the end of the data
            length = size - position
        if length < header or position + length > size:
            return False
        if kind == b'jp2c':
            return data[position + header:position + length].rstrip(b'\x00').endswith(b'\xff\xd9')
        position += length
    return False


def jbig2_state(data: bytes, global_segments=None) -> str:
    """OK when an embedded JBIG2 stream (and its /JBIG2Globals) is a whole number of complete segments
    (ITU-T T.88 7.2), DAMAGED when a segment runs past the data, UNVERIFIED when one does not state its length.
    A stream cut exactly between two segments cannot be told from a whole one."""
    if isinstance(global_segments, StreamObject):
        try:
            state = jbig2_segments(global_segments.get_data())
        except Exception:
            return DAMAGED
        if state != OK:
            return state
    return jbig2_segments(data)


def jbig2_segments(data: bytes) -> str:
    position, size = 0, len(data)
    while position < size:
        if size - position < 6:
            return DAMAGED
        number_ = int.from_bytes(data[position:position + 4], 'big')
        flags, count = data[position + 4], data[position + 5] >> 5
        position += 5
        if count <= 4:
            position += 1
        elif count == 7:
            if position + 4 > size:
                return DAMAGED
            count = int.from_bytes(data[position:position + 4], 'big') & 0x1FFFFFFF
            position += 4 + (count + 8) // 8
        else:
            return DAMAGED  # counts 5 and 6 are not allowed
        position += count * (1 if number_ <= 256 else 2 if number_ <= 65536 else 4)
        position += 4 if flags & 0x40 else 1
        if position + 4 > size:
            return DAMAGED
        length = int.from_bytes(data[position:position + 4], 'big')
        position += 4
        if length == 0xFFFFFFFF:
            return UNVERIFIED  # an unknown length, ended only by a marker inside the coded data
        position += length
        if position > size:
            return DAMAGED
    return OK


def ccitt_state(data: bytes, params, rows: int = 0) -> str:
    """OK, DAMAGED or UNVERIFIED for CCITT fax data (ITU-T T.4 / T.6, PDF 32000-1 7.4.6).

    Group 4 (/K < 0) must end with its end-of-block pattern (EOFB), followed only by fill. Group 3 must end
    with its RTC, or hold an EOL code for every row: an EOL (eleven or more zeros, then a one) occurs nowhere
    else in the coded data, and libtiff, the usual encoder, writes one before each row and no RTC. With
    /EndOfBlock false, or Group 3 data without EOLs, completeness could only be shown by decoding: UNVERIFIED.
    """
    end_of_block = resolved(params.get('/EndOfBlock'))
    k = number(params.get('/K'), 0)
    rows = int(number(params.get('/Rows'), 0)) or rows
    core = data.rstrip(b'\x00')
    if k < 0:
        if getattr(end_of_block, 'value', end_of_block) is False:
            return UNVERIFIED
        tail = ''.join(f'{byte:08b}' for byte in core[-64:]).rstrip('0')
        return OK if FAX_G4_END.search(tail) else DAMAGED
    bits = ''.join(f'{byte:08b}' for byte in core).rstrip('0')
    if FAX_G3_END[k > 0].search(bits[-1024:]):
        return OK
    lines = len(FAX_EOL.findall(bits))
    if lines and rows:
        return OK if lines >= rows else DAMAGED
    return UNVERIFIED
