from app.config import settings
from app.routers.generate import GenerateRequest, build_generation_prompt, extract_json_object, fallback_ai_edit_plan, generated_image_record, resolve_generation_size
from app.services.image_edit_plan import ImageEditPlan


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


def test_preserve_style_prompt_prevents_tech_illustration_drift():
    class AnalysisStub:
        technical_description = "一张白底 API 配置表单界面截图"
        key_features = ["API Key 输入框", "Base URL 输入框", "测试连接按钮"]
        structured_result = {
            "image_type": "软件界面截图",
            "components": ["白色背景", "表单输入框", "蓝色保存按钮"],
        }

    class ImageStub:
        original_filename = "settings.png"
        width = 1226
        height = 1152
        file_type = "png"

    prompt = build_generation_prompt(
        AnalysisStub(),
        GenerateRequest(
            analysis_id=1,
            prompt="增强配置项层次",
            mode="preserve_style",
            style="technical",
        ),
        ImageStub(),
    )

    assert "任务类型：保持原图风格优化" in prompt
    assert "不是重新创作一张概念图" in prompt
    assert "必须执行用户优化指令" in prompt
    assert "不是像素级复制" in prompt
    assert "不要返回与原图几乎无差异" in prompt
    assert "白底" in prompt
    assert "禁止改成 3D 渲染" in prompt
    assert "蓝色科技面板" in prompt
    assert "原图尺寸：1226x1152" in prompt
    assert "增强配置项层次" in prompt


def test_technical_illustration_prompt_allows_new_image():
    class AnalysisStub:
        technical_description = "API 配置方法"
        key_features = ["连接性测试"]
        structured_result = {}

    prompt = build_generation_prompt(
        AnalysisStub(),
        GenerateRequest(
            analysis_id=1,
            prompt="画系统结构",
            mode="technical_illustration",
            style="blueprint",
        ),
    )

    assert "任务类型：生成新的专利技术插图" in prompt
    assert "工程蓝图设计风格" in prompt
    assert "禁止改成 3D 渲染" not in prompt


def test_extract_json_object_accepts_markdown_json_block():
    data = extract_json_object(
        """```json
        {"intent":"增强层次","allowed_edits":["增加标注"]}
        ```"""
    )

    assert data["intent"] == "增强层次"
    assert data["allowed_edits"] == ["增加标注"]


def test_fallback_ai_edit_plan_preserves_plan_when_model_returns_plain_text():
    fallback = ImageEditPlan(
        intent="增强层次",
        executor="cloud_image_to_image",
        executor_reason="用户选择云端图生图",
        source_reference="source.png",
        must_preserve=["保留白底"],
        allowed_edits=["增加标注"],
        must_not_change=["不得改成3D"],
        risk_flags=[],
    )

    plan = fallback_ai_edit_plan("可以增加编号和箭头", fallback, "未找到JSON对象")

    assert plan.executor == "cloud_image_to_image"
    assert "AI计划兜底" in plan.executor_reason
    assert plan.allowed_edits == ["增加标注"]
    assert any("非JSON" in item for item in plan.risk_flags)
    assert any("可以增加编号和箭头" in item for item in plan.risk_flags)
