from app.models.testcase import TestCase as CaseModel
from app.models.environment import TestEnvironment as EnvironmentModel
from app.models.result import TestResult as ResultModel, TestRun as RunModel
from app.utils.config import get_settings


def interface_payload(url: str = "/v1/login") -> dict:
    return {"name": "登录接口", "url": url, "method": "POST", "headers": {}, "body": {}}


def test_environment_crud(client):
    created = client.post(
        "/environments",
        json={
            "name": "测试环境",
            "base_url": "https://test.example.com/",
            "variables": {"tenant": "qa"},
            "headers": {"X-Env": "test"},
        },
    )

    assert created.status_code == 201
    environment = created.json()
    assert environment["base_url"] == "https://test.example.com"
    assert client.get("/environments").json()[0]["name"] == "测试环境"

    updated = client.put(
        f"/environments/{environment['id']}", json={"variables": {"tenant": "uat"}}
    )
    assert updated.json()["variables"] == {"tenant": "uat"}
    assert client.delete(f"/environments/{environment['id']}").status_code == 204


def test_environment_names_are_unique(client):
    payload = {"name": "重复环境", "base_url": "https://api.example.com"}
    assert client.post("/environments", json=payload).status_code == 201
    assert client.post("/environments", json=payload).status_code == 409


def test_environment_update_rejects_explicit_null(client):
    created = client.post(
        "/environments", json={"name": "不可空", "base_url": "https://api.example.com"}
    ).json()

    assert client.put(f"/environments/{created['id']}", json={"variables": None}).status_code == 422


def test_environment_secrets_are_encrypted_and_only_key_names_are_returned(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(get_settings(), "platform_encryption_key", "test-encryption-key")

    response = client.post(
        "/environments",
        json={
            "name": "密钥环境",
            "base_url": "https://api.example.com",
            "secrets": {"access_token": "plain-token"},
            "headers": {"Authorization": "Bearer ${access_token}"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["secret_keys"] == ["access_token"]
    assert "plain-token" not in str(body)
    stored = db_session.get(EnvironmentModel, body["id"])
    assert stored.secrets_encrypted
    assert "plain-token" not in stored.secrets_encrypted


def test_sensitive_values_are_rejected_from_plain_environment_variables(client):
    response = client.post(
        "/environments",
        json={
            "name": "错误环境",
            "base_url": "https://api.example.com",
            "variables": {"password": "plain"},
        },
    )

    assert response.status_code == 422


def test_interface_accepts_relative_urls_for_environment_switching(client):
    response = client.post("/interfaces", json=interface_payload())

    assert response.status_code == 201
    assert response.json()["url"] == "/v1/login"


def test_case_crud_supports_assertions_extractors_and_dependencies(client, db_session):
    interface = client.post("/interfaces", json=interface_payload()).json()
    first = client.post(
        "/cases",
        json={
            "interface_id": interface["id"],
            "case_name": "登录并提取token",
            "data": {"username": "admin"},
            "extractors": [{"name": "token", "source": "body", "path": "$.data.token"}],
        },
    ).json()
    second_response = client.post(
        "/cases",
        json={
            "interface_id": interface["id"],
            "case_name": "携带token查询",
            "data": {"token": "${token}"},
            "dependencies": [first["id"]],
            "assertions": [{"source": "body", "path": "$.code", "operator": "eq", "expected": 0}],
        },
    )

    assert second_response.status_code == 201
    second = second_response.json()
    assert second["dependencies"] == [first["id"]]
    assert client.put(f"/cases/{second['id']}", json={"retry_count": 2}).json()["retry_count"] == 2
    assert client.delete(f"/cases/{first['id']}").status_code == 409
    assert db_session.get(CaseModel, second["id"]).assertions[0]["operator"] == "eq"


def test_case_rejects_unknown_dependencies(client):
    interface = client.post("/interfaces", json=interface_payload()).json()

    response = client.post(
        "/cases",
        json={
            "interface_id": interface["id"],
            "case_name": "错误依赖",
            "dependencies": [9999],
        },
    )

    assert response.status_code == 404


def test_case_update_rejects_explicit_null(client):
    interface = client.post("/interfaces", json=interface_payload()).json()
    case = client.post(
        "/cases",
        json={"interface_id": interface["id"], "case_name": "不可空字段"},
    ).json()

    assert client.put(f"/cases/{case['id']}", json={"data": None}).status_code == 422


def test_case_paged_query_filters_interface_status_and_keyword(client):
    interface = client.post("/interfaces", json=interface_payload()).json()
    for index in range(12):
        client.post(
            "/cases",
            json={
                "interface_id": interface["id"],
                "case_name": f"paged-case-{index}",
                "enabled": index % 2 == 0,
            },
        )

    response = client.get(
        "/cases/page",
        params={
            "keyword": "paged-case",
            "interface_id": interface["id"],
            "enabled": True,
            "page": 2,
            "page_size": 5,
        },
    )

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 6
    assert page["pages"] == 2
    assert len(page["items"]) == 1
    assert page["items"][0]["enabled"] is True


def test_case_with_historical_results_cannot_be_deleted(client, db_session):
    interface = client.post("/interfaces", json=interface_payload()).json()
    case = client.post(
        "/cases",
        json={"interface_id": interface["id"], "case_name": "已有历史"},
    ).json()
    run = RunModel(interface_id=interface["id"], status="passed", total=1, passed=1, failed=0)
    db_session.add(run)
    db_session.flush()
    db_session.add(
        ResultModel(
            run_id=run.id,
            case_id=case["id"],
            case_name="已有历史",
            status="passed",
        )
    )
    db_session.commit()

    assert client.delete(f"/cases/{case['id']}").status_code == 409


def test_environment_with_historical_runs_cannot_be_deleted(client, db_session):
    environment = client.post(
        "/environments", json={"name": "历史环境", "base_url": "https://api.example.com"}
    ).json()
    db_session.add(RunModel(environment_id=environment["id"], status="passed"))
    db_session.commit()

    assert client.delete(f"/environments/{environment['id']}").status_code == 409
