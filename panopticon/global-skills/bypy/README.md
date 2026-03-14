# bypy

Publish-ready OpenClaw skill package for backup, sync, restore, and data exchange workflows using the `bypy` Baidu Netdisk CLI.

## Features

- Upload local files and folders to Baidu Netdisk
- Download and restore remote files to local storage
- Sync local to remote and remote to local
- Compare cloud and local directory state before moving data
- Support simple exchange workflows through the app-scoped cloud directory
- Document upstream limitations and operational risks clearly

## Repository Layout

```text
bypy/
├── SKILL.md
├── README.md
├── LICENSE
├── CHANGELOG.md
├── PUBLISHING.md
├── _meta.json
├── examples/
│   └── backup-and-sync.md
├── sample_codes/
│   └── demo-backup-restore.ps1
└── references/
    ├── command-recipes.md
    └── safety-and-limitations.md
```

## Requirements

- Python available in the environment
- `pip install bypy`
- Baidu Netdisk account and successful first-time authorization
- UTF-8 locale recommended by the upstream project

## Installation

```bash
pip install bypy
```

Then trigger authorization once:

```bash
bypy info
```

## Common Use Cases

- Back up project folders into Baidu Netdisk
- Pull shared material down to a local workspace
- Compare remote and local state before synchronization
- Restore deleted files from the remote recycle bin
- Use the app directory as a simple cloud exchange area

## Included Demo

- [sample_codes/demo-backup-restore.ps1](./sample_codes/demo-backup-restore.ps1) provides a directly runnable PowerShell example for compare, backup, and restore.

## Important Limitation

`bypy` only accesses the Baidu Netdisk app directory at `/apps/bypy`.

## License

MIT License. See [LICENSE](./LICENSE).

Upstream project: [houtianze/bypy](https://github.com/houtianze/bypy).
Use the upstream README for the full command surface beyond this packaged skill summary.

