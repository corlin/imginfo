from app.config import settings
from app.routers.generate import resolve_generation_size


def test_dashscope_wanx_rejects_unsupported_512_size(monkeypatch):
    monkeypatch.setattr(settings, "API_PROVIDER", "aliyun")
    monkeypatch.setattr(settings, "CUSTOM_IMAGE_MODEL", "wanx-v1")

    assert resolve_generation_size(512, 512) == ("1024x1024", 1024, 1024)


def test_dashscope_wanx_keeps_supported_landscape_size(monkeypatch):
    monkeypatch.setattr(settings, "API_PROVIDER", "aliyun")
    monkeypatch.setattr(settings, "CUSTOM_IMAGE_MODEL", "wanx-v1")

    assert resolve_generation_size(1280, 720) == ("1280x720", 1280, 720)
