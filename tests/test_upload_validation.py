from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image as PILImage
from starlette.datastructures import Headers

from app.routers import upload


def make_upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


def make_png(width: int = 120, height: int = 120) -> bytes:
    buffer = BytesIO()
    PILImage.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_validate_image_rejects_non_image_content_type():
    file = make_upload("sample.png", b"not used", "text/plain")

    with pytest.raises(HTTPException) as exc_info:
        upload.validate_image(file)

    assert exc_info.value.status_code == 400
    assert "内容类型" in exc_info.value.detail


def test_validate_image_content_accepts_real_image(tmp_path):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(make_png())

    assert upload.validate_image_content(str(image_path)) == (120, 120)


def test_update_file_index_recovers_from_corrupted_json(tmp_path, monkeypatch):
    monkeypatch.setattr(upload.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(upload.settings, "INDEX_FILE", "file_index.json")
    index_path = tmp_path / "file_index.json"
    index_path.write_text("{bad json", encoding="utf-8")

    upload.update_file_index({"id": 1, "filename": "sample.png"})

    assert '"filename": "sample.png"' in index_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_store_validated_upload_cleans_invalid_image_file(tmp_path, monkeypatch):
    target_path = tmp_path / "invalid.png"
    file = make_upload("invalid.png", b"not an image", "image/png")

    class FakeDB:
        def add(self, _record):
            pass

        def commit(self):
            pass

        def refresh(self, _record):
            pass

    monkeypatch.setattr(
        upload,
        "generate_storage_path",
        lambda _filename: (str(target_path), "invalid.png"),
    )

    with pytest.raises(HTTPException):
        await upload.store_validated_upload(file, FakeDB())

    assert not target_path.exists()
