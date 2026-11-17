"""Green / yellow / red / insufficient evidence rules (pet_explorer.evidence)."""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet_explorer import config as C  # noqa: E402
from pet_explorer import evidence as E  # noqa: E402
from pet_explorer.preprocess import load_proteins  # noqa: E402
from pet_explorer.sequence_matching import Hit, SequenceMatcher, interpret  # noqa: E402

REF_HIGH = {"n_positive_assays": 5, "n_pet_assays": 6, "n_publications": 2, "pet_label": "PET-active",
            "label_confidence": "high"}
REF_MEDIUM = {**REF_HIGH, "label_confidence": "medium"}
WITH_MOTIF = "MKT" + "GHSMG" + "A" * 60          # one G-x-S-x-G
NO_MOTIF = "MKT" + "AHSMA" + "A" * 60


def hit(identity, qcov, tcov, z, name="RefX"):
    return Hit(protein_id=1, protein_name=name, raw_score=100.0, normalised_score=0.5, identity=identity,
               query_coverage=qcov, target_coverage=tcov, aligned_columns=200, query_range=(1, 2),
               target_range=(1, 2), shuffled_z=z, interpretation=interpret(identity, min(qcov, tcov)),
               alignment_text="")


@pytest.mark.parametrize("h,ref,seq,cat,rule", [
    (hit(1.0, 1.0, 1.0, 200), REF_HIGH, WITH_MOTIF, "green", "K"),
    (hit(0.80, 0.95, 0.95, 100), REF_HIGH, WITH_MOTIF, "green", "H1"),
    (hit(0.80, 0.95, 0.95, 100), REF_HIGH, NO_MOTIF, "yellow", "H2"),        # motif can only lower
    (hit(0.80, 0.95, 0.95, 100), REF_MEDIUM, WITH_MOTIF, "yellow", "H2"),    # weak reference evidence
    (hit(0.80, 0.95, 0.95, 12), REF_HIGH, WITH_MOTIF, "insufficient", "H3"),  # identity without significance
    (hit(0.30, 0.80, 0.80, 40), REF_HIGH, WITH_MOTIF, "yellow", "T1"),
    (hit(0.97, 1.0, 0.60, 80), REF_HIGH, WITH_MOTIF, "yellow", "P"),        # partial coverage, high identity
    (hit(0.30, 0.80, 0.80, 12), REF_HIGH, WITH_MOTIF, "insufficient", "T2"),
    (hit(0.30, 0.80, 0.80, 5), REF_HIGH, WITH_MOTIF, "red", "T3"),
    (hit(0.95, 0.95, 0.20, 60), REF_HIGH, WITH_MOTIF, "insufficient", "F"),  # fragment, high identity
    (hit(0.50, 0.30, 0.90, 60), REF_HIGH, WITH_MOTIF, "yellow", "D1"),       # domain in a longer protein
    (hit(0.22, 0.85, 0.85, 30), REF_HIGH, WITH_MOTIF, "yellow", "D2"),
    (hit(0.40, 0.20, 0.20, 30), REF_HIGH, WITH_MOTIF, "insufficient", "L"),
    (hit(0.20, 0.30, 0.30, 12), REF_HIGH, WITH_MOTIF, "insufficient", "N1"),
    (hit(0.20, 0.30, 0.30, 4), REF_HIGH, WITH_MOTIF, "red", "N2"),
])
def test_rules(h, ref, seq, cat, rule):
    a = E.assess(h, ref, seq)
    assert (a["category"], a["rule"]) == (cat, rule)
    assert a["label"] == E.LABELS[cat]
    assert a["known_reference"] is (rule == "K")
    assert a["summary"] and a["limitations"] and a["next_steps"]


def test_identity_alone_never_green():
    # 100% identity over a short stretch of both sequences is not a homolog
    assert E.assess(hit(1.0, 0.2, 0.2, 30), REF_HIGH, WITH_MOTIF)["category"] != "green"


def test_motif_never_raises():
    for h in (hit(0.30, 0.80, 0.80, 5), hit(0.20, 0.30, 0.30, 4)):
        assert E.assess(h, REF_HIGH, NO_MOTIF)["category"] == E.assess(h, REF_HIGH, WITH_MOTIF)["category"] == "red"


def test_red_never_claims_inactivity():
    a = E.assess(hit(0.20, 0.30, 0.30, 4), REF_HIGH, WITH_MOTIF)
    text = " ".join([a["summary"], *a["next_steps"]]).lower()
    assert "does not show the protein is pet-inactive" in text
    assert "proven inactive" not in text


def test_missing_hit_is_insufficient():
    assert E.assess(None, None, WITH_MOTIF)["category"] == "insufficient"


def test_tandem_repeat_flagged():
    assert E.tandem_repeat("MALVQKDTNE" * 17) == 10
    assert E.tandem_repeat("MNFPRASRLMQAAVLGGLMAVSAAATAQTNPYARGPNPTAASLEASAGPFTVRSFTVSRPSGY") is None


def test_thresholds_match_calibration():
    s = E.calibration_summary()
    if s is None:
        pytest.skip("run `python -m pet_explorer.evidence` to generate the calibration")
    null, loo = s["shuffled_null"], s["leave_one_out"]
    assert null["z_quantiles"]["0.99"] <= E.Z_CHANCE < E.Z_STRONG
    assert null["z_max"] < E.Z_STRONG <= loo["twilight_band_z_min"]
    # no shuffled sequence was ever coloured green or yellow
    assert null["categories"].get("green", 0) == null["categories"].get("yellow", 0) == 0


# ------------------------------------------------------------------ with the real matcher

@pytest.fixture(scope="module")
def setup():
    p = load_proteins()
    return p, SequenceMatcher(p), p.set_index("protein_id")


def _assess(setup, seq):
    _, m, card = setup
    _, q, hits = m.search(seq, top_n=1, n_shuffles=E.N_SHUFFLES, seed=E.SHUFFLE_SEED)
    return E.assess(hits[0], card.loc[hits[0].protein_id].to_dict(), q)


def test_reference_is_known_green(setup):
    p = setup[0]
    a = _assess(setup, p.sequence[p.protein_name == "LCC"].iloc[0])
    assert (a["category"], a["rule"], a["known_reference"]) == ("green", "K", True)


def test_mutated_reference_is_green_but_not_known(setup):
    p = setup[0]
    rng = random.Random(3)
    seq = list(p.sequence[p.protein_name == "LCC"].iloc[0])
    for i in rng.sample(range(len(seq)), len(seq) // 10):
        seq[i] = rng.choice([a for a in C.STANDARD_AA if a != seq[i]])
    a = _assess(setup, "".join(seq))
    assert a["known_reference"] is False
    assert a["category"] in ("green", "yellow")


def test_shuffled_reference_not_supported(setup):
    p = setup[0]
    rng = random.Random(7)
    seq = list(p.sequence[0])
    rng.shuffle(seq)
    assert _assess(setup, "".join(seq))["category"] in ("red", "insufficient")
