from io import BytesIO

import pytest
from PIL import Image

from stylemate.demo.sample_data import sample_garments as build_sample_garments
from stylemate.repositories.session import SessionWardrobeRepository


@pytest.fixture
def repo():
    return SessionWardrobeRepository({})


@pytest.fixture
def sample_garments():
    return build_sample_garments()


@pytest.fixture
def jpeg_bytes():
    buffer = BytesIO()
    Image.new("RGB", (16, 16), "white").save(buffer, format="JPEG")
    return buffer.getvalue()
