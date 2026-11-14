from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Nox draft review route: submit, status, or cancel only")
    parser.add_argument("action", choices=("submit", "status", "cancel"))
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--origin-session")
    parser.add_argument("--confirm-role-sharing", action="store_true")
    args = parser.parse_args()
    if not args.request_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in args.request_id):
        parser.error("request-id must be a stable lowercase task identifier")
    path = Path(os.getenv("WEEKLY_ROUTE_CREDENTIAL_FILE") or Path.home() / ".openclaw" / "weekly-route.json")
    try:
        credential = json.loads(path.read_text())
        endpoint = credential["api_url"].rstrip("/") + "/v1/weekly-reviews"
        headers = {"Authorization": "Bearer " + credential["token"], "Content-Type": "application/json"}
        if args.action == "submit":
            if not args.input_file or not args.confirm_role_sharing:
                parser.error("submit requires explicit input-file and three-role sharing confirmation")
            body = {"request_id": args.request_id, "input_text": args.input_file.read_text(encoding="utf-8"),
                    "allow_role_sharing": True, "origin_session": args.origin_session}
            request = urllib.request.Request(endpoint, headers=headers, data=json.dumps(body, ensure_ascii=False).encode("utf-8"))
        else:
            endpoint += "/" + args.request_id + ("/cancel" if args.action == "cancel" else "")
            request = urllib.request.Request(endpoint, headers=headers, method="POST" if args.action == "cancel" else "GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            value = json.loads(response.read())
        print(json.dumps(value, ensure_ascii=False))
    except Exception:
        parser.exit(1, "weekly route failed; check task ID, private configuration, and worker status\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())