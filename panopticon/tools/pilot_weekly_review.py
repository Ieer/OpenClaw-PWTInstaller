from __future__ import annotations

import argparse
import json
import operator
import os
import sqlite3
import time
from pathlib import Path
from typing import Annotated, TypedDict

import httpx
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ReviewState(TypedDict):
    input_refs: list[str]
    artifact_refs: Annotated[list[str], operator.add]
    approved: bool


def validate_artifacts(result: dict) -> list[str]:
    refs = result.get("artifact_refs")
    if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref.strip() for ref in refs):
        raise ValueError("each step must return non-empty artifact_refs")
    if len(refs) > 20 or any(len(ref) > 2048 for ref in refs):
        raise ValueError("artifact references exceed the pilot budget")
    return refs


def build_weekly_review_graph(checkpointer, *, fixtures: dict | None = None, client=None, provider: str | None = None):
    def stage(agent: str):
        def run(state: ReviewState, config):
            if fixtures is not None:
                result = fixtures[agent]
            else:
                thread_id = str(config["configurable"]["thread_id"])
                response = client.post("/v1/execution/jobs", json={
                    "agent_slug": agent, "idempotency_key": f"weekly:{thread_id}:{agent}",
                    "provider": provider, "estimated_tokens": 20000, "max_attempts": 1,
                    "payload": {"workflow": "weekly-review", "step": agent, "mode": "draft-only",
                                "input_refs": state["input_refs"] + state.get("artifact_refs", []),
                                "expected_output": "artifact_refs; no external actions"},
                })
                response.raise_for_status()
                job = response.json()
                if job["status"] in {"FAILED", "CANCELLED"}:
                    raise RuntimeError(f"job {job['id']} requires operator recovery")
                if job["status"] != "SUCCEEDED":
                    interrupt({"kind": "job_wait", "agent": agent, "job_id": job["id"]})
                    response = client.get(f"/v1/execution/jobs/{job['id']}")
                    response.raise_for_status()
                    job = response.json()
                    if job["status"] != "SUCCEEDED":
                        raise RuntimeError("job is not complete; resume only after the worker finishes")
                result = job["result"]
            return {"artifact_refs": validate_artifacts(result)}
        return run

    def review(state: ReviewState):
        decision = interrupt({"kind": "human_review", "artifact_refs": state["artifact_refs"]})
        if not isinstance(decision, dict) or decision.get("action") not in {"approve", "reject"}:
            raise ValueError("an explicit approve or reject decision is required")
        return {"approved": decision["action"] == "approve"}

    builder = StateGraph(ReviewState)
    for agent in ("metrics", "nox", "writing"):
        builder.add_node(agent, stage(agent))
    builder.add_node("review", review)
    builder.add_edge(START, "metrics")
    builder.add_edge("metrics", "nox")
    builder.add_edge("nox", "writing")
    builder.add_edge("writing", "review")
    builder.add_edge("review", END)
    return builder.compile(checkpointer=checkpointer)


def wait_for_jobs(graph, result: dict, config: dict, client, *, timeout: float = 900,
                  poll_seconds: float = 2) -> dict:
    deadline = time.monotonic() + timeout
    while result.get("__interrupt__"):
        pending = result["__interrupt__"][0].value
        if pending.get("kind") != "job_wait":
            break
        response = client.get(f"/v1/execution/jobs/{pending['job_id']}")
        response.raise_for_status()
        job = response.json()
        if job["status"] in {"FAILED", "CANCELLED"}:
            raise RuntimeError(f"job {job['id']} failed; checkpoint retained for operator recovery")
        if job["status"] == "SUCCEEDED":
            result = graph.invoke(Command(resume={"action": "continue"}), config=config)
            continue
        if time.monotonic() >= deadline:
            raise TimeoutError("worker wait timed out; resume the retained checkpoint later")
        time.sleep(min(poll_seconds, max(0, deadline - time.monotonic())))
    return result


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="Checkpointed draft-only weekly review pilot")
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--api-url")
    parser.add_argument("--provider")
    parser.add_argument("--input-ref", action="append", default=[])
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path(os.getenv("MC_WORKER_STATE_DIR", "/data")))
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--wait-timeout", type=float, default=900)
    parser.add_argument("--resume", choices=("continue", "approve", "reject"))
    args = parser.parse_args()
    if len(args.thread_id) > 64:
        parser.error("thread-id must not exceed 64 characters")
    if bool(args.fixtures) == bool(args.api_url):
        parser.error("select exactly one of --fixtures or --api-url")
    token = os.getenv("MC_AUTH_TOKEN")
    if args.api_url and not token:
        parser.error("queue mode requires MC_AUTH_TOKEN in the environment")
    if args.api_url and not args.provider:
        parser.error("queue mode requires --provider matching the worker role configuration")
    if args.wait and (not args.api_url or args.wait_timeout <= 0):
        parser.error("--wait requires queue mode and a positive timeout")
    if args.input_file:
        if args.resume or not args.api_url:
            parser.error("--input-file requires a new queue-mode thread")
        if __package__:
            from .managed_execution_worker import ArtifactStore
        else:
            from managed_execution_worker import ArtifactStore
        args.input_ref.append(ArtifactStore(args.state_dir / "artifacts").stage(args.input_file))
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    fixtures = json.loads(args.fixtures.read_text(encoding="utf-8")) if args.fixtures else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with sqlite3.connect(args.checkpoint, check_same_thread=False) as connection, \
         httpx.Client(base_url=args.api_url or "http://offline.invalid", headers=headers, timeout=10,
                      trust_env=False, follow_redirects=False) as client:
        graph = build_weekly_review_graph(SqliteSaver(connection), fixtures=fixtures, client=client, provider=args.provider)
        config = {"configurable": {"thread_id": args.thread_id}, "recursion_limit": 10}
        current = graph.get_state(config)
        if args.resume:
            if not current.next:
                parser.error("this thread has no pending checkpoint to resume")
            value = Command(resume={"action": args.resume})
        else:
            if current.values:
                parser.error("thread already exists; use --resume or a new thread-id")
            value = {"input_refs": args.input_ref, "artifact_refs": [], "approved": False}
        result = graph.invoke(value, config=config)
        if args.wait:
            result = wait_for_jobs(graph, result, config, client, timeout=args.wait_timeout)
        pending = result.get("__interrupt__", ())
        print(json.dumps({"thread_id": args.thread_id, "artifact_refs": result.get("artifact_refs", []),
                          "approved": result.get("approved", False),
                          "pending": [item.value for item in pending],
                          "external_actions": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())