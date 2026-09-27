"""Compare LibreOffice renders of each original and its synthetic-filled export.

Per document: page counts; answers visible in the rendered text layer (first 12 characters of each text answer);
overlap: pairs of rendered characters whose boxes overlap by >40% of the smaller box while being >2 positions apart
in the text stream (printed text drawn over other text) - counted for the original and the export; an increase is
a finding (new overprinting), never netted against other documents.
"""
import json, pathlib, re, sys
import pypdfium2 as pdfium

C = pathlib.Path("/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus")


def page_chars(pdf_path):
    pdf = pdfium.PdfDocument(str(pdf_path))
    pages = []
    for i in range(len(pdf)):
        tp = pdf[i].get_textpage()
        n = tp.count_chars()
        text = tp.get_text_range(0, n) if n else ""
        boxes = []
        for k in range(n):
            ch = text[k] if k < len(text) else ""
            if not ch.strip():
                continue
            l, b, r, t = tp.get_charbox(k)
            if r - l > 0.1 and t - b > 0.1:
                boxes.append((k, l, b, r, t))
        pages.append((text, boxes))
    return pages


def overlaps(pages):
    total = 0
    for text, boxes in pages:
        boxes.sort(key=lambda x: x[1])
        for i, (k1, l1, b1, r1, t1) in enumerate(boxes):
            a1 = (r1 - l1) * (t1 - b1)
            for k2, l2, b2, r2, t2 in boxes[i + 1:]:
                if l2 >= r1:
                    break
                if abs(k1 - k2) <= 2:
                    continue
                w = min(r1, r2) - max(l1, l2)
                h = min(t1, t2) - max(b1, b2)
                if w > 0 and h > 0 and w * h > 0.4 * min(a1, (r2 - l2) * (t2 - b2)):
                    total += 1
    return total


def main(set_name, filled_pdf_dir, answers_file):
    results = []
    answers_all = json.load(open(answers_file)) if answers_file else {}
    kinds_all = {}
    for f in pathlib.Path("eval/detect-" + set_name).glob("*.json"):
        d = json.load(open(f))
        kinds_all[f.stem] = {x["key"]: x["kind"] for x in d.get("fields", [])}
    for pdf in sorted(pathlib.Path(filled_pdf_dir).glob("*.pdf")):
        stem = pdf.stem
        orig = C / set_name / "renders" / stem / "original.pdf"
        p0 = page_chars(orig)
        p1 = page_chars(pdf)
        o0, o1 = overlaps(p0), overlaps(p1)
        text1 = re.sub(r"[\s\-\u00ad]+", "", "".join(t for t, _ in p1))
        missing = []
        kinds = kinds_all.get(stem, {})
        for key, a in (answers_all.get(stem) or {}).items():
            if isinstance(a, str) and kinds.get(key) in ("text", "long_text", "date", "time"):
                probe = re.sub(r"[\s\-]+", "", a.split("\n")[0])[:12]
                if probe and probe not in text1:
                    missing.append(key)
        r = {"stem": stem, "pages": [len(p0), len(p1)], "overlap": [o0, o1], "answers_missing_in_render": missing}
        results.append(r)
        flag = []
        if o1 > o0:
            flag.append("overlap +%d" % (o1 - o0))
        if missing:
            flag.append("%d answers not visible" % len(missing))
        print(stem[:3], "pages %d->%d" % (len(p0), len(p1)), "; ".join(flag) or "ok")
    json.dump(results, open("eval/render-%s.json" % set_name, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
