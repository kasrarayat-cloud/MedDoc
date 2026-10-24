"""What a PDF page's annotations show, for extraction (ARCHITECTURE 5.1).

A page's content stream is not all a viewer draws on it: filled form fields
(widget annotations), typed-on text (FreeText), stamps and other annotations
are drawn on top. ``read_annotations`` turns what is displayed into text
where that can be done exactly, and accounts for the rest:

- A displayed form field is read from its stored value (``/V``, inherited
  through ``/Parent``): a text field as its text, a choice field as the option
  shown, a check box as checked or not checked, a radio group as the option
  selected: with /Opt, the entry of the selected widget, by its place in the
  field's /Kids (PDF 32000-1 Table 227), else the state's name. Each
  displayed check box's rectangle and state is kept, so that its glyph can be
  written beside its label in the page text (pdf.py). Push buttons and fields without a value contribute the text their
  appearance draws. Password fields are not read.
- A text or combo-box field whose appearance draws text that differs from its
  stored value is named, because viewers differ in which one they show. An
  appearance that draws no text, or whose own /OC group is off, differs from
  a non-empty value; a field with no appearance is drawn from its value.
- A FreeText annotation is read from ``/Contents`` (else its appearance), and
  named when its appearance shows different text. One whose appearance's own
  /OC group is off shows nothing: it is not read and is counted as hidden.
  Any other annotation whose appearance draws text is read from that text;
  one whose appearance is in a hidden layer is named.
- Annotation notes that are not drawn on the page (sticky notes, comment
  text) are counted, not read, like DOCX comments; ink and stamp drawings
  without text are counted. Hidden annotations — the Hidden or NoView flag,
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

from .pdfcontent import (OptionalContent, as_list, clip, form_shows_text, number, page_box, raw_entry, resolved,
                         visible_form)
from .pdffonts import undecodable
from .text import canonicalize, non_space_count

HIDDEN_FLAGS = 2 | 32  # Hidden, NoView (PDF 32000-1 12.5.3)
FIELD_PASSWORD = 1 << 13
FIELD_RADIO = 1 << 15
FIELD_PUSH_BUTTON = 1 << 16
FIELD_COMBO = 1 << 17
MAX_PARENT_DEPTH = 32
NOT_DRAWN = frozenset({'/Popup', '/Link'})  # a popup shows its parent's note; a link draws nothing of its own
DRAWINGS = frozenset({'/Ink', '/Stamp'})
_WHITESPACE = re.compile(r'\s+')
_TAGS = re.compile(r'<[^>]*>')


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

    def block(self, page: int) -> str:
        """The labelled text added after the page's own text ('' when there is none)."""
        parts = []
        if self.fields:
            parts.append(f'[PDF form fields on page {page}]\n' + '\n'.join(self.fields))
        if self.texts:
            parts.append(f'[PDF annotation text on page {page}]\n' + '\n'.join(self.texts))
        return canonicalize('\n'.join(parts))


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


class _Reader:
    def __init__(self, page, defaults, regenerated: bool, box, optional: OptionalContent, found: PageAnnotations):
        self.page = page
        self.defaults = defaults if isinstance(defaults, DictionaryObject) else None
        self.regenerated = regenerated  # /NeedAppearances: viewers redraw fields from their values
        self.box = box
        self.optional = optional
        self.found = found
        self.lines: dict[int, int] = {}  # id(terminal field) -> index in found.fields

    def read(self, annotation) -> None:
        subtype = resolved(annotation.get('/Subtype'))
        if subtype in NOT_DRAWN:
            return
        shown = self.displayed(annotation)
        if subtype == '/Widget':
            self.widget(annotation, shown)
        elif subtype == '/FreeText':
            self.free_text(annotation, shown)
        else:
            self.other(annotation, subtype, shown)

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
            line, on = button_line(widget, info)
            if not shown:
                self.found.hidden += on
                return
            rect = rect_of(widget)
            if rect is not None:
                self.found.buttons.append(rect)
                if not info.flags & FIELD_RADIO:
                    self.found.boxes.append((rect, on))
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
            if shown and comparable and not self.regenerated and drawing and drawn != squeezed(value):
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
        if appearance is None:
            self.found.unreadable += 1
        elif appearance.strip():
            self.found.texts.append(self.clean(appearance.strip('\n')))
        elif subtype in DRAWINGS and self.drawn_appearance(annotation):
            self.found.drawn += 1

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
        stream, damaged, hidden = visible_form(stream, self.page.pdf, self.optional, self.defaults)
        self.found.hidden_text = self.found.hidden_text or hidden
        if damaged:
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
    return _Field(node=terminal, kind=inherited('/FT'), value=inherited('/V'), flags=int(number(inherited('/Ff'))),
                  options=as_list(inherited('/Opt')), label=one_line(label))


def button_line(widget, info: _Field) -> tuple[str, bool]:
    """('label: checked' | 'label: not checked', on) for a check box; the selected option for a radio group."""
    normal = resolved(resolved(widget.get('/AP')).get('/N')) \
        if isinstance(resolved(widget.get('/AP')), DictionaryObject) else None
    states = [key for key in normal if key != '/Off'] if isinstance(normal, DictionaryObject) else []
    state = resolved(widget.get('/AS'))
    if state is None and isinstance(info.value, str) and (info.value in states or not states):
        state = info.value  # no appearance state: viewers draw the box from the field's value
    on = state is not None and state != '/Off' and (not states or state in states)
    if info.flags & FIELD_RADIO:
        option = text_of(state).removeprefix('/') if on else ''
        if on and info.options:
            option = listed_option(widget, info) or option
        return (f'{info.label}: {option}' if option else f'{info.label}: no option selected'), on
    return (f'{info.label}: checked' if on else f'{info.label}: not checked'), on


def listed_option(widget, info: _Field) -> str:
    """The /Opt entry of ``widget``: one per widget, in the order of the field's /Kids (PDF 32000-1 Table 227).
    Read by position, never from a decimal state name, whose digits may be the option itself."""
    kids = as_list(info.node.get('/Kids'))
    index = next((place for place, kid in enumerate(kids) if resolved(kid) is widget), None)
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
