"""Tests for concession→lease linking and net-rent reconstruction (incentives.linking, incentives.reconcile). Owner: FCT.

Hand-made leases and concessions with exact arithmetic: net = contract - (lump + monthly x months) / term. No CRM data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from halolens.contracts import CONCESSIONS_COLUMNS, LEASES_COLUMNS, LINKS_COLUMNS
from halolens.incentives.linking import link_concessions
from halolens.incentives.reconcile import (credit_totals, hypothesis_comparison, lease_term_months,
                                            reconciliation_by_year, reconciliation_rate, reconstruct_net_rent)

CONTRACT = 1200.0
TERM = 12
PROMO = 600.0            # lump credit
PARKING = 50.0           # monthly credit
PARKING_MONTHS = 6


def lease(unit_id: str, start: str, sign: str, net: float, months: int = TERM, contract: float = CONTRACT) -> dict:
    start_ts = pd.Timestamp(start)
    return {"unit_id": unit_id, "prop_code": "aaa", "unit_code": unit_id, "building": "B", "province": "QC",
            "city": "Test", "beds": 1, "baths": 1.0, "sqft": 700, "floor": 1, "unit_type": "1_1", "lease_seq": 1,
            "is_renewal": False, "sign_date": pd.Timestamp(sign), "lease_start": start_ts,
            "lease_end": start_ts + pd.DateOffset(months=months) - pd.Timedelta(days=1),
            "term_months_daycount": float(months), "term_label": "Long Term", "rent_contract": contract,
            "rent_net_all_incentives": net, "has_concession": net < contract}


def concession(cid: int, unit_id: str, date_from: str, code: str, amount: float, months: float) -> dict:
    return {"concession_id": cid, "unit_id": unit_id, "prop_code": "aaa", "unit_code": unit_id, "building": "B",
            "province": "QC", "charge_code": code, "charge_desc": code, "credit_amount": amount,
            "date_from": pd.Timestamp(date_from), "date_to": pd.Timestamp(date_from) + pd.Timedelta(days=30),
            "months": months, "credit_kind": "lump" if code == "PromoPay" else "monthly"}


def frames(lease_rows, concession_rows):
    leases = pd.DataFrame(lease_rows)[LEASES_COLUMNS]
    concessions = pd.DataFrame(concession_rows)[CONCESSIONS_COLUMNS]
    return leases, concessions


NET_WITH_PROMO = CONTRACT - PROMO / TERM                       # 1150
NET_WITH_PARKING = CONTRACT - PARKING * PARKING_MONTHS / TERM  # 1175
NET_WITH_BOTH = CONTRACT - (PROMO + PARKING * PARKING_MONTHS) / TERM


# ---------------------------------------------------------------------------
# Credit arithmetic: no amount multiplication
# ---------------------------------------------------------------------------
def test_lump_credit_counts_once_even_when_months_is_larger_than_one():
    """A PromoPay row with months = 6 must not be multiplied by 6."""
    rows = pd.DataFrame([concession(0, "u1", "2024-01-01", "PromoPay", PROMO, 6.0)])
    assert credit_totals(rows)["total"].iloc[0] == PROMO


def test_monthly_credit_is_amount_times_months():
    rows = pd.DataFrame([concession(0, "u1", "2024-01-01", "freepark", PARKING, PARKING_MONTHS)])
    assert credit_totals(rows)["total"].iloc[0] == PARKING * PARKING_MONTHS


def test_the_rejected_lump_times_months_hypothesis_is_only_available_on_request():
    rows = pd.DataFrame([concession(0, "u1", "2024-01-01", "PromoPay", PROMO, 6.0)])
    assert credit_totals(rows, lump_multiplies_months=True)["total"].iloc[0] == PROMO * 6


def test_reconstruction_never_multiplies_a_lump_credit(raw):
    """Net rent rebuilt from the synthetic records equals the reported one with the lump counted once."""
    from halolens.io import canonicalize
    tables = canonicalize(raw)
    cfg_links = link_concessions(tables.concessions, tables.leases, {"linking": {"recon_tolerance_dollars": 1.0,
                                                                                  "max_combinations": 4096}})
    rebuilt = reconstruct_net_rent(tables.leases, tables.concessions, cfg_links)
    assert rebuilt["recon_error"].abs().max() < 1.0


def test_term_months_comes_from_the_lease_dates():
    leases = pd.DataFrame([lease("u1", "2024-01-01", "2023-12-01", 1000, months=12),
                           lease("u2", "2024-01-01", "2023-12-01", 1000, months=6),
                           lease("u3", "2024-01-01", "2023-12-01", 1000, months=18)])
    assert lease_term_months(leases).tolist() == [12, 6, 18]


# ---------------------------------------------------------------------------
# Candidate rule and statuses
# ---------------------------------------------------------------------------
def test_single_candidate_links_as_unique_and_reconstructs_exactly(cfg):
    leases, concessions = frames([lease("u1", "2024-01-01", "2023-12-01", NET_WITH_PROMO)],
                                 [concession(0, "u1", "2024-01-01", "PromoPay", PROMO, 1.0)])
    links = link_concessions(concessions, leases, cfg)
    assert list(links.columns) == LINKS_COLUMNS
    assert links["status"].tolist() == ["unique"] and links["rule"].tolist() == ["single_candidate"]
    assert links["lease_start"].iloc[0] == pd.Timestamp("2024-01-01")
    assert links["recon_error"].iloc[0] == pytest.approx(0.0)
    rebuilt = reconstruct_net_rent(leases, concessions, links)
    assert rebuilt["rent_net_reconstructed"].iloc[0] == pytest.approx(NET_WITH_PROMO)


def test_concession_for_another_unit_is_never_a_candidate(cfg):
    leases, concessions = frames([lease("u1", "2024-01-01", "2023-12-01", NET_WITH_PROMO)],
                                 [concession(0, "u2", "2024-01-01", "PromoPay", PROMO, 1.0)])
    links = link_concessions(concessions, leases, cfg)
    assert links["status"].tolist() == ["unresolved"] and links["rule"].tolist() == ["no_candidate"]
    assert links["n_candidates"].tolist() == [0] and pd.isna(links["lease_start"].iloc[0])
    assert np.isnan(links["recon_error"].iloc[0])


def test_lease_signed_after_the_concession_is_not_a_candidate(cfg):
    leases, concessions = frames([lease("u1", "2024-01-01", "2024-02-15", NET_WITH_PROMO)],
                                 [concession(0, "u1", "2024-01-20", "PromoPay", PROMO, 1.0)])
    assert link_concessions(concessions, leases, cfg)["n_candidates"].tolist() == [0]


def test_lease_that_ended_before_the_concession_is_not_a_candidate(cfg):
    leases, concessions = frames([lease("u1", "2022-01-01", "2021-12-01", NET_WITH_PROMO)],
                                 [concession(0, "u1", "2024-01-01", "PromoPay", PROMO, 1.0)])
    assert link_concessions(concessions, leases, cfg)["n_candidates"].tolist() == [0]


def test_unit_with_two_leases_links_each_concession_by_date(cfg):
    leases, concessions = frames(
        [lease("u1", "2023-01-01", "2022-12-01", NET_WITH_PROMO), lease("u1", "2024-01-01", "2023-12-01", NET_WITH_PARKING)],
        [concession(0, "u1", "2023-01-01", "PromoPay", PROMO, 1.0),
         concession(1, "u1", "2024-01-01", "freepark", PARKING, PARKING_MONTHS)])
    links = link_concessions(concessions, leases, cfg)
    assert links["status"].tolist() == ["unique", "unique"]
    assert links["lease_start"].tolist() == [pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01")]


# ---------------------------------------------------------------------------
# Ambiguity resolved by reconciliation fit
# ---------------------------------------------------------------------------
def overlapping_leases(old_net: float, new_net: float) -> list[dict]:
    """Old lease runs to 2024-06-30; the renewal was signed in April, so a May concession fits both."""
    return [lease("u1", "2023-07-01", "2023-06-01", old_net), lease("u1", "2024-07-01", "2024-04-01", new_net)]


def test_ambiguous_concession_goes_to_the_lease_whose_net_rent_it_explains(cfg):
    """Concession dated inside the old lease but after the renewal was signed; only the renewal's net rent shows it."""
    leases, concessions = frames(overlapping_leases(CONTRACT, NET_WITH_PROMO),
                                 [concession(0, "u1", "2024-05-15", "PromoPay", PROMO, 1.0)])
    links = link_concessions(concessions, leases, cfg)
    assert links["n_candidates"].tolist() == [2]
    assert links["status"].tolist() == ["resolved_by_fit"] and links["rule"].tolist() == ["best_fit"]
    assert links["lease_start"].iloc[0] == pd.Timestamp("2024-07-01")
    assert links["recon_error"].iloc[0] == pytest.approx(0.0)


