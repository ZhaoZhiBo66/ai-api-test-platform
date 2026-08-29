from types import SimpleNamespace

from app.api import suite_api
from app.models.interface import ApiInterface
from app.models.result import TestRun as RunModel
from app.models.testcase import TestCase as CaseModel


def make_case(db_session, name="用例") -> CaseModel:
    interface = ApiInterface(name=f"接口-{name}", url="https://api.example.com", method="GET")
    db_session.add(interface)
    db_session.flush()
    case = CaseModel(interface_id=interface.id, case_name=name, enabled=True)
    db_session.add(case)
    db_session.commit()
    return case


def test_suite_crud_and_case_order(client, db_session):
    first = make_case(db_session, "登录")
    second = make_case(db_session, "下单")

    created = client.post(
        "/suites",
        json={"name": "核心回归", "description": "主链路", "case_ids": [second.id, first.id]},
    )
    assert created.status_code == 201
    suite_id = created.json()["id"]
    assert created.json()["case_ids"] == [second.id, first.id]

    listed = client.get("/suites?enabled=true")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "核心回归"

    updated = client.put(
        f"/suites/{suite_id}",
        json={"description": "更新说明", "case_ids": [first.id, second.id], "fail_fast": True},
    )
    assert updated.status_code == 200
    assert updated.json()["case_ids"] == [first.id, second.id]
    assert updated.json()["fail_fast"] is True

    deleted = client.delete(f"/suites/{suite_id}")
    assert deleted.status_code == 204


def test_suite_rejects_missing_duplicate_and_disabled_cases(client, db_session):
    case = make_case(db_session)
    duplicate = client.post("/suites", json={"name": "重复", "case_ids": [case.id, case.id]})
    assert duplicate.status_code == 422

    missing = client.post("/suites", json={"name": "缺失", "case_ids": [999]})
    assert missing.status_code == 404

    case.enabled = False
    db_session.commit()
    disabled = client.post("/suites", json={"name": "停用", "case_ids": [case.id]})
    assert disabled.status_code == 422


def test_case_in_suite_cannot_be_deleted(client, db_session):
    case = make_case(db_session)
    suite = client.post("/suites", json={"name": "保护用例", "case_ids": [case.id]})
    assert suite.status_code == 201

    response = client.delete(f"/cases/{case.id}")
    assert response.status_code == 409
    assert "回归套件" in response.json()["detail"]


def test_suite_with_history_cannot_be_deleted(client, db_session):
    case = make_case(db_session)
    suite_id = client.post("/suites", json={"name": "已有历史", "case_ids": [case.id]}).json()["id"]
    db_session.add(RunModel(suite_id=suite_id, status="passed", total=1, passed=1, failed=0))
    db_session.commit()

    response = client.delete(f"/suites/{suite_id}")
    assert response.status_code == 409


def test_suite_sync_run_uses_suite_defaults(client, db_session, monkeypatch):
    case = make_case(db_session)
    suite_id = client.post(
        "/suites",
        json={"name": "快速失败", "case_ids": [case.id], "fail_fast": True, "analyze_by_ai": False},
    ).json()["id"]
    seen = {}

    def fake_run_cases(*args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(id=8, status="passed", total=1, passed=1, failed=0)

    monkeypatch.setattr(suite_api, "run_cases", fake_run_cases)
    response = client.post(f"/suites/{suite_id}/runs", json={})

    assert response.status_code == 200
    assert response.json()["run_id"] == 8
    assert seen["case_ids"] == [case.id]
    assert seen["suite_id"] == suite_id
    assert seen["fail_fast"] is True


def test_suite_trend_reports_latest_pass_rate(client, db_session):
    case = make_case(db_session)
    suite_id = client.post("/suites", json={"name": "趋势", "case_ids": [case.id]}).json()["id"]
    db_session.add_all(
        [
            RunModel(suite_id=suite_id, status="passed", total=2, passed=2, failed=0),
            RunModel(suite_id=suite_id, status="failed", total=2, passed=1, failed=1),
        ]
    )
    db_session.commit()

    response = client.get(f"/suites/{suite_id}/trends")
    assert response.status_code == 200
    assert response.json()["latest_pass_rate"] == 50.0
    assert response.json()["run_count"] == 2
