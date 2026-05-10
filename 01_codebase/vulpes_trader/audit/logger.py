"""日志配置 — 控制台 + 滚动文件日志"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent / "logs"


def setup_logger(name: str = "vulpes", level: int = logging.INFO) -> logging.Logger:
    """配置并返回 logger 实例"""
    LOG_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(console)

    # 文件 handler (10MB 滚动)
    file_handler = RotatingFileHandler(
        LOG_DIR / f"{name}.log",
        maxBytes=10_485_760,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
    ))
    logger.addHandler(file_handler)

    return logger
