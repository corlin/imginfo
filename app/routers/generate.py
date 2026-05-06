import json
import os
import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import SessionLocal, get_db
from ..models.analysis import Analysis
from ..models.image import Image
from ..config import settings
from ..services.image_edit_executor import choose_image_executor, execute_image_plan
from ..services.image_edit_plan import ImageEditPlan, build_edit_plan, format_edit_plan_for_prompt, merge_ai_edit_plan
from ..services.llm_service import llm_service
from ..services.storage_paths import public_upload_url
from ..services.task_store import task_store

router = APIRouter()
DASHSCOPE_ALLOWED_SIZES = {"1024x1024", "720x1280", "1280x720", "768x1152"}


class GenerateRequest(BaseModel):
    analysis_id: int
    prompt: str
    mode: Optional[str] = "preserve_style"  # preserve_style, technical_illustration
    executor: Optional[str] = "cloud_image_to_image"  # auto, cloud_image_to_image, cloud_text_to_image, local_high_fidelity
    plan_mode: Optional[str] = "local"  # local, ai
    edit_plan_override: Optional[dict] = None
    style: Optional[str] = "realistic"  # realistic, sketch, technical, artistic
    width: Optional[int] = 512
    height: Optional[int] = 512
    num_images: Optional[int] = 1
    guidance_scale: Optional[float] = 7.5
    num_inference_steps: Optional[int] = 50


class GenerateResponse(BaseModel):
    id: int
    analysis_id: int
    generated_images: list
    prompt: str
    style: str
    message: str


def resolve_generation_size(width: Optional[int], height: Optional[int]) -> tuple[str, int, int]:
    requested = f"{width or 1024}x{height or 1024}"
    provider = settings.API_PROVIDER.lower()
    image_model = (settings.CUSTOM_IMAGE_MODEL or settings.OPENAI_IMAGE_MODEL or "").lower()

    if provider == "aliyun" and "wanx" in image_model and requested not in DASHSCOPE_ALLOWED_SIZES:
        return "1024x1024", 1024, 1024

    size_map = {
        (256, 256): "256x256",
        (512, 512): "512x512",
        (1024, 1024): "1024x1024",
        (720, 1280): "720x1280",
        (1280, 720): "1280x720",
        (768, 1152): "768x1152",
    }
    size_str = size_map.get((width, height), "1024x1024")
    parsed_width, parsed_height = [int(part) for part in size_str.split("x")]
    return size_str, parsed_width, parsed_height


def build_generation_prompt(
    analysis: Analysis,
    request: GenerateRequest,
    source_image: Optional[Image] = None,
) -> str:
    tech_desc = analysis.technical_description or ""
    key_features = analysis.key_features or []
    structured_result = analysis.structured_result or {}
    image_type = structured_result.get("image_type") or structured_result.get("image_context", {}).get("image_type") or "未知"
    visible_evidence = structured_result.get("components") or structured_result.get("image_context", {}).get("visible_evidence") or []
    if not isinstance(visible_evidence, list):
        visible_evidence = [str(visible_evidence)]

    source_summary = "未找到原图元数据"
    if source_image:
        source_summary = (
            f"原图文件名：{source_image.original_filename}；"
            f"原图尺寸：{source_image.width}x{source_image.height}；"
            f"原图类型：{source_image.file_type}"
        )

    if request.mode == "technical_illustration":
        style_map = {
            "realistic": "写实逼真的照片级效果",
            "sketch": "简洁的线条草图风格",
            "technical": "专业的技术图纸风格，精确清晰",
            "artistic": "艺术化的创意表达风格",
            "3d": "三维立体渲染效果",
            "blueprint": "工程蓝图设计风格，蓝底白线",
        }
        style_desc = style_map.get(request.style, request.style)
        return (
            "任务类型：生成新的专利技术插图。"
            f"技术描述：{tech_desc}。"
            f"关键特征：{', '.join(key_features) if key_features else '无'}。"
            f"风格要求：{style_desc}。"
            f"用户指令：{request.prompt}"
        )

    return (
        "任务类型：保持原图风格优化。"
        "这不是重新创作一张概念图，也不是生成蓝色科技插画。"
        "必须执行用户优化指令，生成结果应当相对原图产生清晰可见的改动。"
        "保持原图风格是指主体、审美语言、版式逻辑和视觉类型一致，不是像素级复制，也不是只做轻微锐化。"
        "在不破坏原图语义的前提下，可以重排信息层级、强化重点、增加清晰标注、优化留白和视觉组织。"
        "同时保持原图的视觉风格、背景颜色、界面层级、控件形态、字体观感和二维截图/平面 UI 质感。"
        "如果原图是网页或软件界面截图，应保持白底、表单布局、输入框、按钮、标签文本区域和整体信息架构。"
        "禁止改成 3D 渲染、发光线框、蓝色科技面板、抽象硬件设备、未来感仪表盘或宣传海报。"
        "不要返回与原图几乎无差异的结果；如果用户指令较笼统，也要在原图风格基础上做可见的信息组织、标注一致性和专利表达友好度优化。"
        f"原图元数据：{source_summary}。"
        f"原图分析类型：{image_type}。"
        f"原图可见事实：{', '.join(visible_evidence) if visible_evidence else '无'}。"
        f"技术描述：{tech_desc}。"
        f"关键特征：{', '.join(key_features) if key_features else '无'}。"
        f"用户优化指令：{request.prompt}"
    )


