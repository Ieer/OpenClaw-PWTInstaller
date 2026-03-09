# Workspaces Runtime Tracked Audit (2026-03-09)

## Summary

- Scope: `panopticon/workspaces/**` 已被 Git 跟踪文件
- Total tracked files in scope: `111`
- Runtime-localization candidates (tracked but should be local): `13`
- Distribution:
  - `metrics`: 1
  - `nox`: 7
  - `personal`: 1
  - `trades`: 4

## Candidate file list

1. `panopticon/workspaces/metrics/artifacts/song-ai-human-era/lyrics.md`
2. `panopticon/workspaces/nox/artifacts/lyrics-collaboration-2026-02-25/artifact.json`
3. `panopticon/workspaces/nox/artifacts/lyrics-collaboration-2026-02-25/artifact.md`
4. `panopticon/workspaces/nox/artifacts/lyrics-collaboration-2026-02-25/execution-plan-route-01.md`
5. `panopticon/workspaces/nox/artifacts/lyrics-collaboration-2026-02-25/option-01-collaboration.md`
6. `panopticon/workspaces/nox/artifacts/lyrics-collaboration-2026-02-25/option-02-reflection.md`
7. `panopticon/workspaces/nox/artifacts/lyrics-collaboration-2026-02-25/option-03-satire.md`
8. `panopticon/workspaces/nox/sources/lyrics-collaboration-2026-02-25/market-insights.md`
9. `panopticon/workspaces/personal/artifacts/daily-2026-03-02.md`
10. `panopticon/workspaces/trades/artifacts/daily-watchlist-2026-03-01.md`
11. `panopticon/workspaces/trades/artifacts/daily-watchlist-2026-03-02.md`
12. `panopticon/workspaces/trades/artifacts/daily-watchlist-2026-03-03/artifact.json`
13. `panopticon/workspaces/trades/artifacts/daily-watchlist-2026-03-03/artifact.md`

## Directly executable cleanup commands

### 1) Dry-run preview (recommended first)

```bash
git -C /home/pi/OpenClaw-PWTInstaller ls-files -z panopticon/workspaces \
| /home/pi/OpenClaw-PWTInstaller/.venv/bin/python - <<'PY' \
| xargs -0 -r -I{} echo git -C /home/pi/OpenClaw-PWTInstaller rm --cached -- '{}'
import re, subprocess, sys
repo='/home/pi/OpenClaw-PWTInstaller'
out=subprocess.check_output(['git','-C',repo,'ls-files','-z','panopticon/workspaces'])
files=[x for x in out.decode('utf-8',errors='replace').split('\0') if x]
patterns=[
 re.compile(r'^panopticon/workspaces/[^/]+/(inbox|outbox|artifacts|state|sources)/'),
 re.compile(r'^panopticon/workspaces/[^/]+/\\.openclaw/'),
 re.compile(r'^panopticon/workspaces/[^/]+/memory/\\d{4}-\\d{2}-\\d{2}\\.md$'),
 re.compile(r'^panopticon/workspaces/[^/]+/memory/heartbeat-state\\.json$'),
 re.compile(r'^panopticon/workspaces/[^/]+/node_modules/'),
 re.compile(r'^panopticon/workspaces/[^/]+/thumbnails/'),
 re.compile(r'^panopticon/workspaces/[^/]+/.*\\.pptx$'),
]
for f in files:
    if any(p.search(f) for p in patterns):
        sys.stdout.buffer.write(f.encode('utf-8')+b'\0')
PY
```

### 2) Execute untracking (keep local files on disk)

```bash
git -C /home/pi/OpenClaw-PWTInstaller ls-files -z panopticon/workspaces \
| /home/pi/OpenClaw-PWTInstaller/.venv/bin/python - <<'PY' \
| xargs -0 -r git -C /home/pi/OpenClaw-PWTInstaller rm --cached --
import re, subprocess, sys
repo='/home/pi/OpenClaw-PWTInstaller'
out=subprocess.check_output(['git','-C',repo,'ls-files','-z','panopticon/workspaces'])
files=[x for x in out.decode('utf-8',errors='replace').split('\0') if x]
patterns=[
 re.compile(r'^panopticon/workspaces/[^/]+/(inbox|outbox|artifacts|state|sources)/'),
 re.compile(r'^panopticon/workspaces/[^/]+/\\.openclaw/'),
 re.compile(r'^panopticon/workspaces/[^/]+/memory/\\d{4}-\\d{2}-\\d{2}\\.md$'),
 re.compile(r'^panopticon/workspaces/[^/]+/memory/heartbeat-state\\.json$'),
 re.compile(r'^panopticon/workspaces/[^/]+/node_modules/'),
 re.compile(r'^panopticon/workspaces/[^/]+/thumbnails/'),
 re.compile(r'^panopticon/workspaces/[^/]+/.*\\.pptx$'),
]
for f in files:
    if any(p.search(f) for p in patterns):
        sys.stdout.buffer.write(f.encode('utf-8')+b'\0')
PY
```

### 3) Verify staged deletions are only runtime files

```bash
git -C /home/pi/OpenClaw-PWTInstaller diff --cached --name-status
```

### 4) Optional rollback (before commit)

```bash
git -C /home/pi/OpenClaw-PWTInstaller restore --staged .
```

## Notes

- This cleanup is index-only (`rm --cached`), local files remain on disk.
- Existing `.gitignore` rules now cover these runtime paths for future protection.
