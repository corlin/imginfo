from PIL import Image

from app.config import settings
from app.services.image_edit_executor import choose_image_executor, enhance_image_locally


class AnalysisStub:
    def __init__(self, technical_description, structured_result=None):
        self.technical_description = technical_description
        self.structured_result = structured_result or {}


def test_choose_executor_uses_local_for_ui_screenshots():
    analysis = AnalysisStub(
        "一张 API 配置界面截图，包含输入框和保存按钮",
        {
            "image_type": "软件界面截图",
            "components": ["API Key 输入框", "Base URL 表单", "保存配置按钮"],
        },
    )

    plan = choose_image_executor(analysis, "preserve_style")

    assert plan.executor == "local_high_fidelity"
    assert plan.uses_source_image is True
    assert "文字密集" in plan.reason


def test_choose_executor_respects_cloud_image_edit_override_for_ui_screenshots():
    analysis = AnalysisStub(
        "一张 API 配置界面截图，包含输入框和保存按钮",
        {
            "image_type": "软件界面截图",
            "components": ["API Key 输入框", "Base URL 表单", "保存配置按钮"],
        },
    )

    plan = choose_image_executor(analysis, "preserve_style", "cloud_image_to_image")

    assert plan.executor == "cloud_image_to_image"
    assert plan.uses_source_image is True
    assert "用户选择云端图生图服务" in plan.reason


def test_choose_executor_respects_local_override_for_non_ui_images():
    analysis = AnalysisStub(
        "机械齿轮传动结构照片",
        {"image_type": "产品照片", "components": ["齿轮", "传动轴"]},
    )

    plan = choose_image_executor(analysis, "preserve_style", "local_high_fidelity")

    assert plan.executor == "local_high_fidelity"
    assert plan.uses_source_image is True
    assert "不调用外部生成服务" in plan.reason


def test_choose_executor_uses_cloud_image_edit_for_non_ui_images():
    analysis = AnalysisStub(
        "机械齿轮传动结构照片",
        {"image_type": "产品照片", "components": ["齿轮", "传动轴"]},
    )

    plan = choose_image_executor(analysis, "preserve_style")

    assert plan.executor == "cloud_image_to_image"
    assert plan.uses_source_image is True


def test_choose_executor_uses_text_to_image_for_new_illustrations():
    analysis = AnalysisStub("API 配置系统")

    plan = choose_image_executor(analysis, "technical_illustration")

    assert plan.executor == "cloud_text_to_image"
    assert plan.uses_source_image is False


def test_local_enhancer_preserves_dimensions_and_writes_png(monkeypatch, tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (240, 120), "white").save(source)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))

    result = enhance_image_locally(str(source))

    assert result["success"] is True
    assert result["model"] == "local-high-fidelity-enhance"
    assert result["local_path"].endswith(".png")
    with Image.open(result["local_path"]) as enhanced:
        assert enhanced.size == (240, 120)
