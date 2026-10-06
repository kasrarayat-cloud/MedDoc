"""Source-only layout preparation. Imported before the document sandbox closes.

The result is a proposal, never a receipt or a claim of visible column ownership.
The renderer service recomputes it from bytes, rather than accepting client spans.
"""
import hashlib
import json
import re
import unicodedata
from bisect import bisect_right

if __package__:
    from . import word_v3 as w
else:
    import word_v3 as w

CONTRACT = "word-tab-containment-v2"
MAX_CANDIDATES = 200
MAX_ANCHORS = 2400


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


FORM_METADATA_NS = "http://schemas.microsoft.com/sharepoint/v3/contenttype/forms"


def default_form_metadata_pi(root, part, data):
    """Only the empty marker on complete default SharePoint form metadata.

    mso-contentType also accompanies document-information-panel resource URLs;
    its target alone is not evidence of inert content. This exact schema holds
    only SharePoint's default Display/Edit/New form names, outside Word content.
    Nothing is removed or rewritten before the renderer receives the package.
    """
    if (not re.fullmatch(r"customXml/item[1-9][0-9]*\.xml", part)
            or not data.startswith(b"<?mso-contentType?>")
            or root.getroottree().docinfo.doctype
            or root.tag != "{" + FORM_METADATA_NS + "}FormTemplates"
            or root.nsmap != {None: FORM_METADATA_NS}
            or root.attrib or root.text or root.tail or root.getnext() is not None):
        return None
    marker = root.getprevious()
    if (not isinstance(marker, w.etree._ProcessingInstruction)
            or marker.target != "mso-contentType" or marker.text
            or marker.tail or marker.getprevious() is not None
            or marker.getparent() is not None or marker.getnext() is not root):
        return None
    children = list(root)
    if len(children) != 3:
        return None
    for child, name in zip(children, ("Display", "Edit", "New")):
        if (child.tag != "{" + FORM_METADATA_NS + "}" + name or child.attrib
                or len(child) or child.text != "DocumentLibraryForm" or child.tail
                or child.nsmap != {None: FORM_METADATA_NS}):
            return None
    return marker


def source_elements(root, *, part="", data=b""):
    """Element nodes after checking the complete parsed XML document."""
    inert_marker = default_form_metadata_pi(root, part, data)
    first = root
    while first.getprevious() is not None:
        first = first.getprevious()
    while first is not None:
        # iter() alone excludes a root's prolog and epilog siblings.
        for node in first.iter():
            if isinstance(node.tag, str):
                yield node
            elif node is not inert_marker and not isinstance(node, w.etree._Comment):
                w.fail("XML processing instructions and unknown node types cannot use layout verification.",
                       "layout_unsafe_source")
        first = first.getnext()


UPDATING_RESOURCE_FIELD = re.compile(r"\b(?:INCLUDETEXT|INCLUDEPICTURE|DDE|DDEAUTO|LINK|DATABASE)\b", re.I)


def check_field_instruction(text):
    if UPDATING_RESOURCE_FIELD.search(text):
        w.fail("An updating resource field cannot be rendered safely.", "layout_unsafe_source")


