import pytest
from fastapi.testclient import TestClient

from demo_sut.main import app, reset_state


@pytest.fixture
def demo_client(monkeypatch):
    monkeypatch.delenv("DEMO_BUG_MODE", raising=False)
    reset_state()
    return TestClient(app)


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/login", json={"username": "demo", "password": "demo123"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_complete_order_flow(demo_client):
    headers = login_headers(demo_client)
    product = demo_client.get("/api/products/1", headers=headers)
    order = demo_client.post("/api/orders", headers=headers, json={"product_id": 1, "quantity": 2})
    order_id = order.json()["data"]["id"]
    payment = demo_client.post(f"/api/orders/{order_id}/pay", headers=headers)
    queried = demo_client.get(f"/api/orders/{order_id}", headers=headers)

    assert product.status_code == 200
    assert order.status_code == 201
    assert order.json()["data"]["total"] == 199.8
    assert payment.json()["data"]["status"] == "paid"
    assert queried.json()["data"]["status"] == "paid"


def test_auth_and_stock_failures_are_deterministic(demo_client):
    assert demo_client.get("/api/products/1").status_code == 401
    headers = login_headers(demo_client)
    response = demo_client.post("/api/orders", headers=headers, json={"product_id": 1, "quantity": 10})
    assert response.status_code == 201
    response = demo_client.post("/api/orders", headers=headers, json={"product_id": 1, "quantity": 10})
    assert response.status_code == 201
    response = demo_client.post("/api/orders", headers=headers, json={"product_id": 1, "quantity": 1})
    assert response.status_code == 409


def test_controlled_bug_mode_changes_total(demo_client, monkeypatch):
    monkeypatch.setenv("DEMO_BUG_MODE", "wrong_total")
    headers = login_headers(demo_client)
    response = demo_client.post("/api/orders", headers=headers, json={"product_id": 1, "quantity": 2})
    assert response.json()["data"]["total"] == 200.8
