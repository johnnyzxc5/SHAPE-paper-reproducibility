"""Read-only verification of the sealed repository payload; no scientific execution."""
from pathlib import Path
import hashlib

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    root = Path(__file__).resolve().parents[1]
    failures = []
    lines = (root / 'provenance/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
    for line in lines:
        expected, relative = line.split('  ', 1)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path) != expected:
            failures.append(relative)
    print(f'{len(lines)} packaged files checked; {len(failures)} mismatches.')
    for name in failures:
        print('FAIL:', name)
    raise SystemExit(bool(failures))

if __name__ == '__main__':
    main()
