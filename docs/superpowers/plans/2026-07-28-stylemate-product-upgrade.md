# StyleMate Product Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing chat-first StyleMate prototype into a publicly deployable digital wardrobe workbench with multimodal garment onboarding, inventory-grounded outfit planning, visible Agent traces, graceful degradation, and measurable evaluation.

**Architecture:** Keep Streamlit as the presentation layer and move domain logic out of the current monolithic `app.py`. Pages call focused services; services call two deterministic Agent Skills; Skills depend on typed gateways and repositories. Public deployments use session-isolated demo storage, while local runs use SQLite and a local image directory.

**Tech Stack:** Python 3.11, Streamlit 1.40.1, Pydantic 2.x, LangChain 0.3.x, ChromaDB, DashScope text and multimodal APIs, SQLite, Pillow, pytest, Streamlit AppTest.

## Global Constraints

- Preserve Streamlit; do not add FastAPI, Vue, React, a mobile client, training, fine-tuning, commerce, payment, or social features.
- `APP_MODE` must be exactly `demo` or `local`; public deployment uses `demo`, and local execution defaults to `local`.
- Accept only JPG, JPEG, PNG, and WEBP uploads with an 8 MB maximum.
- Weather calls time out after 5 seconds; model calls time out after 30 seconds; malformed structured model output receives one retry.
- Public visitors must not register and must not share wardrobe, image, favorite, feedback, or trace state.
- Every recommended garment ID must exist in the active repository; the accepted inventory-truth rate is 100%.
- Missing secrets or failing weather, RAG, vision, or text APIs must return an explicit structured fallback rather than an exception page.
- Never persist or display API keys, complete system prompts, raw image bytes in traces, or private user data.
- README metrics must come from an executed evaluation artifact, never from hand-entered claims.

## Planned File Map

### Existing files to modify

- `app.py` — reduce to application composition, runtime selection, navigation, and page dispatch.
- `requirements.txt` — add direct runtime dependencies used by new modules.
- `.env.example` — document runtime mode and model configuration without real secrets.
- `.gitignore` — exclude secrets, local database, uploaded images, evaluation output, and visual-companion files.
- `README.md` — replace prototype instructions with public demo, architecture, test, evaluation, and limitation documentation.
- `agent/react_agent.py` — expose the two new Skills to the auxiliary chat page without making chat the main application.

### New domain and configuration files

- `domain/models.py` — Pydantic contracts for garments, requests, recommendations, traces, favorites, feedback, and Skill outcomes.
- `config/runtime.py` — validated runtime settings sourced from environment variables.
- `repositories/base.py` — repository protocol used by services.
- `repositories/session.py` — session-isolated demo repository.
- `repositories/sqlite.py` — local persistent repository and schema creation.
- `storage/images.py` — session and local image stores behind one protocol.
- `demo/sample_data.py` — deterministic sample wardrobe and sample recommendations.

### New service, gateway, and Skill files

- `services/wardrobe_service.py` — file validation, hashing, duplicate checks, garment persistence.
- `services/profile_service.py` — normalized profile read/write and conflict-safe merges.
- `services/outfit_service.py` — request assembly, Skill invocation, favorites, and feedback.
- `gateways/vision.py` — multimodal model protocol and DashScope adapter.
- `gateways/outfit_generator.py` — text generation protocol and DashScope adapter.
- `gateways/context.py` — weather and RAG adapters around existing project functions.
- `skills/wardrobe_onboarding.py` — multimodal onboarding workflow.
- `skills/outfit_planning.py` — inventory-grounded planning workflow.
- `rules/outfit_rules.py` — deterministic fallback planner.

### New UI files

- `ui/state.py` — Streamlit session initialization and dependency container.
- `ui/components.py` — garment cards, outfit cards, trace panels, empty states, and status badges.
- `ui/pages/dashboard.py` — overview and daily recommendation.
- `ui/pages/wardrobe.py` — upload, correction, filtering, editing, and deletion.
- `ui/pages/stylist.py` — planning form and recommendation results.
- `ui/pages/favorites.py` — favorites and feedback history.
- `ui/pages/evaluation.py` — evaluation execution and result display.
- `ui/pages/chat.py` — auxiliary access to the existing conversation Agent.

### New evaluation, test, and deployment files

- `evaluation/cases/outfit_cases.json` — at least 10 expected-constraint cases.
- `evaluation/cases/failure_cases.json` — weather, RAG, vision, text, and secret failure cases.
- `evaluation/garments/manifest.json` — labels for at least 15 original garment images.
- `evaluation/runner.py` — metric calculation and JSON artifact generation.
- `evaluation/cli.py` — command-line evaluation entry point.
- `evaluation/render_resume_entry.py` — generate a resume description from measured metrics.
- `.streamlit/config.toml` — production-safe Streamlit theme and upload settings.
- `requirements-dev.txt` — test dependencies.
- `tests/` — unit, Skill, repository, page, evaluation, and smoke tests.

## Five-Day Task Allocation

- Day 1: Tasks 1–2 and the Task 4 application shell.
- Day 2: Task 3 and the remaining Task 4 wardrobe UI.
- Day 3: Tasks 5–6.
- Day 4: Tasks 7–8.
- Day 5: Task 9, public deployment, measured documentation, and final verification.

## Spec Coverage

- Product goals, public guest flow, and workbench pages: Tasks 4 and 6.
- Layered architecture, typed data models, storage modes, and image storage: Tasks 1–4.
- `WardrobeOnboardingSkill`: Task 3.
- `OutfitPlanningSkill`, inventory grounding, weather, RAG, and rules: Task 5.
- Favorites, feedback, and redacted Agent traces: Task 6.
- Error handling and external-service degradation: Tasks 3, 5, and 8.
- Unit, Skill, integration, evaluation, and smoke tests: Tasks 1–9.
- Offline metrics and evaluation center: Task 7.
- Auxiliary chat access: Task 8.
- Streamlit Community Cloud, secrets, README, and measured resume evidence: Task 9.

No design requirement is deferred outside this plan.

---

### Task 1: Runtime Configuration and Typed Domain Contracts

**Files:**
- Create: `config/runtime.py`
- Create: `domain/__init__.py`
- Create: `domain/models.py`
- Create: `requirements-dev.txt`
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `.gitignore`
- Test: `tests/config/test_runtime.py`
- Test: `tests/domain/test_models.py`

**Interfaces:**
- Produces: `RuntimeSettings.from_env() -> RuntimeSettings`
- Produces: `Garment`, `OutfitRequest`, `OutfitRecommendation`, `AgentTrace`, `AgentTraceStep`, `FavoriteOutfit`, `OutfitFeedback`, and `SkillOutcome`
- Consumes: no new project interfaces

- [ ] **Step 1: Add failing runtime-setting tests**

```python
# tests/config/test_runtime.py
import pytest
from config.runtime import RuntimeSettings


def test_runtime_defaults_to_local(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    settings = RuntimeSettings.from_env()
    assert settings.app_mode == "local"
    assert settings.max_upload_bytes == 8 * 1024 * 1024
    assert settings.weather_timeout_seconds == 5
    assert settings.model_timeout_seconds == 30


def test_runtime_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("APP_MODE", "production")
    with pytest.raises(ValueError, match="APP_MODE"):
        RuntimeSettings.from_env()
```

- [ ] **Step 2: Add failing domain-contract tests**

