import os
from typing import List, Tuple
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 项目信息
    PROJECT_NAME: str = "图片信息解析系统"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "基于视觉模型的图片解析与文生图系统，专注于专利角度分析"
    API_V1_STR: str = "/api/v1"
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./imginfo.db"
    
    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "bmp", "gif", "tiff", "webp"]
    MIN_RESOLUTION: Tuple[int, int] = (100, 100)
    MAX_RESOLUTION: Tuple[int, int] = (8192, 8192)
    
    # 文件索引
    INDEX_FILE: str = "file_index.json"
    
    # AI模型配置 - 支持OpenAI兼容API
    VISION_MODEL: str = "gpt-4-vision-preview"
    GENERATION_MODEL: str = "dall-e-3"
    
    # OpenAI兼容API配置
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_VISION_MODEL: str = "gpt-4-vision-preview"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
    
    # 第三方API提供商配置（OpenAI兼容）
    # 支持小米MIMO、Azure OpenAI、阿里云通义千问、百度文心一言等
    API_PROVIDER: str = "openai"  # openai, azure, xiaomi_mimo, aliyun, baidu, custom
    CUSTOM_API_BASE: str = ""
    CUSTOM_API_KEY: str = ""
    CUSTOM_VISION_MODEL: str = ""
    CUSTOM_IMAGE_MODEL: str = ""
    
    # 图片分析配置
    VISION_MAX_TOKENS: int = 4096
    VISION_DETAIL: str = "high"  # low, high, auto
    
    # 文生图配置
    IMAGE_SIZE: str = "1024x1024"  # 256x256, 512x512, 1024x1024
    IMAGE_QUALITY: str = "standard"  # standard, hd
    IMAGE_STYLE: str = "natural"  # natural, vivid
    
    model_config = ConfigDict(env_file=".env", case_sensitive=True)


# 创建全局设置实例
settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
