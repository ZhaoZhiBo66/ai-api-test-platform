import json

import pytest
from fastapi import HTTPException

from app.models.result import TestResult as ResultModel, TestRun as RunModel
from app.services import report_service
from app.utils.config import get_settings


@pytest.fixture
def report_root(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "root_dir", tmp_path)
    return tmp_path


def test_builds_allure_files_from_persisted_run(report_root, db_session):
    run = RunModel(interface_id=None, suite_id=None, status="failed", total=1, passed=0, failed=1)
    db_session.add(run)
    db_session.commit()
    db_session.add(
        ResultModel(
            run_id=run.id,
            case_id=1,
            case_name="金额校验失败",
            status="failed",
            status_code=201,
            request_data={"quantity": 2},
            response_data={"total": 200.8},
            assertion_message="期望199.8，实际200.8",
        )
    )
    db_session.commit()

    report = report_service.generate_allure_from_run(db_session, run.id)
    files = list((report_root / "reports" / "allure-results" / report["execution_id"]).glob("*-result.json"))

    assert report["result_count"] == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["statusDetails"]["message"] == "期望199.8，实际200.8"


def test_report_requires_existing_run(db_session):
    with pytest.raises(HTTPException) as error:
        report_service.generate_allure_from_run(db_session, 999)
    assert error.value.status_code == 404


def test_report_requires_results(db_session):
    run = RunModel(status="queued")
    db_session.add(run)
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        report_service.generate_allure_from_run(db_session, run.id)
    assert error.value.status_code == 409


def test_report_endpoint_requires_run_id(client):
    response = client.post("/reports/allure")
    assert response.status_code == 422
