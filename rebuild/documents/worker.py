"""Private worker entry point; callers use service.py."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import DocumentFailure, process  # noqa: E402
from sandbox import isolate  # noqa: E402


def main():
    workspace = Path(sys.argv[1]).resolve()
    try:
        isolate(workspace)
    except Exception:
        print(json.dumps({"error": "The secure document sandbox is unavailable.", "code": "sandbox_unavailable"}))
        return
    try:
        request = json.loads((workspace / "request.json").read_text())
        result = process(workspace, request)
    except DocumentFailure as exc:
        result = {"error": str(exc), "code": exc.code}
    except Exception:
        # Never return file contents, local paths, parser traces, or secrets.
        result = {"error": "The document is malformed or uses an unsupported structure.", "code": "invalid_document"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
