"""French date labels and Markdown helpers for the notebook (sections 03, 04, 06, 07, 12).

Dates shown in the notebook text are generated from config or data with these helpers, never typed by hand.
Section 12 renders the references file with `track_references_markdown`, so no reference text is copied
into the notebook.
"""

from __future__ import annotations

import re

import pandas as pd

FRENCH_MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                 "novembre", "décembre")
FIRST_DAY = 1
FIRST_DAY_LABEL = "1er"
LEAP_YEAR = 2000  # any leap year: lets a month-day such as "02-29" parse without a real year


def french_month(date) -> str:
    """Month name of a date in French, e.g. 'octobre'."""
    return FRENCH_MONTHS[pd.Timestamp(date).month - 1]


def french_date(date, with_year: bool = True) -> str:
    """'15 novembre 2018' (or '15 novembre' with `with_year=False`); day 1 reads '1er'."""
    stamp = pd.Timestamp(date)
    day = FIRST_DAY_LABEL if stamp.day == FIRST_DAY else str(stamp.day)
    text = f"{day} {french_month(stamp)}"
    return f"{text} {stamp.year}" if with_year else text


def french_month_year(date) -> str:
    """'mai 2023'."""
    stamp = pd.Timestamp(date)
    return f"{french_month(stamp)} {stamp.year}"


def french_month_day(month_day: str) -> str:
    """A config month-day such as '12-31' as '31 décembre'."""
    return french_date(f"{LEAP_YEAR}-{month_day}", with_year=False)


MAX_HEADING_LEVEL = 6  # deepest Markdown heading
CODE_FENCE = "```"
HEADING_PATTERN = re.compile(r"^(#+)(\s.*)$")


def track_references_markdown(text: str, boilerplate: str, heading_shift: int) -> str:
    """Body of the references file, ready to sit under a notebook subsection.

    Input: the raw Markdown of `docs/references.md`, the editing instruction to hide (`boilerplate`) and the
    number of levels to push headings down. Output: the same entries with the file's leading title (`# References`) and the boilerplate
    sentence removed, every heading moved `heading_shift` levels down (capped at 6, code fences left alone), and outer
    blank lines trimmed. An empty string means the file has no entries yet.
    """
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    title = HEADING_PATTERN.match(lines[first]) if first is not None else None
    if title and len(title[1]) == 1:
        lines = lines[first + 1:]
    shifted, in_fence = [], False
    for line in lines:
        if line.lstrip().startswith(CODE_FENCE):
            in_fence = not in_fence
        heading = None if in_fence else HEADING_PATTERN.match(line)
        if heading:
            line = "#" * min(len(heading[1]) + heading_shift, MAX_HEADING_LEVEL) + heading[2]
        shifted.append(line)
    body = "\n".join(shifted)
    if boilerplate:
        body = body.replace(boilerplate, "")
    body = "\n".join(line.rstrip() if line.strip() else "" for line in body.splitlines())
    return re.sub(r"\n{3,}", "\n\n", body).strip()
