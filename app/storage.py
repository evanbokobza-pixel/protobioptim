from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import UploadFile
from fastapi.responses import FileResponse, Response
from supabase import Client, create_client

from app.config import settings


ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class StoredFilePayload:
    provider: str
    bucket: str | None
    path: str
    mime_type: str | None
    size_bytes: int
    original_name: str


class StorageError(Exception):
    pass


def _validate_upload(upload: UploadFile, max_upload_size_bytes: int) -> tuple[str, bytes]:
    original_name = Path(upload.filename or "document").name
    extension = Path(original_name).suffix.lower()
    mime_type = (upload.content_type or "").lower()
    content = upload.file.read(max_upload_size_bytes + 1)

    if len(content) > max_upload_size_bytes:
        raise StorageError(f"Le fichier {original_name} depasse la taille autorisee.")
    if not content:
        raise StorageError(f"Le fichier {original_name} est vide.")
    if extension not in ALLOWED_EXTENSIONS:
        raise StorageError(f"Le format du fichier {original_name} n'est pas accepte.")
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        raise StorageError(f"Le type de fichier {original_name} n'est pas accepte.")

    return original_name, content


def _build_download_headers(filename: str) -> dict[str, str]:
    quoted_name = quote(filename)
    return {
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quoted_name}",
    }


class LocalStorageBackend:
    provider = "local"

    def __init__(self, root: Path, max_upload_size_bytes: int):
        self.root = root
        self.max_upload_size_bytes = max_upload_size_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def upload_case_file(self, case_request_id: int, upload: UploadFile) -> StoredFilePayload:
        original_name, content = _validate_upload(upload, self.max_upload_size_bytes)
        extension = Path(original_name).suffix.lower()
        relative_path = Path("case-files") / str(case_request_id) / f"{uuid4().hex}{extension}"
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

        return StoredFilePayload(
            provider=self.provider,
            bucket=None,
            path=str(relative_path).replace("\\", "/"),
            mime_type=upload.content_type or "application/octet-stream",
            size_bytes=len(content),
            original_name=original_name,
        )

    def download_response(self, file_record) -> Response:
        target = self.root / file_record.storage_path
        if not target.exists():
            raise StorageError("Le fichier demande n'est plus disponible.")
        return FileResponse(
            path=target,
            media_type=file_record.mime_type or "application/octet-stream",
            filename=file_record.original_name,
            headers=_build_download_headers(file_record.original_name),
        )


class SupabaseStorageBackend:
    provider = "supabase"

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        bucket_name: str,
        max_upload_size_bytes: int,
        signed_url_ttl_seconds: int,
    ):
        self.client: Client = create_client(supabase_url, service_role_key)
        self.bucket_name = bucket_name
        self.max_upload_size_bytes = max_upload_size_bytes
        self.signed_url_ttl_seconds = signed_url_ttl_seconds

    def ensure_ready(self) -> None:
        try:
            self.client.storage.get_bucket(self.bucket_name)
        except Exception:
            self.client.storage.create_bucket(
                self.bucket_name,
                options={
                    "public": False,
                    "file_size_limit": self.max_upload_size_bytes,
                    "allowed_mime_types": [
                        "application/pdf",
                        "image/jpeg",
                        "image/png",
                        "image/webp",
                    ],
                },
            )

    def upload_case_file(self, case_request_id: int, upload: UploadFile) -> StoredFilePayload:
        original_name, content = _validate_upload(upload, self.max_upload_size_bytes)
        extension = Path(original_name).suffix.lower()
        object_path = f"case-files/{case_request_id}/{uuid4().hex}{extension}"
        self.client.storage.from_(self.bucket_name).upload(
            path=object_path,
            file=io.BytesIO(content),
            file_options={
                "content-type": upload.content_type or "application/octet-stream",
                "cache-control": "3600",
                "upsert": "false",
            },
        )

        return StoredFilePayload(
            provider=self.provider,
            bucket=self.bucket_name,
            path=object_path,
            mime_type=upload.content_type or "application/octet-stream",
            size_bytes=len(content),
            original_name=original_name,
        )

    def download_response(self, file_record) -> Response:
        content = self.client.storage.from_(file_record.storage_bucket).download(file_record.storage_path)
        return Response(
            content=content,
            media_type=file_record.mime_type or "application/octet-stream",
            headers=_build_download_headers(file_record.original_name),
        )


def build_storage_backend():
    if settings.uses_supabase_storage:
        return SupabaseStorageBackend(
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket_name=settings.supabase_storage_bucket,
            max_upload_size_bytes=settings.max_upload_size_bytes,
            signed_url_ttl_seconds=settings.signed_url_ttl_seconds,
        )
    return LocalStorageBackend(
        root=settings.uploads_dir,
        max_upload_size_bytes=settings.max_upload_size_bytes,
    )
