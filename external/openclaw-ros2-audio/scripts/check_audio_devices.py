#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess


def run(command: list[str]) -> None:
    print(f"\n$ {' '.join(command)}")
    if shutil.which(command[0]) is None:
        print(f"SKIP: {command[0]} not found")
        return
    proc = subprocess.run(command, check=False, capture_output=True, text=True, timeout=8)
    output = (proc.stdout or proc.stderr or "").strip()
    print(output or "<no output>")


def main() -> None:
    run(["arecord", "-l"])
    run(["aplay", "-l"])
    run(["pactl", "list", "short", "sources"])
    run(["pactl", "list", "short", "sinks"])


if __name__ == "__main__":
    main()
