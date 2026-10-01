from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_chain_has_expected_head() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_current_head() == "0003_create_document_chunks"

    revisions = list(scripts.walk_revisions(base="base", head="heads"))
    assert [revision.revision for revision in revisions] == [
        "0003_create_document_chunks",
        "0002_create_documents",
        "0001_enable_pgvector",
    ]
