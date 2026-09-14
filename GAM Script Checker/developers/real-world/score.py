"""Score gamcheck against the hand labels in each corpus folder.

Each paste goes through `gamcheck.py - --json` exactly as posted. The labels
(labels.json) were written from the command text and GAM's own docs without
looking at gamcheck output; their policy is stored in the file.

The number that matters is UNDER-WARNED: gamcheck calls a paste read-only when
it changes something, or calls it CHANGES when it is destructive. CANNOT TELL
is never an under-warning, because it tells the reader to look.

Usage: python3 score.py /path/to/gamcheck.py [--show]
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RANK = {'READ-ONLY': 0, 'CHANGES': 1, 'DESTRUCTIVE': 3, 'SUSPICIOUS': 4}


def verdict(checker, paste):
    """Run one paste through gamcheck and return its verdict, or CRASH."""
    p = subprocess.run([sys.executable, checker, '-', '--json'], input=paste + '\n',
                       capture_output=True, text=True, encoding='utf-8')
    try:
        return json.loads(p.stdout)[0]['verdict']
    except (ValueError, IndexError, KeyError):
        return 'CRASH'


def classify(expect, got):
    """match, under (dangerous), over (noisy) or other (a typo line read as something)."""
    if got == expect:
        return 'match'
    if got == 'CRASH':
        return 'crash'
    if got == 'CANNOT TELL':
        return 'over'
    if expect == 'CANNOT TELL':
        return 'other'
    return 'under' if RANK[got] < RANK[expect] else 'over'


def main():
    checker, show = sys.argv[1], '--show' in sys.argv
    total, failures = Counter(), 0
    for folder in sorted(p.parent for p in HERE.glob('*/labels.json')):
        corpus = {r['id']: r['paste'] for r in json.loads((folder / 'corpus.json').read_text(encoding='utf-8'))}
        labels = json.loads((folder / 'labels.json').read_text(encoding='utf-8'))['labels']
        counts, rows = Counter(), []
        for cid, lab in labels.items():
            got = verdict(checker, corpus[cid])
            kind = classify(lab['expect'], got)
            counts[kind] += 1
            if kind != 'match':
                rows.append(f"  {kind:<6} {cid} expect {lab['expect']:<12} got {got:<12} {corpus[cid][:90]}")
        total += counts
        failures += counts['under'] + counts['crash']
        n = sum(counts.values())
        print(f"{folder.name}: {n} pastes, {counts['match']} match, {counts['under']} under-warned, "
              f"{counts['over']} over-warned, {counts['other']} typo lines read as a verdict, {counts['crash']} crashed")
        if show or rows:
            print('\n'.join(rows))
    n = sum(total.values())
    print(f"ALL: {n} pastes, {total['match']} match ({100 * total['match'] / n:.0f}%), {total['under']} under-warned")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
