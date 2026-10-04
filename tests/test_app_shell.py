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

APP = repo_root() / "app" / "streamlit_app.py"
TIMEOUT_SECONDS = 60


@pytest.fixture(scope="module")
def app() -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=TIMEOUT_SECONDS)
    at.run()
    return at


def test_app_runs_without_exceptions(app):
    assert not app.exception


def test_app_shows_the_four_views_in_order(app):
    assert [tab.label for tab in app.tabs] == list(VIEWS) == ["Overview", "Why", "Validation", "Scenarios & Sources"]


def test_headline_comes_from_the_synthetic_json(app):
    values = {metric.label: metric.value for metric in app.metric}
    document = json.loads(synthetic_path().read_text(encoding="utf-8"))
    headline = document["headline"]["net_pct"]
    assert values["Headline, net of incentives"] == f"{headline:.1f} %"


def test_synthetic_banner_is_shown(app):
    assert any("SYNTHETIC" in warning.value for warning in app.warning)


def test_reads_only_the_synthetic_file():
    """The app must never point at CRM outputs or the real aggregates file."""
    source = APP.read_text(encoding="utf-8")
    for forbidden in ("outputs/private", "data/private", "aggregates.json\"", "requests", "httpx", "urllib", "anthropic"):
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
