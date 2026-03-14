---
name: bypy
description: Backup, sync, download, upload, compare, and exchange files with Baidu Netdisk using bypy. Use when the user wants to back up folders to Baidu Netdisk, restore files, sync local and remote directories, compare cloud vs local contents, or move data through the `/apps/bypy` app directory.
license: MIT
metadata:
  openclaw:
    homepage: https://github.com/houtianze/bypy
    os:
      - win32
      - darwin
      - linux
    requires:
      anyBins:
        - python
---

# bypy

Use `bypy` as a practical file transport and backup layer for Baidu Netdisk.

## When to Use

- The user wants to back up local files or folders to Baidu Netdisk.
- The user wants to pull remote files down for restore or exchange.
- The user needs to compare local and cloud directory state before syncing.
- The user wants a CLI-based workflow for personal cloud storage, especially on servers or headless machines.
- The user needs safe file exchange through the Baidu Netdisk app directory.

## Quick Reference

| Need | bypy action |
| ---- | ----------- |
| Check help and commands | `bypy` or `bypy help <command>` |
| Authorize first-time access | run `bypy info` and follow the prompts |
| Show remote listing | `bypy list` |
| Upload one file or folder | `bypy upload <local> <remote>` |
| Sync local to remote | `bypy syncup <localdir> <remotedir>` |
| Sync remote to local | `bypy syncdown <remotedir> <localdir>` |
| Download a folder | `bypy downdir <remote> <local>` |
| Compare local vs remote | `bypy compare <remote> <local>` |
| Check quota | `bypy info` |
| Restore from recycle bin | `bypy restore <remote-path>` |

## Workflow

1. Confirm that the user is working with Baidu Netdisk and understands bypy only accesses `/apps/bypy`.
2. Ensure Python is available and install `bypy` if needed.
3. Run an authorization-triggering command such as `bypy info` for first-time setup.
4. Choose the right operation: upload, download, sync, compare, or restore.
5. For potentially destructive sync or delete workflows, compare first.
6. Report what changed, what was skipped, and any risk or limitation encountered.

## Safety Rules

- Always mention that bypy works inside `/apps/bypy` on Baidu Netdisk, not the entire drive.
- Prefer `compare` before `syncup`, `syncdown`, or delete-like flows.
- Treat delete, move, and sync-with-delete operations as high risk.
- Warn that bypy is in maintenance mode upstream, and some verification behavior may be affected by Baidu-side MD5 issues.
- For suspicious compare or verification results, mention the upstream note about trying `bypy==1.6.10`.

## References

- Command recipes: ./references/command-recipes.md
- Safety and limitations: ./references/safety-and-limitations.md
- Backup example: ./examples/backup-and-sync.md