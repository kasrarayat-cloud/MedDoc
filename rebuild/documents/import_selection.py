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


def ordinary_parity(legacy, advanced, legacy_regions, reader, *, source_roles=()):
    """A narrow NEW-import preference, requiring exact one-to-one ordinary places.

    Containment used for omission diagnosis is insufficient here. Each old cell
    must be the same complete cell; each span the same complete span. Full labels
    and their governing context must agree, without dropping an actor/instruction.
    Text and long text share the same unrestricted text answer representation.
    Other kinds, extra source rules and human-owned places keep the legacy route.
    """
    old, new = legacy['fields'], advanced['fields']
    if (not old or len(old) != len(new) or len(old) != len(legacy_regions) or source_roles
            or advanced.get('coverage_issues') or advanced.get('layout_pending')
            or any('not mapped' in note.casefold() or 'not be placed' in note.casefold()
                   for note in legacy.get('warnings',[]))):
        return False
    indexed = {}
    for field, place in zip(old,legacy_regions):
        if field.get('kind') != 'text' or place in indexed:
            return False
        indexed[place] = field
    used=set()
    for field in new:
        places=reader.of(field)
        if len(places) != 1 or places[0] not in indexed or places[0] in used:
            return False
        old_field=indexed[places[0]]
        if (field.get('kind') not in ('text','long_text') or field.get('write_protected')
                or any(field.get(key) for key in ('options','copies','source_questions','source_instructions',
                                                 'answer_policy','layout_candidate'))
                or field['label'].strip() != old_field['label'].strip()
                or field.get('context','').strip() not in ('',field['label'].strip())):
            return False
        used.add(places[0])
    return len(used)==len(indexed)


def choose(legacy, advanced, legacy_regions, reader, *, ordinary_roles=(), band_places=()):
    """Return the selected engine and explicit physical differences, including omissions.

    v3 may replace an accepted legacy import only when it preserves every legacy
    writing place. If either comparison is uncertain, legacy stays available and
    the missing coverage is reported; a v3 rejection never grants broader support.
    """
    v3_regions, missing, bands = [], [], []
    band_places = [(place, None, None) for place in band_places]
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
        elif (field.get("write_protected")
              and any(isinstance(q, dict) and q.get("relation") == "protected_inline_signing_lines"
                      for q in field.get("source_questions") or [])
              and any(not covered(place, legacy_regions) for place in locations)):
            # A drawn signing band is v3-only knowledge of the original: legacy
            # cannot see the human-owned event it protects. It selects v3 as
            # the band's old inferred (writable) date did, never a legacy hold.
            bands.append({"label": field["label"], "locator": field["locator"]})
    # Every place of a protected band (line, caption, spacer; header and
    # footer copies included) is held by v3: a legacy writer there is
    # accounted for, never "lost".
    lost = [place for place in legacy_regions if not covered(place, v3_regions + band_places)]
    unmapped = [note for note in legacy["warnings"] if "not mapped" in note.casefold()
                or "not be placed" in note.casefold()]
    # A whole empty cell from legacy may become a more precise cell/paragraph
    # writer. Preserve the legacy route when containment cannot prove parity.
    selected = "v3" if (missing or unmapped or bands) and not lost else "legacy"
    return selected, {"legacy_omissions": missing, "legacy_unmapped": unmapped,
                      "v3_only_signing_bands": bands,
                      "v3_uncovered_legacy_places": [list(place) for place in lost],
                      "block_generation": bool(selected == 'legacy' and (missing or unmapped)),
                      "automatic_complete": False,
                      "review_required": bool(missing or unmapped or lost or advanced.get("warnings"))}


def manifest(engine, fields, coverage, *, legacy_error="", v3_error=""):
    return {"strategy": STRATEGY, "engine": engine, "engine_version": ENGINE_VERSIONS[engine],
            "mapping_sha256": digest(fields), "initial_mapping_sha256": digest(fields),
            "coverage": coverage, "legacy_refusal": legacy_error, "v3_refusal": v3_error}
