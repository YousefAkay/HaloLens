"""Tests for app/streamlit_app.py (I-11a). Owner: INT.

The app runs headlessly through Streamlit's AppTest on the synthetic aggregates file. No browser, no network.
"""

from __future__ import annotations

import copy
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


def test_app_shows_the_four_views_in_order(app):
    assert [tab.label for tab in app.tabs] == list(VIEWS) == [
        "Overview", "Why", "Validation", "Scenarios & Sources", "Ask the analysis", "By building"]


def test_headline_comes_from_the_synthetic_json(app):
    values = {metric.label: metric.value for metric in app.metric}
    document = json.loads(synthetic_path().read_text(encoding="utf-8"))
    headline = document["headline"]["net_pct"]
    assert values["Headline, net of incentives"] == f"{headline:.1f} %"


def test_synthetic_banner_is_shown(app):
    assert any("SYNTHÉTIQUE" in warning.value for warning in app.warning)


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

    ask_analysis_view(document)


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
    at.selectbox(key="preset").select(question).run()
    at.button(key="answer_go").click().run()
    assert not at.exception
    assert any(streamlit_app.NO_KEY_MESSAGES[reason] == info.value for info in at.info)
    assert all("SYNTHETIC CACHED TEXT" not in element.value for element in at.markdown)
    assert not any("Preset answers are not cached" in element.value for element in at.markdown)
    assert at.selectbox(key="lever_incentive").value == "zero"
    assert any("precomputed grid" in element.value for element in at.markdown)
