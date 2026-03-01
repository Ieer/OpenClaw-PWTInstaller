from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, Response
import httpx
import asyncio
from redis.asyncio import Redis

from .config import Settings, load_settings
from .db import create_engine, create_session_factory
from .models import agent_skill_mappings, comments, events, tasks
from .schemas import (
    AgentSkillMappingOut,
    BoardColumn,
    BoardOut,
    CommentCreate,
    CommentOut,
    EventIn,
    EventLiteOut,
    EventOut,
    Health,
    SkillItem,
    SkillsMappingFailureItem,
    SkillsMappingPatchIn,
    SkillsMappingPatchOut,
    TaskCreate,
    TaskOut,
    WorkspaceSkillGroup,
)


ALLOWED_TASK_STATUSES = {"INBOX", "ASSIGNED", "IN PROGRESS", "REVIEW", "DONE"}
TASK_STATUS_TRANSITIONS = {
    "INBOX": {"ASSIGNED"},
    "ASSIGNED": {"IN PROGRESS", "REVIEW"},
    "IN PROGRESS": {"REVIEW", "DONE"},
    "REVIEW": {"IN PROGRESS", "DONE"},
    "DONE": set(),
}


def _rewrite_avatar_paths(obj, agent: str):
    if isinstance(obj, str):
        if obj.startswith("/avatar/"):
            return f"/chat/{agent}{obj}"
        return obj
    if isinstance(obj, list):
        return [_rewrite_avatar_paths(item, agent) for item in obj]
    if isinstance(obj, dict):
        return {k: _rewrite_avatar_paths(v, agent) for k, v in obj.items()}
    return obj


def _build_chat_inject_script(agent: str, token: str | None) -> str:
    base_path = f"/chat/{agent}"
    token_json = json.dumps(token or "", ensure_ascii=False)
    return (
        f'window.__OPENCLAW_CONTROL_UI_BASE_PATH__="{base_path}";'
        "(function(){"
        "try{localStorage.removeItem(\"openclaw.device.auth.v1\");"
        "localStorage.removeItem(\"openclaw-device-identity-v1\");}catch(e){}"
        "try{"
        "const k=\"openclaw.control.settings.v1\";"
        "const raw=localStorage.getItem(k);"
        "let v={};"
        "try{v=raw?JSON.parse(raw):{};}catch{}"
        f"v.gatewayUrl=(location.protocol===\"https:\"?\"wss\":\"ws\")+\"://\"+location.host+\"{base_path}/\";"
        f"v.token={token_json};"
        "localStorage.setItem(k,JSON.stringify(v));"
        "}catch(e){}"
        "try{"
        f"const p=\"{base_path}\";"
        "const scan=()=>{"
        "document.querySelectorAll('img.chat-avatar.assistant[src^=\"/avatar/\"]').forEach((img)=>{"
        "const s=img.getAttribute(\"src\")||\"\";"
        "if(s.startsWith(\"/avatar/\"))img.setAttribute(\"src\",p+s);"
        "});"
        "};"
        "scan();"
        "const mo=new MutationObserver(()=>scan());"
        "mo.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:[\"src\"]});"
        "window.addEventListener(\"beforeunload\",()=>mo.disconnect(),{once:true});"
        "}catch(e){}"
        "})();"
    )


def _normalize_control_ui_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    if origin.startswith("http://127.0.0.1:"):
        return origin.replace("http://127.0.0.1", "http://localhost", 1)
    if origin.startswith("https://127.0.0.1:"):
        return origin.replace("https://127.0.0.1", "https://localhost", 1)
    return origin


def _augment_connect_auth(message: str, token: str | None) -> str:
    try:
        req = json.loads(message)
    except Exception:
        return message

    if not isinstance(req, dict):
        return message
    if req.get("type") != "req" or req.get("method") != "connect":
        return message
    if not isinstance(req.get("params"), dict):
        return message

    params = req["params"]
    auth = params.get("auth")
    if not isinstance(auth, dict):
        auth = {}
    if token and not auth.get("token"):
        auth["token"] = token
    if auth:
        params["auth"] = auth
    req["params"] = params
    return json.dumps(req, ensure_ascii=False)


