# Backup and Sync Example

## Scenario

A user wants to back up a local project folder to Baidu Netdisk, compare differences before syncing, and later pull the backup back down to a recovery directory.

## Recommended Sequence

Install and authorize:

```bash
pip install bypy
bypy info
```

Create a backup destination:

```bash
bypy mkdir /backups
```

Compare local data with the remote destination first:

```bash
bypy compare /backups/project ./project
```

Sync local project up to the cloud:

```bash
bypy syncup ./project /backups/project
```

Recover the project later to a local directory:

```bash
bypy syncdown /backups/project ./project-recovery
```

## Exchange Pattern

Upload a file into a shared exchange area:

```bash
bypy upload ./handoff.zip /exchange/handoff.zip
```

Archive it after consumption:

```bash
bypy move /exchange/handoff.zip /archive/handoff-2026-03-14.zip
```

## Notes

- All remote paths are inside `/apps/bypy`.
- Compare before sync is the safer default.
- If verification looks wrong, mention the upstream MD5 caveat before trusting destructive operations.
