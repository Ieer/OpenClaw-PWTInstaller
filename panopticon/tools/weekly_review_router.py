from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .managed_execution_worker import ArtifactStore
from .pilot_weekly_review import build_weekly_review_graph


class RouteError(ValueError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


class WeeklyReviewRouter:
    def __init__(self, state_dir: Path, api_url: str, api_token: str, *, provider: str,
                 graph_factory=None, client_factory=None):
        self.state_dir = state_dir
        self.store = ArtifactStore(state_dir / "artifacts")
        self.database = state_dir / "routes.sqlite"
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.threads = {}
        self.provider = provider
        self.client_factory = client_factory or (lambda: httpx.Client(
            base_url=api_url, headers={"Authorization": f"Bearer {api_token}"},
            timeout=10, trust_env=False, follow_redirects=False))
        self.graph_factory = graph_factory or (lambda saver, client: build_weekly_review_graph(
            saver, client=client, provider=provider))
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS runs (request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, "
                               "thread_id TEXT NOT NULL, input_ref TEXT NOT NULL, origin_session TEXT, status TEXT NOT NULL, "
                               "created_at REAL NOT NULL, error_type TEXT)")

    def row(self, request_id: str) -> dict:
        with sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM runs WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            raise RouteError(404, "review request not found")
        return dict(row)

    def checkpoint(self, row: dict) -> Path:
        directory = self.state_dir / "checkpoints"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        return directory / f"{row['thread_id']}.sqlite"

    def update(self, request_id: str, status: str, error_type: str | None = None) -> None:
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE runs SET status=?, error_type=? WHERE request_id=? AND status != 'CANCELLED'",
                               (status, error_type, request_id))

    def start(self, request_id: str) -> None:
        with self.lock:
            self.threads = {key: thread for key, thread in self.threads.items() if thread.is_alive()}
            if request_id in self.threads and self.threads[request_id].is_alive():
                return
            if sum(thread.is_alive() for thread in self.threads.values()) >= 2:
                raise RouteError(429, "two review requests are already active")
            thread = threading.Thread(target=self.drive, args=(request_id,), daemon=True)
            self.threads[request_id] = thread
            thread.start()

    def submit(self, body: dict) -> dict:
        if self.stop.is_set():
            raise RouteError(503, "review intake is stopping")
        if not isinstance(body, dict) or set(body) - {"request_id", "input_text", "origin_session", "allow_role_sharing"}:
            raise RouteError(422, "unsupported review request fields")
        request_id = body.get("request_id", "")
        if not isinstance(request_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", request_id):
            raise RouteError(422, "a stable lowercase request_id is required")
        text = body.get("input_text")
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 8192:
            raise RouteError(422, "input_text must be non-empty and at most 8 KiB")
        if body.get("allow_role_sharing") is not True:
            raise RouteError(422, "explicit three-role input sharing acknowledgement is required")
        origin = body.get("origin_session")
        if origin is not None and (not isinstance(origin, str) or len(origin) > 128):
            raise RouteError(422, "invalid origin session reference")
        fingerprint = hashlib.sha256(json.dumps({"input_text": text, "origin_session": origin},
                                                sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            with sqlite3.connect(self.database) as connection:
                previous = connection.execute("SELECT fingerprint FROM runs WHERE request_id=?", (request_id,)).fetchone()
                if previous:
                    if previous[0] != fingerprint:
                        raise RouteError(409, "request_id reused with different input")
                    return self.status(request_id)
                active = sum(thread.is_alive() for thread in self.threads.values())
                recent = connection.execute("SELECT count(*) FROM runs WHERE created_at>?", (time.time() - 60,)).fetchone()[0]
                if active >= 2 or recent >= 5:
                    raise RouteError(429, "review intake capacity reached")
                thread_id = "route-" + hashlib.sha256(request_id.encode()).hexdigest()[:32]
                ref = self.store.write("input-" + hashlib.sha256(text.encode()).hexdigest()[:32] + ".md", text)
                connection.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)",
                                   (request_id, fingerprint, thread_id, ref, origin, "QUEUED", time.time(), None))
            self.start(request_id)
            return self.status(request_id)

    def status(self, request_id: str) -> dict:
        with self.lock:
            row = self.row(request_id)
            values = {}
            path = self.checkpoint(row)
            if path.exists():
                with self.client_factory() as client, sqlite3.connect(path, check_same_thread=False) as connection:
                    graph = self.graph_factory(SqliteSaver(connection), client)
                    state = graph.get_state({"configurable": {"thread_id": row["thread_id"]}})
                    values = state.values
                    if not state.next and values and row["status"] == "REVIEW":
                        self.update(request_id, "APPROVED" if values.get("approved") else "REJECTED")
                        row = self.row(request_id)
            return {"request_id": request_id, "thread_id": row["thread_id"], "status": row["status"],
                    "origin_session": row["origin_session"], "artifact_refs": values.get("artifact_refs", []),
                    "approved": bool(values.get("approved", False)), "external_actions": False,
                    "error_type": row["error_type"]}

    def drive(self, request_id: str) -> None:
        try:
            with self.client_factory() as client:
                row = self.row(request_id)
                with sqlite3.connect(self.checkpoint(row), check_same_thread=False) as connection:
                    graph = self.graph_factory(SqliteSaver(connection), client)
                    config = {"configurable": {"thread_id": row["thread_id"]}, "recursion_limit": 10}
                    with self.lock:
                        if self.stop.is_set() or self.row(request_id)["status"] == "CANCELLED":
                            return
                        self.update(request_id, "RUNNING")
                        state = graph.get_state(config)
                        if not state.values:
                            result = graph.invoke({"input_refs": [row["input_ref"]], "artifact_refs": [], "approved": False}, config)
                        else:
                            result = {**state.values, "__interrupt__": [item for task in state.tasks for item in task.interrupts]}
                    while result.get("__interrupt__") and not self.stop.is_set():
                        pending = result["__interrupt__"][0].value
                        if pending.get("kind") == "human_review":
                            with self.lock:
                                self.update(request_id, "REVIEW")
                            return
                        if pending.get("kind") != "job_wait":
                            raise ValueError("unsupported workflow interrupt")
                        with self.lock:
                            if self.row(request_id)["status"] == "CANCELLED":
                                return
                        response = client.get(f"/v1/execution/jobs/{pending['job_id']}")
                        response.raise_for_status()
                        job = response.json()
                        if job["status"] in {"FAILED", "CANCELLED"}:
                            raise ValueError("workflow job did not succeed")
                        if job["status"] == "SUCCEEDED":
                            with self.lock:
                                if self.stop.is_set() or self.row(request_id)["status"] == "CANCELLED":
                                    return
                                result = graph.invoke(Command(resume={"action": "continue"}), config)
                        else:
                            self.stop.wait(2)
        except Exception as error:
            with self.lock:
                self.update(request_id, "FAILED", type(error).__name__)

    def cancel(self, request_id: str) -> dict:
        with self.lock:
            row = self.row(request_id)
            if row["status"] in {"APPROVED", "REJECTED", "FAILED", "CANCELLED"}:
                return self.status(request_id)
            path = self.checkpoint(row)
            if path.exists():
                with self.client_factory() as client, sqlite3.connect(path, check_same_thread=False) as connection:
                    graph = self.graph_factory(SqliteSaver(connection), client)
                    state = graph.get_state({"configurable": {"thread_id": row["thread_id"]}})
                    for task in state.tasks:
                        for item in task.interrupts:
                            if item.value.get("kind") == "job_wait":
                                response = client.post(f"/v1/execution/jobs/{item.value['job_id']}/cancel")
                                response.raise_for_status()
            with sqlite3.connect(self.database) as connection:
                connection.execute("UPDATE runs SET status='CANCELLED' WHERE request_id=?", (request_id,))
            return self.status(request_id)

    def recover(self) -> None:
        with sqlite3.connect(self.database) as connection:
            requests = connection.execute("SELECT request_id FROM runs WHERE status IN ('QUEUED','RUNNING') ORDER BY created_at").fetchall()
        for (request_id,) in requests[:2]:
            self.start(request_id)

    def close(self) -> None:
        self.stop.set()
        for thread in list(self.threads.values()):
            thread.join(timeout=15)


def create_route_server(router: WeeklyReviewRouter, token: str, *, host="0.0.0.0", port=9190):
    if len(token) < 32:
        raise ValueError("a dedicated route credential is required")

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, format, *args):
            pass

        def handle_request(self):
            try:
                authorization = self.headers.get("Authorization", "")
                if not hmac.compare_digest(authorization, "Bearer " + token):
                    raise RouteError(403, "invalid route credential")
                path = self.path.rstrip("/")
                if self.command == "POST" and path == "/v1/weekly-reviews":
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 16384:
                        raise RouteError(413, "request body exceeds intake budget")
                    result = router.submit(json.loads(self.rfile.read(length)))
                elif self.command == "GET" and path.startswith("/v1/weekly-reviews/"):
                    result = router.status(path.rsplit("/", 1)[-1])
                elif self.command == "POST" and path.endswith("/cancel") and path.startswith("/v1/weekly-reviews/"):
                    result = router.cancel(path.split("/")[-2])
                else:
                    raise RouteError(404, "route not found; approval is operator-only")
                status = 200
            except RouteError as error:
                status, result = error.status, {"error": str(error)}
            except Exception:
                status, result = 400, {"error": "invalid review request"}
            data = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = handle_request
        do_POST = handle_request

    return ThreadingHTTPServer((host, port), Handler)