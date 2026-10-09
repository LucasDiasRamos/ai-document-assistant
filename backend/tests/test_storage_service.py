from importlib import import_module
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.storage_service import (
    StorageService,
    UnsafeStoragePathError,
)


PDF_BYTES = b"%PDF-1.7\nportfolio-test\n%%EOF"


def test_save_creates_storage_root_and_persists_stream(tmp_path: Path) -> None:
    root = tmp_path / "uploads"
    service = StorageService(root)

    stored = service.save(
        BytesIO(PDF_BYTES),
        original_filename="manual.pdf",
    )

    assert root.exists()
    assert stored.original_filename == "manual.pdf"
    assert stored.filename.endswith(".pdf")
    assert stored.filename != "manual.pdf"
    assert stored.path.parent == root.resolve()
    assert stored.path.read_bytes() == PDF_BYTES


def test_same_original_filename_generates_unique_internal_names(
    tmp_path: Path,
) -> None:
    service = StorageService(tmp_path)

    first = service.save(
        BytesIO(PDF_BYTES),
        original_filename="manual.pdf",
    )
    second = service.save(
        BytesIO(PDF_BYTES),
        original_filename="manual.pdf",
    )

    assert first.filename != second.filename
    assert first.path != second.path
    assert first.path.exists()
    assert second.path.exists()


def test_suspicious_original_filename_never_controls_storage_path(
    tmp_path: Path,
) -> None:
    service = StorageService(tmp_path)

    stored = service.save(
        BytesIO(PDF_BYTES),
        original_filename="../../outside.pdf",
    )

    assert stored.original_filename == "../../outside.pdf"
    assert stored.path.parent == tmp_path.resolve()
    assert ".." not in stored.filename
    assert stored.filename.endswith(".pdf")


def test_delete_removes_stored_file(tmp_path: Path) -> None:
    service = StorageService(tmp_path)
    stored = service.save(
        BytesIO(PDF_BYTES),
        original_filename="manual.pdf",
    )

    assert service.delete(stored.path) is True
    assert stored.path.exists() is False


def test_delete_missing_file_returns_false(tmp_path: Path) -> None:
    service = StorageService(tmp_path)

    assert service.delete("missing.pdf") is False


def test_delete_rejects_path_outside_storage_root(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(PDF_BYTES)
    service = StorageService(root)

    with pytest.raises(UnsafeStoragePathError):
        service.delete(outside)

    assert outside.exists()


def test_delete_rejects_parent_traversal(tmp_path: Path) -> None:
    service = StorageService(tmp_path / "storage")

    with pytest.raises(UnsafeStoragePathError):
        service.delete("../outside.pdf")


def test_save_rejects_suffix_with_path_separator(tmp_path: Path) -> None:
    service = StorageService(tmp_path)

    with pytest.raises(ValueError):
        service.save(
            BytesIO(PDF_BYTES),
            original_filename="manual.pdf",
            suffix="../pdf",
        )


def test_save_retries_uuid_collision_without_deleting_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = StorageService(tmp_path)
    existing = tmp_path / "collision.pdf"
    existing.write_bytes(b"existing-data")

    generated = iter(
        [
            SimpleNamespace(hex="collision"),
            SimpleNamespace(hex="new-file"),
        ]
    )
    monkeypatch.setattr(
        import_module("app.services.storage_service"),
        "uuid4",
        lambda: next(generated),
    )

    stored = service.save(
        BytesIO(PDF_BYTES),
        original_filename="manual.pdf",
    )

    assert existing.read_bytes() == b"existing-data"
    assert stored.filename == "new-file.pdf"
    assert stored.path.read_bytes() == PDF_BYTES


def test_save_raises_after_repeated_uuid_collisions_without_data_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = StorageService(tmp_path)
    existing = tmp_path / "collision.pdf"
    existing.write_bytes(b"existing-data")

    monkeypatch.setattr(
        import_module("app.services.storage_service"),
        "uuid4",
        lambda: SimpleNamespace(hex="collision"),
    )

    with pytest.raises(FileExistsError, match="unique storage filename"):
        service.save(
            BytesIO(PDF_BYTES),
            original_filename="manual.pdf",
        )

    assert existing.read_bytes() == b"existing-data"
