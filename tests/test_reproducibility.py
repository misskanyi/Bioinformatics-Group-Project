"""Scientific reproducibility checks: raw-data integrity, deterministic preprocessing,
alignment recomputation, homology-aware validation, baseline/metric consistency,
no fabricated probabilities, and candidate-shortlist calculations.

These recompute small, fast slices of the analysis and compare them with the cached
outputs using tolerances (not byte equality), so they hold across platforms. The full
rebuild is checked by scripts/compare_outputs.py in the scheduled CI workflow.
"""

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet_explorer import config as C  # noqa: E402
from pet_explorer import evidence as E  # noqa: E402
from pet_explorer import prediction, preprocess, shortlist  # noqa: E402
from pet_explorer.sequence_matching import SequenceMatcher, leave_one_out, make_aligner  # noqa: E402

AA = set(C.STANDARD_AA)


@pytest.fixture(scope="module")
def proteins():
    return pd.read_csv(C.F_PROTEINS)


@pytest.fixture(scope="module")
def pairs():
    return pd.read_csv(C.F_PAIRS)


# ---------------------------------------------------------------- raw data
def test_raw_pazy_schema_and_integrity():
    csv = pd.read_csv(C.F_CSV)
    assert list(csv.columns) == ["protein_id", "protein_name", "amino_acid_sequence"]
    assert len(csv) == 301 and csv.protein_id.is_unique
    assert csv.amino_acid_sequence.notna().all()
    fasta = {int(r.id): str(r.seq) for r in SeqIO.parse(C.DATA / "pazy_proteins.fasta", "fasta")}
    assert fasta == dict(zip(csv.protein_id, csv.amino_acid_sequence))


def test_raw_assay_json_schema():
    with gzip.open(C.F_ASSAYS, "rt") as fh:
        records = json.load(fh)
    assert len(records) == 579
    for r in records:
        assert {"protein_id", "protein_name", "assays"} <= set(r)
        for a in r["assays"]:
            assert {"substrate", "conditions", "measurements"} <= set(a)
    assert sum(a["substrate"] == "PET" for r in records for a in r["assays"]) == 5058


def test_other_raw_sources_present():
    for f in (C.F_PLASTICDB, C.F_DEGRADERS, C.F_UNIPROT, C.F_SUMMARY):
        assert f.exists(), f
    assert sum(1 for _ in SeqIO.parse(C.F_PLASTICDB, "fasta")) == 329


# ---------------------------------------------------------------- preprocessing
def test_preprocessing_is_deterministic_and_matches_cache(proteins):
    a, qc_a = preprocess.build_clean_set()
    b, _ = preprocess.build_clean_set()
    pd.testing.assert_frame_equal(a, b)
    assert qc_a.passed.all()
    assert a.protein_id.tolist() == proteins.protein_id.tolist()
    assert a.sequence.tolist() == proteins.sequence.tolist()
    assert all(set(s) <= AA for s in a.sequence)


# ---------------------------------------------------------------- alignment
def test_alignment_recomputation_matches_cache(proteins, pairs):
    seq = dict(zip(proteins.protein_id, proteins.sequence))
    al = make_aligner("local")
    sample = pairs.sample(25, random_state=0)
    for r in sample.itertuples():
        a, b = seq[r.protein_id_a], seq[r.protein_id_b]
        aln = al.align(a, b)[0]
        ident = aln.counts().identities
        assert ident / aln.length == pytest.approx(r.identity, abs=1e-4)
        assert ident / min(len(a), len(b)) == pytest.approx(r.identity_shorter, abs=1e-4)
        assert aln.score == pytest.approx(r.raw_score, abs=1e-3)


def test_self_alignment_is_full_identity(proteins):
    al = make_aligner("local")
    s = proteins.sequence.iloc[0]
    aln = al.align(s, s)[0]
    assert aln.counts().identities == len(s) == aln.length


def test_leave_one_out_generator_matches_cache(proteins, pairs):
    new = leave_one_out(proteins, pairs)
    old = pd.read_csv(C.F_LOO)
    assert list(new.columns) == ["q", "nn", "id", "band"]
    assert (new.q.values == old.q.values).all() and (new.nn.values == old.nn.values).all()
    assert (new.band.values == old.band.values).all()
    assert np.allclose(new.id, old.id, atol=1e-9)
    assert (new.q != new.nn).all()


# ---------------------------------------------------------------- homology-aware validation
def test_cv_folds_never_split_an_identity_group():
    from sklearn.model_selection import StratifiedGroupKFold
    d = pd.read_csv(C.PREDICTION / "prediction_dataset.csv")
    y, g = d.detected_at_60c.to_numpy(), d.identity_group_70.to_numpy()
    for r in range(prediction.N_REPEATS):
        cv = StratifiedGroupKFold(prediction.N_SPLITS, shuffle=True, random_state=prediction.SEED + r)
        for tr, te in cv.split(y, y, g):
            assert not set(g[tr]) & set(g[te])


def test_no_cross_fold_pair_reaches_70pct_identity(pairs):
    d = pd.read_csv(C.PREDICTION / "prediction_dataset.csv")
    grp = dict(zip(d.protein_id, d.identity_group_70))
    p = pairs[pairs.protein_id_a.isin(grp) & pairs.protein_id_b.isin(grp)]
    cross = p[p.protein_id_a.map(grp) != p.protein_id_b.map(grp)]
    assert cross.identity_shorter.max() < 0.70