def safety(package):
    """Rendering has a narrower active-resource boundary than ordinary inspection."""
    fonts = set()
    for name in package.names:
        if name.endswith(".rels"):
            for rel in source_elements(package.tree(name)):
                kind = (rel.get("Type") or "").lower()
                if kind.endswith("/attachedtemplate"):
                    w.fail("Attached templates cannot be used for layout verification.", "layout_unsafe_source")
                if (rel.get("TargetMode") or "").lower() == "external" and not kind.endswith("/hyperlink"):
                    w.fail("Linked resources cannot be used for layout verification.", "layout_unsafe_source")
        if name.endswith(".xml"):
            instructions = []
            for node in source_elements(package.tree(name), part=name, data=package.zip.read(name)):
                if node.tag == w.q("w:fldSimple"):
                    check_field_instruction(node.get(w.q("w:instr")) or "")
                if node.tag == w.q("w:fldChar"):
                    kind = node.get(w.q("w:fldCharType"))
                    if kind == "begin":
                        instructions.append({"parts": [], "reading": True})
                    elif kind in ("separate", "end") and instructions:
                        check_field_instruction("".join(instructions[-1]["parts"]))
                        if kind == "end":
                            instructions.pop()
                        else:
                            instructions[-1]["reading"] = False
                if node.tag == w.q("w:instrText"):
                    # Comments do not contribute characters; their tails do.
                    text = "".join(node.itertext())
                    check_field_instruction(text)
                    if instructions and instructions[-1]["reading"]:
                        instructions[-1]["parts"].append(text)
                if node.tag == w.q("w:rFonts"):
                    fonts.update(node.get(w.q("w:" + key)) for key in ("ascii", "hAnsi", "eastAsia", "cs")
                                 if node.get(w.q("w:" + key)))
                if node.tag in {w.q('w:embedRegular'), w.q('w:embedBold'), w.q('w:embedItalic'), w.q('w:embedBoldItalic')}:
                    w.fail('Embedded font programs cannot use the pinned layout profile.', 'layout_unsafe_source')
                # Theme typefaces are included even when an unused script is
                # present; a profile may conservatively refuse an unknown font.
                if node.tag.startswith("{http://schemas.openxmlformats.org/drawingml/2006/main}"):
                    if node.get("typeface"):
                        fonts.add(node.get("typeface"))
            for instruction in instructions:
                check_field_instruction("".join(instruction["parts"]))
    if len(fonts) > 200 or any(len(font) > 200 or any(ord(c) < 32 for c in font) for font in fonts):
        w.fail("The source font profile exceeds its bounded format.", "layout_unsafe_source")
    return sorted(fonts)


def resolve_path(package, reference):
    node = package.tree(reference["part"])
    for tag, index in reference["path"]:
        if not isinstance(tag, str) or type(index) is not int or index < 0:
            w.fail("Invalid retained layout identity.", "mapping_mismatch")
        matches = node.findall(tag)
        if index >= len(matches):
            w.fail("A retained layout source is unavailable.", "mapping_mismatch")
        node = matches[index]
    if node.tag != w.q("w:p"):
        w.fail("A layout identity is not a paragraph.", "mapping_mismatch")
    return node


def segments(paragraph):
    text = w.paragraph_text(paragraph)[0]
    offset, result = 0, []
    for ordinal, segment in enumerate(text.rstrip(" \t").split("\t")):
        if ordinal:
            start = offset + len(segment) - len(segment.lstrip())
            end = offset + len(segment.rstrip())
            if start >= end:
                w.fail("A layout segment is empty.", "layout_unresolved")
            result.append((start, end))
        offset += len(segment) + 1
    return result


def rendered_paragraph(paragraph):
    """Complete printed paragraph, with native fields retaining typed identity."""
    text, pieces = w.paragraph_text(paragraph)
    result = [[]]
    for piece in pieces:
        if piece.kind == 'tab':
            result.append([]); continue
        if piece.kind == 'obj':
            if piece.obj == 'ff_checkbox':
                state = w.ff_checkbox_state(piece.node)
                if type(state) is not bool: w.fail('Unknown native checkbox state.', 'layout_unresolved')
                item = {'kind':'ff_checkbox','text':'\ufffc','checked':state}
            elif piece.obj == 'sdt_checkbox':
                state = w.sdt_checkbox_state(piece.node)
                if type(state) is not bool: w.fail('Unknown native checkbox state.', 'layout_unresolved')
                item = {'kind':'glyph','text':'☒' if state else '☐'}
            else: w.fail('Unsupported object in visible tab paragraph.', 'layout_unresolved')
        elif piece.kind in ('t','sym'):
            item = {'kind':'glyph','text':w.piece_text(piece)}
        else: w.fail('Wrapped visible tab paragraph is unresolved.', 'layout_unresolved')
        result[-1].append(item)
    # Tabs after the complete last segment do not create an answer column.
    while result and not result[-1]: result.pop()
    for segment in result:
        if segment:
            segment[0]['text'] = segment[0]['text'].lstrip()
            segment[-1]['text'] = segment[-1]['text'].rstrip()
    return result


