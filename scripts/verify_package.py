"""Verify the public file set and hashes, excluding documented local runtime data."""
from pathlib import Path
import hashlib
import os
import sys

root = Path(__file__).resolve().parents[1]
errors = []
lines = (root / 'docs/checksums.sha256').read_text().splitlines()
listed = set()
for line in lines:
    expected, name = line.split('  ', 1)
    listed.add(name)
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        errors.append('Missing or modified: ' + name)
for folder, directories, names in os.walk(root):
    directories[:] = [d for d in directories if d not in {'.venv', 'venv', 'generated', '.git', '__pycache__'}]
    for name in names:
        path = Path(folder) / name
        relative = path.relative_to(root).as_posix()
        if relative.startswith('data/') and relative != 'data/README.md':
            continue
        if relative == 'docs/checksums.sha256' or name == '.DS_Store':
            continue
        if path.suffix in {'.log', '.aux', '.toc', '.out', '.bbl', '.blg', '.fls', '.fdb_latexmk', '.pyc'} or name.endswith('.synctex.gz') or relative in {'paper/source/main.pdf', 'paper/english-source/main.pdf'}:
            continue
        if relative not in listed:
            errors.append('Unexpected distributable file: ' + relative)
if errors:
    print(*errors, sep='\n')
    sys.exit(1)
print(f'Verified {len(lines)} distributed files. Local environments and generated data are excluded; research limitations still apply.')
