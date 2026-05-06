from app.services.image_edit_executor import ImageExecutionPlan
from app.services.image_edit_plan import build_edit_plan, format_edit_plan_for_prompt, merge_ai_edit_plan


class AnalysisStub:
    def __init__(self, technical_description, key_features=None, structured_result=None):
        self.technical_description = technical_description
        self.key_features = key_features or []
        self.structured_result = structured_result or {}


class ImageStub:
    original_filename = "settings.png"
    width = 1226
    height = 1152
    file_type = "png"


def test_edit_plan_for_ui_preserves_text_and_blocks_diffusion_repaint():
    analysis = AnalysisStub(
        "一张 API 配置界面截图",
        ["API Key 输入框", "测试连接按钮"],
        {
            "image_type": "软件界面截图",
            "components": ["白色背景", "表单输入框", "保存按钮"],
        },
    )
    executor_plan = ImageExecutionPlan(
        executor="local_high_fidelity",
        reason="检测到 UI/截图/文字密集图片",
        uses_source_image=True,
    )

    plan = build_edit_plan(
        analysis,
        ImageStub(),
        user_instruction="增强字段层次",
        mode="preserve_style",
        execution_plan=executor_plan,
    )

    assert plan.intent == "增强字段层次"
    assert plan.executor == "local_high_fidelity"
    assert any("保留可读文字" in item for item in plan.must_preserve)
    assert any("肉眼可见" in item for item in plan.allowed_edits)
    assert any("不得使用扩散模型" in item for item in plan.must_not_change)
    assert any("本地增强不会新增复杂图形元素" in item for item in plan.risk_flags)


def test_edit_plan_for_new_illustration_allows_recomposing():
    analysis = AnalysisStub("API 配置方法", ["连接性测试"])
    executor_plan = ImageExecutionPlan(
        executor="cloud_text_to_image",
        reason="用户选择生成新的技术插图",
        uses_source_image=False,
    )

    plan = build_edit_plan(
        analysis,
        None,
        user_instruction="画系统结构",
        mode="technical_illustration",
        execution_plan=executor_plan,
    )

    assert plan.executor == "cloud_text_to_image"
    assert any("允许重新组织画面布局" in item for item in plan.allowed_edits)
    assert any("突出：连接性测试" in item for item in plan.allowed_edits)


def test_format_edit_plan_for_prompt_includes_constraints():
    plan = build_edit_plan(
        AnalysisStub("界面截图", ["保存配置"]),
        ImageStub(),
        user_instruction="提升清晰度",
        mode="preserve_style",
        execution_plan=ImageExecutionPlan(
            executor="local_high_fidelity",
            reason="检测到 UI",
            uses_source_image=True,
        ),
    )

    prompt_text = format_edit_plan_for_prompt(plan)

    assert "编辑计划" in prompt_text
    assert "必须保留" in prompt_text
    assert "允许修改" in prompt_text
    assert "禁止修改" in prompt_text


def test_merge_ai_edit_plan_keeps_executor_and_fills_ai_fields():
    fallback = build_edit_plan(
        AnalysisStub("界面截图", ["保存配置"]),
        ImageStub(),
        user_instruction="提升清晰度",
        mode="preserve_style",
        execution_plan=ImageExecutionPlan(
            executor="cloud_image_to_image",
            reason="用户选择云端图生图服务",
            uses_source_image=True,
        ),
    )

    plan = merge_ai_edit_plan(
        {
            "intent": "突出配置流程",
            "allowed_edits": ["增加步骤编号", "强化主按钮层级"],
            "must_preserve": ["保留白底表单风格"],
        },
        fallback,
    )

    assert plan.executor == "cloud_image_to_image"
    assert plan.intent == "突出配置流程"
    assert "AI计划" in plan.executor_reason
    assert plan.allowed_edits == ["增加步骤编号", "强化主按钮层级"]
    assert plan.must_not_change == fallback.must_not_change
