"""Fill every detected field of each development form with a synthetic answer and verify the export mechanically.

Checks (per document):
  opens      the export re-opens under the same safety checks, and python-docx loads it
  structure  per content part: counts of paragraphs, tables, cells, content controls, field begins, drawings are
             unchanged (rows may grow only in table_rows targets)
  untouched  every paragraph outside the targeted slots has byte-identical text
  kept       in targeted paragraphs, the original text minus the target ranges is a subsequence of the new text
  landed     every answer's text is present in its target (marks for choices)
Synthetic answers only; signature/initials areas are left empty (they are never auto-filled).
"""
import copy, difflib, importlib.util, io, json, pathlib, sys, traceback, zipfile
spec = importlib.util.spec_from_file_location("word_v3", "/opt/meddoc-pro/.worktrees/v1-word/rebuild/documents/word_v3.py")
w = importlib.util.module_from_spec(spec); sys.modules["word_v3"] = w; spec.loader.exec_module(w)
from lxml import etree

C = pathlib.Path("/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus")


def synthetic(field, n):
    k = field["kind"]
    opts = field.get("options") or []
    if k in ("signature", "initials"):
        return None
    if k == "checkbox":
        return True
    if k == "choice":
        return opts[min(1, len(opts) - 1)] if opts else None
    if k == "multi_choice":
        return opts[:2] if opts else None
    if k == "date":
        return "03/14/2026"
    if k == "time":
        return "14:30"
    if k == "long_text":
        return "Synthetic finding %d, first line.\nSecond line of the synthetic answer." % n
    if k == "table_rows":
        cols = len(field["locator"]["target"]["columns"])
        return [["R%dC%d" % (r, c) for c in range(cols)] for r in range(2)]
    return "Synthetic %d" % n


def counts(tree):
    tags = {"p": w.q("w:p"), "tbl": w.q("w:tbl"), "tc": w.q("w:tc"), "sdt": w.q("w:sdt"), "drawing": w.q("w:drawing")}
    out = {k: sum(1 for _ in tree.iter(t)) for k, t in tags.items()}
    out["fld"] = sum(1 for x in tree.iter(w.q("w:fldChar")) if x.get(w.q("w:fldCharType")) == "begin")
    out["tr"] = sum(1 for _ in tree.iter(w.q("w:tr")))
    return out


def para_texts(pkg):
    idx = w.SlotIndex(pkg)
    return {s.id: w.paragraph_text(s.el)[0] for s in idx.slots if s.kind == "p"}, idx


def is_subsequence(small, big):
    it = iter(big)
    return all(ch in it for ch in small)


def allowed_removals(field, idx):
    """{paragraph slot id: set(positions) | 'all'} - original characters this field may replace."""
    loc = field["locator"]
    tgt = loc["target"]
    out = {}

    def paras_under(part, path):
        s = idx.by_id.get("%s#%s" % (part, path))
        if s is None:
            return []
        return [x for x in idx.slots if x.part == s.part and x.kind == "p" and (x.path == s.path or x.path.startswith(s.path + "/"))]

    def host_p(part, path):
        s = idx.by_id.get("%s#%s" % (part, path))
        while s is not None and s.kind != "p":
            s = s.parent
        return s

    anchors = [(loc["part"], loc["slot"])] + [(c["part"], c["slot"]) for c in tgt.get("copies", [])]
    kind = tgt["type"]
    for part, path in anchors:
        if kind == "span":
            p = idx.by_id["%s#%s" % (part, path)]
            out.setdefault(p.id, set()).update(range(tgt["start"], tgt["end"]))
        elif kind in ("cell", "cell_replace", "sdt_text", "sdt_choice", "paragraph"):
            for p in paras_under(part, path):
                out[p.id] = "all"
            for e in loc.get("extra", []):
                for p in paras_under(e["part"], e["slot"]):
                    out[p.id] = "all"
            h = host_p(part, path)
            if h is not None and kind.startswith("sdt"):
                out.setdefault(h.id, set())
        elif kind in ("ff_text", "ff_dropdown", "paragraph_options", "text_options"):
            h = host_p(part, path)
            if h is not None:
                out.setdefault(h.id, set())
            for e in loc.get("extra", []):
                for p in paras_under(e["part"], e["slot"]):
                    out.setdefault(p.id, set())
        elif kind == "checkboxes":
            for b in tgt["boxes"]:
                if b["kind"] == "cell":
                    for p in paras_under(b["part"], b["slot"]):
                        out[p.id] = "all"
                elif b["kind"] == "cell_text":
                    for p in paras_under(b["part"], b["slot"]):
                        out.setdefault(p.id, set())
                else:
                    h = host_p(b["part"], b["slot"])
                    if h is not None:
                        text = w.paragraph_text(h.el)[0]
                        cur = out.setdefault(h.id, set())
                        if cur != "all":
                            cur.update(i for i, ch in enumerate(text) if ch in (w.BOX, w.CHECKED))
        elif kind == "table_rows":
            for p in paras_under(part, tgt["table"]):
                out.setdefault(p.id, set())
                text = w.paragraph_text(p.el)[0]
                if not text.strip():
                    out[p.id] = "all"
    return out


