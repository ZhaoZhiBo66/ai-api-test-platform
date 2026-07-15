import pytest

from app.models.interface import ApiInterface

# Aliased away from their Test* names: pytest tries to collect any class called
# Test* as a test suite and warns when it cannot.
from app.models.result import TestResult as ResultModel
from app.models.result import TestRun as RunModel
from app.models.testcase import TestCase as CaseModel
from app.services import test_runner


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.fixture
def interface(db_session) -> ApiInterface:
    item = ApiInterface(name="登录", url="https://api.example.com/login", method="POST", headers={}, body={})
    db_session.add(item)
    db_session.commit()
    return item


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if anything reaches out over HTTP instead of silently hanging."""

    def forbidden(*args, **kwargs):
        raise AssertionError("test made a real HTTP call")

    for verb in ["get", "post", "put", "delete", "patch"]:
        monkeypatch.setattr(test_runner.requests, verb, forbidden)


def make_case(db_session, interface, **overrides) -> CaseModel:
    fields = {
        "interface_id": interface.id,
        "case_name": "用例",
        "data": {"username": "admin"},
        "expected_status_code": 200,
        "expected_json": {},
        "sql_check": {},
    }
    fields.update(overrides)
    case = CaseModel(**fields)
    db_session.add(case)
    db_session.commit()
    return case


def stub_request(monkeypatch, response: FakeResponse):
    monkeypatch.setattr(test_runner, "_send_request", lambda interface, data: response)


# --- _assert_response -------------------------------------------------------


def test_assert_response_accepts_a_match(db_session, interface):
    case = make_case(db_session, interface, expected_json={"code": 0})

    assert test_runner._assert_response(200, {"code": 0}, case) == ""


def test_assert_response_reports_status_code_mismatch(db_session, interface):
    case = make_case(db_session, interface, expected_status_code=201)

    message = test_runner._assert_response(500, {}, case)

    assert "期望 201" in message and "实际 500" in message


def test_assert_response_reports_every_bad_field(db_session, interface):
    case = make_case(db_session, interface, expected_json={"code": 0, "msg": "ok"})

    message = test_runner._assert_response(200, {"code": 1, "msg": "bad"}, case)

    assert message.count(";") == 1
    assert "字段 code" in message and "字段 msg" in message


def test_assert_response_ignores_extra_response_fields(db_session, interface):
    case = make_case(db_session, interface, expected_json={"code": 0})

    assert test_runner._assert_response(200, {"code": 0, "extra": "x"}, case) == ""


# --- _parse_response --------------------------------------------------------


def test_parse_response_passes_through_an_object():
    assert test_runner._parse_response(FakeResponse(payload={"a": 1})) == {"a": 1}


def test_parse_response_wraps_a_non_object_body():
    assert test_runner._parse_response(FakeResponse(payload=[1, 2])) == {"data": [1, 2]}


def test_parse_response_falls_back_to_text():
    assert test_runner._parse_response(FakeResponse(text="boom")) == {"text": "boom"}


# --- _send_request ----------------------------------------------------------


def test_send_request_uses_params_for_get(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        seen.update(url=url, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(test_runner.requests, "get", fake_get)
    item = ApiInterface(name="q", url="https://api.example.com/q", method="GET", headers={}, body={})

    test_runner._send_request(item, {"k": "v"})

    assert seen["params"] == {"k": "v"}
    assert seen["url"] == "https://api.example.com/q"


def test_send_request_uses_json_body_for_post(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(json=json)
        return FakeResponse()

    monkeypatch.setattr(test_runner.requests, "post", fake_post)
    item = ApiInterface(name="p", url="https://api.example.com/p", method="POST", headers={}, body={})

    test_runner._send_request(item, {"k": "v"})

    assert seen["json"] == {"k": "v"}


def test_send_request_rejects_an_unsupported_method(no_network):
    item = ApiInterface(name="x", url="https://api.example.com/x", method="TRACE", headers={}, body={})

    with pytest.raises(ValueError, match="不支持的请求方法"):
        test_runner._send_request(item, {})


# --- _execute_case ----------------------------------------------------------


def test_execute_case_without_an_interface_fails(db_session, interface, no_network):
    case = make_case(db_session, interface)

    result = test_runner._execute_case(None, case, analyze_by_ai=False)

    assert (result.status, result.assertion_message) == ("failed", "接口不存在")


def test_execute_case_turns_a_request_error_into_a_failure(monkeypatch, db_session, interface):
    case = make_case(db_session, interface)

    def boom(interface, data):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(test_runner, "_send_request", boom)

    result = test_runner._execute_case(interface, case, analyze_by_ai=False)

    assert result.status == "failed"
    assert "connection refused" in result.assertion_message


def test_execute_case_records_the_exchange(monkeypatch, db_session, interface):
    case = make_case(db_session, interface)
    stub_request(monkeypatch, FakeResponse(200, {"code": 0}))

    result = test_runner._execute_case(interface, case, analyze_by_ai=False)

    assert result.status == "passed"
    assert result.status_code == 200
    assert result.request_data == {"username": "admin"}
    assert result.response_data == {"code": 0}
    assert result.ai_analysis == ""


def test_execute_case_skips_ai_analysis_when_passing(monkeypatch, db_session, interface):
    case = make_case(db_session, interface)
    stub_request(monkeypatch, FakeResponse(200, {}))
    monkeypatch.setattr(
        test_runner.openai_client,
        "analyze_result",
        lambda *a, **k: pytest.fail("AI analysis ran for a passing case"),
    )

    assert test_runner._execute_case(interface, case, analyze_by_ai=True).status == "passed"


def test_execute_case_attaches_ai_analysis_when_failing(monkeypatch, db_session, interface):
    case = make_case(db_session, interface, expected_status_code=200)
    stub_request(monkeypatch, FakeResponse(500, {}))
    monkeypatch.setattr(test_runner.openai_client, "analyze_result", lambda *a, **k: "AI 诊断结果")

    result = test_runner._execute_case(interface, case, analyze_by_ai=True)

    assert (result.status, result.ai_analysis) == ("failed", "AI 诊断结果")


def test_execute_case_fails_when_the_sql_check_fails(monkeypatch, db_session, interface):
    case = make_case(db_session, interface, sql_check={"sql": "SELECT 1"})
    stub_request(monkeypatch, FakeResponse(200, {}))
    monkeypatch.setattr(test_runner.sql_validator, "validate", lambda check: (False, "SQL校验失败"))

    result = test_runner._execute_case(interface, case, analyze_by_ai=False)

    assert (result.status, result.assertion_message) == ("failed", "SQL校验失败")


def test_sql_failure_is_appended_to_an_existing_assertion_message(monkeypatch, db_session, interface):
    case = make_case(db_session, interface, expected_status_code=201)
    stub_request(monkeypatch, FakeResponse(200, {}))
    monkeypatch.setattr(test_runner.sql_validator, "validate", lambda check: (False, "SQL校验失败"))

    message = test_runner._execute_case(interface, case, analyze_by_ai=False).assertion_message

    assert "期望 201" in message and message.endswith("; SQL校验失败")


# --- run_cases --------------------------------------------------------------


def test_run_cases_counts_and_persists_results(monkeypatch, db_session, interface):
    passing = make_case(db_session, interface, case_name="通过的")
    failing = make_case(db_session, interface, case_name="失败的", expected_status_code=201)
    stub_request(monkeypatch, FakeResponse(200, {}))

    run = test_runner.run_cases(db_session, interface.id, [], analyze_by_ai=False)

    assert (run.total, run.passed, run.failed, run.status) == (2, 1, 1, "failed")
    results = db_session.query(ResultModel).filter(ResultModel.run_id == run.id).all()
    assert {r.case_name for r in results} == {"通过的", "失败的"}
    assert {r.case_id for r in results} == {passing.id, failing.id}


def test_run_cases_marks_an_all_passing_run(monkeypatch, db_session, interface):
    make_case(db_session, interface)
    stub_request(monkeypatch, FakeResponse(200, {}))

    run = test_runner.run_cases(db_session, interface.id, [], analyze_by_ai=False)

    assert (run.status, run.failed, run.ai_summary) == ("passed", 0, "")


def test_run_cases_selects_by_case_ids_over_interface_id(monkeypatch, db_session, interface):
    wanted = make_case(db_session, interface, case_name="选中的")
    make_case(db_session, interface, case_name="没选中的")
    stub_request(monkeypatch, FakeResponse(200, {}))

    run = test_runner.run_cases(db_session, None, [wanted.id], analyze_by_ai=False)

    assert run.total == 1
    only = db_session.query(ResultModel).filter(ResultModel.run_id == run.id).one()
    assert only.case_name == "选中的"


def test_run_cases_summarizes_failures(monkeypatch, db_session, interface):
    make_case(db_session, interface, case_name="坏用例", expected_status_code=201)
    stub_request(monkeypatch, FakeResponse(500, {}))
    monkeypatch.setattr(test_runner.openai_client, "analyze_result", lambda *a, **k: "AI 诊断")

    run = test_runner.run_cases(db_session, interface.id, [], analyze_by_ai=True)

    assert run.ai_summary == "坏用例: AI 诊断"


def test_run_cases_with_no_matching_cases_passes_vacuously(db_session, no_network):
    run = test_runner.run_cases(db_session, 9999, [], analyze_by_ai=False)

    assert (run.total, run.passed, run.failed, run.status) == (0, 0, 0, "passed")
    assert db_session.query(RunModel).filter(RunModel.id == run.id).one().status == "passed"
