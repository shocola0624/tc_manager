from typing import Any

_TRUE_VALUES = {"true", "1", "yes"}
_FALSE_VALUES = {"false", "0", "no"}


def empty_str_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def parse_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    raise ValueError(f"invalid boolean value: {value!r}")


def parse_bool_default_true(value: Any) -> Any:
    """空欄は TRUE として扱う parse_bool。既存シートに列を後から足したとき、
    既存行が一斉に不正な行として弾かれないようにするための救済措置。"""
    if isinstance(value, str) and value.strip() == "":
        return True
    return parse_bool(value)
