"""Q-02: fact sheets, the deterministic composer and the answer pipeline on the synthetic aggregates. No API call."""

from __future__ import annotations

import json
import re

import pytest
from test_qa_topics import CASES

from app import narrative, qa_answers, qa_topics
from app.number_guard import ungrounded_numbers
from halolens.config import repo_root

AGGREGATES = repo_root() / "outputs" / "public" / "aggregates_synthetic.json"
MODEL_CODE = re.compile(r"\b[A-Z]\d_[a-z_]+\b")
DECIMALS = re.compile(r"\d+[.,]\d{2,}")
FRENCH_MARKERS = {"la", "le", "les", "des", "est", "une", "et", "de", "du", "en", "pour", "sont"}
ENGLISH_MARKERS = {"the", "is", "are", "and", "of", "to", "in", "for", "with", "this", "that", "it"}
SECTION_TITLES = {*qa_answers.SECTION_TITLES_EN.values(), *qa_answers.SECTION_TITLES_FR.values()}


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(AGGREGATES.read_text(encoding="utf-8"))


def words(text: str) -> list[str]:
    return re.findall(r"[a-zàâçéèêëîïôûùü']+", text.lower())


def body_without_titles(text: str) -> str:
    for title in SECTION_TITLES:
        text = text.replace(title, " ")
    return text


@pytest.mark.parametrize("question, topic, lang", CASES)
def test_every_question_gets_a_complete_clean_answer(doc, question, topic, lang):
    answer = qa_answers.answer_question(question, doc)
    text = answer.text
    assert answer.topic == topic and answer.lang == lang
    # structure: one short sentence, 2-4 bullets (refusals and out-of-scope have 3), a read-more line for real topics
    assert answer.lead.strip() and 2 <= len(answer.bullets) <= qa_answers.MAX_BULLETS
    assert answer.lead.rstrip().endswith((".", "!", "?")) and all(b.rstrip().endswith(".") for b in answer.bullets)
    if topic in qa_topics.TOPICS:
        assert answer.read_more.startswith("Read more in the notebook:" if lang == "en" else "Pour approfondir, dans le carnet :")
        assert any(title in answer.read_more for title in SECTION_TITLES)
    # no internal codes, section tokens, python keys or raw floats
    assert not MODEL_CODE.search(text) and "§" not in text and not DECIMALS.search(text)
    assert "_pct" not in text and "None" not in text and "nan" not in words(text)
    # every number is grounded in the aggregates at <= 1 decimal
    assert ungrounded_numbers(text, doc) == [], (question, ungrounded_numbers(text, doc))
    # the answer is in the question's language
    tokens = words(body_without_titles(text))
    french, english = sum(t in FRENCH_MARKERS for t in tokens), sum(t in ENGLISH_MARKERS for t in tokens)
    assert (french > english) if lang == "fr" else (english > french), (question, french, english)
    assert answer.caption in (qa_answers.CAPTION["synthetic"][lang],)


@pytest.mark.parametrize("topic", qa_topics.TOPICS)
@pytest.mark.parametrize("lang", ["en", "fr"])
def test_fact_sheet_numbers_are_grounded_and_labels_are_plain(doc, topic, lang):
    sheet = qa_answers.fact_sheet(topic, doc, lang)
    assert sheet.facts, topic
    for key, fact in sheet.facts.items():
        assert not MODEL_CODE.search(fact.label + fact.text), (topic, key)
        assert "_" not in fact.label and "_" not in fact.text, (topic, key)
        assert not DECIMALS.search(fact.text), (topic, key, fact.text)
        assert fact.text.strip() and "None" not in fact.text
    assert ungrounded_numbers("\n".join(f.text for f in sheet.facts.values()), doc) == []
    assert ungrounded_numbers("\n".join(f.text for f in sheet.facts.values()), {"facts": sheet.numbers}) == []


