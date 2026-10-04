"""I-11d: the Questions tab wording. The refusal never cites repository files, and the chips follow the page language."""
from app import narrative, streamlit_app


def test_refusal_does_not_cite_repository_files():
    for language, text in narrative.REFUSAL.items():
        assert "AGENTS.md" not in text, language
    assert "section 01 du notebook" in narrative.REFUSAL["fr"] and "notebook section 01" in narrative.REFUSAL["en"]


def test_chip_labels_follow_the_language():
    english, french = streamlit_app._pills("en"), streamlit_app._pills("fr")
    assert english[:-1] == list(narrative.PRESET_QUESTIONS_EN) and french[:-1] == list(narrative.PRESET_QUESTIONS)
    assert len(narrative.PRESET_QUESTIONS_EN) == len(narrative.PRESET_QUESTIONS)
    assert english != french


def test_an_english_chip_sends_the_french_preset_at_the_same_index():
    for index in range(len(narrative.PRESET_QUESTIONS)):
        assert streamlit_app._pill_question(index, "en") == narrative.PRESET_QUESTIONS[index]
        assert streamlit_app._pill_question(index, "fr") == narrative.PRESET_QUESTIONS[index]
    last = len(streamlit_app._pills("en")) - 1
    assert streamlit_app._pill_question(last, "en") == streamlit_app._pills("en")[last]  # the occupancy example is sent as shown
