"""LLM 토큰 수 계산 — llama-server /tokenize 사용, 실패 시 문자 길이 근사."""

from __future__ import annotations

import asyncio
import logging
import requests

from config import config

logger = logging.getLogger(__name__)


def _approx_tokens(text: str) -> int:
    # 한국어 기준 2자 ≈ 1토큰, 보수적 근사
    return max(1, len(text) // 2)


def _count_via_server(text: str) -> int | None:
    try:
        r = requests.post(
            f"{config.LLM_SERVER_URL}/tokenize",
            json={"content": text},
            timeout=2,
        )
        if r.status_code == 200:
            return len(r.json().get("tokens", []))
    except Exception as e:
        logger.debug(f"/tokenize 실패: {e}")
    return None


async def count_tokens(text: str) -> int:
    """텍스트 토큰 수 반환. 서버 죽었거나 응답 비정상이면 문자 길이 근사로 폴백."""
    if not text:
        return 0
    loop = asyncio.get_event_loop()
    n = await loop.run_in_executor(None, _count_via_server, text)
    return n if n is not None else _approx_tokens(text)
