from __future__ import annotations

import aiosqlite
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


#Tier 1: turns

async def insert_turn(
    db: aiosqlite.Connection,
    session_id: str,
    turn_num: int,
    role: str,
    content: str,
    token_count: int = 0,
) -> None:
    await db.execute(
        """
        INSERT INTO turns (session_id, turn_num, role, content, token_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, turn_num, role, content, token_count, _now()),
    )


async def get_recent_turns(db: aiosqlite.Connection, session_id: str, n: int) -> list[dict]:
    """최근 n턴 반환 (오름차순)."""
    async with db.execute(
        """
        SELECT role, content, token_count, created_at
        FROM turns
        WHERE session_id = ?
        ORDER BY turn_num DESC
        LIMIT ?
        """,
        (session_id, n),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in reversed(rows)]


#Tier 2: facts

async def insert_fact(
    db: aiosqlite.Connection,
    category: str,
    content: str,
    importance: int,
    source_session: str | None = None,
) -> int:
    """저장된 fact의 id 반환."""
    now = _now()
    cursor = await db.execute(
        """
        INSERT INTO facts (category, content, importance, created_at, last_accessed, source_session)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (category, content, importance, now, now, source_session),
    )
    return cursor.lastrowid


async def get_facts(db: aiosqlite.Connection, min_importance: int = 1, limit: int = 20) -> list[dict]:
    """importance 높고 최근 접근한 순으로 반환."""
    async with db.execute(
        """
        SELECT id, category, content, importance, last_accessed
        FROM facts
        WHERE importance >= ?
        ORDER BY importance DESC, last_accessed DESC
        LIMIT ?
        """,
        (min_importance, limit),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def touch_facts(db: aiosqlite.Connection, ids: list[int]) -> None:
    """last_accessed 갱신 — LRU."""
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    await db.execute(
        f"UPDATE facts SET last_accessed = ? WHERE id IN ({placeholders})",
        [_now(), *ids],
    )


# Tier 3: session_summaries

async def insert_summary(
    db: aiosqlite.Connection,
    session_id: str,
    summary: str,
    token_count: int,
    started_at: str,
    ended_at: str | None = None,
) -> None:
    await db.execute(
        """
        INSERT OR REPLACE INTO session_summaries
            (session_id, summary, token_count, started_at, ended_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, summary, token_count, started_at, ended_at),
    )


async def get_recent_summaries(db: aiosqlite.Connection, limit: int = 5) -> list[dict]:
    """최신 세션 요약 반환 (최신순)."""
    async with db.execute(
        """
        SELECT session_id, summary, token_count, started_at, ended_at
        FROM session_summaries
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (limit,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]