def test_the_headline_fact_sheet_reads_like_the_example_in_the_brief(doc):
    sheet = qa_answers.fact_sheet("headline", doc, "en")
    assert sheet.facts["net"].label == "Net increase 2026" and sheet.facts["net"].text == f"{doc['headline']['net_pct']:.1f} %"
    assert sheet.facts["contract"].label == "Contractual increase"
    french = qa_answers.fact_sheet("headline", doc, "fr")
    assert french.facts["net"].text == f"{doc['headline']['net_pct']:.1f}".replace(".", ",") + " %"


def test_model_codes_are_translated_in_one_table(doc):
    assert set(qa_answers.MODEL_NAMES) >= {row["model"] for row in doc["backtest"]}
    for code, (en, fr) in qa_answers.MODEL_NAMES.items():
        assert not MODEL_CODE.search(en + fr), code
    assert qa_answers.model_label("B3_tal_anchor", "fr") != qa_answers.model_label("B3_tal_anchor", "en")
    assert qa_answers.model_label("Z9_unknown_model", "en") == "Z9 unknown model"  # an unknown code is still readable


def test_percent_never_writes_more_than_one_decimal_or_a_negative_zero():
    assert qa_answers.percent(3.5353, "en") == "3.5 %" and qa_answers.percent(3.5353, "fr") == "3,5 %"
    assert qa_answers.percent(-0.04, "en") == "0.0 %" and qa_answers.percent(-0.2, "en") == "−0.2 %"
    assert qa_answers.percent(None, "en") == "n/a"


def test_forbidden_topics_are_always_refused_without_numbers_and_without_the_client(doc):
    class Client:
        messages = None

        def create(self, **kwargs):
            raise AssertionError("a refusal must not call the model")

    Client.messages = Client()
    for question in ("What is the occupancy?", "Quelle est la vacance ?", "Show me the absorption", "Total rent roll please",
                     "What is the vacancy and the 2026 increase?", "Taux d'occupation et hausse 2026 ?"):
        answer = qa_answers.answer_question(question, doc, Client())
        assert answer.topic == "forbidden", question
        assert "%" not in answer.text and not re.search(r"\d[.,]\d", answer.text), question
        assert "cannot measure" in answer.text or "ne permet pas de mesurer" in answer.text


def test_out_of_scope_lists_what_can_be_asked(doc):
    answer = qa_answers.answer_question("Tell me a joke about cats", doc)
    assert answer.topic == "out_of_scope" and "scenarios" in answer.text and "%" not in answer.text


def test_the_five_preset_questions_cover_five_topics_in_both_languages(doc):
    for questions, lang in ((narrative.PRESET_QUESTIONS_EN, "en"), (narrative.PRESET_QUESTIONS, "fr")):
        topics = [qa_answers.answer_question(question, doc).topic for question in questions]
        assert topics == ["headline", "scenarios_levers", "regulation", "validation_backtest", "uncertainty"]
        assert {qa_answers.answer_question(q, doc).lang for q in questions} == {lang}


def test_real_mode_caption_says_your_data(doc):
    real = {**doc, "mode": "real"}
    assert qa_answers.answer_question("How many leases are in the data?", real).caption == qa_answers.CAPTION["real"]["en"]


def test_missing_values_never_break_an_answer_or_print_nan(doc):
    sparse = {key: doc[key] for key in ("mode", "target_year", "as_of", "headline", "companions", "coverage")}
    sparse["headline"] = {**doc["headline"], "net_pct": None, "provinces": {"QC": {"net_pct": None, "contract_pct": None},
                                                                          "ON": {"net_pct": None, "contract_pct": None}}}
    for topic in qa_topics.ALL_TOPICS:
        answer, _ = qa_answers.compose(topic, sparse, "en")
        assert answer.lead and "nan" not in words(answer.text)


def test_section_titles_exist_for_every_section_used():
    for numbers in qa_answers.READ_MORE.values():
        for number in numbers:
            assert number in qa_answers.SECTION_TITLES_EN and number in qa_answers.SECTION_TITLES_FR
