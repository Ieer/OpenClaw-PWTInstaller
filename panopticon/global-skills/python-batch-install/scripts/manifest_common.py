from __future__ import annotations

from pathlib import Path


def parse_scalar(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_simple_yaml(text: str):
    raw_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        raw_lines.append(line.rstrip("\n"))

    def next_significant(index: int):
        for candidate in raw_lines[index + 1 :]:
            stripped = candidate.strip()
            if stripped and not stripped.startswith("#"):
                return candidate
        return None

    root = {}
    stack = [(-1, root)]

    for index, line in enumerate(raw_lines):
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]

        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if not isinstance(parent, list):
                raise ValueError(f"Unexpected list item: {line}")
            if ":" in item:
                key, _, value = item.partition(":")
                entry = {key.strip(): parse_scalar(value)}
                parent.append(entry)
                stack.append((indent, entry))
            else:
                parent.append(parse_scalar(item))
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"Unexpected mapping item: {line}")

        if value:
            parent[key] = parse_scalar(value)
            continue

        upcoming = next_significant(index)
        if upcoming is None:
            parent[key] = {}
            continue

        next_indent = len(upcoming) - len(upcoming.lstrip(" "))
        next_stripped = upcoming.strip()
        if next_indent <= indent:
            parent[key] = {}
            continue

        container = [] if next_stripped.startswith("- ") else {}
        parent[key] = container
        stack.append((indent, container))

    return root


def load_manifest(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return parse_simple_yaml(text)
    return yaml.safe_load(text)