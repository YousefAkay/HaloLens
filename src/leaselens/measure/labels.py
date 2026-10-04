"""French date labels for notebook Markdown (MSR sections 03, 04, 06, 07).

Owner: MSR. Dates shown in the notebook text are generated from config or data with these helpers, never typed by hand.
"""

from __future__ import annotations

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
