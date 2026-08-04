from pathlib import Path

from streamlit.testing.v1 import AppTest

from demo.sample_data import sample_garments


def test_streamlit_app_starts_in_demo_mode(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"))

    app.run(timeout=20)

    assert not app.exception
    assert "StyleMate" in app.title[0].value
    assert [tab.label for tab in app.tabs] == ["今日搭配", "我的衣橱", "搭配助手", "关于项目"]


def test_sample_wardrobe_renders_all_cards_without_exception(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"))

    app.run(timeout=20)
    app.button(key="load_samples_today").click()
    app.run(timeout=20)

    assert not app.exception
    rendered = "\n".join(item.value for item in app.markdown)
    assert all(garment.name in rendered for garment in sample_garments())
