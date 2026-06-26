import os
import sys
from pathlib import Path

# backend/ on path so `import app.*` works; skip real DB bootstrap on startup.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DSE_SKIP_INIT"] = "1"

import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    import app.models as _models  # noqa: F401  (register tables, no name shadow)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override():
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_db] = _override
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.clear()