def test_ambiguous_concession_follows_the_fit_to_the_older_lease_too(cfg):
    leases, concessions = frames(overlapping_leases(NET_WITH_PROMO, CONTRACT),
                                 [concession(0, "u1", "2024-05-15", "PromoPay", PROMO, 1.0)])
    assert link_concessions(concessions, leases, cfg)["lease_start"].iloc[0] == pd.Timestamp("2023-07-01")


def test_equally_good_candidates_stay_unresolved(cfg):
    """Both leases show the same discount: the record cannot tell them apart."""
    leases, concessions = frames(overlapping_leases(NET_WITH_PROMO, NET_WITH_PROMO),
                                 [concession(0, "u1", "2024-05-15", "PromoPay", PROMO, 1.0)])
    links = link_concessions(concessions, leases, cfg)
    assert links["status"].tolist() == ["unresolved"] and links["rule"].tolist() == ["tied_fit"]
    assert pd.isna(links["lease_start"].iloc[0])


def test_two_ambiguous_concessions_are_assigned_jointly(cfg):
    """Promo goes to the old lease and parking to the renewal; each fits only that way round."""
    leases, concessions = frames(overlapping_leases(NET_WITH_PROMO, NET_WITH_PARKING),
                                 [concession(0, "u1", "2024-05-15", "PromoPay", PROMO, 1.0),
                                  concession(1, "u1", "2024-05-16", "freepark", PARKING, PARKING_MONTHS)])
    links = link_concessions(concessions, leases, cfg)
    assert links["status"].tolist() == ["resolved_by_fit", "resolved_by_fit"]
    assert links["lease_start"].tolist() == [pd.Timestamp("2023-07-01"), pd.Timestamp("2024-07-01")]


