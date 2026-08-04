# StyleMate Resume-Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Finish StyleMate as a polished, publicly deployable master’s-level AI wardrobe project with one complete image-to-wardrobe-to-outfit workflow.

**Architecture:** Keep the completed typed domain, session/SQLite repositories, image stores, and garment onboarding workflow. Add one deterministic inventory-grounded outfit workflow, then replace the legacy login/chat-first Streamlit screen with a four-tab product demo. Finish with a ten-case offline evaluation, concise documentation, and public Streamlit deployment.

**Tech Stack:** Python 3.11, Streamlit 1.40, Pydantic 2, Pillow, DashScope vision integration, pytest, SQLite.

## Global Constraints

- This is a master’s-level personal project intended to be understandable and implementable in about five days.
- Preserve Streamlit; do not add FastAPI, Vue, React, a mobile client, training, fine-tuning, commerce, payment, or social features.
- Keep exactly two app modes: demo and local. Public deployment uses demo; local remains the default.
- Public demo data is session-local and requires no account registration.
- Accept only JPG/JPEG, PNG, and WebP uploads, with a maximum size of 8 MB.
- Every recommended garment ID must exist in the current owner’s candidate wardrobe.
- Missing model or weather configuration must produce a usable rule-based or manual fallback.
- Show only a short user-facing generation summary; do not build a trace center, monitoring system, or evaluation dashboard.
- Do not persist or display API keys, full prompts, raw image bytes, or private data in traces.
- README and résumé metrics must come only from the executed evaluation artifact.
- Stop after Tasks 4–6; do not expand the chat Agent, feedback analytics, authentication, or enterprise infrastructure.

---

## File Map

- rules/outfit_rules.py — deterministic inventory-grounded outfit combinations and scores.
- skills/outfit_planning.py — small workflow that loads the owner wardrobe, optionally reads weather, and returns SkillOutcome.
- ui/state.py — creates demo/local dependencies and provides sample-load/edit/delete helpers.
- ui/components.py — small reusable Streamlit garment, outfit, empty-state, and trace renderers.
- app.py — four-tab public product experience.
- evaluation/run_eval.py — executes ten fixed cases and writes the three approved metrics.
- evaluation/cases.json — deterministic evaluation inputs.
- tests/rules/test_outfit_rules.py — inventory and scoring invariants.
- tests/skills/test_outfit_planning.py — success, empty wardrobe, and weather fallback behavior.
- tests/ui/test_state.py — app dependency and sample-data behavior.
- tests/test_app_smoke.py — headless Streamlit smoke coverage.
- tests/evaluation/test_run_eval.py — artifact schema and metric provenance.
- .streamlit/config.toml — light visual theme and safe server defaults.
- docs/resume/stylemate-resume-entry.md — truthful résumé-ready project entry.

---

### Task 4: Inventory-Grounded Outfit Recommendation

**Files:**
- Create: rules/__init__.py
- Create: rules/outfit_rules.py
- Create: skills/outfit_planning.py
- Test: tests/rules/test_outfit_rules.py
- Test: tests/skills/test_outfit_planning.py

**Interfaces:**
- Consumes: Garment, OutfitRequest, OutfitRecommendation, SkillOutcome, WardrobeRepository.
- Produces: plan_outfits(request: OutfitRequest, garments: list[Garment], limit: int = 3) -> list[OutfitRecommendation].
- Produces: OutfitPlanningSkill(repository, weather_loader=None).
- Produces: OutfitPlanningSkill.run(owner_id: str, request: OutfitRequest) -> SkillOutcome.

- [ ] **Step 1: Write failing inventory-grounding tests**

~~~python
# tests/rules/test_outfit_rules.py
from domain.models import OutfitRequest
from rules.outfit_rules import plan_outfits


def test_plan_uses_only_candidate_inventory(sample_garments):
    candidates = sample_garments[:4]
    request = OutfitRequest(
        scene="通勤",
        style_preference="简约",
        candidate_garment_ids=[item.id for item in candidates],
    )
    results = plan_outfits(request, sample_garments)
    allowed = {item.id for item in candidates}
    assert 1 <= len(results) <= 3
    assert all(set(item.garment_ids) <= allowed for item in results)
    assert all(item.constraint_checks["inventory"] for item in results)


def test_plan_is_deterministic(sample_garments):
    request = OutfitRequest(scene="通勤")
    first = [item.model_dump(mode="json", exclude={"created_at"}) for item in plan_outfits(request, sample_garments)]
    second = [item.model_dump(mode="json", exclude={"created_at"}) for item in plan_outfits(request, sample_garments)]
    assert first == second
