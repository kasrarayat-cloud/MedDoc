"""Score v3 detection against ground truth (development set during iteration).

Rules (fixed 2026-09-27 before the first score was printed):
- GT source: the reviewer file <stem>.json; if absent, the annotator file (result marked PROVISIONAL).
- Slots are compared after dropping a trailing '/glyphs'. A detected slot is RELATED to a GT slot when they are in
  the same part and equal, or one is a path-prefix of the other and the shorter one is a paragraph, cell, content
  control, form field or text box (never a bare table/body), except table_rows, which may anchor on the table.
- Kind classes: FREE{text,long_text,number,measurement,time} DATE{date} CHOICE{choice,checkbox_group}
  MULTI{multi_choice,checkbox_group} CHECK{checkbox} SIGN{signature,initials} TABLE{table_rows}.
- Matching: each GT area takes the best unused related detected field (exact slot > prefix; then label similarity).
- A GT area is CORRECT if matched, its class agrees, and (choice/multi) the option count agrees.
- Duplicate labels: a GT area with duplicate_label must be matched by a field whose (label, context) is unique.
- Detection success (strict): every GT area CORRECT, every duplicate disambiguated, zero unmatched detected fields.
  Detection success (tolerant): the same, with unmatched detected fields <= max(2, 10% of GT). Both are printed.
"""
import json, re, sys, pathlib, collections
C = pathlib.Path("/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus")
CLASSES = {"text": "FREE", "long_text": "FREE", "number": "FREE", "measurement": "FREE", "time": "FREE",
           "date": "DATE", "choice": "CHOICE", "multi_choice": "MULTI", "checkbox": "CHECK", "signature": "SIGN",
           "initials": "SIGN", "table_rows": "TABLE"}


def norm(s):
    return re.sub(r"/glyphs$", "", s)


def split(s):
    part, _, path = norm(s).partition("#")
    return part, path


def leaf_ok(path, kind):
    last = path.split("/")[-1]
    if kind == "table_rows":
        return True
    return not (last in ("b", "hf") or last.startswith("tbl[") or last.startswith("tr["))


def related(a, b, kind):
    pa, xa = split(a)
    pb, xb = split(b)
    if pa != pb:
        return 0
    if xa == xb:
        return 2
    short, long_ = (xa, xb) if len(xa) < len(xb) else (xb, xa)
    if long_.startswith(short + "/") and leaf_ok(short, kind):
        return 1
    return 0


def det_slots(f):
    loc = f["locator"]
    out = ["%s#%s" % (loc["part"], loc["slot"])]
    for e in loc.get("extra", []):
        out.append("%s#%s" % (e["part"], e["slot"]))
    for b in loc["target"].get("boxes", []):
        out.append("%s#%s" % (b["part"], b["slot"]))
    for c in loc["target"].get("copies", []):
        out.append("%s#%s" % (c["part"], c["slot"]))
    return out


