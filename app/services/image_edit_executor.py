"""Execution strategies for controlled image generation and editing."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import uuid

from PIL import Image as PILImage
from PIL import ImageEnhance, ImageFilter

from app.config import settings
from app.models.analysis import Analysis
from app.models.image import Image
from app.services.llm_service import llm_service


@dataclass(frozen=True)
class ImageExecutionPlan:
    executor: str
    reason: str
    uses_source_image: bool


SCREENSHOT_MARKERS = [
    "截图",
    "界面",
    "ui",
    "表单",
    "网页",
    "软件",
    "输入框",
    "按钮",
    "api",
    "配置",
    "文档",
    "表格",
]


def choose_image_executor(analysis: Analysis, mode: str, executor_override: Optional[str] = None) -> ImageExecutionPlan:
    if executor_override and executor_override != "auto":
        return _execution_plan_from_override(executor_override, mode)

    if mode == "technical_illustration":
        return ImageExecutionPlan(
            executor="cloud_text_to_image",
            reason="用户选择生成新的技术插图，可重新创作画面",
            uses_source_image=False,
        )

    if _is_text_heavy_or_ui_image(analysis):
        return ImageExecutionPlan(
            executor="local_high_fidelity",
            reason="检测到 UI/截图/文字密集图片，避免图生图重绘文字导致模糊",
            uses_source_image=True,
        )

    return ImageExecutionPlan(
        executor="cloud_image_to_image",
        reason="非文字密集图片，可使用云端图生图参考原图编辑",
        uses_source_image=True,
    )


def _execution_plan_from_override(executor: str, mode: str) -> ImageExecutionPlan:
    if executor == "local_high_fidelity":
        return ImageExecutionPlan(
            executor="local_high_fidelity",
            reason="用户选择本地保真增强，不调用外部生成服务",
            uses_source_image=True,
        )

    if executor == "cloud_image_to_image":
        return ImageExecutionPlan(
            executor="cloud_image_to_image",
            reason="用户选择云端图生图服务，将参考原图执行编辑",
            uses_source_image=True,
        )

    if executor == "cloud_text_to_image":
        return ImageExecutionPlan(
            executor="cloud_text_to_image",
            reason="用户选择云端文生图服务，将基于分析结果重新生成",
            uses_source_image=False,
        )

    if mode == "technical_illustration":
        return ImageExecutionPlan(
            executor="cloud_text_to_image",
            reason="未知执行方式，已按技术插图模式使用云端文生图",
            uses_source_image=False,
        )

    return ImageExecutionPlan(
        executor="cloud_image_to_image",
        reason="未知执行方式，已按保持原图风格模式使用云端图生图",
        uses_source_image=True,
    )


async def execute_image_plan(
    plan: ImageExecutionPlan,
    *,
    source_image: Optional[Image],
    prompt: str,
    style: str,
    size: str,
) -> dict:
    if plan.uses_source_image and not source_image:
        return {"success": False, "error": "原图记录不存在，无法执行需要参考图的编辑"}

    if plan.executor == "local_high_fidelity":
        return enhance_image_locally(source_image.file_path)

    if plan.executor == "cloud_image_to_image":
        return await llm_service.edit_image(
            image_path=source_image.file_path,
            prompt=prompt,
            size=size,
        )

    return await llm_service.generate_image(
        prompt=prompt,
        style=style,
        size=size,
    )


def enhance_image_locally(image_path: str) -> dict:
    source_path = Path(image_path)
    generated_dir = Path(settings.UPLOAD_DIR) / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    output_path = generated_dir / f"enhanced_{uuid.uuid4().hex[:12]}.png"

    with PILImage.open(source_path) as image:
        image = image.convert("RGB")
        enhanced = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=3))
        enhanced = ImageEnhance.Contrast(enhanced).enhance(1.04)
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.08)
        enhanced.save(output_path, format="PNG", optimize=True)

    return {
        "success": True,
        "image_url": "",
        "local_path": str(output_path),
        "prompt": "",
        "model": "local-high-fidelity-enhance",
        "provider": "local",
    }


def _is_text_heavy_or_ui_image(analysis: Analysis) -> bool:
    structured_result = analysis.structured_result or {}
    image_context = structured_result.get("image_context", {}) or {}
    components = structured_result.get("components") or image_context.get("visible_evidence") or []
    if not isinstance(components, list):
        components = [str(components)]

    content = " ".join(
        [
            str(structured_result.get("image_type") or ""),
            str(image_context.get("image_type") or ""),
            analysis.technical_description or "",
            " ".join(str(component) for component in components),
        ]
    ).lower()
    return any(marker in content for marker in SCREENSHOT_MARKERS)
