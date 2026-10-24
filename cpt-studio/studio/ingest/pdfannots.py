"""What a PDF page's annotations show, for extraction (ARCHITECTURE 5.1).

A page's content stream is not all a viewer draws on it: filled form fields
(widget annotations), typed-on text (FreeText), stamps and other annotations
are drawn on top. ``read_annotations`` turns what is displayed into text
where that can be done exactly, and accounts for the rest:

- A displayed form field is read from its stored value (``/V``, inherited
  through ``/Parent``): a text field as its text, a choice field as the option
  shown, a check box as checked or not checked, a radio group as the option
  selected: with /Opt, the entry of the selected widget, by its place in the
  field's /Kids (PDF 32000-1 Table 227), else the state's name ('no option
  selected' when none is). A check-box field with /Opt, or whose widgets carry
  more than one distinct on-state (a yes/no pair of boxes), is a set of options
  and is read like a radio group. Each displayed button's rectangle, state and
  option word is kept, so that its glyph can be written beside its label or
  option word in the page text (pdf.py), as is the rectangle of a FreeText or
  stamp annotation that shows only a mark (X, ✓, ✔), which checks a printed box
  it covers. Push buttons and fields without a value contribute the text their
  appearance draws. Password fields are not read.
- The labelled block keeps one line per entry: blank lines inside an entry (a
  multi-line field value, FreeText text) are dropped, so the only blank line
  after a page's block is the page separator.
- A text or combo-box field whose appearance draws text that differs from its
  stored value is named, because viewers differ in which one they show. An
  appearance that draws no text, or whose own /OC group is off, differs from
  a non-empty value; a field with no appearance is drawn from its value. A
  difference that the field's own standard format action explains (Acrobat's
  AFNumber_Format, AFPercent_Format, AFDate_FormatEx / AFDate_Format,
  AFSpecial_Format: studio.ingest.pdfformat) is display formatting, not a
  disagreement; any other format script leaves it named.
- A FreeText annotation is read from ``/Contents`` (else its appearance), and
  named when its appearance shows different text. One whose appearance's own
  /OC group is off shows nothing: it is not read and is counted as hidden.
  Any other annotation whose appearance draws text is read from that text;
  one whose appearance is in a hidden layer is named.
- Annotation notes that are not drawn on the page (sticky notes, comment
  text) are counted, not read, like DOCX comments; any other displayed
  annotation that draws without text (ink, a stamp, a shape, a highlight, a
  mark viewers draw from its /QuadPoints) is counted as a drawing. Strike-out
  and redaction marks are counted as marks, and the opaque rectangles an
  annotation paints over the page (its appearance's fills and images, or a
  Square / Circle's /IC interior) are kept, so that text they cover is named
  (pdf.py). Any displayed annotation (an image field, a Square, ...) whose
  appearance paints an image is counted as drawn; those images also count
  towards the page's image coverage, placed as viewers place the appearance
  (PDF 32000-1 12.5.5). Hidden annotations — the Hidden or NoView flag,
  an optional-content group that is off, or a rectangle that misses the page
  — are not read and are counted.
- An appearance is read like page content: optional content hidden by
  default inside it is dropped (and named), an appearance whose own /OC group
  is off draws nothing, symbol fonts are read as the characters their glyphs
  show, and its streams are integrity-checked. Characters that name no glyph
  (private-use or control codes, unmapped symbol glyphs) are counted and
  dropped from what is written. An annotation
  that must be read from its appearance and whose appearance cannot be read
  (a damaged stream, a parse error) is counted as unreadable.

Importable without Django (the extraction child imports it).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, StreamObject

from .pdfcontent import (OptionalContent, appearance_matrix, as_list, clip, form_shows_text, multiply, number,
                         object_key, page_box, raw_entry, rectilinear, resolved, transformed_box, visible_form)
from .pdfformat import displayed_texts
from .pdffonts import undecodable
from .text import canonicalize, non_space_count

HIDDEN_FLAGS = 2 | 32  # Hidden, NoView (PDF 32000-1 12.5.3)
FIELD_PASSWORD = 1 << 13
FIELD_RADIO = 1 << 15
FIELD_PUSH_BUTTON = 1 << 16
FIELD_COMBO = 1 << 17
MAX_PARENT_DEPTH = 32
NOT_DRAWN = frozenset({'/Popup', '/Link'})  # a popup shows its parent's note; a link draws nothing of its own
# Marks that change what the text under them says: struck through, or redacted (shown as its overlay).
STRIKE_MARKS = frozenset({'/StrikeOut', '/Redact'})
# Text markup viewers draw from /QuadPoints when there is no appearance.
QUAD_MARKUP = frozenset({'/Highlight', '/Underline', '/Squiggly', '/StrikeOut', '/Redact'})
FILLED_SHAPES = frozenset({'/Square', '/Circle'})  # drawn from /IC (their interior colour) without an appearance
_WHITESPACE = re.compile(r'\s+')
_TAGS = re.compile(r'<[^>]*>')
BOX_MARKS = frozenset({'X', 'x', '\u2713', '\u2714'})  # what a typed or stamped mark over a printed box says
MARKED = frozenset({'/FreeText', '/Stamp'})


@dataclass(frozen=True)
class Button:
    """A displayed check box or radio button, as pdf.py places its glyph."""
    rect: tuple  # (x0, y0, x1, y1)
    on: bool
    radio: bool  # a radio button: its glyph is written only before its own option word
    option: str  # its option word (a radio group or a set of options); '' for a single check box
    group: int  # its field: the buttons of one group are placed together or not at all


@dataclass
class PageAnnotations:
    fields: list[str] = field(default_factory=list)  # 'label: value' lines, in page order
    texts: list[str] = field(default_factory=list)  # annotation text, in page order
    mismatched: list[str] = field(default_factory=list)  # fields whose appearance differs from the value
    unreadable: int = 0
    hidden: int = 0
    drawn: int = 0
    note_chars: int = 0
    hidden_text: bool = False  # an appearance held text in optional content that is hidden by default
    undecodable: int = 0  # characters dropped from what is written: they name no glyph
    boxes: list = field(default_factory=list)  # (rect, checked) of each displayed check box
    buttons: list = field(default_factory=list)  # rect of each displayed check box or radio button
    widgets: list = field(default_factory=list)  # Button of each displayed check box or radio button
    marks: list = field(default_factory=list)  # rect of each displayed FreeText or stamp that shows only a mark
    placements: list = field(default_factory=list)  # (CTM, pixels) of images displayed appearances paint, page space
    images: list = field(default_factory=list)  # the image XObjects displayed appearances paint
    marked: int = 0  # displayed strike-out and redaction marks
    covers: list = field(default_factory=list)  # opaque page-space rectangles displayed annotations paint

    def block(self, page: int) -> str:
        """The labelled text added after the page's own text ('' when there is none)."""
        parts = []
        if self.fields:
            parts.append(f'[PDF form fields on page {page}]\n' + _entries(self.fields))
        if self.texts:
            parts.append(f'[PDF annotation text on page {page}]\n' + _entries(self.texts))
        return canonicalize('\n'.join(parts))