def rendered_columns(paragraph, starts):
    """Partition all printed characters at source code/header boundaries.

    Literal spaces remain part of the complete match. Tabs have no printed
    character; their geometry still comes solely from the unchanged PDF.
    """
    text, pieces = w.paragraph_text(paragraph)
    if (not starts or starts[0] != 0 or sorted(set(starts)) != starts
            or any(type(n) is not int or n < 0 or n > len(text) for n in starts)):
        w.fail('Invalid complete column partition.', 'layout_unresolved')
    result = [[] for _ in starts]
    for piece in pieces:
        if piece.kind == 'tab':
            continue
        if piece.kind == 'obj':
            if piece.obj == 'ff_checkbox':
                state = w.ff_checkbox_state(piece.node)
                if type(state) is not bool: w.fail('Unknown native checkbox state.', 'layout_unresolved')
                item = {'kind': 'ff_checkbox', 'text': '\ufffc', 'checked': state}
            elif piece.obj == 'sdt_checkbox':
                state = w.sdt_checkbox_state(piece.node)
                if type(state) is not bool: w.fail('Unknown content-control state.', 'layout_unresolved')
                item = {'kind': 'glyph', 'text': '☒' if state else '☐'}
            else: w.fail('Unresolved object in complete source sequence.', 'layout_unresolved')
        elif piece.kind in ('t', 'sym'):
            item = {'kind': 'glyph', 'text': w.piece_text(piece)}
        else: w.fail('Unresolved source sequence piece.', 'layout_unresolved')
        if len(item['text']) != piece.end - piece.start:
            w.fail('A printed source piece changed length.', 'layout_unresolved')
        for offset, char in enumerate(item['text'], piece.start):
            if offset >= len(text.rstrip(' \t')):
                continue
            result[bisect_right(starts, offset) - 1].append(dict(item, text=char))
    return result


HIDE = ("w:vanish", "w:specVanish", "w:webHidden")


def unprinted(char):
    """A character that prints nothing by itself: format controls (soft hyphen, zero-width space, word
    joiner, bidirectional marks, ...), control characters and the other default-ignorable code points."""
    code = ord(char)
    return (unicodedata.category(char) in ("Cf", "Cc") or code in (0x034F, 0x115F, 0x1160, 0x3164, 0xFFA0)
            or 0x180B <= code <= 0x180F or 0xFE00 <= code <= 0xFE0F or 0xE0000 <= code <= 0xE0FFF)


class Printed:
    """What a paragraph can print, as a coarse key for counting places that print the same text.

    Every space, every character that prints nothing and every run that may be hidden (directly, by its
    character style, its paragraph style or the document defaults) is removed, letters are case-folded
    (capitals may come from formatting) and box states are merged. This removes the known ways a source
    character prints nothing; it is not a proof that the key equals what prints (a field the renderer
    recomputes, or text a table style hides, is not modelled). A count over it can still under-count, so
    the rendered witness also refuses a sequence the rendering paints twice (layout_geometry.rendered_elsewhere)."""

    def __init__(self, package):
        styles = package.tree("word/styles.xml") if "word/styles.xml" in package.names else None
        self.styles = {} if styles is None else {s.get(w.q("w:styleId")): s for s in styles.findall(w.q("w:style"))}
        defaults = None if styles is None else styles.find(w.q("w:docDefaults") + "/" + w.q("w:rPrDefault"))
        self.everything = self.hides(defaults)
        default = lambda kind: next((s.get(w.q("w:styleId")) for s in self.styles.values()
                                     if s.get(w.q("w:type")) == kind and s.get(w.q("w:default")) in ("1", "true", "on")), None)
        self.default_paragraph, self.default_character = default("paragraph"), default("character")
        self._style = {}

    @staticmethod
    def hides(node):
        return node is not None and any(n.tag in {w.q(t) for t in HIDE}
                                        and (n.get(w.q("w:val")) or "1").lower() not in ("0", "false", "off")
                                        for n in node.iter())

    def style_hides(self, name):
        """A style (with everything it is based on) that may hide text; an unknown or cyclic one may."""
        if name not in self._style:
            self._style[name] = True  # a cycle through this style resolves as hiding
            style = self.styles.get(name)
            if style is None:
                result = name is not None
            else:
                based = style.find(w.q("w:basedOn"))
                result = self.hides(style.find(w.q("w:rPr"))) or (based is not None and self.style_hides(based.get(w.q("w:val"))))
            self._style[name] = result
        return self._style[name]

    def run_hidden(self, run):
        props = run.find(w.q("w:rPr"))
        style = props.find(w.q("w:rStyle")) if props is not None else None
        name = style.get(w.q("w:val")) if style is not None else self.default_character
        return self.hides(props) or (name is not None and self.style_hides(name))

    def key(self, paragraph):
        props = paragraph.find(w.q("w:pPr"))
        style = props.find(w.q("w:pStyle")) if props is not None else None
        name = style.get(w.q("w:val")) if style is not None else self.default_paragraph
        if self.everything or (name is not None and self.style_hides(name)):
            return ""
        text, pieces = w.paragraph_text(paragraph)
        kept = "".join(text[piece.start:piece.end] for piece in pieces
                       if piece.run is None or not self.run_hidden(piece.run))
        return "".join(c for c in kept.casefold() if not c.isspace() and not unprinted(c)).replace(w.CHECKED, w.BOX)


