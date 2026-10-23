"""Loading, hash verification and data dictionary. Owner: INT."""

import shutil

import pytest

from leaselens.config import data_dir
from leaselens.contracts import SOURCE_FILES
from leaselens.io import load_raw, run_qa
from leaselens.io.load import verify_manifest


def test_manifest_hashes_verified(cfg):
    results = verify_manifest(data_dir(cfg))
    assert all(results.values())


def test_tampered_file_is_rejected(cfg, tmp_path):
    for item in data_dir(cfg).iterdir():
        shutil.copy(item, tmp_path / item.name)
    with open(tmp_path / SOURCE_FILES["leases"], "a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(ValueError):
        load_raw(tmp_path)


def test_leading_zeros_preserved(raw, tables):
    assert raw["listings"]["sUnitCode"].str.startswith("0").any()
    assert tables.leases["unit_code"].str.startswith("0").any()
    assert tables.leases["unit_id"].map(type).eq(str).all()


def test_unsafe_site_key_collides_but_safe_key_does_not(raw):
    listings = raw["listings"]
    assert listings.duplicated(["sSite", "sUnitCode"]).any()
    assert not listings.duplicated(["sPropCode", "sUnitCode"]).any()


def test_available_column_dropped_and_types(tables):
    assert "sAvailable" not in tables.leases.columns
    assert set(tables.leases["province"]) <= {"QC", "ON"}
    assert tables.leases["is_renewal"].dtype == bool
    assert (tables.concessions["credit_amount"] >= 0).all()
    assert set(tables.concessions["credit_kind"]) <= {"lump", "monthly"}
    assert (tables.concessions.loc[tables.concessions["charge_code"] == "PromoPay", "credit_kind"] == "lump").all()


def test_qa_passes_on_synthetic(raw, tables, cfg):
    report = run_qa(raw, tables, cfg["data"]["data_end_date"])
    assert (report["status"] == "pass").all(), report.loc[report["status"] != "pass", "check"].tolist()


# --- optional config/local.yaml: differently named source files ---------------------------------------------------
def test_local_yaml_overrides_source_file_names(tmp_path):
    import hashlib
    import json
    import shutil

    import yaml

    from leaselens.config import load_config, repo_root, source_files

    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    for name in ("core.yaml", "measure.yaml", "forecast.yaml"):
        shutil.copy(repo_root() / "config" / name, root / "config" / name)
    assert source_files(load_config(root)) == SOURCE_FILES  # no local file: defaults

    fake_names = {"leases": "my_leases.csv", "concessions": "my_credits.csv"}
    (root / "config" / "local.yaml").write_text(yaml.safe_dump({"data": {"source_files": fake_names}}), encoding="utf-8")
    names = source_files(load_config(root))
    assert names["leases"] == "my_leases.csv" and names["concessions"] == "my_credits.csv"
    assert names["asking"] == SOURCE_FILES["asking"]  # the rest keep their defaults
    assert load_config(root)["data"]["mode"] == load_config()["data"]["mode"]  # other keys untouched

    data = tmp_path / "data"
    data.mkdir()
    entries = []
    for logical, name in names.items():
        shutil.copy(repo_root() / "data" / "synthetic" / SOURCE_FILES[logical], data / name)
        entries.append({"path": name, "sha256": hashlib.sha256((data / name).read_bytes()).hexdigest()})
    (data / "manifest.json").write_text(json.dumps({"files": entries}), encoding="utf-8")
    raw = load_raw(data, source_files=names)
    assert set(raw) == set(SOURCE_FILES) and len(raw["leases"]) > 0
    with pytest.raises(ValueError):
        load_raw(data)  # default names are not listed in this manifest
