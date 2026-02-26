from pathlib import Path

from app.core.config import settings


def save_user_file(user_id: str, document_id: str, original_name: str, content: bytes) -> str:
    base_dir = Path(settings.local_upload_dir)
    user_dir = base_dir / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    safe_name = original_name.replace("\\", "_").replace("/", "_")
    file_path = user_dir / f"{document_id}_{safe_name}"
    file_path.write_bytes(content)
    return str(file_path)
