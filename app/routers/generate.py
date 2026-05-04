import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models.image import Image
from ..models.analysis import Analysis
from ..config import settings
from ..services.llm_service import llm_service

router = APIRouter()


class GenerateRequest(BaseModel):
    analysis_id: int
    prompt: str
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


@router.post("/generate")
async def generate_image(
    request: GenerateRequest,
    db: Session = Depends(get_db)
):
    """基于分析结果和用户指令生成图片"""
    # 查找分析结果
    analysis = db.query(Analysis).filter(Analysis.id == request.analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="分析结果不存在")
    
    # 构建生成提示词
    tech_desc = analysis.technical_description or ""
    key_features = analysis.key_features or []
    
    # 风格映射
    style_map = {
        "realistic": "写实逼真的照片级效果",
        "sketch": "简洁的线条草图风格",
        "technical": "专业的技术图纸风格，精确清晰",
        "artistic": "艺术化的创意表达风格",
        "3d": "三维立体渲染效果",
        "blueprint": "工程蓝图设计风格，蓝底白线"
    }
    style_desc = style_map.get(request.style, request.style)
    
    full_prompt = (
        f"基于专利技术方案的图片生成。"
        f"技术描述：{tech_desc}。"
        f"关键特征：{', '.join(key_features) if key_features else '无'}。"
        f"风格要求：{style_desc}。"
        f"用户指令：{request.prompt}"
    )
    
    # 调用LLM文生图API
    size_map = {
        (256, 256): "256x256",
        (512, 512): "512x512",
        (1024, 1024): "1024x1024",
    }
    size_str = size_map.get((request.width, request.height), "1024x1024")
    
    # DALL-E风格映射
    dalle_style = "natural"
    if request.style in ["realistic", "3d", "blueprint"]:
        dalle_style = "vivid"
    
    llm_result = await llm_service.generate_image(
        prompt=full_prompt,
        style=dalle_style,
        size=size_str
    )
    
    if not llm_result["success"]:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {llm_result.get('error', '未知错误')}")
    
    generated_images = []
    if llm_result.get("local_path"):
        generated_images.append({
            "filename": os.path.basename(llm_result["local_path"]),
            "file_path": llm_result["local_path"],
            "width": request.width,
            "height": request.height,
            "url": llm_result.get("image_url", "")
        })
    else:
        generated_images.append({
            "filename": "generated_image",
            "file_path": None,
            "width": request.width,
            "height": request.height,
            "url": llm_result.get("image_url", "")
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
        "style": request.style,
        "model": llm_result.get("model", "unknown"),
        "message": f"成功生成 {len(generated_images)} 张图片"
    }


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