import sqlite3

from stylemate.domain.models import Garment
from stylemate.repositories.sqlite import SQLiteWardrobeRepository


class TrackingConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.closed = False

    def close(self):
        self.closed = True
        super().close()


def test_sqlite_connections_close_after_normal_operations(monkeypatch, tmp_path):
    database_path = tmp_path / "stylemate.db"
    original_connect = sqlite3.connect
    connections: list[TrackingConnection] = []

    def tracked_connect(path):
        connection = original_connect(path, factory=TrackingConnection)
        connections.append(connection)
        return connection

    monkeypatch.setattr("stylemate.repositories.sqlite.sqlite3.connect", tracked_connect)
    repository = SQLiteWardrobeRepository(database_path)
    repository.save_garment(
        "owner-1",
        Garment(
            id="g-1",
            name="白色衬衫",
            category="上装",
            primary_color="白色",
            seasons=["春"],
            styles=["通勤"],
            source="manual",
        ),
    )
    repository.list_garments("owner-1")

    assert connections and all(connection.closed for connection in connections)
    database_path.unlink()
    assert not database_path.exists()


def test_sqlite_repository_creates_missing_parent_directories(tmp_path):
    database_path = tmp_path / "nested" / "data" / "stylemate.db"

    repository = SQLiteWardrobeRepository(database_path)

    assert repository.list_garments("owner-1") == []
    assert database_path.is_file()