```python
# tests/domain/test_models.py
import pytest
from pydantic import ValidationError
from domain.models import Garment, OutfitRecommendation


def test_garment_requires_core_fields():
    with pytest.raises(ValidationError):
        Garment(
            id="g-1",
            name="无分类单品",
            category="",
            primary_color="白色",
            seasons=["春"],
            styles=["简约"],
            source="ai",
        )


def test_recommendation_deduplicates_garment_ids():
    outfit = OutfitRecommendation(
        id="o-1",
        garment_ids=["g-1", "g-1", "g-2"],
        score=88,
        reason="适合通勤",
        constraint_checks={"inventory": True},
    )
    assert outfit.garment_ids == ["g-1", "g-2"]
```

- [ ] **Step 3: Run the focused tests and verify import failures**

Run:

```powershell
python -m pytest tests/config/test_runtime.py tests/domain/test_models.py -v
```

Expected: collection fails because `config.runtime` and `domain.models` do not exist.

- [ ] **Step 4: Implement runtime settings**

```python
# config/runtime.py
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RuntimeSettings:
    app_mode: str
    vision_model_name: str
    text_model_name: str
    max_upload_bytes: int = 8 * 1024 * 1024
    weather_timeout_seconds: int = 5
    model_timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "RuntimeSettings":
        mode = os.getenv("APP_MODE", "local").strip().lower()
        if mode not in {"demo", "local"}:
            raise ValueError("APP_MODE must be 'demo' or 'local'")
        return cls(
            app_mode=mode,
            vision_model_name=os.getenv("VISION_MODEL_NAME", "qwen-vl-plus"),
            text_model_name=os.getenv("TEXT_MODEL_NAME", "qwen-plus"),
        )
```

- [ ] **Step 5: Implement the Pydantic models with exact field contracts**

```python
# domain/models.py
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class Garment(BaseModel):
    id: str
    name: str
    category: str = Field(min_length=1)
    primary_color: str = Field(min_length=1)
    material: str | None = None
    seasons: list[str] = Field(min_length=1)
    styles: list[str] = Field(min_length=1)
    image_ref: str | None = None
    image_hash: str | None = None
    confidence: dict[str, float] = Field(default_factory=dict)
    source: Literal["ai", "manual", "sample"]
    created_at: datetime = Field(default_factory=datetime.now)


class OutfitRequest(BaseModel):
    scene: str = Field(min_length=1)
    target_date: str | None = None
    city: str | None = None
    style_preference: str | None = None
    extra_constraints: list[str] = Field(default_factory=list)
    candidate_garment_ids: list[str] = Field(default_factory=list)


class OutfitRecommendation(BaseModel):
    id: str
    garment_ids: list[str] = Field(min_length=1)
    score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1)
    weather_note: str | None = None
    constraint_checks: dict[str, bool]
    knowledge_sources: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("garment_ids")
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))


class AgentTraceStep(BaseModel):
    name: str
    status: Literal["success", "fallback", "failed"]
    summary: str
    duration_ms: int = Field(ge=0)


class AgentTrace(BaseModel):
    skill_name: str
    steps: list[AgentTraceStep]
    tool_calls: list[str] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
    status: Literal["success", "fallback", "failed"]


class FavoriteOutfit(BaseModel):
    owner_id: str
    recommendation: OutfitRecommendation


class OutfitFeedback(BaseModel):
    outfit_id: str
    owner_id: str
    reasons: list[str]
    note: str = ""


class SkillOutcome(BaseModel):
    status: Literal["success", "needs_review", "fallback", "failed"]
    data: dict[str, Any]
    trace: AgentTrace
    user_message: str
```

- [ ] **Step 6: Declare dependencies and safe local files**

Add `pydantic==2.9.2` and `Pillow==11.0.0` to `requirements.txt`. Add `pytest==8.3.3`, `pytest-cov==5.0.0`, and `ruff==0.7.4` to `requirements-dev.txt`.

Add these entries to `.gitignore`:

```gitignore
.superpowers/
.streamlit/secrets.toml
data/stylemate.db
data/uploads/
artifacts/
```

Extend `.env.example` with:

```dotenv
APP_MODE=local
VISION_MODEL_NAME=qwen-vl-plus
TEXT_MODEL_NAME=qwen-plus
DASHSCOPE_API_KEY=
AMAP_API_KEY=
```

- [ ] **Step 7: Run tests and static syntax checks**

Run:

```powershell
python -m pytest tests/config/test_runtime.py tests/domain/test_models.py -v
python -m compileall config domain
```

Expected: all tests pass and compilation exits with code 0.

- [ ] **Step 8: Commit Task 1**

```powershell
git add .gitignore .env.example requirements.txt requirements-dev.txt config/runtime.py domain tests/config tests/domain
git commit -m "feat: add StyleMate runtime and domain contracts"
```

---

### Task 2: Storage Modes, Sample Data, and Profile Service

**Files:**
- Create: `repositories/__init__.py`
- Create: `repositories/base.py`
- Create: `repositories/session.py`
- Create: `repositories/sqlite.py`
- Create: `demo/__init__.py`
- Create: `demo/sample_data.py`
- Create: `services/profile_service.py`
- Create: `tests/conftest.py`
- Test: `tests/repositories/test_contract.py`
- Test: `tests/services/test_profile_service.py`

**Interfaces:**
- Consumes: `Garment`, `FavoriteOutfit`, `OutfitFeedback`
- Produces: `WardrobeRepository` protocol
- Produces: `SessionWardrobeRepository(state: dict)`, `SQLiteWardrobeRepository(path: Path)`
- Produces: `ProfileService.get(owner_id) -> dict[str, str]`, `ProfileService.merge(owner_id, updates) -> tuple[dict[str, str], list[str]]`, `ProfileService.replace(owner_id, profile) -> dict[str, str]`

- [ ] **Step 1: Write one repository contract test used by both implementations**

```python
# tests/repositories/test_contract.py
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
```

Add shared fixtures for later tasks:

```python
# tests/conftest.py
from io import BytesIO
import pytest
from PIL import Image
from demo.sample_data import sample_garments as build_sample_garments
from repositories.session import SessionWardrobeRepository


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
```

- [ ] **Step 2: Run the repository test and verify missing-module failure**

Run:

```powershell
python -m pytest tests/repositories/test_contract.py -v
```

Expected: collection fails because repository modules do not exist.

- [ ] **Step 3: Define the repository protocol**

```python
# repositories/base.py
from typing import Protocol
from domain.models import FavoriteOutfit, Garment, OutfitFeedback


class WardrobeRepository(Protocol):
    def list_garments(self, owner_id: str) -> list[Garment]: ...
    def get_garment(self, owner_id: str, garment_id: str) -> Garment | None: ...
    def save_garment(self, owner_id: str, garment: Garment) -> None: ...
    def delete_garment(self, owner_id: str, garment_id: str) -> None: ...
    def find_garment_by_hash(self, owner_id: str, image_hash: str) -> Garment | None: ...
    def get_profile(self, owner_id: str) -> dict[str, str]: ...
    def save_profile(self, owner_id: str, profile: dict[str, str]) -> None: ...
    def save_favorite(self, favorite: FavoriteOutfit) -> None: ...
    def list_favorites(self, owner_id: str) -> list[FavoriteOutfit]: ...
    def save_feedback(self, feedback: OutfitFeedback) -> None: ...
```

- [ ] **Step 4: Implement the session repository**

