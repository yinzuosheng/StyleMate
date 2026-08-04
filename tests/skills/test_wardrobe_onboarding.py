from domain.models import Garment
from services.wardrobe_service import WardrobeService
from skills.wardrobe_onboarding import WardrobeOnboardingSkill
from storage.images import SessionImageStore


class FakeVision:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def analyze(self, image_bytes, mime_type, user_note):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


VALID = {
    "name": "Beige coat",
    "category": "outerwear",
    "primary_color": "beige",
    "material": "cotton blend",
    "seasons": ["spring", "autumn"],
    "styles": ["commute", "minimal"],
    "confidence": {"category": 0.96, "material": 0.72},
}


def make_skill(repo, vision):
    service = WardrobeService(
        repo,
        SessionImageStore({}),
        max_upload_bytes=8 * 1024 * 1024,
    )
    return WardrobeOnboardingSkill(service=service, vision=vision)


def test_skill_returns_reviewable_draft_without_persisting(repo):
    skill = make_skill(repo, FakeVision([VALID]))

    outcome = skill.run("u1", b"image", "image/jpeg", "coat.jpg", "private note")

    garment = Garment.model_validate(outcome.data["garment"])
    assert outcome.status == "needs_review"
    assert garment.category == "outerwear"
    assert garment.source == "ai"
    assert garment.image_ref is None
    assert repo.list_garments("u1") == []
    assert all("private note" not in step.summary for step in outcome.trace.steps)


def test_skill_retries_once_then_returns_manual_form(repo):
    vision = FakeVision([TimeoutError(), TimeoutError()])

    outcome = make_skill(repo, vision).run("u1", b"image", "image/jpeg", "coat.jpg", "")

    assert vision.calls == 2
    assert outcome.status == "needs_review"
    assert outcome.data["manual_entry"] is True
    assert outcome.data["garment"]["name"] == ""
    assert "manual" in outcome.user_message.lower()


def test_skill_retries_malformed_provider_schema_then_returns_manual_form(repo):
    malformed = {**VALID, "confidence": {"category": 1.1}}
    vision = FakeVision([malformed, malformed])

    outcome = make_skill(repo, vision).run("u1", b"image", "image/jpeg", "coat.jpg", "")

    assert vision.calls == 2
    assert outcome.status == "needs_review"
    assert outcome.data["manual_entry"] is True


def test_skill_returns_existing_owner_garment_without_calling_vision(repo):
    service = WardrobeService(repo, SessionImageStore({}), max_upload_bytes=8 * 1024 * 1024)
    image_bytes = b"image"
    existing = Garment(
        id="existing",
        name="Existing coat",
        category="outerwear",
        primary_color="beige",
        seasons=["spring"],
        styles=["minimal"],
        image_hash=service.image_hash(image_bytes),
        source="manual",
    )
    repo.save_garment("u1", existing)
    vision = FakeVision([])

    outcome = WardrobeOnboardingSkill(service=service, vision=vision).run(
        "u1", image_bytes, "image/jpeg", "coat.jpg", ""
    )

    assert outcome.status == "needs_review"
    assert outcome.data["duplicate"] is True
    assert Garment.model_validate(outcome.data["garment"]) == existing
    assert vision.calls == 0
