# bypy Command Recipes

## Install and Authorize

```bash
pip install bypy
bypy info
```

Run `bypy info` once to trigger the authorization flow.

## Inspect Remote State

Show help and available commands:

```bash
bypy
bypy help compare
```

List files in the app root:

```bash
bypy list
```

Check quota and account info:

```bash
bypy info
```

## Upload and Backup

Upload one file:

```bash
bypy upload ./report.zip /exchange/report.zip
```

Upload a folder recursively:

```bash
bypy upload ./project-backup /backups/project-backup
```

Sync a local folder upward:

```bash
bypy syncup ./data /backups/data
```

Use multiprocessing if the environment supports it:

```bash
bypy --processes 4 syncup ./data /backups/data
```

## Download and Restore

Download a remote file:

```bash
bypy downfile /exchange/report.zip ./restored/
```

Download a remote folder:

```bash
bypy downdir /backups/data ./recovered-data
```

Sync remote down to local:

```bash
bypy syncdown /backups/data ./recovered-data
```

Restore from recycle bin:

```bash
bypy restore /backups/data/archive.zip
```

## Compare Before Syncing

Compare remote and local folders:

```bash
bypy compare /backups/data ./data
```

This is the preferred dry-check before any sync flow.

## Remote Organization

Create a remote directory:

```bash
bypy mkdir /exchange
```

Move or rename remotely:

```bash
bypy move /exchange/report.zip /archive/report-2026-03.zip
```

Copy remotely:

```bash
bypy copy /exchange/report.zip /archive/report-copy.zip
```

Delete remotely:

```bash
bypy delete /exchange/report.zip
```

## Debugging

Add verbose progress output:

```bash
bypy -v syncup ./data /backups/data
```

Add debug logging:

```bash
bypy -d compare /backups/data ./data
```

Add HTTP-level debug logs only when necessary:

```bash
bypy -ddd list
```
