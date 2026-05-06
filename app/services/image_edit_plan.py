"""Deterministic edit-plan builder for controlled image editing."""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.models.analysis import Analysis
from app.models.image import Image
from app.services.image_edit_executor import ImageExecutionPlan


@dataclass(frozen=True)
class ImageEditPlan:
    intent: str
    executor: str
    executor_reason: str
    source_reference: str
    must_preserve: List[str] = field(default_factory=list)
    allowed_edits: List[str] = field(default_factory=list)
    must_not_change: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_edit_plan(
    analysis: Analysis,
    source_image: Optional[Image],
    *,
    user_instruction: str,
    mode: str,
    execution_plan: ImageExecutionPlan,
) -> ImageEditPlan:
    structured_result = analysis.structured_result or {}
    image_context = structured_result.get("image_context", {}) or {}
    context_analysis = structured_result.get("context_analysis", {}) or {}
    image_type = structured_result.get("image_type") or image_context.get("image_type") or "未知"
    visible_evidence = _as_list(
        structured_result.get("components")
        or image_context.get("visible_evidence")
        or []
    )
    key_features = _as_list(analysis.key_features or [])
    context_gaps = _as_list(context_analysis.get("gaps") or [])

    source_reference = "未找到原图元数据"
    if source_image:
        source_reference = (
            f"{source_image.original_filename} ({source_image.width}x{source_image.height}, "
            f"{source_image.file_type})"
        )

    if mode == "technical_illustration":
        return ImageEditPlan(
            intent=user_instruction.strip() or "生成新的专利技术插图",
            executor=execution_plan.executor,
            executor_reason=execution_plan.reason,
            source_reference=source_reference,
            must_preserve=[
                "保留技术方案中的核心组件与关键关系",
                "保留用户上下文中明确给出的技术事实",
            ],
            allowed_edits=[
                "允许重新组织画面布局以形成专利技术插图",
                "允许抽象化表达系统结构、流程或模块关系",
                *[f"突出：{feature}" for feature in key_features[:5]],
            ],
            must_not_change=[
                "不得声称图片已证明新颖性或创造性",
                "不得加入用户上下文和图像分析均未支持的技术特征",
            ],
            risk_flags=context_gaps or ["新插图可能与原图视觉风格不同，需人工确认是否符合用途"],
        )

    must_preserve = [
        "保留原图主体、整体构图和视觉风格",
        "保留原图背景色、版式层级和主要元素位置",
    ]
    if source_image:
        must_preserve.append(f"保留原图长宽比例和接近原始分辨率：{source_image.width}x{source_image.height}")
    if "截图" in image_type or execution_plan.executor == "local_high_fidelity":
        must_preserve.extend([
            "保留可读文字、输入框、按钮和表单控件",
            "保留二维 UI 截图质感，不重绘为概念插画",
        ])
    must_preserve.extend([f"保留可见事实：{item}" for item in visible_evidence[:5]])

    allowed_edits = [
        user_instruction.strip() or "在保持原图风格前提下提升表达清晰度",
        "必须产生肉眼可见的优化结果，不要输出与原图几乎一致的图片",
        "允许轻微增强清晰度、对比度、标注层级和信息组织",
    ]
    allowed_edits.extend([f"强化表达：{feature}" for feature in key_features[:5]])

    must_not_change = [
        "不得把原图改成 3D 渲染、蓝色科技面板、发光线框或宣传海报",
        "不得改变无关区域",
        "不得新增未由图片、上下文或用户指令支持的技术结构",
    ]
    if execution_plan.executor == "local_high_fidelity":
        must_not_change.append("不得使用扩散模型重绘文字密集区域")

    risk_flags = context_gaps or []
    if execution_plan.executor == "cloud_image_to_image":
        risk_flags.append("云端图生图可能改变局部细节，生成后需审查风格一致性")
    if execution_plan.executor == "local_high_fidelity":
        risk_flags.append("本地增强不会新增复杂图形元素，只适合清晰化和轻微视觉优化")

    return ImageEditPlan(
        intent=user_instruction.strip() or "保持原图风格优化",
        executor=execution_plan.executor,
        executor_reason=execution_plan.reason,
        source_reference=source_reference,
        must_preserve=_dedupe(must_preserve),
        allowed_edits=_dedupe(allowed_edits),
        must_not_change=_dedupe(must_not_change),
        risk_flags=_dedupe(risk_flags),
    )


def format_edit_plan_for_prompt(plan: ImageEditPlan) -> str:
    return (
        "编辑计划："
        f"意图：{plan.intent}。"
        f"执行器：{plan.executor}（{plan.executor_reason}）。"
        f"原图参考：{plan.source_reference}。"
        f"必须保留：{'；'.join(plan.must_preserve) or '无'}。"
        f"允许修改：{'；'.join(plan.allowed_edits) or '无'}。"
        f"禁止修改：{'；'.join(plan.must_not_change) or '无'}。"
        f"风险提示：{'；'.join(plan.risk_flags) or '无'}。"
    )


def merge_ai_edit_plan(ai_data: Dict[str, Any], fallback: ImageEditPlan) -> ImageEditPlan:
    """Coerce a model-produced JSON object into the strict edit-plan shape."""
    return ImageEditPlan(
        intent=_clean_text(ai_data.get("intent")) or fallback.intent,
        executor=fallback.executor,
        executor_reason=f"AI计划：{fallback.executor_reason}",
        source_reference=fallback.source_reference,
        must_preserve=_dedupe(_as_list(ai_data.get("must_preserve")) or fallback.must_preserve),
        allowed_edits=_dedupe(_as_list(ai_data.get("allowed_edits")) or fallback.allowed_edits),
        must_not_change=_dedupe(_as_list(ai_data.get("must_not_change")) or fallback.must_not_change),
        risk_flags=_dedupe(_as_list(ai_data.get("risk_flags")) or fallback.risk_flags),
    )


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value).strip()]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _dedupe(values: List[str]) -> List[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
