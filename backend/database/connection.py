"""
aiosqlite 연결 관리 모듈.

- connect()   : 앱 시작 시 호출 (DB 파일 열기 + 스키마 초기화 + 세션 ID 생성)
- disconnect(): 앱 종료 시 호출
- get_db()    : 현재 연결 객체 반환 (리포지터리 레이어에서 사용)
- get_session_id(): 현재 세션 UUID 반환
"""

from __future__ import annotations

import uuid
import logging
import aiosqlite
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None
_session_id: str = ""


def get_session_id() -> str:
    """현재 앱 실행 세션의 UUID를 반환한다."""
    return _session_id


async def get_db() -> aiosqlite.Connection:
    """활성 DB 연결을 반환한다. connect() 전에 호출하면 RuntimeError."""
    if _db is None:
        raise RuntimeError("DB가 초기화되지 않았습니다. connect()를 먼저 호출하세요.")
    return _db


async def connect() -> None:
    """
    DB 파일을 열고, 스키마를 초기화하며, 세션 ID를 생성한다.
    FastAPI lifespan 또는 CLI 진입점에서 최초 1회 호출.
    """
    global _db, _session_id

    _session_id = str(uuid.uuid4())
    logger.info(f"[DB] 세션 시작: {_session_id}")

    db_path = Path(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(str(db_path))
    _db.row_factory = aiosqlite.Row

    # WAL 모드: 읽기/쓰기 동시성 향상, 배치 작업과 대화 처리 충돌 방지
    await _db.execute("PRAGMA journal_mode=WAL")
    # 외래키 제약 활성화
    await _db.execute("PRAGMA foreign_keys=ON")

    from database.schema import init_schema
    await init_schema(_db)

    logger.info(f"[DB] 연결 완료: {db_path}")


async def disconnect() -> None:
    """DB 연결을 안전하게 닫는다. FastAPI lifespan 또는 CLI 종료 시 호출."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("[DB] 연결 종료")
