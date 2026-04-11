# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Structured logger powered by loguru.
"""
import sys

from loguru import logger

# Remove default handler, add custom stderr handler
logger.remove()
_handler_id = logger.add(
    sys.stderr,
    format="<level>[{level.name}]</level> {message}",
    level="WARNING",
)

_verbosity = 0


def set_verbosity(v: int) -> None:
    """Set verbosity level: 0=WARN+, 1=INFO+, 2=DEBUG+."""
    global _verbosity, _handler_id
    _verbosity = v
    level = "WARNING"
    if v >= 2:
        level = "DEBUG"
    elif v >= 1:
        level = "INFO"
    logger.remove(_handler_id)
    _handler_id = logger.add(
        sys.stderr,
        format="<level>[{level.name}]</level> {message}",
        level=level,
    )


def _fmt(msg: str, kwargs: dict) -> str:
    if not kwargs:
        return msg
    pairs = " ".join(f"{k}={v}" for k, v in kwargs.items())
    return f"{msg} {pairs}"


def info(msg: str, **kwargs: object) -> None:
    logger.info(_fmt(msg, kwargs))


def warn(msg: str, **kwargs: object) -> None:
    logger.warning(_fmt(msg, kwargs))


def error(msg: str, **kwargs: object) -> None:
    logger.error(_fmt(msg, kwargs))


def debug(msg: str, **kwargs: object) -> None:
    logger.debug(_fmt(msg, kwargs))
