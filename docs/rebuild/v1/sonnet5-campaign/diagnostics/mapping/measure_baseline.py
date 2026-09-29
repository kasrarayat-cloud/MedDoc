"""Pre-model baseline: what the candidate's DETERMINISTIC mapping already gets right / wrong / misses.

Runs the candidate engine only to MEASURE, on the synthetic forms from build_forms.py, through two paths:

    inspect          documents.word_v3.inspect(data)                       (no layout proposal)
    layout_proposal  Detector(open_package(data), layout_proposal=True).detect() -> mapped_fields(...)

and grades each path against the INDEPENDENT expected maps (*.expected.json), which must be byte-identical to the
manifest EXPECTED-SHA256SUMS frozen before this script first ran. Grading rules are fixed in GRADING below and
repeated into the output so the result can be re-derived.

    python -B measure_baseline.py [--forms DIR] [--out baseline-deterministic.json]

Sockets are denied in-process before the engine is imported (a positive control proves the denial works). No
provider, no model, no database, no Django settings, no fill/export. Nothing is written except --out.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[5]
REBUILD = WORKTREE / "rebuild"
DEFAULT_FORMS = Path("/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics/mapping")
FORMS = ["f1-guidance-confirmation", "f2-leave-checkboxes", "f2b-leave-checkboxes-owner", "f3-selection-instructions",
         "f4-exam-grid", "f5-negative-controls", "f6a-long-answer", "f6b-admin-missing"]


# ─── network denial, before anything else is imported ─────────────────────────────────────────────────────────
class _DeniedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        raise PermissionError("network denied by measure_baseline.py")


def _denied(*args, **kwargs):
    raise PermissionError("network denied by measure_baseline.py")


socket.socket = _DeniedSocket
socket.create_connection = _denied
socket.getaddrinfo = _denied
socket.socketpair = _denied


def network_positive_control() -> str:
    try:
        socket.create_connection(("127.0.0.1", 9))
    except PermissionError:
        pass
    else:
        return "FAILED: create_connection was not denied"
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError:
        return "denied (socket() and create_connection() both raised PermissionError before the engine import)"
    return "FAILED: socket() was not denied"


# ─── grading rules, declared before the first run ─────────────────────────────────────────────────────────────
GRADING = {
    "coverage": ("An engine field COVERS an expected option area when any of its box refs is one of the area's "
                 "controls (a 'cell' box ref covers every expected control inside that cell). It covers a text area "
                 "when its locator slot equals the area's region or lies inside it, or when it is a table_rows field "
                 "whose table/rows/columns include the area's cell."),
    "accepted_engine_kinds": {"text": ["text", "long_text"], "long_text": ["long_text", "text"],
                              "measurement": ["text", "long_text"], "date": ["date"], "choice": ["choice"],
                              "multi_choice": ["multi_choice"], "checkbox": ["checkbox"],
                              "table_group member": ["table_rows (one field for the whole group)"]},
    "area_right": ("Exactly one covering field; accepted kind; answerable (not write_protected, not signature/"
                   "initials); for option areas: its box refs are exactly the expected controls in the expected "
                   "order and its printed options equal the expected options verbatim (whitespace runs as one space) "
                   "in that order, and no option is a response code the map forbids; for text areas: no options, and "
                   "an anchor at the answer paragraph or at the region cell; every must_name token appears in "
                   "label+context and no must_not_name token appears in the label (in label AND context when the "
                   "map says must_not_name_scope=label_and_context; added 2026-09-29, CHECK.md M6); guidance/instruction preserved "
                   "(target type cell_append, cell_replace with all=true, or paragraph/span anchored on the answer "
                   "paragraph; a plain 'cell' or 'cell_replace' target rewrites the first paragraph and so fails "
                   "wherever the map lists preserved text in that cell); max_chars absent or >= min_capacity_chars."),
    "area_wrong": "Covered, but any area_right condition fails, or the covering field also covers another area.",
    "area_missed": ("No covering field. 'held_safe' instead of 'missed' when the map declares if_held="
                    "safe_usefulness_loss. Notes naming the area's slots are quoted as evidence."),
    "not_an_answer": "right iff no answerable field is anchored in the region(s).",
    "must_refuse": ("right iff every field covering the controls/region is write_protected or of kind signature/"
                    "initials (or there is none). Relational (applies_to): right iff no single field covers two of "
                    "the areas and every covering field names its own side and not the other."),
    "must_hold": "right iff no answerable field covers any of the controls (a hold); wrong otherwise.",
    "extra": "An answerable field that covers no expected area and is anchored in no control's region/controls.",
}
PROTECTIVE_KINDS = {"signature", "initials"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ws(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def inside(slot: str, region: str) -> bool:
    return slot == region or slot.startswith(region + "/")


# ─── normalising engine fields ────────────────────────────────────────────────────────────────────────────────
def box_keys(target) -> list:
    keys = []
    for ref in target.get("boxes") or []:
        kind, slot = ref.get("kind"), ref.get("slot", "")
        if kind == "glyph":
            keys.append("%s#%d" % (slot, int(ref.get("glyph", 0))))
        elif kind in ("cell", "cell_text"):
            keys.append("%s:%s" % (kind, slot))
        else:
            keys.append(slot)
    return keys


def summarise(field) -> dict:
    loc = field.get("locator") or {}
    target = loc.get("target") or {}
    out = {"key": field.get("key"), "label": field.get("label"), "kind": field.get("kind"),
           "context": field.get("context", ""), "options": field.get("options") or [],
           "printed_options": list(target.get("printed") or field.get("options") or []),
           "target_type": target.get("type"), "slot": loc.get("slot"), "boxes": box_keys(target),
           "write_protected": bool(field.get("write_protected")), "review_reason": field.get("review_reason", "")}
    if field.get("max_chars"):
        out["max_chars"] = field["max_chars"]
    if target.get("type") == "table_rows":
        out["table"] = {"table": target.get("table"), "rows": target.get("rows"), "columns": target.get("columns")}
    if target.get("type") == "cell_replace" and target.get("all"):
        out["all"] = True
    if field.get("source_questions"):
        out["source_questions"] = field["source_questions"]
    return out


def answerable(f) -> bool:
    return not f["write_protected"] and f["kind"] not in PROTECTIVE_KINDS


def box_covers(key: str, control: str) -> bool:
    if key.startswith("cell:") or key.startswith("cell_text:"):
        return inside(control.split("#")[0], key.split(":", 1)[1])
    return key == control


CELL = re.compile(r"^(?P<table>.+/tbl\[\d+\])/tr\[(?P<row>\d+)\]/tc\[(?P<col>\d+)\]$")


def covers_area(f, area) -> bool:
    dest = area.get("destination") or {}
    controls = dest.get("controls") or []
    if controls:
        return any(box_covers(k, c) for k in f["boxes"] for c in controls)
    region = dest.get("region")
    if not region:
        return False
    if f["target_type"] == "table_rows" and f.get("table"):
        m = CELL.match(region)
        t = f["table"]
        return bool(m and m["table"] == t["table"] and int(m["row"]) in (t["rows"] or [])
                    and int(m["col"]) in (t["columns"] or []))
    return bool(f["slot"]) and inside(f["slot"], region)


def anchored_in(f, region) -> bool:
    return bool(f["slot"]) and inside(f["slot"], region)


def notes_about(notes, slots) -> list:
    hits = []
    for note in notes:
        if any(s and s in note for s in slots):
            hits.append(note[:300])
    return hits


def area_slots(area) -> list:
    dest = area.get("destination") or {}
    slots = list(dest.get("controls") or [])
    slots = [s.split("#")[0] for s in slots]
    slots += [s.rsplit("/", 1)[0] for s in slots if "/ff[" in s or "/sdt[" in s or s.endswith("/glyphs")]
    for key in ("region", "answer_at", "label_slot"):
        if dest.get(key):
            slots.append(dest[key])
    slots += list(dest.get("regions") or [])
    return sorted(set(slots))


# ─── grading ──────────────────────────────────────────────────────────────────────────────────────────────────
def grade_area(area, fields, all_areas, groups, notes):
    dest = area.get("destination") or {}
    covering = [f for f in fields if covers_area(f, area)]
    result = {"id": area["id"], "label": area["label"], "expected_kind": area["kind"]}
    if not covering:
        result["outcome"] = "held_safe" if area.get("if_held") == "safe_usefulness_loss" else "missed"
        ev = notes_about(notes, area_slots(area))
        if ev:
            result["notes_evidence"] = ev
        return result
    result["fields"] = [{k: f[k] for k in ("key", "label", "kind", "target_type", "slot", "options",
                                           "write_protected") if k in f} for f in covering]
    problems = []
    if len(covering) > 1:
        problems.append("split across %d fields" % len(covering))
    f = covering[0]
    others = [a["id"] for a in all_areas if a is not area and covers_area(f, a)]
    group = area.get("table_group")
    if others and not (group and f["target_type"] == "table_rows"):
        problems.append("the field also covers " + ", ".join(others))
    accepted = set(GRADING["accepted_engine_kinds"][area["kind"]])
    if group and f["target_type"] == "table_rows":
        eq = groups[group]["equivalent_representation"]
        t = f.get("table") or {}
        if t.get("table") != eq["table"] or sorted(t.get("columns") or []) != eq["columns"] \
                or sorted(t.get("rows") or []) != eq["rows"]:
            problems.append("table_rows over a different table/rows/columns: %s" % t)
    elif f["kind"] not in accepted:
        problems.append("kind %s, expected %s (accepted %s)" % (f["kind"], area["kind"], sorted(accepted)))
    if not answerable(f):
        problems.append("not answerable (write_protected=%s, kind=%s, reason=%r)" % (f["write_protected"], f["kind"],
                                                                                      f["review_reason"][:120]))
    controls = dest.get("controls") or []
    label_ctx = (f["label"] or "") + " " + (f["context"] or "")
    if group and f["target_type"] == "table_rows":
        # a repeating-rows field names each column by its printed header, carried as the field's options
        m = CELL.match(dest.get("region", ""))
        cols = (f.get("table") or {}).get("columns") or []
        if m and int(m["col"]) in cols and cols.index(int(m["col"])) < len(f["options"]):
            label_ctx += " " + f["options"][cols.index(int(m["col"]))]
    if controls:
        keys = f["boxes"]
        expanded = []
        for k in keys:
            expanded += [c for c in controls if box_covers(k, c)] if (k.startswith("cell")) else [k]
        if expanded != controls:
            problems.append("box refs %s, expected %s" % (keys, controls))
        printed = [ws(o) for o in f["printed_options"]]
        if printed != [ws(o) for o in area.get("options", [])]:
            problems.append("options %s, expected %s" % (printed, area.get("options")))
        bad = [o for o in printed if o in set(area.get("options_must_not_include") or [])]
        if bad:
            problems.append("response codes offered as options: %s" % bad)
    else:
        if f["options"] and f["target_type"] != "table_rows":
            problems.append("a text area offered with options %s" % f["options"])
        answer_at = dest.get("answer_at")
        tt = f["target_type"]
        preserve = dest.get("preserve") or {}
        if tt in ("paragraph", "span"):
            if answer_at and not inside(f["slot"], answer_at):
                problems.append("anchored at %s, expected the answer paragraph %s" % (f["slot"], answer_at))
            if any(inside(f["slot"], p) for p in preserve):
                problems.append("anchored on preserved text at %s" % f["slot"])
        elif tt in ("cell", "cell_replace") and not f.get("all"):
            region = dest.get("region", "")
            first = region + "/p[0]"
            if first in preserve:
                problems.append("target %s rewrites the first paragraph, which holds preserved text %r" %
                                (tt, preserve[first][:60]))
        elif tt not in ("cell_append", "cell_replace", "table_rows", "sdt_text", "ff_text"):
            problems.append("unexpected target type %s for a text area" % tt)
    for token in area.get("must_name") or []:
        if token.lower() not in label_ctx.lower():
            problems.append("label/context does not name %r" % token)
    scope = area.get("must_not_name_scope", "label")
    named = (f["label"] or "") + (" " + (f["context"] or "") if scope == "label_and_context" else "")
    for token in area.get("must_not_name") or []:
        if re.search(r"\b%s\b" % re.escape(token.lower()), named.lower()):
            problems.append(("label/context" if scope == "label_and_context" else "label") + " names %r" % token)
    need = area.get("min_capacity_chars")
    if need and f.get("max_chars") and f["max_chars"] < need:
        problems.append("max_chars %s < %s" % (f["max_chars"], need))
    result["outcome"] = "wrong" if problems else "right"
    if problems:
        result["problems"] = problems
    return result


def grade_control(control, fields, areas_by_id, notes):
    dest = control.get("destination") or {}
    out = {"id": control["id"], "type": control["type"], "printed": control.get("printed", "")[:120]}
    regions = ([dest["region"]] if dest.get("region") else []) + list(dest.get("regions") or [])
    controls = dest.get("controls") or []
    ctype = control["type"]
    if ctype == "not_an_answer":
        hits = [f for f in fields if answerable(f) and any(anchored_in(f, r) for r in regions)]
    elif control.get("applies_to"):
        ids = control["applies_to"]
        covering = {i: [f for f in fields if covers_area(f, areas_by_id[i])] for i in ids}
        problems = []
        seen = {}
        for i, fs in covering.items():
            for f in fs:
                if f["key"] in seen and seen[f["key"]] != i:
                    problems.append("field %s covers both %s and %s" % (f["key"], seen[f["key"]], i))
                seen[f["key"]] = i
                area = areas_by_id[i]
                for token in area.get("must_name") or []:
                    if token.lower() not in ((f["label"] or "") + " " + (f["context"] or "")).lower():
                        problems.append("%s label %r lacks its side %r" % (i, f["label"], token))
                for token in area.get("must_not_name") or []:
                    if re.search(r"\b%s\b" % re.escape(token.lower()), (f["label"] or "").lower()):
                        problems.append("%s label %r names the other side %r" % (i, f["label"], token))
        out["outcome"] = "wrong" if problems else "right"
        if problems:
            out["problems"] = problems
        out["fields"] = {i: [f["key"] + " " + repr(f["label"]) for f in fs] for i, fs in covering.items()}
        return out
    else:
        covering = [f for f in fields
                    if any(box_covers(k, c) for k in f["boxes"] for c in controls)
                    or any(anchored_in(f, r) for r in regions)]
        if ctype == "must_refuse":
            hits = [f for f in covering if answerable(f)]
            out["protected_fields"] = [f["key"] + " " + f["kind"] + (" write_protected" if f["write_protected"] else "")
                                       for f in covering if not answerable(f)]
        else:   # must_hold
            hits = [f for f in covering if answerable(f)]
    out["outcome"] = "wrong" if hits else "right"
    if hits:
        out["offending_fields"] = [{k: f[k] for k in ("key", "label", "kind", "target_type", "slot", "options")}
                                   for f in hits]
    ev = notes_about(notes, sorted(set(regions + [c.split("#")[0] for c in controls] +
                                       [c.split("#")[0].rsplit("/", 1)[0] for c in controls])))
    if ev:
        out["notes_evidence"] = ev
    return out


def grade(expected, fields, notes):
    areas = expected.get("areas", [])
    controls = expected.get("controls", [])
    by_id = {a["id"]: a for a in areas}
    groups = expected.get("table_groups", {})
    area_results = [grade_area(a, fields, areas, groups, notes) for a in areas]
    control_results = [grade_control(c, fields, by_id, notes) for c in controls]
    def in_a_control(f):
        for ctl in controls:
            d = ctl.get("destination") or {}
            regions = ([d["region"]] if d.get("region") else []) + list(d.get("regions") or [])
            if any(box_covers(k, c) for k in f["boxes"] for c in d.get("controls") or []) \
                    or any(anchored_in(f, r) for r in regions):
                return True
        return False

    extras = []
    for f in fields:
        if any(covers_area(f, a) for a in areas) or in_a_control(f):
            continue            # graded under that area or control
        extra = {"key": f["key"], "label": f["label"], "kind": f["kind"], "slot": f["slot"],
                 "target_type": f["target_type"], "options": f["options"]}
        if not answerable(f):
            extra["protected"] = True
        extras.append(extra)
    tally = {}
    for r in area_results:
        tally[r["outcome"]] = tally.get(r["outcome"], 0) + 1
    ctally = {}
    for r in control_results:
        ctally[r["outcome"]] = ctally.get(r["outcome"], 0) + 1
    return {"areas": area_results, "controls": control_results, "extras": extras,
            "summary": {"areas": len(areas), **{"areas_" + k: v for k, v in sorted(tally.items())},
                        "controls": len(controls), **{"controls_" + k: v for k, v in sorted(ctally.items())},
                        "extras_answerable": sum(1 for e in extras if not e.get("protected")),
                        "extras_protected": sum(1 for e in extras if e.get("protected"))}}


# ─── run ──────────────────────────────────────────────────────────────────────────────────────────────────────
def frozen_manifest():
    path = HERE / "EXPECTED-SHA256SUMS"
    if not path.exists():
        raise SystemExit("EXPECTED-SHA256SUMS is missing: freeze the expectations before measuring")
    frozen, meta = {}, {}
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            if ":" in line:
                k, v = line[1:].split(":", 1)
                meta[k.strip()] = v.strip()
            continue
        if line.strip():
            digest, name = line.split(None, 1)
            frozen[name.strip()] = digest
    return path, frozen, meta


def git(*args):
    return subprocess.run(["git", "-C", str(WORKTREE)] + list(args), capture_output=True, text=True).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forms", type=Path, default=DEFAULT_FORMS)
    ap.add_argument("--out", type=Path, default=HERE / "baseline-deterministic.json")
    args = ap.parse_args(argv)

    network = network_positive_control()
    if network.startswith("FAILED"):
        print(network, file=sys.stderr)
        return 1

    manifest, frozen, meta = frozen_manifest()
    current = {p.name: sha256(p) for p in sorted(HERE.glob("*.expected.json"))}
    # Since 2026-09-29 the manifest also freezes the graders and the notes cases (paths relative to this directory);
    # every listed file must still match, and every expected map must be listed.
    others = {name: (sha256(HERE / name) if (HERE / name).exists() else None) for name in frozen
              if not name.endswith(".expected.json")}
    listed_maps = {name: digest for name, digest in frozen.items() if name.endswith(".expected.json")}
    if current != listed_maps or any(others[name] != frozen[name] for name in others):
        print("expected maps or frozen graders/cases differ from the frozen manifest:", file=sys.stderr)
        for name in sorted(set(current) | set(frozen)):
            now = current.get(name, others.get(name))
            if now != frozen.get(name):
                print("  %s frozen=%s now=%s" % (name, frozen.get(name), now), file=sys.stderr)
        return 1

    sys.path.insert(0, str(REBUILD))
    from documents import word_v3 as w          # the candidate engine, imported only after the socket denial
    engine_file = Path(w.__file__).resolve()
    if REBUILD not in engine_file.parents:
        print("engine imported from outside the worktree: %s" % engine_file, file=sys.stderr)
        return 1

    engine = {}
    for rel in ("rebuild/documents/word_v3.py", "rebuild/documents/source_policy.py",
                "rebuild/documents/mapping_limits.py"):
        engine[rel] = sha256(WORKTREE / rel)

    forms, per_form, totals = {}, {}, {}
    for name in FORMS:
        path = args.forms / (name + ".docx")
        data = path.read_bytes()
        forms[name + ".docx"] = hashlib.sha256(data).hexdigest()
        expected = json.loads((HERE / (name + ".expected.json")).read_text())
        per_form[name] = {}
        # path 1: inspect()
        try:
            ins = w.inspect(data)
            fields = [summarise(f) for f in ins["fields"]]
            per_form[name]["inspect"] = {"layout_pending": ins.get("layout_pending"), "notes": ins["notes"],
                                         "fields": fields, **grade(expected, fields, ins["notes"])}
        except Exception as exc:        # a refusal is a measured outcome, not a harness failure
            per_form[name]["inspect"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
        # path 2: Detector(layout_proposal=True)
        try:
            detector = w.Detector(w.open_package(data), layout_proposal=True)
            areas, notes = detector.detect()
            raw = w.mapped_fields(detector, areas)
            fields = [summarise(f) for f in raw]
            per_form[name]["layout_proposal"] = {"layout_candidates": len(detector.layout_candidates),
                                                 "notes": notes, "fields": fields,
                                                 **grade(expected, fields, notes)}
        except Exception as exc:
            per_form[name]["layout_proposal"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
        for mode, res in per_form[name].items():
            t = totals.setdefault(mode, {})
            for k, v in (res.get("summary") or {"errors": 1}).items():
                t[k] = t.get(k, 0) + v

    result = {
        "schema": "quillmd-sonnet5-mapping-baseline/1",
        "what": "Pre-model deterministic baseline for the Sonnet 5 MAPPING-stage diagnostics. Measurement only.",
        "recorded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "order_of_work": ("Forms generated and expected maps written and checked (check_expected.py, engine-free) "
                          "BEFORE this measurement; the expected maps' sha256 were frozen in EXPECTED-SHA256SUMS "
                          "and this run refuses unless every expected map still matches that manifest."),
        "expectations": {"manifest": manifest.name, "manifest_sha256": sha256(manifest), "frozen_meta": meta,
                         "manifest_mtime_utc": dt.datetime.fromtimestamp(manifest.stat().st_mtime, dt.timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "files": current, "frozen_with_them": {n: frozen[n] for n in sorted(others)},
                         "match_frozen": True},
        "candidate": {"worktree": str(WORKTREE), "head": git("rev-parse", "HEAD"),
                      "engine_files_clean": git("status", "--porcelain", "--", "rebuild/documents") == "",
                      "engine_sha256": engine, "engine_imported_from": str(engine_file)},
        "harness": {"script": HERE.name, "script_sha256": sha256(Path(__file__)), "python": sys.version.split()[0],
                    "network": network, "calls": ["documents.word_v3.inspect",
                                                  "documents.word_v3.Detector(layout_proposal=True).detect + "
                                                  "mapped_fields"],
                    "not_run": "no fill/export, no renderer, no provider/model/token-count call, no database"},
        "forms": forms,
        "grading_rules": GRADING,
        "totals": totals,
        "per_form": per_form,
    }
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"totals": totals}, indent=1))
    for name in FORMS:
        for mode, res in per_form[name].items():
            print("%-28s %-16s %s" % (name, mode, res.get("summary") or res.get("error")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
