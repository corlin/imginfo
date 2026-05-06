"""LLM API服务层 - 支持OpenAI兼容API（小米MIMO、Azure、通义千问等）"""
import base64
import httpx
import json
import logging
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger(__name__)

# API提供商预设配置
API_PROVIDER_PRESETS = {
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "vision_model": "gpt-4o",
        "image_model": "dall-e-3",
    },
    "openrouter": {
        "api_base": "https://openrouter.ai/api/v1",
        "vision_model": "openai/gpt-5.4-image-2",
        "image_model": "openai/gpt-5.4-image-2",
    },
    "xiaomi_mimo": {
        "api_base": "https://api.xiaomimimo.com/v1",
        "vision_model": "MiMo-VL-7B",
        "image_model": "stable-diffusion-3",
    },
    "azure": {
        "api_base": "",  # 用户需配置自定义endpoint
        "vision_model": "gpt-4o",
        "image_model": "dall-e-3",
    },
    "aliyun": {
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "vision_model": "qwen-vl-max",
        "image_model": "wanx-v1",
    },
    "zhipu": {
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "vision_model": "glm-4v",
        "image_model": "cogview-3",
    },
}


def format_exception(error: Exception) -> str:
    message = str(error).strip()
    return message or error.__class__.__name__


def _truncate_prompt(prompt: str, max_chars: int) -> str:
    text = prompt.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