@router.post("/generate")
async def generate_image(
    request: GenerateRequest,
    db: Session = Depends(get_db)
):
    """基于分析结果和用户指令生成图片"""
    return await run_image_generation(request, db)


@router.post("/generate/plan")
async def preview_generation_plan(
    request: GenerateRequest,
    db: Session = Depends(get_db)
):
    """生成编辑计划预览，不执行图片生成。"""
    prepared = await prepare_generation(request, db, use_ai_plan=(request.plan_mode == "ai"))
    return {
        "analysis_id": request.analysis_id,
        "mode": request.mode,
        "plan_mode": prepared["plan_mode"],
        "requested_executor": request.executor,
        "style": request.style,
        "prompt": prepared["full_prompt"],
        "executor": prepared["execution_plan"].executor,
        "executor_reason": prepared["execution_plan"].reason,
        "planner_model": prepared.get("planner_model"),
        "planner_provider": prepared.get("planner_provider"),
        "edit_plan": prepared["edit_plan"].to_dict(),
    }


@router.post("/generate/async")
async def enqueue_image_generation(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
):
    """创建图片生成任务，前端可通过 /tasks/{id} 查询进度。"""
    task = task_store.create("generation")
    background_tasks.add_task(run_generation_task, task["id"], request)
    return {
        "task_id": task["id"],
        "status": task["status"],
        "message": "生成任务已创建"
    }


async def run_generation_task(task_id: str, request: GenerateRequest) -> None:
    task_store.mark_running(task_id)
    db = SessionLocal()
    try:
        result = await run_image_generation(request, db)
        task_store.mark_completed(task_id, result)
    except HTTPException as exc:
        task_store.mark_failed(task_id, str(exc.detail))
    except Exception as exc:
        task_store.mark_failed(task_id, str(exc))
    finally:
        db.close()


async def run_image_generation(request: GenerateRequest, db: Session):
    prepared = await prepare_generation(request, db, use_ai_plan=(request.plan_mode == "ai"))
    analysis = prepared["analysis"]
    source_image = prepared["source_image"]
    full_prompt = prepared["full_prompt"]
    size_str = prepared["size_str"]
    output_width = prepared["output_width"]
    output_height = prepared["output_height"]
    dalle_style = prepared["dalle_style"]
    execution_plan = prepared["execution_plan"]
    edit_plan = prepared["edit_plan"]

    llm_result = await execute_image_plan(
        execution_plan,
        source_image=source_image,
        prompt=full_prompt,
        style=dalle_style,
        size=size_str,
    )

    if execution_plan.executor == "local_high_fidelity" and source_image:
        output_width = source_image.width or output_width
        output_height = source_image.height or output_height
    
    if not llm_result["success"]:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {llm_result.get('error', '未知错误')}")
    
    generated_images = []
    if llm_result.get("local_path"):
        generated_images.append({
            "filename": os.path.basename(llm_result["local_path"]),
            "file_path": llm_result["local_path"],
            "width": output_width,
            "height": output_height,
            "url": public_upload_url(llm_result["local_path"]),
            "source_url": llm_result.get("image_url", ""),
            "model": llm_result.get("model", "unknown"),
            "provider": llm_result.get("provider", "unknown"),
        })
    else:
        generated_images.append({
            "filename": "generated_image",
            "file_path": None,
            "width": output_width,
            "height": output_height,
            "url": llm_result.get("image_url", ""),
            "model": llm_result.get("model", "unknown"),
            "provider": llm_result.get("provider", "unknown"),
        })
    
    # 更新分析记录
    analysis.generation_prompt = full_prompt
    if generated_images and generated_images[0].get("file_path"):
        analysis.generated_image_path = generated_images[0]["file_path"]
    db.commit()
    
    return {
        "id": analysis.id,
        "analysis_id": request.analysis_id,
        "generated_images": generated_images,
        "prompt": full_prompt,
        "mode": request.mode,
        "requested_executor": request.executor,
        "style": request.style,
        "executor": execution_plan.executor,
        "executor_reason": execution_plan.reason,
        "edit_plan": edit_plan.to_dict(),
        "model": llm_result.get("model", "unknown"),
        "message": f"成功生成 {len(generated_images)} 张图片"
    }


