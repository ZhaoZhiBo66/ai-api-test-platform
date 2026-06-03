from fastapi import FastAPI

from app.api.ai_case_api import router as ai_case_router
from app.api.interface_api import router as interface_router
from app.api.report_api import router as report_router
from app.api.run_api import router as run_router
from app.database.db import Base, engine
from app.utils.logger import init_logger

init_logger()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI 智能接口自动化测试平台",
    description="基于 FastAPI + Pytest + OpenAI API 的接口自动化测试平台",
    version="1.0.0",
)

app.include_router(interface_router)
app.include_router(ai_case_router)
app.include_router(run_router)
app.include_router(report_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}

