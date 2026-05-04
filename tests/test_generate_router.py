from app.config import settings
from app.routers.generate import generated_image_record, resolve_generation_size


def test_dashscope_wanx_rejects_unsupported_512_size(monkeypatch):
    monkeypatch.setattr(settings, "API_PROVIDER", "aliyun")
    monkeypatch.setattr(settings, "CUSTOM_IMAGE_MODEL", "wanx-v1")

    assert resolve_generation_size(512, 512) == ("1024x1024", 1024, 1024)


def test_dashscope_wanx_keeps_supported_landscape_size(monkeypatch):
    monkeypatch.setattr(settings, "API_PROVIDER", "aliyun")
    monkeypatch.setattr(settings, "CUSTOM_IMAGE_MODEL", "wanx-v1")

    assert resolve_generation_size(1280, 720) == ("1280x720", 1280, 720)


def test_generated_image_record_exposes_review_url():
    class AnalysisStub:
        id = 7
        image_id = 3
        generated_image_path = "uploads/generated/gen_test.png"
        generation_prompt = "review prompt"
        updated_at = None
        created_at = "2026-05-04"

    record = generated_image_record(AnalysisStub())

    assert record["analysis_id"] == 7
    assert record["filename"] == "gen_test.png"
    assert record["url"] == "/uploads/generated/gen_test.png"
    assert record["prompt"] == "review prompt"