def printed_stream(package):
    """Every nonempty printed paragraph of every displayed part, in document order. Text-box and
    fallback copies are included, so a repeated place is counted, never missed."""
    printed = Printed(package)
    return printed, [key for part in package.displayed_parts() for p in package.tree(part).iter(w.q("w:p"))
                     for key in [printed.key(p)] if key]


def occurrences(stream, paragraphs):
    printed, keys = stream[0], [stream[0].key(p) for p in paragraphs]
    if not all(keys):
        return 0
    stream = stream[1]
    return sum(1 for i in range(len(stream) - len(keys) + 1) if stream[i:i + len(keys)] == keys)


def distinct_cell_sequence(stream, nodes, model):
    """A duplicate coded row needs its own preceding printed cell source.

    Keep the stored destination unchanged. Add only the physical prefix of the
    same already validated coded cell; the PDF must still prove its complete,
    unique, contiguous rendering. A duplicate complete cell remains ambiguous.
    """
    short_occurrences = occurrences(stream, nodes)
    if short_occurrences <= 1 or not nodes:
        return nodes, model
    parent = nodes[0].getparent()
    if parent is None or parent.tag != w.q('w:tc') or any(node.getparent() is not parent for node in nodes):
        return nodes, model
    children = list(parent); at = children.index(nodes[0])
    prefix = children[:at]
    if any(node.tag not in (w.q('w:tcPr'), w.q('w:p')) for node in prefix):
        return nodes, model
    prefix = [p for p in prefix if p.tag == w.q('w:p') and w.paragraph_text(p)[0].strip()]
    if not prefix or len(prefix) + len(nodes) > 100:
        return nodes, model
    # These paragraphs belong to the detector's complete coded-cell source,
    # not to a neighbouring cell or a title inferred from a mutable field.
    additions = [{'segments': rendered_columns(p, [0]),
                  'dot_leaders': any(n.get(w.q('w:leader')) == 'dot'
                      for n in p.findall('.//' + w.q('w:tabs') + '/' + w.q('w:tab')))} for p in prefix]
    result = dict(model, sequence=additions + model['sequence'], header_index=len(prefix) + model['header_index'],
                  short_source_occurrences=short_occurrences)
    return prefix + nodes, result


def rendered_characters(paragraph):
    """The characters a paragraph renders, as the witness reads them: a native checkbox is one vector
    control, a checkbox content control its state glyph; spaces are removed."""
    text, pieces = w.paragraph_text(paragraph)
    out = []
    for piece in pieces:
        if piece.kind == "obj":
            if piece.obj == "ff_checkbox":
                out.append("\ufffc")
            elif piece.obj == "sdt_checkbox":
                out.append(w.CHECKED if w.sdt_checkbox_state(piece.node) is True else w.BOX)
        elif piece.kind in ("t", "sym"):
            out.append(w.piece_text(piece))
    return "".join("".join(out).split())