def test_too_many_combinations_leave_concessions_unresolved(cfg):
    capped = {**cfg, "linking": {**cfg["linking"], "max_combinations": 1}}
    leases, concessions = frames(overlapping_leases(CONTRACT, NET_WITH_PROMO),
                                 [concession(0, "u1", "2024-05-15", "PromoPay", PROMO, 1.0)])
    links = link_concessions(concessions, leases, capped)
    assert links["rule"].tolist() == ["too_many_combinations"] and links["status"].tolist() == ["unresolved"]


def test_unique_credit_on_a_lease_is_counted_when_fitting_an_ambiguous_one(cfg):
    """The renewal already carries a unique parking credit; the extra ambiguous promo must fit on top of it."""
    leases, concessions = frames(
        overlapping_leases(CONTRACT, NET_WITH_BOTH),
        [concession(0, "u1", "2024-07-01", "freepark", PARKING, PARKING_MONTHS),
         concession(1, "u1", "2024-05-15", "PromoPay", PROMO, 1.0)])
    links = link_concessions(concessions, leases, cfg)
    assert links["lease_start"].tolist() == [pd.Timestamp("2024-07-01"), pd.Timestamp("2024-07-01")]
    assert links["status"].tolist() == ["unique", "resolved_by_fit"]


# ---------------------------------------------------------------------------
# Reconstruction and summaries
# ---------------------------------------------------------------------------
def test_unresolved_concessions_are_ignored_by_the_reconstruction(cfg):
    leases, concessions = frames([lease("u1", "2024-01-01", "2023-12-01", NET_WITH_PROMO)],
                                 [concession(0, "u2", "2024-01-01", "PromoPay", PROMO, 1.0)])
    links = link_concessions(concessions, leases, cfg)
    rebuilt = reconstruct_net_rent(leases, concessions, links)
    assert rebuilt["rent_net_reconstructed"].iloc[0] == pytest.approx(CONTRACT)
    assert rebuilt["recon_error"].iloc[0] == pytest.approx(CONTRACT - NET_WITH_PROMO)   # unexplained discount


