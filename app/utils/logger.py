from pathlib import Path

from loguru import logger

from app.utils.config import get_settings


def init_logger() -> None:
    settings = get_settings()
    log_dir = settings.root_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    logger.remove()
    logger.add(
        log_dir / "app.log",
        level=settings.log_level,
        encoding="utf-8",
        rotation="10 MB",
        retention="14 days",
        enqueue=True,
    )
    logger.add(lambda msg: print(msg, end=""), level=settings.log_level)


__all__ = ["logger", "init_logger"]

