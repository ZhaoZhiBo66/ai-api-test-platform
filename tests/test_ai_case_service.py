import pytest
from fastapi import HTTPException

from app.ai.openai_client import OpenAIClient
from app.models.interface import ApiInterface
from app.models.testcase import TestCase as CaseModel
from app.services import ai_case_service


@pytest.fixture
def interface(db_session) -> ApiInterface:
    item = ApiInterface(name="登录", url="https://api.example.com/login", method="POST", headers={}, body={})
    db_session.add(item)
    db_session.commit()
    return item


def names(cases) -> set[str]:
    return {case["case_name"] for case in cases}


# --- _fallback_cases --------------------------------------------------------
# This is the path the platform actually runs whenever OPENAI_API_KEY is unset,
# which is the documented way to demo it.


def test_fallback_covers_every_field_and_the_injection_cases():
    cases = OpenAIClient._fallback_cases({"username": "admin", "age": 30})

    assert names(cases) == {
        "username为空",
        "username非法类型",
        "username超长字符串",
        "age为空",
        "age非法类型",
        "SQL注入",
        "XSS脚本注入",
    }


def test_fallback_only_adds_a_long_string_case_for_string_fields():
    cases = OpenAIClient._fallback_cases({"age": 30})

    assert "age超长字符串" not in names(cases)


def test_fallback_varies_one_field_and_keeps_the_rest():
    cases = OpenAIClient._fallback_cases({"username": "admin", "age": 30})
    empty_username = next(c for c in cases if c["case_name"] == "username为空")

    assert empty_username["data"] == {"username": "", "age": 30}


def test_fallback_long_string_is_over_the_column_limit():
    cases = OpenAIClient._fallback_cases({"username": "admin"})
    long_case = next(c for c in cases if c["case_name"] == "username超长字符串")

    assert len(long_case["data"]["username"]) == 256


def test_fallback_injection_cases_replace_every_field():
    cases = OpenAIClient._fallback_cases({"username": "admin", "age": 30})
    sql = next(c for c in cases if c["case_name"] == "SQL注入")
    xss = next(c for c in cases if c["case_name"] == "XSS脚本注入")

    assert sql["data"] == {"username": "' OR '1'='1", "age": "' OR '1'='1"}
    assert xss["data"] == {"username": "<script>alert(1)</script>", "age": "<script>alert(1)</script>"}


def test_fallback_on_empty_input_still_yields_the_injection_cases():
    assert names(OpenAIClient._fallback_cases({})) == {"SQL注入", "XSS脚本注入"}


def test_generate_cases_falls_back_when_no_client_is_configured():
    # The root conftest forces OPENAI_API_KEY empty, so this is the real path.
    client = OpenAIClient()
    assert client.client is None

    assert names(client.generate_cases({"username": "admin"})) == names(
        OpenAIClient._fallback_cases({"username": "admin"})
    )


# --- generate_and_save_cases ------------------------------------------------


def test_generate_and_save_persists_the_generated_cases(db_session, interface):
    saved = ai_case_service.generate_and_save_cases(db_session, interface.id, {"username": "admin"})

    assert len(saved) == 5
    stored = db_session.query(CaseModel).filter(CaseModel.interface_id == interface.id).all()
    assert {c.case_name for c in stored} == {c.case_name for c in saved}
    assert all(c.id is not None for c in saved)


def test_generate_and_save_rejects_an_unknown_interface(db_session):
    with pytest.raises(HTTPException) as exc:
        ai_case_service.generate_and_save_cases(db_session, 9999, {"username": "admin"})

    assert exc.value.status_code == 404


def test_generate_and_save_fills_in_defaults_for_a_bare_item(monkeypatch, db_session, interface):
    monkeypatch.setattr(ai_case_service.openai_client, "generate_cases", lambda data: [{}])

    saved = ai_case_service.generate_and_save_cases(db_session, interface.id, {"username": "admin"}, 201)

    assert saved[0].case_name == "AI生成用例"
    assert saved[0].data == {"username": "admin"}
    assert saved[0].expected_json == {}
    assert saved[0].sql_check == {}
    # The caller's value is only reachable when the item omits the field.
    assert saved[0].expected_status_code == 201


def test_generated_item_overrides_the_callers_expected_status_code(monkeypatch, db_session, interface):
    monkeypatch.setattr(
        ai_case_service.openai_client,
        "generate_cases",
        lambda data: [{"case_name": "自定义", "expected_status_code": 400}],
    )

    saved = ai_case_service.generate_and_save_cases(db_session, interface.id, {"username": "admin"}, 201)

    assert saved[0].expected_status_code == 400


def test_generate_and_save_keeps_a_sql_check_from_the_item(monkeypatch, db_session, interface):
    check = {"sql": "select username from user", "expected": {"username": "admin"}}
    monkeypatch.setattr(
        ai_case_service.openai_client, "generate_cases", lambda data: [{"case_name": "带SQL", "sql_check": check}]
    )

    saved = ai_case_service.generate_and_save_cases(db_session, interface.id, {"username": "admin"})

    assert saved[0].sql_check == check


def test_generate_and_save_with_no_generated_cases_saves_nothing(monkeypatch, db_session, interface):
    monkeypatch.setattr(ai_case_service.openai_client, "generate_cases", lambda data: [])

    assert ai_case_service.generate_and_save_cases(db_session, interface.id, {}) == []
    assert db_session.query(CaseModel).count() == 0


# --- list_cases_by_interface ------------------------------------------------


def test_list_cases_returns_newest_first(db_session, interface):
    ai_case_service.generate_and_save_cases(db_session, interface.id, {"username": "admin"})

    listed = ai_case_service.list_cases_by_interface(db_session, interface.id)

    assert [c.id for c in listed] == sorted([c.id for c in listed], reverse=True)


def test_list_cases_is_scoped_to_one_interface(db_session, interface):
    other = ApiInterface(name="其他", url="https://api.example.com/x", method="GET", headers={}, body={})
    db_session.add(other)
    db_session.commit()
    ai_case_service.generate_and_save_cases(db_session, interface.id, {"username": "admin"})

    assert ai_case_service.list_cases_by_interface(db_session, other.id) == []


# --- API layer --------------------------------------------------------------


def test_generate_cases_endpoint_returns_the_saved_cases(client, interface):
    response = client.post(
        f"/ai/interfaces/{interface.id}/cases",
        json={"input_data": {"username": "admin"}, "expected_status_code": 200},
    )

    assert response.status_code == 200
    assert "SQL注入" in {case["case_name"] for case in response.json()}


def test_generate_cases_endpoint_404s_for_an_unknown_interface(client):
    response = client.post("/ai/interfaces/9999/cases", json={"input_data": {"username": "admin"}})

    assert response.status_code == 404


def test_analyze_result_endpoint_uses_the_offline_analysis(client):
    response = client.post("/ai/analyze-result", json={"status_code": 500, "response": {}})

    assert response.status_code == 200
    assert "服务端异常" in response.json()["analysis"]


def test_analyze_result_endpoint_reports_an_auth_failure(client):
    response = client.post("/ai/analyze-result", json={"status_code": 401, "response": {}})

    assert "鉴权失败" in response.json()["analysis"]
