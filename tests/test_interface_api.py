import pytest

from app.models.interface import ApiInterface


def payload(**overrides) -> dict:
    body = {
        "name": "登录接口",
        "url": "https://api.example.com/login",
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": {"username": "admin"},
    }
    body.update(overrides)
    return body


def test_create_returns_201_and_persists(client, db_session):
    response = client.post("/interfaces", json=payload())

    assert response.status_code == 201
    created = response.json()
    assert created["id"] > 0
    assert created["name"] == "登录接口"
    assert created["headers"] == {"Content-Type": "application/json"}

    stored = db_session.get(ApiInterface, created["id"])
    assert stored.method == "POST"
    assert stored.body == {"username": "admin"}


def test_create_normalizes_url_with_trailing_slash(client):
    response = client.post("/interfaces", json=payload(url="https://api.example.com"))

    # HttpUrl normalizes a bare host to include the root path.
    assert response.json()["url"] == "https://api.example.com/"


def test_headers_and_body_default_to_empty_dicts(client):
    response = client.post(
        "/interfaces",
        json={"name": "极简", "url": "https://api.example.com/ping", "method": "GET"},
    )

    assert response.status_code == 201
    assert response.json()["headers"] == {}
    assert response.json()["body"] == {}


def test_list_returns_newest_first(client):
    first = client.post("/interfaces", json=payload(name="第一个")).json()
    second = client.post("/interfaces", json=payload(name="第二个")).json()

    listed = client.get("/interfaces").json()

    assert [item["id"] for item in listed] == [second["id"], first["id"]]


def test_get_unknown_id_returns_404(client):
    response = client.get("/interfaces/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "接口不存在"


def test_update_only_touches_supplied_fields(client):
    created = client.post("/interfaces", json=payload()).json()

    response = client.put(f"/interfaces/{created['id']}", json={"name": "改名了"})

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "改名了"
    assert updated["method"] == created["method"]
    assert updated["url"] == created["url"]
    assert updated["headers"] == created["headers"]


def test_delete_removes_the_row(client, db_session):
    created = client.post("/interfaces", json=payload()).json()

    assert client.delete(f"/interfaces/{created['id']}").status_code == 204
    assert client.get(f"/interfaces/{created['id']}").status_code == 404
    assert db_session.get(ApiInterface, created["id"]) is None


def test_update_unknown_id_returns_404(client):
    response = client.put("/interfaces/9999", json={"name": "不存在"})

    assert response.status_code == 404


def test_delete_unknown_id_returns_404(client):
    response = client.delete("/interfaces/9999")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "field, value",
    [
        ("method", "get"),  # the schema pattern only accepts upper case
        ("method", "TRACE"),
        ("url", "not-a-url"),
        ("url", "ftp://api.example.com"),
        ("name", ""),
    ],
    ids=["lowercase-method", "unsupported-method", "malformed-url", "non-http-url", "empty-name"],
)
def test_create_rejects_invalid_input(client, field, value):
    response = client.post("/interfaces", json=payload(**{field: value}))

    assert response.status_code == 422
