from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from .config import Settings, load_settings
from .db import create_engine, create_session_factory
from .models import comments, events, tasks
from .schemas import (
    BoardColumn,
    BoardOut,
    CommentCreate,
    CommentOut,
    EventIn,
    EventOut,
    Health,
    TaskCreate,
    TaskOut,
)


def require_auth(settings: Settings, authorization: str | None = Header(default=None)) -> None:
    if not settings.auth_token:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.auth_token:
        raise HTTPException(status_code=403, detail="invalid token")


def create_app() -> FastAPI:
    settings = load_settings()

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    app = FastAPI(title="Mission Control API", version="0.1.0")

    async def get_session():
        async with session_factory() as session:
            yield session

    @app.get("/health", response_model=Health)
    async def healthcheck() -> Health:
        return Health(ok=True)

    @app.post("/v1/tasks", response_model=TaskOut)
    async def create_task(
        body: TaskCreate,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> TaskOut:
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
        event_id = uuid4()
        stmt = (
            events.insert()
            .values(id=event_id, type=body.type, agent=body.agent, task_id=body.task_id, payload=body.payload)
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

        last_id = "0-0"
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

    @app.on_event("shutdown")
    async def _shutdown():
        await redis.aclose()
        await engine.dispose()

    return app


async def publish_event(redis: Redis, stream_key: str, event: dict) -> None:
    await redis.xadd(stream_key, {"event": json.dumps(event, ensure_ascii=False)})


app = create_app()