~~~

- [ ] **Step 2: Run the rule tests and capture RED**

Run:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest tests/rules/test_outfit_rules.py -v
~~~

Expected: collection fails because rules.outfit_rules does not exist.

- [ ] **Step 3: Implement the minimal deterministic planner**

rules/outfit_rules.py must:

- filter by candidate_garment_ids when the list is non-empty;
- sort garments by ID before combining them;
- require one 上装 and one 下装;
- add one 鞋履 and one 外套 only when available;
- create at most three unique combinations;
- score category completeness, requested style, and requested scene with a value from 0 to 100;
- build a deterministic recommendation ID from a SHA-1 hash of scene plus sorted garment IDs;
- set constraint_checks with exactly inventory, top_bottom, and style;
- never invent an ID or call a model.

Use these helpers and signatures:

~~~python
def plan_outfits(
    request: OutfitRequest,
    garments: list[Garment],
    limit: int = 3,
) -> list[OutfitRecommendation]: ...


def _matches_category(garment: Garment, label: str) -> bool:
    return label in garment.category


def _recommendation_id(scene: str, garment_ids: list[str]) -> str:
    payload = "|".join([scene, *sorted(garment_ids)])
    return "outfit-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
~~~

When no valid top-and-bottom combination exists, return an empty list.

- [ ] **Step 4: Run the rule tests to GREEN**

Run:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest tests/rules/test_outfit_rules.py -v
~~~

Expected: both tests pass.

- [ ] **Step 5: Write failing workflow tests**

~~~python
# tests/skills/test_outfit_planning.py
from domain.models import OutfitRequest
from skills.outfit_planning import OutfitPlanningSkill


def test_skill_returns_recommendations_from_owner_inventory(repo, sample_garments):
    for garment in sample_garments:
        repo.save_garment("u1", garment)
    outcome = OutfitPlanningSkill(repo).run("u1", OutfitRequest(scene="通勤"))
    allowed = {item.id for item in sample_garments}
    assert outcome.status == "success"
    assert outcome.data["recommendations"]
    assert all(
        set(item["garment_ids"]) <= allowed
        for item in outcome.data["recommendations"]
    )


def test_skill_keeps_rule_results_when_weather_fails(repo, sample_garments):
    for garment in sample_garments:
        repo.save_garment("u1", garment)

    def unavailable(city: str) -> str:
        raise TimeoutError(city)

    outcome = OutfitPlanningSkill(repo, weather_loader=unavailable).run(
        "u1",
        OutfitRequest(scene="通勤", city="杭州"),
    )
    assert outcome.status == "fallback"
    assert outcome.data["recommendations"]
    assert "天气" in outcome.user_message


def test_skill_explains_incomplete_wardrobe(repo):
    outcome = OutfitPlanningSkill(repo).run("u1", OutfitRequest(scene="通勤"))
    assert outcome.status == "fallback"
    assert outcome.data["recommendations"] == []
    assert "上装" in outcome.user_message and "下装" in outcome.user_message
~~~

- [ ] **Step 6: Implement the small planning workflow**

skills/outfit_planning.py must load repository.list_garments(owner_id), call plan_outfits, and return SkillOutcome. Weather is an optional injected callable with signature Callable[[str], str]. A weather error changes the outcome status to fallback but does not discard valid rule results.

The trace contains no more than three steps named load_wardrobe, weather, and plan_outfits. Its summaries contain no prompts, keys, raw weather payloads, or wardrobe details.

- [ ] **Step 7: Run focused and full verification**

Run:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest tests/rules/test_outfit_rules.py tests/skills/test_outfit_planning.py -v
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest -q
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m ruff check rules skills tests/rules tests/skills
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m compileall -q rules skills
~~~

- [ ] **Step 8: Commit Task 4**

~~~powershell
git add rules skills/outfit_planning.py tests/rules tests/skills/test_outfit_planning.py
git commit -m "feat: add inventory-grounded outfit planning"
~~~

---

### Task 5: Demo-First Streamlit Wardrobe Workbench

**Files:**
- Create: ui/__init__.py
- Create: ui/state.py
- Create: ui/components.py
- Modify: app.py
- Test: tests/ui/test_state.py
- Test: tests/test_app_smoke.py

**Interfaces:**
- Consumes: RuntimeSettings, repositories, image stores, WardrobeOnboardingSkill, OutfitPlanningSkill, sample_garments.
- Produces: AppContext with settings, owner_id, repository, image_store, wardrobe_service, onboarding_skill, and outfit_skill.
- Produces: build_context(state: dict, settings: RuntimeSettings, vision=None, weather_loader=None) -> AppContext.
- Produces: load_sample_wardrobe(context: AppContext) -> int.
- Produces: delete_garment(context: AppContext, garment_id: str) -> None.