def neighbours(paragraph):
    """What the other cells of the paragraph's table row print, left and right of its own cell. Text
    written beside an answered row shares its baselines; only this text may (layout_geometry.match_line)."""
    cell = next(paragraph.iterancestors(w.q("w:tc")), None)
    row = next(cell.iterancestors(w.q("w:tr")), None) if cell is not None else None
    if row is None:
        return {"left": "", "right": ""}
    cells = w.row_cells_of(row)
    at = next(i for i, c in enumerate(cells) if c is cell)
    text = lambda group: "".join(rendered_characters(p) for c in group for p in c.iter(w.q("w:p")))
    return {"left": text(cells[:at]), "right": text(cells[at + 1:])}


def touched_destinations(mapping, answers):
    """Every (part, slot) that an answered mapping field may write, including its boxes."""
    result = []
    for field in mapping:
        if answers.get(field.get("key")) in (None, "", []):
            continue
        loc = field.get("locator") or {}
        target = loc.get("target") or {}
        refs = [loc] + list(loc.get("extra", [])) + list(target.get("copies", [])) + list(target.get("boxes", []))
        refs += [{"part": anchor.get("part"), "slot": path}
                 for anchor in [loc] + list(target.get("copies", [])) for path in target.get("paragraphs", [])]
        if target.get("type") == "table_rows":
            refs.append({"part": loc.get("part"), "slot": target.get("table")})
        result.extend((str(ref.get("part")), str(ref.get("slot"))) for ref in refs)
    return result


def overlaps(a, b):
    """One slot is the other, contains it or lies inside it."""
    return a[0] == b[0] and (a[1] == b[1] or a[1].startswith(b[1] + "/") or b[1].startswith(a[1] + "/"))