def _entries(entries: list[str]) -> str:
    """The entries one after another, each without its blank lines: a blank line would end the block early."""
    lines = (line for entry in entries for line in canonicalize(entry).split('\n'))
    return '\n'.join(line for line in lines if line.strip())


def read_annotations(page, optional: OptionalContent, acroform) -> PageAnnotations:
    found = PageAnnotations()
    annotations = resolved(page.get('/Annots'))
    if not isinstance(annotations, (list, ArrayObject)):
        return found
    acroform = acroform if isinstance(acroform, DictionaryObject) else DictionaryObject()
    reader = _Reader(page, resolved(acroform.get('/DR')), is_true(acroform.get('/NeedAppearances')),
                     page_box(page), optional, found)
    for reference in annotations:
        annotation = resolved(reference)
        if isinstance(annotation, DictionaryObject):
            reader.read(annotation)
    return found


@dataclass
class _Field:
    node: DictionaryObject  # the terminal field (the widget itself when the two are merged)
    kind: str | None
    value: object
    flags: int
    options: list
    label: str
    script: str = ''  # the JavaScript of its format action (/AA /F), '' for none


class _Reader:
    def __init__(self, page, defaults, regenerated: bool, box, optional: OptionalContent, found: PageAnnotations):
        self.page = page
        self.defaults = defaults if isinstance(defaults, DictionaryObject) else None
        self.regenerated = regenerated  # /NeedAppearances: viewers redraw fields from their values
        self.box = box
        self.optional = optional
        self.found = found
        self.lines: dict[int, int] = {}  # id(terminal field) -> index in found.fields
        self.painted = None  # the appearance read for the current annotation: (stream, VisibleForm)
        self.groups: dict = {}  # id(terminal field) -> (options set, {kid key: place in /Kids}), read once per field

    def read(self, annotation) -> None:
        subtype = resolved(annotation.get('/Subtype'))
        if subtype in NOT_DRAWN:
            return
        shown = self.displayed(annotation)
        self.painted = None
        written = len(self.found.texts)
        if subtype == '/Widget':
            self.widget(annotation, shown)
        elif subtype == '/FreeText':
            self.free_text(annotation, shown)
        else:
            self.other(annotation, subtype, shown)
        if subtype in MARKED and len(self.found.texts) == written + 1 and self.found.texts[-1].strip() in BOX_MARKS:
            rect = rect_of(annotation)
            if rect is not None:
                self.found.marks.append(rect)
        if shown and self.painted is not None and self.painted[1].placements:
            self.add_images(annotation, *self.painted)

    def add_images(self, annotation, stream, form) -> None:
        """An appearance that paints images is not text: counted as drawn, its images placed on the page."""
        self.found.drawn += 1
        matrix = appearance_matrix(stream, rect_of(annotation))
        if matrix is None:
            return
        self.found.placements.extend((multiply(local, matrix), pixels) for local, pixels in form.placements)
        self.found.images.extend(image for image in form.images
                                 if all(image is not known for known in self.found.images))

    def displayed(self, annotation) -> bool:
        flags = int(number(annotation.get('/F'), 0))
        if flags & HIDDEN_FLAGS or not self.optional.visible(raw_entry(annotation, '/OC')):
            return False
        rect = rect_of(annotation)
        return rect is not None and clip(rect, self.box) is not None

    # Form fields -------------------------------------------------------------------
    def widget(self, widget, shown: bool) -> None:
        info = field_of(widget)
        if info.kind == '/Tx' and info.flags & FIELD_PASSWORD:
            return
        if info.kind == '/Btn' and not info.flags & FIELD_PUSH_BUTTON:
            options, places = self.group(info)
            line, on, option = button_line(widget, info, options, places)
            if not shown:
                self.found.hidden += on
                return
            rect = rect_of(widget)
            if rect is not None:
                radio = bool(info.flags & FIELD_RADIO)
                self.found.buttons.append(rect)
                if not radio:
                    self.found.boxes.append((rect, on))
                self.found.widgets.append(Button(rect, on, radio, option, id(info.node)))
            self.add_line(info, line, replace=on)
            return
        value = choice_text(info) if info.kind == '/Ch' else value_text(info.value) if info.kind == '/Tx' else ''
        appearance = self.appearance_text(widget)
        if value.strip():
            line = f'{info.label}: {value}'
            comparable = info.kind == '/Tx' or bool(info.flags & FIELD_COMBO)
            drawn = squeezed(appearance or '')
            # An appearance that exists is what viewers draw, even when it draws nothing or is in a hidden layer.
            drawing = normal_appearance(widget) is not None
            if shown and comparable and not self.regenerated and drawing:
                if appearance is None:  # what it shows cannot be read: not a known disagreement, but unread
                    self.found.unreadable += 1
                elif drawn != squeezed(value) and drawn not in {squeezed(text)
                                                                 for text in displayed_texts(info.script, value)}:
                    self.found.mismatched.append(info.label)
        elif appearance is None:
            self.found.unreadable += shown
            return
        elif appearance.strip():
            line = f'{info.label}: {one_line(appearance)}'
        else:
            if shown and info.kind == '/Sig' and info.value is not None:
                self.found.drawn += 1  # signed; its appearance draws no text
            return
        if not shown:
            self.found.hidden += 1
            return
        self.add_line(info, line, replace=False)

    def group(self, info: _Field) -> tuple[bool, dict]:
        """(whether the field is a set of options, {kid key: its first place in /Kids}), read once per field: a
        radio group, a check-box field with /Opt, or one whose widgets carry more than one distinct on-state."""
        key = id(info.node)
        if key not in self.groups:
            places, states = {}, set()
            for place, kid in enumerate(as_list(info.node.get('/Kids'))):
                places.setdefault(object_key(kid), place)
                states.update(on_states(resolved(kid)))
            options = bool(info.flags & FIELD_RADIO) or bool(info.options) or len(states) > 1
            self.groups[key] = (options, places)
        return self.groups[key]

    def add_line(self, info: _Field, line: str, *, replace: bool) -> None:
        """One line per field on a page; a later widget of the field that is on replaces the line."""
        key = id(info.node)
        if key in self.lines:
            if replace:
                self.found.fields[self.lines[key]] = self.clean(line)
            return
        self.lines[key] = len(self.found.fields)
        self.found.fields.append(self.clean(line))

    def clean(self, text: str) -> str:
        """``text`` without the characters that name no glyph, which are counted."""
        kept = ''.join(char for char in text if not undecodable(char))
        self.found.undecodable += len(text) - len(kept)
        return kept

    # Other annotations -------------------------------------------------------------
    def free_text(self, annotation, shown: bool) -> None:
        contents = canonicalize(text_of(annotation.get('/Contents'))).strip('\n')
        if not contents.strip():
            contents = rich_text(annotation.get('/RC'))
        if self.appearance_hidden(annotation):  # it draws nothing, so what /Contents says is not shown
            self.found.hidden += bool(contents.strip()) or self.hidden_appearance_shows_text(annotation)
            return
        appearance = self.appearance_text(annotation)
        text = contents if contents.strip() else (appearance or '').strip('\n')
        if not text.strip():
            self.found.unreadable += shown and appearance is None
            return
        if not shown:
            self.found.hidden += 1
            return
        drawn = squeezed(appearance or '')
        if contents.strip() and normal_appearance(annotation) is not None and drawn != squeezed(contents):
            self.found.mismatched.append('text annotation')
        self.found.texts.append(self.clean(text))

    def other(self, annotation, subtype, shown: bool) -> None:
        note = canonicalize(text_of(annotation.get('/Contents')))
        appearance = self.appearance_text(annotation)
        if not shown:
            self.found.hidden += bool((appearance or '').strip())
            return
        if self.appearance_hidden(annotation) and self.hidden_appearance_shows_text(annotation):
            self.found.hidden_text = True
        self.found.note_chars += non_space_count(note)
        if subtype in STRIKE_MARKS:  # what the page now says of the text under it is not what that text reads
            self.found.marked += 1
        self.found.covers.extend(self.covers(annotation, subtype))
        if appearance is None:
            self.found.unreadable += 1
        elif appearance.strip():
            self.found.texts.append(self.clean(appearance.strip('\n')))
        elif self.drawn_appearance(annotation) or (normal_appearance(annotation) is None and subtype in QUAD_MARKUP):
            self.found.drawn += 1  # a drawing, a shape or a mark over the text: not text, so named

    def covers(self, annotation, subtype) -> list:
        """The opaque page-space rectangles a displayed annotation paints over the page: the opaque fills and images
        of its appearance (read by appearance_text, mapped as viewers place it), or the interior of a Square or
        Circle drawn from /IC when it has no appearance. None when the annotation is translucent (/CA)."""
        if number(annotation.get('/CA'), 1.0) < 1:
            return []
        rect = rect_of(annotation)
        stream = normal_appearance(annotation)
        if stream is not None:
            if rect is None or self.painted is None or self.painted[0] is not stream:
                return []  # an appearance in a hidden layer paints nothing
            matrix = appearance_matrix(stream, rect)
            bbox = [number(v) for v in as_list(stream.get('/BBox'))]
            if matrix is None or not rectilinear(matrix) or len(bbox) != 4:
                return []
            box = (min(bbox[0], bbox[2]), min(bbox[1], bbox[3]), max(bbox[0], bbox[2]), max(bbox[1], bbox[3]))
            return [transformed_box(inside, matrix) for inside in (clip(cover, box) for cover in self.painted[1].covers)
                    if inside is not None]
        if rect is None or subtype not in FILLED_SHAPES or not as_list(annotation.get('/IC')):
            return []
        border = resolved(annotation.get('/BS'))
        width = number(border.get('/W'), 1.0) if isinstance(border, DictionaryObject) else 1.0
        x0, y0, x1, y1 = rect[0] + width, rect[1] + width, rect[2] - width, rect[3] - width
        if subtype == '/Circle':  # the rectangle inscribed in the ellipse
            cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * 0.7071, (y1 - y0) / 2 * 0.7071
            x0, y0, x1, y1 = cx - rx, cy - ry, cx + rx, cy + ry
        return [(x0, y0, x1, y1)] if x1 > x0 and y1 > y0 else []

    def appearance_hidden(self, annotation) -> bool:
        """Whether the annotation has a normal appearance whose own /OC group is off (it then draws nothing)."""
        stream = normal_appearance(annotation)
        return stream is not None and not self.optional.visible(raw_entry(stream, '/OC'))

    def hidden_appearance_shows_text(self, annotation) -> bool:
        stream = normal_appearance(annotation)
        return stream is not None and form_shows_text(stream, self.page.pdf)

    def drawn_appearance(self, annotation) -> bool:
        stream = normal_appearance(annotation)
        return stream is not None and self.optional.visible(raw_entry(stream, '/OC'))

    def appearance_text(self, annotation) -> str | None:
        """The text the normal appearance draws ('' when it draws none), or None when it cannot be read."""
        stream = normal_appearance(annotation)
        if stream is None or not self.optional.visible(raw_entry(stream, '/OC')):
            return ''
        form = visible_form(stream, self.page.pdf, self.optional, self.defaults)
        self.painted = (stream, form)
        stream = form.stream
        self.found.hidden_text = self.found.hidden_text or form.hidden_text
        if form.damaged:
            return None
        if not isinstance(resolved(stream.get('/Resources')), DictionaryObject) and self.defaults is not None:
            copy = DecodedStreamObject()  # an appearance relying on the form's default resources
            try:
                copy.set_data(stream.get_data())
            except Exception:
                return None
            for key in stream:
                if key not in ('/Filter', '/DecodeParms', '/Length'):
                    copy[NameObject(key)] = stream.raw_get(key)
            copy[NameObject('/Resources')] = self.defaults
            stream = copy
        try:
            return canonicalize(self.page.extract_xform_text(stream, (0, 90, 180, 270), 200.0))
        except (MemoryError, RecursionError):
            raise
        except Exception:
            return None


