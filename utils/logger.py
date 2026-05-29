"""
统一日志模块 —— 所有模块通过 get_logger(__name__) 获取 logger
日志格式: [时间][级别][模块] 消息
"""
import logging
import sys

_log_initialized = False


def setup_logging(level: int = logging.INFO):
    global _log_initialized
    if _log_initialized:
        return
    _log_initialized = True

    fmt = logging.Formatter(
        "[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    setup_logging()  # 幂等，首次调用初始化
    return logging.getLogger(name)
