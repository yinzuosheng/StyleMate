"""Draft-first multimodal garment onboarding workflow."""

import time
import uuid
from json import JSONDecodeError

from pydantic import ValidationError

from domain.models import AgentTrace, AgentTraceStep, Garment, SkillOutcome
from gateways.vision import VisionError, VisionGateway
from services.wardrobe_service import UploadValidationError, WardrobeService


class WardrobeOnboardingSkill:
    def __init__(self, service: WardrobeService, vision: VisionGateway):
        self.service = service
        self.vision = vision

    def run(
        self,
        owner_id: str,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
        user_note: str,
    ) -> SkillOutcome:
        del filename
        started = time.perf_counter()
        steps: list[AgentTraceStep] = []
        try:
            self.service.validate_upload(image_bytes, mime_type)
        except UploadValidationError:
            steps.append(self._step("validate_upload", "fallback", "Upload validation failed"))
            return self._manual_outcome(steps, started, "Upload could not be used; enter garment details manually.")
        steps.append(self._step("validate_upload", "success", "Upload accepted"))

        duplicate = self.service.find_duplicate(owner_id, image_bytes)
        if duplicate is not None:
            steps.append(self._step("duplicate_check", "success", "Existing garment found"))
            return SkillOutcome(
                status="needs_review",
                data={"garment": duplicate.model_dump(mode="json"), "duplicate": True},
                trace=self._trace(steps, started, "success"),
                user_message="This image already exists in your wardrobe. Review the existing garment.",
            )
        steps.append(self._step("duplicate_check", "success", "No matching garment found"))

        for attempt in range(2):
            try:
                payload = self.vision.analyze(image_bytes, mime_type, user_note)
                garment = Garment.model_validate(
                    {
                        **payload,
                        "id": str(uuid.uuid4()),
                        "image_hash": self.service.image_hash(image_bytes),
                        "image_ref": None,
                        "source": "ai",
                    }
                )
            except (TimeoutError, OSError, VisionError, JSONDecodeError, ValidationError, ValueError):
                steps.append(
                    self._step(
                        f"vision_analysis_{attempt + 1}",
                        "fallback" if attempt else "failed",
                        "Vision analysis did not return a usable draft",
                    )
                )
                continue
            steps.append(self._step(f"vision_analysis_{attempt + 1}", "success", "Draft created"))
            return SkillOutcome(
                status="needs_review",
                data={"garment": garment.model_dump(mode="json"), "duplicate": False},
                trace=self._trace(steps, started, "success"),
                user_message="Review and confirm the suggested garment details before saving.",
            )

        return self._manual_outcome(
            steps,
            started,
            "Vision analysis is unavailable. Please enter the garment details manually.",
        )

    def _manual_outcome(
        self,
        steps: list[AgentTraceStep],
        started: float,
        message: str,
    ) -> SkillOutcome:
        return SkillOutcome(
            status="needs_review",
            data={"garment": self._blank_garment(), "manual_entry": True, "duplicate": False},
            trace=self._trace(steps, started, "fallback"),
            user_message=message,
        )

    @staticmethod
    def _blank_garment() -> dict:
        return {
            "id": str(uuid.uuid4()),
            "name": "",
            "category": "",
            "primary_color": "",
            "material": "",
            "seasons": [],
            "styles": [],
            "confidence": {},
            "image_ref": None,
            "image_hash": None,
            "source": "manual",
        }

    @staticmethod
    def _step(name: str, status: str, summary: str) -> AgentTraceStep:
        return AgentTraceStep(name=name, status=status, summary=summary, duration_ms=0)

    @staticmethod
    def _trace(steps: list[AgentTraceStep], started: float, status: str) -> AgentTrace:
        return AgentTrace(
            skill_name="WardrobeOnboardingSkill",
            steps=steps,
            duration_ms=int((time.perf_counter() - started) * 1000),
            status=status,
        )
