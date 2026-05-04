from pathlib import Path

from app.services.storage_paths import public_upload_url


def test_public_upload_url_keeps_nested_relative_path():
    assert (
        public_upload_url("uploads/20260503/111438/example.png")
        == "/uploads/20260503/111438/example.png"
    )


def test_public_upload_url_handles_generated_images():
    assert public_upload_url("uploads/generated/gen_123.png") == "/uploads/generated/gen_123.png"


def test_public_upload_url_handles_absolute_upload_path():
    absolute_path = Path.cwd() / "uploads" / "20260503" / "111438" / "example.png"

    assert public_upload_url(absolute_path) == "/uploads/20260503/111438/example.png"
