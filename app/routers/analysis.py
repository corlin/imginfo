import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import SessionLocal, get_db
from ..models.image import Image
from ..models.analysis import Analysis
from ..services.llm_service import llm_service
from ..services.analysis_parser import build_analysis_artifacts, build_patent_prompt
from ..services.task_store import task_store

router = APIRouter()


class AnalysisRequest(BaseModel):
    image_id: int
    model_name: Optional[str] = "gpt-4-vision-preview"
    patent_focus: Optional[str] = "general"  # general, apparatus, method, composition
    user_context: Optional[str] = None
    custom_prompt: Optional[str] = None


class AnalysisResponse(BaseModel):
    id: int
    image_id: int
    model_name: str
    structured_result: dict
    patent_elements: dict
    technical_description: str
    key_features: list
    novelty_analysis: str


@router.post("/analyze")
async def analyze_image(
    request: AnalysisRequest,
    db: Session = Depends(get_db)
):
    """分析图片（基于专利角度）"""
    return await run_image_analysis(request, db)


@router.post("/analyze/async")
async def enqueue_image_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
):
    """创建图片分析任务，前端可通过 /tasks/{id} 查询进度。"""
    task = task_store.create("analysis")
    background_tasks.add_task(run_analysis_task, task["id"], request)
    return {
        "task_id": task["id"],
        "status": task["status"],
        "message": "分析任务已创建"
    }


async def run_analysis_task(task_id: str, request: AnalysisRequest) -> None:
    task_store.mark_running(task_id)
    db = SessionLocal()
    try:
        result = await run_image_analysis(request, db)
        task_store.mark_completed(task_id, result)
    except HTTPException as exc:
        task_store.mark_failed(task_id, str(exc.detail))
    except Exception as exc:
        task_store.mark_failed(task_id, str(exc))
    finally:
        db.close()


async def run_image_analysis(request: AnalysisRequest, db: Session):
    # 查找图片
    image = db.query(Image).filter(Image.id == request.image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 检查图片文件是否存在
    if not os.path.exists(image.file_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")
    
    # 构建分析提示词
    if request.custom_prompt:
        prompt = request.custom_prompt
    else:
        patent_focus_map = {
            "general": "通用",
            "apparatus": "装置/设备",
            "method": "方法/工艺",
            "composition": "组合物/配方"
        }
        focus_type = patent_focus_map.get(request.patent_focus, "通用")
        
        prompt = build_patent_prompt(focus_type, request.user_context or "")
    
    # 调用LLM Vision API进行分析
    llm_result = await llm_service.analyze_image(image.file_path, prompt)
    
    if not llm_result["success"]:
        raise HTTPException(status_code=500, detail=f"图片分析失败: {llm_result.get('error', '未知错误')}")
    
    raw_output = llm_result["analysis"]
    artifacts = build_analysis_artifacts(
        raw_output,
        request.patent_focus or "general",
        request.user_context or "",
    )
    structured_result = artifacts["structured_result"]
    patent_elements = artifacts["patent_elements"]
    technical_description = artifacts["technical_description"]
    key_features = artifacts["key_features"]
    novelty_analysis = artifacts["novelty_analysis"]
    
    # 创建分析记录
    analysis = Analysis(
        image_id=request.image_id,
        model_name=request.model_name,
        raw_output=raw_output,
        structured_result=structured_result,
        patent_elements=patent_elements,
        technical_description=technical_description,
        key_features=key_features,
        novelty_analysis=novelty_analysis
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    
    # 更新图片的分析关联
    image.analysis_id = analysis.id
    db.commit()
    
    return {
        "id": analysis.id,
        "image_id": request.image_id,
        "model_name": request.model_name,
        "structured_result": structured_result,
        "patent_elements": patent_elements,
        "technical_description": technical_description,
        "key_features": key_features,
        "novelty_analysis": novelty_analysis,
        "message": "分析完成"
    }


@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """获取分析结果"""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="分析结果不存在")
    return {
        "id": analysis.id,
        "image_id": analysis.image_id,
        "model_name": analysis.model_name,
        "structured_result": analysis.structured_result,
        "patent_elements": analysis.patent_elements,
        "technical_description": analysis.technical_description,
        "key_features": analysis.key_features,
        "novelty_analysis": analysis.novelty_analysis,
        "created_at": str(analysis.created_at)
    }


@router.get("/analyses")
async def list_analyses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取分析列表"""
    analyses = db.query(Analysis).offset(skip).limit(limit).all()
    total = db.query(Analysis).count()
    return {
        "total": total,
        "analyses": [
            {
                "id": a.id,
                "image_id": a.image_id,
                "model_name": a.model_name,
                "created_at": str(a.created_at)
            }
            for a in analyses
        ]
    }