async def prepare_generation(request: GenerateRequest, db: Session, use_ai_plan: bool = False) -> dict:
    analysis = db.query(Analysis).filter(Analysis.id == request.analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="分析结果不存在")

    source_image = db.query(Image).filter(Image.id == analysis.image_id).first()
    base_prompt = build_generation_prompt(analysis, request, source_image)
    
    # 调用LLM文生图API
    size_str, output_width, output_height = resolve_generation_size(request.width, request.height)
    
    # DALL-E风格映射
    dalle_style = "natural"
    if request.mode == "technical_illustration" and request.style in ["realistic", "3d", "blueprint"]:
        dalle_style = "vivid"

    execution_plan = choose_image_executor(
        analysis,
        request.mode or "preserve_style",
        request.executor or "auto",
    )
    edit_plan = build_edit_plan(
        analysis,
        source_image,
        user_instruction=request.prompt,
        mode=request.mode or "preserve_style",
        execution_plan=execution_plan,
    )
    if execution_plan.uses_source_image:
        if not source_image or not os.path.exists(source_image.file_path):
            raise HTTPException(status_code=404, detail="原图文件不存在，无法执行需要参考图的编辑")

    plan_mode = request.plan_mode if request.plan_mode in {"local", "ai"} else "local"
    planner_model = None
    planner_provider = None
    if request.edit_plan_override:
        edit_plan = merge_ai_edit_plan(request.edit_plan_override, edit_plan)
    elif use_ai_plan:
        ai_plan_result = await build_ai_edit_plan(analysis, source_image, request, execution_plan, edit_plan)
        edit_plan = ai_plan_result["edit_plan"]
        plan_mode = "ai"
        planner_model = ai_plan_result.get("planner_model")
        planner_provider = ai_plan_result.get("planner_provider")

    full_prompt = f"{base_prompt}{format_edit_plan_for_prompt(edit_plan)}"

    return {
        "analysis": analysis,
        "source_image": source_image,
        "full_prompt": full_prompt,
        "size_str": size_str,
        "output_width": output_width,
        "output_height": output_height,
        "dalle_style": dalle_style,
        "execution_plan": execution_plan,
        "edit_plan": edit_plan,
        "plan_mode": plan_mode,
        "planner_model": planner_model,
        "planner_provider": planner_provider,
    }


def build_ai_plan_prompt(
    analysis: Analysis,
    source_image: Optional[Image],
    request: GenerateRequest,
    execution_plan,
    fallback_plan: ImageEditPlan,
) -> str:
    structured_result = analysis.structured_result or {}
    source_summary = "无原图元数据"
    if source_image:
        source_summary = (
            f"{source_image.original_filename}, {source_image.width}x{source_image.height}, "
            f"{source_image.file_type}"
        )

    return (
        "你是专利图片编辑导演。请基于原图、已有分析和用户指令，生成一个可执行的图片编辑计划。"
        "只输出一个合法JSON对象，不要输出Markdown代码块、解释文字、前后缀或自然语言段落。"
        "JSON字段必须为：intent, must_preserve, allowed_edits, must_not_change, risk_flags。"
        "其中 must_preserve、allowed_edits、must_not_change、risk_flags 必须是字符串数组。"
        "计划要比本地规则更具体，必须包含肉眼可见的修改动作，但不能引入图片和上下文均不支持的新技术事实。"
        "如果是保持原图风格优化，不要建议像素级复制，也不要只建议锐化。"
        f"用户指令：{request.prompt}。"
        f"生成模式：{request.mode}。执行器：{execution_plan.executor}。"
        f"原图元数据：{source_summary}。"
        f"技术描述：{analysis.technical_description or '无'}。"
        f"关键特征：{', '.join(analysis.key_features or []) if analysis.key_features else '无'}。"
        f"结构化分析：{json.dumps(structured_result, ensure_ascii=False)[:3000]}。"
        f"本地快速计划参考：{json.dumps(fallback_plan.to_dict(), ensure_ascii=False)}。"
    )


