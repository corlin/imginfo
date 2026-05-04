import os
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models.image import Image
from ..models.analysis import Analysis
from ..services.llm_service import llm_service

router = APIRouter()


class AnalysisRequest(BaseModel):
    image_id: int
    model_name: Optional[str] = "gpt-4-vision-preview"
    patent_focus: Optional[str] = "general"  # general, apparatus, method, composition
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
        
        prompt = f"""请从专利申请的角度分析这张图片，重点关注{focus_type}类型的专利。
        
请以JSON格式输出以下内容：
{{
    "image_type": "图片类型（技术图纸、流程图、结构图、照片等）",
    "content_description": "图片主要内容的详细描述",
    "components": ["组件1", "组件2", ...],
    "relationships": ["组件A与组件B的关系", ...],
    "technical_field": "所属技术领域",
    "technical_features": ["技术特征1", "技术特征2", ...],
    "key_elements": ["关键元素1", "关键元素2", ...],
    "patent_title": "建议的专利标题",
    "technical_problem": "解决的技术问题",
    "solution": "技术方案概述",
    "advantage": "技术效果/优势",
    "novelty_points": ["新颖性特征1", "新颖性特征2", ...]
}}"""
    
    # 调用LLM Vision API进行分析
    llm_result = await llm_service.analyze_image(image.file_path, prompt)
    
    if not llm_result["success"]:
        raise HTTPException(status_code=500, detail=f"图片分析失败: {llm_result.get('error', '未知错误')}")
    
    # 解析LLM返回的结果
    raw_output = llm_result["analysis"]
    
    # 尝试解析JSON
    try:
        # 处理可能的markdown代码块格式
        if "```json" in raw_output:
            json_str = raw_output.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_output:
            json_str = raw_output.split("```")[1].split("```")[0].strip()
        else:
            json_str = raw_output.strip()
        
        parsed_result = json.loads(json_str)
    except json.JSONDecodeError:
        # 如果解析失败，创建一个基本结构
        parsed_result = {
            "image_type": "未知",
            "content_description": raw_output,
            "components": [],
            "relationships": [],
            "technical_field": "未知",
            "technical_features": [],
            "key_elements": [],
            "patent_title": "待分析",
            "technical_problem": "待分析",
            "solution": "待分析",
            "advantage": "待分析",
            "novelty_points": []
        }
    
    # 构建结构化结果
    structured_result = {
        "image_type": parsed_result.get("image_type", "未知"),
        "content_description": parsed_result.get("content_description", ""),
        "components": parsed_result.get("components", []),
        "relationships": parsed_result.get("relationships", []),
        "technical_field": parsed_result.get("technical_field", "未知")
    }
    
    # 构建专利要素
    patent_elements = {
        "title": parsed_result.get("patent_title", "基于图片分析的技术方案"),
        "technical_problem": parsed_result.get("technical_problem", "现有技术中存在的问题"),
        "solution": parsed_result.get("solution", "本技术方案通过创新结构解决了上述问题"),
        "advantage": parsed_result.get("advantage", "提高了效率和可靠性"),
        "claim_type": request.patent_focus
    }
    
    # 生成技术描述
    technical_description = parsed_result.get("content_description", "")
    if not technical_description:
        technical_description = (
            f"本图片展示了{structured_result['technical_field']}领域的一项技术方案。"
            f"图片中包含以下主要组件：{', '.join(structured_result['components'])}。"
            f"各组件之间的关系为：{'; '.join(structured_result['relationships'])}。"
            f"该方案解决了{patent_elements['technical_problem']}的问题。"
        )
    
    # 提取关键特征
    key_features = parsed_result.get("technical_features", [])
    if not key_features:
        key_features = parsed_result.get("key_elements", ["创新的结构设计", "高效的组件布局"])
    
    # 新颖性分析
    novelty_points = parsed_result.get("novelty_points", [])
    if novelty_points:
        novelty_analysis = "基于图片分析，该技术方案具有以下新颖性特征：\n"
        for i, point in enumerate(novelty_points, 1):
            novelty_analysis += f"{i}. {point}\n"
    else:
        novelty_analysis = (
            "基于图片分析，该技术方案具有以下新颖性特征：\n"
            "1. 结构设计具有独创性\n"
            "2. 组件关系明确，技术方案清晰\n"
            "3. 具有实用性和可实施性"
        )
    
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