Store each owner below `state["owners"][owner_id]` with `garments`, `profile`, `favorites`, and `feedback` keys. Serialize models with `model_dump(mode="json")` and reconstruct them with `model_validate`.

The constructor must retain the passed dictionary rather than copying it:

```python
class SessionWardrobeRepository:
    def __init__(self, state: dict):
        self.state = state
        self.state.setdefault("owners", {})
```

- [ ] **Step 5: Implement SQLite schema creation and repository operations**

Create tables `garments`, `profiles`, `favorites`, and `feedback`. Store Pydantic payloads as UTF-8 JSON text and use `(owner_id, entity_id)` composite primary keys. Every method must open a short-lived `sqlite3.connect(self.path)` context and use parameterized SQL.

Schema initialization must execute:

```sql
CREATE TABLE IF NOT EXISTS garments (
  owner_id TEXT NOT NULL,
  garment_id TEXT NOT NULL,
  image_hash TEXT,
  payload TEXT NOT NULL,
  PRIMARY KEY (owner_id, garment_id)
);
CREATE INDEX IF NOT EXISTS idx_garment_hash
  ON garments(owner_id, image_hash);
CREATE TABLE IF NOT EXISTS profiles (
  owner_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS favorites (
  owner_id TEXT NOT NULL,
  outfit_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  PRIMARY KEY (owner_id, outfit_id)
);
CREATE TABLE IF NOT EXISTS feedback (
  owner_id TEXT NOT NULL,
  outfit_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  PRIMARY KEY (owner_id, outfit_id)
);
```

- [ ] **Step 6: Add deterministic sample wardrobe data**

`demo/sample_data.py` must expose `sample_garments() -> list[Garment]` with at least these six IDs and labels:

```python
[
    ("sample-shirt-white", "白色衬衫", "上装", "白色", ["通勤", "简约"]),
    ("sample-jeans-blue", "浅蓝牛仔裤", "下装", "浅蓝", ["休闲", "简约"]),
    ("sample-trench-beige", "米色风衣", "外套", "米色", ["通勤", "简约"]),
    ("sample-loafers-black", "黑色乐福鞋", "鞋履", "黑色", ["通勤"]),
    ("sample-cardigan-cream", "奶油色针织开衫", "上装", "奶油色", ["温柔", "休闲"]),
    ("sample-skirt-gray", "深灰半身裙", "下装", "深灰", ["通勤", "优雅"]),
]
```

All sample records use `source="sample"` and repository-local image references.

- [ ] **Step 7: Test and implement conflict-safe profile merging**

```python
# tests/services/test_profile_service.py
def test_profile_merge_keeps_existing_value_and_reports_conflict(repo):
    service = ProfileService(repo)
    repo.save_profile("u1", {"style_preference": "简约"})
    merged, conflicts = service.merge("u1", {"style_preference": "街头", "height": "171cm"})
    assert merged == {"style_preference": "简约", "height": "171cm"}
    assert conflicts == ["style_preference"]
```

`ProfileService.merge` must add empty fields, retain a non-empty existing value when a different non-empty value arrives, report the conflicting key, and persist the merged profile. `ProfileService.replace` is used only by the explicit profile form, normalizes the seven allowed keys, saves the submitted values, and allows an intentional preference change.

- [ ] **Step 8: Run repository and profile tests**

Run:

```powershell
python -m pytest tests/repositories/test_contract.py tests/services/test_profile_service.py -v
```

Expected: both repository implementations pass the same contract and profiles remain owner-isolated.

- [ ] **Step 9: Commit Task 2**

```powershell
git add repositories demo services/profile_service.py tests/repositories tests/services/test_profile_service.py
git commit -m "feat: add wardrobe repositories and demo data"
```

---

### Task 3: Wardrobe Onboarding Skill

**Files:**
- Create: `gateways/__init__.py`
- Create: `gateways/vision.py`
- Create: `services/wardrobe_service.py`
- Create: `storage/__init__.py`
- Create: `storage/images.py`
- Create: `skills/__init__.py`
- Create: `skills/wardrobe_onboarding.py`
- Test: `tests/services/test_wardrobe_service.py`
- Test: `tests/storage/test_images.py`
- Test: `tests/skills/test_wardrobe_onboarding.py`

**Interfaces:**
- Consumes: `RuntimeSettings`, `Garment`, `WardrobeRepository`
- Produces: `VisionGateway.analyze(image_bytes: bytes, mime_type: str, user_note: str) -> dict`
- Produces: `WardrobeService(repository, image_store, max_upload_bytes)`
- Produces: `WardrobeService.validate_upload`, `WardrobeService.image_hash`, `WardrobeService.save_confirmed`
- Produces: `ImageStore.save(owner_id, garment_id, image_bytes, mime_type) -> str`
- Produces: `SessionImageStore(state: dict)` and `LocalImageStore(root: Path)`
- Produces: `WardrobeOnboardingSkill.run(...) -> SkillOutcome`

- [ ] **Step 1: Write upload-validation tests**

```python
# tests/services/test_wardrobe_service.py
import pytest
from services.wardrobe_service import UploadValidationError, WardrobeService
from storage.images import SessionImageStore


def test_upload_rejects_unknown_mime(repo):
    service = WardrobeService(repo, SessionImageStore({}), max_upload_bytes=8 * 1024 * 1024)
    with pytest.raises(UploadValidationError, match="JPG"):
        service.validate_upload(b"abc", "application/pdf")


def test_upload_rejects_more_than_eight_mb(repo):
    service = WardrobeService(repo, SessionImageStore({}), max_upload_bytes=8 * 1024 * 1024)
    with pytest.raises(UploadValidationError, match="8 MB"):
        service.validate_upload(b"x" * (8 * 1024 * 1024 + 1), "image/jpeg")
```

Add image-store isolation and path-safety tests:

```python
# tests/storage/test_images.py
from pathlib import Path
from storage.images import LocalImageStore, SessionImageStore


def test_session_images_are_owner_isolated():
    store = SessionImageStore({})
    ref = store.save("u1", "g1", b"image", "image/jpeg")
    assert store.read("u1", ref) == b"image"
    assert store.read("u2", ref) is None


def test_local_store_keeps_files_below_configured_root(tmp_path: Path, jpeg_bytes):
    store = LocalImageStore(tmp_path / "uploads")
    ref = store.save("../../escape", "../garment", jpeg_bytes, "image/jpeg")
    saved = (tmp_path / "uploads" / ref).resolve()
    assert saved.is_relative_to((tmp_path / "uploads").resolve())
```

- [ ] **Step 2: Write Skill success, retry, duplicate, and manual-fallback tests**

```python
# tests/skills/test_wardrobe_onboarding.py
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
    "name": "米色风衣",
    "category": "外套",
    "primary_color": "米色",
    "material": "棉混纺",
    "seasons": ["春", "秋"],
    "styles": ["通勤", "简约"],
    "confidence": {"category": 0.96, "material": 0.72},
}


def test_skill_returns_reviewable_draft(repo):
    skill = make_skill(repo, FakeVision([VALID]))
    outcome = skill.run("u1", b"image", "image/jpeg", "coat.jpg", "")
    garment = Garment.model_validate(outcome.data["garment"])
    assert outcome.status == "needs_review"
    assert garment.category == "外套"
    assert garment.source == "ai"


def test_skill_retries_once_then_returns_manual_form(repo):
    vision = FakeVision([TimeoutError(), TimeoutError()])
    outcome = make_skill(repo, vision).run("u1", b"image", "image/jpeg", "coat.jpg", "")
    assert vision.calls == 2
    assert outcome.status == "needs_review"
    assert outcome.data["manual_entry"] is True
    assert "手动" in outcome.user_message
```