async def build_ai_edit_plan(
    analysis: Analysis,
    source_image: Optional[Image],
    request: GenerateRequest,
    execution_plan,
    fallback_plan: ImageEditPlan,
) -> dict:
    prompt = build_ai_plan_prompt(analysis, source_image, request, execution_plan, fallback_plan)
    image_path = source_image.file_path if source_image and os.path.exists(source_image.file_path) else None
    result = await llm_service.generate_edit_plan(prompt, image_path=image_path)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"AI编辑计划失败: {result.get('error', '未知错误')}")

    try:
        ai_data = extract_json_object(result["plan_text"])
    except ValueError as exc:
        edit_plan = fallback_ai_edit_plan(result["plan_text"], fallback_plan, str(exc))
        return {
            "edit_plan": edit_plan,
            "planner_model": result.get("model"),
            "planner_provider": result.get("provider"),
        }

    return {
        "edit_plan": merge_ai_edit_plan(ai_data, fallback_plan),
        "planner_model": result.get("model"),
        "planner_provider": result.get("provider"),
    }


def extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("未找到JSON对象")
    data = json.loads(stripped[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("顶层结果不是JSON对象")
    return data


def fallback_ai_edit_plan(plan_text: str, fallback_plan: ImageEditPlan, reason: str) -> ImageEditPlan:
    raw_text = str(plan_text or "").strip()
    risk_flags = [
        *fallback_plan.risk_flags,
        f"AI计划返回了非JSON内容，已使用快速计划兜底：{reason}",
    ]
    if raw_text:
        risk_flags.append(f"AI原始建议摘要：{raw_text[:240]}")
    return ImageEditPlan(
        intent=fallback_plan.intent,
        executor=fallback_plan.executor,
        executor_reason=f"AI计划兜底：{fallback_plan.executor_reason}",
        source_reference=fallback_plan.source_reference,
        must_preserve=fallback_plan.must_preserve,
        allowed_edits=fallback_plan.allowed_edits,
        must_not_change=fallback_plan.must_not_change,
        risk_flags=risk_flags,
    )


@router.get("/generate/styles")
async def get_available_styles():
    """获取可用的生成风格"""
    return {
        "styles": [
            {"id": "realistic", "name": "写实风格", "description": "逼真的照片级效果"},
            {"id": "sketch", "name": "草图风格", "description": "简洁的线条草图"},
            {"id": "technical", "name": "技术图纸", "description": "专业的技术图纸风格"},
            {"id": "artistic", "name": "艺术风格", "description": "艺术化的创意表达"},
            {"id": "3d", "name": "3D渲染", "description": "三维立体渲染效果"},
            {"id": "blueprint", "name": "蓝图风格", "description": "工程蓝图设计风格"}
        ]
    }


@router.get("/generate/history")
async def list_generated_images(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取已生成图片列表，供前端review。"""
    query = db.query(Analysis).filter(Analysis.generated_image_path.isnot(None))
    analyses = query.order_by(Analysis.updated_at.desc(), Analysis.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": query.count(),
        "generated_images": [
            generated_image_record(analysis)
            for analysis in analyses
        ],
    }


def generated_image_record(analysis: Analysis) -> dict:
    path = analysis.generated_image_path or ""
    return {
        "analysis_id": analysis.id,
        "image_id": analysis.image_id,
        "filename": os.path.basename(path),
        "file_path": path,
        "url": public_upload_url(path),
        "prompt": analysis.generation_prompt or "",
        "created_at": str(analysis.updated_at or analysis.created_at),
    }


@router.get("/generate/models")
async def get_available_models():
    """获取可用的生成模型"""
    return {
        "models": [
            {
                "id": settings.OPENAI_IMAGE_MODEL,
                "name": "DALL-E 3",
                "description": "OpenAI文生图模型",
                "status": "available" if settings.OPENAI_API_KEY else "未配置API Key"
            }
        ]
    }
