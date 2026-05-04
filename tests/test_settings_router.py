import pytest
from fastapi import HTTPException

from app.config import settings
from app.routers.settings_router import APIConfigUpdate, apply_api_config
from app.services.llm_service import llm_service


def test_apply_api_config_updates_runtime_custom_provider():
    previous = {
        "API_PROVIDER": settings.API_PROVIDER,
        "CUSTOM_API_BASE": settings.CUSTOM_API_BASE,
        "CUSTOM_API_KEY": settings.CUSTOM_API_KEY,
        "CUSTOM_VISION_MODEL": settings.CUSTOM_VISION_MODEL,
        "CUSTOM_IMAGE_MODEL": settings.CUSTOM_IMAGE_MODEL,
    }
    try:
        config = apply_api_config(
            APIConfigUpdate(
                api_provider="custom",
                custom_api_base="https://example.test/v1",
                custom_api_key="test-key",
                custom_vision_model="vision-test",
                custom_image_model="image-test",
            )
        )

        assert settings.API_PROVIDER == "custom"
        assert settings.CUSTOM_API_BASE == "https://example.test/v1"
        assert config["api_base"] == "https://example.test/v1"
        assert config["vision_model"] == "vision-test"
        assert config["image_model"] == "image-test"
        assert config["api_key_configured"] is True
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)
        llm_service.refresh_config()


def test_apply_api_config_rejects_unknown_provider():
    with pytest.raises(HTTPException) as exc_info:
        apply_api_config(APIConfigUpdate(api_provider="unknown"))

    assert exc_info.value.status_code == 400


def test_openai_provider_ignores_stale_custom_base():
    previous = {
        "API_PROVIDER": settings.API_PROVIDER,
        "OPENAI_API_BASE": settings.OPENAI_API_BASE,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        "CUSTOM_API_BASE": settings.CUSTOM_API_BASE,
        "CUSTOM_API_KEY": settings.CUSTOM_API_KEY,
    }
    try:
        settings.CUSTOM_API_BASE = "https://stale-custom.test/v1"
        settings.CUSTOM_API_KEY = "stale-custom-key"
        config = apply_api_config(
            APIConfigUpdate(
                api_provider="openai",
                openai_api_base="https://api.openai.com/v1",
                openai_api_key="openai-key",
            )
        )

        assert config["provider"] == "openai"
        assert config["api_base"] == "https://api.openai.com/v1"
        assert config["api_key_configured"] is True
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)
        llm_service.refresh_config()


def test_placeholder_api_key_is_not_configured():
    previous = {
        "API_PROVIDER": settings.API_PROVIDER,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
    }
    try:
        settings.API_PROVIDER = "openai"
        settings.OPENAI_API_KEY = "your_openai_api_key_here"
        llm_service.refresh_config()

        assert llm_service.get_config_info()["api_key_configured"] is False
        assert llm_service._has_valid_api_key() is False
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)
        llm_service.refresh_config()
