# Publishing bypy

## Pre-Publication Checklist

- `SKILL.md` exists and uses English frontmatter
- `README.md` documents install, layout, and common workflows
- `LICENSE` is included
- `CHANGELOG.md` includes the current release entry
- Demo and reference files are present
- No secrets, tokens, or private paths are committed

## Suggested Repository Layout

```text
bypy/
├── SKILL.md
├── README.md
├── LICENSE
├── CHANGELOG.md
├── PUBLISHING.md
├── _meta.json
├── examples/
├── sample_codes/
└── references/
```

## GitHub Repository Description

```text
OpenClaw skill for Baidu Netdisk backup, sync, restore, compare, and file exchange workflows using bypy.
```

## Suggested GitHub Topics

```text
openclaw, openclaw-skill, bypy, baidu-netdisk, baidu-pan, backup, sync, restore, file-transfer, powershell
```

## GitHub Release Title

```text
v0.1.0 - Initial public release of the bypy OpenClaw skill
```

## GitHub Release Notes

```md
## Highlights

- Added a publish-ready OpenClaw skill for Baidu Netdisk workflows using bypy
- Covered upload, download, sync, compare, restore, and exchange use cases
- Added command recipes and safety notes for risky operations
- Included a runnable PowerShell demo for backup and restore

## Notes

- `bypy` only works within the `/apps/bypy` app directory on Baidu Netdisk
- First-time use requires authorization through a command such as `bypy info`
- Upstream bypy is in maintenance mode and may exhibit MD5-related verification caveats
```

## Suggested ClawHub Metadata

- Slug: `bypy`
- Name: `bypy`
- Version: `0.1.0`
- Tags: `latest,bypy,baidu-netdisk,backup,sync,restore,file-exchange`

## Example Publish Command

```bash
clawhub publish ./bypy \
  --slug bypy \
  --name "bypy" \
  --version 0.1.0 \
  --tags latest,bypy,baidu-netdisk,backup,sync,restore,file-exchange \
  --changelog "Initial public release of the bypy OpenClaw skill"
```

## Submission Notes

- Confirm `SKILL.md` frontmatter remains concise and trigger-oriented
- Confirm README highlights the `/apps/bypy` scope limitation
- Confirm the demo script and references are included
- Keep version numbers aligned across changelog, release notes, and `_meta.json`
