import httpx

from app.services.llm_service import format_exception


def test_format_exception_uses_type_when_message_is_empty():
    assert format_exception(httpx.ReadTimeout("")) == "ReadTimeout"


def test_format_exception_keeps_message_when_present():
    assert format_exception(ValueError("bad input")) == "bad input"