def test_reconstruction_has_one_row_per_lease_including_leases_without_concessions(cfg):
    leases, concessions = frames(
        [lease("u1", "2024-01-01", "2023-12-01", NET_WITH_BOTH), lease("u2", "2024-01-01", "2023-12-01", CONTRACT)],
        [concession(0, "u1", "2024-01-01", "PromoPay", PROMO, 1.0),
         concession(1, "u1", "2024-01-01", "freepark", PARKING, PARKING_MONTHS)])
    rebuilt = reconstruct_net_rent(leases, concessions, link_concessions(concessions, leases, cfg))
    assert len(rebuilt) == 2
    assert rebuilt["n_concessions"].tolist() == [2, 0]
    assert rebuilt["lump_credit_total"].tolist() == [PROMO, 0.0]
    assert rebuilt["monthly_credit_total"].tolist() == [PARKING * PARKING_MONTHS, 0.0]
    assert reconciliation_rate(rebuilt, cfg) == 1.0


def test_rate_counts_leases_within_the_tolerance(cfg):
    rebuilt = pd.DataFrame({"recon_error": [0.0, 0.5, -0.9, 2.0], "rent_net_reported": [1, 1, 1, 1],
                            "rent_contract": [2, 1, 2, 2]})
    assert reconciliation_rate(rebuilt, cfg) == pytest.approx(0.75)
    assert reconciliation_rate(rebuilt, cfg, only_discounted=True) == pytest.approx(2 / 3)


def test_hypothesis_comparison_rejects_leaving_out_accessories_and_multiplying_lumps(cfg):
    leases, concessions = frames(
        [lease("u1", "2024-01-01", "2023-12-01", NET_WITH_BOTH)],
        [concession(0, "u1", "2024-01-01", "PromoPay", PROMO, 6.0),
         concession(1, "u1", "2024-01-01", "freepark", PARKING, PARKING_MONTHS)])
    table = hypothesis_comparison(leases, concessions, link_concessions(concessions, leases, cfg), cfg).set_index("scenario")
    assert table.loc["lump_once_all_codes", "rate_all"] == 1.0
    assert table.loc["lump_times_months", "rate_all"] == 0.0
    assert table.loc["without_accessories", "rate_all"] == 0.0


def test_reconciliation_by_year_reports_counts_and_rates(cfg):
    leases, concessions = frames(
        [lease("u1", "2023-01-01", "2022-12-01", NET_WITH_PROMO), lease("u1", "2024-01-01", "2023-12-01", CONTRACT)],
        [concession(0, "u1", "2023-01-01", "PromoPay", PROMO, 1.0)])
    rebuilt = reconstruct_net_rent(leases, concessions, link_concessions(concessions, leases, cfg))
    table = reconciliation_by_year(rebuilt, cfg).set_index("year")
    assert table["n_leases"].to_dict() == {2023: 1, 2024: 1}
    assert table["n_discounted"].to_dict() == {2023: 1, 2024: 0}
    assert table["rate_all"].to_dict() == {2023: 1.0, 2024: 1.0}


def test_synthetic_links_resolve_and_reconcile_every_lease(tables, cfg):
    """Done-when check on the synthetic fixtures: reconciliation rate reported (aggregates only)."""
    links = link_concessions(tables.concessions, tables.leases, cfg)
    assert len(links) == len(tables.concessions)
    assert set(links["status"]) <= {"unique", "resolved_by_fit", "unresolved"}
    rebuilt = reconstruct_net_rent(tables.leases, tables.concessions, links)
    assert reconciliation_rate(rebuilt, cfg) == 1.0
    assert reconciliation_rate(rebuilt, cfg, only_discounted=True) == 1.0
