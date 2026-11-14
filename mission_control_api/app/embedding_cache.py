from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time
from collections import OrderedDict


def embedding_cache_key(*, query: str, agent_slug: str | None, risk_level: str, config: dict, revision: str) -> str:
    values = {"query": query, "agent_slug": agent_slug, "risk_level": risk_level, "revision": revision, "config": config}
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class EmbeddingCache:
    def __init__(self, *, ttl_seconds: float = 60, max_entries: int = 128, concurrency: int = 2, clock=time.monotonic) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock
        self.entries: OrderedDict = OrderedDict()
        self.pending: dict[str, asyncio.Task] = {}
        self.semaphore = asyncio.Semaphore(concurrency)
        self.hits = 0
        self.misses = 0

    async def _compute(self, key: str, factory):
        try:
            async with self.semaphore:
                value = await factory()
            if self.ttl_seconds > 0:
                self.entries[key] = (self.clock() + self.ttl_seconds, copy.deepcopy(value))
                self.entries.move_to_end(key)
                while len(self.entries) > self.max_entries:
                    self.entries.popitem(last=False)
            return value
        finally:
            self.pending.pop(key, None)

    async def get(self, key: str, factory):
        cached = self.entries.get(key)
        if cached and cached[0] > self.clock() and self.ttl_seconds > 0:
            self.hits += 1
            self.entries.move_to_end(key)
            return copy.deepcopy(cached[1])
        self.entries.pop(key, None)
        task = self.pending.get(key)
        if task is None:
            if len(self.pending) >= self.max_entries:
                async with self.semaphore:
                    return await factory()
            self.misses += 1
            task = asyncio.create_task(self._compute(key, factory))
            task.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None)
            self.pending[key] = task
        else:
            self.hits += 1
        return copy.deepcopy(await asyncio.shield(task))

    async def close(self) -> None:
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)