def rect_of(annotation) -> tuple[float, float, float, float] | None:
    """An annotation's /Rect as (x0, y0, x1, y1) with x0 <= x1 and y0 <= y1, or None."""
    rect = [number(v) for v in as_list(annotation.get('/Rect'))]
    if len(rect) != 4:
        return None
    return min(rect[0], rect[2]), min(rect[1], rect[3]), max(rect[0], rect[2]), max(rect[1], rect[3])


def field_of(widget) -> _Field:
    chain, node = [], widget
    while isinstance(node, DictionaryObject) and len(chain) < MAX_PARENT_DEPTH and \
            not any(node is seen for seen in chain):
        chain.append(node)
        node = resolved(node.get('/Parent'))

    def inherited(key):
        return next((resolved(item.get(key)) for item in chain if key in item), None)

    terminal = next((item for item in chain if '/T' in item), widget)
    names = [text_of(item.get('/T')) for item in reversed(chain) if '/T' in item]
    label = text_of(terminal.get('/TU')) or '.'.join(name for name in names if name) or 'form field'
    options = inherited('/Opt')  # an array is used as it is: never copied per widget
    return _Field(node=terminal, kind=inherited('/FT'), value=inherited('/V'), flags=int(number(inherited('/Ff'))),
                  options=options if isinstance(options, (list, ArrayObject)) else as_list(options),
                  label=one_line(label), script=format_script(chain))


