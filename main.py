from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from app.api.ai_case_api import router as ai_case_router
from app.api.audit_api import router as audit_router
from app.api.environment_api import router as environment_router
from app.api.interface_api import router as interface_router
from app.api.openapi_api import router as openapi_router
from app.api.report_api import router as report_router
from app.api.result_api import router as result_router
from app.api.run_api import router as run_router
from app.api.testcase_api import router as testcase_router
from app.api.system_api import router as system_router
from app.api.suite_api import router as suite_router
from app.database.db import SessionLocal
from app.models.audit import AuditLog
from app.utils.config import get_settings
from app.utils.logger import init_logger
from app.services.async_run_service import mark_interrupted_runs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_logger()
    with SessionLocal() as session:
        mark_interrupted_runs(session)
    yield


app = FastAPI(
    title="接口回归质量门禁平台",
    description="基于 OpenAPI 契约、回归套件和确定性断言的接口质量门禁",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None,
)
app.mount("/static", StaticFiles(directory=get_settings().root_dir / "app" / "static"), name="static")

app.include_router(interface_router)
app.include_router(audit_router)
app.include_router(openapi_router)
app.include_router(environment_router)
app.include_router(testcase_router)
app.include_router(ai_case_router)
app.include_router(run_router)
app.include_router(result_router)
app.include_router(report_router)
app.include_router(system_router)
app.include_router(suite_router)


@app.middleware("http")
async def audit_requests(request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid4().hex
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    if request.url.path not in {"/health"} and not request.url.path.startswith("/static/"):
        try:
            with SessionLocal() as session:
                session.add(
                    AuditLog(
                        request_id=request_id,
                        actor=getattr(request.state, "actor", "anonymous"),
                        role=getattr(request.state, "role", "anonymous"),
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        duration_ms=round((perf_counter() - started) * 1000),
                        client_ip=request.client.host if request.client else "",
                    )
                )
                session.commit()
        except Exception:
            # Auditing must never turn a successful test-platform request into a 500.
            pass
    return response


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    """Serve a Chinese-first landing page before exposing API documentation."""
    return FileResponse(get_settings().root_dir / "app" / "static" / "index.html")


@app.get("/workbench", include_in_schema=False)
def workbench() -> FileResponse:
    return FileResponse(get_settings().root_dir / "app" / "static" / "workbench.html")


@app.get("/docs", include_in_schema=False)
def premium_swagger_docs() -> HTMLResponse:
    """Serve Swagger with a Chinese-first, product-quality visual theme."""
    swagger = get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{app.title} · 接口调试中心")
    content = swagger.body.decode("utf-8").replace(
        "</head>",
        '<link rel="stylesheet" href="/static/swagger-theme.css">'
        '<script defer src="/static/swagger-i18n.js"></script></head>',
    )
    return HTMLResponse(content, headers={"Cache-Control": "no-store"})


@app.get("/api-docs", include_in_schema=False)
def api_docs_redirect() -> RedirectResponse:
    """Keep the short-lived alternate URL compatible with the canonical docs URL."""
    return RedirectResponse(url="/docs", status_code=307)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}