Define the helper used by both tests in the same file:

```python
def make_skill(repo, vision):
    service = WardrobeService(
        repo,
        SessionImageStore({}),
        max_upload_bytes=8 * 1024 * 1024,
    )
    return WardrobeOnboardingSkill(service=service, vision=vision)
```

- [ ] **Step 3: Run focused tests and verify failures**

Run:

```powershell
python -m pytest tests/services/test_wardrobe_service.py tests/skills/test_wardrobe_onboarding.py -v
```

Expected: collection fails because the service and Skill modules do not exist.

- [ ] **Step 4: Implement file validation and duplicate checks**

`WardrobeService.validate_upload` must verify MIME membership in:

```python
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
```

It must verify non-empty bytes and the configured size ceiling. `image_hash` returns `hashlib.sha256(image_bytes).hexdigest()`. `find_duplicate(owner_id, image_bytes)` queries `repository.find_garment_by_hash`.

- [ ] **Step 5: Implement session and local image stores**

`storage/images.py` defines:

```python
class ImageStore(Protocol):
    def save(self, owner_id: str, garment_id: str, image_bytes: bytes, mime_type: str) -> str: ...
    def read(self, owner_id: str, image_ref: str) -> bytes | None: ...
    def delete(self, owner_id: str, image_ref: str) -> None: ...
```

`SessionImageStore` keeps bytes under `state["images"][owner_id][image_ref]` and returns `memory://<uuid>`. `LocalImageStore` ignores user-provided path fragments, creates safe UUID filenames below its configured root, decodes and re-encodes images with Pillow to strip metadata, and returns a root-relative POSIX path. `resolve` must reject any path whose resolved form is outside the configured root.

- [ ] **Step 6: Define the vision gateway and DashScope adapter**

```python
# gateways/vision.py
from typing import Protocol


class VisionGateway(Protocol):
    def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        user_note: str,
    ) -> dict: ...
```

The DashScope adapter must:

1. Convert bytes to a `data:{mime_type};base64,...` URL.
2. Request only JSON with keys `name`, `category`, `primary_color`, `material`, `seasons`, `styles`, and `confidence`.
3. Set the configured 30-second timeout.
4. Reject empty output and parse JSON after removing a surrounding Markdown code fence.
5. Never log the data URL or raw image bytes.
6. Construct successfully without a key and raise a typed `VisionUnavailable` only when `analyze` is called, so the no-secret demo can reach manual entry.

- [ ] **Step 7: Implement the Skill workflow and trace**

`WardrobeOnboardingSkill.run` must:

1. Add a `validate_upload` trace step.
2. Return the existing garment with status `needs_review` when the hash already exists.
3. Invoke `VisionGateway.analyze`.
4. Retry once for timeout, transport failure, JSON parse failure, or Pydantic validation failure.
5. Build a `Garment` with a UUID-based ID, calculated hash, `source="ai"`, and no persistent `image_ref` until confirmation.
6. Return the draft with `status="needs_review"`.
7. Return a blank, editable field dictionary with `manual_entry=True` after the second failure.

The Skill must not persist a garment or image. After explicit page confirmation, `WardrobeService.save_confirmed` stores the image through the active `ImageStore`, sets the returned `image_ref`, and then saves the garment through the repository.

- [ ] **Step 8: Run tests and confirm retry count and safe fallback**

Run:

```powershell
python -m pytest tests/services/test_wardrobe_service.py tests/storage/test_images.py tests/skills/test_wardrobe_onboarding.py -v
```

Expected: all tests pass; retry tests show exactly two gateway calls.

- [ ] **Step 9: Commit Task 3**

```powershell
git add gateways services/wardrobe_service.py storage skills tests/services/test_wardrobe_service.py tests/storage tests/skills/test_wardrobe_onboarding.py
git commit -m "feat: add garment onboarding skill"
```

---

### Task 4: Demo-First Streamlit Shell and Wardrobe Workbench

**Files:**
- Create: `ui/__init__.py`
- Create: `ui/state.py`
- Create: `ui/components.py`
- Create: `ui/pages/__init__.py`
- Create: `ui/pages/dashboard.py`
- Create: `ui/pages/wardrobe.py`
- Modify: `app.py`
- Test: `tests/ui/test_app_shell.py`
- Test: `tests/ui/test_wardrobe_page.py`

**Interfaces:**
- Consumes: `RuntimeSettings`, repositories, `WardrobeService`, `WardrobeOnboardingSkill`
- Produces: `AppContainer`, `initialize_session()`, `render_dashboard(container)`, `render_wardrobe(container)`
- Produces: `seed_demo_repository(repository, owner_id) -> None`
- Produces: Streamlit session keys `owner_id`, `repository_state`, `onboarding_draft`, and `active_page`

- [ ] **Step 1: Write an AppTest that proves public demo mode has no login gate**

```python
# tests/ui/test_app_shell.py
from streamlit.testing.v1 import AppTest


def test_demo_mode_opens_dashboard_without_login(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    at = AppTest.from_file("app.py").run(timeout=20)
    assert not at.exception
    assert at.title[0].value == "StyleMate 智能衣橱"
    assert any("示例衣橱" in item.value for item in at.info)
    assert not any("请先登录" in item.value for item in at.info)
```

- [ ] **Step 2: Run the AppTest and verify it fails against the current login-first app**

Run:

```powershell
python -m pytest tests/ui/test_app_shell.py -v
```

Expected: assertion fails because the current title and login gate are still present.

- [ ] **Step 3: Build the dependency container and isolated owner state**

`ui/state.py` must:

- Create a random `visitor-<uuid>` owner ID once per Streamlit session in demo mode.
- Construct `SessionWardrobeRepository(st.session_state["repository_state"])` in demo mode.
- Construct `SessionImageStore(st.session_state["image_state"])` in demo mode.
- Construct `SQLiteWardrobeRepository(Path("data/stylemate.db"))` in local mode.
- Construct `LocalImageStore(Path("data/uploads"))` in local mode.
- Seed sample garments only when the active owner has no garments and mode is demo.
- Build services and Skills once with `st.cache_resource` only for stateless gateways; repositories remain session-bound.

- [ ] **Step 4: Replace the monolithic shell with explicit navigation**

`app.py` must contain only:

```python
from dotenv import load_dotenv
import streamlit as st
from ui.state import build_container, initialize_session
from ui.pages import dashboard, evaluation, favorites, chat, stylist, wardrobe

load_dotenv()
st.set_page_config(page_title="StyleMate 智能衣橱", page_icon="👗", layout="wide")
initialize_session()
container = build_container()

PAGES = {
    "概览": dashboard.render,
    "我的衣橱": wardrobe.render,
    "智能搭配": stylist.render,
    "搭配收藏": favorites.render,
    "评测中心": evaluation.render,
    "对话助手": chat.render,
}
selected = st.sidebar.radio("导航", list(PAGES), key="active_page")
PAGES[selected](container)
```

- [ ] **Step 5: Implement dashboard summary and garment-card components**

`dashboard.render` must show:

