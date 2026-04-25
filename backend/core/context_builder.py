from __future__ import annotations

from database.connection import get_db
import database.repository as repo
from domains.soul.memory import MemoryManager


def _est_tokens(text: str) -> int:
    # 한국어 기준 2자 ≈ 1토큰, 보수적으로 추정
    return max(1, len(text) // 2)


def _summary_block(summaries: list[dict]) -> str:
    if not summaries:
        return ""
    lines = ["[이전 대화 요약]"]
    for s in summaries:
        lines.append(f"- {s['summary']}")
    return "\n".join(lines)


def _fact_block(facts: list[dict]) -> str:
    if not facts:
        return ""
    lines = ["[사용자 정보]"]
    for f in facts:
        lines.append(f"- {f['content']}")
    return "\n".join(lines)


async def build_messages(
    system_prompt: str,
    memory: MemoryManager,
    user_text: str,
    token_budget: int,
) -> list[dict]:
    """
    Tier 3 → Tier 2 → Tier 1 순서로 컨텍스트 조립.
    token_budget 초과 시 Tier 3 (오래된 것), 낮은 importance facts, 오래된 턴 순 컷오프.
    """
    db = await get_db()
    used = _est_tokens(system_prompt) + _est_tokens(user_text)

    # Tier 3: 최신 세션 요약 — 예산 안에서 최신순으로 선택
    summaries = await repo.get_recent_summaries(db, limit=10)
    selected_summaries: list[dict] = []
    for s in summaries:
        cost = _est_tokens(s["summary"])
        if used + cost > token_budget:
            break
        selected_summaries.append(s)
        used += cost

    # Tier 2: facts — 예산 안에서 importance 높은 순
    facts = await memory.get_facts(min_importance=1, limit=20)
    selected_facts: list[dict] = []
    for f in facts:
        cost = _est_tokens(f["content"])
        if used + cost > token_budget:
            break
        selected_facts.append(f)
        used += cost

    # Tier 1: 최근 턴 — 남은 예산 안에서 오래된 것부터 제거
    turns = await memory.get_recent_turns(n=20)
    budget_for_turns = token_budget - used
    turn_tokens = sum(_est_tokens(t["content"]) for t in turns)
    while turns and turn_tokens > budget_for_turns:
        turn_tokens -= _est_tokens(turns[0]["content"])
        turns = turns[1:]

    # system prompt에 Tier 3/2 블록 주입
    full_system = system_prompt
    sb = _summary_block(selected_summaries)
    fb = _fact_block(selected_facts)
    if sb:
        full_system += f"\n\n{sb}"
    if fb:
        full_system += f"\n\n{fb}"

    messages: list[dict] = [{"role": "system", "content": full_system}]
    messages.extend({"role": t["role"], "content": t["content"]} for t in turns)
    messages.append({"role": "user", "content": user_text})

    return messages
