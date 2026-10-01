from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copyfileobj
from typing import BinaryIO
from uuid import uuid4

from app.core.config import settings


class UnsafeStoragePathError(ValueError):
    """Raised when a requested storage path escapes the configured root."""


@dataclass(frozen=True, slots=True)
class StoredFile:
    original_filename: str
    filename: str
    path: Path


class StorageService:
    MAX_FILENAME_ATTEMPTS = 10

    def __init__(self, root: Path | None = None) -> None:
        configured_root = root if root is not None else settings.storage_root
        self.root = configured_root.expanduser().resolve()

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        stream: BinaryIO,
        *,
        original_filename: str,
        suffix: str = ".pdf",
    ) -> StoredFile:
        self.ensure_root()
        safe_suffix = self._normalize_suffix(suffix)

        for _ in range(self.MAX_FILENAME_ATTEMPTS):
            internal_filename = f"{uuid4().hex}{safe_suffix}"
            destination = self._resolve_internal_path(internal_filename)

            try:
                output = destination.open("xb")
            except FileExistsError:
                continue

            try:
                with output:
                    copyfileobj(stream, output)
            except Exception:
                destination.unlink(missing_ok=True)
                raise

            return StoredFile(
                original_filename=original_filename,
                filename=internal_filename,
                path=destination,
            )

        raise FileExistsError(
            "Could not allocate a unique storage filename "
            f"after {self.MAX_FILENAME_ATTEMPTS} attempts"
        )

    def delete(self, path: str | Path) -> bool:
        candidate = self._resolve_existing_or_target_path(path)

        if not candidate.exists():
            return False

        if candidate.is_dir():
            raise IsADirectoryError(candidate)

        candidate.unlink()
        return True

    def _resolve_internal_path(self, filename: str) -> Path:
        candidate = (self.root / filename).resolve()
        self._assert_within_root(candidate)
        return candidate

    def _resolve_existing_or_target_path(self, path: str | Path) -> Path:
        raw_path = Path(path)

        if not raw_path.is_absolute():
            raw_path = self.root / raw_path

        candidate = raw_path.expanduser().resolve()
        self._assert_within_root(candidate)
        return candidate

    def _assert_within_root(self, candidate: Path) -> None:
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise UnsafeStoragePathError(
                f"Storage path is outside configured root: {candidate}"
            ) from exc

    @staticmethod
    def _normalize_suffix(suffix: str) -> str:
        clean = suffix.strip().lower()

        if not clean:
            return ""

        if "/" in clean or "\\" in clean:
            raise ValueError("Storage suffix cannot contain path separators")

        if not clean.startswith("."):
            clean = f".{clean}"

        return clean


storage_service = StorageService()
