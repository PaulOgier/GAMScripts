"""Paste gam lines into gamcheck's prompt through a real terminal, as a user would.

Runs COMMAND... inside a pseudo-terminal (use `ssh -tt host python gamcheck.py`
to reach a VM's own terminal), types each case line, then an empty line, and
reports whether the verdict appeared and the line's last word reached the report.
Usage: python3 ttypaste.py COMMAND...
"""
import os
import pty
import select
import sys
import time

CASES = {}
for n in (5, 45, 90):
    users = ','.join(f'user{i:04d}@example.com' for i in range(n))
    CASES[n] = f'gam users {users} delete messages query "older_than:1y" doit'
CASES['multi'] = 'gam print users\ngam user bob@example.com delete messages query "older_than:1y" doit'

ok = True
for name, text in CASES.items():
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(sys.argv[1], sys.argv[1:])
    out, end, sent = b'', time.time() + 25, 0
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.3)
        if r:
            try:
                c = os.read(fd, 65536)
            except OSError:
                break
            if not c:
                break
            out += c
        if sent == 0 and b'empty line' in out:
            for ln in text.split('\n'):
                os.write(fd, ln.encode() + b'\r')
                time.sleep(0.3)
            os.write(fd, b'\r')
            sent = 1
    t = out.decode(errors='replace')
    rep = t[t.find('VERDICT'):] if 'VERDICT' in t else ''
    last = text.split('\n')[-1].split(',')[-1][:20]
    good = 'VERDICT: DESTRUCTIVE' in rep and last in rep.replace('\r\n', '').replace('\n', '')
    ok &= good
    print(f'{name!s:>6} len={len(text):5} prompt={sent==1} verdict={"VERDICT: DESTRUCTIVE" in rep} tail_seen={last in rep} -> {"PASS" if good else "FAIL"}')
    if not good:
        print('   last output:', repr(t[-300:]))
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass
    os.waitpid(pid, 0)
sys.exit(0 if ok else 1)
