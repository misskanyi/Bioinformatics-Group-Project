"""Thin wrapper around pet_explorer.sequence_matching (the validated matcher)."""

from functools import lru_cache

from pet_explorer import config as C
from pet_explorer.sequence_matching import SequenceMatcher, parse_query

from . import store


@lru_cache
def matcher() -> SequenceMatcher:
    return SequenceMatcher(store.proteins())


def method() -> dict:
    return {
        "algorithm": "Smith-Waterman local alignment (Biopython PairwiseAligner)",
        "matrix": "BLOSUM62",
        "gap_open": C.GAP_OPEN,
        "gap_extend": C.GAP_EXTEND,
        "ranking": "Length-normalised score: raw / sqrt(self(query) x self(reference)); 1.0 = identical",
        "identity_definition": "Identical residues / aligned columns (gaps included)",
        "coverage_definition": "Aligned span / full length of that sequence",
        "shuffle_control": "z-score of raw score vs 25 composition-preserving shuffles of the query",
        "reference_set_size": len(store.proteins()),
        "bands": [{"min_identity": i, "min_coverage": c, "label": l} for i, c, l in C.MATCH_BANDS],
        "no_match_label": C.NO_MATCH_BAND,
        "min_length": C.MIN_QUERY_LEN,
        "max_length": C.MAX_QUERY_LEN,
    }


def search(text: str, top_n: int = 5) -> dict:
    header, query, hits = matcher().search(text, top_n=top_n)
    out = []
    for rank, h in enumerate(hits, 1):
        out.append({
            "rank": rank,
            "protein_id": h.protein_id,
            "protein_name": h.protein_name,
            "identity": h.identity,
            "query_coverage": h.query_coverage,
            "target_coverage": h.target_coverage,
            "aligned_columns": h.aligned_columns,
            "raw_score": h.raw_score,
            "normalised_score": h.normalised_score,
            "shuffled_z": h.shuffled_z,
            "query_range": list(h.query_range),
            "target_range": list(h.target_range),
            "interpretation": h.interpretation,
            "aligned_query": h.aligned_query,
            "aligned_target": h.aligned_target,
            "reference": store.protein_card(h.protein_id),
        })
    return {"header": header, "sequence": query, "length": len(query), "hits": out, "method": method()}


def validate(text: str) -> tuple:
    return parse_query(text)
