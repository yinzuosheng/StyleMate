from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_in_demo_mode(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"))

    app.run(timeout=20)

    assert not app.exception
    assert "StyleMate" in app.title[0].value
