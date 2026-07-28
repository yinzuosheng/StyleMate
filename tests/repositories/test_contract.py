from pathlib import Path

import pytest

from domain.models import Garment
from repositories.session import SessionWardrobeRepository
from repositories.sqlite import SQLiteWardrobeRepository


@pytest.fixture(params=["session", "sqlite"])
def repo(request, tmp_path: Path):
    if request.param == "session":
        return SessionWardrobeRepository({})
    return SQLiteWardrobeRepository(tmp_path / "stylemate.db")


def garment() -> Garment:
    return Garment(
        id="g-1",
        name="白色衬衫",
        category="上装",
        primary_color="白色",
        seasons=["春", "秋"],
        styles=["通勤"],
        image_hash="abc",
        source="manual",
    )


def test_repository_crud_and_duplicate_lookup(repo):
    repo.save_garment("owner-1", garment())

    assert [item.id for item in repo.list_garments("owner-1")] == ["g-1"]
    assert repo.find_garment_by_hash("owner-1", "abc").id == "g-1"
    assert repo.list_garments("owner-2") == []

    repo.delete_garment("owner-1", "g-1")

    assert repo.list_garments("owner-1") == []
