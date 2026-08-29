import socket

import pytest

from app.services.target_validator import UnsafeTargetError, validate_target_url
from app.utils.config import get_settings


def _address(ip: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


def test_target_validator_allows_a_public_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _address("8.8.8.8"))

    validate_target_url("https://api.example.com/v1")


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000", "http://localhost:8000", "http://169.254.169.254"])
def test_target_validator_blocks_private_targets(monkeypatch, url):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _address("127.0.0.1"))

    with pytest.raises(UnsafeTargetError):
        validate_target_url(url)


def test_target_validator_blocks_a_hostname_resolving_to_private_ip(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _address("10.0.0.7"))

    with pytest.raises(UnsafeTargetError, match="非公网"):
        validate_target_url("https://internal.example.com")


def test_api_key_is_enforced_when_enabled(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "platform_api_key", "test-secret")

    response = client.get("/interfaces")

    assert response.status_code == 401
    assert client.get("/interfaces", headers={"X-API-Key": "test-secret"}).status_code == 200


def test_health_remains_public_when_api_key_is_enabled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_auth_enabled", True)
    monkeypatch.setattr(get_settings(), "platform_api_key", "test-secret")

    assert client.get("/health").status_code == 200


def test_role_based_api_keys_enforce_read_write_and_delete(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "platform_api_key", "")
    monkeypatch.setattr(
        settings,
        "platform_api_keys",
        {"viewer-key": "viewer", "operator-key": "operator", "admin-key": "admin"},
    )
    payload = {
        "name": "接口",
        "url": "https://api.example.com/ping",
        "method": "GET",
    }

    assert client.get("/interfaces", headers={"X-API-Key": "viewer-key"}).status_code == 200
    assert client.post("/interfaces", json=payload, headers={"X-API-Key": "viewer-key"}).status_code == 403
    created = client.post("/interfaces", json=payload, headers={"X-API-Key": "operator-key"})
    assert created.status_code == 201
    interface_id = created.json()["id"]
    assert client.delete(f"/interfaces/{interface_id}", headers={"X-API-Key": "operator-key"}).status_code == 403
    assert client.delete(f"/interfaces/{interface_id}", headers={"X-API-Key": "admin-key"}).status_code == 204


def test_private_target_can_be_explicitly_allowlisted(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "target_host_allowlist", {"internal.example.com"})
    monkeypatch.setattr(settings, "allow_private_targets", False)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _address("10.0.0.7"))

    validate_target_url("https://internal.example.com/api")
