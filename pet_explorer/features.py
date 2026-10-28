"""Sequence features: amino-acid composition, length, physicochemical
properties (Biopython ProtParam) and motif search.

The motif searched is the G-x-S-x-G pentapeptide that surrounds the catalytic
serine in many alpha/beta-hydrolases (lipases, esterases, cutinases). It is a
hypothesis-driven check: we report where it is and is not found; we do not
assume every protein has it.
"""

import re
from collections import Counter

import pandas as pd
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from . import config as C

GXSXG = re.compile(r"(?=(G.S.G))")


def composition(proteins):
    rows = []
    for pid, seq in zip(proteins.protein_id, proteins.sequence):
        n = len(seq)
        c = Counter(seq)
        rows.append({"protein_id": pid, **{f"aa_{a}": 100 * c.get(a, 0) / n for a in C.STANDARD_AA}})
    return pd.DataFrame(rows)


def physicochemical(proteins):
    rows = []
    for pid, seq in zip(proteins.protein_id, proteins.sequence):
        pa = ProteinAnalysis(seq)
        helix, turn, sheet = pa.secondary_structure_fraction()
        rows.append({
            "protein_id": pid,
            "length": len(seq),
            "molecular_weight_kda": pa.molecular_weight() / 1000,
            "isoelectric_point": pa.isoelectric_point(),
            "gravy": pa.gravy(),
            "aromaticity": pa.aromaticity(),
            "instability_index": pa.instability_index(),
            "helix_prone_fraction": helix,
            "turn_prone_fraction": turn,
            "sheet_prone_fraction": sheet,
        })
    return pd.DataFrame(rows)


def motifs(proteins):
    rows = []
    for pid, seq in zip(proteins.protein_id, proteins.sequence):
        hits = [(m.start() + 1, m.group(1)) for m in GXSXG.finditer(seq)]
        rows.append({
            "protein_id": pid,
            "gxsxg_count": len(hits),
            "gxsxg_variants": "; ".join(sorted({h[1] for h in hits})),
            "gxsxg_positions": "; ".join(str(h[0]) for h in hits),
            "gxsxg_relative_position": "; ".join(f"{h[0] / len(seq):.2f}" for h in hits),
        })
    return pd.DataFrame(rows)


def feature_table(proteins):
    """One row per protein with all numeric features + motif summary."""
    f = proteins[["protein_id"]].merge(physicochemical(proteins), on="protein_id")
    f = f.merge(composition(proteins), on="protein_id")
    return f.merge(motifs(proteins), on="protein_id")


ML_FEATURES = ([f"aa_{a}" for a in C.STANDARD_AA]
               + ["length", "isoelectric_point", "gravy", "aromaticity", "instability_index",
                  "helix_prone_fraction", "turn_prone_fraction", "sheet_prone_fraction"])


def cluster_kmers(proteins, labels, k=5, min_size=5, min_in=0.8, max_out=0.2):
    """k-mers present in >= min_in of a cluster's members and <= max_out of all other proteins."""
    sets = {pid: {s[i:i + k] for i in range(len(s) - k + 1)} for pid, s in zip(proteins.protein_id, proteins.sequence)}
    lab = dict(zip(proteins.protein_id, labels))
    rows = []
    for c in sorted(set(labels)):
        members = [p for p in sets if lab[p] == c]
        others = [p for p in sets if lab[p] != c]
        if len(members) < min_size:
            continue
        cin = Counter(km for p in members for km in sets[p])
        cout = Counter(km for p in others for km in sets[p])
        for km, n in cin.items():
            fin, fout = n / len(members), cout.get(km, 0) / max(len(others), 1)
            if fin >= min_in and fout <= max_out:
                rows.append({"cluster": c, "kmer": km, "fraction_in_cluster": round(fin, 3),
                             "fraction_outside": round(fout, 3)})
    return pd.DataFrame(rows, columns=["cluster", "kmer", "fraction_in_cluster", "fraction_outside"])
