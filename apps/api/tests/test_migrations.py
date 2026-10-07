"""Roda no CI contra um Postgres com pgvector (nunca no Windows): RUN_DB_TESTS=1."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

API_DIR = Path(__file__).resolve().parents[1]


def test_upgrade_cria_extensoes_e_semente() -> None:
    cfg = Config(str(API_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        exts = {r[0] for r in conn.execute(text("SELECT extname FROM pg_extension"))}
        assert {"vector", "pg_trgm", "unaccent"} <= exts
        name = conn.execute(text("SELECT name FROM brand_settings WHERE id = 1")).scalar_one()
        assert name  # semente neutra existe
        with pytest.raises(Exception, match="singleton"):
            conn.execute(
                text(
                    "INSERT INTO brand_settings (id, name, colors, fonts) VALUES (2,'x','{}','{}')"
                )
            )


def test_downgrade_e_upgrade_sao_reversiveis() -> None:
    cfg = Config(str(API_DIR / "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
