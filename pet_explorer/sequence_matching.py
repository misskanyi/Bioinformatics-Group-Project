"""Feature 1 - match a query protein against the PET-active reference set.

Method
------
* Smith-Waterman local alignment (Biopython PairwiseAligner), BLOSUM62,
  gap open -11 / extend -1 (BLASTP defaults).
* Ranking uses a *length-normalised* score, not the raw score:
      normalised_score = raw / sqrt(self_score(query) * self_score(target))
  (a symmetric BLAST-score-ratio). 1.0 = identical sequences.
* Reported per hit: identity over aligned columns, query coverage, target
  coverage, raw score, normalised score, and a z-score of the raw score versus
  25 shuffled copies of the query (same composition, no order) as an empirical
  check that the similarity is not due to composition alone.

Sequence similarity is NOT experimental evidence. A close match to a
characterised PET-active enzyme makes a query a promising candidate only.
"""

import random
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from Bio.Align import PairwiseAligner, substitution_matrices

from . import config as C

_NUCLEOTIDE = re.compile(r"^[ACGTUN]+$")


class SequenceInputError(ValueError):
    """Raised for user input that is not a single valid protein sequence."""


def make_aligner(mode="local"):
    a = PairwiseAligner()
    a.mode = mode
    a.substitution_matrix = substitution_matrices.load("BLOSUM62")
    a.open_gap_score, a.extend_gap_score = C.GAP_OPEN, C.GAP_EXTEND
    return a


def parse_query(text):
    """Parse plain or FASTA text into (header, sequence). Raises SequenceInputError."""
    if text is None or not text.strip():
        raise SequenceInputError("No sequence entered.")
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    header = "query"
    if lines[0].startswith(">"):
        if sum(ln.startswith(">") for ln in lines) > 1:
            raise SequenceInputError("Please enter one sequence only (found several FASTA headers).")
        header = lines[0][1:].strip() or "query"
        lines = lines[1:]
    elif any(ln.startswith(">") for ln in lines):
        raise SequenceInputError("A FASTA header ('>') must be on the first line.")
    # tolerate spaces, line numbers (GenBank style) and a terminal stop '*'
    seq = re.sub(r"[\s\d]", "", "".join(lines)).upper()
    if seq.endswith("*"):
        seq = seq[:-1]
    if not seq:
        raise SequenceInputError("The FASTA record contains no sequence.")
    if _NUCLEOTIDE.match(seq) and len(seq) >= 30:
        raise SequenceInputError("This looks like a DNA/RNA sequence. Please enter an amino-acid (protein) sequence.")
    bad = sorted(set(seq) - set(C.STANDARD_AA))
    if bad:
        raise SequenceInputError(
            "Invalid characters: " + ", ".join(repr(b) for b in bad)
            + ". Only the 20 standard amino-acid letters are accepted (ambiguity codes B, Z, J, X, U, O are not).")
    if len(seq) < C.MIN_QUERY_LEN:
        raise SequenceInputError(f"Sequence too short ({len(seq)} aa). Minimum is {C.MIN_QUERY_LEN} aa.")
    if len(seq) > C.MAX_QUERY_LEN:
        raise SequenceInputError(f"Sequence too long ({len(seq)} aa). Maximum is {C.MAX_QUERY_LEN} aa.")
    return header, seq


def interpret(identity, min_coverage):
    for min_id, min_cov, label in C.MATCH_BANDS:
        if identity >= min_id and min_coverage >= min_cov:
            return label
    return C.NO_MATCH_BAND


@dataclass
class Hit:
    protein_id: int
    protein_name: str
    raw_score: float
    normalised_score: float
    identity: float
    query_coverage: float
    target_coverage: float
    aligned_columns: int
    query_range: tuple
    target_range: tuple
    shuffled_z: float
    interpretation: str
    alignment_text: str
    aligned_target: str = ""   # gapped rows of the same alignment, for viewers
    aligned_query: str = ""


class SequenceMatcher:
    """Holds the reference set and its self-scores; reuse across queries."""

    def __init__(self, proteins: pd.DataFrame):
        self.ref = proteins.reset_index(drop=True)
        self.aligner = make_aligner("local")
        self.self_scores = np.array([self.aligner.score(s, s) for s in self.ref.sequence])

    def _detail(self, query, idx, n_shuffles, seed):
        target = self.ref.sequence[idx]
        # Biopython convention: first argument is displayed as "target", second as "query"
        aln = self.aligner.align(target, query)[0]
        counts = aln.counts()
        cols = aln.length
        t0, t1 = int(aln.coordinates[0][0]), int(aln.coordinates[0][-1])
        q0, q1 = int(aln.coordinates[1][0]), int(aln.coordinates[1][-1])
        qcov, tcov = (q1 - q0) / len(query), (t1 - t0) / len(target)
        ident = counts.identities / cols if cols else 0.0
        rng = random.Random(seed)
        shuffled = []
        for _ in range(n_shuffles):
            s = list(query)
            rng.shuffle(s)
            shuffled.append(self.aligner.score("".join(s), target))
        sd = float(np.std(shuffled)) or 1.0
        z = (aln.score - float(np.mean(shuffled))) / sd
        norm = aln.score / np.sqrt(self.aligner.score(query, query) * self.self_scores[idx])
        return Hit(
            protein_id=int(self.ref.protein_id[idx]),
            protein_name=self.ref.protein_name[idx],
            raw_score=float(aln.score),
            normalised_score=float(norm),
            identity=float(ident),
            query_coverage=float(qcov),
            target_coverage=float(tcov),
            aligned_columns=int(cols),
            query_range=(q0 + 1, q1),
            target_range=(t0 + 1, t1),
            shuffled_z=float(z),
            interpretation=interpret(ident, min(qcov, tcov)),
            alignment_text=format(aln),
            aligned_target=aln[0],
            aligned_query=aln[1],
        )

    def search(self, query_text, top_n=5, n_shuffles=25, seed=0, exclude_ids=()):
        """Return (header, sequence, list[Hit]) for the top_n matches."""
        header, query = parse_query(query_text)
        q_self = self.aligner.score(query, query)
        raw = np.array([self.aligner.score(query, s) for s in self.ref.sequence])
        norm = raw / np.sqrt(q_self * self.self_scores)
        order = [i for i in np.argsort(-norm) if int(self.ref.protein_id[i]) not in set(exclude_ids)]
        hits = [self._detail(query, i, n_shuffles, seed) for i in order[:top_n]]
        return header, query, hits


def hits_to_frame(hits, proteins):
    rows = []
    info = proteins.set_index("protein_id")
    for rank, h in enumerate(hits, 1):
        p = info.loc[h.protein_id]
        rows.append({
            "rank": rank,
            "protein_id": h.protein_id,
            "protein_name": h.protein_name,
            "identity_pct": round(100 * h.identity, 1),
            "query_coverage_pct": round(100 * h.query_coverage, 1),
            "target_coverage_pct": round(100 * h.target_coverage, 1),
            "normalised_score": round(h.normalised_score, 3),
            "raw_score": round(h.raw_score, 1),
            "shuffled_z": round(h.shuffled_z, 1),
            "interpretation": h.interpretation,
            "pet_evidence": f"{p.pet_label} ({p.label_confidence} confidence); "
                            f"{p.n_positive_assays} positive / {p.n_pet_assays} PET assays; "
                            f"{p.n_publications} publication(s)",
        })
    return pd.DataFrame(rows)
