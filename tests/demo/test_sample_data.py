import time
from pathlib import Path

from stylemate.demo.sample_data import sample_garments


def test_sample_garments_have_deterministic_json_payloads():
    first_payloads = [garment.model_dump_json() for garment in sample_garments()]
    time.sleep(0.02)
    second_payloads = [garment.model_dump_json() for garment in sample_garments()]

    assert first_payloads == second_payloads


def test_sample_garment_image_references_exist_in_repository():
    image_references = [garment.image_ref for garment in sample_garments()]

    assert len(image_references) == 6
    assert all(reference and reference.endswith(".webp") for reference in image_references)
    assert all(Path(reference).is_file() for reference in image_references)
