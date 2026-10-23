"""Generate fully invented fixtures in the source schema. Owner: INT.

No real record, name, address or value is used: buildings, codes and rents are made up.
The fixtures deliberately reproduce the structural traps of the real extract so tests are meaningful:
  - unit codes with leading zeros (must be read as text)
  - one site hosting two property codes with overlapping unit codes (sSite + sUnitCode collides)
  - buildings entering the portfolio later (composition effect)
  - renewals vs turnovers, 6-month leases, turnover downtime between leases
  - PromoPay one-off credits and monthly accessory credits (parking), with net rent consistent with
    net = contract - (lump credits + monthly credits x months) / term
  - asking rents posted before turnover leases, a listings snapshot with varying sAsOf months

Run:  python scripts/make_synthetic.py      (writes data/synthetic/*.csv + manifest.json)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from halolens.config import load_config  # noqa: E402
from halolens.contracts import SOURCE_FILES  # noqa: E402

# ---- Invented portfolio --------------------------------------------------------------------
PROPERTIES = [
    # site,          prop_code, building,            city,        province, first_year, units, base_rent
    ("north-court", "nc1", "North Court",        "Laval",      "Quebec",  2018, 8, 1400),
    ("north-court", "nc2", "North Court",        "Laval",      "Quebec",  2019, 8, 1500),  # same site → collisions
    ("cedar-park",  "cdp", "Cedar Park",         "Montreal",   "Quebec",  2023, 8, 2100),  # enters later
    ("lakeview",    "lkv", "Lakeview Residences", "Ottawa",    "Ontario", 2023, 8, 2500),  # Ontario, enters later
]
LAST_YEAR = 2025
YEAR_GROWTH = {2018: 0.020, 2019: 0.022, 2020: 0.030, 2021: 0.040, 2022: 0.050,
               2023: 0.022, 2024: 0.035, 2025: 0.065}            # invented market path
RENEWAL_DISCOUNT = 0.01        # renewals grow a bit slower than turnovers (invented)
GROWTH_NOISE_SD = 0.015
RENEWAL_PROBABILITY = 0.6
SHORT_LEASE_PROBABILITY = 0.05
CONCESSION_PROBABILITY = {2018: 0.3, 2023: 0.5, 2024: 0.75, 2025: 0.85}
PARKING_MONTHLY_CREDIT = 150.0
PROMO_SHARE_OF_RENT = 0.8
ASKING_PREMIUM = 0.02          # asking ≈ 2% above signed rent (invented)
SEED = 7


def concession_probability(year: int) -> float:
    eligible = [y for y in CONCESSION_PROBABILITY if y <= year]
    return CONCESSION_PROBABILITY[max(eligible)]


def build(seed: int = SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    leases, concessions, asking, listings = [], [], [], []
    h_unit = 9000
    for p_index, (site, prop, building, city, state, first_year, n_units, base_rent) in enumerate(PROPERTIES):
        h_property, h_building = str(500 + p_index), str(60 + PROPERTIES.index(
            next(x for x in PROPERTIES if x[2] == building)))
        prov = "qc" if state == "Quebec" else "on"
        for u in range(n_units):
            h_unit += 1
            floor = 1 + u // 4
            unit_code = f"{floor:02d}{(u % 4) + 1:02d}"         # e.g. "0101": leading zero
            beds = int(rng.choice([1, 2, 3], p=[0.4, 0.45, 0.15]))
            baths = 1.0 if beds == 1 else 2.0
            sqft = int(500 + 250 * beds + rng.integers(-40, 40))
            unit_type = f"{beds}_{int(baths)}"
            common = dict(hProperty=h_property, hUnit=str(h_unit), hBuilding=h_building, sPropCode=prop,
                          sUnitCode=unit_code, sBuilding=building, sCity=city, sState=state, sSite=site,
                          sBeds=beds, sSqft=sqft, sFloor=floor)
            rent = round(base_rent * (1 + 0.25 * (beds - 1)) * (1 + rng.normal(0, 0.03)))
            start = pd.Timestamp(f"{first_year}-{rng.integers(1, 13):02d}-01")
            seq = 0
            while start.year <= LAST_YEAR:
                seq += 1
                is_renewal = seq > 1 and rng.random() < RENEWAL_PROBABILITY
                term = 6 if rng.random() < SHORT_LEASE_PROBABILITY else 12
                if seq > 1:
                    growth = YEAR_GROWTH[start.year] - (RENEWAL_DISCOUNT if is_renewal else 0)
                    rent = round(rent * (1 + growth + rng.normal(0, GROWTH_NOISE_SD)))
                end = start + pd.DateOffset(months=term) - pd.Timedelta(days=1)
                sign = start - pd.Timedelta(days=int(rng.integers(10, 60)))
                lump, monthly, months = 0.0, 0.0, 0
                if rng.random() < concession_probability(start.year):
                    if rng.random() < 0.6:
                        lump = round(rent * PROMO_SHARE_OF_RENT * rng.uniform(0.5, 1.0), 2)
                        concessions.append(dict(common, sChargeCode="PromoPay",
                                                sChargeDesc="Promo - Payable in the future",
                                                sAmount=-lump, sDateFrom=start.date(),
                                                sDateTo=(start + pd.DateOffset(months=1) - pd.Timedelta(days=1)).date(),
                                                sMonths=1.0))
                    if rng.random() < 0.5:
                        months = int(rng.choice([3, 6]))
                        monthly = PARKING_MONTHLY_CREDIT
                        concessions.append(dict(common, sChargeCode="freepark", sChargeDesc="Free Parking",
                                                sAmount=-monthly, sDateFrom=start.date(),
                                                sDateTo=(start + pd.DateOffset(months=months) - pd.Timedelta(days=1)).date(),
                                                sMonths=float(months)))
                net = round(rent - (lump + monthly * months) / term, 2)
                leases.append(dict(common, sAddr1=f"{100 + p_index} Invented St.", sLatitude=45.0 + p_index / 10,
                                   sLongitude=-74.0 + p_index / 10, sLeaseTerm="Long Term", sPropType="Apartment",
                                   sRent=rent, sBaths=baths, sLink=f"/rental/{prov}/{city.lower()}/{prop}/{unit_code}",
                                   sFurnishing="Unfurnished", sAvailable=start.date(), sSmoking="Non-Smoking",
                                   sCats=True, sDogs=True, sRentEffective=net, sConcession=int(net < rent),
                                   sUnitSubtype=f"{beds} Bed", sUnitType=unit_type, sSignDate=sign.date(),
                                   sLeaseFrom=start.date(), sLeaseTo=end.date(),
                                   sTermMonths=round(term * 0.99 if term == 6 else float(term), 1),
                                   sTermSeq=seq, sRenewal=int(is_renewal)))
                if not is_renewal:
                    for back in range(1, int(rng.integers(1, 4)) + 1):
                        month = (start - pd.DateOffset(months=back)).to_period("M")
                        asking.append(dict(common, sMonth=str(month),
                                           sAskingRent=round(rent * (1 + ASKING_PREMIUM))))
                downtime = 0 if is_renewal or seq == 1 else int(rng.integers(0, 45))
                start = end + pd.Timedelta(days=1 + downtime)
            listings.append(dict(common, sAddr1=f"{100 + p_index} Invented St.", sLatitude=45.0 + p_index / 10,
                                 sLongitude=-74.0 + p_index / 10, sLeaseTerm="Long Term", sPropType="Apartment",
                                 sBaths=baths, sLink=f"/rental/{prov}/{city.lower()}/{prop}/{unit_code}",
                                 sFurnishing="Unfurnished", sSmoking="Non-Smoking", sCats=True, sDogs=True,
                                 sUnitType=unit_type, sUnitSubtype=f"{beds} Bed",
                                 sUnitDesc=f"{beds} bed, {int(baths)} bath", sRent=round(rent * 1.03),
                                 sAsOf=f"{LAST_YEAR}-{rng.integers(1, 13):02d}",
                                 sAvailable=f"{LAST_YEAR + 1}-{rng.integers(1, 10):02d}-01"))

    lease_cols = ["hProperty", "hUnit", "hBuilding", "sPropCode", "sUnitCode", "sBuilding", "sCity", "sState",
                  "sAddr1", "sLatitude", "sLongitude", "sLeaseTerm", "sPropType", "sRent", "sBeds", "sBaths",
                  "sSqft", "sLink", "sFurnishing", "sAvailable", "sSmoking", "sCats", "sDogs", "sRentEffective",
                  "sConcession", "sSite", "sUnitSubtype", "sUnitType", "sSignDate", "sLeaseFrom", "sLeaseTo",
                  "sTermMonths", "sTermSeq", "sRenewal", "sFloor"]
    concession_cols = ["hProperty", "hUnit", "hBuilding", "sPropCode", "sUnitCode", "sBuilding", "sSite", "sCity",
                       "sState", "sBeds", "sSqft", "sChargeCode", "sChargeDesc", "sAmount", "sDateFrom", "sDateTo",
                       "sMonths", "sFloor"]
    asking_cols = ["hProperty", "hUnit", "hBuilding", "sPropCode", "sUnitCode", "sBuilding", "sSite", "sCity",
                   "sState", "sBeds", "sSqft", "sMonth", "sAskingRent", "sFloor"]
    listing_cols = ["hProperty", "hUnit", "hBuilding", "sPropCode", "sUnitCode", "sBuilding", "sCity", "sState",
                    "sAddr1", "sLatitude", "sLongitude", "sLeaseTerm", "sPropType", "sBeds", "sBaths", "sSqft",
                    "sLink", "sFurnishing", "sSmoking", "sCats", "sDogs", "sSite", "sUnitType", "sUnitSubtype",
                    "sUnitDesc", "sRent", "sAsOf", "sAvailable", "sFloor"]
    asking_df = pd.DataFrame(asking)[asking_cols].drop_duplicates(["hUnit", "sMonth"])
    return {
        "leases": pd.DataFrame(leases)[lease_cols],
        "concessions": pd.DataFrame(concessions)[concession_cols],
        "asking": asking_df.reset_index(drop=True),
        "listings": pd.DataFrame(listings)[listing_cols],
    }


def write(out_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for logical, file_name in SOURCE_FILES.items():
        path = out_dir / file_name
        tables[logical].to_csv(path, index=False)
        entries.append({"path": file_name, "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"challengeId": "synthetic", "files": entries}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    cfg = load_config()
    target = ROOT / cfg["data"]["synthetic_dir"]
    data = build()
    write(target, data)
    for name, df in data.items():
        print(f"{name:<12} {len(df):>5} rows  {df.shape[1]:>2} columns")
    print(f"written to {target}")
