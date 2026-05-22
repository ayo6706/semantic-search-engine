from __future__ import annotations

from collections.abc import Awaitable, Callable

DisconnectChecker = Callable[[], Awaitable[bool]]
StaleChecker = Callable[[], Awaitable[bool]]
