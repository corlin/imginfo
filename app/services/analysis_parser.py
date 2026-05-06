"""Utilities for turning vision-model output into patent-safe analysis data."""
import json
from typing import Any, Dict, List

from pydantic import BaseModel, Field, ValidationError, field_validator


class PatentImageAnalysis(BaseModel):
    image_type: str = "未知"
    content_description: str = ""
    scene_context: str = "需结合图片来源或业务场景确认"
    technical_domain: str = "未知"
    visible_evidence: List[str] = Field(default_factory=list)
    inferred_context: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    context_alignment: str = "未提供用户上下文，无法进行上下文对齐"
    context_supported_points: List[str] = Field(default_factory=list)
    context_gaps: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)
    technical_field: str = "未知"
    technical_features: List[str] = Field(default_factory=list)
    key_elements: List[str] = Field(default_factory=list)
    patent_title: str = "待分析的图片技术方案"
    technical_problem: str = "需结合现有技术进一步确认"
    solution: str = "需基于可见结构和人工确认后形成"
    advantage: str = "需结合实验数据或现有技术对比确认"
    novelty_points: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)

    @field_validator(
        "components",
        "relationships",
        "visible_evidence",
        "inferred_context",
        "uncertainties",
        "context_supported_points",
        "context_gaps",
        "technical_features",
        "key_elements",
        "novelty_points",
        "risk_flags",
        mode="before",
    )
    @classmethod
    def coerce_string_list(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return [str(value)]


def build_patent_prompt(focus_type: str, user_context: str = "") -> str:
    context_block = ""
    if user_context.strip():
        context_block = f"""
用户提供的确定性上下文如下，请将其作为输入材料使用，而不是作为模型推断输出：
---
{user_context.strip()}
---
"""

    return f"""请从专利申请准备的角度分析这张图片，重点关注{focus_type}类型的专利。
{context_block}

重要边界：
1. 只能基于图片可见内容描述技术事实，不要编造图中不存在的结构或步骤。
2. 未进行现有技术检索时，不要断言“具有新颖性/创造性”。
3. 如果用户提供了专利原文、权利要求、说明书片段或业务场景，请把它当作确定性上下文输入。
4. 请区分“图片可见事实”“用户上下文支持的点”“图片与上下文不一致或待人工确认的点”。

请仅以JSON格式输出以下内容：
{{
    "image_type": "图片类型（技术图纸、流程图、结构图、照片等）",
    "scene_context": "仅当用户上下文中明确给出场景时填写，否则说明未提供确定场景",
    "technical_domain": "可能所属技术领域",
    "visible_evidence": ["图片中直接可见、可支撑判断的事实"],
    "context_alignment": "图片内容与用户上下文/专利文本的整体对应关系",
    "context_supported_points": ["图片直接支持用户上下文中的哪些技术点"],
    "context_gaps": ["用户上下文提到但图片无法确认、缺失或存在不一致的点"],
    "inferred_context": ["必要时列出基于图片的有限推断，必须说明为推断"],
    "uncertainties": ["仅凭图片无法确认、需要用户补充或人工核查的信息"],
    "content_description": "图片主要内容的详细描述",
    "components": ["可见组件1", "可见组件2"],
    "relationships": ["组件A与组件B的可见连接或功能关系"],
    "technical_field": "可能所属技术领域",
    "technical_features": ["可从图片支持的技术特征"],
    "key_elements": ["对权利要求可能重要的要素"],
    "patent_title": "建议的中性专利标题",
    "technical_problem": "可能要解决的技术问题，需注明待确认",
    "solution": "基于可见内容的技术方案概述",
    "advantage": "可能技术效果，需注明待验证",
    "novelty_points": ["潜在可保护点，不得表述为已具备新颖性"],
    "risk_flags": ["需要人工确认或现有技术检索的风险"]
}}"""


def parse_llm_analysis(raw_output: Any) -> PatentImageAnalysis:
    if isinstance(raw_output, PatentImageAnalysis):
        return raw_output
    if isinstance(raw_output, dict):
        return _validate_analysis(raw_output)
    if not isinstance(raw_output, str):
        return _fallback_analysis(str(raw_output))

    text = raw_output.strip()
    try:
        return _validate_analysis(json.loads(_extract_json_payload(text)))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return _fallback_analysis(text)


def build_analysis_artifacts(
    raw_output: Any,
    claim_type: str,
    user_context: str = "",
) -> Dict[str, Any]:
    parsed = parse_llm_analysis(raw_output)
    image_context = _build_image_context(parsed)

    structured_result = {
        "user_context": user_context.strip(),
        "image_context": image_context,
        "context_analysis": {
            "alignment": parsed.context_alignment,
            "supported_points": parsed.context_supported_points,
            "gaps": parsed.context_gaps,
        },
        "image_type": parsed.image_type,
        "content_description": parsed.content_description,
        "components": parsed.components,
        "relationships": parsed.relationships,
        "technical_field": parsed.technical_field,
        "risk_flags": parsed.risk_flags,
    }

    patent_elements = {
        "title": parsed.patent_title,
        "technical_problem": parsed.technical_problem,
        "solution": parsed.solution,
        "advantage": parsed.advantage,
        "claim_type": claim_type,
    }

    key_features = parsed.technical_features or parsed.key_elements
    if not key_features:
        key_features = ["模型未能可靠提取技术特征，需人工复核图片内容"]

    return {
        "structured_result": structured_result,
        "patent_elements": patent_elements,
        "technical_description": _build_technical_description(parsed),
        "key_features": key_features,
        "novelty_analysis": _build_patentability_note(parsed),
    }


def _extract_json_payload(text: str) -> str:
    if "```json" in text:
        return text.split("```json", 1)[1].split("```", 1)[0].strip()
    if "```" in text:
        return text.split("```", 1)[1].split("```", 1)[0].strip()
    return text


def _validate_analysis(data: Dict[str, Any]) -> PatentImageAnalysis:
    # Older mock responses used main_content and patent_suggestions.
    if "content_description" not in data and "main_content" in data:
        data = {**data, "content_description": data["main_content"]}
    if "risk_flags" not in data and "patent_suggestions" in data:
        data = {**data, "risk_flags": [data["patent_suggestions"]]}
    if "technical_domain" not in data and "technical_field" in data:
        data = {**data, "technical_domain": data["technical_field"]}
    return PatentImageAnalysis.model_validate(data)


def _fallback_analysis(text: str) -> PatentImageAnalysis:
    return PatentImageAnalysis(
        content_description=text,
        risk_flags=[
            "模型输出不是有效JSON，结构化分析可靠性较低",
            "需人工复核后再用于专利撰写或审查判断",
        ],
    )


def _build_technical_description(parsed: PatentImageAnalysis) -> str:
    if parsed.content_description:
        return parsed.content_description
    components = "、".join(parsed.components) if parsed.components else "若干待确认组件"
    relationships = "；".join(parsed.relationships) if parsed.relationships else "组件关系需进一步确认"
    return (
        f"图片可能涉及{parsed.technical_field}领域，包含{components}。"
        f"可见关系包括：{relationships}。"
    )


def _build_image_context(parsed: PatentImageAnalysis) -> Dict[str, Any]:
    visible_evidence = parsed.visible_evidence or []
    if not visible_evidence:
        visible_evidence = parsed.components + parsed.relationships
    if not visible_evidence and parsed.content_description:
        visible_evidence = [parsed.content_description]

    uncertainties = parsed.uncertainties or []
    if parsed.risk_flags:
        uncertainties = uncertainties + [
            flag for flag in parsed.risk_flags if flag not in uncertainties
        ]
    if not uncertainties:
        uncertainties = ["图片来源、使用场景和现有技术差异仍需人工确认"]

    technical_domain = parsed.technical_domain
    if technical_domain == "未知" and parsed.technical_field != "未知":
        technical_domain = parsed.technical_field

    return {
        "scene": parsed.scene_context,
        "image_type": parsed.image_type,
        "technical_domain": technical_domain,
        "visible_evidence": visible_evidence,
        "inferred_context": parsed.inferred_context,
        "uncertainties": uncertainties,
    }


def _build_patentability_note(parsed: PatentImageAnalysis) -> str:
    lines = ["潜在可保护点与待检索风险："]
    if parsed.novelty_points:
        for index, point in enumerate(parsed.novelty_points, 1):
            lines.append(f"{index}. {point}（需通过现有技术检索确认）")
    else:
        lines.append("1. 当前图片不足以直接判断新颖性，需补充现有技术检索和人工比对。")

    if parsed.risk_flags:
        lines.append("")
        lines.append("待确认事项：")
        for index, flag in enumerate(parsed.risk_flags, 1):
            lines.append(f"{index}. {flag}")

    return "\n".join(lines)
