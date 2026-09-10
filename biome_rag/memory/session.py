"""Redis-backed sliding-window session memory — Phase 5.

Each conversation is identified by a ``session_id`` (UUID string).
Messages are stored as a Redis list using the key ``biome:session:<session_id>``.
The list is trimmed to ``window_size`` entries on every write, implementing
an O(1) sliding window without a scan.

Design decisions:
  - Each list element is a JSON-encoded dict: ``{"role": "user"|"assistant", "content": "..."}``
  - Expiry: every read/write resets the TTL (default 3600 s) so idle sessions expire.
  - Graceful fallback: if Redis is unreachable, ``InMemorySessionStore`` is used
    transparently. The caller never needs to handle ConnectionError.
  - Thread-safe: Redis operations are atomic (RPUSH + LTRIM are pipelined).

Usage::

    store = get_session_store()          # auto-detects Redis availability
    store.append(session_id, "user",     "What is the VPN policy?")
    store.append(session_id, "assistant", "According to [1]...")
    history = store.get_history(session_id)
    # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    store.clear(session_id)
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# redis is optional
try:
    import redis as _redis_lib  # type: ignore
    _REDIS_AVAILABLE = True
except ImportError:
    _redis_lib = None  # type: ignore
    _REDIS_AVAILABLE = False
    logger.warning("redis package not installed (`pip install redis`). Using in-memory session store.")


Message = dict[str, str]   # {"role": "user"|"assistant", "content": "..."}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class SessionStore(ABC):
    """Abstract interface for conversation history stores."""

    @abstractmethod
    def append(self, session_id: str, role: str, content: str) -> None:
        """Append one turn to the session history."""

    @abstractmethod
    def get_history(self, session_id: str) -> list[Message]:
        """Return the full (windowed) history for ``session_id``."""

    @abstractmethod
    def clear(self, session_id: str) -> None:
        """Delete all history for ``session_id``."""

    def build_prompt_messages(
        self,
        session_id: str,
        new_user_message: str,
        system_prompt: str | None = None,
    ) -> list[Message]:
        """Build an OpenAI-style message list from history + new user turn.

        The result is ready to pass to ``openai.ChatCompletion.create(messages=...)``.
        """
        messages: list[Message] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(self.get_history(session_id))
        messages.append({"role": "user", "content": new_user_message})
        return messages


# ---------------------------------------------------------------------------
# In-memory fallback (no Redis required — used in tests and CI)
# ---------------------------------------------------------------------------

class InMemorySessionStore(SessionStore):
    """Thread-unsafe in-process session store for testing and CI.

    Not suitable for multi-worker production deployments.
    """

    def __init__(self, window_size: int = 10) -> None:
        self._store: dict[str, list[Message]] = {}
        self.window_size = window_size

    def append(self, session_id: str, role: str, content: str) -> None:
        history = self._store.setdefault(session_id, [])
        history.append({"role": role, "content": content})
        # Keep only the last window_size messages
        if len(history) > self.window_size:
            self._store[session_id] = history[-self.window_size:]

    def get_history(self, session_id: str) -> list[Message]:
        return list(self._store.get(session_id, []))

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)


# ---------------------------------------------------------------------------
# Redis-backed store
# ---------------------------------------------------------------------------

class RedisSessionStore(SessionStore):
    """Sliding-window session store backed by Redis lists.

    Args:
        redis_url: Full Redis URL. Default: ``REDIS_URL`` env var or localhost.
        window_size: Maximum number of messages retained (oldest trimmed first).
        ttl: Session expiry in seconds (reset on every read/write).
        key_prefix: Redis key prefix, e.g. ``"biome:session:"``.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        window_size: int | None = None,
        ttl: int | None = None,
        key_prefix: str = "biome:session:",
    ) -> None:
        from biome_rag.config import get_settings  # noqa: PLC0415
        settings = get_settings()

        self.redis_url = redis_url or os.getenv("REDIS_URL", settings.redis_url)
        self.window_size = window_size or settings.redis_window_size
        self.ttl = ttl or settings.redis_session_ttl
        self.key_prefix = key_prefix
        self._client: Any = None
        self._fallback = InMemorySessionStore(window_size=self.window_size)
        self._available = _REDIS_AVAILABLE

    def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        if not _REDIS_AVAILABLE:
            return None
        try:
            client = _redis_lib.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self._client = client
            logger.info("RedisSessionStore: connected to %s", self.redis_url)
        except Exception as exc:
            logger.warning(
                "Redis not reachable at %s (%s). Falling back to in-memory session store.",
                self.redis_url, exc,
            )
            self._client = None
            self._available = False
        return self._client

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}{session_id}"

    def append(self, session_id: str, role: str, content: str) -> None:
        client = self._get_client()
        if client is None:
            self._fallback.append(session_id, role, content)
            return
        key = self._key(session_id)
        msg = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        try:
            pipe = client.pipeline()
            pipe.rpush(key, msg)
            pipe.ltrim(key, -self.window_size, -1)   # keep last window_size items
            pipe.expire(key, self.ttl)
            pipe.execute()
        except Exception as exc:
            logger.warning("Redis append failed: %s — using in-memory fallback.", exc)
            self._client = None
            self._available = False
            self._fallback.append(session_id, role, content)

    def get_history(self, session_id: str) -> list[Message]:
        client = self._get_client()
        if client is None:
            return self._fallback.get_history(session_id)
        key = self._key(session_id)
        try:
            raw_messages = client.lrange(key, 0, -1)
            client.expire(key, self.ttl)   # reset TTL on read
            return [json.loads(m) for m in raw_messages]
        except Exception as exc:
            logger.warning("Redis get_history failed: %s — using in-memory fallback.", exc)
            return self._fallback.get_history(session_id)

    def clear(self, session_id: str) -> None:
        client = self._get_client()
        if client is None:
            self._fallback.clear(session_id)
            return
        try:
            client.delete(self._key(session_id))
        except Exception as exc:
            logger.warning("Redis clear failed: %s", exc)


# ---------------------------------------------------------------------------
# Factory — returns the best available store
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    """Return a cached singleton SessionStore.

    Tries ``RedisSessionStore`` first; falls back to ``InMemorySessionStore``
    if Redis is not reachable.
    """
    store = RedisSessionStore()
    # Probe connectivity at creation time so the fallback is set up eagerly
    store._get_client()
    if store._available:
        logger.info("Session store: RedisSessionStore active.")
    else:
        logger.info("Session store: InMemorySessionStore (Redis unavailable).")
    return store
