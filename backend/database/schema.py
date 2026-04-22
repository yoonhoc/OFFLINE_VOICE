"""
DB 스키마 초기화 모듈.

init_schema()는 connect() 내부에서 호출된다.
각 테이블은 Phase별 커밋에서 순서대로 추가된다:
  - Tier 1: turns            (Phase 1, Commit 2)
  - Tier 2: facts            (Phase 1, Commit 3)
  - Tier 3: session_summaries (Phase 1, Commit 4)
"""

from __future__ import annotations

import aiosqlite


async def init_schema(db: aiosqlite.Connection) -> None:
    """모든 테이블과 인덱스를 CREATE IF NOT EXISTS로 초기화한다."""

    # ── Tier 1: 대화 턴 원본 ─────────────────────────────────────────────
    # 현재 세션의 날것 대화 기록. 프롬프트 조립 시 가장 최근 N턴을 읽는다.
    await db.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            turn_num    INTEGER NOT NULL,
            role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
            content     TEXT    NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 세션별 턴 조회 및 최신순 정렬에 사용
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_session
        ON turns(session_id, turn_num DESC)
    """)

    await db.commit()
