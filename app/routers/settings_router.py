"""
配置管理路由 - 提供前后端配置管理API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..config import settings
from ..services.llm_service import llm_service

router = APIRouter(prefix="/settings", tags=["settings"])
SUPPORTED_PROVIDERS = {"openai", "azure", "xiaomi_mimo", "aliyun", "zhipu", "baidu", "custom"}


class APIConfigUpdate(BaseModel):
    """API配置更新请求"""
    api_provider: Optional[str] = None
    custom_api_base: Optional[str] = None
    custom_api_key: Optional[str] = None
    custom_vision_model: Optional[str] = None
    custom_image_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    openai_vision_model: Optional[str] = None
    openai_image_model: Optional[str] = None


class UploadConfigUpdate(BaseModel):
    """上传配置更新请求"""
    max_file_size: Optional[int] = None
    allowed_extensions: Optional[list] = None
    min_resolution: Optional[list] = None
    max_resolution: Optional[list] = None


class ImageConfigUpdate(BaseModel):
    """图片生成配置更新请求"""
    image_size: Optional[str] = None
    image_quality: Optional[str] = None
    image_style: Optional[str] = None
    vision_max_tokens: Optional[int] = None
    vision_detail: Optional[str] = None


def apply_api_config(update: APIConfigUpdate) -> dict:
    data = update.model_dump(exclude_unset=True)
    provider = data.get("api_provider")
    if provider:
        provider = provider.lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=400, detail=f"不支持的API提供商: {provider}")
        settings.API_PROVIDER = provider

    field_map = {
        "custom_api_base": "CUSTOM_API_BASE",
        "custom_api_key": "CUSTOM_API_KEY",
        "custom_vision_model": "CUSTOM_VISION_MODEL",
        "custom_image_model": "CUSTOM_IMAGE_MODEL",
        "openai_api_key": "OPENAI_API_KEY",
        "openai_api_base": "OPENAI_API_BASE",
        "openai_vision_model": "OPENAI_VISION_MODEL",
        "openai_image_model": "OPENAI_IMAGE_MODEL",
    }
    for request_field, settings_field in field_map.items():
        if request_field in data and data[request_field] is not None:
            setattr(settings, settings_field, data[request_field].strip())

    llm_service.refresh_config()
    return llm_service.get_config_info()


@router.get("/current")
async def get_current_settings():
    """获取当前所有配置（前端展示用，隐藏敏感信息）"""
    def mask_key(key: str) -> str:
        if not key or key.startswith("your_"):
            return "未配置"
        return key[:8] + "****" + key[-4:] if len(key) > 12 else "****"
    
    active_key = settings.CUSTOM_API_KEY if settings.API_PROVIDER == "custom" else settings.OPENAI_API_KEY
    
    return {
        "api": {
            "provider": settings.API_PROVIDER,
            "openai_api_base": settings.OPENAI_API_BASE,
            "openai_api_key_masked": mask_key(settings.OPENAI_API_KEY),
            "openai_vision_model": settings.OPENAI_VISION_MODEL,
            "openai_image_model": settings.OPENAI_IMAGE_MODEL,
            "custom_api_base": settings.CUSTOM_API_BASE or "未配置",
            "custom_api_key_masked": mask_key(settings.CUSTOM_API_KEY),
            "custom_vision_model": settings.CUSTOM_VISION_MODEL or "使用默认",
            "custom_image_model": settings.CUSTOM_IMAGE_MODEL or "使用默认",
            "api_key_configured": bool(active_key) and not active_key.startswith("your_"),
        },
        "upload": {
            "max_file_size": settings.MAX_FILE_SIZE,
            "max_file_size_mb": round(settings.MAX_FILE_SIZE / 1024 / 1024, 1),
            "allowed_extensions": settings.ALLOWED_EXTENSIONS,
            "min_resolution": list(settings.MIN_RESOLUTION),
            "max_resolution": list(settings.MAX_RESOLUTION),
        },
        "image": {
            "image_size": settings.IMAGE_SIZE,
            "image_quality": settings.IMAGE_QUALITY,
            "image_style": settings.IMAGE_STYLE,
            "vision_max_tokens": settings.VISION_MAX_TOKENS,
            "vision_detail": settings.VISION_DETAIL,
        },
        "llm_config": llm_service.get_config_info(),
    }


@router.get("/providers")
async def get_available_providers():
    """获取支持的API提供商列表"""
    return {
        "providers": [
            {
                "id": "openai",
                "name": "OpenAI",
                "description": "OpenAI官方API",
                "default_base": "https://api.openai.com/v1",
            },
            {
                "id": "azure",
                "name": "Azure OpenAI",
                "description": "微软Azure托管的OpenAI服务",
                "default_base": "https://{resource}.openai.azure.com",
            },
            {
                "id": "xiaomi_mimo",
                "name": "小米MIMO",
                "description": "小米MIMO大模型（OpenAI兼容）",
                "default_base": "https://api.mimo.xiaomi.com/v1",
            },
            {
                "id": "aliyun",
                "name": "阿里云通义千问",
                "description": "阿里云百炼平台（OpenAI兼容模式）",
                "default_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            {
                "id": "zhipu",
                "name": "智谱AI",
                "description": "智谱GLM系列模型（OpenAI兼容）",
                "default_base": "https://open.bigmodel.cn/api/paas/v4",
            },
            {
                "id": "baidu",
                "name": "百度文心一言",
                "description": "百度千帆平台",
                "default_base": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1",
            },
            {
                "id": "custom",
                "name": "自定义",
                "description": "任何OpenAI兼容的API服务",
                "default_base": "",
            },
        ]
    }


@router.post("/api")
async def update_api_settings(update: APIConfigUpdate):
    """Update API configuration for the current running process."""
    config = apply_api_config(update)
    return {
        "success": True,
        "message": "API配置已更新（当前运行进程生效，重启后需同步.env）",
        "llm_config": config,
    }


@router.post("/test-connection")
async def test_api_connection():
    """测试当前API连接是否可用"""
    api_key = settings.CUSTOM_API_KEY or settings.OPENAI_API_KEY
    api_base = settings.CUSTOM_API_BASE or settings.OPENAI_API_BASE
    
    if not api_key:
        return {
            "success": False,
            "message": "API Key未配置，请先在设置中配置API Key",
            "provider": settings.API_PROVIDER,
        }
    
    try:
        import httpx
        # 尝试调用models接口测试连接
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{api_base}/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "API连接成功",
                    "provider": settings.API_PROVIDER,
                    "api_base": api_base,
                }
            else:
                return {
                    "success": False,
                    "message": f"API返回状态码: {response.status_code}",
                    "provider": settings.API_PROVIDER,
                }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}",
            "provider": settings.API_PROVIDER,
        }
