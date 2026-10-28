"""API tests: every response must agree with the cached analysis outputs.

    .venv/bin/pytest backend/tests -q        # from the repository root
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from pet_explorer import config as C


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def proteins():
    return pd.read_csv(C.F_PROTEINS)


def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["proteins"] == 298 and r["matcher_ready"]


def test_overview_matches_tables(client, proteins):
    s = client.get("/api/overview").json()["stats"]
    assert s["proteins"] == len(proteins)
    assert s["publications"] == proteins.dois.str.split("; ").explode().nunique()
    org = pd.read_csv(C.ORGANISMS / "protein_organisms.csv")
    assert s["proteins_with_organism"] == int((org.organism_evidence != "none").sum())
    assert s["network_edges"] == len(pd.read_csv(C.NETWORK / "ssn_edges.csv"))


def test_match_is_consistent_with_its_alignment(client, proteins):
    seq = proteins.loc[proteins.protein_name == "ISPETase", "sequence"].iloc[0]
    r = client.post("/api/sequence/match", json={"sequence": seq[20:220]}).json()
    assert r["length"] == 200 and len(r["hits"]) == 5
    assert r["hits"][0]["protein_name"] == "ISPETase"
    scores = [h["normalised_score"] for h in r["hits"]]
    assert scores == sorted(scores, reverse=True)
    for h in r["hits"]:
        q, t = h["aligned_query"], h["aligned_target"]
        assert len(q) == len(t) == h["aligned_columns"]
        same = sum(a == b and a != "-" for a, b in zip(q, t))
        assert abs(same / len(q) - h["identity"]) < 1e-9
        assert q.replace("-", "") == r["sequence"][h["query_range"][0] - 1:h["query_range"][1]]
        assert 0 <= h["query_coverage"] <= 1 and 0 <= h["target_coverage"] <= 1
        assert "probability" not in h  # no fabricated activity score


@pytest.mark.parametrize("text", ["", "ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCATCG", "MKV", ">a\nMKVLLLLLLLLLLLLLLLLLLLLLLLLLLLLL\n>b\nMKV"])
def test_bad_input_rejected(client, text):
    r = client.post("/api/sequence/match", json={"sequence": text})
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


def test_network_threshold_filter(client):
    pairs = pd.read_csv(C.F_PAIRS)
    r = client.get("/api/network?min_identity=0.6&min_coverage=0.8").json()
    expected = ((pairs.identity >= 0.6) & (pairs.min_coverage >= 0.8)).sum()
    assert r["stats"]["edges"] == len(r["edges"]) == expected
    assert all(e[2] >= 0.6 - 1e-3 and e[3] >= 0.8 - 1e-3 for e in r["edges"])
    assert len(r["nodes"]) == 298


def test_unknown_organisms_are_never_named(client):
    r = client.get("/api/organisms").json()
    named = {p["protein_id"] for o in r["organisms"] for p in o["proteins"]}
    unknown = {u["protein_id"] for u in r["unknown"]}
    assert not named & unknown
    assert len(unknown) == r["evidence_counts"]["none"]
    assert all(p["evidence"] != "none" for o in r["organisms"] for p in o["proteins"])


def test_conditions_rows_belong_to_reference_set(client, proteins):
    r = client.get("/api/conditions").json()
    ids = {row[0] for row in r["assays"]}
    assert ids <= set(proteins.protein_id)
    assert all(len(s["temperatures"]) >= 3 for s in r["series"])


def test_downloads_are_whitelisted(client):
    assert client.get("/api/downloads/ssn_edges").status_code == 200
    assert client.get("/api/downloads/..%2F..%2Fdata%2Fdegraders_list.tsv").status_code == 404
    assert client.get("/api/proteins/999999").status_code == 404
