from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.environment import TestEnvironment
from app.models.result import TestRun
from app.schemas.testcase_schema import RunRequest
from app.services.test_runner import run_cases, select_cases
from app.utils.config import get_settings
from app.utils.logger import logger
from app.utils.redaction import redact
from app.utils.time_utils import utc_now


TERMINAL_STATUSES = {"passed", "failed", "cancelled", "interrupted"}


class AsyncRunManager:
    def __init__(self) -> None:
        settings = get_settings()
        self.executor = ThreadPoolExecutor(max_workers=settings.async_workers, thread_name_prefix="api-test-run")
        self.max_queued_runs = settings.max_queued_runs
        self.futures: dict[int, Future] = {}
        self.lock = Lock()

    def submit(self, run_id: int, payload: dict[str, Any]) -> None:
        with self.lock:
            active = sum(not future.done() for future in self.futures.values())
            if active >= self.max_queued_runs:
                raise HTTPException(status_code=429, detail="异步测试任务队列已满，请稍后重试")
            future = self.executor.submit(self._worker, run_id, payload)
            self.futures[run_id] = future

    def cancel(self, run_id: int) -> bool:
        with self.lock:
            future = self.futures.get(run_id)
            return bool(future and future.cancel())

    @staticmethod
    def _worker(run_id: int, payload: dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            run = db.get(TestRun, run_id)
            if run is None:
                return
            if run.cancel_requested:
                run.status = "cancelled"
                run.finished_at = utc_now()
                db.commit()
                return
            run_cases(
                db,
                interface_id=payload.get("interface_id"),
                case_ids=payload.get("case_ids") or [],
                analyze_by_ai=payload.get("analyze_by_ai", True),
                environment_id=payload.get("environment_id"),
                variables=payload.get("variables") or {},
                fail_fast=payload.get("fail_fast", False),
                existing_run=run,
                suite_id=payload.get("suite_id"),
            )
        except Exception as exc:
            logger.exception("异步测试任务执行失败: run_id={}", run_id)
            db.rollback()
            run = db.get(TestRun, run_id)
            if run is not None:
                run.status = "failed"
                run.ai_summary = f"任务执行异常: {exc}"
                run.finished_at = utc_now()
                db.commit()
        finally:
            db.close()


async_run_manager = AsyncRunManager()


def create_async_run(db: Session, payload: RunRequest, *, suite_id: int | None = None) -> TestRun:
    cases = select_cases(db, payload.interface_id, payload.case_ids)
    if payload.environment_id is not None:
        environment = db.get(TestEnvironment, payload.environment_id)
        if environment is None:
            raise HTTPException(status_code=404, detail="测试环境不存在")
        if not environment.enabled:
            raise HTTPException(status_code=422, detail="测试环境已禁用")
    run = TestRun(
        interface_id=payload.interface_id,
        suite_id=suite_id,
        environment_id=payload.environment_id,
        status="queued",
        total=len(cases),
        variables=redact(payload.variables),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        worker_payload = payload.model_dump()
        worker_payload["suite_id"] = suite_id
        async_run_manager.submit(run.id, worker_payload)
    except Exception:
        run.status = "failed"
        run.finished_at = utc_now()
        db.commit()
        raise
    return run


def cancel_run(db: Session, run_id: int) -> TestRun:
    run = db.get(TestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="测试任务不存在")
    if run.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail=f"任务已结束，当前状态: {run.status}")
    run.cancel_requested = True
    cancelled_before_start = async_run_manager.cancel(run_id)
    if cancelled_before_start:
        run.status = "cancelled"
        run.finished_at = utc_now()
    db.commit()
    db.refresh(run)
    return run


def mark_interrupted_runs(db: Session) -> int:
    runs = db.query(TestRun).filter(TestRun.status.in_(["queued", "running"])).all()
    for run in runs:
        run.status = "interrupted"
        run.finished_at = utc_now()
        run.ai_summary = "应用重启，进程内异步任务已中断，请重新提交"
    if runs:
        db.commit()
    return len(runs)
