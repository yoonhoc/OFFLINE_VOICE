"""세션 종료 배치 — 대화에서 장기 기억 facts 추출 후 DB 저장."""

from __future__ import annotations

import json
import logging
import re

from database.connection import get_db
import database.repository as repo
from domains.llm.llama_engine import LlamaEngine
from domains.soul.memory import MemoryManager

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
아래는 사용자와 AI(아이리)의 대화 기록입니다.
이 대화에서 사용자에 대해 장기적으로 기억할 가치가 있는 사실만 추출해주세요.

추출 기준:
- 사용자가 직접 말하거나 문맥상 명확하게 드러난 사실만 포함
- 추측·유추·일시적 감정(오늘 피곤함, 지금 배고픔 등)은 제외
- 대화에서 반복되거나 사용자가 강조한 정보를 우선시

카테고리:
- preference : 좋아하는 것/싫어하는 것 (음식, 음악, 활동, 취미 등)
- personal   : 이름, 나이, 직업, 거주지 등 개인 신상 정보
- event      : 사용자가 언급한 과거 경험 또는 예정된 중요 사건
- relation   : 가족, 친구, 연인, 반려동물 등 인간관계

importance 기준:
- 1 : 가벼운 취향 (예: 아이스 아메리카노를 즐겨 마심, 고양이를 좋아함)
- 2 : 중요한 개인 정보 (예: 직업이 개발자, 서울 거주, 고양이를 키움)
- 3 : 핵심 정체성 정보 (예: 이름, 나이, 가족 구성원)

주의사항:
- 동일한 사실을 중복 추출하지 말 것
- 확실하지 않은 정보는 포함하지 말 것
- 아이리(AI)에 대한 정보가 아니라 사용자에 대한 정보만 추출

응답은 반드시 순수 JSON 배열만 출력하세요. 설명·마크다운·코드블록 없이.
추출할 사실이 없으면 [] 를 출력하세요.

출력 형식:
[
  {{"category": "preference", "content": "매운 음식을 싫어함", "importance": 1}},
  {{"category": "personal",   "content": "이름은 김민준",      "importance": 3}}
]

대화 기록:
{conversation}"""


def _format_turns(turns: list[dict]) -> str:
    lines = []
    for t in turns:
        label = "사용자" if t["role"] == "user" else "아이리"
        lines.append(f"{label}: {t['content']}")
    return "\n".join(lines)


def _parse_facts(response: str) -> list[dict]:
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if not match:
        return []
    try:
        facts = json.loads(match.group())
        return [
            f for f in facts
            if isinstance(f, dict)
            and f.get("category") in ("preference", "personal", "event", "relation")
            and isinstance(f.get("content"), str)
            and f.get("content").strip()
            and isinstance(f.get("importance"), int)
            and 1 <= f["importance"] <= 3
        ]
    except json.JSONDecodeError:
        return []


async def run_session_batch(llm: LlamaEngine, memory: MemoryManager) -> None:
    """disconnect() 호출 전 실행. 대화 → facts 추출 → DB 저장."""
    turns = await memory.get_recent_turns(n=200)
    if not turns:
        return

    conversation = _format_turns(turns)
    prompt = _EXTRACTION_PROMPT.format(conversation=conversation)
    messages = [{"role": "user", "content": prompt}]

    logger.info("세션 종료 배치 시작")
    try:
        response = await llm.generate(messages)
    except Exception as e:
        logger.warning(f"facts 추출 실패: {e}")
        return

    facts = _parse_facts(response)
    if not facts:
        logger.info("추출된 facts 없음")
        return

    db = await get_db()
    try:
        for fact in facts:
            await repo.insert_fact(
                db,
                category=fact["category"],
                content=fact["content"],
                importance=fact["importance"],
                source_session=memory.session_id,
            )
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning(f"facts 저장 실패, 롤백: {e}")
        return

    logger.info(f"facts {len(facts)}개 저장 (세션 {memory.session_id[:8]})")
