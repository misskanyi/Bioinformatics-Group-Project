"""All-vs-all local alignment of the PET-active set (cached).

For every pair we store:
  identity          identical positions / aligned columns (BLAST-style)
  coverage_a/_b     fraction of each sequence inside the aligned region
  identity_shorter  identical positions / length of the shorter sequence
                    (coverage-aware; used as the clustering similarity)
  normalised_score  raw / sqrt(self_a * self_b)
"""

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import config as C
from .sequence_matching import make_aligner

_ALIGNER = None


def _row(args):
    global _ALIGNER
    if _ALIGNER is None:
        _ALIGNER = make_aligner("local")
    i, seqs, selfs = args
    out = []
    for j in range(i + 1, len(seqs)):
        a, b = seqs[i], seqs[j]
        aln = _ALIGNER.align(a, b)[0]
        ident = aln.counts().identities
        ca = (aln.coordinates[0][-1] - aln.coordinates[0][0]) / len(a)
        cb = (aln.coordinates[1][-1] - aln.coordinates[1][0]) / len(b)
        out.append((i, j, ident / aln.length, ca, cb, ident / min(len(a), len(b)),
                    aln.score, aln.score / np.sqrt(selfs[i] * selfs[j])))
    return out


def compute_pairs(proteins, reuse=True):
    if reuse and C.F_PAIRS.exists():
        pairs = pd.read_csv(C.F_PAIRS)
        if set(pairs.protein_id_a) | set(pairs.protein_id_b) == set(proteins.protein_id):
            return pairs
    seqs = proteins.sequence.tolist()
    al = make_aligner("local")
    selfs = [al.score(s, s) for s in seqs]
    with ProcessPoolExecutor() as ex:
        rows = [r for chunk in ex.map(_row, [(i, seqs, selfs) for i in range(len(seqs))], chunksize=4)
                for r in chunk]
    pairs = pd.DataFrame(rows, columns=["i", "j", "identity", "coverage_a", "coverage_b",
                                        "identity_shorter", "raw_score", "normalised_score"])
    ids = proteins.protein_id.to_numpy()
    pairs.insert(0, "protein_id_a", ids[pairs.i])
    pairs.insert(1, "protein_id_b", ids[pairs.j])
    pairs = pairs.drop(columns=["i", "j"])
    pairs["min_coverage"] = pairs[["coverage_a", "coverage_b"]].min(axis=1)
    pairs = pairs.round(4)
    pairs.to_csv(C.F_PAIRS, index=False)
    return pairs


def square_matrix(pairs, ids, column="identity_shorter", diagonal=1.0):
    """Symmetric matrix indexed in the order of `ids`."""
    pos = {p: k for k, p in enumerate(ids)}
    m = np.full((len(ids), len(ids)), np.nan)
    a = pairs.protein_id_a.map(pos).to_numpy()
    b = pairs.protein_id_b.map(pos).to_numpy()
    m[a, b] = m[b, a] = pairs[column].to_numpy()
    np.fill_diagonal(m, diagonal)
    return m
