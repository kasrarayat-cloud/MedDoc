"""Networkless, bounded preparation parser. No provider, credentials or database."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import isolate
from engine import DocumentFailure
from preparation import inventory, candidate

def main():
    workspace = Path(sys.argv[1]).resolve()
    try:
        isolate(workspace)
    except Exception:
        print(json.dumps({'error': 'The secure document sandbox is unavailable.', 'code': 'sandbox_unavailable'}))
        return
    try:
        request = json.loads((workspace/'request.json').read_text())
        if request['operation'] == 'inventory':
            result = inventory(workspace/'input.docx', request.get('known'))
        elif request['operation'] == 'candidate':
            result = candidate(workspace/'input.docx', workspace/'output.docx',
                               request['inventory'], request['selected'],request.get('placements'))
        else:
            raise DocumentFailure('Unsupported preparation operation.', 'invalid_operation')
    except DocumentFailure as exc:
        result = {'error': str(exc), 'code': exc.code}
    except Exception:
        result = {'error': 'The blank form has an unsupported structure.', 'code': 'invalid_document'}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
