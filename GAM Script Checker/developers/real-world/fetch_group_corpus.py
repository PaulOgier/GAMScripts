#!/usr/bin/env python3
"""Build a real-world paste corpus from the newest threads of the GAM Google Group.

The group's pages are server-rendered, so plain HTTP works: the front page lists
30 threads, and `search?q=before:<date>` lists older ones (the Next page button
is JavaScript-only and the old RSS feeds return 404). Each thread becomes text,
and every line that starts with a gam command, prompt prefix included, is kept
exactly as posted. Writes OUT_DIR/corpus.json for runcorpus.py.

Usage: python3 fetch_group_corpus.py OUT_DIR [--threads 50] [--before YYYY/MM/DD]
"""
import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

GROUP = 'https://groups.google.com/g/google-apps-manager'
# Google serves a stripped page to non-browser user agents.
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
LEAD = re.compile(r'^(?:\$\s*|>\s*|PS [^>]*>\s*|[A-Za-z]:\\[^>]*>\s*|Command is\s*:\s*)?(?:[~\w./\\:-]*[/\\])?(gam|gam7|gam\.exe|gamx)\s+(\S+)')
# Lower-case "gam" followed by one of these is a sentence about GAM, not a command.
PROSE = set("is can can't cannot and for to will with was has commands command team version support gui does doesn't isn't would should that the a an it as of in on or not now also".split())


def get(url):
    """Fetch a page as text, failing loudly on anything but HTTP 200."""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            raise RuntimeError(f'{url}: HTTP {r.status}')
        return r.read().decode('utf-8', errors='replace')


def thread_ids(page):
    """Thread ids in page order, without repeats."""
    return list(dict.fromkeys(re.findall(r'g/google-apps-manager/c/([A-Za-z0-9_-]+)', page)))


def thread_lines(page):
    """Visible text of a thread page, one line per rendered line."""
    body = re.sub(r'<script.*?</script>|<style.*?</style>', '', page, flags=re.S)
    body = re.sub(r'<br\s*/?>|</(?:div|p|li|pre|tr)>', '\n', body)
    return [l.strip() for l in html.unescape(re.sub(r'<[^>]+>', '', body)).replace('\xa0', ' ').splitlines()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('out_dir')
    ap.add_argument('--threads', type=int, default=50)
    ap.add_argument('--before', required=True, help='search date for older threads, e.g. 2026/08/14 (the oldest front-page date)')
    opts = ap.parse_args()
    ids = thread_ids(get(GROUP))
    print(f'front page: {len(ids)} threads')
    older = thread_ids(get(f'{GROUP}/search?' + urllib.parse.urlencode({'q': f'before:{opts.before}'})))
    ids = list(dict.fromkeys(ids + older))[:opts.threads]
    print(f'with search: {len(ids)} threads')
    seen = {}
    for tid in ids:
        for s in thread_lines(get(f'{GROUP}/c/{tid}')):
            m = LEAD.match(s)
            if m and m.group(2).lower().strip('.,:') not in PROSE and not s.endswith('?'):
                seen.setdefault(s, tid)
    corpus = [{'id': f'L{i:02d}', 'thread': t, 'paste': s} for i, (s, t) in enumerate(seen.items(), 1)]
    out = Path(opts.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'corpus.json').write_text(json.dumps(corpus, indent=1), encoding='utf-8')
    print(f'{len(corpus)} command lines -> {out / "corpus.json"} (review for prose before trusting counts)')


if __name__ == '__main__':
    main()
