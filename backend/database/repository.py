from __future__ import annotations
from datetime import datetime, timezone
from database.connection import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


#Tier 1: turns

async def insert_turn(
    session_id: str,
    turn_num: int,
    role: str,
    content: str,
    token_count: int = 0,
) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT INTO turns (session_id, turn_num, role, content, token_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, turn_num, role, content, token_count, _now()),
    )
    await db.commit()


async def get_recent_turns(session_id: str, n: int) -> list[dict]:
    """최근 n턴 반환 (오름차순)."""
    db = await get_db()
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
    category: str,
    content: str,
    importance: int,
    source_session: str | None = None,
) -> int:
    """저장된 fact의 id 반환."""
    db = await get_db()
    now = _now()
    cursor = await db.execute(
        """
        INSERT INTO facts (category, content, importance, created_at, last_accessed, source_session)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (category, content, importance, now, now, source_session),
    )
    await db.commit()
    return cursor.lastrowid


async def get_facts(min_importance: int = 1, limit: int = 20) -> list[dict]:
    """importance 높고 최근 접근한 순으로 반환."""
    db = await get_db()
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


async def touch_facts(ids: list[int]) -> None:
    """last_accessed 갱신 — LRU."""
    if not ids:
        return
    db = await get_db()
    placeholders = ",".join("?" * len(ids))
    await db.execute(
        f"UPDATE facts SET last_accessed = ? WHERE id IN ({placeholders})",
        [_now(), *ids],
    )
    await db.commit()


# Tier 3: session_summaries

async def insert_summary(
    session_id: str,
    summary: str,
    token_count: int,
    started_at: str,
    ended_at: str | None = None,
) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT OR REPLACE INTO session_summaries
            (session_id, summary, token_count, started_at, ended_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, summary, token_count, started_at, ended_at),
    )
    await db.commit()


async def get_recent_summaries(limit: int = 5) -> list[dict]:
    """최신 세션 요약 반환 (최신순)."""
    db = await get_db()
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
