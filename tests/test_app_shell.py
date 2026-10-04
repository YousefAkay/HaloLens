"""Tests for app/streamlit_app.py (I-11a). Owner: INT.

The app runs headlessly through Streamlit's AppTest on the synthetic aggregates file. No browser, no network.
"""

from __future__ import annotations

import copy
import html
import json

import jsonschema
import pytest
from streamlit.testing.v1 import AppTest

from leaselens.config import repo_root
from app.streamlit_app import VIEWS, load_aggregates, synthetic_path
from app import narrative, streamlit_app

APP = repo_root() / "app" / "streamlit_app.py"
TIMEOUT_SECONDS = 60


@pytest.fixture(scope="module")
def app() -> AppTest:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(narrative, "get_client", lambda: None)
        at = AppTest.from_file(str(APP), default_timeout=TIMEOUT_SECONDS)
        at.run()
        return at


def test_app_runs_without_exceptions(app):
    assert not app.exception


def test_page_shows_the_seven_tabs_in_order_and_a_sidebar(app):
    """Seven tabs in story order (the app opens in French), the controls in the sidebar, no anchor navigation."""
    from app.ui import t

    assert list(VIEWS) == ["01 · Answer", "02 · Why", "03 · Validation", "04 · Scenario Lab", "05 · Buildings",
                           "06 · Questions", "07 · Sources"]
    assert [tab.label for tab in app.tabs] == [t(f"tab_{key}", "fr") for key in streamlit_app.TAB_KEYS]
    assert [radio.key for radio in app.sidebar.radio] == ["lang", "data_mode"]
    assert 'class="ll-nav"' not in "\n".join(element.value for element in app.markdown)


def test_headline_comes_from_the_synthetic_json(app):
    document = json.loads(synthetic_path().read_text(encoding="utf-8"))
    headline = document["headline"]["net_pct"]
    hero = next(element.value for element in app.markdown if 'class="ll-hero-number"' in element.value)
    assert f"{headline:.1f}" in hero


def test_synthetic_banner_is_shown(app):
    assert any("ll-notice" in element.value and "SYNTHÉTIQUE" in element.value for element in app.markdown)


def test_app_reads_only_the_aggregates_files_and_no_network_library():
    """Real mode reads only the gitignored aggregates file. The CRM folder and HTTP libraries never appear in the app;
    the Claude API is reached only through app/narrative.py."""
    source = APP.read_text(encoding="utf-8")
    assert "data/private" not in source
    for forbidden in ("requests", "httpx", "urllib", "import anthropic"):
        assert forbidden not in source, forbidden


def test_loader_accepts_the_synthetic_example():
    assert load_aggregates(synthetic_path())["mode"] == "synthetic"


def test_loader_rejects_a_non_conforming_file(tmp_path):
    document = json.loads(synthetic_path().read_text(encoding="utf-8"))
    tampered = copy.deepcopy(document)
    tampered["units"] = [{"unit_id": "123"}]
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(jsonschema.ValidationError):
        load_aggregates(path)


def _qa_view(document):
    from app.streamlit_app import ask_analysis_view

    ask_analysis_view(document, "en")              # NO_KEY_MESSAGES are the English texts; the app itself opens in French


@pytest.mark.parametrize("mode, cached, reason", [
    ("real", "SYNTHETIC CACHED TEXT: 99.9 %", "cache_synthetic_only"),
    ("synthetic", None, "cache_missing"),
    ("synthetic", "SYNTHETIC CACHED TEXT: 99.9 %", "cache_rejected"),
])
def test_no_key_qa_view_explains_unavailability_without_rendering_cache(monkeypatch, mode, cached, reason):
    document = json.loads(synthetic_path().read_text(encoding="utf-8"))
    document["mode"] = mode  # routing only: all values are invented, even when labelled real
    question = narrative.PRESET_QUESTIONS[0]
    monkeypatch.setattr(streamlit_app, "_client", lambda: None)
    monkeypatch.setattr(streamlit_app, "_notes", lambda: [])

    def load_cache():
        if mode == "real":
            pytest.fail("real-mode Q&A must not load the synthetic cache")
        return {question: cached} if cached is not None else {}

    monkeypatch.setattr(narrative, "load_preset_cache", load_cache)
    at = AppTest.from_function(_qa_view, args=(document,), default_timeout=TIMEOUT_SECONDS).run()
    at.button(key="pill_0").click().run()          # the first preset question, as a pill
    assert not at.exception
    page = html.unescape(" ".join(element.value for element in at.markdown))
    assert streamlit_app.NO_KEY_MESSAGES[reason] in page          # a plain paragraph, no info box
    assert not at.info
    assert "SYNTHETIC CACHED TEXT" not in page
    assert "Preset answers are not cached" not in page


def test_masthead_and_page_title_show_halo_lens(app):
    """I-16: the display name is Halo Lens in the masthead (both languages) and in the browser page title."""
    from app.ui import labels

    page = html.unescape(" ".join(element.value for element in app.markdown))
    assert "Halo Lens" in page and "LeaseLens" not in page
    assert labels.LABELS["en"]["app_title"] == labels.LABELS["fr"]["app_title"] == "Halo Lens"
    assert 'page_title="Halo Lens"' in APP.read_text(encoding="utf-8")
