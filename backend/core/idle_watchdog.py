"""
Idle Watchdog — 매 턴 reset(), idle 시간 초과 시 세션 배치 1회 실행.

reset()  : 발화 처리 직후 호출. 기존 타이머 취소 + 새 타이머 시작.
stop()   : 앱 종료 시 호출. 타이머 영구 정지.
"""

from __future__ import annotations

import asyncio
import logging

from config import config
from core.pipeline import VoicePipeline
from core.session_batch import run_session_batch

logger = logging.getLogger(__name__)


class IdleWatchdog:

    def __init__(self, pipeline: VoicePipeline, timeout_sec: int | None = None):
        self.pipeline = pipeline
        self.timeout  = timeout_sec or config.IDLE_TIMEOUT_SEC
        self._task: asyncio.Task | None = None

    def reset(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _run(self) -> None:
        try:
            await asyncio.sleep(self.timeout)
        except asyncio.CancelledError:
            return
        logger.info(f"idle {self.timeout}초 경과 — 세션 배치 자동 트리거")
        try:
            await run_session_batch(self.pipeline.llm, self.pipeline.memory)
        except Exception as e:
            logger.warning(f"idle batch 실패: {e}")
