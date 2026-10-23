"""The Questions tab wording. The refusal never cites repository files, and the chips follow the page language."""
from app import narrative, streamlit_app


def test_refusal_does_not_cite_repository_files():
    from app import qa_answers

    for language, (lead, bullets) in qa_answers.REFUSAL.items():
        assert "AGENTS.md" not in " ".join([lead, *bullets]), language


def test_chip_labels_follow_the_language():
    english, french = streamlit_app._pills("en"), streamlit_app._pills("fr")
    assert english == list(narrative.PRESET_QUESTIONS_EN) and french == list(narrative.PRESET_QUESTIONS)
    assert len(narrative.PRESET_QUESTIONS_EN) == len(narrative.PRESET_QUESTIONS)
    assert english != french


def test_a_chip_sends_the_question_as_shown():
    for lang in ("en", "fr"):
        assert streamlit_app._pills(lang)[0] == (narrative.PRESET_QUESTIONS_EN if lang == "en" else narrative.PRESET_QUESTIONS)[0]
