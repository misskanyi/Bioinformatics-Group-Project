"""Validation of the curation pipeline (run `python -m pet_explorer.curation` first).

These tests guard the scientific invariants, not just the plumbing: that a
sequence is the identity key, that no condition is collapsed into a global
label, that expression failures never become inactive labels, and that no
identity group straddles the train/test boundary.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet_explorer import curation as K  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (K.CURATION / "proteins_master.csv").exists(),
    reason="curation outputs not generated (run python -m pet_explorer.curation)",
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def proteins():
    return pd.read_csv(K.CURATION / "proteins_master.csv")


@pytest.fixture(scope="module")
def observations():
    return pd.read_csv(K.CURATION / "experimental_observations.csv")


@pytest.fixture(scope="module")
def labels():
    return pd.read_csv(K.CURATION / "condition_specific_labels.csv")


@pytest.fixture(scope="module")
def groups():
    return pd.read_csv(K.CURATION / "homology_groups.csv")


@pytest.fixture(scope="module")
def splits():
    return pd.read_csv(K.CURATION / "split_assignments.csv")


@pytest.fixture(scope="module")
def eligibility():
    return pd.read_csv(K.CURATION / "candidate_eligibility.csv")


# --------------------------------------------------------------------------
# Sequence hashing - the key the whole registry rests on
# --------------------------------------------------------------------------

def test_hash_is_stable_and_whitespace_insensitive():
    assert K.sequence_hash("MKV LLA") == K.sequence_hash("mkvlla")
    assert K.sequence_hash("MKVLLA*") == K.sequence_hash("MKVLLA")
    assert K.sequence_hash("MKVLLA") != K.sequence_hash("MKVLLB")


def test_normalise_strips_stop_and_case():
    assert K.normalise(" mkv\nlla* ") == "MKVLLA"


# --------------------------------------------------------------------------
# Protein registry
# --------------------------------------------------------------------------

def test_one_row_per_unique_sequence(proteins):
    assert proteins.sequence_sha1.is_unique
    assert proteins.sequence.map(K.normalise).is_unique


def test_hash_matches_its_sequence(proteins):
    recomputed = proteins.sequence.map(K.sequence_hash)
    assert (recomputed == proteins.sequence_sha1).all()


def test_length_matches_sequence(proteins):
    assert (proteins.sequence.str.len() == proteins.sequence_length).all()


def test_every_protein_has_a_source(proteins):
    assert proteins.source_datasets.notna().all()
    assert (proteins.source_datasets.str.len() > 0).all()


def _name_set(row):
    names = {str(row.primary_name)}
    if isinstance(row.aliases, str) and row.aliases:
        names |= {part.strip() for part in row.aliases.split(";")}
    return names


def test_duplicate_names_resolved_to_one_sequence(proteins):
    """BbPETase and BurPL are one protein under two names in two papers.

    Matched on exact names, so that mutant series like BurPL_S121E - which
    are genuinely different sequences - do not count.
    """
    rows = [r for r in proteins.itertuples()
            if {"BbPETase", "BurPL"} & _name_set(r)]
    assert len(rows) == 1, "the two names must collapse onto a single sequence"
    assert {"BbPETase", "BurPL"} <= _name_set(rows[0])


def test_testing_status_is_a_known_value(proteins):
    allowed = {
        "standardised_screen_measured", "curated_database_measured",
        "literature_uncalibrated_measured", "no_identified_testing_evidence",
    }
    assert set(proteins.testing_status) <= allowed


# --------------------------------------------------------------------------
# Observation registry
# --------------------------------------------------------------------------

def test_observations_carry_an_evidence_class(observations):
    allowed = {K.EV_STANDARDISED, K.EV_CURATED, K.EV_LITERATURE_REL, K.EV_COMPUTATIONAL}
    assert set(observations.evidence_class) <= allowed
    assert observations.evidence_class.notna().all()


def test_computational_predictions_are_separated(observations):
    comp = observations[observations.evidence_class == K.EV_COMPUTATIONAL]
    assert len(comp) > 0, "the four Cui ddG sheets should be present and tagged"
    assert (comp.metric_type == "ddG_prediction").all()
    # and they must never be given an experimental label
    assert set(comp.observation_label) == {K.LAB_UNCERTAIN}


def test_petml_activity_is_never_given_units(observations):
    """The 33 workbooks record no units; inventing one would be fabrication."""
    lit = observations[observations.evidence_class == K.EV_LITERATURE_REL]
    assert len(lit) > 0
    assert lit.measurement_unit.isna().all()
    assert (lit.metric_type == "relative_activity_uncalibrated").all()


def test_standardised_observations_are_condition_resolved(observations):
    std = observations[observations.evidence_class == K.EV_STANDARDISED]
    enzyme_rows = std[std.row_role == "library_enzyme"]
    assert enzyme_rows.substrate.notna().all()
    assert enzyme_rows.temperature_c.notna().all()
    assert enzyme_rows.ph.notna().all()
    # more than one condition per enzyme: nothing has been collapsed
    per = enzyme_rows.groupby("sequence_sha1").size()
    assert per.min() >= 4


def test_blanks_and_controls_are_retained_and_flagged(observations):
    std = observations[observations.evidence_class == K.EV_STANDARDISED]
    assert (std.row_role == "blank").sum() == 220
    assert (std.row_role == "control").sum() > 0
    # blanks must all be at or below the reporting floor
    blanks = std[std.row_role == "blank"]
    assert (blanks.measurement_value == 0).all()


def test_detection_threshold_recorded_for_the_screen(observations):
    std = observations[observations.evidence_class == K.EV_STANDARDISED]
    assert (std.detection_threshold == K.SI_DETECTION_FLOOR_MM).all()
    # no reported non-zero value may sit below the stated floor
    nz = std[std.measurement_value > 0].measurement_value
    assert nz.min() >= K.SI_DETECTION_FLOOR_MM


def test_pazy_zero_is_not_called_a_protein_level_negative(observations):
    """A zero in PAZy is a condition-level failure of an active enzyme."""
    pazy = observations[observations.evidence_class == K.EV_CURATED]
    zeros = pazy[pazy.observation_label == K.LAB_BELOW]
    assert len(zeros) > 0
    assert zeros.label_basis.str.contains("NOT evidence that the protein is inactive").all()


# --------------------------------------------------------------------------
# Condition-specific labels
# --------------------------------------------------------------------------

def test_labels_are_for_one_named_condition(labels):
    assert labels.condition.nunique() == 1
    assert labels.condition.iloc[0] == f"{K.TARGET_SUBSTRATE}, {K.TARGET_TEMP_C} C, pH {K.TARGET_PH}"


def test_label_values_are_the_three_declared_classes(labels):
    assert set(labels.label) <= {K.LAB_DETECT, K.LAB_BELOW, K.LAB_UNCERTAIN}


def test_every_label_has_a_basis(labels):
    assert labels.label_basis.notna().all()
    assert (labels.label_basis.str.len() > 20).all()


def test_label_follows_the_replicate_rule(labels):
    detect = labels[labels.label == K.LAB_DETECT]
    below = labels[labels.label == K.LAB_BELOW]
    uncertain = labels[labels.label == K.LAB_UNCERTAIN]
    assert (detect.n_replicates_positive == detect.n_replicates).all()
    assert (below.n_replicates_positive == 0).all()
    assert ((uncertain.n_replicates_positive > 0)
            & (uncertain.n_replicates_positive < uncertain.n_replicates)).all()


def test_below_detection_label_is_condition_qualified(labels):
    below = labels[labels.label == K.LAB_BELOW]
    assert below.label_basis.str.contains("NOT evidence of universal inactivity").all()


def test_positive_labels_have_product_above_floor(labels):
    detect = labels[labels.label == K.LAB_DETECT]
    assert (detect.max_mM_product >= K.SI_DETECTION_FLOOR_MM).all()


def test_marginal_positives_are_flagged_not_dropped(labels):
    marginal = labels[labels.is_marginal_positive]
    assert len(marginal) > 0
    assert (marginal.label == K.LAB_DETECT).all()


def test_no_expression_failure_appears_as_a_label(labels):
    """Only assayed enzymes may carry a label at all."""
    assert (labels.expression_mgml.fillna(1.0) >= K.SI_EXPRESSION_FAIL_MGML).all()


# --------------------------------------------------------------------------
# Homology groups and leakage
# --------------------------------------------------------------------------

def test_every_protein_has_a_group(proteins, groups):
    assert len(groups) == len(proteins)
    assert set(groups.sequence_sha1) == set(proteins.sequence_sha1)
    assert groups.primary_group.notna().all()


def test_groups_are_nested_across_thresholds(groups):
    """A looser threshold can only merge groups, never split them."""
    merged = groups.groupby("group_90").group_70.nunique()
    assert (merged == 1).all()
    merged = groups.groupby("group_70").group_50.nunique()
    assert (merged == 1).all()


def test_grouping_rule_is_documented(groups):
    rule = groups.grouping_method.iloc[0]
    for token in ("BLOSUM62", "shorter", "coverage", "single-linkage"):
        assert token in rule


def test_no_group_spans_train_and_test(splits):
    both = splits[splits.split.isin(["train", "test"])]
    spanning = both.groupby("primary_group").split.nunique()
    assert (spanning == 1).all(), "a group on both sides of the split is leakage"


def test_uncertain_rows_are_excluded_from_training(splits):
    assert (splits[splits.label == K.LAB_UNCERTAIN].split == "excluded").all()
    assert (splits[splits.split == "excluded"].cv_fold == -1).all()


def test_both_classes_present_on_both_sides(splits):
    for side in ("train", "test"):
        got = set(splits[splits.split == side].label)
        assert {K.LAB_DETECT, K.LAB_BELOW} <= got, f"{side} is missing a class"


def test_cv_folds_respect_groups(splits):
    labelled = splits[splits.cv_fold >= 0]
    spanning = labelled.groupby("primary_group").cv_fold.nunique()
    assert (spanning == 1).all()


def test_split_diagnostics_show_no_near_duplicate_leak():
    import json
    with open(K.CURATION / "split_diagnostics.json") as fh:
        d = json.load(fh)
    assert d["groups_spanning_both_sides"] == 0
    assert d["n_cross_split_pairs_above_70pct"] == 0
    assert d["max_cross_split_identity"] < K.PRIMARY_THRESHOLD


# --------------------------------------------------------------------------
# Candidate eligibility - the rule that matters most
# --------------------------------------------------------------------------

def test_eligibility_covers_every_protein(proteins, eligibility):
    assert len(eligibility) == len(proteins)
    assert set(eligibility.status) <= {
        K.ST_TESTED, K.ST_FAILED_EXPR, K.ST_UNCERTAIN, K.ST_NO_EVIDENCE}


def test_expression_failures_are_never_eligible(eligibility):
    failed = eligibility[eligibility.status == K.ST_FAILED_EXPR]
    assert len(failed) > 0
    assert not failed.eligible_for_ranking.any()
    assert (failed.expression_mgml < K.SI_EXPRESSION_FAIL_MGML).all()


def test_expression_failures_are_not_called_inactive(eligibility, labels):
    """An expression failure must not appear anywhere as a PET-inactive label."""
    failed = set(eligibility[eligibility.status == K.ST_FAILED_EXPR].sequence_sha1)
    below = set(labels[labels.label == K.LAB_BELOW].sequence_sha1)
    assert failed & below == set()


def test_tested_proteins_are_not_offered_as_candidates(eligibility):
    tested = eligibility[eligibility.status == K.ST_TESTED]
    assert not tested.eligible_for_ranking.any()


def test_every_eligibility_row_explains_itself(eligibility):
    assert eligibility.reason.notna().all()
    assert (eligibility.reason.str.len() > 20).all()
