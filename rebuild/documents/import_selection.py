"""Deterministic NEW-import selection; no encounter or stored mapping is reparsed here.

The comparison is of physical writing places, never field counts or question wording.
Coverage findings are evidence for mapping review, not a whole-document qualification.
"""
from __future__ import annotations

import hashlib
import json


STRATEGY = "physical-coverage-v1"
ENGINE_VERSIONS = {"legacy": "legacy-v2", "v3": "word-v3-ec3-v1"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def legacy_places(document, paragraphs, cells, fields, detector):
    """Legacy locators as original-part/slot extents understood by v3's place reader.

    Legacy-valid packages contain no content controls/text boxes/field wrappers, so
    each part's raw paragraph and cell order is the same in both readers. Any
    unexpected mismatch refuses the comparison rather than inventing coverage.
    """
    from docx.oxml.ns import qn
    try:
        from .engine import docx_parts
    except ImportError:  # isolated worker
        from engine import docx_parts
    by_element, by_paragraph = {}, {}
    for part in docx_parts(document):
        name = str(part.partname).lstrip("/")
        for kind, tag in (("p", "w:p"), ("tc", "w:tc")):
            old = list(part.element.iter(qn(tag)))
            new = [slot for slot in detector.index.slots if slot.part == name and slot.kind == kind]
            if len(old) != len(new):
                raise ValueError("Original place readers disagree.")
            for n, (element, slot) in enumerate(zip(old, new)):
                by_element[(name, element.getroottree().getpath(element))] = slot.id
                if kind == "p":
                    by_paragraph[(name, n)] = slot
    places = []
    for field in fields:
        loc = field["locator"]
        if "cell" in loc:
            cell, part = cells[loc["cell"]]
            name = str(part.partname).lstrip("/")
            places.append((by_element[(name, cell.getroottree().getpath(cell))], None, None))
        elif "paragraph" in loc:
            paragraph = paragraphs[loc["paragraph"]]
            name = str(paragraph.part.partname).lstrip("/")
            places.append((by_element[(name, paragraph._p.getroottree().getpath(paragraph._p))],
                           loc["start"], loc["end"]))
        elif "tab_form" in loc:
            for anchor in loc["tab_form"]["anchors"]:
                slot = by_paragraph[(anchor["part"], anchor["paragraph"])]
                runs = list(slot.el.findall(qn("w:r")))
                wanted = list(runs[anchor["run"]])[anchor["child"]]
                # The v3 text reader records every tab's original offset and node.
                printed, pieces = detector.ptext(slot.el)
                piece = next(piece for piece in pieces if piece.node is wanted)
                low, high = piece.start, piece.end
                while low > 0 and printed[low-1] in ' \t':
                    low -= 1
                while high < len(printed) and printed[high] in ' \t':
                    high += 1
                places.append((slot.id, low, high))
        else:
            raise ValueError("Unrecognized original locator.")
    return places


def covered(place, regions):
    slot, start, end = place
    for parent, low, high in regions:
        if low is None and (slot == parent or slot.startswith(parent + "/")):
            return True
        if slot == parent and start is not None and low is not None and low <= start and high >= end:
            return True
    return False


def choose(legacy, advanced, legacy_regions, reader, *, ordinary_roles=()):
    """Return the selected engine and explicit physical differences, including omissions.

    v3 may replace an accepted legacy import only when it preserves every legacy
    writing place. If either comparison is uncertain, legacy stays available and
    the missing coverage is reported; a v3 rejection never grants broader support.
    """
    v3_regions, missing = [], []
    for field in advanced["fields"]:
        locations = reader.of(field)
        target = field.get('locator', {}).get('target', {})
        # Destination coverage concerns the original answer area, while the
        # role reader deliberately represents after-label INSERTIONS as points.
        if target.get('type') == 'span' and target.get('shape') == 'after_label':
            locations = [(slot, target['start'], target['end']) for slot, _, _ in locations]
        v3_regions.extend(locations)
        if (not field.get("write_protected")
                and (field.get("kind") not in ("signature", "initials") or field['key'] in ordinary_roles)):
            if any(not covered(place, legacy_regions) for place in locations):
                missing.append({"label": field["label"], "locator": field["locator"]})
    lost = [place for place in legacy_regions if not covered(place, v3_regions)]
    unmapped = [note for note in legacy["warnings"] if "not mapped" in note.casefold()
                or "not be placed" in note.casefold()]
    # A whole empty cell from legacy may become a more precise cell/paragraph
    # writer. Preserve the legacy route when containment cannot prove parity.
    selected = "v3" if (missing or unmapped) and not lost else "legacy"
    return selected, {"legacy_omissions": missing, "legacy_unmapped": unmapped,
                      "v3_uncovered_legacy_places": [list(place) for place in lost],
                      "block_generation": bool(selected == 'legacy' and (missing or unmapped)),
                      "automatic_complete": False,
                      "review_required": bool(missing or unmapped or lost or advanced.get("warnings"))}


def manifest(engine, fields, coverage, *, legacy_error="", v3_error=""):
    return {"strategy": STRATEGY, "engine": engine, "engine_version": ENGINE_VERSIONS[engine],
            "mapping_sha256": digest(fields), "initial_mapping_sha256": digest(fields),
            "coverage": coverage, "legacy_refusal": legacy_error, "v3_refusal": v3_error}
