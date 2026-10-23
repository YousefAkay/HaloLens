"""Question router for the Questions tab: one topic per question, French and English, no API needed.

Owner: INT. Task Q-02.

`route` is deterministic: it strips accents, lower-cases the question and scores keyword patterns per topic.
Forbidden subjects (occupancy, vacancy, absorption, rent roll) always win. A question with no keyword at all is
out of scope. When the router is unsure and a client exists, `route_with_client` may ask the model to choose one topic
through an enum tool call (the model never writes text there); without a client the deterministic result stands.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

TOPICS = ("headline", "definition", "scenarios_levers", "regulation", "validation_backtest", "incentives",
          "uncertainty", "buildings_segments", "data_quality")
FORBIDDEN = "forbidden"
OUT_OF_SCOPE = "out_of_scope"
ALL_TOPICS = TOPICS + (FORBIDDEN, OUT_OF_SCOPE)

FORBIDDEN_PATTERN = re.compile(r"occupan|occupation|inoccup|vacan|absorption|rent[ -]?roll|taux de vacance|"
                               r"loyers? total|total rent")
NAME_WEIGHT = 3.0  # weight of a building display name listed in the aggregates
UNSURE_BELOW = 2.0  # a best score under this value counts as "unsure" (the client may then choose the topic)

# (pattern, weight) per topic; patterns run on accent-free lower-case text.
PATTERNS: dict[str, tuple[tuple[str, float], ...]] = {
    "headline": (
        (r"hausse (de |en |pour )?\d{4}|\d{4} (increase|rent)|increase (in|for) \d{4}", 2.5),
        (r"\bhausse\b|\bincrease\b|\bheadline\b|\bresultat\b|\bchiffre cle\b|\bkey (number|figure)\b", 1.5),
        (r"combien|how much|how high|a quel point|quelle est la hausse|what is the (net )?increase", 2.0),
        (r"prevision|forecast|predict|projection|\bprevu\b|expected|attendu|prochaine annee|next year", 1.5),
        (r"loyers? .*(augment|monte|hauss)|rents? .*(rise|go up|grow|increase)", 2.0),
        (r"\bnet\b|\bnette\b", 1.0), (r"\bmediane?\b|\bmedian\b", 1.0),
    ),
    "definition": (
        (r"defini|definition|\bdefine\b|\bmeaning\b|signifie|veut dire|c.?est quoi|what is meant", 3.0),
        (r"what does .* mean|que veut dire|what do you mean by", 4.0),
        (r"comment (est|se) (calcul|mesur)|how (is|are) .*(calculated|measured|computed|defined)|how do you (calculate|measure)", 3.0),
        (r"meme unite|same[- ]unit|unite constante|composition|a composition fixe|fixed[- ]composition", 2.5),
        (r"methode|method(ology)?\b|\bmesure\b|measured|measure the|apparie|matching|paires?\b", 1.5),
        (r"\blog\b|annualis|geometri|weights?|poids", 1.5),
        (r"elle-meme|itself|chaque unite|each unit|lui-meme", 2.5),
    ),
    "scenarios_levers": (
        (r"what if|et si\b|que se passe|what happens|\bsi l.?effet|\bif the\b|supposons|suppose", 4.5),
        (r"scenario", 3.0),
        (r"plus fort|plus faible|plus eleve|moins eleve|stronger|weaker|deeper|shallower|bigger|smaller|higher|lower", 2.0),
        (r"levier|lever|simul|slider|curseur|grille|\bgrid\b|laboratoire|scenario lab", 2.5),
        (r"exempt(ion)?|exempte", 1.0),
    ),
    "regulation": (
        (r"\btal\b|tribunal|\bltb\b|landlord and tenant", 3.0),
        (r"regulat|reglement|regle\b|\brules?\b|loi\b|\blaw\b|legal|guideline|ligne directrice|plafon|\bcap\b|capped", 2.5),
        # renewal and turnover words are generic: they appear in questions on every topic, so they weigh little
        (r"renouvel|renewal|\brenew", 1.0), (r"relocation|turnover|nouveau locataire|new tenant|roulement", 1.0),
        (r"quebec|ontario|province|\bqc\b", 1.5), (r"\bipc\b|\bcpi\b|inflation", 1.5),
    ),
    "validation_backtest": (
        (r"backtest|retro-?test|back-test|historical test|test historique", 3.5),
        (r"valid|fiable|reliable|reliab|accura|precis|exact|trust|confiance dans|confiable", 2.0),
        (r"modele|model|champion|classement|ranking|rank|meilleur|best model|baseline|reference", 2.0),
        (r"erreur|error|\bmae\b|ecart|miss|manque|wrong|past years|annees passees|track record", 2.0),
        (r"statistiquement|statistically|significant|faible|weak", 1.0),
    ),
    "incentives": (
        # specific keywords: they decide the topic even when generic words (renewal, increase) also appear
        (r"incitatif|incentive|concession|rabais|discount|mois gratuit|free month|gratuit|promotion|cadeau", 3.0),
        (r"contractuel|contractual|asking|affiche|loyer net|net rent|net of", 1.5),
    ),
    "uncertainty": (
        (r"incertitude|uncertain|intervalle|interval|marge d.?erreur|margin of error|fourchette|\brange\b|bootstrap", 3.0),
        (r"sensib|sensitiv|hypothese|assumption|deplace|move the|influence|affect|drives?\b|facteur|driver", 2.5),
        (r"risque|risk|confiance|confidence|how sure|certain|surs? de|robust|solid", 2.0),
        (r"pire|worst|best case|meilleur cas|low and high|bas et haut|bas ou haut", 1.5),
    ),
    "buildings_segments": (
        (r"immeuble|building|propriete|property|\bsite\b|\btour\b", 3.0),
        (r"segment|chambre|bedroom|studio|\bbeds?\b|\bbr\b|\bcac\b|\b1 ?br\b|\b2 ?br\b|par type|by type", 2.5),
        (r"quel(le)? .*(plus|moins) .*(hausse|augment)|which .*(highest|lowest|most|least)", 1.5),
        (r"unite par unite|unit by unit|par unite|per unit", 1.0),
    ),
    "data_quality": (
        (r"qualite|quality|donnees|\bdata\b|dataset|extrait|extract|fichier|\bfile", 2.5),
        (r"exclu|excluded|exclusion|manquant|missing|erreurs? de donnees|outlier|aberrant", 2.5),
        (r"combien de (bail|baux|unites|paires|lignes)|how many (lease|unit|pair|row|record|building)s?", 3.0),
        (r"couverture|coverage|echantillon|sample|taille|size|volume|nombre de", 2.0),
        (r"\bsources?\b|provenance|where .* come from|d.?ou viennent|statistique canada|statistics canada|schl|cmhc", 2.5),
    ),
}
COMPILED = {topic: tuple((re.compile(pattern), weight) for pattern, weight in items) for topic, items in PATTERNS.items()}

ROUTER_TOOL = {
    "name": "choose_topic",
    "description": "Choose the single topic that best matches the question. Never write an answer.",
    "input_schema": {"type": "object", "additionalProperties": False, "required": ["topic"],
                     "properties": {"topic": {"enum": list(ALL_TOPICS)}}},
}
ROUTER_SYSTEM = ("Choose the one topic that fits the user's question by calling choose_topic. Use out_of_scope when the "
                 "question is not about the rent-increase analysis, and forbidden for occupancy, vacancy, absorption or "
                 "rent roll. Never answer the question.")

FRENCH_WORDS = frozenset("quel quelle quels quelles comment pourquoi est les des une un du de la le au aux que qui quoi "
                         "et ou en pour sur dans par avec sans ce cette ces mon ma mes votre vos nous sont ont fait "
                         "combien quand où où hausse loyer loyers baux immeuble modèle modèles règle y a il elle "
                         "peut peuvent faut donc plus moins très".split())
ENGLISH_WORDS = frozenset("what which how why is are the a an of to in for on by with without this that these those my our "
                          "your and or do does did can could would should will be been it its there their rent rents "
                          "lease leases building models rule increase if when where who much many more less very "
                          "tell me about explain show give".split())
ACCENTED = re.compile(r"[àâçéèêëîïôûùüÿœ]")


@dataclass(frozen=True)
class Route:
    """Result of routing one question: the topic, its language and whether the match was clear."""

    topic: str
    lang: str
    score: float
    confident: bool


def normalize(text: str) -> str:
    """Lower-case, accent-free, apostrophes unified, spaces collapsed."""
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("’", "'").replace("œ", "oe"))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", plain).strip()


def detect_language(question: str, default: str = "fr") -> str:
    """'fr' or 'en' from accents and function words; the default stands on a tie."""
    lowered = question.lower().replace("’", "'")
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ]+", lowered)
    french = sum(word in FRENCH_WORDS for word in words) + len(ACCENTED.findall(lowered))
    english = sum(word in ENGLISH_WORDS for word in words)
    french += sum(lowered.startswith(prefix) for prefix in ("qu'", "l'", "d'")) + len(re.findall(r"\b[ldjqn]'", lowered))
    if english == french:
        return default
    return "en" if english > french else "fr"


def building_names(document: dict[str, Any] | None) -> tuple[str, ...]:
    """Building or property display names listed in the aggregates (`building_beds`, `newbuild_building`); empty if none."""
    if not document:
        return ()
    names = {str(row.get("building")) for row in document.get("building_beds") or [] if isinstance(row, dict) and row.get("building")}
    if document.get("newbuild_building"):
        names.add(str(document["newbuild_building"]))
    return tuple(sorted(names))


def _name_pattern(names: tuple[str, ...]) -> re.Pattern[str] | None:
    """One pattern matching any of the given display names (accent-free, lower-case, whole words)."""
    plain = sorted({normalize(name) for name in names if normalize(name)}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(name) for name in plain) + r")\b") if plain else None


def _matches(question: str, names: tuple[str, ...] = ()) -> dict[str, list[float]]:
    """Weights of the patterns that match, per answerable topic; display names add a building pattern at run time."""
    text = normalize(question)
    found = {topic: [weight for pattern, weight in patterns if pattern.search(text)] for topic, patterns in COMPILED.items()}
    name_pattern = _name_pattern(names)
    if name_pattern is not None and name_pattern.search(text):
        found.setdefault("buildings_segments", []).append(NAME_WEIGHT)
    return found


def scores(question: str, names: tuple[str, ...] = ()) -> dict[str, float]:
    """Keyword score of every answerable topic (each pattern counts once)."""
    return {topic: sum(weights) for topic, weights in _matches(question, names).items()}


def route(question: str, default_lang: str = "fr", names: tuple[str, ...] = ()) -> Route:
    """Map a question to one topic. Forbidden subjects win; no keyword at all means out of scope.

    Ties on the total score go to the topic with the strongest single pattern (a specific keyword beats generic words),
    then to the order of `TOPICS`. `names` are building display names read from the aggregates.
    """
    lang = detect_language(question, default_lang)
    text = normalize(question)
    if FORBIDDEN_PATTERN.search(text):
        return Route(FORBIDDEN, lang, 10.0, True)
    matches = _matches(question, names)
    topic_scores = {topic: sum(weights) for topic, weights in matches.items()}
    best = max(topic_scores.values())
    if best <= 0:
        return Route(OUT_OF_SCOPE, lang, 0.0, False)
    tied = [topic for topic in TOPICS if topic_scores.get(topic) == best]
    strongest = max(max(matches[topic]) for topic in tied)
    leaders = [topic for topic in tied if max(matches[topic]) == strongest]  # TOPICS order breaks the remaining ties
    runner_up = sorted(topic_scores.values(), reverse=True)[1]
    return Route(leaders[0], lang, best, best >= UNSURE_BELOW and best - runner_up >= 0.5)


def route_with_client(question: str, client: Any | None, call: Any, default_lang: str = "fr",
                      names: tuple[str, ...] = ()) -> Route:
    """`route`, then the model's enum choice when the router is unsure. `call(client, system, content, **extra)` is the
    API wrapper of app/narrative.py. Any failure keeps the deterministic result; the model is never required.
    """
    result = route(question, default_lang, names)
    if client is None or result.confident or result.topic == FORBIDDEN:
        return result
    try:
        response = call(client, ROUTER_SYSTEM, question, tools=[ROUTER_TOOL], tool_choice={"type": "tool", "name": "choose_topic"})
        chosen = next((block.input.get("topic") for block in response.content
                       if getattr(block, "type", "") == "tool_use" and block.name == "choose_topic"), None)
    except Exception:  # noqa: BLE001 - the deterministic route is always an acceptable answer
        return result
    if chosen in ALL_TOPICS and chosen != FORBIDDEN:
        return Route(chosen, result.lang, result.score, True)
    return result