- [ ] **Step 1: Write failing context and sample-loading tests**

~~~python
# tests/ui/test_state.py
from config.runtime import RuntimeSettings
from ui.state import build_context, load_sample_wardrobe


def settings(mode: str) -> RuntimeSettings:
    return RuntimeSettings(
        app_mode=mode,
        vision_model_name="vision-test",
        text_model_name="text-test",
    )


def test_demo_context_reuses_session_state():
    state = {}
    first = build_context(state, settings("demo"))
    second = build_context(state, settings("demo"))
    assert first.repository is second.repository
    assert first.image_store is second.image_store
    assert first.owner_id == "demo-user"


def test_sample_load_is_idempotent():
    context = build_context({}, settings("demo"))
    assert load_sample_wardrobe(context) == 6
    assert load_sample_wardrobe(context) == 0
    assert len(context.repository.list_garments(context.owner_id)) == 6
~~~

- [ ] **Step 2: Run the state tests and capture RED**

Run:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest tests/ui/test_state.py -v
~~~

Expected: collection fails because ui.state does not exist.

- [ ] **Step 3: Implement the dependency context**

ui/state.py must define:

~~~python
@dataclass
class AppContext:
    settings: RuntimeSettings
    owner_id: str
    repository: WardrobeRepository
    image_store: ImageStore
    wardrobe_service: WardrobeService
    onboarding_skill: WardrobeOnboardingSkill
    outfit_skill: OutfitPlanningSkill
~~~

For demo mode, cache SessionWardrobeRepository and SessionImageStore inside the passed state dictionary. For local mode, cache SQLiteWardrobeRepository(Path("data/stylemate.db")) and LocalImageStore(Path("data/uploads")). Use owner IDs demo-user and local-user respectively.

If vision is omitted, construct DashScopeVisionGateway(settings). If weather_loader is omitted, use a small callable that returns fetch_weather_text(city); do not add a new gateway layer.

load_sample_wardrobe saves only missing sample IDs and returns the number inserted. delete_garment removes an owned stored image when present, then removes the garment record.

- [ ] **Step 4: Create small UI renderers**

ui/components.py provides:

~~~python
def render_garment_card(garment: Garment, image_value=None) -> None: ...
def render_outfit_card(recommendation: OutfitRecommendation, garments: dict[str, Garment]) -> None: ...
def render_trace(trace: AgentTrace) -> None: ...
def render_empty_state(title: str, body: str) -> None: ...
~~~

Use Streamlit primitives and one compact CSS block. The trace renderer uses one expander titled 生成过程 and shows only step name, status, and summary.

- [ ] **Step 5: Replace the legacy app with the four-tab product flow**

app.py must:

1. load dotenv and RuntimeSettings;
2. set a wide Streamlit page with title StyleMate 衣橱管家;
3. build AppContext from st.session_state;
4. show tabs 今日搭配, 我的衣橱, 搭配助手, 关于项目;
5. offer an explicit 加载样例衣橱 button when the wardrobe is empty;
6. use st.file_uploader with type ["jpg", "jpeg", "png", "webp"];
7. run onboarding only after the user clicks 识别衣物;
8. store the returned draft and uploaded bytes in session state;
9. show a correction form for name, category, color, material, seasons, and styles;
10. call wardrobe_service.save_confirmed only after 确认入库;
11. show wardrobe filters for category and style, plus edit and delete controls;
12. create OutfitRequest from scene, city, and style fields and call outfit_skill.run;
13. render one to three recommendations and one short generation expander;
14. show the technology stack, demo/local behavior, privacy note, and evaluation metrics on 关于项目;
15. omit login, registration, chat history, feedback analytics, and evaluation-center UI.

The manual fallback uses the same correction form. Never place uploaded bytes or API values into visible trace text.
Because Task 6 has not produced artifacts/evaluation.json yet, the 关于项目 tab must show 评测将在发布前生成 when that file is absent, and load the three rates only when the file exists.

- [ ] **Step 6: Add a headless app smoke test**

