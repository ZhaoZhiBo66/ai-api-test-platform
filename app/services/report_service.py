import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.result import TestResult, TestRun
from app.utils.config import get_settings


def generate_allure_from_run(db: Session, run_id: int) -> dict:
    """Build isolated Allure result files from persisted results without rerunning targets."""
    settings = get_settings()
    run = db.get(TestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="测试任务不存在")
    results = (
        db.query(TestResult).filter(TestResult.run_id == run_id).order_by(TestResult.id.asc()).all()
    )
    if not results:
        raise HTTPException(status_code=409, detail="该任务还没有可生成报告的测试结果")

    execution_id = f"run-{run_id}-{uuid4().hex[:8]}"
    allure_dir = settings.root_dir / "reports" / "allure-results" / execution_id
    allure_dir.mkdir(parents=True, exist_ok=False)
    for result in results:
        item_uuid = str(uuid4())
        duration = result.duration_ms or 0
        stop = int(result.created_at.timestamp() * 1000)
        start = max(0, stop - duration)
        payload = {
            "uuid": item_uuid,
            "name": result.case_name,
            "fullName": f"platform.run_{run_id}.case_{result.case_id}",
            "status": "passed" if result.status == "passed" else "failed",
            "statusDetails": {
                "message": result.assertion_message or result.ai_analysis,
                "trace": result.ai_analysis,
            },
            "start": start,
            "stop": stop,
            "labels": [
                {"name": "feature", "value": "接口回归质量门禁"},
                {"name": "suite", "value": f"run-{run_id}"},
                {"name": "framework", "value": "platform"},
            ],
            "parameters": [
                {"name": "status_code", "value": repr(result.status_code)},
                {"name": "duration_ms", "value": repr(result.duration_ms)},
                {"name": "request", "value": json.dumps(result.request_data, ensure_ascii=False)},
                {"name": "response", "value": json.dumps(result.response_data, ensure_ascii=False)},
            ],
        }
        (allure_dir / f"{item_uuid}-result.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    return {
        "run_id": run_id,
        "execution_id": execution_id,
        "result_count": len(results),
        "allure_results": str(allure_dir),
    }
