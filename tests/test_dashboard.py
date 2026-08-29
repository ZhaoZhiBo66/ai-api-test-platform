from pathlib import Path


def test_dashboard_is_the_chinese_first_entry_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "接口回归质量门禁" in response.text
    assert "第一次使用，从这里开始" in response.text
    assert 'href="/workbench"' in response.text
    assert 'href="/docs"' in response.text


def test_docs_is_the_themed_swagger_and_api_docs_redirects_to_it(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert "/static/swagger-theme.css" in response.text
    assert "/static/swagger-i18n.js" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api-docs", follow_redirects=False).status_code == 307


def test_swagger_theme_assets_are_served(client):
    assert client.get("/static/swagger-theme.css").status_code == 200
    assert client.get("/static/swagger-i18n.js").status_code == 200


def test_dashboard_asset_exists():
    assert Path("app/static/index.html").is_file()
    assert Path("app/static/home.css").is_file()


def test_functional_workbench_and_assets_are_served(client):
    response = client.get("/workbench")

    assert response.status_code == 200
    assert "发起测试" in response.text
    assert "导入 OpenAPI 文档" in response.text
    assert "AI 生成测试用例" in response.text
    assert "回归执行过程" in response.text
    assert 'id="run-steps"' in response.text
    assert "interface-page-size" in response.text
    assert "case-filter-interface" in response.text
    assert client.get("/static/home.css").status_code == 200
    assert client.get("/static/workbench.css").status_code == 200
    assert client.get("/static/workbench.js").status_code == 200


def test_system_info_exposes_safe_storage_identity_and_database_counts(client):
    client.post(
        "/interfaces",
        json={"name": "storage-check", "url": "https://api.example.com/ping", "method": "GET"},
    )

    response = client.get("/system/info")

    assert response.status_code == 200
    info = response.json()
    assert info["storage"] == "SQLite"
    assert info["database"] == "memory"
    assert info["persistent"] is False
    assert info["counts"]["interfaces"] == 1
    assert "password" not in str(info).lower()