class LLMService:
    """支持OpenAI兼容API的LLM服务类"""

    def __init__(self):
        self._resolve_api_config()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _resolve_api_config(self):
        """根据API_PROVIDER解析实际的API配置"""
        provider = settings.API_PROVIDER.lower()
        preset = API_PROVIDER_PRESETS.get(provider, {})

        if provider == "openai":
            self.api_base = settings.OPENAI_API_BASE.rstrip("/")
        elif provider == "openrouter":
            self.api_base = settings.OPENROUTER_API_BASE.rstrip("/")
        elif settings.CUSTOM_API_BASE:
            self.api_base = settings.CUSTOM_API_BASE.rstrip("/")
        elif provider in API_PROVIDER_PRESETS and preset.get("api_base"):
            self.api_base = preset["api_base"]
        else:
            self.api_base = settings.OPENAI_API_BASE.rstrip("/")

        if provider == "openai":
            self.api_key = settings.OPENAI_API_KEY
        elif provider == "openrouter":
            self.api_key = settings.OPENROUTER_API_KEY
        else:
            self.api_key = settings.CUSTOM_API_KEY or settings.OPENAI_API_KEY

        if provider == "openai":
            self.vision_model = settings.OPENAI_VISION_MODEL
        elif provider == "openrouter":
            self.vision_model = settings.OPENROUTER_VISION_MODEL
        elif settings.CUSTOM_VISION_MODEL:
            self.vision_model = settings.CUSTOM_VISION_MODEL
        elif provider in API_PROVIDER_PRESETS and preset.get("vision_model"):
            self.vision_model = preset["vision_model"]
        else:
            self.vision_model = settings.OPENAI_VISION_MODEL

        if provider == "openai":
            self.image_model = settings.OPENAI_IMAGE_MODEL
        elif provider == "openrouter":
            self.image_model = settings.OPENROUTER_IMAGE_MODEL
        elif settings.CUSTOM_IMAGE_MODEL:
            self.image_model = settings.CUSTOM_IMAGE_MODEL
        elif provider in API_PROVIDER_PRESETS and preset.get("image_model"):
            self.image_model = preset["image_model"]
        else:
            self.image_model = settings.OPENAI_IMAGE_MODEL

        logger.info(f"LLM Service initialized: provider={provider}, "
                     f"api_base={self.api_base}, vision_model={self.vision_model}, "
                     f"image_model={self.image_model}")

    def _has_valid_api_key(self) -> bool:
        return bool(self.api_key) and not self.api_key.startswith("your_")

    def refresh_config(self) -> None:
        """Refresh runtime settings after the settings API updates values."""
        self._resolve_api_config()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _image_to_base64(self, image_path: str) -> str:
        """将图片转换为base64编码"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _get_mime_type(self, image_path: str) -> str:
        """根据文件扩展名获取MIME类型"""
        ext = Path(image_path).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
        }
        return mime_map.get(ext, "image/png")

    async def analyze_image(self, image_path: str, prompt: Optional[str] = None) -> dict:
        """
        使用Vision API分析图片（OpenAI兼容格式）

        Args:
            image_path: 图片文件路径
            prompt: 自定义分析提示词

        Returns:
            包含分析结果的字典
        """
        if not self._has_valid_api_key():
            return self._mock_analysis()

        try:
            base64_image = self._image_to_base64(image_path)
            mime_type = self._get_mime_type(image_path)

            if not prompt:
                prompt = """请从专利申请的角度分析这张图片，包括：
                1. 图片类型（技术图纸、流程图、结构图、照片等）
                2. 主要内容描述
                3. 技术特征识别
                4. 关键元素提取
                5. 专利撰写建议

                请以JSON格式输出分析结果。"""

            # OpenAI兼容的Vision API请求格式
            payload = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}",
                                    "detail": settings.VISION_DETAIL
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": settings.VISION_MAX_TOKENS
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=120.0
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    return {
                        "success": True,
                        "analysis": content,
                        "model": self.vision_model,
                        "provider": settings.API_PROVIDER
                    }
                else:
                    error_text = response.text
                    logger.error(f"Vision API error: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"API调用失败({response.status_code}): {error_text[:200]}"
                    }

        except httpx.ConnectError as e:
            logger.error(f"Vision API connection failed: {format_exception(e)}")
            return {
                "success": False,
                "error": f"API连接失败，请检查API地址是否正确: {self.api_base}"
            }
        except Exception as e:
            logger.error(f"Image analysis failed: {format_exception(e)}")
            return {
                "success": False,
                "error": format_exception(e)
            }

    async def generate_edit_plan(self, prompt: str, image_path: Optional[str] = None) -> dict:
        """Ask the active vision/chat model to produce an edit plan without generating an image."""
        if not self._has_valid_api_key():
            return {
                "success": False,
                "error": "API Key未配置，无法生成AI编辑计划",
            }

        try:
            content = [{"type": "text", "text": prompt}]
            if image_path:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": self._image_to_data_url(image_path),
                            "detail": settings.VISION_DETAIL,
                        },
                    }
                )

            payload = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
                "max_tokens": min(settings.VISION_MAX_TOKENS, 1800),
                "response_format": {"type": "json_object"},
                "stream": False,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=120.0,
                )

            if response.status_code != 200:
                error_text = response.text
                logger.error("AI edit plan error: %s - %s", response.status_code, error_text)
                return {
                    "success": False,
                    "error": f"AI编辑计划调用失败({response.status_code}): {error_text[:200]}",
                }

            result = response.json()
            content_text = self._message_content_to_text(result["choices"][0]["message"].get("content", ""))
            return {
                "success": True,
                "plan_text": content_text,
                "model": self.vision_model,
                "provider": settings.API_PROVIDER,
            }
        except Exception as e:
            logger.error("AI edit plan failed: %s", format_exception(e))
            return {
                "success": False,
                "error": f"AI编辑计划异常: {format_exception(e)}",
            }

    def _message_content_to_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif isinstance(item.get("content"), str):
                        parts.append(item["content"])
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        return str(content or "")

    async def generate_image(self, prompt: str, style: Optional[str] = None, size: Optional[str] = None) -> dict:
        """
        使用文生图API生成图片（OpenAI兼容格式）

        Args:
            prompt: 图片生成提示词
            style: 图片风格（natural/vivid）
            size: 图片尺寸

        Returns:
            包含生成图片URL的字典
        """
        if not self._has_valid_api_key():
            return self._mock_generation()

        # 检查是否为不支持文生图的API提供商
        provider = settings.API_PROVIDER.lower()
        if provider in ["xiaomi_mimo", "custom"] and "mimo" in self.image_model.lower():
            return await self._generate_image_mimo(prompt, size)

        # 阿里云DashScope wanx模型使用原生异步API
        if provider == "aliyun" and "wanx" in self.image_model.lower():
            return await self._generate_image_dashscope(prompt, size)

        if provider == "openrouter":
            return await self._generate_image_openrouter(prompt, size)

        try:
            # OpenAI兼容的图片生成API请求格式
            payload = {
                "model": self.image_model,
                "prompt": prompt,
                "size": size or settings.IMAGE_SIZE,
                "n": 1,
                "response_format": "url"
            }

            # 仅OpenAI原生支持quality和style参数
            if provider == "openai":
                payload["quality"] = settings.IMAGE_QUALITY
                payload["style"] = style or settings.IMAGE_STYLE

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/images/generations",
                    headers=self.headers,
                    json=payload,
                    timeout=180.0
                )

                if response.status_code == 200:
                    result = response.json()
                    image_url = result["data"][0]["url"]

                    # 下载图片到本地
                    local_path = await self._download_image(image_url)

                    return {
                        "success": True,
                        "image_url": image_url,
                        "local_path": local_path,
                        "prompt": prompt,
                        "model": self.image_model,
                        "provider": provider
                    }
                else:
                    error_text = response.text
                    logger.error(f"Image generation error: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"API调用失败({response.status_code}): {error_text[:200]}"
                    }

        except httpx.ConnectError as e:
            logger.error(f"Image generation connection failed: {format_exception(e)}")
            return {
                "success": False,
                "error": f"API连接失败，请检查API地址是否正确: {self.api_base}"
            }
        except Exception as e:
            logger.error(f"Image generation failed: {format_exception(e)}")
            return {
                "success": False,
                "error": format_exception(e)
            }

    async def edit_image(self, image_path: str, prompt: str, size: Optional[str] = None) -> dict:
        """
        使用支持图生图的模型编辑原图。

        当前优先支持阿里云 DashScope Wan image editing HTTP API。
        """
        if not self._has_valid_api_key():
            return self._mock_generation()

        provider = settings.API_PROVIDER.lower()
        if provider == "aliyun":
            return await self._edit_image_dashscope(image_path, prompt)

        if provider == "openrouter":
            return await self._edit_image_openrouter(image_path, prompt, size)

        return {
            "success": False,
            "error": f"当前提供商 {provider} 尚未接入图生图编辑接口"
        }

    def _openrouter_image_config(self, size: Optional[str] = None) -> dict:
        image_size = size or settings.IMAGE_SIZE
        config = {}

        if image_size in {"0.5K", "1K", "2K", "4K"}:
            config["image_size"] = image_size
            return config

        if "x" in image_size:
            try:
                width, height = [int(part) for part in image_size.lower().split("x", 1)]
            except ValueError:
                return config

            size_map = {
                (256, 256): "1:1",
                (512, 512): "1:1",
                (1024, 1024): "1:1",
                (1024, 1792): "9:16",
                (1792, 1024): "16:9",
            }
            ratio_map = {
                (1, 1): "1:1",
                (2, 3): "2:3",
                (3, 2): "3:2",
                (3, 4): "3:4",
                (4, 3): "4:3",
                (4, 5): "4:5",
                (5, 4): "5:4",
                (9, 16): "9:16",
                (16, 9): "16:9",
                (21, 9): "21:9",
            }
            from math import gcd

            divisor = gcd(width, height)
            ratio = (width // divisor, height // divisor)
            config["aspect_ratio"] = size_map.get((width, height)) or ratio_map.get(ratio, f"{ratio[0]}:{ratio[1]}")
            config["image_size"] = "2K" if settings.IMAGE_QUALITY == "hd" else "1K"

        return config

    async def _generate_image_openrouter(self, prompt: str, size: Optional[str] = None) -> dict:
        """Generate images through OpenRouter chat completions image-output models."""
        try:
            payload = {
                "model": self.image_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "modalities": ["image", "text"],
                "stream": False,
            }
            image_config = self._openrouter_image_config(size)
            if image_config:
                payload["image_config"] = image_config

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=180.0,
                )

            if response.status_code != 200:
                error_text = response.text
                logger.error("OpenRouter image generation error: %s - %s", response.status_code, error_text)
                return {
                    "success": False,
                    "error": f"OpenRouter调用失败({response.status_code}): {error_text[:200]}",
                }

            result = response.json()
            message = result.get("choices", [{}])[0].get("message", {})
            image_url = self._extract_openrouter_image_url(message)
            if not image_url:
                return {
                    "success": False,
                    "error": f"OpenRouter未返回图片。请确认模型支持image输出，并使用了图片生成模型。响应: {json.dumps(result)[:300]}",
                    "provider": "openrouter",
                }

            local_path = await self._store_generated_image_url(image_url)
            return {
                "success": True,
                "image_url": image_url,
                "local_path": local_path,
                "prompt": prompt,
                "model": self.image_model,
                "provider": "openrouter",
            }

        except httpx.ConnectError as e:
            logger.error("OpenRouter image generation connection failed: %s", format_exception(e))
            return {
                "success": False,
                "error": f"OpenRouter连接失败，请检查API地址是否正确: {self.api_base}",
            }
        except Exception as e:
            logger.error("OpenRouter image generation failed: %s", format_exception(e))
            return {
                "success": False,
                "error": f"OpenRouter文生图异常: {format_exception(e)}",
            }

    async def _edit_image_openrouter(self, image_path: str, prompt: str, size: Optional[str] = None) -> dict:
        """Edit images through OpenRouter image-output chat models."""
        try:
            payload = {
                "model": self.image_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": self._image_to_data_url(image_path),
                                },
                            },
                        ],
                    }
                ],
                "modalities": ["image", "text"],
                "stream": False,
            }
            image_config = self._openrouter_image_config(size)
            if image_config:
                payload["image_config"] = image_config

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=180.0,
                )

            if response.status_code != 200:
                error_text = response.text
                return {
                    "success": False,
                    "error": f"OpenRouter图生图调用失败({response.status_code}): {error_text[:200]}",
                }

            result = response.json()
            message = result.get("choices", [{}])[0].get("message", {})
            image_url = self._extract_openrouter_image_url(message)
            if not image_url:
                return {
                    "success": False,
                    "error": f"OpenRouter未返回编辑图片。响应: {json.dumps(result)[:300]}",
                    "provider": "openrouter",
                }

            local_path = await self._store_generated_image_url(image_url)
            return {
                "success": True,
                "image_url": image_url,
                "local_path": local_path,
                "prompt": prompt,
                "model": self.image_model,
                "provider": "openrouter",
            }
        except Exception as e:
            logger.error("OpenRouter image edit failed: %s", format_exception(e))
            return {
                "success": False,
                "error": f"OpenRouter图生图异常: {format_exception(e)}",
            }

    def _extract_openrouter_image_url(self, message: dict) -> Optional[str]:
        images = message.get("images") or []
        for image in images:
            image_url = image.get("image_url") or image.get("imageUrl") or {}
            url = image_url.get("url")
            if url:
                return url
        return None

    async def _generate_image_mimo(self, prompt: str, size: Optional[str] = None) -> dict:
        """
        使用小米MIMO API生成图片
        MIMO API使用chat/completions端点，通过特殊prompt生成图片
        """
        try:
            # MIMO文生图使用聊天接口
            payload = {
                "model": self.image_model,
                "messages": [
                    {
                        "role": "user",
                        "content": f"请生成一张图片：{prompt}"
                    }
                ],
                "max_tokens": 4096,
                "stream": False
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=180.0
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # 检查响应中是否包含图片URL
                    import re
                    url_pattern = r'https?://[^\s\)\"]+\.(?:png|jpg|jpeg|gif|webp)'
                    urls = re.findall(url_pattern, content)
                    
                    if urls:
                        image_url = urls[0]
                        local_path = await self._download_image(image_url)
                        return {
                            "success": True,
                            "image_url": image_url,
                            "local_path": local_path,
                            "prompt": prompt,
                            "model": self.image_model,
                            "provider": "xiaomi_mimo"
                        }
                    else:
                        # MIMO可能返回文本描述而不是图片URL
                        return {
                            "success": False,
                            "error": f"MIMO API返回了文本描述而非图片URL。API可能不支持文生图功能。响应内容: {content[:300]}",
                            "provider": "xiaomi_mimo"
                        }
                else:
                    error_text = response.text
                    logger.error(f"MIMO Image generation error: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"API调用失败({response.status_code}): {error_text[:200]}"
                    }

        except Exception as e:
            logger.error(f"MIMO Image generation failed: {format_exception(e)}")
            return {
                "success": False,
                "error": f"小米MIMO文生图失败: {format_exception(e)}"
            }

    async def _generate_image_dashscope(self, prompt: str, size: Optional[str] = None) -> dict:
        """
        使用阿里云DashScope原生API生成图片（wanx-v1等模型）
        DashScope文生图使用异步任务接口：
        1. 提交任务 -> POST /api/v1/services/aigc/text2image/image-synthesis
        2. 轮询任务状态 -> GET /api/v1/tasks/{task_id}
        """
        import asyncio

        try:
            # 解析尺寸
            img_size = size or settings.IMAGE_SIZE
            # 将 "1024x1024" 格式转为 DashScope 需要的格式
            if "x" in img_size:
                parts = img_size.split("x")
                width, height = int(parts[0]), int(parts[1])
            else:
                width, height = 1024, 1024

            # 提交文生图任务
            dashscope_base = "https://dashscope.aliyuncs.com/api/v1"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable"
            }

            payload = {
                "model": self.image_model,
                "input": {
                    "prompt": prompt,
                },
                "parameters": {
                    "size": f"{width}*{height}",
                    "n": 1
                }
            }

            async with httpx.AsyncClient() as client:
                # 1. 提交任务
                logger.info(f"DashScope文生图: 提交任务 model={self.image_model}, prompt={prompt[:50]}...")
                response = await client.post(
                    f"{dashscope_base}/services/aigc/text2image/image-synthesis",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"DashScope文生图任务提交失败: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"DashScope任务提交失败({response.status_code}): {error_text[:200]}"
                    }

                task_result = response.json()
                task_id = task_result.get("output", {}).get("task_id")
                if not task_id:
                    logger.error(f"DashScope返回结果中没有task_id: {task_result}")
                    return {
                        "success": False,
                        "error": f"DashScope任务提交成功但未返回task_id: {json.dumps(task_result)[:200]}"
                    }

                logger.info(f"DashScope文生图任务已提交, task_id={task_id}")

                # 2. 轮询任务状态
                poll_headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                max_retries = 60  # 最多等待60次，每次间隔3秒
                for i in range(max_retries):
                    await asyncio.sleep(3)
                    try:
                        poll_response = await client.get(
                            f"{dashscope_base}/tasks/{task_id}",
                            headers=poll_headers,
                            timeout=30.0
                        )
                    except httpx.TimeoutException as e:
                        logger.warning("DashScope任务轮询超时，继续重试: %s", format_exception(e))
                        continue

                    if poll_response.status_code != 200:
                        logger.warning(f"DashScope任务轮询失败: {poll_response.status_code}")
                        continue

                    poll_result = poll_response.json()
                    task_status = poll_result.get("output", {}).get("task_status", "")

                    if task_status == "SUCCEEDED":
                        # 任务成功，获取图片URL
                        results = poll_result.get("output", {}).get("results", [])
                        if results and results[0].get("url"):
                            image_url = results[0]["url"]
                            local_path = await self._download_image(image_url)
                            logger.info(f"DashScope文生图成功: {local_path}")
                            return {
                                "success": True,
                                "image_url": image_url,
                                "local_path": local_path,
                                "prompt": prompt,
                                "model": self.image_model,
                                "provider": "aliyun_dashscope"
                            }
                        else:
                            return {
                                "success": False,
                                "error": f"DashScope任务成功但未返回图片URL: {json.dumps(poll_result)[:300]}"
                            }

                    elif task_status == "FAILED":
                        error_msg = poll_result.get("output", {}).get("message", "未知错误")
                        logger.error(f"DashScope文生图任务失败: {error_msg}")
                        return {
                            "success": False,
                            "error": f"DashScope文生图任务失败: {error_msg}"
                        }

                    elif task_status in ["PENDING", "RUNNING"]:
                        logger.debug(f"DashScope任务进行中: {task_status}, 已等待{(i+1)*3}秒")
                        continue

                    else:
                        logger.warning(f"DashScope未知任务状态: {task_status}")
                        continue

                # 超时
                return {
                    "success": False,
                    "error": f"DashScope文生图任务超时（已等待{max_retries * 3}秒）, task_id={task_id}"
                }

        except httpx.ConnectError as e:
            logger.error(f"DashScope文生图连接失败: {format_exception(e)}")
            return {
                "success": False,
                "error": f"DashScope API连接失败: {format_exception(e)}"
            }
        except Exception as e:
            logger.error(f"DashScope文生图失败: {format_exception(e)}")
            return {
                "success": False,
                "error": f"DashScope文生图异常: {format_exception(e)}"
            }

    async def _edit_image_dashscope(self, image_path: str, prompt: str) -> dict:
        """
        使用阿里云 DashScope 通用图像编辑 API。
        """
        import asyncio

        try:
            dashscope_base = "https://dashscope.aliyuncs.com/api/v1"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            }
            image_model = self.image_model if "imageedit" in self.image_model.lower() else "wanx2.1-imageedit"
            payload = {
                "model": image_model,
                "input": {
                    "function": "description_edit",
                    "prompt": _truncate_prompt(prompt, 800),
                    "base_image_url": self._image_to_data_url(image_path),
                },
                "parameters": {
                    "n": 1
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{dashscope_base}/services/aigc/image2image/image-synthesis",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.error("DashScope图生图任务提交失败: %s - %s", response.status_code, error_text)
                    return {
                        "success": False,
                        "error": f"DashScope图生图任务提交失败({response.status_code}): {error_text[:200]}"
                    }

                task_result = response.json()
                task_id = task_result.get("output", {}).get("task_id")
                if not task_id:
                    return {
                        "success": False,
                        "error": f"DashScope图生图任务提交成功但未返回task_id: {json.dumps(task_result)[:200]}"
                    }

                poll_headers = {"Authorization": f"Bearer {self.api_key}"}
                max_retries = 60
                for i in range(max_retries):
                    await asyncio.sleep(3)
                    try:
                        poll_response = await client.get(
                            f"{dashscope_base}/tasks/{task_id}",
                            headers=poll_headers,
                            timeout=30.0,
                        )
                    except httpx.TimeoutException as e:
                        logger.warning("DashScope图生图任务轮询超时，继续重试: %s", format_exception(e))
                        continue

                    if poll_response.status_code != 200:
                        logger.warning("DashScope图生图任务轮询失败: %s", poll_response.status_code)
                        continue

                    poll_result = poll_response.json()
                    task_status = poll_result.get("output", {}).get("task_status", "")

                    if task_status == "SUCCEEDED":
                        results = poll_result.get("output", {}).get("results", [])
                        if results and results[0].get("url"):
                            image_url = results[0]["url"]
                            local_path = await self._download_image(image_url)
                            return {
                                "success": True,
                                "image_url": image_url,
                                "local_path": local_path,
                                "prompt": prompt,
                                "model": image_model,
                                "provider": "aliyun_dashscope_imageedit"
                            }
                        return {
                            "success": False,
                            "error": f"DashScope图生图任务成功但未返回图片URL: {json.dumps(poll_result)[:300]}"
                        }

                    if task_status == "FAILED":
                        error_msg = poll_result.get("output", {}).get("message", "未知错误")
                        return {
                            "success": False,
                            "error": f"DashScope图生图任务失败: {error_msg}"
                        }

                    if task_status in ["PENDING", "RUNNING"]:
                        logger.debug("DashScope图生图任务进行中: %s, 已等待%s秒", task_status, (i + 1) * 3)
                        continue

                return {
                    "success": False,
                    "error": f"DashScope图生图任务超时（已等待{max_retries * 3}秒）, task_id={task_id}"
                }

        except httpx.ConnectError as e:
            logger.error("DashScope图生图连接失败: %s", format_exception(e))
            return {
                "success": False,
                "error": f"DashScope图生图API连接失败: {format_exception(e)}"
            }
        except Exception as e:
            logger.error("DashScope图生图失败: %s", format_exception(e))
            return {
                "success": False,
                "error": f"DashScope图生图异常: {format_exception(e)}"
            }

    def _image_to_data_url(self, image_path: str) -> str:
        mime_type = self._get_mime_type(image_path)
        return f"data:{mime_type};base64,{self._image_to_base64(image_path)}"

    async def _store_generated_image_url(self, image_url: str) -> str:
        if image_url.startswith("data:image/"):
            return self._save_data_url_image(image_url)
        parsed = urlparse(image_url)
        if parsed.scheme in {"http", "https"}:
            return await self._download_image(image_url)
        raise ValueError("图片URL格式无效")

    def _save_data_url_image(self, data_url: str) -> str:
        import uuid

        header, separator, encoded = data_url.partition(",")
        if not separator or ";base64" not in header:
            raise ValueError("图片data URL格式无效")

        mime_type = header.removeprefix("data:").split(";", 1)[0].lower()
        extension_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        extension = extension_map.get(mime_type, ".png")
        content = base64.b64decode(encoded, validate=True)
        if len(content) > settings.MAX_FILE_SIZE:
            raise ValueError(f"生成图片超过最大保存限制: {len(content)} 字节")

        generated_dir = Path(settings.UPLOAD_DIR) / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        local_path = generated_dir / f"gen_{uuid.uuid4().hex[:12]}{extension}"
        with open(local_path, "wb") as f:
            f.write(content)
        return str(local_path)

    async def _download_image(self, url: str) -> str:
        """下载远程图片到本地"""
        import uuid

        generated_dir = Path(settings.UPLOAD_DIR) / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        filename = f"gen_{uuid.uuid4().hex[:12]}.png"
        local_path = generated_dir / filename

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code >= 400:
                raise ValueError(f"图片下载失败({response.status_code}): {response.text[:200]}")

            content_type = response.headers.get("content-type", "").split(";")[0].lower()
            if content_type and not content_type.startswith("image/"):
                raise ValueError(f"图片下载响应类型无效: {content_type}")

            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = 0
                if declared_size > settings.MAX_FILE_SIZE:
                    raise ValueError(f"生成图片超过最大保存限制: {content_length} 字节")

            if len(response.content) > settings.MAX_FILE_SIZE:
                raise ValueError(f"生成图片超过最大保存限制: {len(response.content)} 字节")

            with open(local_path, "wb") as f:
                f.write(response.content)

        return str(local_path)

    def get_config_info(self) -> dict:
        """返回当前API配置信息（用于前端展示，隐藏敏感信息）"""
        masked_key = ""
        is_configured = self._has_valid_api_key()
        if is_configured:
            masked_key = self.api_key[:8] + "****" + self.api_key[-4:] if len(self.api_key) > 12 else "****"

        return {
            "provider": settings.API_PROVIDER,
            "api_base": self.api_base,
            "vision_model": self.vision_model,
            "image_model": self.image_model,
            "api_key_configured": is_configured,
            "api_key_preview": masked_key,
        }

    def _mock_analysis(self) -> dict:
        """模拟分析结果（当API未配置时）"""
        return {
            "success": True,
            "analysis": {
                "image_type": "技术图纸",
                "main_content": "这是一张展示机械结构的技术图纸",
                "technical_features": [
                    "包含多个机械部件的连接关系",
                    "标注了详细的尺寸参数",
                    "展示了内部结构的剖视图"
                ],
                "key_elements": ["主体框架", "连接部件", "固定螺栓", "密封圈"],
                "patent_suggestions": "建议从结构创新和连接方式的角度撰写专利申请"
            },
            "model": "mock",
            "provider": "mock"
        }

    def _mock_generation(self) -> dict:
        """模拟生成结果（当API未配置时）"""
        return {
            "success": True,
            "image_url": "https://via.placeholder.com/1024",
            "local_path": None,
            "prompt": "mock",
            "model": "mock",
            "provider": "mock"
        }


# 创建全局服务实例
llm_service = LLMService()
