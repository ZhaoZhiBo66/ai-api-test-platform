from app.models.interface import ApiInterface
from app.models.testcase import TestCase as CaseModel


def sample_document() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {"title": "用户服务", "version": "1.0.0"},
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/users": {
                "post": {
                    "summary": "创建用户",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["username"],
                                    "properties": {
                                        "username": {"type": "string", "maxLength": 10, "example": "qa"},
                                        "age": {"type": "integer", "minimum": 1},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "created"}, "400": {"description": "bad"}},
                }
            },
            "/users/{user_id}": {
                "get": {
                    "operationId": "getUser",
                    "parameters": [
                        {"name": "user_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            },
        },
    }


def test_import_openapi_creates_interfaces_and_schema_cases(client, db_session):
    response = client.post("/openapi/import", json={"document": sample_document()})

    assert response.status_code == 200
    result = response.json()
    assert result["created_interfaces"] == 2
    assert result["generated_cases"] >= 4
    created = db_session.query(ApiInterface).order_by(ApiInterface.id).all()
    assert [(item.method, item.url) for item in created] == [
        ("POST", "/users"),
        ("GET", "/users/{user_id}"),
    ]
    post_cases = db_session.query(CaseModel).filter(CaseModel.interface_id == created[0].id).all()
    assert any(case.case_name == "必填字段 username 缺失" and case.expected_status_code == 400 for case in post_cases)
    assert any(case.case_name == "字段 username 超过最大长度" for case in post_cases)
    get_case = (
        db_session.query(CaseModel)
        .filter(CaseModel.interface_id == created[1].id, CaseModel.case_name == "OpenAPI基础有效用例")
        .one()
    )
    assert get_case.request_config["path_parameters"] == ["user_id"]


def test_import_openapi_is_idempotent_by_default(client):
    payload = {"document": sample_document(), "generate_schema_cases": False}
    assert client.post("/openapi/import", json=payload).json()["created_interfaces"] == 2

    second = client.post("/openapi/import", json=payload).json()

    assert second["created_interfaces"] == 0
    assert second["skipped_interfaces"] == 2


def test_import_openapi_can_store_absolute_urls(client):
    response = client.post(
        "/openapi/import",
        json={
            "document": sample_document(),
            "store_relative_urls": False,
            "generate_schema_cases": False,
        },
    )

    assert response.status_code == 200
    interface = client.get(f"/interfaces/{response.json()['interface_ids'][0]}").json()
    assert interface["url"] == "https://api.example.com/users"


def test_import_rejects_documents_without_paths(client):
    response = client.post(
        "/openapi/import",
        json={"document": {"openapi": "3.0.0", "info": {"title": "x", "version": "1"}}},
    )

    assert response.status_code == 422
