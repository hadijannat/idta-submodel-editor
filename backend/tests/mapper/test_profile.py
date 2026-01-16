import io
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.config import get_settings
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.mapper import MapperService
from app.services.parser import ParserService


@pytest.mark.asyncio
async def test_profile_csv(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef")
    get_settings.cache_clear()
    csv_path = Path("backend/tests/fixtures/mapper/sample.csv")
    data = csv_path.read_bytes()
    file = UploadFile(filename="sample.csv", file=io.BytesIO(data))
    mapper = MapperService(
        fetcher=TemplateFetcherService(),
        parser=ParserService(),
        hydrator=HydratorService(),
    )

    profile = await mapper.profile(file, sheet=None, header_row=1, sample_rows=10)

    assert profile.columns[0].name_original == "Name"
    assert profile.columns[1].name_original == "Weight"
    assert profile.columns[1].inferred_type in {"number", "mixed"}
    assert profile.columns[2].inferred_type in {"boolean", "mixed"}
