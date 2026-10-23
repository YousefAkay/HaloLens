"""Evaluation set for the Q&A guard: hand-written fake model responses, no API calls.

Each case feeds a scripted response through `qa_answers.polish` or `scenario_copilot` and checks the outcome:
refusal topics, language detection, section citations, long floats, truncation, ungrounded numbers, a clean answer.
The aggregates are the committed synthetic file.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import app.narrative as narrative
from app import qa_answers
from app.number_guard import ungrounded_numbers
from halolens.config import load_config, repo_root

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


def polish(topic: str, doc: dict, lang: str, *responses):
    """Run the optional rewrite of the deterministic answer on a scripted client."""
    client = FakeClient(*responses)
    answer, sheet = qa_answers.compose(topic, doc, lang)
    return qa_answers.polish(answer, sheet, "question", client), answer, client


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
    client = FakeClient()
    answer = qa_answers.answer_question(question, doc, client)
    assert answer.topic == "forbidden" and answer.lang == lang
    assert answer.lead == qa_answers.REFUSAL[lang][0] and client.calls == []


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


def test_the_rewrite_prompt_asks_to_keep_every_number(doc):
    _, _, client = polish("headline", doc, "en", reply("x"))
    assert "Keep every number exactly" in client.calls[0]["system"]


def good_text(doc: dict, lang: str = "en") -> str:
    answer, _ = qa_answers.compose("headline", doc, lang)
    return answer.lead + "\n" + "\n".join(f"- {bullet}" for bullet in answer.bullets[:3])


# ---------------------------------------------------------------- polish outcomes
def test_grounded_rewrite_is_accepted_and_keeps_the_read_more_line(doc):
    result, answer, client = polish("headline", doc, "en", reply(good_text(doc)))
    assert result.source == "polished" and result.read_more == answer.read_more
    assert len(client.calls) == 1


def test_long_float_rewrite_is_rejected(doc):
    bad = good_text(doc).replace(f"{headline(doc):.1f}", f"{headline(doc):.12f}")
    result, answer, _ = polish("headline", doc, "en", reply(bad))
    assert result == answer


def test_ungrounded_number_in_a_rewrite_keeps_the_deterministic_answer(doc):
    result, answer, _ = polish("headline", doc, "en", reply(good_text(doc).replace("increase", "increase of 41.7 %", 1)))
    assert result == answer and "41" not in result.text


def test_truncated_rewrite_is_rejected(doc):
    result, answer, _ = polish("headline", doc, "en", reply(good_text(doc), stop_reason="max_tokens"))
    assert result == answer


def test_rewrite_in_the_wrong_language_is_rejected(doc):
    result, answer, _ = polish("headline", doc, "en", reply(good_text(doc, "fr")))
    assert result == answer


def test_rewrite_with_a_model_code_or_section_token_is_rejected(doc):
    for extra in ("(see §05)", "from B0_last_year"):
        text = good_text(doc).replace("increase", f"increase {extra}", 1)
        result, answer, _ = polish("headline", doc, "en", reply(text))
        assert result == answer


def test_a_failing_client_never_raises(doc):
    class Broken:
        messages = None

        def create(self, **kwargs):
            raise TimeoutError("down")

    Broken.messages = Broken()
    answer, sheet = qa_answers.compose("headline", doc, "en")
    assert qa_answers.polish(answer, sheet, "q", Broken()) == answer


def test_the_token_limit_is_raised_and_sent(doc):
    assert load_config()["app"]["llm_max_tokens"] == 1500
    _, _, client = polish("headline", doc, "en", reply(good_text(doc)))
    assert client.calls[0]["max_tokens"] == 1500


def test_fallback_texts_pass_the_guard(doc):
    row = narrative.scenario_row(doc, "zero", "zero", narrative.SELECTION_NEWBUILD[0], "jan31")
    base = narrative.baseline_row(doc, "jan31")
    for lang in ("fr", "en"):
        assert ungrounded_numbers(narrative.fallback_scenario_text(row, base, lang), doc) == []
