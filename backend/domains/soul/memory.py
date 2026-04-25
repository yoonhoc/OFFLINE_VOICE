from __future__ import annotations

import database.repository as repo
from database.connection import get_db, get_session_id


class MemoryManager:
    """Tier 1/2 메모리 읽기/쓰기. 트랜잭션 바운더리 담당 즉 서비스"""

    def __init__(self) -> None:
        self._session_id = get_session_id()
        self._turn_num = 0

    @property #getter
    def session_id(self) -> str:
        return self._session_id

    # Tier 1: turns
    async def add_turn(self, role: str, content: str, token_count: int = 0) -> None:
        self._turn_num += 1
        db = await get_db()
        await repo.insert_turn(db, self._session_id, self._turn_num, role, content, token_count)
        await db.commit()

    async def get_recent_turns(self, n: int) -> list[dict]:
        db = await get_db()
        return await repo.get_recent_turns(db, self._session_id, n)

    #Tier 2: facts
    async def get_facts(self, min_importance: int = 1, limit: int = 20) -> list[dict]:
        db = await get_db()
        facts = await repo.get_facts(db, min_importance, limit)
        if facts:
            ids = [f["id"] for f in facts]
            await repo.touch_facts(db, ids)
            await db.commit()
        return facts
