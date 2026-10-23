"""Evaluation set for the Q&A guard: hand-written fake model responses, no API calls.

Each case feeds a scripted response through `ask_analysis` or `scenario_copilot` and checks the outcome:
refusal topics, language detection, section citations, long floats, truncation, ungrounded numbers, a clean answer.
The aggregates are the committed synthetic file.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import app.narrative as narrative
from app.number_guard import ungrounded_numbers
from leaselens.config import load_config, repo_root

AGGREGATES = repo_root() / "outputs" / "public" / "aggregates_synthetic.json"


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(AGGREGATES.read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected extra API call")
        return self.responses.pop(0)


def reply(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason)


def headline(doc: dict) -> float:
    return narrative.baseline_row(doc, "jan31")["headline_net_pct"]


def ask(question: str, doc: dict, *responses):
    client = FakeClient(*responses)
    return narrative.ask_analysis(question, doc, [], client), client


# ---------------------------------------------------------------- refusal topics, both languages
@pytest.mark.parametrize("question, lang", [
    ("Quel est le taux d'occupation du portefeuille ?", "fr"),
    ("Quelle est la vacance dans l'immeuble ?", "fr"),
    ("Quelle est l'absorption nette en 2025 ?", "fr"),
    ("What is the occupancy of the portfolio?", "en"),
    ("What is the vacancy rate in the building?", "en"),
    ("What is the total rent roll?", "en"),
])
def test_refusal_topics_are_refused_without_calling_the_model(doc, question, lang):
    result, client = ask(question, doc)
    assert result["status"] == "refused"
    assert result["text"] == narrative.REFUSAL[lang]
    assert client.calls == []


# ---------------------------------------------------------------- language detection
@pytest.mark.parametrize("question, lang", [
    ("Quelle est la hausse nette pour 2026 ?", "fr"),
    ("Pourquoi le classement des modèles est-il faible ?", "fr"),
    ("What is the net increase for 2026?", "en"),
    ("Why is the ranking of the models weak?", "en"),
])
def test_language_detection(question, lang):
    assert narrative.detect_language(question) == lang


# ---------------------------------------------------------------- guard: citations, long floats, ungrounded numbers
def test_citation_only_text_passes_against_empty_aggregates():
    assert ungrounded_numbers("Voir §07 puis §11a et §10.", {}) == []


def test_ungrounded_number_next_to_a_citation_is_rejected():
    assert ungrounded_numbers("Voir §07 : la hausse est de 9,9 %.", {}) == ["9,9"]


def test_long_float_is_rejected_even_when_the_json_holds_it(doc):
    value = headline(doc)
    long_float = f"{value:.12f}"
    assert ungrounded_numbers(f"La hausse est de {long_float} %.", doc) != []
    assert ungrounded_numbers(f"La hausse est de {value:.1f} %.", doc) == []


def test_decimal_limit_comes_from_the_config():
    limit = load_config()["app"]["max_written_decimals"]
    assert ungrounded_numbers(f"{1.0 / 3:.{limit}f}", {"x": 1.0 / 3}) == []
    assert ungrounded_numbers(f"{1.0 / 3:.{limit + 1}f}", {"x": 1.0 / 3}) != []


def test_the_answer_prompt_asks_for_one_decimal(doc):
    _, client = ask("Quelle est la hausse nette ?", doc, reply(f"Voir §10 : {headline(doc):.1f} %."))
    assert "une décimale" in client.calls[0]["system"]


# ---------------------------------------------------------------- ask_analysis outcomes
def test_clean_grounded_answer_passes(doc):
    text = f"Voir §10 : la hausse nette est de {headline(doc):.1f} %."
    result, client = ask("Quelle est la hausse nette ?", doc, reply(text))
    assert result == {"status": "ai", "text": text}
    assert len(client.calls) == 1


def test_long_float_answer_is_retried_then_accepted_when_rounded(doc):
    bad = f"Voir §10 : la hausse nette est de {headline(doc):.12f} %."
    good = f"Voir §10 : la hausse nette est de {headline(doc):.1f} %."
    result, client = ask("Quelle est la hausse nette ?", doc, reply(bad), reply(good))
    assert result["status"] == "ai" and result["text"] == good
    assert len(client.calls) == 2


def test_ungrounded_number_falls_back_after_one_retry(doc):
    text = "Voir §10 : la hausse nette est de 41,7 %."
    result, client = ask("Quelle est la hausse nette ?", doc, reply(text), reply(text))
    assert result["status"] == "fallback"
    assert "41" not in result["text"]
    assert len(client.calls) == 2


def test_truncated_answer_is_retried_then_accepted(doc):
    truncated = reply(f"Voir §10 : la hausse nette est de {headline(doc):.1f} %", stop_reason="max_tokens")
    good = f"Voir §10 : la hausse nette est de {headline(doc):.1f} %."
    result, client = ask("Quelle est la hausse nette ?", doc, truncated, reply(good))
    assert result["status"] == "ai" and result["text"] == good
    assert len(client.calls) == 2


def test_two_truncated_answers_fall_back(doc):
    truncated = reply(f"Voir §10 : la hausse nette est de {headline(doc):.1f} %", stop_reason="max_tokens")
    result, client = ask("Quelle est la hausse nette ?", doc, truncated, truncated)
    assert result["status"] == "fallback"
    assert len(client.calls) == 2


def test_answer_without_a_valid_citation_is_not_accepted(doc):
    no_citation = f"La hausse nette est de {headline(doc):.1f} %."
    result, _ = ask("Quelle est la hausse nette ?", doc, reply(no_citation), reply(no_citation))
    assert result["status"] == "fallback"


def test_the_token_limit_is_raised_and_sent(doc):
    assert load_config()["app"]["llm_max_tokens"] == 1500
    _, client = ask("Quelle est la hausse nette ?", doc, reply(f"Voir §10 : {headline(doc):.1f} %."))
    assert client.calls[0]["max_tokens"] == 1500


def test_fallback_texts_pass_the_guard(doc):
    row = narrative.scenario_row(doc, "zero", "zero", narrative.SELECTION_MET[0], "jan31")
    base = narrative.baseline_row(doc, "jan31")
    for lang in ("fr", "en"):
        assert ungrounded_numbers(narrative.fallback_scenario_text(row, base, lang), doc) == []
