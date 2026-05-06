import httpx
import pytest

from app.config import settings
from app.services.llm_service import LLMService, format_exception


def test_format_exception_uses_type_when_message_is_empty():
    assert format_exception(httpx.ReadTimeout("")) == "ReadTimeout"


def test_format_exception_keeps_message_when_present():
    assert format_exception(ValueError("bad input")) == "bad input"


class FakeImageResponse:
    def __init__(self, status_code=200, content=b"image-bytes", headers=None, text=""):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"content-type": "image/png"}
        self.text = text


class FakeAsyncClient:
    response = FakeImageResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        return self.response


class FakeJsonResponse:
    def __init__(self, data, status_code=200, text=""):
        self._data = data
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._data


class FakeDashScopeEditClient:
    posted = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None, timeout=None):
        self.__class__.posted = {
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        }
        return FakeJsonResponse({"output": {"task_id": "task-1"}})

    async def get(self, url, headers=None, timeout=None):
        return FakeJsonResponse(
            {
                "output": {
                    "task_status": "SUCCEEDED",
                    "results": [{"url": "https://example.test/result.png"}],
                }
            }
        )


class FakeOpenRouterImageClient:
    posted = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None, timeout=None):
        self.__class__.posted = {
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        }
        return FakeJsonResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "done",
                            "images": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": "data:image/png;base64,iVBORw0KGgo=",
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        )


class FakeEditPlanClient:
    posted = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None, timeout=None):
        self.__class__.posted = {
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        }
        return FakeJsonResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": '{"intent":"优化标注","allowed_edits":["增加编号"]}',
                                }
                            ]
                        }
                    }
                ]
            }
        )


@pytest.mark.asyncio
async def test_download_image_saves_valid_image(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.response = FakeImageResponse(content=b"\x89PNG\r\n")

    service = LLMService()
    local_path = await service._download_image("https://example.test/generated.png")

    assert local_path.startswith(str(tmp_path / "generated"))
    assert (tmp_path / "generated").exists()
    with open(local_path, "rb") as image_file:
        assert image_file.read() == b"\x89PNG\r\n"


@pytest.mark.asyncio
async def test_download_image_rejects_failed_response(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.response = FakeImageResponse(status_code=403, text="forbidden")

    service = LLMService()

    with pytest.raises(ValueError, match="图片下载失败"):
        await service._download_image("https://example.test/forbidden.png")


@pytest.mark.asyncio
async def test_download_image_rejects_non_image_response(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.response = FakeImageResponse(headers={"content-type": "application/json"})

    service = LLMService()

    with pytest.raises(ValueError, match="图片下载响应类型无效"):
        await service._download_image("https://example.test/error.json")


@pytest.mark.asyncio
async def test_download_image_rejects_oversized_response(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MAX_FILE_SIZE", 4)
    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.response = FakeImageResponse(content=b"12345")

    service = LLMService()

    with pytest.raises(ValueError, match="生成图片超过最大保存限制"):
        await service._download_image("https://example.test/large.png")


@pytest.mark.asyncio
async def test_dashscope_image_edit_uses_base_image_data_url(monkeypatch, tmp_path):
    image_path = tmp_path / "source.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(settings, "API_PROVIDER", "aliyun")
    monkeypatch.setattr(settings, "CUSTOM_API_KEY", "sk-valid-test-key")
    monkeypatch.setattr(settings, "CUSTOM_IMAGE_MODEL", "wanx-v1")
    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", FakeDashScopeEditClient)

    async def no_sleep(seconds):
        return None

    async def fake_download(url):
        return str(tmp_path / "edited.png")

    monkeypatch.setattr("asyncio.sleep", no_sleep)
    service = LLMService()
    monkeypatch.setattr(service, "_download_image", fake_download)

    result = await service.edit_image(str(image_path), "保持原图白底表单风格")

    payload = FakeDashScopeEditClient.posted["json"]
    assert result["success"] is True
    assert FakeDashScopeEditClient.posted["url"].endswith("/services/aigc/image2image/image-synthesis")
    assert payload["model"] == "wanx2.1-imageedit"
    assert payload["input"]["function"] == "description_edit"
    assert payload["input"]["prompt"] == "保持原图白底表单风格"
    assert payload["input"]["base_image_url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_openrouter_image_generation_uses_chat_modalities_and_saves_data_url(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "API_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-valid-test-key")
    monkeypatch.setattr(settings, "OPENROUTER_IMAGE_MODEL", "openai/gpt-5.4-image-2")
    monkeypatch.setattr(settings, "IMAGE_QUALITY", "hd")
    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", FakeOpenRouterImageClient)

    service = LLMService()
    result = await service.generate_image("生成一张专利结构示意图", size="1792x1024")

    payload = FakeOpenRouterImageClient.posted["json"]
    assert result["success"] is True
    assert result["provider"] == "openrouter"
    assert result["local_path"].startswith(str(tmp_path / "generated"))
    assert FakeOpenRouterImageClient.posted["url"].endswith("/chat/completions")
    assert payload["model"] == "openai/gpt-5.4-image-2"
    assert payload["modalities"] == ["image", "text"]
    assert payload["image_config"] == {"aspect_ratio": "16:9", "image_size": "2K"}
    with open(result["local_path"], "rb") as image_file:
        assert image_file.read() == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_openrouter_image_edit_sends_source_image_data_url(monkeypatch, tmp_path):
    image_path = tmp_path / "source.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "API_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-valid-test-key")
    monkeypatch.setattr(settings, "OPENROUTER_IMAGE_MODEL", "openai/gpt-5.4-image-2")
    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", FakeOpenRouterImageClient)

    service = LLMService()
    result = await service.edit_image(str(image_path), "保留布局，增强线条清晰度")

    content = FakeOpenRouterImageClient.posted["json"]["messages"][0]["content"]
    assert result["success"] is True
    assert content[0] == {"type": "text", "text": "保留布局，增强线条清晰度"}
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_generate_edit_plan_requests_json_object_and_flattens_content_blocks(monkeypatch):
    monkeypatch.setattr(settings, "API_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-valid-test-key")
    monkeypatch.setattr(settings, "OPENROUTER_VISION_MODEL", "openai/gpt-5.4-image-2")
    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", FakeEditPlanClient)

    service = LLMService()
    result = await service.generate_edit_plan("只输出JSON")

    payload = FakeEditPlanClient.posted["json"]
    assert result["success"] is True
    assert result["plan_text"] == '{"intent":"优化标注","allowed_edits":["增加编号"]}'
    assert payload["response_format"] == {"type": "json_object"}
