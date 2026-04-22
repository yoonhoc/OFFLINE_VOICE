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
    # 각 커밋에서 테이블 DDL이 여기에 추가된다
    await db.commit()
