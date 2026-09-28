"""Source-only layout preparation. Imported before the document sandbox closes.

The result is a proposal, never a receipt or a claim of visible column ownership.
The renderer service recomputes it from bytes, rather than accepting client spans.
"""
import hashlib
import json
import re
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


def safety(package):
    """Rendering has a narrower active-resource boundary than ordinary inspection."""
    fonts = set()
    for name in package.names:
        if name.endswith(".rels"):
            for rel in package.tree(name):
                kind = (rel.get("Type") or "").lower()
                if kind.endswith("/attachedtemplate"):
                    w.fail("Attached templates cannot be used for layout verification.", "layout_unsafe_source")
                if (rel.get("TargetMode") or "").lower() == "external" and not kind.endswith("/hyperlink"):
                    w.fail("Linked resources cannot be used for layout verification.", "layout_unsafe_source")
        if name.endswith(".xml"):
            for node in package.tree(name).iter():
                if node.tag == w.q("w:instrText") and re.search(
                        r"\b(?:INCLUDETEXT|INCLUDEPICTURE|DDE|DDEAUTO|LINK|DATABASE)\b", node.text or "", re.I):
                    w.fail("An updating resource field cannot be rendered safely.", "layout_unsafe_source")
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


def printed_key(paragraph):
    """A paragraph's printed characters with every space and tab removed and every box state merged.
    Coarser than the rendered match, so a count over it can only over-count repeats (fail closed)."""
    return re.sub(r"\s", "", w.paragraph_text(paragraph)[0]).replace(w.CHECKED, w.BOX)


def printed_stream(package):
    """Every nonempty printed paragraph of every displayed part, in document order. Text-box and
    fallback copies are included, so a repeated place is counted, never missed."""
    return [key for part in package.displayed_parts() for p in package.tree(part).iter(w.q("w:p"))
            for key in [printed_key(p)] if key]


def occurrences(stream, paragraphs):
    keys = [printed_key(p) for p in paragraphs]
    if not all(keys):
        return 0
    return sum(1 for i in range(len(stream) - len(keys) + 1) if stream[i:i + len(keys)] == keys)


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
        # The witness measures only a sequence printed once; any other place printing it is ambiguous.
        model['source_occurrences'] = occurrences(stream, nodes)
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
            "manifest_sha256": digest(canonical(manifest))}, actual, instrumented
