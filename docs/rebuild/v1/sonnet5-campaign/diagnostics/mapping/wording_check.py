"""Wording check: no provider-bound string may share a normalized substring of 25+ characters with development text.

Rule (the independent checker's W1/W2 rule, made strict): every string is normalized with NFKC, casefold, and every
run of non-alphanumeric characters collapsed to ONE space (ends trimmed). A HIT is any 25-character window of a
normalized provider-bound string that also occurs in a normalized development string. Boundary spaces count, so the
checker's "24 trimmed, 25 with a boundary space" cases are hits here.

Development side (read offline only, never copied anywhere; hits are reported by file id, area id and field name):
  * dev/groundtruth/*.json (the 80 files, annotator files included): answer_areas[].label / options / context,
    and form_title;
  * dev/slots/*.json (40 files): every slot's text, options, alias and tag.
Holdout and qualification are never opened: only the dev directory is listed.

Provider-bound side (everything a Sonnet 5 request of this campaign could carry, plus supersets):
  * GATE  every paragraph and every table cell of every synthetic form (mapping forms and notes forms), every
          docProps text value, every string the candidate's own assistance outline and inspect produce from those
          forms (slot text, heading, row label, options; field label, context, options), every string value in
          notes/cases.json (notes, labels, contexts, options, and - as a superset - rationales), the f6b note, the f6a
          long answer, every string value in the expected maps (a superset of the printed labels), and every string
          literal of the three generators (a superset of everything they print);
  * INFO  each XML part's text joined across paragraphs and cells. No request carries a whole part as one string,
          so a hit that exists ONLY across a paragraph/cell join is a reproduction of structure and is reported
          separately, not gated.

    python -B wording_check.py [--out wording-check.json] [--probe "candidate text" ...]

--probe checks candidate strings only (for choosing fresh wording) and prints hits by dev id; nothing else runs.
Exit 0 = the gate is clean; 1 = at least one gated hit (or a missing input); 2 = --probe found a hit.
Sockets are denied in-process; the engine calls run inside the candidate's isolated worker.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import re
import socket
import sys
import unicodedata
import zipfile
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
DIAG = HERE.parent
WORKTREE = HERE.parents[5]
REBUILD = WORKTREE / "rebuild"
DEV = Path("/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/dev")
RUNTIME = Path("/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics")
WINDOW = 25
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# The generic instruction phrases the campaign plan itself names as fixed strings (mapping/README.md, "Why the forms
# are synthetic"). A window lying ENTIRELY inside one of them is reported as plan_phrase, not gated; any window that
# extends past the phrase (for example into a neighbouring title) is gated as usual.
PLAN_PHRASES = ["(please tick one)", "(one box only)", "Tick all that apply", "You may tick more than one box",
                "Select up to 3", "Route (e.g., po)", "Recipient(s)", "Describe any abnormality",
                "Normal / Abnormal / Not examined", "Left knee / Right knee"]


def _denied(*args, **kwargs):
    raise PermissionError("network denied by wording_check.py")


socket.socket.connect = _denied
socket.socket.connect_ex = _denied
socket.create_connection = _denied
socket.getaddrinfo = _denied


def norm(text) -> str:
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"\s+", " ", _alnum_only(text)).strip()


def _alnum_only(text: str) -> str:
    # str.isalnum decides what an alphanumeric character is (letters of every script, every digit form);
    # everything else becomes a separator.
    return "".join(ch if ch.isalnum() else " " for ch in text)


def windows(text: str):
    n = norm(text)
    for i in range(0, max(0, len(n) - WINDOW + 1)):
        yield n[i:i + WINDOW]


def plan_spans(n: str):
    spans = []
    for phrase in PLAN_PHRASES:
        p = norm(phrase)
        start = n.find(p)
        while start != -1:
            spans.append((start, start + len(p)))
            start = n.find(p, start + 1)
    return spans


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ─── development side ──────────────────────────────────────────────────────────────────────────────────────────
def dev_strings():
    """(dev id, field, text) for every development string the rule covers. Holdout/qual are never touched."""
    gt = sorted((DEV / "groundtruth").glob("*.json"))
    slots = sorted((DEV / "slots").glob("*.json"))
    if len(gt) != 80 or len(slots) != 40:
        raise SystemExit("unexpected dev layout: %d groundtruth files, %d slot files" % (len(gt), len(slots)))
    for path in gt:
        doc = json.loads(path.read_text())
        ident = path.name.split("-")[0] + (":annotator" if ".annotator." in path.name else "")
        if doc.get("form_title"):
            yield ident, "form_title", doc["form_title"]
        for area in doc.get("answer_areas") or []:
            aid = "%s/%s" % (ident, area.get("id", "?"))
            for key in ("label", "context"):
                if area.get(key):
                    yield aid, key, area[key]
            for option in area.get("options") or []:
                yield aid, "option", option
    for path in slots:
        ident = path.name.split("-")[0] + ":slots"
        for row in json.loads(path.read_text()):
            sid = "%s/%s" % (ident, row.get("slot", "?"))
            for key in ("text", "alias", "tag"):
                if row.get(key):
                    yield sid, key, row[key]
            for option in row.get("options") or []:
                yield sid, "option", option


# ─── provider-bound side ───────────────────────────────────────────────────────────────────────────────────────
def docx_strings(path: Path):
    """(where, text, gated) for one form: paragraphs, cells and docProps values (gated); whole parts (info)."""
    out = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith(".xml") or not (name.startswith("word/") or name.startswith("docProps/")):
                continue
            root = etree.fromstring(z.read(name))
            if name.startswith("docProps/"):
                for el in root.iter():
                    if isinstance(el.tag, str) and el.text and el.text.strip():
                        out.append(("%s:%s:%s" % (path.name, name, etree.QName(el).localname), el.text, True))
                continue
            paras = list(root.iter("{%s}p" % W))
            for n, p in enumerate(paras):
                text = "".join(t.text or "" if t.tag == "{%s}t" % W else " " for t in p.iter("{%s}t" % W, "{%s}tab" % W))
                if text.strip():
                    out.append(("%s:%s:p#%d" % (path.name, name, n), text, True))
            for n, tc in enumerate(root.iter("{%s}tc" % W)):
                text = " ".join("".join(t.text or "" for t in p.iter("{%s}t" % W)) for p in tc.iter("{%s}p" % W))
                if text.strip():
                    out.append(("%s:%s:tc#%d" % (path.name, name, n), text, True))
            whole = " ".join("".join(t.text or "" for t in p.iter("{%s}t" % W)) for p in paras)
            if whole.strip():
                out.append(("%s:%s:WHOLE" % (path.name, name), whole, False))
    return out


def json_strings(value, where):
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from json_strings(v, "%s.%s" % (where, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from json_strings(v, "%s[%d]" % (where, i))


def engine_strings(paths):
    """What the candidate itself extracts from each form: assistance outline rows and v3 inspect fields."""
    sys.path.insert(0, str(REBUILD))
    from documents import service
    out = []
    for path in paths:
        outline = service.assistance_outline(str(path))
        for row in outline["slots"]:
            for key in ("text", "heading", "row_label", "preview", "context"):
                if row.get(key):
                    out.append(("%s:outline:%s:%s" % (path.name, row["slot"], key), row[key], True))
            for option in row.get("options") or []:
                out.append(("%s:outline:%s:option" % (path.name, row["slot"]), option, True))
        inspected = service.inspect_template(str(path), engine="v3")
        for field in inspected["fields"]:
            for key in ("label", "context"):
                if field.get(key):
                    out.append(("%s:inspect:%s:%s" % (path.name, field["key"], key), field[key], True))
            for option in field.get("options") or []:
                out.append(("%s:inspect:%s:option" % (path.name, field["key"]), option, True))
    return out


def provider_strings(with_engine=True):
    forms = sorted((RUNTIME / "mapping").glob("*.docx")) + sorted((RUNTIME / "notes").glob("*.docx"))
    strings, inputs = [], {}
    for path in forms:
        inputs[str(path)] = sha(path)
        strings += docx_strings(path)
    if with_engine:
        strings += engine_strings(forms)
    cases = DIAG / "notes" / "cases.json"
    inputs[str(cases)] = sha(cases)
    strings += [("cases.json:%s" % w, s, True) for w, s in json_strings(json.loads(cases.read_text()), "$")]
    for expected in sorted(HERE.glob("*.expected.json")):
        inputs[str(expected)] = sha(expected)
        strings += [("%s:%s" % (expected.name, w), s, True) for w, s in json_strings(json.loads(expected.read_text()), "$")]
    for script in (HERE / "build_forms.py", DIAG / "notes" / "build_note_forms.py", HERE / "long_answer_readback.py"):
        inputs[str(script)] = sha(script)
        tree = ast.parse(script.read_text())
        strings += [("%s:literal@%d" % (script.name, node.lineno), node.value, True) for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(norm(node.value)) >= WINDOW]
    long_answer = HERE / "long-answer.txt"
    if long_answer.exists():
        inputs[str(long_answer)] = sha(long_answer)
        strings.append(("long-answer.txt", long_answer.read_text(), True))
    return strings, forms, inputs


CHECKED_FREEZE = "00a423a956b3a95bc41efdb7ede4ad72668443e7"   # the sets as the independent checker read them


def positive_control():
    """The same check over the CHECKED (pre-repair) cases.json and expected maps, read from git: it must find the
    overlaps the checker reported, or this instrument proves nothing when it says CLEAN."""
    import subprocess
    rel = "docs/rebuild/v1/sonnet5-campaign/diagnostics/"
    names = ["notes/cases.json"] + ["mapping/%s.expected.json" % n for n in (
        "f1-guidance-confirmation", "f2-leave-checkboxes", "f5-negative-controls")]
    strings = []
    for name in names:
        text = subprocess.run(["git", "-C", str(WORKTREE), "show", "%s:%s%s" % (CHECKED_FREEZE, rel, name)],
                              capture_output=True, text=True, check=True).stdout
        strings += [("checked:%s:%s" % (name, w), s, True) for w, s in json_strings(json.loads(text), "$")]
    hits, _, _ = check(strings)
    gated = [h for h in hits if h["windows_outside_plan_phrases"]]
    sources = sorted({h["provider"].split(":$")[0] for h in gated})
    return {"source": "git %s (the sets the checker read)" % CHECKED_FREEZE[:8], "gated_hits": len(gated),
            "files_with_hits": sources, "detects_the_reported_overlaps": bool(gated)}


def check(strings):
    """Index the provider windows (small), then stream the development strings against them."""
    index = {}
    for where, text, gated in strings:
        n = norm(text)
        spans = plan_spans(n)
        for i in range(0, max(0, len(n) - WINDOW + 1)):
            allowed = any(a <= i and i + WINDOW <= b for a, b in spans)
            index.setdefault(n[i:i + WINDOW], []).append((where, gated, allowed))
    hits, dev_count = {}, 0
    for dev_id, field, text in dev_strings():
        dev_count += 1
        for w in set(windows(text)):
            for where, gated, allowed in index.get(w, ()):
                key = (where, dev_id, field)
                hit = hits.setdefault(key, {"provider": where, "dev": dev_id, "dev_field": field, "gated": gated,
                                            "windows": 0, "windows_outside_plan_phrases": 0})
                hit["windows"] += 1
                hit["windows_outside_plan_phrases"] += 0 if allowed else 1
    return list(hits.values()), dev_count, len(index)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--probe", nargs="*")
    ap.add_argument("--no-engine", action="store_true", help="skip the outline/inspect strings (faster; not the gate)")
    args = ap.parse_args(argv)
    if args.probe:
        hits, dev_count, _ = check([("probe[%d]" % i, s, True) for i, s in enumerate(args.probe)])
        hits = [h for h in hits if h["windows_outside_plan_phrases"]]
        for h in hits:
            print("HIT %s ~ %s %s (%d windows)" % (h["provider"], h["dev"], h["dev_field"], h["windows"]))
        print("%d probe strings, %d dev strings, %d hits" % (len(args.probe), dev_count, len(hits)))
        return 2 if hits else 0
    control = positive_control()
    if not control["detects_the_reported_overlaps"]:
        print("positive control FAILED: the check finds nothing in the pre-repair sets", file=sys.stderr)
        return 1
    strings, forms, inputs = provider_strings(with_engine=not args.no_engine)
    hits, dev_count, index_size = check(strings)
    gated = [h for h in hits if h["gated"] and h["windows_outside_plan_phrases"]]
    plan = [h for h in hits if h["gated"] and not h["windows_outside_plan_phrases"]]
    info = [h for h in hits if not h["gated"]]
    result = {
        "schema": "quillmd-sonnet5-wording-check/1",
        "recorded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule": ("normalized (NFKC, casefold, non-alphanumeric runs -> one space) shared substring of %d+ characters, "
                 "boundary spaces counted" % WINDOW),
        "script_sha256": sha(Path(__file__)),
        "engine_strings_included": not args.no_engine,
        "provider_strings": len(strings), "provider_strings_gated": sum(1 for s in strings if s[2]),
        "provider_windows": index_size, "dev_strings": dev_count, "forms": len(forms), "inputs_sha256": inputs,
        "positive_control": control,
        "plan_phrases": PLAN_PHRASES,
        "gated_hits": gated, "plan_phrase_hits_not_gated": plan, "info_hits_join_only": info,
        "verdict": "CLEAN" if not gated else "NOT CLEAN",
    }
    if args.out:
        args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("inputs_sha256",)}, indent=1, ensure_ascii=False))
    return 0 if not gated else 1


if __name__ == "__main__":
    sys.exit(main())
