"""Validation of cached pipeline outputs (run `python -m pet_explorer.pipeline` first)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet_explorer import config as C  # noqa: E402
from pet_explorer.organisms import UNKNOWN  # noqa: E402

pytestmark = pytest.mark.skipif(not (C.ORGANISMS / "protein_organisms.csv").exists(),
                                reason="pipeline outputs not generated")


@pytest.fixture(scope="module")
def proteins():
    return pd.read_csv(C.F_PROTEINS)


def test_every_protein_has_one_cluster(proteins):
    a = pd.read_csv(C.CLUSTERING / "cluster_assignments.csv")
    assert len(a) == len(proteins) == 298
    assert set(a.protein_id) == set(proteins.protein_id)
    assert a.cluster.notna().all() and a.subcluster.notna().all()
    assert a.subcluster.str.startswith(tuple(a.cluster.unique())).all()


def test_pairwise_table_complete(proteins):
    p = pd.read_csv(C.F_PAIRS)
    n = len(proteins)
    assert len(p) == n * (n - 1) // 2
    assert p[["identity", "coverage_a", "coverage_b", "identity_shorter"]].stack().between(0, 1).all()


def test_network_edges_respect_threshold():
    e = pd.read_csv(C.NETWORK / "ssn_edges.csv")
    n = pd.read_csv(C.NETWORK / "ssn_nodes.csv")
    assert len(n) == 298
    assert (e.identity >= C.EDGE_MIN_IDENTITY).all()
    assert (e.min_coverage >= C.EDGE_MIN_COVERAGE).all()
    assert (e.interaction == "sequence_similarity").all()
    assert set(e.source) | set(e.target) <= set(n.id)
    assert {"organism", "cluster", "protein_name"} <= set(n.columns)


def test_no_optimum_claimed_from_few_temperatures():
    s = pd.read_csv(C.TEMPERATURE / "protein_temperature_summary.csv")
    one = s[s.n_temperatures_tested == 1]
    assert one.temperature_optimum_status.str.contains("insufficient").all()
    two = s[s.n_temperatures_tested == 2]
    assert two.temperature_optimum_status.str.contains("cannot be determined").all()
    assert not s.temperature_optimum_status.str.contains(r"\boptimum is\b").any()


def test_comparable_series_have_three_temperatures():
    s = pd.read_csv(C.TEMPERATURE / "comparable_temperature_series.csv")
    assert (s.n_temperatures >= 3).all()
    assert s.groupby(["protein_id", "literature_doi", "metric_type", "unit"]).size().min() >= 1


def test_organisms_never_expression_hosts():
    o = pd.read_csv(C.ORGANISMS / "protein_organisms.csv")
    assert len(o) == 298
    assert not o.organism.str.contains("Escherichia coli").any()
    unknown = o[o.organism_evidence == "none"]
    assert (unknown.organism == UNKNOWN).all()
    assert (o.loc[o.organism != UNKNOWN, "organism_evidence"] != "none").all()
