"""Source-only layout preparation. Imported before the document sandbox closes.

The result is a proposal, never a receipt or a claim of visible column ownership.
The renderer service recomputes it from bytes, rather than accepting client spans.
"""
import hashlib
import json
import re

if __package__:
    from . import word_v3 as w
else:
    import word_v3 as w

CONTRACT = "word-tab-layout-v1"
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


def prepare(data, *, mapping=None, answers=None):
    package = w.open_package(data)
    fonts = safety(package)
    detector = w.Detector(package, layout_proposal=True)
    areas, notes = detector.detect()
    candidates = detector.layout_candidates
    if not candidates or len(candidates) > MAX_CANDIDATES:
        w.fail("No bounded tab-column proposal is available.", "layout_unresolved")
    fields = [w.area_to_field(i + 1, area) for i, area in enumerate(areas)]
    for field in fields:
        w.annotate_printed(detector.index, field)
    w.source_policy.annotate(detector, fields)
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
        package = w.open_package(actual)
        safety(package)
        paragraph_pairs = [(resolve_path(package, r["header"]), resolve_path(package, r["row"])) for r in retained]
    else:
        paragraph_pairs = [(header.el, row.el) for header, row, _ in candidates]
    existing_names, existing_ids = set(), set()
    for part in package.content_parts():
        for node in package.tree(part).iter(w.q("w:bookmarkStart"), w.q("w:bookmarkEnd")):
            existing_names.add(node.get(w.q("w:name")))
            existing_ids.add(node.get(w.q("w:id")))
    anchors, changed = [], set()
    next_id = 0
    actual_sha = digest(actual)
    for description, (header, row) in zip(descriptions, paragraph_pairs):
        count = len(description["source"]["options"])
        for role, paragraph in (("header", header), ("row", row)):
            part = description["source"]["header" if role == "header" else "row"]["part"]
            spans = segments(paragraph)
            if len(spans) != count:
                w.fail("An export changed the complete layout segments.", "layout_unresolved")
            original = w.paragraph_text(paragraph)[0]
            expected_text = original
            points = []
            for ordinal, (start, end) in enumerate(spans):
                for edge, offset in (("start", start), ("end", end)):
                    name = "QMD" + digest(canonical([actual_sha, description["id"], role, ordinal, edge]))[:32]
                    if name in existing_names:
                        w.fail("A layout anchor name collides with an existing bookmark.", "layout_unresolved")
                    existing_names.add(name)
                    points.append((offset, name, ordinal, edge))
            for offset, name, ordinal, edge in sorted(points, reverse=True):
                w._split_at(paragraph, offset)
                before = next((p.run for p in w.paragraph_text(paragraph)[1] if p.start == offset), None)
                # Writer omits bookmarks inside smart tags. A boundary before
                # their first child is exactly the boundary before the wrapper;
                # retain the original wrapper and all of its layout behavior.
                while before is not None and before.getparent() is not paragraph:
                    parent = before.getparent()
                    if parent.tag != w.q("w:smartTag") or parent.index(before) != 0:
                        break
                    before = parent
                while str(next_id) in existing_ids:
                    next_id += 1
                identity = str(next_id); existing_ids.add(identity); next_id += 1
                begin = w._el("w:bookmarkStart"); begin.set(w.q("w:id"), identity); begin.set(w.q("w:name"), name)
                end = w._el("w:bookmarkEnd"); end.set(w.q("w:id"), identity)
                carrier = w._el("w:r")
                # A default-size invisible glyph can enlarge a smaller source
                # line. Use the minimum half-point run for instrumentation only;
                # exact PDF graphics equality remains mandatory afterwards.
                props = w._el("w:rPr")
                for tag in ("w:sz", "w:szCs"):
                    size = w._el(tag); size.set(w.q("w:val"), "1"); props.append(size)
                carrier.append(props)
                leaf = w._el("w:t"); leaf.text = "\u2060"; carrier.append(leaf)
                if before is None:
                    paragraph.extend([begin, end, carrier])
                else:
                    before.addprevious(begin); before.addprevious(end); before.addprevious(carrier)
                expected_text = expected_text[:offset] + "\u2060" + expected_text[offset:]
                anchors.append({"name": name, "candidate": description["id"], "role": role,
                                "ordinal": ordinal, "edge": edge, "offset": offset})
            after = w.paragraph_text(paragraph)[0]
            if after != expected_text:
                w.fail("Instrumentation changed source text.", "layout_unresolved")
            changed.add(part)
    if len(anchors) > MAX_ANCHORS:
        w.fail("The layout witness exceeds its anchor limit.", "layout_limit")
    instrumented = package.write({part: package.tree(part) for part in changed})
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