- title `StyleMate 智能衣橱`
- demo-mode information banner
- garment count
- category count
- one deterministic daily sample recommendation
- buttons that set `active_page` to `我的衣橱` or `智能搭配`

The sidebar must also show a compact personal-profile summary and an edit popover for height, weight, fit, style, color, common scene, and body features. Saving the explicit form calls `ProfileService.replace`; automatic extraction elsewhere calls `merge`, whose conflicts are shown rather than silently overwritten.

`ui/components.py` must expose `render_garment_card(garment: Garment)` and escape user-controlled text before inserting custom HTML.

- [ ] **Step 6: Implement wardrobe upload, correction, filtering, editing, and deletion**

`wardrobe.render` must:

1. Filter cards by category, color, season, and style.
2. Use `st.file_uploader` with `type=["jpg", "jpeg", "png", "webp"]`.
3. Run the onboarding Skill only after pressing `AI 识别`.
4. Render every draft field in an editable form.
5. Call `save_confirmed` only after pressing `确认并加入衣橱`.
6. Show duplicate and manual-entry outcomes explicitly.
7. Require a second click in a confirmation popover before deletion.

- [ ] **Step 7: Add AppTests for seeded cards and manual fallback**

```python
# tests/ui/test_wardrobe_page.py
from repositories.session import SessionWardrobeRepository
from ui.state import seed_demo_repository


def test_demo_repository_seeds_six_garments():
    repository = SessionWardrobeRepository({})
    seed_demo_repository(repository, "visitor-test")
    items = repository.list_garments("visitor-test")
    assert len(items) == 6
    assert {item.id for item in items} >= {
        "sample-shirt-white",
        "sample-trench-beige",
        "sample-loafers-black",
    }
```

Use a fake onboarding Skill in the page-container fixture so UI tests never call DashScope.

- [ ] **Step 8: Run all UI and earlier tests**

Run:

```powershell
python -m pytest tests/ui tests/domain tests/repositories tests/services/test_wardrobe_service.py tests/skills/test_wardrobe_onboarding.py -v
```

Expected: dashboard loads without login in demo mode, six sample garments are present, and no external API is called.

- [ ] **Step 9: Commit Task 4**

```powershell
git add app.py ui tests/ui
git commit -m "feat: add demo-first wardrobe workbench"
```

---

### Task 5: Inventory-Grounded Outfit Planning Skill

**Files:**
- Create: `gateways/context.py`
- Create: `gateways/outfit_generator.py`
- Create: `rules/__init__.py`
- Create: `rules/outfit_rules.py`
- Create: `services/outfit_service.py`
- Create: `skills/outfit_planning.py`
- Test: `tests/rules/test_outfit_rules.py`
- Test: `tests/skills/test_outfit_planning.py`
- Test: `tests/services/test_outfit_service.py`

**Interfaces:**
- Consumes: repository, profile service, existing weather and RAG functions
- Produces: `WeatherGateway.get(city: str | None) -> str`
- Produces: `KnowledgeGateway.search(query: str) -> tuple[str, list[str]]`
- Produces: `OutfitGenerator.generate(payload: dict) -> list[dict]`
- Produces: `RuleOutfitPlanner.plan(request, garments) -> list[OutfitRecommendation]`
- Produces: `OutfitPlanningSkill.run(owner_id, request) -> SkillOutcome`
- Produces: `OutfitPlanningSkill(repository, profile_service, weather, knowledge, generator, rule_planner)`

- [ ] **Step 1: Write a deterministic fallback-rule test**

```python
# tests/rules/test_outfit_rules.py
def test_rule_planner_uses_only_inventory(sample_garments):
    request = OutfitRequest(scene="面试", style_preference="通勤")
    outfits = RuleOutfitPlanner().plan(request, sample_garments)
    inventory_ids = {item.id for item in sample_garments}
    assert outfits
    assert all(set(outfit.garment_ids) <= inventory_ids for outfit in outfits)
    assert all(outfit.constraint_checks["inventory"] for outfit in outfits)
```

- [ ] **Step 2: Write Skill tests for normal output, hallucinated IDs, and three fallback paths**

```python
# tests/skills/test_outfit_planning.py
from demo.sample_data import sample_garments
from domain.models import OutfitRecommendation, OutfitRequest
from rules.outfit_rules import RuleOutfitPlanner
from services.profile_service import ProfileService
from skills.outfit_planning import OutfitPlanningSkill


class FakeGenerator:
    def __init__(self, response):
        self.response = response

    def generate(self, payload):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class StaticWeather:
    def get(self, city):
        return "武汉：多云，22°C"


class StaticKnowledge:
    def search(self, query):
        return "面试穿搭应保持整洁、低饱和。", ["style_guide.txt"]


def build_skill(repo, generator):
    for garment in sample_garments():
        repo.save_garment("u1", garment)
    return OutfitPlanningSkill(
        repository=repo,
        profile_service=ProfileService(repo),
        weather=StaticWeather(),
        knowledge=StaticKnowledge(),
        generator=generator,
        rule_planner=RuleOutfitPlanner(),
    )


def test_skill_rejects_unknown_ids_and_keeps_valid_candidates(repo):
    generator = FakeGenerator([
        {"id": "bad", "garment_ids": ["not-owned"], "score": 99, "reason": "错误", "constraint_checks": {}},
        {"id": "good", "garment_ids": ["sample-shirt-white", "sample-skirt-gray"], "score": 90, "reason": "正式", "constraint_checks": {}},
    ])
    outcome = build_skill(repo, generator).run("u1", OutfitRequest(scene="面试"))
    ids = [OutfitRecommendation.model_validate(item).id for item in outcome.data["outfits"]]
    assert ids == ["good"]


def test_skill_uses_rules_when_generator_times_out(repo):
    outcome = build_skill(repo, FakeGenerator(TimeoutError())).run(
        "u1", OutfitRequest(scene="通勤")
    )
    assert outcome.status == "fallback"
    assert outcome.data["outfits"]
    assert "规则" in outcome.user_message
```

Also add tests that weather failure keeps planning active and RAG empty results produce `knowledge_sources=[]`.

- [ ] **Step 3: Run focused tests and verify missing implementations**

Run:

```powershell
python -m pytest tests/rules/test_outfit_rules.py tests/skills/test_outfit_planning.py -v
```

Expected: collection fails because planner and Skill modules do not exist.

- [ ] **Step 4: Implement gateway protocols and adapters**

`WeatherGateway` wraps `resolve_user_city` and `fetch_weather_text` from `agent.tools.agent_tools`, applies a 5-second HTTP timeout inside the underlying request path, and raises `ContextUnavailable` for failed responses.

`KnowledgeGateway` wraps `RagSummarizeService.retriever_docs`, returns joined content plus source labels derived from document metadata, and returns `("", [])` for no documents.

`OutfitGenerator` sends a JSON-only request containing:

```python
{
    "request": request.model_dump(mode="json"),
    "profile": profile,
    "weather": weather_text,
    "knowledge": knowledge_text,
    "garments": [garment.model_dump(mode="json") for garment in candidates],
}
```

It may return only 2 to 3 objects matching `OutfitRecommendation` fields.
The adapter must construct without a key and raise typed `GenerationUnavailable` on `generate`; the Skill then uses `RuleOutfitPlanner`.

- [ ] **Step 5: Implement the rule planner**

Rules must:

