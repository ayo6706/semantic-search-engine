from __future__ import annotations

import asyncio
from collections import OrderedDict


class SearchCancellationRegistry:
    def __init__(self, max_sessions: int = 1000) -> None:
        self.max_sessions = max_sessions
        self._latest_request_ids: OrderedDict[str, int] = OrderedDict()
        self._lock = asyncio.Lock()

    async def mark_latest(self, session_id: str, request_id: int) -> None:
        async with self._lock:
            self._latest_request_ids[session_id] = request_id
            self._latest_request_ids.move_to_end(session_id)

            while len(self._latest_request_ids) > self.max_sessions:
                self._latest_request_ids.popitem(last=False)

    async def is_stale(self, session_id: str, request_id: int) -> bool:
        async with self._lock:
            return self._latest_request_ids.get(session_id) != request_id


search_cancellation_registry = SearchCancellationRegistry()