def prepare(data, *, mapping=None, answers=None):
    package = w.open_package(data)
    fonts = safety(package)
    detector = w.Detector(package, layout_proposal=True)
    areas, notes = detector.detect()
    candidates = detector.layout_candidates
    if not candidates or len(candidates) > MAX_CANDIDATES:
        w.fail("No bounded tab-column proposal is available.", "layout_unresolved")
    fields = w.mapped_fields(detector, areas)
    descriptions = []
    for header, row, area in candidates:
        field = next((f for f in fields if f["locator"]["part"] == row.part
                      and f["locator"]["slot"] == row.path), None)
        if field is None or area not in areas:
            w.fail("A tab proposal was not preserved by complete mapping validation.", "layout_unresolved")
        source = {"header": {"part": header.part, "slot": header.path, "fingerprint": w.fingerprint(header.el)},
                  "row": field["locator"], "options": field["options"], "kind": field["kind"],
                  "label": field["label"], "context": field["context"]}
        identity = digest(canonical(source))
        field["layout_candidate"] = identity
        descriptions.append({"id": identity, "source": source, "field_key": field["key"]})
    actual = data
    if mapping is not None:
        if not isinstance(mapping, list) or not isinstance(answers, dict):
            w.fail("Invalid layout export request.", "layout_unresolved")
        # Any mapped tab destination must match its source. Constraint readers
        # may supply a subset; every original tab row is still rendered below.
        # Removing metadata cannot opt the original out of verification.
        for description in descriptions:
            expected = next(f for f in fields if f.get("layout_candidate") == description["id"])
            found = [f for f in mapping if f.get("locator") == expected["locator"]]
            if len(found) > 1 or (found and any(found[0].get(k) != expected.get(k)
                                      for k in ("label", "context", "kind", "options"))):
                w.fail("A tab-column mapping changed; verify its complete source again.", "mapping_mismatch")
        retained = []
        actual = w.fill(data, mapping, answers, retained_layout=retained)
        if len(retained) != len(candidates):
            w.fail("The export lost a source layout identity.", "mapping_mismatch")
        if not any(value not in (None, '', []) for value in answers.values()):
            actual = data  # Validation above still runs; an empty review need not repack the original ZIP.
        package = w.open_package(actual)
        safety(package)
        paragraph_pairs = [(resolve_path(package, r["header"]), resolve_path(package, r["row"])) for r in retained]
        sequences = [[resolve_path(package, ref) for ref in r.get('sequence', [])] for r in retained]
    else:
        paragraph_pairs = [(header.el, row.el) for header, row, _ in candidates]
        sequences = [[detector.index.by_id[ref['part'] + '#' + ref['slot']].el
                      for ref in area.target.get('column_sequence', {}).get('source', [])]
                     for _, _, area in candidates]
    written = touched_destinations(mapping, answers) if mapping is not None else []
    stream = printed_stream(package)  # the package that is rendered: the original, or the export
    for description, (header, row), sequence in zip(descriptions, paragraph_pairs, sequences):
        relation = description['source']['row']['target'].get('column_sequence')
        if relation:
            at = relation.get('header_index')
            if (len(sequence) != len(relation['source']) or len(sequence) < 2 or type(at) is not int
                    or not 0 <= at < len(sequence) - 1):
                w.fail('Incomplete retained printed source sequence.', 'mapping_mismatch')
            model = {'sequence': [{'segments': rendered_columns(p, ref['starts']),
                                   'dot_leaders': any(n.get(w.q('w:leader')) == 'dot'
                                       for n in p.findall('.//' + w.q('w:tabs') + '/' + w.q('w:tab')))}
                                  for p, ref in zip(sequence, relation['source'])],
                     'header_index': at, 'row_dot_leaders': False}
            model['header'] = model['sequence'][at]['segments']
            model['row'] = model['sequence'][-1]['segments']
            nodes = sequence
            sources = [(ref['part'], ref['slot'], ref['fingerprint']) for ref in relation['source']]
        else:
            model = {'header':rendered_paragraph(header), 'row':rendered_paragraph(row),
                     'row_dot_leaders':any(n.get(w.q('w:leader')) == 'dot' for n in row.findall('.//' + w.q('w:tabs') + '/' + w.q('w:tab')))}
            nodes = [header, row]
            sources = [(description['source'][k]['part'], description['source'][k]['slot'],
                        description['source'][k]['fingerprint']) for k in ('header', 'row')]
        if len(model['header']) != len(description['source']['options']) + 1 or len(model['row']) != len(model['header']):
            w.fail('A complete printed tab relation changed.', 'layout_unresolved')
        # A repeated short coded row can be identified only by its complete
        # own-cell printed prefix. Neither source nor PDF uniqueness is waived.
        if relation:
            nodes, model = distinct_cell_sequence(stream, nodes, model)
        model['source_occurrences'] = occurrences(stream, nodes)
        model['neighbours'] = neighbours(nodes[-1])
        description['rendered_source'] = model
        # Only a coded-column sequence is a separately holdable proposal, and only
        # while this export leaves its own answer row byte-identical and unanswered
        # (earlier rows of its printed sequence are other questions and may be).
        # A held proposal never publishes its destination.
        part, slot, fp = sources[-1]
        description['optional'] = bool(relation)
        description['untouched'] = (w.fingerprint(nodes[-1]) == fp
                                    and not any(overlaps(destination, (part, slot)) for destination in written))
    # V2 uses unique original-text alignment. It introduces no annotation glyphs,
    # run splits or bookmarks; both independently rendered packages stay exact.
    anchors = []
    actual_sha = digest(actual)
    instrumented = actual
    manifest = {"contract": CONTRACT, "source_sha256": digest(data), "document_sha256": actual_sha,
                "instrumented_sha256": digest(instrumented), "mapping_sha256": digest(canonical(mapping)) if mapping is not None else "",
                "answers_sha256": digest(canonical(answers)) if mapping is not None else "",
                "candidates": descriptions, "anchors": anchors, "requested_fonts": fonts}
    states = None
    if mapping is not None:
        constrained = [field for field in mapping if field.get("kind") in
                       ("choice", "multi_choice", "checkbox", "text", "long_text", "date", "time")]
        keys = {field["key"] for field in constrained}
        states = w.effective_values(data, constrained, {k: v for k, v in answers.items() if k in keys},
                                   _written=actual) if constrained else {}
    return {"manifest": manifest, "fields": fields, "warnings": notes, "states": states,
            "coverage_issues": detector.coverage_issues,
            "manifest_sha256": digest(canonical(manifest))}, actual, instrumented
