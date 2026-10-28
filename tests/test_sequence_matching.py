import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pet_explorer import config as C  # noqa: E402
from pet_explorer.preprocess import load_proteins  # noqa: E402
from pet_explorer.sequence_matching import SequenceInputError, SequenceMatcher, parse_query  # noqa: E402


@pytest.fixture(scope="module")
def proteins():
    return load_proteins()


@pytest.fixture(scope="module")
def matcher(proteins):
    return SequenceMatcher(proteins)


def test_clean_set_size(proteins):
    assert len(proteins) == 298
    assert proteins.protein_id.is_unique


@pytest.mark.parametrize("text,msg", [
    ("", "No sequence"),
    ("   \n  ", "No sequence"),
    (">a\nMKV\n>b\nMKV", "one sequence"),
    ("MKVLA\n>x\nMKV", "first line"),
    ("ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCATCG", "DNA"),
    ("MKVLAAGG1", "too short"),
    ("MKVLAXGGLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "Invalid characters"),
    ("MKVLA-GGLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL", "Invalid characters"),
    ("M" * (C.MAX_QUERY_LEN + 1), "too long"),
])
def test_invalid_input_rejected(text, msg):
    with pytest.raises(SequenceInputError, match=msg):
        parse_query(text)


def test_fasta_and_plain_equivalent(proteins):
    seq = proteins.sequence[0]
    fasta = ">my protein\n" + "\n".join(seq[i:i + 60] for i in range(0, len(seq), 60)) + "*"
    assert parse_query(fasta) == ("my protein", seq)
    assert parse_query(seq.lower())[1] == seq


def test_self_match_is_top_hit(matcher, proteins):
    for idx in [0, 50, 150, 297]:
        _, _, hits = matcher.search(proteins.sequence[idx], top_n=1, n_shuffles=5)
        assert hits[0].protein_id == proteins.protein_id[idx]
        assert hits[0].identity == pytest.approx(1.0)
        assert hits[0].normalised_score == pytest.approx(1.0)


def test_mutated_sequence_finds_parent(matcher, proteins):
    rng = random.Random(1)
    seq = list(proteins.sequence[0])
    for i in rng.sample(range(len(seq)), len(seq) // 10):   # 10% substitutions
        seq[i] = rng.choice([a for a in C.STANDARD_AA if a != seq[i]])
    _, _, hits = matcher.search("".join(seq), top_n=3)
    assert hits[0].protein_id == proteins.protein_id[0]
    assert 0.85 < hits[0].identity < 0.95
    assert hits[0].shuffled_z > 10


def test_shuffled_sequence_not_reliable(matcher, proteins):
    rng = random.Random(2)
    seq = list(proteins.sequence[0])
    rng.shuffle(seq)
    _, _, hits = matcher.search("".join(seq), top_n=1)
    assert hits[0].interpretation in (C.NO_MATCH_BAND, "Twilight zone - possible distant homolog")
    assert hits[0].identity < 0.40
