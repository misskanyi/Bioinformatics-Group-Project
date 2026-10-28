"""Paths and analysis constants shared by all modules."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"                       # original downloads - never modified
FEASIBILITY = ROOT / "outputs"             # outputs of analyze_pet_dataset.py
EXPLORER = ROOT / "outputs" / "explorer"   # outputs of this package

CLEAN = EXPLORER / "clean"
MATCHING = EXPLORER / "matching"
CLUSTERING = EXPLORER / "clustering"
NETWORK = EXPLORER / "network"
TEMPERATURE = EXPLORER / "temperature"
ORGANISMS = EXPLORER / "organisms"
FIGURES = EXPLORER / "figures"

F_ASSAYS = DATA / "pazy_polymer_assays.json.gz"
F_CSV = DATA / "pazy_proteins_sequences.csv"
F_PLASTICDB = DATA / "PlasticDB.fasta"
F_DEGRADERS = DATA / "degraders_list.tsv"
F_UNIPROT = DATA / "uniprotkb_accession_E9LVH8_OR_accession_2026_10_27.fasta.gz"

F_SUMMARY = FEASIBILITY / "pet_protein_activity_summary.csv"
F_ASSAY_RECORDS = FEASIBILITY / "tables" / "pet_assay_records.csv"

F_PROTEINS = CLEAN / "pet_active_proteins.csv"
F_FASTA = CLEAN / "pet_active_proteins.fasta"
F_PAIRS = CLUSTERING / "pairwise_alignment.csv"

STANDARD_AA = "ACDEFGHIKLMNPQRSTVWY"

# Local alignment scoring (NCBI BLASTP defaults for BLOSUM62).
GAP_OPEN, GAP_EXTEND = -11, -1

# Query input limits.
MIN_QUERY_LEN, MAX_QUERY_LEN = 30, 5000

# Similarity-network edge rule (see network.py for justification).
EDGE_MIN_IDENTITY = 0.40
EDGE_MIN_COVERAGE = 0.70

# Interpretation bands for a query match (identity over aligned columns,
# coverage of the shorter sequence). 25-40% identity is the "twilight zone"
# where homology cannot be inferred from identity alone (Rost 1999).
MATCH_BANDS = [
    (0.90, 0.80, "Near-identical to a characterised PET-active enzyme"),
    (0.40, 0.70, "Clear homolog of a characterised PET-active enzyme"),
    (0.25, 0.50, "Twilight zone - possible distant homolog"),
]
NO_MATCH_BAND = "No reliable similarity"


def ensure_dirs():
    for d in (CLEAN, MATCHING, CLUSTERING, NETWORK, TEMPERATURE, ORGANISMS, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
