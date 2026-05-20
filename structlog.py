from __future__ import annotations

import datetime as _dt
import json as _json
import logging as _logging


class _CompatLogger:
    def __init__(self, name: str | None = None) -> None:
        self._logger = _logging.getLogger(name or "agentmd")

    def bind(self, **_: object) -> "_CompatLogger":
        return self

    def new(self, **_: object) -> "_CompatLogger":
        return self

    def _emit(self, level: str, event: object, **kwargs: object) -> None:
        exc_info = bool(kwargs.pop("exc_info", False))
        stack_info = bool(kwargs.pop("stack_info", False))
        message = str(event)
        if kwargs:
            details = " ".join(f"{k}={v!r}" for k, v in sorted(kwargs.items()))
            message = f"{message} {details}"
        getattr(self._logger, level)(message, exc_info=exc_info, stack_info=stack_info)

    def debug(self, event: object, **kwargs: object) -> None:
        self._emit("debug", event, **kwargs)

    def info(self, event: object, **kwargs: object) -> None:
        self._emit("info", event, **kwargs)

    def warning(self, event: object, **kwargs: object) -> None:
        self._emit("warning", event, **kwargs)

    def error(self, event: object, **kwargs: object) -> None:
        self._emit("error", event, **kwargs)

    def exception(self, event: object, **kwargs: object) -> None:
        kwargs["exc_info"] = True
        self._emit("error", event, **kwargs)

    def critical(self, event: object, **kwargs: object) -> None:
        self._emit("critical", event, **kwargs)


def get_logger(name: str | None = None) -> _CompatLogger:
    return _CompatLogger(name)


def configure(**_: object) -> None:
    return None


def make_filtering_bound_logger(_: int):
    return _CompatLogger


class _TimeStamper:
    def __init__(self, fmt: str = "iso", utc: bool = True) -> None:
        self.fmt = fmt
        self.utc = utc

    def __call__(self, _: object, __: object, event_dict: dict[str, object]) -> dict[str, object]:
        ts = _dt.datetime.utcnow().isoformat() if self.utc else _dt.datetime.now().isoformat()
        event_dict["timestamp"] = ts
        return event_dict


class _EventRenamer:
    def __init__(self, key: str) -> None:
        self.key = key

    def __call__(self, _: object, __: object, event_dict: dict[str, object]) -> dict[str, object]:
        if "event" in event_dict:
            event_dict[self.key] = event_dict.pop("event")
        return event_dict


class _JSONRenderer:
    def __call__(self, _: object, __: object, event_dict: dict[str, object]) -> str:
        return _json.dumps(event_dict, default=str)


class processors:
    TimeStamper = _TimeStamper
    EventRenamer = _EventRenamer
    JSONRenderer = _JSONRenderer

    @staticmethod
    def add_log_level(_: object, method_name: str, event_dict: dict[str, object]) -> dict[str, object]:
        event_dict["level"] = method_name
        return event_dict

    @staticmethod
    def dict_tracebacks(_: object, __: object, event_dict: dict[str, object]) -> dict[str, object]:
        return event_dict


class contextvars:
    @staticmethod
    def merge_contextvars(_: object, __: object, event_dict: dict[str, object]) -> dict[str, object]:
        return event_dict


class stdlib:
    @staticmethod
    def filter_by_level(_: object, __: object, event_dict: dict[str, object]) -> dict[str, object]:
        return event_dict

    class LoggerFactory:
        def __call__(self, *args: object, **kwargs: object) -> _CompatLogger:
            name = kwargs.get("name")
            return _CompatLogger(name if isinstance(name, str) else None)
