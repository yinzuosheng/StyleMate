from __future__ import annotations

from dataclasses import dataclass

import pytest

from scripts.discover_cc_wardrobe import (
    SourceSpec,
    candidate_from_page,
    normalize_license,
)
from scripts.download_cc_wardrobe import canonical_source_url, download_with_retry


def _page(
    *,
    title: str = "File:Blouse (AM 1965.78-1).jpg",
    license_name: str = "CC BY 4.0",
    width: int = 2592,
    height: int = 1944,
    mime: str = "image/jpeg",
) -> dict:
    return {
        "title": title,
        "imageinfo": [
            {
                "url": "https://upload.wikimedia.org/example.jpg?download=1",
                "thumburl": "https://upload.wikimedia.org/example-1600px.jpg",
                "width": width,
                "height": height,
                "mime": mime,
                "extmetadata": {
                    "LicenseShortName": {"value": license_name},
                    "Artist": {"value": "Auckland Museum"},
                    "ObjectName": {"value": "<div>Blouse</div>"},
                    "ImageDescription": {
                        "value": "Black silk blouse photographed on a plain background"
                    },
                    "Credit": {
                        "value": '<a href="https://api.aucklandmuseum.com/id/media/v/210022">Photo</a>'
                    },
                },
            }
        ],
    }


def test_normalize_license_accepts_only_explicit_allowlist():
    assert normalize_license("CC BY 4.0") == "CC BY 4.0"
    assert normalize_license("Creative Commons Attribution-Share Alike 3.0") == "CC BY-SA 3.0"
    assert normalize_license("CC0 1.0") == "CC0 1.0"
    assert normalize_license("Public domain") == "Public Domain"

    assert normalize_license("Copyrighted free use") is None
    assert normalize_license("Unknown") is None


def test_candidate_rejects_non_garments_people_and_undersized_media():
    spec = SourceSpec("上装", "Blouse", "罩衫", 1, ("春", "夏", "秋"), ("优雅",))

    assert candidate_from_page(_page(), spec) is not None
    assert candidate_from_page(_page(title="File:Portrait of a woman in a blouse.jpg"), spec) is None
    assert candidate_from_page(_page(title="File:Blouse diagram.svg", mime="image/svg+xml"), spec) is None
    assert candidate_from_page(_page(width=799), spec) is None
    assert candidate_from_page(_page(license_name="All rights reserved"), spec) is None


def test_candidate_has_complete_provenance_and_stable_content_key():
    spec = SourceSpec("上装", "Blouse", "罩衫", 1, ("春", "夏", "秋"), ("优雅",))

    candidate = candidate_from_page(_page(), spec)

    assert candidate is not None
    assert candidate["license"] == "CC BY 4.0"
    assert candidate["creator"] == "Auckland Museum"
    assert candidate["source_url"] == "https://upload.wikimedia.org/example.jpg"
    assert candidate["download_url"].endswith("example-1600px.jpg")
    assert candidate["museum_media_url"] == "https://api.aucklandmuseum.com/id/media/v/210022"
    assert candidate["source_page"].startswith("https://commons.wikimedia.org/wiki/File:")
    assert candidate["content_key"]


@dataclass
class _Response:
    status_code: int
    content: bytes = b"image"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    def __init__(self, statuses: list[int]):
        self.statuses = iter(statuses)
        self.urls: list[str] = []

    def get(self, url: str, *, timeout: int):
        self.urls.append(url)
        return _Response(next(self.statuses))


def test_download_retries_429_and_canonicalizes_url():
    session = _Session([429, 429, 200])
    delays: list[float] = []

    payload = download_with_retry(
        session,
        "https://upload.wikimedia.org/example.jpg?utm_source=test&download=1",
        sleep=delays.append,
    )

    assert payload == b"image"
    assert session.urls == ["https://upload.wikimedia.org/example.jpg"] * 3
    assert delays == [2.0, 4.0]
    assert canonical_source_url("https://example.test/a.jpg?x=1#part") == "https://example.test/a.jpg"


def test_download_stops_after_retry_budget():
    session = _Session([429, 429, 429, 429, 429, 429, 429, 429])

    with pytest.raises(RuntimeError, match="HTTP 429"):
        download_with_retry(session, "https://example.test/a.jpg", sleep=lambda _: None)