def _rewrite_avatar_meta(content: bytes, agent: str, query: str) -> bytes:
    try:
        payload = json.loads(content.decode("utf-8", errors="replace"))
    except Exception:
        return content

    avatar_url = payload.get("avatarUrl") if isinstance(payload, dict) else None
    if isinstance(avatar_url, str) and avatar_url.startswith("/avatar/"):
        rewritten = f"/chat/{agent}{avatar_url}"
        if query:
            rewritten = f"{rewritten}?{query}"
        payload["avatarUrl"] = rewritten
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return content


def _avatar_fallback_svg(agent: str) -> bytes:
    label = (agent[:1] or "A").upper()
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
        "<rect width='96' height='96' rx='48' fill='#2f3747'/>"
        "<text x='50%' y='54%' dominant-baseline='middle' text-anchor='middle' "
        "font-family='system-ui, -apple-system, Segoe UI, Roboto, sans-serif' "
        "font-size='42' fill='#ffffff'>"
        f"{label}</text></svg>"
    ).encode("utf-8")


def require_auth(settings: Settings, authorization: str | None = Header(default=None)) -> None:
    if not settings.auth_token:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.auth_token:
        raise HTTPException(status_code=403, detail="invalid token")


def _parse_skill_frontmatter(skill_file: Path, fallback_slug: str) -> tuple[str, str | None]:
    name = fallback_slug
    description: str | None = None

    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return name, description

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return name, description

    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            parsed = line.split(":", 1)[1].strip().strip('"').strip("'")
            if parsed:
                name = parsed
        elif line.startswith("description:"):
            parsed = line.split(":", 1)[1].strip().strip('"').strip("'")
            if parsed:
                description = parsed
    return name, description


def _scan_global_skills(settings: Settings) -> list[SkillItem]:
    root = Path(settings.global_skills_dir)
    if not root.exists() or not root.is_dir():
        return []

    out: list[SkillItem] = []
    for skill_file in sorted(root.glob("*/SKILL.md")):
        slug = skill_file.parent.name
        name, description = _parse_skill_frontmatter(skill_file, slug)
        out.append(
            SkillItem(
                slug=slug,
                name=name,
                description=description,
                path=str(skill_file),
                scope="global",
            )
        )
    return out


def _scan_workspace_skills(settings: Settings, agent_slug: str | None = None) -> list[WorkspaceSkillGroup]:
    root = Path(settings.agent_homes_dir)
    if not root.exists() or not root.is_dir():
        return []

    groups: list[WorkspaceSkillGroup] = []
    agent_dirs = sorted(path for path in root.iterdir() if path.is_dir())

    for agent_dir in agent_dirs:
        slug = agent_dir.name
        if agent_slug and slug != agent_slug:
            continue

        skills_dir = agent_dir / "skills"
        skill_items: list[SkillItem] = []
        if skills_dir.exists() and skills_dir.is_dir():
            for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
                s_slug = skill_file.parent.name
                s_name, s_desc = _parse_skill_frontmatter(skill_file, s_slug)
                skill_items.append(
                    SkillItem(
                        slug=s_slug,
                        name=s_name,
                        description=s_desc,
                        path=str(skill_file),
                        scope="workspace",
                    )
                )

        groups.append(WorkspaceSkillGroup(agent_slug=slug, skills=skill_items))
    return groups


def _scan_agent_slugs(settings: Settings) -> list[str]:
    root = Path(settings.agent_homes_dir)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def _known_agent_slugs(settings: Settings) -> set[str]:
    root = Path(settings.agent_homes_dir)
    if not root.exists() or not root.is_dir():
        return set()
    return {path.name for path in root.iterdir() if path.is_dir()}