- group garments into `上装`, `下装`, `外套`, and `鞋履`
- prefer `通勤` or `简约` style for `通勤` and `面试`
- choose at most one item from each group
- omit an empty group instead of inventing an item
- return one recommendation when inventory is insufficient for two distinct sets
- set `score=60`, `knowledge_sources=[]`, and `constraint_checks={"inventory": True, "rule_fallback": True}`

- [ ] **Step 6: Implement Skill validation and tracing**

`OutfitPlanningSkill.run` must:

1. Load profile and wardrobe snapshot.
2. Return `failed` with a user-facing “先添加衣物” message when inventory is empty.
3. Obtain weather and record a fallback when unavailable.
4. Filter candidate inventory by season and scene without removing every item.
5. Retrieve knowledge and keep empty sources honest.
6. Call the generator with one retry for malformed output.
7. Validate every output through `OutfitRecommendation`.
8. Reject any candidate containing an unknown garment ID.
9. Use `RuleOutfitPlanner` if no valid candidate remains.
10. Return sorted results and a redacted `AgentTrace`.

- [ ] **Step 7: Implement `OutfitService`**

`OutfitService.plan(owner_id, request)` delegates to the Skill. `favorite` saves `FavoriteOutfit`. `feedback` accepts only these fixed reasons plus optional note:

```python
ALLOWED_FEEDBACK_REASONS = {
    "颜色不喜欢",
    "不适合场景",
    "不符合天气",
    "版型不适合",
    "想换一件单品",
}
```

- [ ] **Step 8: Run all Task 5 tests**

Run:

```powershell
python -m pytest tests/rules tests/skills/test_outfit_planning.py tests/services/test_outfit_service.py -v
```

Expected: unknown inventory IDs never reach returned recommendations and all three fallback tests pass.

- [ ] **Step 9: Commit Task 5**

```powershell
git add gateways rules services/outfit_service.py skills/outfit_planning.py tests/rules tests/skills/test_outfit_planning.py tests/services/test_outfit_service.py
git commit -m "feat: add inventory-grounded outfit planning skill"
```

---

### Task 6: Stylist Results, Favorites, Feedback, and Agent Trace UI

**Files:**
- Create: `ui/pages/stylist.py`
- Create: `ui/pages/favorites.py`
- Create: `tests/ui/fixtures/stylist_components_app.py`
- Modify: `ui/components.py`
- Modify: `ui/state.py`
- Test: `tests/ui/test_stylist_page.py`
- Test: `tests/ui/test_favorites_page.py`

**Interfaces:**
- Consumes: `OutfitService`, `OutfitRequest`, `OutfitRecommendation`, `AgentTrace`
- Produces: `render_outfit_card`, `render_agent_trace`, `render_feedback_form`
- Produces: session keys `latest_outfits`, `latest_trace`

- [ ] **Step 1: Write component tests using Streamlit AppTest fixtures**

```python
# tests/ui/test_stylist_page.py
from streamlit.testing.v1 import AppTest


def test_stylist_renders_inventory_items_and_trace():
    at = AppTest.from_file("tests/ui/fixtures/stylist_components_app.py").run()
    assert not at.exception
    assert any("白色衬衫" in markdown.value for markdown in at.markdown)
    assert any("执行轨迹" in expander.label for expander in at.expander)
```

The fixture app creates one known recommendation referencing two sample garment IDs and a five-step trace:

```python
# tests/ui/fixtures/stylist_components_app.py
from domain.models import AgentTrace, AgentTraceStep, OutfitRecommendation
from demo.sample_data import sample_garments
from ui.components import render_agent_trace, render_outfit_card

garments = {item.id: item for item in sample_garments()}
recommendation = OutfitRecommendation(
    id="fixture-outfit",
    garment_ids=["sample-shirt-white", "sample-skirt-gray"],
    score=90,
    reason="适合正式面试",
    constraint_checks={"inventory": True, "scene": True},
)
trace = AgentTrace(
    skill_name="OutfitPlanningSkill",
    steps=[
        AgentTraceStep(name=name, status="success", summary=name, duration_ms=1)
        for name in ["理解需求", "获取上下文", "筛选库存", "检索知识", "生成并校验"]
    ],
    duration_ms=5,
    status="success",
)
render_outfit_card(recommendation, garments)
render_agent_trace(trace)
```

- [ ] **Step 2: Run the page tests and verify missing renderer failure**

Run:

```powershell
python -m pytest tests/ui/test_stylist_page.py tests/ui/test_favorites_page.py -v
```

Expected: imports fail because the pages are not implemented.

- [ ] **Step 3: Implement the planning form**

The form includes:

- required scene select with `通勤`, `面试`, `约会`, `旅行`, `日常休闲`
- optional target date
- optional city
- optional style preference
- multiselect extra constraints

On submission, create `OutfitRequest`, call `OutfitService.plan`, store serialized results in session state, and render the Skill user message.

- [ ] **Step 4: Implement structured outfit cards**

Each card must resolve `garment_ids` through the repository and render:

- stored garment names and images
- score
- reason
- weather note
- constraint-check badges
- knowledge-source labels
- favorite button
- feedback popover

If resolution unexpectedly fails, render “该搭配已失效” and do not display a fabricated garment.

- [ ] **Step 5: Implement redacted trace rendering**

`render_agent_trace` uses a collapsed `st.expander("查看 Agent 执行轨迹")`. It renders only step name, status, summary, duration, tool name, and fallback label. Before rendering, reject any string containing `DASHSCOPE_API_KEY`, `AMAP_API_KEY`, `data:image/`, or `system prompt`.

- [ ] **Step 6: Implement favorites and feedback pages**

Favorites list comes from the repository. Feedback must require at least one fixed reason or a non-empty note. Public demo state remains isolated by owner ID.

- [ ] **Step 7: Run UI and service tests**

Run:

```powershell
python -m pytest tests/ui/test_stylist_page.py tests/ui/test_favorites_page.py tests/services/test_outfit_service.py -v
```

Expected: cards resolve only real inventory, traces start collapsed, and favorites are owner-isolated.

- [ ] **Step 8: Commit Task 6**

```powershell
git add ui tests/ui/test_stylist_page.py tests/ui/test_favorites_page.py
git commit -m "feat: add stylist results and explainable traces"
```

---

### Task 7: Offline Evaluation and Evaluation Center

**Files:**
- Create: `evaluation/__init__.py`
- Create: `evaluation/cases/outfit_cases.json`
- Create: `evaluation/cases/failure_cases.json`
- Create: `evaluation/garments/manifest.json`
- Create: `evaluation/runner.py`
- Create: `evaluation/cli.py`
- Create: `ui/pages/evaluation.py`
- Test: `tests/evaluation/test_runner.py`
- Test: `tests/ui/test_evaluation_page.py`

**Interfaces:**
- Consumes: both Skills and their typed outputs
- Produces: `EvaluationRunner.run() -> EvaluationReport`
- Produces: `EvaluationRunner.with_deterministic_fakes() -> EvaluationRunner`
- Produces: `EvaluationRunner.run_failure_case(dependency, behavior) -> SkillOutcome`
- Produces: JSON artifact at `artifacts/evaluation.json`
- Produces: metrics `required_field_completeness`, `manual_correction_rate`, `inventory_truth_rate`, `constraint_pass_rate`, `failure_recovery_rate`, and `latency_ms`

- [ ] **Step 1: Create exact outfit and failure case schemas**

Each outfit case in `outfit_cases.json` must contain:

