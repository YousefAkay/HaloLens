"""Scenario copilot, privacy wall and shared helpers for the Q&A over the aggregates. Answers: app/qa_answers.py.

Privacy wall: the Claude API only ever receives (1) the aggregates document, which has no unit-level field by schema,
(2) committed decision and assumption notes with their real-data numbers removed, and (3) the user's question. Never CRM
rows. `privacy_payload` builds exactly that, and `assert_privacy_payload` refuses anything else.

The model never computes a number: it chooses one row of the precomputed scenario grid (tool use, enum-restricted), or
it writes text that must pass app/number_guard.py against the aggregates. Otherwise the guarded fallback is shown.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.number_guard import ungrounded_numbers
from halolens.config import load_config, repo_root
from halolens.contracts import INFORMATION_RULES, LEVER_LABELS, NEWBUILD_LABELS
from halolens.forecast.combine import REGULATED_MODEL_NAME

API_KEY_VARIABLE = "ANTHROPIC_API_KEY"
SELECTION_LEVERS = tuple(label for label in LEVER_LABELS if label != "none")  # the three lever settings
SELECTION_NEWBUILD = tuple(label for label in NEWBUILD_LABELS if label != "none")  # exempt or guideline
UNIT_LEVEL_KEYS = {"unit_id", "unit_code", "hunit", "sunitcode", "spropcode", "prop_code", "lease_start", "sign_date"}
SECTION_MAP = {
    "01": "Définition de la hausse mesurée", "02": "Dictionnaire de données et contrôle qualité",
    "03": "Effet de composition", "04": "Appariement à unité constante",
    "05": "Concessions : loyer contractuel vs net", "06": "Renouvellements vs relocations, règles QC et ON",
    "07": "Données externes et dates de publication", "08": "Méthode de prévision",
    "09": "Backtest 2023-2025", "10": "Prévision 2026 et règle du champion", "11a": "Incertitude",
    "11b": "Scénarios 2026", "12": "Références",
}
PRESET_QUESTIONS = (  # the five preset questions of the Questions tab, in French and English (same order)
    "Quelle est la hausse 2026 nette de toutes les concessions ?",
    "Que se passe-t-il si l'effet des incitatifs est plus fort ?",
    "Comment la règle du TAL intervient-elle pour les renouvellements québécois ?",
    "Pourquoi le classement des modèles est-il statistiquement faible ?",
    "Quelles hypothèses déplacent le plus la hausse ?",
)
PRESET_QUESTIONS_EN = (
    "What is the 2026 increase net of all concessions?",
    "What happens if the effect of incentives is stronger?",
    "How does the TAL rule apply to Québec renewals?",
    "Why is the ranking of the models statistically weak?",
    "Which assumptions move the increase the most?",
)
DECISION_FILES = ("docs/qa_knowledge.md",)
SAFE_NOTE_LINE = re.compile(r"^\s*-\s")  # bullet lines only
REAL_NUMBER = re.compile(r"\d+[.,]\d+|\d+\s?%|\d+\s?pp|−|-\d")  # decimals, percentages, pp: real-data numbers


# ---------------------------------------------------------------------------- privacy wall
def committed_notes(root: Path | None = None) -> list[str]:
    """Bullet lines of the committed decision and assumption logs, with any line that carries a real-data number removed.

    Only counts (whole numbers in plain text) can pass. Lines that hold decimals, percentages or pp are dropped.
    """
    root = root or repo_root()
    notes = []
    for name in DECISION_FILES:
        path = root / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if SAFE_NOTE_LINE.match(line) and not REAL_NUMBER.search(line):
                notes.append(line.strip("- ").strip())
    return notes


def privacy_payload(aggregates: dict[str, Any], question: str, notes: list[str]) -> dict[str, Any]:
    """Exactly what may be sent to the Claude API: the aggregates, the counts-only notes and the question."""
    payload = {"aggregates": aggregates, "notes": notes, "question": question}
    assert_privacy_payload(payload)
    return payload


def _keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        return {str(key).lower() for key in node} | {key for child in node.values() for key in _keys(child)}
    if isinstance(node, list):
        return {key for child in node for key in _keys(child)}
    return set()


def assert_privacy_payload(payload: dict[str, Any]) -> None:
    """Raise if any unit-level field name appears in what would be sent (test and runtime guard)."""
    found = _keys(payload) & UNIT_LEVEL_KEYS
    if found:
        raise ValueError(f"unit-level field in an outbound payload: {sorted(found)}")
    text = json.dumps(payload, ensure_ascii=False).lower()
    if "hunit" in text or "sunitcode" in text or "spropcode" in text:
        raise ValueError("unit identifier column name in an outbound payload")


# ---------------------------------------------------------------------------- client and key
def get_client() -> Any | None:
    """A Claude API client, or None when no key is configured. The key is read from .env and never printed."""
    load_dotenv(repo_root() / ".env", override=False)
    key = os.environ.get(API_KEY_VARIABLE)
    if not key:
        return None
    import anthropic

    return anthropic.Anthropic(api_key=key)


def _settings() -> dict[str, Any]:
    return load_config()["app"]


def _call(client: Any, system: str, content: str, **extra: Any) -> Any:
    settings = _settings()
    return client.messages.create(model=settings["llm_model"], max_tokens=settings["llm_max_tokens"], system=system,
                                  messages=[{"role": "user", "content": content}], **extra)


def _text(response: Any) -> str:
    """The text of a response, or "" when the model stopped at the token limit (a truncated answer is a failed attempt)."""
    if getattr(response, "stop_reason", None) == "max_tokens":
        return ""
    return " ".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()


def detect_language(question: str) -> str:
    """'fr' or 'en' from a few function words; French is the default of the notebook and the app."""
    lowered = f" {question.lower()} "
    french = sum(word in lowered for word in (" quel", " quelle", " comment", " pourquoi", " est", " les", " des ",
                                             " que ", " la ", " le "))
    english = sum(word in lowered for word in (" what", " how", " why", " is ", " the ", " would ", " which "))
    return "en" if english > french else "fr"


# ---------------------------------------------------------------------------- scenario copilot
SELECT_TOOL = {
    "name": "select_scenario",
    "description": "Choose one row of the precomputed scenario grid. Never compute a number.",
    "input_schema": {
        "type": "object", "additionalProperties": False,
        "required": ["incentive_shift", "renewal_shift", "newbuild_regime", "information_rule"],
        "properties": {
            "incentive_shift": {"enum": list(SELECTION_LEVERS)},
            "renewal_shift": {"enum": list(SELECTION_LEVERS)},
            "newbuild_regime": {"enum": list(SELECTION_NEWBUILD)},
            "information_rule": {"enum": list(INFORMATION_RULES)},
        },
    },
}
SELECT_SYSTEM = ("Tu choisis un scénario dans la grille précalculée en appelant select_scenario. Tu ne calcules aucun "
                 "chiffre. Choisis les valeurs qui correspondent à la question ; par défaut : zero, zero, exempt, jan31.")


def scenario_row(aggregates: dict[str, Any], incentive: str, renewal: str, newbuild: str, rule: str) -> dict[str, Any] | None:
    """Exact lookup of one E2 row of the scenario grid; None when the combination is not in the grid."""
    for row in aggregates.get("scenario_grid", []):
        if (row["model"] == REGULATED_MODEL_NAME and row["incentive_shift"] == incentive
                and row["renewal_shift"] == renewal and row["newbuild_regime"] == newbuild and row["information_rule"] == rule):
            return row
    return None


def baseline_row(aggregates: dict[str, Any], rule: str = "jan31") -> dict[str, Any] | None:
    """The E2 central row (no lever moved, new-build exempt) under the given information rule: the comparison point."""
    return scenario_row(aggregates, "zero", "zero", "exempt", rule)


def _valid_selection(arguments: dict[str, Any]) -> bool:
    return (arguments.get("incentive_shift") in SELECTION_LEVERS and arguments.get("renewal_shift") in SELECTION_LEVERS
            and arguments.get("newbuild_regime") in SELECTION_NEWBUILD and arguments.get("information_rule") in INFORMATION_RULES)


def fallback_scenario_text(row: dict[str, Any], base: dict[str, Any] | None, lang: str) -> str:
    """Deterministic sentence from the grid row and the baseline; it passes the guard by construction."""
    net, contract = f"{row['headline_net_pct']:.1f} %", f"{row['headline_contract_pct']:.1f} %"
    if base is None or base["headline_net_pct"] is None:
        return (f"Scénario {row['incentive_shift']}/{row['renewal_shift']}/{row['newbuild_regime']} : hausse nette {net}."
                if lang == "fr" else
                f"Scenario {row['incentive_shift']}/{row['renewal_shift']}/{row['newbuild_regime']}: net increase {net}.")
    base_net = f"{base['headline_net_pct']:.1f} %"
    if lang == "fr":
        return (f"Dans ce scénario, la hausse nette est de {net} (contractuelle : {contract}), contre {base_net} dans le "
                f"scénario central. Ces valeurs viennent de la grille précalculée.")
    return (f"In this scenario the net increase is {net} (contractual: {contract}), against {base_net} in the central "
            f"scenario. These values come from the precomputed grid.")


def scenario_copilot(question: str, aggregates: dict[str, Any], client: Any | None, rule: str = "jan31") -> dict[str, Any]:
    """Pick a grid row from a question, then describe it in the question's language. Returns status and text.

    status: "no_key" (use the dropdowns), "ai" (model text passed the guard), "fallback" (guarded deterministic text).
    """
    lang = detect_language(question)
    if client is None:
        return {"status": "no_key", "row": None, "text": None}
    selection_response = _call(client, SELECT_SYSTEM, question, tools=[SELECT_TOOL], tool_choice={"type": "auto"})
    arguments = next((block.input for block in selection_response.content
                      if getattr(block, "type", "") == "tool_use" and block.name == "select_scenario"), {})
    if not _valid_selection(arguments):
        return {"status": "fallback", "row": None, "text": None}
    row = scenario_row(aggregates, arguments["incentive_shift"], arguments["renewal_shift"], arguments["newbuild_regime"],
                       arguments["information_rule"])
    if row is None:
        return {"status": "fallback", "row": None, "text": None}
    base = baseline_row(aggregates, arguments["information_rule"])
    describe = json.dumps({"row": row, "baseline": base, "language": lang}, ensure_ascii=False)
    for _attempt in range(2):
        text = _text(_call(client, "Écris 2 à 4 phrases dans la langue demandée, en utilisant seulement les valeurs de ce "
                                   "JSON, arrondies à une décimale au plus. Ne calcule rien.", describe))
        if text and not ungrounded_numbers(text, aggregates):
            return {"status": "ai", "row": row, "text": text}
    return {"status": "fallback", "row": row, "text": fallback_scenario_text(row, base, lang)}
