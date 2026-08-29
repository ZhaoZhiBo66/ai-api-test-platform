from app.models.interface import ApiInterface
from app.models.result import TestResult as ResultModel
from app.models.testcase import TestCase as CaseModel
from app.services import async_run_service, test_runner


class FakeResponse:
    status_code = 200
    headers = {"Content-Type": "application/json"}

    def json(self):
        return {"code": 0}


def make_case(db_session):
    interface = ApiInterface(
        name="查询", url="https://api.example.com/query", method="GET", headers={}, body={}
    )
    db_session.add(interface)
    db_session.commit()
    case = CaseModel(
        interface_id=interface.id,
        case_name="查询成功",
        data={},
        expected_status_code=200,
        expected_json={"code": 0},
    )
    db_session.add(case)
    db_session.commit()
    return interface, case


def test_run_and_result_query_endpoints(client, db_session, monkeypatch):
    interface, case = make_case(db_session)
    monkeypatch.setattr(test_runner, "_send_request", lambda interface, data: FakeResponse())

    run_response = client.post(
        "/runs", json={"interface_id": interface.id, "analyze_by_ai": False}
    )
    run_id = run_response.json()["run_id"]

    run = client.get(f"/runs/{run_id}")
    assert run.status_code == 200
    assert run.json()["status"] == "passed"
    page = client.get(f"/runs/{run_id}/results").json()
    assert page["total"] == 1
    assert page["items"][0]["duration_ms"] is not None
    result_id = db_session.query(ResultModel).filter(ResultModel.run_id == run_id).one().id
    assert client.get(f"/results/{result_id}").json()["case_name"] == "查询成功"
    assert client.get("/runs").json()["total"] == 1


def test_async_endpoint_creates_a_queued_run(client, db_session, monkeypatch):
    interface, case = make_case(db_session)
    submitted = {}

    def fake_submit(run_id, payload):
        submitted.update(run_id=run_id, payload=payload)

    monkeypatch.setattr(async_run_service.async_run_manager, "submit", fake_submit)

    response = client.post(
        "/runs/async",
        json={"case_ids": [case.id], "variables": {"tenant": "qa"}, "analyze_by_ai": False},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert submitted["payload"]["case_ids"] == [case.id]


def test_cancel_endpoint_marks_a_queued_run_cancelled(client, db_session, monkeypatch):
    _, case = make_case(db_session)
    monkeypatch.setattr(async_run_service.async_run_manager, "submit", lambda *args: None)
    monkeypatch.setattr(async_run_service.async_run_manager, "cancel", lambda run_id: True)
    run_id = client.post("/runs/async", json={"case_ids": [case.id]}).json()["run_id"]

    response = client.post(f"/runs/{run_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancel_requested"] is True


def test_async_endpoint_validates_selection_before_queueing(client):
    response = client.post("/runs/async", json={"case_ids": [9999]})

    assert response.status_code == 404