def check(stem, src_bytes, det):
    fields = det["fields"]
    answers = {}
    for i, f in enumerate(fields):
        a = synthetic(f, i + 1)
        if a is not None:
            answers[f["key"]] = a
    out = w.fill(src_bytes, fields, answers)
    res = {"stem": stem, "fields": len(fields), "answered": len(answers), "problems": [], "answers": answers}
    pkg0 = w.open_package(src_bytes)
    pkg1 = w.open_package(out)
    try:
        import docx
        docx.Document(io.BytesIO(out))
    except Exception as e:
        res["problems"].append("python-docx cannot open: %r" % e)
    has_rows = any(f["locator"]["target"]["type"] == "table_rows" for f in fields)
    idx_pre = w.SlotIndex(pkg0)
    expected_p_drop = {}
    for f in fields:
        t = f["locator"]["target"]
        if f["key"] in answers and t.get("all"):
            cell = idx_pre.by_id["%s#%s" % (f["locator"]["part"], f["locator"]["slot"])]
            n = len(cell.el.findall(w.q("w:p")))
            expected_p_drop[f["locator"]["part"]] = expected_p_drop.get(f["locator"]["part"], 0) + max(0, n - 1)
    for part in pkg0.content_parts():
        c0, c1 = counts(pkg0.tree(part)), counts(pkg1.tree(part))
        c0["p"] -= expected_p_drop.get(part, 0)
        for k in c0:
            if c0[k] != c1[k] and not (has_rows and k in ("tr", "tc", "p")):
                res["problems"].append("structure %s %s: %d -> %d" % (part, k, c0[k], c1[k]))
    t0, idx0 = para_texts(pkg0)
    t1, idx1 = para_texts(pkg1)
    allowed = {}
    for f in fields:
        if f["key"] in answers:
            for pid, pos in allowed_removals(f, idx0).items():
                if allowed.get(pid) == "all" or pos == "all":
                    allowed[pid] = "all"
                else:
                    allowed.setdefault(pid, set()).update(pos)
    for sid, text in t0.items():
        if sid not in t1:
            if allowed.get(sid) != "all":
                res["problems"].append("paragraph lost %s" % sid)
            continue
        new = t1[sid]
        if sid not in allowed:
            if new != text:
                res["problems"].append("untargeted paragraph changed %s: %r -> %r" % (sid, text[:60], new[:60]))
            continue
        if allowed[sid] == "all":
            continue
        kept = "".join(ch for i, ch in enumerate(text) if i not in allowed[sid])
        if not is_subsequence(kept, new):
            sm = difflib.SequenceMatcher(None, kept, new, autojunk=False)
            lost = "".join(kept[i1:i2] for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ("delete", "replace"))
            res["problems"].append("printed text lost in %s: %r" % (sid, lost[:80]))
    alltext = "\n".join(t1.values()) + "\n".join(w.text_of(pkg1.tree(p)) for p in pkg1.content_parts())
    for f in fields:
        a = answers.get(f["key"])
        if isinstance(a, str) and f["kind"] not in ("choice", "multi_choice"):
            first = a.split("\n")[0]
            if first not in alltext:
                res["problems"].append("answer not found: %s %r" % (f["key"], first[:40]))
    return res, out


def main(set_name="dev", only=None, keep_dir=None):
    det_dir = pathlib.Path("eval/detect-" + set_name)
    results = []
    for orig in sorted((C / set_name / "originals").iterdir()):
        stem = orig.stem
        if only and stem[:3] not in only:
            continue
        src = C / set_name / "converted" / (stem + ".docx") if orig.suffix == ".doc" else orig
        det = json.loads((det_dir / (stem + ".json")).read_text())
        if "fields" not in det:
            results.append({"stem": stem, "problems": ["not inspected: %s" % det.get("refused") or det.get("crash")]})
            continue
        try:
            res, out = check(stem, src.read_bytes(), det)
            if keep_dir:
                pathlib.Path(keep_dir).mkdir(parents=True, exist_ok=True)
                (pathlib.Path(keep_dir) / (stem + ".docx")).write_bytes(out)
        except w.V3Failure as e:
            res = {"stem": stem, "problems": ["fill refused: %s (%s)" % (e, e.code)]}
        except Exception as e:
            res = {"stem": stem, "problems": ["fill crashed: %r" % e, traceback.format_exc()[-600:]]}
        results.append(res)
        print(stem[:3], "ok" if not res["problems"] else "PROBLEMS %d: %s" % (len(res["problems"]), res["problems"][0][:150]))
    json.dump(results, open("eval/fill-%s.json" % set_name, "w"), indent=1)
    print("clean exports: %d / %d" % (sum(1 for r in results if not r["problems"]), len(results)))


if __name__ == "__main__":
    args = sys.argv[1:]
    keep = None
    if args and args[0].startswith("--keep="):
        keep = args.pop(0).split("=", 1)[1]
    main("dev", set(args) or None, keep)
