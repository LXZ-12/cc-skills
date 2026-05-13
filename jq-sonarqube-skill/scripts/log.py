"""统一日志配置模块"""
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

_loggers = {}
_log_dir = Path.home() / ".logs"
_log_dir.mkdir(exist_ok=True)


def setup_logging(log_file: str = "sonar_queries.log", level: str = "INFO") -> logging.Logger:
    """
    统一日志配置
    - 输出到 ~/.logs/<log_file>
    - 控制台同时输出
    - 格式: 时间 | 级别 | 消息
    """
    log_path = _log_dir / log_file

    logger = logging.getLogger("sonar")
    logger.setLevel(getattr(logging, level.upper()))

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "sonar") -> logging.Logger:
    """获取指定名称的 logger"""
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]


def log_query(logger: logging.Logger, query_type: str, sonarkey: str,
              cached: bool = False, elapsed: float = 0.0, results: int = 0,
              filters: dict = None, error: str = None):
    """记录查询日志"""
    if error:
        logger.error(f"Query: {query_type}, sonarkey: {sonarkey}, error: {error}")
        return

    parts = [f"Query: {query_type}, sonarkey: {sonarkey}"]
    if cached:
        parts.append(f"cached: true")
    if elapsed > 0:
        parts.append(f"elapsed: {elapsed:.2f}s")
    if results > 0:
        parts.append(f"results: {results}")
    if filters:
        parts.append(f"filters: {filters}")

    logger.info(", ".join(parts))
