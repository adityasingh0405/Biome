"""Slack ingester — Phase 1 stub.

The student confirmed no Slack workspace is available for testing.
This file provides the full class structure, docstrings, and interface
so that:

1. The codebase is architecturally complete (DECISIONS.md D013).
2. A future engineer can implement it by filling in the ``_fetch_messages``
   and ``_build_node`` methods.
3. The Prefect flow in Phase 5 can reference ``SlackIngester`` without
   runtime errors (it will just return an empty ``IngestResult``).

To activate:
    1. Create a Slack app at https://api.slack.com/apps
    2. Add OAuth scopes: channels:history, channels:read, groups:history,
       im:history, mpim:history, users:read
    3. Set SLACK_BOT_TOKEN and SLACK_WORKSPACE_ID in .env
    4. Fill in ``_fetch_messages`` below using the ``slack_sdk`` library.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from .base import Ingester, IngestResult
from .models import DocumentMetadata, DocumentNode

logger = logging.getLogger(__name__)


class SlackIngester(Ingester):
    """Ingests Slack messages at the thread level.

    Each Slack thread becomes one ``DocumentNode``. Messages within a thread
    are concatenated as Markdown with speaker labels.

    ACL:
        ``access_scope`` is set to the Slack channel ID so that query-time
        ACL enforcement can filter results to channels the requester can access.

    Incremental ingestion:
        Uses the Slack API ``oldest`` parameter, which accepts a Unix timestamp.
        ``since`` is converted to a Unix timestamp and passed directly to the API.

    Args:
        channel_ids: List of Slack channel IDs to ingest.
                     If empty, all public channels in the workspace are used.
        bot_token: Slack bot token (xoxb-…). Defaults to SLACK_BOT_TOKEN env var.
        workspace_id: Slack workspace/team ID. Defaults to SLACK_WORKSPACE_ID env var.
        max_messages_per_channel: Cap on messages fetched per channel per run.
    """

    source_type = "slack"

    def __init__(
        self,
        channel_ids: list[str] | None = None,
        bot_token: str | None = None,
        workspace_id: str | None = None,
        max_messages_per_channel: int = 1000,
    ) -> None:
        self.channel_ids: list[str] = channel_ids or []
        self.bot_token: str = bot_token or os.getenv("SLACK_BOT_TOKEN", "")
        self.workspace_id: str = workspace_id or os.getenv("SLACK_WORKSPACE_ID", "")
        self.max_messages_per_channel = max_messages_per_channel
        self._client: Any = None   # slack_sdk.WebClient, lazy-loaded

    # ------------------------------------------------------------------
    # Lazy SDK initialisation
    # ------------------------------------------------------------------

    def _get_client(self) -> Any | None:
        """Return a cached Slack WebClient, or None if SDK / token unavailable."""
        if self._client is not None:
            return self._client
        if not self.bot_token:
            logger.warning(
                "SlackIngester: SLACK_BOT_TOKEN is not set. Ingestion will be skipped. "
                "Set SLACK_BOT_TOKEN in .env to activate Slack ingestion."
            )
            return None
        try:
            from slack_sdk import WebClient  # noqa: PLC0415
            self._client = WebClient(token=self.bot_token)
            logger.info("Slack WebClient initialised.")
        except ImportError:
            logger.warning("slack_sdk not installed (`pip install slack-sdk`). Skipping Slack ingestion.")
            self._client = None
        return self._client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ingest(self, since: datetime | None = None) -> IngestResult:
        """Ingest Slack threads.

        Args:
            since: If provided, only fetch messages newer than this timestamp
                   (passed as ``oldest=<unix_ts>`` to the Slack API).

        Returns:
            ``IngestResult`` with one ``DocumentNode`` per thread. Returns an
            empty result when the bot token is missing or SDK is not installed.
        """
        client = self._get_client()
        if client is None:
            logger.info("SlackIngester: no client available — returning empty result.")
            return IngestResult()

        since = self._normalize_ts(since)
        result = IngestResult()

        # ----------------------------------------------------------------
        # TODO: Implement when Slack workspace is available.
        # ----------------------------------------------------------------
        # Pseudocode:
        #
        # channels = self.channel_ids or self._list_all_channels(client)
        # for channel_id in channels:
        #     oldest_ts = str(since.timestamp()) if since else "0"
        #     messages = self._fetch_messages(client, channel_id, oldest_ts)
        #     threads = self._group_by_thread(messages)
        #     for thread_ts, thread_messages in threads.items():
        #         node = self._build_node(channel_id, thread_ts, thread_messages)
        #         result.documents.append(node)
        #         result.summary.documents_processed += 1
        # ----------------------------------------------------------------

        logger.info(
            "SlackIngester: stub — no messages ingested. "
            "Implement _fetch_messages() to activate Slack ingestion."
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers (to be implemented)
    # ------------------------------------------------------------------

    def _list_all_channels(self, client: Any) -> list[str]:
        """Return all public channel IDs in the workspace.

        TODO: Call client.conversations_list(types="public_channel") and
        paginate using cursor.
        """
        raise NotImplementedError("_list_all_channels not yet implemented.")

    def _fetch_messages(
        self, client: Any, channel_id: str, oldest_ts: str
    ) -> list[dict[str, Any]]:
        """Fetch messages from a channel since ``oldest_ts``.

        TODO: Call client.conversations_history(channel=channel_id, oldest=oldest_ts)
        and paginate using cursor until all messages are collected up to
        ``self.max_messages_per_channel``.
        """
        raise NotImplementedError("_fetch_messages not yet implemented.")

    def _group_by_thread(
        self, messages: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group messages by thread_ts.

        A message with no ``thread_ts`` is its own single-message thread.
        Messages that are replies (``thread_ts != ts``) belong to the parent.
        """
        threads: dict[str, list[dict[str, Any]]] = {}
        for msg in messages:
            key = msg.get("thread_ts") or msg["ts"]
            threads.setdefault(key, []).append(msg)
        return threads

    def _build_node(
        self,
        channel_id: str,
        thread_ts: str,
        messages: list[dict[str, Any]],
    ) -> DocumentNode:
        """Convert a list of thread messages into a single ``DocumentNode``.

        TODO: Resolve user IDs to display names using client.users_info().
        Format as Markdown:
            **[username]** (2024-01-15 14:32): <message text>
            ...
        """
        # Placeholder text — replace with real formatting once implemented.
        text = "\n".join(
            f"**[{m.get('user', 'unknown')}]**: {m.get('text', '')}"
            for m in messages
        )
        return DocumentNode(
            page_content=text.strip(),
            metadata=DocumentMetadata(
                source_type="slack",
                source_name=f"slack/{channel_id}/{thread_ts}",
                access_level="internal",
                access_scope=[channel_id, "internal"],
                extra={
                    "channel_id": channel_id,
                    "thread_ts": thread_ts,
                    "message_count": len(messages),
                    "parser": "slack_sdk",
                },
            ),
        )
