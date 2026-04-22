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

    # ── Tier 3: 세션 요약 ────────────────────────────────────────────────
    # 과거 세션을 LLM이 압축한 에피소드 기억.
    # 배치 작업(Phase 4)에서 세션 종료 또는 1시간 idle 시 생성된다.
    await db.execute("""
        CREATE TABLE IF NOT EXISTS session_summaries (
            session_id  TEXT    PRIMARY KEY,
            summary     TEXT    NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            started_at  DATETIME NOT NULL,
            ended_at    DATETIME
        )
    """)
    # 최신 세션 요약부터 역순 조회용 (Tier 3 조립 시 최근 N개 선택)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_summaries_started
        ON session_summaries(started_at DESC)
    """)

    # ── Tier 2: 장기 사용자 사실 ─────────────────────────────────────────
    # 세션을 넘어 영구 보존되는 사용자 관련 사실.
    # 배치 작업(Phase 4)에서 LLM이 대화를 분석해 추출·저장한다.
    await db.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            category       TEXT    NOT NULL
                               CHECK(category IN ('preference','personal','event','relation')),
            content        TEXT    NOT NULL,
            importance     INTEGER NOT NULL CHECK(importance BETWEEN 1 AND 3),
            created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_accessed  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            source_session TEXT
        )
    """)
    # importance 높고 최근 접근한 fact 우선 조회용
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_rank
        ON facts(importance DESC, last_accessed DESC)
    """)

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
