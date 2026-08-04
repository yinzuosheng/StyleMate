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