def format_script(chain) -> str:
    """The JavaScript of the format action (/AA /F) of the widget or of the field it belongs to."""
    for item in chain:
        actions = resolved(item.get('/AA'))
        action = resolved(actions.get('/F')) if isinstance(actions, DictionaryObject) else None
        script = resolved(action.get('/JS')) if isinstance(action, DictionaryObject) else None
        if isinstance(script, StreamObject):
            try:
                return script.get_data().decode('latin-1')
            except Exception:
                return ''
        if script is not None:
            return text_of(script)
    return ''


def on_states(widget) -> list:
    """The on-state names of a widget's normal appearance (every state but /Off)."""
    appearances = resolved(widget.get('/AP')) if isinstance(widget, DictionaryObject) else None
    normal = resolved(appearances.get('/N')) if isinstance(appearances, DictionaryObject) else None
    return [key for key in normal if key != '/Off'] if isinstance(normal, DictionaryObject) else []


def button_line(widget, info: _Field, options: bool, places: dict) -> tuple[str, bool, str]:
    """('label: checked' | 'label: not checked', on, '') for a check box; for a radio group or a set of options
    ('label: <option>' | 'label: no option selected', on, the widget's own option word)."""
    states = on_states(widget)
    state = resolved(widget.get('/AS'))
    if state is None and isinstance(info.value, str) and (info.value in states or not states):
        state = info.value  # no appearance state: viewers draw the box from the field's value
    on = state is not None and state != '/Off' and (not states or state in states)
    if options:
        own = text_of(state if on else (states[0] if states else '')).removeprefix('/')
        if info.options:
            own = listed_option(widget, info, places) or own
        option = own if on else ''
        return (f'{info.label}: {option}' if option else f'{info.label}: no option selected'), on, own
    return (f'{info.label}: checked' if on else f'{info.label}: not checked'), on, ''


