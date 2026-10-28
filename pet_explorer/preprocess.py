"""Stage 1 - build the cleaned PET-active protein set.

Reuses the protein-level labels produced by analyze_pet_dataset.py (feasibility
analysis) and re-checks every selected sequence against the original PAZy CSV
so the cleaned set is traceable to the raw download.
"""

import re

import pandas as pd

from . import config as C

KEEP = [
    "protein_id", "protein_name", "pet_label", "label_confidence",
    "n_pet_assays", "n_positive_assays", "n_negative_assays", "n_publications",
    "temperature_range_c", "ph_range", "substrate_forms", "enzyme_preparations",
    "detection_methods", "in_standardised_screen", "dois",
    "plasticdb_ids", "plasticdb_enzyme_name", "genbank", "uniprot_match",
    "sequence_length", "sequence",
]


def load_feasibility_summary():
    if not C.F_SUMMARY.exists():
        raise FileNotFoundError(
            f"{C.F_SUMMARY} not found - run `python analyze_pet_dataset.py` first.")
    return pd.read_csv(C.F_SUMMARY)


def build_clean_set():
    """Return the 298 usable PET-active proteins and a list of QC checks."""
    summary = load_feasibility_summary()
    raw = pd.read_csv(C.F_CSV)
    raw_seq = dict(zip(raw.protein_id, raw.amino_acid_sequence))

    active = summary[(summary.usable_for_binary_ml) & (summary.binary_class == "active")].copy()
    active = active[KEEP].sort_values("protein_id").reset_index(drop=True)
    active["sequence_length"] = active.sequence_length.astype(int)

    valid = re.compile(f"^[{C.STANDARD_AA}]+$")
    checks = [
        ("Proteins selected (usable PET-active)", len(active), len(active) == 298),
        ("Sequences identical to raw PAZy CSV",
         int(sum(raw_seq.get(i) == s for i, s in zip(active.protein_id, active.sequence))),
         all(raw_seq.get(i) == s for i, s in zip(active.protein_id, active.sequence))),
        ("Sequences with only standard amino acids",
         int(active.sequence.str.match(valid).sum()), bool(active.sequence.str.match(valid).all())),
        ("Unique protein IDs", active.protein_id.nunique(), active.protein_id.is_unique),
        ("Unique sequences", active.sequence.nunique(), active.sequence.is_unique),
        ("Recorded length equals sequence length",
         int((active.sequence.str.len() == active.sequence_length).sum()),
         bool((active.sequence.str.len() == active.sequence_length).all())),
    ]
    qc = pd.DataFrame(checks, columns=["check", "value", "passed"])
    return active, qc


def write_fasta(df, path):
    with open(path, "w") as fh:
        for pid, name, seq in zip(df.protein_id, df.protein_name, df.sequence):
            fh.write(f">{pid} {name}\n")
            for i in range(0, len(seq), 60):
                fh.write(seq[i:i + 60] + "\n")


def run():
    C.ensure_dirs()
    active, qc = build_clean_set()
    if not qc.passed.all():
        raise RuntimeError("QC failed:\n" + qc.to_string(index=False))
    active.to_csv(C.F_PROTEINS, index=False)
    write_fasta(active, C.F_FASTA)
    qc.to_csv(C.CLEAN / "qc_checks.csv", index=False)
    return active, qc


def load_proteins():
    if not C.F_PROTEINS.exists():
        run()
    return pd.read_csv(C.F_PROTEINS)
