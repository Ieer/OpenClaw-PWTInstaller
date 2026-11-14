from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa

from .models import event_outbox


logger = logging.getLogger(__name__)


async def stage_event(session, event: dict) -> None:
    await session.execute(event_outbox.insert().values(event_id=UUID(event["id"]), event=event))


async def send_event(redis, *, stream_key: str, event: dict, maxlen: int | None = None) -> None:
    options = {"maxlen": int(maxlen), "approximate": True} if maxlen and maxlen > 0 else {}
    await redis.xadd(stream_key, {"event": json.dumps(event, ensure_ascii=False)}, **options)


class EventOutbox:
    def __init__(self, session_factory, redis, settings) -> None:
        self.session_factory = session_factory
        self.redis = redis
        self.settings = settings
        self.last_prune = 0.0

    async def publish(self, *, redis, stream_key: str, event: dict, maxlen: int | None = None) -> None:
        if not self.settings.event_outbox_enabled:
            await send_event(redis, stream_key=stream_key, event=event, maxlen=maxlen)
            return
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    row = (await session.execute(
                        sa.select(event_outbox).where(event_outbox.c.event_id == UUID(event["id"])).with_for_update()
                    )).first()
                    if row and row.delivered_at is not None:
                        return
                    await asyncio.wait_for(
                        send_event(redis, stream_key=stream_key, event=event, maxlen=maxlen), timeout=3
                    )
                    if row:
                        await session.execute(event_outbox.update().where(
                            event_outbox.c.event_id == row.event_id
                        ).values(delivered_at=datetime.now(timezone.utc)))
        except Exception:
            logger.warning("Event delivery deferred; durable events remain in the outbox", exc_info=False)

    async def drain_once(self) -> int:
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                rows = (await session.execute(
                    sa.select(event_outbox).where(
                        event_outbox.c.delivered_at.is_(None), event_outbox.c.next_attempt_at <= now
                    ).order_by(event_outbox.c.created_at, event_outbox.c.event_id)
                    .limit(50).with_for_update(skip_locked=True)
                )).all()
                delivered = 0
                for row in rows:
                    try:
                        await asyncio.wait_for(send_event(
                            self.redis, stream_key=self.settings.redis_stream_key,
                            event=row.event, maxlen=self.settings.redis_stream_maxlen,
                        ), timeout=3)
                    except Exception:
                        attempts = row.attempts + 1
                        await session.execute(event_outbox.update().where(
                            event_outbox.c.event_id == row.event_id
                        ).values(attempts=attempts, next_attempt_at=now + timedelta(seconds=min(300, 2 ** min(attempts, 8)))))
                        break
                    else:
                        await session.execute(event_outbox.update().where(
                            event_outbox.c.event_id == row.event_id
                        ).values(delivered_at=datetime.now(timezone.utc)))
                        delivered += 1
                if time.monotonic() - self.last_prune >= 60:
                    await session.execute(event_outbox.delete().where(
                        event_outbox.c.delivered_at < now - timedelta(days=1)
                    ))
                    self.last_prune = time.monotonic()
                return delivered

    async def run(self) -> None:
        while True:
            try:
                await self.drain_once()
            except Exception:
                logger.warning("Outbox unavailable; retrying on the next interval", exc_info=False)
            await asyncio.sleep(2)