```json
{
  "id": "interview-cool-weather",
  "request": {"scene": "面试", "city": "武汉", "style_preference": "通勤"},
  "required_categories": ["上装", "下装"],
  "required_checks": ["inventory"],
  "forbidden_styles": ["运动"]
}
```

Create at least 10 cases covering all five supported scenes. `failure_cases.json` contains exactly these failure injections:

```json
[
  {"id": "vision-timeout", "dependency": "vision", "behavior": "timeout"},
  {"id": "vision-invalid-json", "dependency": "vision", "behavior": "invalid_json"},
  {"id": "weather-timeout", "dependency": "weather", "behavior": "timeout"},
  {"id": "rag-empty", "dependency": "knowledge", "behavior": "empty"},
  {"id": "text-timeout", "dependency": "generator", "behavior": "timeout"},
  {"id": "missing-secrets", "dependency": "runtime", "behavior": "no_keys"}
]
```

- [ ] **Step 2: Define the 15-image manifest**

`manifest.json` contains these original-image filenames and expected core labels:

```json
[
  {"file":"white-shirt.webp","category":"上装","primary_color":"白色"},
  {"file":"black-tshirt.webp","category":"上装","primary_color":"黑色"},
  {"file":"cream-cardigan.webp","category":"上装","primary_color":"奶油色"},
  {"file":"navy-blazer.webp","category":"外套","primary_color":"藏青"},
  {"file":"beige-trench.webp","category":"外套","primary_color":"米色"},
  {"file":"denim-jacket.webp","category":"外套","primary_color":"蓝色"},
  {"file":"blue-jeans.webp","category":"下装","primary_color":"蓝色"},
  {"file":"gray-trousers.webp","category":"下装","primary_color":"深灰"},
  {"file":"black-skirt.webp","category":"下装","primary_color":"黑色"},
  {"file":"white-sneakers.webp","category":"鞋履","primary_color":"白色"},
  {"file":"black-loafers.webp","category":"鞋履","primary_color":"黑色"},
  {"file":"brown-boots.webp","category":"鞋履","primary_color":"棕色"},
  {"file":"red-dress.webp","category":"连衣裙","primary_color":"红色"},
  {"file":"floral-dress.webp","category":"连衣裙","primary_color":"多色"},
  {"file":"green-hoodie.webp","category":"上装","primary_color":"绿色"}
]
```

Use original images created for this project, resize each to at most 768×768, strip metadata, and keep each below 300 KB. Do not download copyrighted retail catalog images.

- [ ] **Step 3: Write metric-calculation tests**

```python
# tests/evaluation/test_runner.py
def test_inventory_truth_rate_counts_unknown_ids():
    report = EvaluationRunner.compute_outfit_metrics(
        inventory_ids={"g1", "g2"},
        recommendations=[
            {"garment_ids": ["g1", "g2"], "constraint_checks": {"inventory": True}},
            {"garment_ids": ["g1", "ghost"], "constraint_checks": {"inventory": False}},
        ],
    )
    assert report.inventory_truth_rate == 0.75


def test_failure_recovery_requires_structured_outcome():
    assert EvaluationRunner.is_recovered({"status": "fallback", "data": {"outfits": []}})
    assert not EvaluationRunner.is_recovered(RuntimeError("stack trace"))
```

- [ ] **Step 4: Run evaluation tests and verify failure**

Run:

```powershell
python -m pytest tests/evaluation/test_runner.py -v
```

Expected: import fails because the runner does not exist.

- [ ] **Step 5: Implement evaluation report and runner**

Define `MetricSummary` with float fields `required_field_completeness`, `manual_correction_rate`, `inventory_truth_rate`, `constraint_pass_rate`, `failure_recovery_rate`, and `latency_ms`. Define `EvaluationReport` with `mode`, `model_names`, `metrics: MetricSummary`, and `case_results`. `compute_outfit_metrics` returns `MetricSummary`.

Use Pydantic models for per-case results and aggregate metrics. Measure latency with `time.perf_counter`. The runner accepts injected fake or live gateways. Default CLI mode is `mock`, which is deterministic and free; `--live` requires configured secrets and records model names.

`python -m evaluation.cli --output artifacts/evaluation.json` must create parent directories, write UTF-8 JSON, print a compact metric table, and exit nonzero if `inventory_truth_rate < 1.0` or any failure case is unrecovered.

- [ ] **Step 6: Implement the evaluation page**

The page must:

- label results as `模拟评测` or `实时评测`
- require an explicit button press
- display actual metric values from the report
- list failing case IDs
- never show a success percentage before a run completes
- allow downloading the JSON artifact

- [ ] **Step 7: Run mock evaluation and UI tests**

Run:

```powershell
python -m pytest tests/evaluation tests/ui/test_evaluation_page.py -v
python -m evaluation.cli --output artifacts/evaluation.json
```

Expected: tests pass, the command exits 0, and `inventory_truth_rate` is `1.0` in deterministic mock mode.

- [ ] **Step 8: Commit Task 7**

```powershell
git add evaluation ui/pages/evaluation.py tests/evaluation tests/ui/test_evaluation_page.py
git commit -m "feat: add reproducible StyleMate evaluation"
```

Do not commit `artifacts/evaluation.json`; it is generated evidence.

---

### Task 8: Auxiliary Chat Integration and Full Failure Hardening

**Files:**
- Create: `ui/pages/chat.py`
- Modify: `agent/react_agent.py`
- Modify: `agent/tools/agent_tools.py`
- Modify: `ui/state.py`
- Test: `tests/agent/test_chat_skill_routing.py`
- Test: `tests/integration/test_failure_matrix.py`

**Interfaces:**
- Consumes: both Skills and existing Agent tools
- Produces: `build_skill_tools(owner_id_provider, outfit_skill) -> list[BaseTool]`
- Produces: registered chat tools `plan_from_my_wardrobe` and `describe_wardrobe_onboarding`
- Produces: an integration failure matrix proving every external dependency has a structured fallback

- [ ] **Step 1: Write routing tests**

```python
# tests/agent/test_chat_skill_routing.py
from agent.react_agent import build_skill_tools
from domain.models import AgentTrace, SkillOutcome


class SpyOutfitSkill:
    def __init__(self):
        self.calls = 0
        self.owner_ids = []

    def run(self, owner_id, request):
        self.calls += 1
        self.owner_ids.append(owner_id)
        return SkillOutcome(
            status="fallback",
            data={"outfits": []},
            trace=AgentTrace(
                skill_name="OutfitPlanningSkill",
                steps=[],
                duration_ms=0,
                status="fallback",
            ),
            user_message="规则搭配结果",
        )


def test_outfit_tool_uses_active_owner_and_planning_skill():
    skill = SpyOutfitSkill()
    tools = build_skill_tools(lambda: "visitor-1", skill)
    planning_tool = next(tool for tool in tools if tool.name == "plan_from_my_wardrobe")
    result = planning_tool.invoke({"scene": "面试", "city": "武汉", "style": "通勤"})
    assert skill.calls == 1
    assert skill.owner_ids == ["visitor-1"]
    assert "outfits" in result
```

- [ ] **Step 2: Add Skill wrappers to the auxiliary Agent**

Expose two typed tool wrappers:

```python
@tool
def plan_from_my_wardrobe(scene: str, city: str = "", style: str = "") -> str:
    """Use the active user's stored wardrobe and OutfitPlanningSkill."""


@tool
def describe_wardrobe_onboarding() -> str:
    """Explain that image upload and confirmation happen on the wardrobe page."""
```