def listed_option(widget, info: _Field, places: dict) -> str:
    """The /Opt entry of ``widget``: one per widget, in the order of the field's /Kids (PDF 32000-1 Table 227),
    found through the field's place map (read once per field). Read by position, never from a decimal state name,
    whose digits may be the option itself."""
    index = places.get(object_key(widget))
    if index is None or index >= len(info.options):
        return ''
    entry = resolved(info.options[index])
    return one_line(text_of(entry)) if isinstance(entry, (str, bytes)) else ''


def choice_text(info: _Field) -> str:
    """The option(s) a choice field shows: an export value is shown as its display text."""
    shown = []
    for value in as_list(info.value):
        text = text_of(value)
        for option in info.options:
            option = resolved(option)
            if isinstance(option, (list, ArrayObject)) and len(option) >= 2 and text_of(option[0]) == text:
                text = text_of(option[1])
                break
        if text:
            shown.append(text)
    return canonicalize('; '.join(shown))


def value_text(value) -> str:
    value = resolved(value)
    if isinstance(value, StreamObject):  # a long or rich-text value
        try:
            return canonicalize(value.get_data().decode('utf-8', 'replace'))
        except Exception:
            return ''
    return canonicalize(text_of(value))


def rich_text(value) -> str:
    """The text of a rich-text string (/RC, XHTML): its character data, one line per block element."""
    value = resolved(value)
    if isinstance(value, StreamObject):
        try:
            value = value.get_data().decode('utf-8', 'replace')
        except Exception:
            return ''
    markup = text_of(value)
    if not markup.strip():
        return ''
    try:
        root = etree.fromstring(markup.encode('utf-8'), etree.XMLParser(resolve_entities=False, no_network=True,
                                                                        remove_comments=True, remove_pis=True))
    except etree.XMLSyntaxError:  # not well-formed: its text without the tags
        return canonicalize(_TAGS.sub('', markup)).strip('\n')
    paragraphs = [''.join(paragraph.itertext()) for paragraph in root.iter('{*}p')]
    return canonicalize('\n'.join(paragraphs) if paragraphs else ''.join(root.itertext())).strip('\n')


def normal_appearance(annotation):
    appearances = resolved(annotation.get('/AP'))
    if not isinstance(appearances, DictionaryObject):
        return None
    normal = resolved(appearances.get('/N'))
    if isinstance(normal, StreamObject):
        return normal
    if isinstance(normal, DictionaryObject):
        state = resolved(annotation.get('/AS'))
        chosen = resolved(normal.get(state)) if state is not None and state in normal else None
        return chosen if isinstance(chosen, StreamObject) else None
    return None


def is_true(value) -> bool:
    """A PDF boolean's value: pypdf's BooleanObject(False) is truthy as a Python object."""
    value = resolved(value)
    return getattr(value, 'value', value) is True


def text_of(value) -> str:
    value = resolved(value)
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode('latin-1')
    return str(value)


def one_line(text: str) -> str:
    return _WHITESPACE.sub(' ', text).strip()


def squeezed(text: str) -> str:
    return _WHITESPACE.sub('', text)
