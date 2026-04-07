# bypy Safety and Limitations

## Scope Limitation

Upstream bypy only accesses the Baidu Netdisk app directory:

```text
/apps/bypy
```

It does not provide unrestricted access to the entire user drive.

## First-Time Authorization

The first real command, often `bypy info`, will trigger an authorization flow. This is expected and normally only required once per config directory.

## UTF-8 Requirement

The upstream project strongly recommends a UTF-8 locale, especially for non-ASCII file names.

## Maintenance Mode

The upstream bypy project is in maintenance mode. That means it is still useful, but you should avoid assuming active feature development.

## MD5 / Verification Caveat

The upstream project explicitly warns that Baidu PCS may return incorrect MD5 values for remote files in some situations. This can affect compare or verification-related workflows.

If compare or verification behaves suspiciously, mention the upstream workaround note:

```bash
pip install bypy==1.6.10
```

Do not automatically downgrade unless the user asks.

## High-Risk Operations

Treat these as potentially destructive:

- `delete`
- `move`
- `syncup` with delete behavior
- `syncdown` with delete behavior
- any workflow using `--move`

Preferred safe order:

1. `list` or `info`
2. `compare`
3. `upload`, `download`, `syncup`, or `syncdown`
4. `delete` or `move` only after confirmation

## Backup Guidance

For backup tasks:

- create a dated remote target path
- compare before overwriting
- prefer upload or syncup over destructive remote edits
- keep restore paths explicit when downloading back

## Data Exchange Guidance

For exchange workflows:

- use dedicated remote folders such as `/exchange`, `/incoming`, `/archive`
- move completed files into an archive path after successful transfer
- avoid deleting originals before verifying the receiving side