def words(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def sim(a, b):
    wa, wb = words(a), words(b)
    return len(wa & wb) / max(1, len(wa | wb))


def classes_agree(gk, dk):
    g = CLASSES.get(gk, "FREE" if gk not in ("checkbox_group",) else "GROUP")
    d = CLASSES.get(dk, "FREE")
    if g == "GROUP":
        return d in ("CHOICE", "MULTI")
    return g == d


def score_doc(gt, det):
    areas = gt.get("answer_areas", [])
    fields = det.get("fields", [])
    used = set()
    rows = []
    for a in areas:
        gslots = [norm(s) for s in a.get("slots", [])]
        best, bestkey = None, None
        for i, f in enumerate(fields):
            if i in used:
                continue
            r = max((related(g, d, a.get("kind")) for g in gslots for d in det_slots(f)), default=0)
            if not r:
                continue
            key = (r, sim(a.get("label", ""), f["label"]) + 0.5 * sim(a.get("context", ""), f.get("context", "")))
            if bestkey is None or key > bestkey:
                best, bestkey = i, key
        if best is None:
            rows.append({"id": a["id"], "status": "MISSED", "gt": a})
            continue
        used.add(best)
        f = fields[best]
        problems = []
        if not classes_agree(a.get("kind"), f["kind"]):
            problems.append("kind %s->%s" % (a.get("kind"), f["kind"]))
        if a.get("kind") in ("choice", "multi_choice", "checkbox_group"):
            go, do = len(a.get("options") or []), len(f.get("options") or [])
            if go and go != do:
                problems.append("options %d->%d" % (go, do))
        rows.append({"id": a["id"], "status": "WRONG" if problems else "OK", "problems": problems, "gt": a, "det": f})
    # a header/footer answer written to every copy of the header satisfies each copy's area (same answer, every
    # destination covered); only for areas outside the body, only via the field's recorded copies
    for r in rows:
        if r["status"] != "MISSED":
            continue
        gslots = [norm(x) for x in r["gt"].get("slots", [])]
        if not gslots or any(split(g)[0] == "word/document.xml" for g in gslots):
            continue
        for i in used:
            f = fields[i]
            copies = ["%s#%s" % (c["part"], c["slot"]) for c in f["locator"]["target"].get("copies", [])]
            if copies and any(related(g, c, r["gt"].get("kind")) for g in gslots for c in copies) and \
                    classes_agree(r["gt"].get("kind"), f["kind"]):
                r.update(status="OK", det=f, problems=[], via="copy")
                break
    # duplicates
    pair_counts = collections.Counter((f["label"], f.get("context", "")) for f in fields)
    dup_bad = [r for r in rows if r["gt"].get("duplicate_label") and r.get("det") and pair_counts[(r["det"]["label"], r["det"].get("context", ""))] > 1]
    extras = [f for i, f in enumerate(fields) if i not in used]
    ok = sum(1 for r in rows if r["status"] == "OK")
    n = len(areas)
    strict = ok == n and not dup_bad and not extras and "fields" in det
    tolerant = ok == n and not dup_bad and len(extras) <= max(2, n // 10) and "fields" in det
    return {"n": n, "ok": ok, "missed": sum(r["status"] == "MISSED" for r in rows), "wrong": sum(r["status"] == "WRONG" for r in rows),
            "extras": len(extras), "dup_bad": len(dup_bad), "strict": strict, "tolerant": tolerant,
            "rows": rows, "extra_fields": extras, "dup_rows": dup_bad}


def main(det_dir, set_name="dev", detail=None):
    det_dir = pathlib.Path(det_dir)
    tot = collections.Counter()
    for gtf in sorted((C / set_name / "groundtruth").glob("*.annotator.json")):
        stem = gtf.name.split(".")[0]
        final = C / set_name / "groundtruth" / (stem + ".json")
        gt = json.loads((final if final.exists() else gtf).read_text())
        prov = "" if final.exists() else " PROVISIONAL"
        detp = det_dir / (stem + ".json")
        if not detp.exists():
            continue
        det = json.loads(detp.read_text())
        s = score_doc(gt, det)
        tot["docs"] += 1; tot["strict"] += s["strict"]; tot["tolerant"] += s["tolerant"]
        tot["n"] += s["n"]; tot["ok"] += s["ok"]; tot["missed"] += s["missed"]; tot["wrong"] += s["wrong"]; tot["extras"] += s["extras"]
        print("%s n=%3d ok=%3d missed=%3d wrong=%3d extra=%3d dup=%d %s%s" % (stem[:3], s["n"], s["ok"], s["missed"], s["wrong"], s["extras"], s["dup_bad"],
              "PASS" if s["strict"] else ("pass~" if s["tolerant"] else "fail"), prov))
        if detail and stem.startswith(detail):
            for r in s["rows"]:
                if r["status"] != "OK":
                    g = r["gt"]
                    print("  %s %s [%s] %r slots=%s notes=%r" % (r["status"], r.get("problems", ""), g.get("kind"), g.get("label", "")[:60], g.get("slots"), (g.get("notes") or "")[:140]))
                    if r.get("det"):
                        d = r["det"]; print("     det: [%s] %r %s %s" % (d["kind"], d["label"][:60], d["locator"]["slot"], d.get("options")))
            for f in s["extra_fields"]:
                print("  EXTRA [%s] %r %s %s" % (f["kind"], f["label"][:60], f["locator"]["slot"], f["locator"]["target"].get("type")))
            for r in s["dup_rows"]:
                print("  DUP %r ctx=%r" % (r["det"]["label"], r["det"].get("context")))
    print("TOTAL docs=%d strict=%d tolerant=%d | areas=%d ok=%d missed=%d wrong=%d extras=%d" % (
        tot["docs"], tot["strict"], tot["tolerant"], tot["n"], tot["ok"], tot["missed"], tot["wrong"], tot["extras"]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "dev", sys.argv[3] if len(sys.argv) > 3 else None)
