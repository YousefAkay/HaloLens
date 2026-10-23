"""Tests for app/narrative.py (I-12). Owner: INT.

No network: the Claude client is a fake that records what it was sent. Tests read the synthetic aggregates only.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

import app.narrative as narrative
from app import qa_answers
from app.number_guard import ungrounded_numbers
from halolens.config import load_config, repo_root
from halolens.contracts import INFORMATION_RULES

EXAMPLE = repo_root() / "outputs" / "public" / "aggregates_synthetic.json"


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class FakeClient:
    """Returns the scripted responses in order and records every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected extra API call")
        return self.responses.pop(0)


def text_response(text: str):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def tool_response(**arguments):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name="select_scenario", input=arguments)])


def _grounded_sentence(row: dict) -> str:
    return f"La hausse nette de ce scénario est de {row['headline_net_pct']:.1f} % (contractuelle : " \
           f"{row['headline_contract_pct']:.1f} %)."


# ---------------------------------------------------------------- privacy wall
def test_outbound_payload_passes_the_unit_level_check(doc):
    payload = narrative.privacy_payload(doc, "Quelle est la hausse ?", narrative.committed_notes())
    assert set(payload) == {"aggregates", "notes", "question"}


def test_outbound_payload_refuses_a_unit_level_field(doc):
    tampered = copy.deepcopy(doc)
    tampered["units"] = [{"unit_id": "123"}]
    with pytest.raises(ValueError):
        narrative.privacy_payload(tampered, "x", [])


def test_committed_notes_carry_no_real_data_numbers():
    for note in narrative.committed_notes():
        assert not narrative.REAL_NUMBER.search(note), note


def test_what_the_api_receives_has_no_unit_identifiers(doc):
    client = FakeClient(tool_response(incentive_shift="zero", renewal_shift="zero", newbuild_regime="exempt",
                                      information_rule="jan31"),
                        text_response(_grounded_sentence(narrative.scenario_row(doc, "zero", "zero", "exempt", "jan31"))))
    narrative.scenario_copilot("Quelle est la hausse ?", doc, client)
    polish_client = FakeClient(text_response("Le classement reste faible.\n- Trois années seulement.\n- Une année peut tout changer."))
    answer, sheet = qa_answers.compose("validation_backtest", doc, "fr")
    qa_answers.polish(answer, sheet, "Pourquoi le classement est-il faible ?", polish_client)
    client.calls.extend(polish_client.calls)
    for call in client.calls:
        sent = json.dumps(call, ensure_ascii=False, default=str).lower()
        for token in ("unit_id", "unit_code", "hunit", "sunitcode", "spropcode"):
            assert token not in sent


# ---------------------------------------------------------------- tool and grid
def test_tool_arguments_are_restricted_to_enums():
    schema = narrative.SELECT_TOOL["input_schema"]["properties"]
    assert set(schema["incentive_shift"]["enum"]) == {"minus", "zero", "plus"}
    assert set(schema["renewal_shift"]["enum"]) == {"minus", "zero", "plus"}
    assert set(schema["newbuild_regime"]["enum"]) == {"exempt", "guideline"}
    assert set(schema["information_rule"]["enum"]) == set(INFORMATION_RULES)


def test_invalid_tool_argument_stops_before_any_lookup(doc):
    client = FakeClient(tool_response(incentive_shift="huge", renewal_shift="zero", newbuild_regime="exempt",
                                      information_rule="jan31"))
    result = narrative.scenario_copilot("Quelle est la hausse ?", doc, client)
    assert result["status"] == "fallback" and result["row"] is None
    assert len(client.calls) == 1  # no description call was made


def test_grid_lookup_is_exact_and_complete(doc):
    rows = [row for row in doc["scenario_grid"] if row["model"] == narrative.REGULATED_MODEL_NAME]
    assert len(rows) == 3 * 3 * 2 * len(INFORMATION_RULES)  # incentive x renewal x new-build x information rule
    for row in rows:
        found = narrative.scenario_row(doc, row["incentive_shift"], row["renewal_shift"], row["newbuild_regime"],
                                       row["information_rule"])
        assert found == row
    champion = [row for row in doc["scenario_grid"] if row["model"] != narrative.REGULATED_MODEL_NAME]
    assert len(champion) == len(INFORMATION_RULES)
    assert all(row["incentive_shift"] == "none" for row in champion)


# ---------------------------------------------------------------- guard and retries
def test_ai_text_that_passes_the_guard_is_used(doc):
    row = narrative.scenario_row(doc, "zero", "zero", "exempt", "jan31")
    client = FakeClient(tool_response(incentive_shift="zero", renewal_shift="zero", newbuild_regime="exempt",
                                      information_rule="jan31"), text_response(_grounded_sentence(row)))
    result = narrative.scenario_copilot("Quelle est la hausse ?", doc, client)
    assert result["status"] == "ai"


def test_guard_rejects_an_invented_number_then_falls_back(doc):
    row = narrative.scenario_row(doc, "zero", "zero", "exempt", "jan31")
    bad = text_response("La hausse atteint 99,9 % dans ce scénario.")
    client = FakeClient(tool_response(incentive_shift="zero", renewal_shift="zero", newbuild_regime="exempt",
                                      information_rule="jan31"), bad, bad)
    result = narrative.scenario_copilot("Quelle est la hausse ?", doc, client)
    assert result["status"] == "fallback"
    assert ungrounded_numbers(result["text"], doc) == []
    assert row is not None


def test_without_a_key_the_copilot_says_use_the_dropdowns(doc):
    assert narrative.scenario_copilot("Quelle est la hausse ?", doc, None)["status"] == "no_key"


def test_get_client_is_none_without_a_key(monkeypatch):
    monkeypatch.delenv(narrative.API_KEY_VARIABLE, raising=False)
    monkeypatch.setattr(narrative, "load_dotenv", lambda *args, **kwargs: None)
    assert narrative.get_client() is None


def test_language_detection():
    assert narrative.detect_language("Quelle est la hausse nette ?") == "fr"
    assert narrative.detect_language("What is the net increase?") == "en"


# ---------------------------------------------------------------- building table
def test_building_table_has_no_cell_below_the_minimum(doc):
    minimum = load_config()["app"]["building_min_pairs"]
    assert doc["building_beds"], "the synthetic example should show some building cells"
    assert all(cell["n_pairs"] >= minimum for cell in doc["building_beds"])
    assert all(isinstance(cell["building"], str) for cell in doc["building_beds"])


def test_champion_grid_row_equals_the_headline(doc):
    champion_jan31 = next(row for row in doc["scenario_grid"]
                          if row["model"] != narrative.REGULATED_MODEL_NAME and row["information_rule"] == "jan31")
    assert champion_jan31["headline_net_pct"] == pytest.approx(doc["headline"]["net_pct"])
    assert champion_jan31["model"] == doc["headline"]["model"]


def test_sensitivity_delta_is_variant_minus_base(doc):
    rows = [row for row in doc["sensitivity"] if row["headline_net_pct"] is not None and row["base_net_pct"] is not None]
    assert rows, "the synthetic example should carry runnable sensitivity variants"
    for row in rows:
        assert row["delta_pp"] == pytest.approx(row["headline_net_pct"] - row["base_net_pct"], abs=1e-6)
