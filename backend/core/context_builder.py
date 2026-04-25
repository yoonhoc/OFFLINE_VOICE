from __future__ import annotations

import asyncio

from core.tokenizer import count_tokens
from database.connection import get_db
import database.repository as repo
from domains.soul.memory import MemoryManager


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
    token_budget 초과 시 Tier 3(오래된 것), 낮은 importance facts, 오래된 턴 순 컷오프.
    """
    db = await get_db()

    summaries = await repo.get_recent_summaries(db, limit=10)
    facts     = await memory.get_facts(min_importance=1, limit=20)
    turns     = await memory.get_recent_turns(n=20)

    # 토큰 수 일괄 병렬 계산 (HTTP 왕복 1라운드)
    texts = (
        [system_prompt, user_text]
        + [s["summary"]  for s in summaries]
        + [f["content"]  for f in facts]
        + [t["content"]  for t in turns]
    )
    counts = await asyncio.gather(*(count_tokens(t) for t in texts))

    sys_tok, user_tok = counts[0], counts[1]
    o = 2
    summary_toks = counts[o : o + len(summaries)]; o += len(summaries)
    fact_toks    = counts[o : o + len(facts)];     o += len(facts)
    turn_toks    = counts[o : o + len(turns)]

    used = sys_tok + user_tok

    # Tier 3: 최신 요약부터 예산 안에서 채우기
    selected_summaries: list[dict] = []
    for s, cost in zip(summaries, summary_toks):
        if used + cost > token_budget:
            break
        selected_summaries.append(s)
        used += cost

    # Tier 2: importance 높은 fact부터 예산 안에서 채우기
    selected_facts: list[dict] = []
    for f, cost in zip(facts, fact_toks):
        if used + cost > token_budget:
            break
        selected_facts.append(f)
        used += cost

    # Tier 1: 남은 예산 안에서 오래된 턴부터 제거
    budget_for_turns = token_budget - used
    turn_total = sum(turn_toks)
    while turns and turn_total > budget_for_turns:
        turn_total -= turn_toks[0]
        turns      = turns[1:]
        turn_toks  = turn_toks[1:]

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
