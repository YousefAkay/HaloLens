"""Q-02: the deterministic topic router, French and English. No API call anywhere."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import qa_topics

CASES = [
    # (question, expected topic, language)
    ("Quelle est la hausse 2026 nette de toutes les concessions ?", "headline", "fr"),
    ("What is the 2026 increase net of all concessions?", "headline", "en"),
    ("Combien vont augmenter les loyers l'an prochain ?", "headline", "fr"),
    ("How much will rents rise next year?", "headline", "en"),
    ("Quelle est la prévision de hausse pour 2026 ?", "headline", "fr"),
    ("Give me the headline number for the forecast", "headline", "en"),
    ("Comment est définie la hausse que vous mesurez ?", "definition", "fr"),
    ("What does the rent increase actually mean here?", "definition", "en"),
    ("Pourquoi comparer chaque unité à elle-même ?", "definition", "fr"),
    ("How is the same-unit growth calculated?", "definition", "en"),
    ("Que se passe-t-il si l'effet des incitatifs est plus fort ?", "scenarios_levers", "fr"),
    ("What happens if the effect of incentives is stronger?", "scenarios_levers", "en"),
    ("Et si les incitatifs étaient moins profonds ?", "scenarios_levers", "fr"),
    ("What if the Ontario new-build guideline applies?", "scenarios_levers", "en"),
    ("Comment la règle du TAL intervient-elle pour les renouvellements québécois ?", "regulation", "fr"),
    ("How does the TAL rule apply to Québec renewals?", "regulation", "en"),
    ("Quelle est la ligne directrice de l'Ontario pour les renouvellements ?", "regulation", "fr"),
    ("Is there a rent cap for renewals in Ontario?", "regulation", "en"),
    ("Pourquoi le classement des modèles est-il statistiquement faible ?", "validation_backtest", "fr"),
    ("Why is the ranking of the models statistically weak?", "validation_backtest", "en"),
    ("Les prévisions passées étaient-elles fiables ?", "validation_backtest", "fr"),
    ("How accurate was the backtest in past years?", "validation_backtest", "en"),
    ("Que sont les incitatifs et comment les traitez-vous ?", "incentives", "fr"),
    ("How do free months affect the numbers?", "incentives", "en"),
    ("Quelle différence entre le loyer contractuel et les rabais ?", "incentives", "fr"),
    ("What is the difference between contractual rent and net of concessions?", "incentives", "en"),
    ("Quelles hypothèses déplacent le plus la hausse ?", "uncertainty", "fr"),
    ("Which assumptions move the increase the most?", "uncertainty", "en"),
    ("Quelle est l'incertitude autour de ce chiffre ?", "uncertainty", "fr"),
    ("How confident are you in the range?", "uncertainty", "en"),
    ("Quel immeuble a la plus forte hausse ?", "buildings_segments", "fr"),
    ("Which building has the highest increase?", "buildings_segments", "en"),
    ("Comment diffèrent les hausses selon le nombre de chambres ?", "buildings_segments", "fr"),
    ("How do the segments by bedrooms compare?", "buildings_segments", "en"),
    ("Combien de baux contiennent les données ?", "data_quality", "fr"),
    ("How many leases are in the data?", "data_quality", "en"),
    ("Quelles paires ont été exclues et pourquoi ?", "data_quality", "fr"),
    ("Where do the public statistics come from?", "data_quality", "en"),
    ("Quel est le taux d'occupation du portefeuille ?", "forbidden", "fr"),
    ("What is the occupancy rate?", "forbidden", "en"),
    ("Quelle est la vacance dans l'immeuble ?", "forbidden", "fr"),
    ("What is the vacancy rate in the building?", "forbidden", "en"),
    ("Quelle est l'absorption nette en 2025 ?", "forbidden", "fr"),
    ("What is the total rent roll?", "forbidden", "en"),
    ("Quelle sera la météo demain ?", "out_of_scope", "fr"),
    ("Tell me a joke about cats", "out_of_scope", "en"),
    ("Qui a gagné la Coupe du monde ?", "out_of_scope", "fr"),
    ("Write me a poem about the sea", "out_of_scope", "en"),
    # plain prepositions ("on", "in", "sur", "en") are not keywords; concessions on renewals are an incentives question
    ("Tell me about the effect on rents", "out_of_scope", "en"),
    ("Tell me a story on the sea in winter", "out_of_scope", "en"),
    ("Qu'en est-il de la météo sur la côte en hiver ?", "out_of_scope", "fr"),
    ("How do concessions affect the increase on renewals?", "incentives", "en"),
    ("Do free months on renewals change the increase?", "incentives", "en"),
    ("What discounts apply to turnovers in Ontario?", "incentives", "en"),
    ("Les concessions sur les renouvellements changent-elles la hausse ?", "incentives", "fr"),
    ("Quel est l'effet des rabais sur la hausse des renouvellements ?", "incentives", "fr"),
    ("What is the increase in 2026 for units on the second floor?", "headline", "en"),
    ("Quelle est la hausse sur les renouvellements ?", "headline", "fr"),
    ("How many leases are in the data on renewals?", "data_quality", "en"),
    ("Is the guideline on renewals binding?", "regulation", "en"),
    ("What is the range on the forecast?", "uncertainty", "en"),
    ("Peut-on se fier au modèle sur les années passées ?", "validation_backtest", "fr"),
]


@pytest.mark.parametrize("question, topic, lang", CASES)
def test_every_question_maps_to_its_expected_topic_and_language(question, topic, lang):
    result = qa_topics.route(question)
    assert result.topic == topic, (question, result)
    assert result.lang == lang, (question, result)


def test_there_are_at_least_thirty_cases_in_both_languages():
    assert len(CASES) >= 30
    assert {lang for _, _, lang in CASES} == {"fr", "en"}
    assert {topic for _, topic, _ in CASES} == set(qa_topics.ALL_TOPICS)


def test_forbidden_subjects_win_over_other_keywords():
    assert qa_topics.route("What is the vacancy rate and the 2026 increase?").topic == "forbidden"
    assert qa_topics.route("Hausse 2026 et taux d'occupation ?").topic == "forbidden"


def test_accents_and_case_do_not_matter():
    assert qa_topics.route("QUELLE EST LA HAUSSE 2026 ?").topic == qa_topics.route("quelle est la hausse 2026 ?").topic
    assert qa_topics.route("renouvellements québécois").topic == qa_topics.route("renouvellements quebecois").topic


def test_router_is_deterministic():
    assert qa_topics.route("How many leases are in the data?") == qa_topics.route("How many leases are in the data?")


class FakeClient:
    def __init__(self, topic=None, fail=False):
        self.topic, self.fail, self.calls = topic, fail, []


def make_call(client_topic, fail=False):
    def call(client, system, content, **extra):
        if fail:
            raise TimeoutError("down")
        block = SimpleNamespace(type="tool_use", name="choose_topic", input={"topic": client_topic})
        return SimpleNamespace(content=[block], stop_reason="tool_use", extra=extra)

    return call


def test_without_a_client_the_deterministic_route_stands():
    result = qa_topics.route_with_client("Tell me about the increase", None, make_call("definition"))
    assert result == qa_topics.route("Tell me about the increase")


def test_an_unsure_route_may_use_the_models_enum_choice():
    question = "Parlez-moi des chiffres"
    assert not qa_topics.route(question).confident
    chosen = qa_topics.route_with_client(question, object(), make_call("uncertainty"))
    assert chosen.topic == "uncertainty"


def test_a_confident_route_never_calls_the_client():
    def forbidden(*args, **kwargs):
        raise AssertionError("must not be called")

    assert qa_topics.route_with_client("What is the 2026 increase net of all concessions?", object(), forbidden).topic == "headline"


def test_the_model_cannot_unlock_a_forbidden_subject_or_break_the_router():
    assert qa_topics.route_with_client("What is the occupancy rate?", object(), make_call("headline")).topic == "forbidden"
    unsure = "Parlez-moi des chiffres"
    assert qa_topics.route_with_client(unsure, object(), make_call("forbidden")).topic == qa_topics.route(unsure).topic
    assert qa_topics.route_with_client(unsure, object(), make_call("nonsense")).topic == qa_topics.route(unsure).topic
    assert qa_topics.route_with_client(unsure, object(), make_call("x", fail=True)).topic == qa_topics.route(unsure).topic


def test_the_tool_schema_is_an_enum_of_the_topics():
    assert set(qa_topics.ROUTER_TOOL["input_schema"]["properties"]["topic"]["enum"]) == set(qa_topics.ALL_TOPICS)


def test_a_specific_keyword_beats_generic_renewal_words_on_a_tie(monkeypatch):
    import re
    # equal totals (2.0): the topic whose strongest pattern is larger leads, whatever the order of TOPICS
    monkeypatch.setattr(qa_topics, "COMPILED", {
        "regulation": ((re.compile("renewal"), 1.0), (re.compile("rule"), 1.0)),
        "incentives": ((re.compile("concession"), 2.0),),
    })
    assert qa_topics.route("concession on renewal rule").topic == "incentives"
    # the reverse weights give the reverse winner: the rule is about pattern strength, not about a topic name
    monkeypatch.setattr(qa_topics, "COMPILED", {
        "regulation": ((re.compile("renewal"), 2.0),),
        "incentives": ((re.compile("concession"), 1.0), (re.compile("rule"), 1.0)),
    })
    assert qa_topics.route("concession on renewal rule").topic == "regulation"


def _aggregates() -> dict:
    import json
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parents[1] / "outputs" / "public" / "aggregates_synthetic.json").read_text("utf-8"))


def test_building_display_names_come_from_the_aggregates_at_runtime():
    document = _aggregates()
    names = qa_topics.building_names(document)
    assert names and all(isinstance(name, str) for name in names)
    for name in names:
        question = f"What changed at {name} last year?"
        assert qa_topics.route(question).topic != "buildings_segments" or name.lower() in {"building", "property"}
        assert qa_topics.route(question, names=names).topic == "buildings_segments", question
    assert qa_topics.building_names(None) == () and qa_topics.building_names({}) == ()


def test_the_router_and_the_labels_name_no_fixture_building():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    names = {name.lower() for name in qa_topics.building_names(_aggregates())}
    sources = [root / "app" / "qa_topics.py", root / "app" / "qa_answers.py", root / "app" / "ui" / "labels.py"]
    for path in sources:
        text = path.read_text("utf-8").lower()
        assert not [name for name in names if name in text], path


def test_answer_question_uses_the_building_names_of_the_aggregates():
    from app import qa_answers
    document = _aggregates()
    name = qa_topics.building_names(document)[0]
    assert qa_answers.answer_question(f"How is {name} doing?", document, default_lang="en").topic == "buildings_segments"
