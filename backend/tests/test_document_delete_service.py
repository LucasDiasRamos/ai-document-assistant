from pathlib import Path

import pytest

from app.models.document import Document, DocumentStatus
from app.services.document_service import (
    DocumentFileCleanupError,
    delete_document,
)
from app.services.storage_service import StorageService


def make_document(path: Path) -> Document:
    return Document(
        id=7,
        filename=path.name,
        original_filename="manual.pdf",
        file_path=str(path),
        status=DocumentStatus.PROCESSED,
    )


class FakeSession:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.fail_commit = fail_commit
        self.deleted = []
        self.committed = False
        self.rolled_back = False

    def delete(self, value) -> None:
        self.deleted.append(value)

    def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("database delete failed")
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def test_delete_document_removes_database_record_and_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stored.pdf"
    path.write_bytes(b"%PDF-test")
    document = make_document(path)
    db = FakeSession()
    storage = StorageService(tmp_path)

    delete_document(db, document, storage=storage)

    assert db.deleted == [document]
    assert db.committed is True
    assert db.rolled_back is False
    assert not path.exists()


def test_missing_local_file_does_not_block_database_delete(
    tmp_path: Path,
) -> None:
    path = tmp_path / "already-missing.pdf"
    document = make_document(path)
    db = FakeSession()
    storage = StorageService(tmp_path)

    delete_document(db, document, storage=storage)

    assert db.deleted == [document]
    assert db.committed is True
    assert db.rolled_back is False


def test_database_failure_rolls_back_before_file_cleanup(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stored.pdf"
    path.write_bytes(b"%PDF-test")
    document = make_document(path)
    db = FakeSession(fail_commit=True)
    storage = StorageService(tmp_path)

    with pytest.raises(RuntimeError, match="database delete failed"):
        delete_document(db, document, storage=storage)

    assert db.rolled_back is True
    assert path.exists()


class FailingDeleteStorage(StorageService):
    def delete(self, path):
        raise OSError("filesystem unavailable")


def test_file_cleanup_failure_is_controlled_after_database_delete(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stored.pdf"
    path.write_bytes(b"%PDF-test")
    document = make_document(path)
    db = FakeSession()
    storage = FailingDeleteStorage(tmp_path)

    with pytest.raises(
        DocumentFileCleanupError,
        match="stored file cleanup failed",
    ):
        delete_document(db, document, storage=storage)

    assert db.committed is True
    assert path.exists()
