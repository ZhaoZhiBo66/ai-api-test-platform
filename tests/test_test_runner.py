import pytest

from app.models.interface import ApiInterface
from app.models.environment import TestEnvironment as EnvironmentModel

# Aliased away from their Test* names: pytest tries to collect any class called
# Test* as a test suite and warns when it cannot.
from app.models.result import TestResult as ResultModel
from app.models.result import TestRun as RunModel
from app.models.testcase import TestCase as CaseModel
from app.services import test_runner
from app.utils.config import get_settings
from app.utils.encryption import encrypt_mapping


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

    def fake_get(url, headers=None, params=None, timeout=None, allow_redirects=None):
        seen.update(url=url, params=params, timeout=timeout, allow_redirects=allow_redirects)
        return FakeResponse()

    monkeypatch.setattr(test_runner.requests, "get", fake_get)
    monkeypatch.setattr(test_runner, "validate_target_url", lambda url: None)
    item = ApiInterface(name="q", url="https://api.example.com/q", method="GET", headers={}, body={})

    test_runner._send_request(item, {"k": "v"})

    assert seen["params"] == {"k": "v"}
    assert seen["url"] == "https://api.example.com/q"
    assert seen["allow_redirects"] is False


def test_send_request_uses_json_body_for_post(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, allow_redirects=None):
        seen.update(json=json, allow_redirects=allow_redirects)
        return FakeResponse()

    monkeypatch.setattr(test_runner.requests, "post", fake_post)
    monkeypatch.setattr(test_runner, "validate_target_url", lambda url: None)
    item = ApiInterface(name="p", url="https://api.example.com/p", method="POST", headers={}, body={})

    test_runner._send_request(item, {"k": "v"})

    assert seen["json"] == {"k": "v"}
    assert seen["allow_redirects"] is False


def test_send_request_rejects_an_unsupported_method(no_network, monkeypatch):
    item = ApiInterface(name="x", url="https://api.example.com/x", method="TRACE", headers={}, body={})

    # Method validation happens after target validation in production. Keep this
    # unit test focused on the unsupported-method branch and DNS-free.
    monkeypatch.setattr(test_runner, "validate_target_url", lambda url: None)
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


def test_execute_case_redacts_sensitive_request_and_response_fields(monkeypatch, db_session, interface):
    case = make_case(
        db_session,
        interface,
        data={"username": "admin", "password": "plain"},
    )
    stub_request(monkeypatch, FakeResponse(200, {"access_token": "token-value"}))

    result = test_runner._execute_case(interface, case, analyze_by_ai=False)

    assert result.request_data["password"] == "***REDACTED***"
    assert result.response_data["access_token"] == "***REDACTED***"
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


def test_run_cases_rejects_an_unknown_interface(db_session, no_network):
    with pytest.raises(Exception) as exc:
        test_runner.run_cases(db_session, 9999, [], analyze_by_ai=False)

    assert getattr(exc.value, "status_code", None) == 404


def test_run_cases_rejects_an_empty_selection(db_session, no_network):
    with pytest.raises(Exception) as exc:
        test_runner.run_cases(db_session, None, [], analyze_by_ai=False)

    assert getattr(exc.value, "status_code", None) == 422


def test_run_cases_rejects_unknown_case_ids(db_session, no_network):
    with pytest.raises(Exception) as exc:
        test_runner.run_cases(db_session, None, [9999], analyze_by_ai=False)

    assert getattr(exc.value, "status_code", None) == 404


def test_run_cases_executes_dependencies_and_passes_extracted_variables(monkeypatch, db_session):
    environment = EnvironmentModel(
        name="测试环境", base_url="https://api.example.com", variables={}, headers={}
    )
    login = ApiInterface(name="登录", url="/login", method="POST", headers={}, body={})
    profile = ApiInterface(name="资料", url="/profile", method="POST", headers={}, body={})
    db_session.add_all([environment, login, profile])
    db_session.commit()

    login_case = CaseModel(
        interface_id=login.id,
        case_name="登录",
        data={"username": "admin"},
        expected_status_code=200,
        extractors=[{"name": "token", "source": "body", "path": "$.data.token"}],
    )
    db_session.add(login_case)
    db_session.commit()
    profile_case = CaseModel(
        interface_id=profile.id,
        case_name="查询资料",
        data={"access_token": "${token}"},
        expected_status_code=200,
        dependencies=[login_case.id],
    )
    db_session.add(profile_case)
    db_session.commit()

    seen = []

    def fake_send(runtime_interface, data):
        seen.append((runtime_interface.url, data))
        if runtime_interface.url.endswith("/login"):
            return FakeResponse(200, {"data": {"token": "token-123"}})
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(test_runner, "_send_request", fake_send)

    run = test_runner.run_cases(
        db_session,
        None,
        [profile_case.id],
        analyze_by_ai=False,
        environment_id=environment.id,
    )

    assert run.total == 2
    assert run.status == "passed"
    assert seen == [
        ("https://api.example.com/login", {"username": "admin"}),
        ("https://api.example.com/profile", {"access_token": "token-123"}),
    ]


def test_run_cases_decrypts_environment_secrets_only_for_runtime(monkeypatch, db_session):
    monkeypatch.setattr(get_settings(), "platform_encryption_key", "runtime-test-key")
    environment = EnvironmentModel(
        name="密钥环境",
        base_url="https://api.example.com",
        variables={},
        headers={"Authorization": "Bearer ${access_token}"},
        secrets_encrypted=encrypt_mapping({"access_token": "secret-token"}),
    )
    interface = ApiInterface(name="资料", url="/profile", method="GET", headers={}, body={})
    db_session.add_all([environment, interface])
    db_session.commit()
    case = CaseModel(
        interface_id=interface.id,
        case_name="查询资料",
        data={"token": "${access_token}"},
        expected_status_code=200,
    )
    db_session.add(case)
    db_session.commit()
    seen = {}

    def fake_send(runtime_interface, data):
        seen.update(headers=runtime_interface.headers, data=data)
        return FakeResponse(200, {})

    monkeypatch.setattr(test_runner, "_send_request", fake_send)

    run = test_runner.run_cases(
        db_session,
        interface.id,
        [],
        analyze_by_ai=False,
        environment_id=environment.id,
    )

    assert run.status == "passed"
    assert seen["headers"]["Authorization"] == "Bearer secret-token"
    assert seen["data"]["token"] == "secret-token"
    assert run.variables["access_token"] == "***REDACTED***"


def test_execute_case_substitutes_and_url_encodes_path_parameters(monkeypatch, db_session, interface):
    interface.url = "https://api.example.com/users/{user_id}"
    interface.method = "GET"
    db_session.commit()
    case = make_case(
        db_session,
        interface,
        data={"user_id": "qa/user", "expand": "profile"},
        request_config={"path_parameters": ["user_id"]},
    )
    seen = {}

    def fake_send(runtime_interface, data):
        seen.update(url=runtime_interface.url, data=data)
        return FakeResponse(200, {})

    monkeypatch.setattr(test_runner, "_send_request", fake_send)

    result = test_runner._execute_case(interface, case, analyze_by_ai=False)

    assert result.status == "passed"
    assert seen["url"] == "https://api.example.com/users/qa%2Fuser"
    assert seen["data"] == {"expand": "profile"}