The chat tool must not accept arbitrary owner IDs. Resolve the active owner through the dependency container.

- [ ] **Step 3: Render chat without a mandatory public login**

In demo mode, store messages in session state. In local mode, existing chat history may be loaded only for an authenticated existing user; unauthenticated local use falls back to session messages rather than blocking the page.

- [ ] **Step 4: Build the full failure matrix**

```python
# tests/integration/test_failure_matrix.py
import pytest
from evaluation.runner import EvaluationRunner


@pytest.mark.parametrize(
    "dependency,behavior",
    [
        ("vision", "timeout"),
        ("vision", "invalid_json"),
        ("weather", "timeout"),
        ("knowledge", "empty"),
        ("generator", "timeout"),
        ("runtime", "no_keys"),
    ],
)
def test_external_failure_returns_safe_outcome(dependency, behavior):
    runner = EvaluationRunner.with_deterministic_fakes()
    outcome = runner.run_failure_case(dependency, behavior)
    assert outcome.status in {"needs_review", "fallback"}
    assert outcome.user_message
    assert "Traceback" not in outcome.user_message
```

- [ ] **Step 5: Add trace-redaction integration assertions**

Inject strings containing fake secrets, `data:image/`, and `system prompt` into fake gateway errors. Assert none appear in serialized `AgentTrace` or rendered UI.

- [ ] **Step 6: Run the Agent and integration suites**

Run:

```powershell
python -m pytest tests/agent tests/integration -v
```

Expected: all dependency failures produce safe structured outcomes and no secret marker is rendered.

- [ ] **Step 7: Commit Task 8**

```powershell
git add agent ui/pages/chat.py ui/state.py tests/agent tests/integration
git commit -m "feat: integrate skills with auxiliary chat"
```

---

### Task 9: Deployment, Documentation, Measured Resume Entry, and Final Verification

**Files:**
- Create: `.streamlit/config.toml`
- Create: `evaluation/render_resume_entry.py`
- Create: `tests/smoke/test_public_demo.py`
- Modify: `README.md`
- Modify: `requirements.txt`
- Modify: `docs/resume/stylemate.md` through the renderer

**Interfaces:**
- Consumes: completed app and `artifacts/evaluation.json`
- Produces: public Streamlit URL, reproducible README, measured resume entry

- [ ] **Step 1: Add a public-demo smoke test**

```python
# tests/smoke/test_public_demo.py
from streamlit.testing.v1 import AppTest


def test_public_demo_core_pages_without_secrets(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("AMAP_API_KEY", raising=False)
    at = AppTest.from_file("app.py").run(timeout=30)
    assert not at.exception
    assert at.title[0].value == "StyleMate 智能衣橱"
    assert any("示例衣橱" in item.value for item in at.info)
```

- [ ] **Step 2: Add Streamlit configuration**

```toml
# .streamlit/config.toml
[theme]
primaryColor = "#3C6F47"
backgroundColor = "#FBFAF7"
secondaryBackgroundColor = "#F2EEE8"
textColor = "#27312A"
font = "sans serif"

[server]
maxUploadSize = 8
headless = true

[browser]
gatherUsageStats = false
```

- [ ] **Step 3: Generate the resume entry from measured metrics**

`evaluation/render_resume_entry.py` must read the evaluation JSON and write `docs/resume/stylemate.md` using real values:

```python
payload = json.loads(input_path.read_text(encoding="utf-8"))
metrics = payload["metrics"]
text = (
    "StyleMate 智能衣橱｜AI 应用开发\n"
    f"- 设计 WardrobeOnboarding 与 OutfitPlanning 两个可组合 Agent Skills，"
    f"编排多模态识别、RAG、天气与用户画像，离线评测库存真实性"
    f"{metrics['inventory_truth_rate']:.1%}。\n"
    f"- 通过 Pydantic 结构化输出、真实库存 ID 校验与规则降级，"
    f"实现外部服务失败恢复率 {metrics['failure_recovery_rate']:.1%}，"
    f"并提供可脱敏的 Agent 执行轨迹。\n"
)
```

The script exits nonzero if the evaluation file is absent, if `inventory_truth_rate < 1.0`, or if required metric keys are missing.

- [ ] **Step 4: Rewrite README around verifiable evidence**

README sections, in order:

1. public demo link and screenshot
2. 30–60 second quick experience
3. user workflow
4. architecture diagram
5. two Agent Skill definitions
6. structured-output and fallback strategy
7. actual evaluation command and result table
8. local setup
9. Streamlit Secrets example with empty values
10. tests
11. known limitations

Do not describe sample fallback as a live model call.

- [ ] **Step 5: Run complete local verification**

Run:

```powershell
python -m pytest -v
python -m evaluation.cli --output artifacts/evaluation.json
python -m evaluation.render_resume_entry --input artifacts/evaluation.json --output docs/resume/stylemate.md
python -m compileall agent config demo domain evaluation gateways repositories rules services skills ui
git diff --check
```

Expected: tests and compilation pass, evaluation exits 0, the resume entry contains numeric metrics, and `git diff --check` prints nothing.

- [ ] **Step 6: Perform a local Streamlit smoke run**

Run:

```powershell
$env:APP_MODE="demo"
python -m streamlit run app.py --server.headless true --server.port 8501
```

Verify in the browser:

- overview loads without login
- six sample garments appear
- a sample outfit can be generated without secrets
- wardrobe and stylist pages show explicit demo labels
- Agent trace is collapsed and contains no sensitive strings
- evaluation center runs mock cases

Stop the local server after verification.

- [ ] **Step 7: Inspect the repository before public deployment**

Run:

```powershell
git status --short
git grep -n -I -E "DASHSCOPE_API_KEY=.+|AMAP_API_KEY=.+" -- . ":!docs/superpowers"
git ls-files data/uploads data/stylemate.db .streamlit/secrets.toml
```

Expected: no real key values are found and no local database, upload, or secrets file is tracked.

- [ ] **Step 8: Commit final application documentation**

```powershell
git add .streamlit/config.toml README.md docs/resume/stylemate.md evaluation/render_resume_entry.py tests/smoke requirements.txt
git commit -m "docs: prepare StyleMate public demo"
```

- [ ] **Step 9: Push the completed branch and deploy on Streamlit Community Cloud**

Push only after the user has reviewed the final diff. In Streamlit Community Cloud:

- select repository `yinzuosheng/StyleMate`
- select the completed branch
- set entry point `app.py`
- set Python 3.11
- configure `APP_MODE="demo"`, `DASHSCOPE_API_KEY`, `AMAP_API_KEY`, `VISION_MODEL_NAME`, and `TEXT_MODEL_NAME` in Secrets
- deploy and wait for a healthy application URL

- [ ] **Step 10: Verify the deployed URL in a fresh unauthenticated session**

Repeat the five browser checks from Step 6. Trigger one live visual recognition request, one live outfit request, and one no-secret/sample path. Record only measured results and the final URL in README, then commit and push that README update.

- [ ] **Step 11: Final repository and evidence check**

Run:

```powershell
python -m pytest -v
python -m evaluation.cli --output artifacts/evaluation.json
git status --short
git log --oneline -10
```

Expected: the full test suite passes, evaluation exits 0 with inventory truth `1.0`, only intentionally untracked local artifacts remain, and the task commits appear in order.