~~~python
# tests/test_app_smoke.py
from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_in_demo_mode(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"))
    app.run(timeout=20)
    assert not app.exception
    assert "StyleMate" in app.title[0].value
~~~

- [ ] **Step 7: Verify the product flow**

Run:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest tests/ui/test_state.py tests/test_app_smoke.py -v
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest -q
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m ruff check app.py ui tests/ui tests/test_app_smoke.py
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m compileall -q app.py ui
~~~

Then run locally:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m streamlit run app.py --server.headless true
~~~

Use the in-app browser to verify sample loading, wardrobe cards, no-key manual fallback, recommendation rendering, and mobile-width readability.

- [ ] **Step 8: Commit Task 5**

~~~powershell
git add app.py ui tests/ui tests/test_app_smoke.py
git commit -m "feat: build StyleMate Streamlit workbench"
~~~

---

### Task 6: Lightweight Evaluation, Documentation, and Public Demo

**Files:**
- Create: evaluation/__init__.py
- Create: evaluation/cases.json
- Create: evaluation/run_eval.py
- Create: artifacts/evaluation.json
- Create: tests/evaluation/test_run_eval.py
- Create: .streamlit/config.toml
- Create: docs/assets/stylemate-main.png
- Create: docs/resume/stylemate-resume-entry.md
- Modify: .gitignore
- Modify: README.md

**Interfaces:**
- Consumes: sample_garments, OutfitRequest, plan_outfits, OutfitPlanningSkill.
- Produces: run_evaluation(output_path: Path) -> dict[str, float | int].
- Produces artifact keys: case_count, inventory_valid_rate, constraint_pass_rate, fallback_success_rate, generated_at.

- [ ] **Step 1: Add ten deterministic evaluation cases**

evaluation/cases.json contains exactly:

~~~json
[
  {"id": "commute-full", "scene": "通勤", "style_preference": "简约", "candidate_ids": ["sample-shirt-white", "sample-jeans-blue", "sample-trench-beige", "sample-loafers-black"], "expect_recommendation": true, "simulate_weather_failure": false},
  {"id": "commute-formal", "scene": "面试", "style_preference": "通勤", "candidate_ids": ["sample-shirt-white", "sample-skirt-gray", "sample-trench-beige", "sample-loafers-black"], "expect_recommendation": true, "simulate_weather_failure": false},
  {"id": "casual-weekend", "scene": "周末", "style_preference": "休闲", "candidate_ids": ["sample-cardigan-cream", "sample-jeans-blue", "sample-loafers-black"], "expect_recommendation": true, "simulate_weather_failure": false},
  {"id": "date-soft", "scene": "约会", "style_preference": "温柔", "candidate_ids": ["sample-cardigan-cream", "sample-skirt-gray", "sample-loafers-black"], "expect_recommendation": true, "simulate_weather_failure": false},
  {"id": "travel-layer", "scene": "旅行", "style_preference": "简约", "candidate_ids": ["sample-shirt-white", "sample-jeans-blue", "sample-trench-beige", "sample-loafers-black"], "expect_recommendation": true, "simulate_weather_failure": false},
  {"id": "minimal-pair", "scene": "日常", "style_preference": "简约", "candidate_ids": ["sample-shirt-white", "sample-jeans-blue"], "expect_recommendation": true, "simulate_weather_failure": false},
  {"id": "weather-timeout-commute", "scene": "通勤", "style_preference": "通勤", "candidate_ids": ["sample-shirt-white", "sample-skirt-gray", "sample-loafers-black"], "expect_recommendation": true, "simulate_weather_failure": true},
  {"id": "weather-timeout-casual", "scene": "出游", "style_preference": "休闲", "candidate_ids": ["sample-cardigan-cream", "sample-jeans-blue", "sample-loafers-black"], "expect_recommendation": true, "simulate_weather_failure": true},
  {"id": "incomplete-top-only", "scene": "通勤", "style_preference": "简约", "candidate_ids": ["sample-shirt-white"], "expect_recommendation": false, "simulate_weather_failure": false},
  {"id": "all-samples", "scene": "日常", "style_preference": "", "candidate_ids": ["sample-shirt-white", "sample-jeans-blue", "sample-trench-beige", "sample-loafers-black", "sample-cardigan-cream", "sample-skirt-gray"], "expect_recommendation": true, "simulate_weather_failure": false}
]
~~~

- [ ] **Step 2: Write the failing evaluation test**

~~~python
# tests/evaluation/test_run_eval.py
import json
from evaluation.run_eval import run_evaluation


def test_evaluation_writes_metrics_from_ten_cases(tmp_path):
    target = tmp_path / "evaluation.json"
    result = run_evaluation(target)
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert result == saved
    assert saved["case_count"] == 10
    for key in (
        "inventory_valid_rate",
        "constraint_pass_rate",
        "fallback_success_rate",
    ):
        assert 0.0 <= saved[key] <= 1.0
~~~

- [ ] **Step 3: Run the evaluation test and capture RED**

Run:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest tests/evaluation/test_run_eval.py -v
~~~

Expected: collection fails because evaluation.run_eval does not exist.

- [ ] **Step 4: Implement and execute the lightweight evaluator**

evaluation/run_eval.py loads the ten JSON cases and sample garments. For each case:

- construct OutfitRequest;
- call plan_outfits;
- count inventory validity only from returned garment IDs;
- count constraint success from the recommendation constraint_checks;
- for simulated weather failures, call OutfitPlanningSkill with a loader that raises TimeoutError and count fallback success when a usable SkillOutcome is returned;
- treat an expected empty result as a passed constraint case when expect_recommendation is false;
- round rates to four decimals;
- create the output parent directory and write UTF-8 indented JSON;
- use an ISO-8601 UTC generated_at value.

Run:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m evaluation.run_eval --output artifacts/evaluation.json
~~~

- [ ] **Step 5: Make the generated artifact intentionally trackable**

Replace the broad artifacts ignore rule with:

~~~gitignore
artifacts/*
!artifacts/evaluation.json
~~~

Do not commit uploaded images, SQLite files, keys, or Streamlit secrets.

- [ ] **Step 6: Add Streamlit deployment configuration**

.streamlit/config.toml contains:

~~~toml
[theme]
primaryColor = "#8B6F5A"
backgroundColor = "#FAF8F5"
secondaryBackgroundColor = "#F1ECE6"
textColor = "#2F2925"
font = "sans serif"

[server]
headless = true
maxUploadSize = 8
~~~

- [ ] **Step 7: Rewrite README and add the résumé entry**

README.md must contain:

- one-sentence project positioning;
- a screenshot placed at docs/assets/stylemate-main.png;
- the five-step user flow;
- a small architecture diagram showing Streamlit → onboarding/planning → repository/gateways;
- demo and local run commands using APP_MODE;
- environment variable table for APP_MODE, DASHSCOPE_API_KEY, AMAP_API_KEY, VISION_MODEL_NAME, and TEXT_MODEL_NAME;
- the exact three rates read from artifacts/evaluation.json;
- explicit limitations: no authentication, no cloud persistence, rule-based recommendation, external APIs optional;
- test command and the public demo URL after deployment.

docs/resume/stylemate-resume-entry.md contains a three-bullet Chinese résumé entry. It must accurately mention Streamlit, DashScope multimodal recognition, manual correction, inventory-grounded recommendation, fallback behavior, the executed evaluation case count/rates, and the public URL. It must not claim enterprise architecture, high concurrency, training, fine-tuning, or production scale.

- [ ] **Step 8: Capture the real product screenshot**

Start the app in demo mode, load sample data, open 我的衣橱, and capture a 1440-pixel-wide screenshot to docs/assets/stylemate-main.png. Use the browser inspection workflow; do not create a mock screenshot.

- [ ] **Step 9: Verify all local deliverables**

Run:

~~~powershell
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m pytest -q
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m ruff check .
& "C:\Users\Administrator\.conda\envs\LLM\python.exe" -m compileall -q .
git diff --check
~~~

Confirm that README metric values exactly equal artifacts/evaluation.json.

- [ ] **Step 10: Commit the deployable local deliverables**

~~~powershell
git add evaluation artifacts/evaluation.json tests/evaluation .streamlit/config.toml .gitignore README.md docs/assets/stylemate-main.png docs/resume/stylemate-resume-entry.md
git commit -m "docs: add StyleMate evaluation and deployment"
~~~

- [ ] **Step 11: Publish, verify, and record the demo URL**

Push the completed branch to the existing GitHub remote, deploy app.py with Streamlit Community Cloud, set APP_MODE=demo, and add only the optional provider keys through the platform secret UI. Open the public URL in a fresh browser session and verify:

- the app loads without registration;
- sample wardrobe works without provider keys;
- no visitor data is visible in a new session;
- outfit recommendations contain only displayed sample garment IDs;
- the URL is written exactly into README.md and docs/resume/stylemate-resume-entry.md.

Commit and push the verified URL:

~~~powershell
git add README.md docs/resume/stylemate-resume-entry.md
git commit -m "docs: publish StyleMate demo URL"
git push origin feat/stylemate-product-upgrade
~~~

---

## Completion Gate

The project is complete when Tasks 4–6 pass independent specification and quality review, the full test suite passes in the LLM environment, the actual browser screenshot is committed, and the public demo URL works in a fresh session. No additional product scope is added after this gate.
