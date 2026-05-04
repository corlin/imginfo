"""Helpers for exposing stored files through FastAPI static mounts."""
from pathlib import Path

from app.config import settings


def public_upload_url(file_path: str | Path) -> str:
    upload_root = Path(settings.UPLOAD_DIR)
    path = Path(file_path)

    for root in (upload_root, upload_root.resolve()):
        try:
            relative_path = path.relative_to(root)
            break
        except ValueError:
            continue
    else:
        relative_path = path.name

    return f"/uploads/{relative_path.as_posix()}"