# ---------------------------------------------------------------- baselines and metrics
def test_majority_baseline_is_exactly_chance():
    t = pd.read_csv(C.PREDICTION / "model_comparison.csv").set_index("model")
    assert t.loc["majority class", "roc_auc_mean"] == 0.5
    assert t.loc["majority class", "roc_auc_sd"] == 0.0


def test_fold_metrics_reproduce_model_comparison():
    """The per-fold table is the same CV run as model_comparison.csv, not a different one."""
    f = pd.read_csv(C.PREDICTION / "cv_fold_metrics.csv")
    t = pd.read_csv(C.PREDICTION / "model_comparison.csv").set_index("model")
    ok = f[~f.skipped_single_class]
    per_repeat = ok.groupby(["model", "repeat"])[["roc_auc", "balanced_accuracy"]].mean()
    for m, g in per_repeat.groupby(level=0):
        assert g.roc_auc.mean() == pytest.approx(t.loc[m, "roc_auc_mean"], abs=6e-4)
        assert g.roc_auc.std(ddof=0) == pytest.approx(t.loc[m, "roc_auc_sd"], abs=6e-4)
        assert g.balanced_accuracy.mean() == pytest.approx(t.loc[m, "balanced_accuracy_mean"], abs=6e-4)


def test_threshold_metrics_are_held_out_only():
    f = pd.read_csv(C.PREDICTION / "cv_fold_metrics.csv")
    ok = f[~f.skipped_single_class]
    assert ((ok.tp + ok.fp + ok.tn + ok.fn) == ok.n_test).all()
    assert (ok.tp + ok.fn == ok.n_test_positive).all()
    oof = pd.read_csv(C.PREDICTION / "oof_predictions.csv.gz")
    # each protein is scored at most once per model and repeat (never on its own training fold)
    assert not oof.duplicated(["model", "repeat", "protein_id"]).any()
    assert oof.score.between(0, 1).all()


def test_permutation_null_matches_summary():
    null = pd.read_csv(C.PREDICTION / "permutation_null.csv").null_roc_auc
    p = pd.read_csv(C.PREDICTION / "permutation_test.csv").iloc[0]
    assert len(null) == p.n_permutations
    assert null.mean() == pytest.approx(p.null_mean, abs=6e-4)
    assert np.percentile(null, 95) == pytest.approx(p.null_95th_percentile, abs=6e-4)
    assert (1 + (null >= p.observed_roc_auc).sum()) / (len(null) + 1) == pytest.approx(p.empirical_p, abs=1e-4)


# ---------------------------------------------------------------- no fabricated probabilities
def test_no_model_artifact_and_no_probability_columns():
    assert not (C.PREDICTION / "model.joblib").exists()
    s = pd.read_csv(shortlist.F_SHORTLIST)
    assert not [c for c in s.columns if "prob" in c.lower() or "predict" in c.lower()]


def test_negative_result_is_not_overstated():
    p = pd.read_csv(C.PREDICTION / "permutation_test.csv").iloc[0]
    assert p.empirical_p >= 0.05, "The 60 °C model now beats its null: update the conclusions before shipping."


# ---------------------------------------------------------------- candidate shortlist
@pytest.fixture(scope="module")
def short():
    return pd.read_csv(shortlist.F_SHORTLIST)


def test_shortlist_covers_exactly_the_eligible_candidates(short):
    elig = pd.read_csv(shortlist.F_ELIGIBILITY)
    assert set(short.sequence_sha1) == set(elig[elig.eligible_for_ranking].sequence_sha1)
    tested = set(elig[elig.status == "experimentally_tested"].sequence_sha1)
    assert not tested & set(short.sequence_sha1)


def test_shortlist_tiers_follow_the_evidence(short):
    s = short[short.evidence_category != "invalid"]
    for r in s.itertuples():
        assert r.priority_tier == shortlist.tier(r.evidence_category, r.similarity_band, r.rule)
    assert s.priority_tier.is_monotonic_increasing
    assert (s[s.priority_tier == 1].evidence_category == E.GREEN).all()
    assert (s[s.priority_tier == 5].evidence_category == E.RED).all()


def test_shortlist_never_claims_activity_or_inactivity(short):
    text = " ".join(short.prioritisation_reason.fillna("")).lower()
    for phrase in ("is pet-inactive", "will degrade", "probability", "predicted active"):
        assert phrase not in text
    assert short.limitations.str.contains("not a validated prediction").all()


def test_shortlist_rows_recompute(short, proteins):
    """Re-run the matcher + rules for the top candidates; numbers and colours must agree."""
    m = SequenceMatcher(proteins)
    cards = proteins.set_index("protein_id")
    for r in short[short.evidence_category != "invalid"].head(5).itertuples():
        seq = pd.read_csv(shortlist.F_MASTER).set_index("sequence_sha1").sequence[r.sequence_sha1]
        _, q, hits = m.search(seq, top_n=1, n_shuffles=E.N_SHUFFLES, seed=E.SHUFFLE_SEED)
        h = hits[0]
        a = E.assess(h, cards.loc[h.protein_id].to_dict(), q)
        assert h.protein_name == r.closest_reference
        assert h.identity == pytest.approx(r.identity, abs=1e-4)
        assert h.shuffled_z == pytest.approx(r.shuffled_z, abs=0.11)
        assert (a["category"], a["rule"]) == (r.evidence_category, r.rule)
