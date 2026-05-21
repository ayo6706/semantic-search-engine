"""Schemas for system health checks."""

from __future__ import annotations

from dataclasses import dataclass


from typing import Literal


@dataclass
class ServiceHealth:
    """Detailed health check status for a service."""

    status: Literal["ok", "error"]
    latency_ms: float
    error_message: str | None = None
