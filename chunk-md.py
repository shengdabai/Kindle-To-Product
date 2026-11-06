#!/usr/bin/env python3
"""Split clean.md into up to four chunks, cutting only at page markers."""
import argparse
import os
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=Path(os.environ.get(
        'WORK', Path(__file__).resolve().parent / 'output' / 'half-second')))
    args = parser.parse_args()
    src = args.work / 'clean.md'
    chunk_dir = args.work / 'chunks'
    text = src.read_text(encoding='utf-8')
    fm = re.match(r'^---\n.*?\n---\n', text, re.DOTALL)
    body = text[fm.end():] if fm else text
    if not body.strip():
        parser.error('clean.md has no body')

    # Unique page boundaries prevent repeated cuts when one page is very long.
    first_content = len(body) - len(body.lstrip())
    boundaries = [m.start() for m in re.finditer(r'(?m)^<!-- page \d+ -->', body)
                  if m.start() > first_content]
    cuts = sorted({0, len(body), *(min(boundaries, key=lambda off: abs(off - target))
                                  for target in (len(body) // 4, len(body) // 2, 3 * len(body) // 4)
                                  if boundaries)})
    chunks = [body[a:b] for a, b in zip(cuts, cuts[1:])]
    expected = {f'chunk-{i:02d}.md' for i in range(1, len(chunks) + 1)}
    stale = {p.name for p in chunk_dir.glob('chunk-*.md')} - expected
    if stale:
        parser.error('stale chunks exist; use a fresh work directory: ' + ', '.join(sorted(stale)))
    chunk_dir.mkdir(exist_ok=True)
    for i, (start, end, chunk) in enumerate(zip(cuts, cuts[1:], chunks), 1):
        header = (f'---\nchunk: {i}/{len(chunks)}\nsource: clean.md\n'
                  f'char_range: {start}..{end}\nword_count: {len(chunk.split())}\n---\n\n')
        path = chunk_dir / f'chunk-{i:02d}.md'
        path.write_text(header + chunk, encoding='utf-8')
        print(f'{path.name}: {len(chunk)} chars, {len(chunk.split())} words')


if __name__ == '__main__':
    main()
