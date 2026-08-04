"""Small deterministic outfit-planning workflow."""

import time
from collections.abc import Callable

from domain.models import AgentTrace, AgentTraceStep, OutfitRequest, SkillOutcome
from repositories.base import WardrobeRepository
from rules.outfit_rules import plan_outfits


class OutfitPlanningSkill:
    def __init__(
        self,
        repository: WardrobeRepository,
        weather_loader: Callable[[str], str] | None = None,
    ):
        self.repository = repository
        self.weather_loader = weather_loader

    def run(self, owner_id: str, request: OutfitRequest) -> SkillOutcome:
        started = time.perf_counter()
        steps: list[AgentTraceStep] = []
        garments = self.repository.list_garments(owner_id)
        steps.append(self._step("load_wardrobe", "success", "Wardrobe loaded"))

        weather_available = True
        if self.weather_loader is not None and request.city:
            try:
                self.weather_loader(request.city)
            except Exception:
                weather_available = False
                steps.append(self._step("weather", "fallback", "Weather unavailable"))
            else:
                steps.append(self._step("weather", "success", "Weather checked"))

        recommendations = plan_outfits(request, garments)
        steps.append(self._step("plan_outfits", "success", "Outfits planned"))
        status = "success" if recommendations and weather_available else "fallback"
        if not recommendations:
            message = "请先添加上装和下装，再生成穿搭建议。"
        elif not weather_available:
            message = "天气信息暂不可用，已根据衣柜生成穿搭建议。"
        else:
            message = "已根据你的衣柜生成穿搭建议。"
        return SkillOutcome(
            status=status,
            data={
                "recommendations": [
                    item.model_dump(mode="json") for item in recommendations
                ]
            },
            trace=self._trace(steps, started, status),
            user_message=message,
        )

    @staticmethod
    def _step(name: str, status: str, summary: str) -> AgentTraceStep:
        return AgentTraceStep(name=name, status=status, summary=summary, duration_ms=0)

    @staticmethod
    def _trace(steps: list[AgentTraceStep], started: float, status: str) -> AgentTrace:
        return AgentTrace(
            skill_name="OutfitPlanningSkill",
            steps=steps,
            duration_ms=int((time.perf_counter() - started) * 1000),
            status=status,
        )
