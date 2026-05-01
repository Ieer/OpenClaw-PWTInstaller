#!/usr/bin/env python3
"""Verify nox workspace required directories exist and are writable."""
import os
import sys
import tempfile

REQUIRED_DIRS = ["artifacts", "sources", "state", "memory"]

def check():
    errors = []
    for d in REQUIRED_DIRS:
        if not os.path.isdir(d):
            errors.append(f"MISSING: {d}")
        elif not os.access(d, os.W_OK):
            errors.append(f"NOT_WRITABLE: {d}")
        else:
            # quick write test
            try:
                tf = tempfile.NamedTemporaryFile(dir=d, delete=True)
                tf.close()
            except OSError as e:
                errors.append(f"WRITE_FAIL: {d}: {e}")
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(2)
    print("Workspace contract OK")
    sys.exit(0)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    check()