def _validate_handoff_payload(payload: dict, known_agents: set[str]) -> list[str]:
    errors: list[str] = []

    target_agent = str(payload.get("to") or "").strip()
    if not target_agent:
        errors.append("payload.to is required")
    elif known_agents and target_agent not in known_agents:
        errors.append(f"payload.to agent not found: {target_agent}")

    for field in ("problem", "context", "expected_output"):
        value = str(payload.get(field) or "").strip()
        if not value:
            errors.append(f"payload.{field} is required")

    artifact_refs = payload.get("artifact_refs")
    if not isinstance(artifact_refs, list) or not artifact_refs:
        errors.append("payload.artifact_refs must be a non-empty list")
    elif not all(isinstance(item, str) and item.strip() for item in artifact_refs):
        errors.append("payload.artifact_refs must contain non-empty strings")

    if not isinstance(payload.get("review_gate"), bool):
        errors.append("payload.review_gate must be boolean")

    return errors


def create_app() -> FastAPI:
    settings = load_settings()

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    app = FastAPI(title="Mission Control API", version="0.1.0")

    async def get_session():
        async with session_factory() as session:
            yield session

    async def publish_validation_result(
        *,
        accepted: bool,
        body: EventIn,
        errors: list[str],
        details: dict | None = None,
    ) -> None:
        await publish_event(
            redis,
            stream_key=settings.redis_stream_key,
            event={
                "id": str(uuid4()),
                "type": "event.validation",
                "agent": body.agent,
                "task_id": str(body.task_id) if body.task_id else None,
                "payload": {
                    "event_type": body.type,
                    "accepted": accepted,
                    "errors": errors,
                    "details": details or {},
                },
                "created_at": datetime.utcnow().isoformat() + "Z",
            },
        )

    @app.get("/health", response_model=Health)
    async def healthcheck() -> Health:
        return Health(ok=True)

    @app.get("/v1/skills/global", response_model=list[SkillItem])
    async def get_global_skills(
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
    ) -> list[SkillItem]:
        return _scan_global_skills(settings)

    @app.get("/v1/skills/workspace", response_model=list[WorkspaceSkillGroup])
    async def get_workspace_skills(
        agent_slug: str | None = None,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
    ) -> list[WorkspaceSkillGroup]:
        return _scan_workspace_skills(settings, agent_slug=agent_slug)

    @app.get("/v1/skills/mappings", response_model=list[AgentSkillMappingOut])
    async def get_skill_mappings(
        agent_slug: str | None = None,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> list[AgentSkillMappingOut]:
        stmt = sa.select(
            agent_skill_mappings.c.id,
            agent_skill_mappings.c.agent_slug,
            agent_skill_mappings.c.skill_slug,
            agent_skill_mappings.c.created_at,
        ).order_by(agent_skill_mappings.c.agent_slug.asc(), agent_skill_mappings.c.skill_slug.asc())
        if agent_slug:
            stmt = stmt.where(agent_skill_mappings.c.agent_slug == agent_slug)
        rows = (await session.execute(stmt)).all()
        return [AgentSkillMappingOut(**row._asdict()) for row in rows]

    @app.patch("/v1/skills/mappings", response_model=SkillsMappingPatchOut)
    async def patch_skill_mappings(
        body: SkillsMappingPatchIn,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> SkillsMappingPatchOut:
        agent_slugs = sorted({slug.strip() for slug in body.agent_slugs if slug and slug.strip()})
        add_skill_slugs = sorted({slug.strip() for slug in body.add_skill_slugs if slug and slug.strip()})
        remove_skill_slugs = sorted({slug.strip() for slug in body.remove_skill_slugs if slug and slug.strip()})

        if not agent_slugs:
            raise HTTPException(status_code=400, detail="agent_slugs is required")
        if not add_skill_slugs and not remove_skill_slugs:
            raise HTTPException(status_code=400, detail="nothing to update")

        failed: list[SkillsMappingFailureItem] = []
        known_agents = set(_scan_agent_slugs(settings))
        valid_agents = agent_slugs
        if known_agents:
            unknown_agents = [slug for slug in agent_slugs if slug not in known_agents]
            valid_agents = [slug for slug in agent_slugs if slug in known_agents]
            for agent in unknown_agents:
                for skill in add_skill_slugs:
                    failed.append(
                        SkillsMappingFailureItem(
                            action="add",
                            agent_slug=agent,
                            skill_slug=skill,
                            reason="unknown_agent",
                        )
                    )
                for skill in remove_skill_slugs:
                    failed.append(
                        SkillsMappingFailureItem(
                            action="remove",
                            agent_slug=agent,
                            skill_slug=skill,
                            reason="unknown_agent",
                        )
                    )

        known_global = {item.slug for item in _scan_global_skills(settings)}
        unknown_add = [slug for slug in add_skill_slugs if slug not in known_global]
        unknown_remove = [slug for slug in remove_skill_slugs if slug not in known_global]
        valid_add_skill_slugs = [slug for slug in add_skill_slugs if slug in known_global]
        valid_remove_skill_slugs = [slug for slug in remove_skill_slugs if slug in known_global]

        for skill in unknown_add:
            for agent in valid_agents:
                failed.append(
                    SkillsMappingFailureItem(
                        action="add",
                        agent_slug=agent,
                        skill_slug=skill,
                        reason="unknown_global_skill",
                    )
                )
        for skill in unknown_remove:
            for agent in valid_agents:
                failed.append(
                    SkillsMappingFailureItem(
                        action="remove",
                        agent_slug=agent,
                        skill_slug=skill,
                        reason="unknown_global_skill",
                    )
                )

        if not valid_agents:
            return SkillsMappingPatchOut(
                updated=0,
                affected_agents=[],
                restart_hint="No valid mappings were updated.",
                failed=failed,
            )

        updated = 0
        if valid_add_skill_slugs:
            target_pairs = {(agent, skill) for agent in valid_agents for skill in valid_add_skill_slugs}
            existing_stmt = sa.select(
                agent_skill_mappings.c.agent_slug,
                agent_skill_mappings.c.skill_slug,
            ).where(
                agent_skill_mappings.c.agent_slug.in_(valid_agents),
                agent_skill_mappings.c.skill_slug.in_(valid_add_skill_slugs),
            )
            existing_rows = (await session.execute(existing_stmt)).all()
            existing_pairs = {(str(row.agent_slug), str(row.skill_slug)) for row in existing_rows}

            for agent, skill in sorted(existing_pairs):
                failed.append(
                    SkillsMappingFailureItem(
                        action="add",
                        agent_slug=agent,
                        skill_slug=skill,
                        reason="already_mapped",
                    )
                )

            rows = [
                {"id": uuid4(), "agent_slug": agent, "skill_slug": skill}
                for (agent, skill) in sorted(target_pairs - existing_pairs)
            ]
            if rows:
                insert_stmt = pg_insert(agent_skill_mappings).values(rows)
                insert_stmt = insert_stmt.on_conflict_do_nothing(
                    constraint="uq_agent_skill_mappings_agent_skill"
                )
                insert_stmt = insert_stmt.returning(agent_skill_mappings.c.id)
                result = await session.execute(insert_stmt)
                updated += len(result.scalars().all())

        if valid_remove_skill_slugs:
            target_pairs = {(agent, skill) for agent in valid_agents for skill in valid_remove_skill_slugs}
            existing_stmt = sa.select(
                agent_skill_mappings.c.id,
                agent_skill_mappings.c.agent_slug,
                agent_skill_mappings.c.skill_slug,
            ).where(
                agent_skill_mappings.c.agent_slug.in_(valid_agents),
                agent_skill_mappings.c.skill_slug.in_(valid_remove_skill_slugs),
            )
            existing_rows = (await session.execute(existing_stmt)).all()
            existing_pairs = {(str(row.agent_slug), str(row.skill_slug)) for row in existing_rows}

            missing_pairs = sorted(target_pairs - existing_pairs)
            for agent, skill in missing_pairs:
                failed.append(
                    SkillsMappingFailureItem(
                        action="remove",
                        agent_slug=agent,
                        skill_slug=skill,
                        reason="not_mapped",
                    )
                )

            if existing_rows:
                existing_ids = [row.id for row in existing_rows]
                delete_stmt = agent_skill_mappings.delete().where(agent_skill_mappings.c.id.in_(existing_ids))
                result = await session.execute(delete_stmt)
                updated += int(result.rowcount or 0)

        await session.commit()

        return SkillsMappingPatchOut(
            updated=updated,
            affected_agents=valid_agents,
            restart_hint=(
                "Configuration saved. Restart affected agent containers to apply changes."
                if updated > 0
                else "No mapping changes were applied."
            ),
            failed=failed,
        )

    @app.post("/v1/tasks", response_model=TaskOut)
    async def create_task(
        body: TaskCreate,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> TaskOut:
        if body.status not in ALLOWED_TASK_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"invalid task status: {body.status}; allowed={sorted(ALLOWED_TASK_STATUSES)}",
            )

        task_id = uuid4()
        now = datetime.utcnow()
        stmt = (
            tasks.insert()
            .values(
                id=task_id,
                title=body.title,
                status=body.status,
                assignee=body.assignee,
                tags=body.tags,
                created_at=now,
                updated_at=now,
            )
            .returning(
                tasks.c.id,
                tasks.c.title,
                tasks.c.status,
                tasks.c.assignee,
                tasks.c.tags,
                tasks.c.created_at,
                tasks.c.updated_at,
            )
        )
        row = (await session.execute(stmt)).one()
        await session.commit()
        return TaskOut(**row._asdict())

    @app.get("/v1/boards/default", response_model=BoardOut)
    async def get_board(
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> BoardOut:
        statuses = ["INBOX", "ASSIGNED", "IN PROGRESS", "REVIEW", "DONE"]
        columns: list[BoardColumn] = []
        for status in statuses:
            stmt = (
                sa.select(
                    tasks.c.id,
                    tasks.c.title,
                    tasks.c.status,
                    tasks.c.assignee,
                    tasks.c.tags,
                    tasks.c.created_at,
                    tasks.c.updated_at,
                )
                .where(tasks.c.status == status)
                .order_by(tasks.c.updated_at.desc())
                .limit(100)
            )
            rows = (await session.execute(stmt)).all()
            cards = [TaskOut(**r._asdict()) for r in rows]
            columns.append(BoardColumn(title=status, count=len(cards), cards=cards))
        return BoardOut(columns=columns)

    @app.post("/v1/tasks/{task_id}/comments", response_model=CommentOut)
    async def add_comment(
        task_id: UUID,
        body: CommentCreate,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> CommentOut:
        comment_id = uuid4()
        stmt = (
            comments.insert()
            .values(id=comment_id, task_id=task_id, author=body.author, body=body.body)
            .returning(
                comments.c.id,
                comments.c.task_id,
                comments.c.author,
                comments.c.body,
                comments.c.created_at,
            )
        )
        row = (await session.execute(stmt)).one()
        await session.commit()

        await publish_event(
            redis,
            stream_key=settings.redis_stream_key,
            event={
                "id": str(uuid4()),
                "type": "comment.created",
                "agent": body.author,
                "task_id": str(task_id),
                "payload": {"comment_id": str(row.id)},
                "created_at": datetime.utcnow().isoformat() + "Z",
            },
        )

        return CommentOut(**row._asdict())

    @app.post("/v1/events", response_model=EventOut)
    async def ingest_event(
        body: EventIn,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> EventOut:
        validation_errors: list[str] = []
        validation_details: dict = {}

        if body.type == "task.handoff":
            if not body.task_id:
                validation_errors.append("task.handoff requires task_id")
            known_agents = _known_agent_slugs(settings)
            validation_errors.extend(_validate_handoff_payload(body.payload, known_agents))
            validation_details["known_agents_count"] = len(known_agents)

        event_payload = dict(body.payload)
        if body.type == "task.status":
            if not body.task_id:
                validation_errors.append("task.status requires task_id")
            next_status = str(body.payload.get("new_status") or "").strip().upper()
            if not next_status:
                validation_errors.append("payload.new_status is required")
            elif next_status not in ALLOWED_TASK_STATUSES:
                validation_errors.append(
                    f"payload.new_status invalid: {next_status}; allowed={sorted(ALLOWED_TASK_STATUSES)}"
                )

            current_status = None
            if body.task_id:
                current_row = (
                    await session.execute(
                        sa.select(tasks.c.id, tasks.c.status).where(tasks.c.id == body.task_id)
                    )
                ).first()
                if not current_row:
                    validation_errors.append(f"task not found: {body.task_id}")
                else:
                    current_status = str(current_row.status)

            if not validation_errors and current_status is not None:
                allowed = TASK_STATUS_TRANSITIONS.get(current_status, set())
                if next_status != current_status and next_status not in allowed:
                    validation_errors.append(
                        f"invalid status transition: {current_status} -> {next_status}; allowed={sorted(allowed)}"
                    )

            if not validation_errors and current_status is not None:
                now = datetime.utcnow()
                await session.execute(
                    tasks.update()
                    .where(tasks.c.id == body.task_id)
                    .values(status=next_status, updated_at=now)
                )
                event_payload["previous_status"] = current_status
                event_payload["new_status"] = next_status
                event_payload["transition_applied"] = True
                validation_details["transition"] = {
                    "from": current_status,
                    "to": next_status,
                }

        if validation_errors:
            await publish_validation_result(
                accepted=False,
                body=body,
                errors=validation_errors,
                details=validation_details,
            )
            raise HTTPException(status_code=422, detail={"errors": validation_errors})

        event_id = uuid4()
        stmt = (
            events.insert()
            .values(id=event_id, type=body.type, agent=body.agent, task_id=body.task_id, payload=event_payload)
            .returning(
                events.c.id,
                events.c.type,
                events.c.agent,
                events.c.task_id,
                events.c.payload,
                events.c.created_at,
            )
        )
        row = (await session.execute(stmt)).one()
        await session.commit()

        await publish_event(
            redis,
            stream_key=settings.redis_stream_key,
            event={
                "id": str(row.id),
                "type": row.type,
                "agent": row.agent,
                "task_id": str(row.task_id) if row.task_id else None,
                "payload": row.payload,
                "created_at": row.created_at.isoformat(),
            },
        )

        await publish_validation_result(
            accepted=True,
            body=body,
            errors=[],
            details=validation_details,
        )

        return EventOut(**row._asdict())

    @app.get("/v1/feed", response_model=list[EventOut])
    async def get_feed(
        limit: int = 50,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> list[EventOut]:
        stmt = (
            sa.select(
                events.c.id,
                events.c.type,
                events.c.agent,
                events.c.task_id,
                events.c.payload,
                events.c.created_at,
            )
            .order_by(events.c.created_at.desc())
            .limit(min(limit, 200))
        )
        rows = (await session.execute(stmt)).all()
        return [EventOut(**r._asdict()) for r in rows]

    @app.get("/v1/feed-lite", response_model=list[EventLiteOut])
    async def get_feed_lite(
        limit: int = 50,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> list[EventLiteOut]:
        stmt = (
            sa.select(
                events.c.id,
                events.c.type,
                events.c.agent,
                events.c.task_id,
                events.c.created_at,
                sa.func.jsonb_extract_path_text(events.c.payload, "method").label("method"),
                sa.func.jsonb_extract_path_text(events.c.payload, "path").label("path"),
                sa.cast(sa.func.nullif(sa.func.jsonb_extract_path_text(events.c.payload, "status_code"), ""), sa.Integer).label("status_code"),
                sa.func.jsonb_extract_path_text(events.c.payload, "error_type").label("error_type"),
                sa.func.jsonb_extract_path_text(events.c.payload, "test_id").label("test_id"),
                sa.cast(sa.func.nullif(sa.func.jsonb_extract_path_text(events.c.payload, "round"), ""), sa.Integer).label("round"),
            )
            .order_by(events.c.created_at.desc())
            .limit(min(limit, 500))
        )
        rows = (await session.execute(stmt)).all()
        return [EventLiteOut(**r._asdict()) for r in rows]

    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket):
        await websocket.accept()

        # 可選 Bearer token（如果設定了 MC_AUTH_TOKEN）
        if settings.auth_token:
            auth = websocket.headers.get("authorization")
            if not auth or not auth.lower().startswith("bearer "):
                await websocket.close(code=4401)
                return
            token = auth.split(" ", 1)[1].strip()
            if token != settings.auth_token:
                await websocket.close(code=4403)
                return

        # Start from the latest stream ID to avoid replaying long history on each
        # new websocket connection, which can significantly increase perceived
        # real-time latency on the dashboard.
        last_id = "$"
        try:
            latest = await redis.xrevrange(settings.redis_stream_key, count=1)
            if latest:
                last_id = str(latest[0][0])
        except Exception:
            # Fall back to '$' (new entries only).
            last_id = "$"
        try:
            while True:
                result = await redis.xread({settings.redis_stream_key: last_id}, block=25_000, count=50)
                if not result:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    continue

                _, entries = result[0]
                for entry_id, fields in entries:
                    last_id = entry_id
                    # fields["event"] 會是一個 JSON 字串
                    event_json = fields.get("event")
                    if event_json:
                        await websocket.send_text(event_json)
        except WebSocketDisconnect:
            return

    
    @app.api_route("/chat/{agent}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def chat_proxy(agent: str, path: str, request: Request):
        upgrade = request.headers.get("upgrade", "").lower() == "websocket"
        if not upgrade:
            payload = {
                "path": f"/{path}",
                "query": str(request.url.query)[:256],
                "method": request.method,
                "status_code": 0,
                "request_time": "0.0",
                "upstream_status": "proxy",
                "is_ws_upgrade": False,
                "source": "api_gateway_proxy",
                "ts": datetime.utcnow().isoformat() + "Z",
            }
            await publish_event(
                redis,
                stream_key=settings.redis_stream_key,
                event={
                    "type": "chat.gateway.access",
                    "agent": agent,
                    "payload": payload,
                },
            )
            
        target_url = f"http://openclaw-{agent}:26216/{path}"
        query = request.url.query
        if query:
            target_url += f"?{query}"
            
        async with httpx.AsyncClient(timeout=3600.0) as client:
            headers = dict(request.headers.items())
            headers.pop("host", None)
            
            token = settings.agent_token_map.get(agent)
            if token:
                headers["authorization"] = f"Bearer {token}"
                
            req = client.build_request(
                request.method,
                target_url,
                headers=headers,
                content=request.stream(),
            )
            
            try:
                resp = await client.send(req, stream=True)
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Proxy error: {e}")
            
            is_html = "text/html" in resp.headers.get("content-type", "")
            if is_html:
                content = await resp.aread()
                text = content.decode("utf-8", errors="replace")
                
                inject_script = _build_chat_inject_script(agent, token)
                
                text = text.replace('window.__OPENCLAW_CONTROL_UI_BASE_PATH__="";', inject_script)
                text = re.sub(
                    r'window\.__OPENCLAW_ASSISTANT_AVATAR__=("|\')/avatar/[^"\']*("|\')',
                    'window.__OPENCLAW_ASSISTANT_AVATAR__=""',
                    text,
                )
                await resp.aclose()
                
                return HTMLResponse(content=text, status_code=resp.status_code)

            content = await resp.aread()
            await resp.aclose()

            if request.method.upper() == "GET" and path.startswith("avatar/"):
                is_meta = request.query_params.get("meta") == "1"

                if is_meta and resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                    content = _rewrite_avatar_meta(content, agent, query)

                if not is_meta and resp.status_code == 404:
                    svg = _avatar_fallback_svg(agent)
                    return Response(content=svg, status_code=200, media_type="image/svg+xml")

            r = Response(content=content, status_code=resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() not in ("content-length", "transfer-encoding", "connection"):
                    r.headers[k] = v
            return r

    @app.websocket("/chat/{agent}/{path:path}")
    async def chat_ws_proxy(agent: str, path: str, websocket: WebSocket):
        await websocket.accept()
        
        payload = {
            "path": f"/{path}",
            "query": "",
            "method": "GET",
            "status_code": 101,
            "request_time": "0.0",
            "upstream_status": "proxy",
            "is_ws_upgrade": True,
            "source": "api_gateway_proxy",
            "ts": datetime.utcnow().isoformat() + "Z",
        }
        await publish_event(
            redis,
            stream_key=settings.redis_stream_key,
            event={
                "type": "chat.gateway.access",
                "agent": agent,
                "payload": payload,
            },
        )
            
        target_ws_url = f"ws://openclaw-{agent}:26216/{path}"
        ws_query = websocket.scope.get("query_string", b"")
        if isinstance(ws_query, (bytes, bytearray)) and ws_query:
            target_ws_url = f"{target_ws_url}?{ws_query.decode('utf-8', errors='ignore')}"
        import websockets
        from websockets.exceptions import ConnectionClosed
        
        token = settings.agent_token_map.get(agent)
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        upstream_origin = _normalize_control_ui_origin(websocket.headers.get("origin"))
            
        try:
            async with websockets.connect(
                target_ws_url,
                extra_headers=headers or None,
                origin=upstream_origin or None,
            ) as upstream_ws:
                async def forward_to_upstream():
                    try:
                        while True:
                            msg = await websocket.receive_text()
                            msg = _augment_connect_auth(msg, token)
                            await upstream_ws.send(msg)
                    except WebSocketDisconnect:
                        pass
                    except Exception:
                        pass
                        
                async def forward_to_client():
                    try:
                        while True:
                            msg = await upstream_ws.recv()
                            if isinstance(msg, str) and "/avatar/" in msg:
                                try:
                                    payload = json.loads(msg)
                                    rewritten = _rewrite_avatar_paths(payload, agent)
                                    msg = json.dumps(rewritten, ensure_ascii=False)
                                except Exception:
                                    pass
                            await websocket.send_text(msg)
                    except ConnectionClosed:
                        pass
                    except Exception:
                        pass
                        
                await asyncio.gather(
                    forward_to_upstream(),
                    forward_to_client()
                )
        except Exception as e:
            await websocket.close(code=1011, reason=str(e))

    @app.on_event("startup")
    async def _startup():
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_events_created_at_desc
                    ON events(created_at DESC);
                    """
                )
            )
            await conn.execute(
                sa.text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_events_type_created_at_desc
                    ON events(type, created_at DESC);
                    """
                )
            )
            await conn.execute(
                sa.text(
                    """
                    CREATE TABLE IF NOT EXISTS agent_skill_mappings (
                      id uuid PRIMARY KEY,
                      agent_slug text NOT NULL,
                      skill_slug text NOT NULL,
                      created_at timestamptz NOT NULL DEFAULT now(),
                      CONSTRAINT uq_agent_skill_mappings_agent_skill UNIQUE (agent_slug, skill_slug)
                    );
                    """
                )
            )
            await conn.execute(
                sa.text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agent_skill_mappings_agent_slug
                    ON agent_skill_mappings(agent_slug);
                    """
                )
            )

    @app.on_event("shutdown")
    async def _shutdown():
        await redis.aclose()
        await engine.dispose()

    return app


async def publish_event(redis: Redis, stream_key: str, event: dict) -> None:
    await redis.xadd(stream_key, {"event": json.dumps(event, ensure_ascii=False)})


app = create_app()
