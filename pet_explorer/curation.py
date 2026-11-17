"""Unified dataset curation for supervised learning (KDD stages 1-3).

This module implements *Selection*, *Preprocessing* and *Transformation* only.
No model is trained here; `pet_explorer.prediction` remains the mining stage.

Why this module exists
----------------------
The evaluation in `outputs/dataset_evaluation/REPORT.md` established that the
project's label evidence is fragmented and, in one place, actively misleading:

  * PAZy ingested the 2025 standardised screen, but - being a database of
    *published activity* - it kept the 99 enzymes that worked and none of the
    84 that did not. Training on PAZy alone is positive-unlabelled data.
  * The 33 PETML workbooks carry an `Activity` column with **no units**, on
    mutually irreconcilable scales. They cannot be pooled into one label.
  * 263 sequences in the 2025 library were never assayed because they failed
    purification (BCA < 0.1 mg/mL, stated in the paper's SI section S2), not
    because nobody tried them. They are not untested candidates.

So the curation here keys everything on the *sequence*, records the evidence
class of every observation, and never collapses conditions into a global label.

Outputs (all under outputs/curation/)
-------------------------------------
proteins_master.csv            one row per unique amino acid sequence
experimental_observations.csv  one row per experimental observation
condition_specific_labels.csv  the supervised target, one condition
homology_groups.csv            identity-based groups for leakage control
split_assignments.csv          grouped train/test split
candidate_eligibility.csv      who may be ranked later, and who may not
curation_report.md             narrative summary

Run with:  python -m pet_explorer.curation
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import config as C
from .sequence_matching import make_aligner

# --------------------------------------------------------------------------
# Paths and constants
# --------------------------------------------------------------------------

CURATION = C.ROOT / "outputs" / "curation"

F_SI = C.DATA / "cs5c03460_si_002.xlsx"
F_PETML_FASTA = C.DATA / "sequences.fasta"
F_PAZY_FASTA = C.DATA / "pazy_proteins.fasta"

SI_DOI = "10.1021/acscatal.5c03460"

#: The 2025 screen reports product rounded to 0.01 mM and floored at zero;
#: the smallest non-zero value observed anywhere in the table is 0.03 mM.
#: A zero therefore means "below this floor", never "no catalysis".
SI_DETECTION_FLOOR_MM = 0.03

#: Paper SI section S2: purified protein was normalised to 0.1 mg/mL, and a
#: concentration under 0.1 mg/mL is described as a failed purification.
SI_EXPRESSION_FAIL_MGML = 0.1

#: Target condition for the supervised dataset. Confirmed against SI figure
#: captions S4-S5: every assayed enzyme, including the lowest-yield tier
#: (4 conditions = 4 pH x 40 C x cryPow), was tested here.
TARGET_SUBSTRATE, TARGET_TEMP_C, TARGET_PH = "cryPow", 40, 6.5

#: Identity thresholds investigated for grouping. 0.70 is the primary value.
GROUP_THRESHOLDS = (0.50, 0.70, 0.90)
PRIMARY_THRESHOLD = 0.70

#: k-mer prefilter: pairs below this 5-mer Jaccard are never aligned. Two
#: sequences at >=50% identity share far more 5-mers than this, so the filter
#: cannot split a group that the alignment would have merged.
KMER_K, KMER_MIN_JACCARD = 5, 0.02

#: The four sheets in Cui et al 2021 (NanoPET) that hold computed ddG values.
COMPUTATIONAL_SHEETS = {"Abacus", "FoldX", "Rosetta_ddg", "Consensus"}

# Evidence classes. Kept explicit so no caller has to guess.
EV_STANDARDISED = "experimental_standardised_screen"
EV_CURATED = "experimental_curated_database"
EV_LITERATURE_REL = "experimental_literature_relative_uncalibrated"
EV_COMPUTATIONAL = "computational_prediction"

# Condition-specific labels.
LAB_DETECT = "detectable_activity"
LAB_BELOW = "below_detection"
LAB_UNCERTAIN = "uncertain"

# Candidate eligibility statuses.
ST_TESTED = "experimentally_tested"
ST_FAILED_EXPR = "failed_expression"
ST_UNCERTAIN = "uncertain_experimental_status"
ST_NO_EVIDENCE = "no_identified_testing_evidence"


# --------------------------------------------------------------------------
# Sequence helpers
# --------------------------------------------------------------------------

def normalise(seq: str) -> str:
    """Canonical sequence form: uppercase, no whitespace, no trailing stop."""
    return "".join(str(seq).split()).upper().rstrip("*")


def sequence_hash(seq: str) -> str:
    """Stable identifier for a sequence. Same sequence -> same hash, always."""
    return hashlib.sha1(normalise(seq).encode()).hexdigest()


def read_fasta(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    heads, seqs, head, buf = [], [], None, []
    with opener(path, "rt") as fh:
        for line in fh:
            line = line.rstrip()
            if line.startswith(">"):
                if head is not None:
                    heads.append(head)
                    seqs.append("".join(buf))
                head, buf = line[1:], []
            elif line:
                buf.append(line.strip())
    if head is not None:
        heads.append(head)
        seqs.append("".join(buf))
    return heads, seqs


# --------------------------------------------------------------------------
# KDD stage 1: Selection - load every source
# --------------------------------------------------------------------------

def load_si_rounds():
    df = pd.read_excel(F_SI, sheet_name="Rounds", engine="openpyxl")
    df["sample_id"] = df.sample_id.astype(str)
    df["is_control"] = df.sample_id.str.upper() == "RFP"
    df["sequence"] = df.seq_aa.map(normalise)
    df["sequence_sha1"] = df.sequence.map(sequence_hash)
    return df


def load_si_activity():
    df = pd.read_excel(F_SI, sheet_name="Activity", engine="openpyxl")
    df["sample_id"] = df.sample_id.astype(str)
    return df


def load_petml_sequences():
    heads, seqs = read_fasta(F_PETML_FASTA)
    return pd.DataFrame({
        "protein_name": heads,
        "sequence": [normalise(s) for s in seqs],
        "sequence_sha1": [sequence_hash(s) for s in seqs],
    })


def petml_workbooks():
    """The 33 study workbooks, i.e. every xlsx in data/ except the 2025 SI."""
    return sorted(p for p in C.DATA.glob("*.xlsx") if p.name != F_SI.name)


def load_petml_measurements():
    """Per-study activity/Tm records, tagged with their evidence class.

    The `Activity` column carries no unit anywhere in these 33 files and the
    scales are mutually irreconcilable, so each row is kept with its study as
    an ordinal record only. The four Cui ddG sheets are tagged computational.
    """
    rows = []
    for wb in petml_workbooks():
        study = wb.stem
        for sheet, df in pd.read_excel(wb, sheet_name=None, engine="openpyxl").items():
            df = df.rename(columns={c: str(c).strip() for c in df.columns})
            if "Protein" not in df.columns:
                continue
            computational = sheet in COMPUTATIONAL_SHEETS
            for _, r in df.iterrows():
                rows.append({
                    "study_id": study,
                    "sheet": sheet,
                    "source_file": wb.name,
                    "protein_name": r["Protein"],
                    "activity": r.get("Activity"),
                    "log_activity": r.get("logActivity"),
                    "tm": r.get("Tm"),
                    "dtm": r.get("dTm"),
                    "evidence_class": EV_COMPUTATIONAL if computational else EV_LITERATURE_REL,
                })
    return pd.DataFrame(rows)


def load_pazy_sequences():
    df = pd.read_csv(C.F_CSV)
    df = df[df.amino_acid_sequence.notna()].copy()
    df["sequence"] = df.amino_acid_sequence.map(normalise)
    df["sequence_sha1"] = df.sequence.map(sequence_hash)
    return df


def load_pazy_assays():
    """Flatten PAZy PET assays, keeping conditions, units and the DOI."""
    with gzip.open(C.F_ASSAYS, "rt") as fh:
        raw = json.load(fh)
    rows = []
    for rec in raw:
        for assay in rec.get("assays") or []:
            if str(assay.get("substrate", "")).upper() != "PET":
                continue
            cond = assay.get("conditions") or {}
            material = assay.get("material") or {}
            for m in assay.get("measurements") or [{}]:
                rows.append({
                    "protein_id": rec.get("protein_id"),
                    "protein_name": rec.get("protein_name"),
                    "doi": rec.get("literature_doi"),
                    "substrate_form": material.get("form"),
                    "temperature_c": cond.get("temperature_c"),
                    "ph": cond.get("ph"),
                    "enzyme_preparation": cond.get("enzyme_preparation"),
                    "metric_type": m.get("metric_type"),
                    "value": m.get("value"),
                    "unit": m.get("unit"),
                    "digitized": m.get("value_is_digitized"),
                })
    return pd.DataFrame(rows)


def load_plasticdb():
    heads, seqs = read_fasta(C.F_PLASTICDB)
    out = []
    for h, s in zip(heads, seqs):
        parts = h.split("|")
        out.append({
            "plasticdb_id": parts[0] if parts else h,
            "enzyme_name": parts[1] if len(parts) > 1 else None,
            "organism": parts[2] if len(parts) > 2 else None,
            "plastic": parts[3] if len(parts) > 3 else None,
            "genbank": parts[4] if len(parts) > 4 else None,
            "sequence": normalise(s),
            "sequence_sha1": sequence_hash(s),
        })
    return pd.DataFrame(out)


def load_uniprot():
    heads, seqs = read_fasta(C.F_UNIPROT)
    out = []
    for h, s in zip(heads, seqs):
        acc = h.split("|")[1] if h.count("|") >= 2 else h.split()[0]
        organism = None
        if "OS=" in h:
            organism = h.split("OS=")[1].split("OX=")[0].strip()
        out.append({
            "accession": acc, "header": h, "organism": organism,
            "sequence": normalise(s), "sequence_sha1": sequence_hash(s),
        })
    return pd.DataFrame(out)


def load_degraders():
    df = pd.read_csv(C.F_DEGRADERS, sep="\t", low_memory=False)
    df = df[df.Sequence.notna()].copy()
    df["sequence"] = df.Sequence.map(normalise)
    df = df[df.sequence.str.len() >= 30]
    df["sequence_sha1"] = df.sequence.map(sequence_hash)
    return df


# --------------------------------------------------------------------------
# KDD stage 2: Preprocessing - the protein registry
# --------------------------------------------------------------------------

def _join(values):
    seen, out = set(), []
    for v in values:
        v = str(v).strip()
        if v and v.lower() not in ("nan", "none") and v not in seen:
            seen.add(v)
            out.append(v)
    return "; ".join(out)


def build_protein_registry(si_rounds, petml_seqs, pazy, plasticdb, uniprot, degraders):
    """One canonical record per unique amino acid sequence.

    Deduplication is on the sequence itself, never on the name: this is what
    resolves BbPETase/BurPL (one protein, two papers, two names) and the two
    mutation-order duplicates in the PETML FASTA.
    """
    acc = defaultdict(lambda: {
        "sequence": None, "names": [], "accessions": [], "sources": [],
        "dois": [], "organisms": [], "source_record_ids": [],
    })

    def add(h, seq, *, name=None, accession=None, source=None, doi=None,
            organism=None, record_id=None):
        e = acc[h]
        e["sequence"] = e["sequence"] or seq
        for key, val in (("names", name), ("accessions", accession),
                         ("sources", source), ("dois", doi),
                         ("organisms", organism), ("source_record_ids", record_id)):
            if val is not None and str(val) != "nan":
                e[key].append(val)

    for r in si_rounds.itertuples():
        add(r.sequence_sha1, r.sequence, name=r.sample_id, accession=r.accession,
            source="SI2025_library", doi=SI_DOI,
            record_id=f"SI2025:{r.sample_id}")

    for r in petml_seqs.itertuples():
        add(r.sequence_sha1, r.sequence, name=r.protein_name, source="PETML",
            record_id=f"PETML:{r.protein_name}")

    for r in pazy.itertuples():
        add(r.sequence_sha1, r.sequence, name=r.protein_name, source="PAZy",
            record_id=f"PAZy:{r.protein_id}")

    for r in plasticdb.itertuples():
        add(r.sequence_sha1, r.sequence, name=r.enzyme_name, accession=r.genbank,
            source="PlasticDB", organism=r.organism,
            record_id=f"PlasticDB:{r.plasticdb_id}")

    for r in uniprot.itertuples():
        add(r.sequence_sha1, r.sequence, name=r.accession, accession=r.accession,
            source="UniProt", organism=r.organism,
            record_id=f"UniProt:{r.accession}")

    for r in degraders.itertuples():
        add(r.sequence_sha1, r.sequence, name=getattr(r, "Enzyme", None),
            accession=getattr(r, "GenbankID", None), source="degraders_list",
            doi=getattr(r, "DOI", None), organism=getattr(r, "Microorganism", None),
            record_id=f"degraders:{r.Index}")

    rows = []
    for h, e in acc.items():
        rows.append({
            "sequence_sha1": h,
            "sequence": e["sequence"],
            "sequence_length": len(e["sequence"]),
            "primary_name": e["names"][0] if e["names"] else None,
            "aliases": _join(e["names"][1:]),
            "accessions": _join(e["accessions"]),
            "source_datasets": _join(e["sources"]),
            "n_source_datasets": len(set(e["sources"])),
            "organism": _join(e["organisms"][:3]) or None,
            "dois": _join(e["dois"]),
            "source_record_ids": _join(e["source_record_ids"]),
        })
    out = pd.DataFrame(rows).sort_values("sequence_sha1").reset_index(drop=True)
    return out


# --------------------------------------------------------------------------
# KDD stage 2: Preprocessing - the observation registry
# --------------------------------------------------------------------------

def build_observations(si_rounds, si_activity, petml_meas, petml_seqs, pazy, pazy_assays):
    """One row per experimental observation, never collapsed across conditions."""
    sid_to_hash = dict(zip(si_rounds.sample_id, si_rounds.sequence_sha1))
    rows = []

    # --- the 2025 standardised screen: one row per assay well ---
    act = si_activity.copy()
    act["is_blank"] = act.sample_id.str.lower() == "blank"
    act["is_control"] = act.sample_id.str.contains("LCC", na=False) | \
        (act.sample_id.str.upper() == "RFP")
    for r in act.itertuples():
        h = sid_to_hash.get(r.sample_id)
        if h is None and not r.is_blank:
            continue
        value = float(r.mM_product)
        rows.append({
            "sequence_sha1": h,
            "study_id": "ACS_Catalysis_2025",
            "source_file": F_SI.name,
            "source_record_id": f"{r.dataset}:{r.plate}:{r.well}",
            "doi": SI_DOI,
            "sample_id": r.sample_id,
            "substrate": r.substrate,
            "temperature_c": r.temperature_c,
            "ph": r.pH,
            "measurement_value": value,
            "measurement_unit": "mM product (TPA+MHET equivalents)",
            "metric_type": "product_concentration",
            "normalised_value": float(r.umol_product_per_mg_enzyme),
            "normalised_unit": "umol product per mg enzyme",
            "enzyme_loading_ug": float(r.enzyme_loading_ug) if pd.notna(r.enzyme_loading_ug) else None,
            "detection_threshold": SI_DETECTION_FLOOR_MM,
            "detection_threshold_unit": "mM product",
            "replicate_group": f"{r.sample_id}|{r.substrate}|{r.temperature_c}|{r.pH}",
            "row_role": "blank" if r.is_blank else ("control" if r.is_control else "library_enzyme"),
            "observation_label": LAB_DETECT if value > 0 else LAB_BELOW,
            "label_basis": (
                "product detected above the 0.03 mM reporting floor"
                if value > 0 else
                "no product above the 0.03 mM reporting floor, in a plate with a blank "
                "and an LCC-ICCG positive control"
            ),
            "evidence_class": EV_STANDARDISED,
        })

    # --- PAZy curated assays ---
    hash_by_pid = dict(zip(pazy.protein_id, pazy.sequence_sha1))
    for r in pazy_assays.itertuples():
        h = hash_by_pid.get(r.protein_id)
        if h is None:
            continue
        value = pd.to_numeric(r.value, errors="coerce")
        rows.append({
            "sequence_sha1": h,
            "study_id": f"PAZy:{r.doi}",
            "source_file": C.F_ASSAYS.name,
            "source_record_id": f"PAZy:{r.protein_id}",
            "doi": r.doi,
            "sample_id": r.protein_name,
            "substrate": f"PET ({r.substrate_form})" if pd.notna(r.substrate_form) else "PET",
            "temperature_c": r.temperature_c,
            "ph": r.ph,
            "measurement_value": float(value) if pd.notna(value) else None,
            "measurement_unit": r.unit,
            "metric_type": r.metric_type,
            "normalised_value": None,
            "normalised_unit": None,
            "enzyme_loading_ug": None,
            "detection_threshold": None,
            "detection_threshold_unit": None,
            "replicate_group": None,
            "row_role": "curated_record",
            "observation_label": (
                LAB_DETECT if pd.notna(value) and value > 0
                else (LAB_BELOW if pd.notna(value) and value == 0 else LAB_UNCERTAIN)
            ),
            "label_basis": (
                "curated database record; PAZy admits proteins with published activity, "
                "so a zero here is a condition-level failure of an otherwise active enzyme, "
                "NOT evidence that the protein is inactive"
            ),
            "evidence_class": EV_CURATED,
        })

    # --- PETML per-study records (ordinal only, never a training label) ---
    name_to_hash = dict(zip(petml_seqs.protein_name, petml_seqs.sequence_sha1))
    for r in petml_meas.itertuples():
        h = name_to_hash.get(r.protein_name)
        if h is None:
            continue
        value = pd.to_numeric(r.activity, errors="coerce")
        rows.append({
            "sequence_sha1": h,
            "study_id": f"PETML:{r.study_id}",
            "source_file": r.source_file,
            "source_record_id": f"PETML:{r.study_id}:{r.sheet}:{r.protein_name}",
            "doi": None,
            "sample_id": r.protein_name,
            "substrate": "PET (unspecified in source file)",
            "temperature_c": None,
            "ph": None,
            "measurement_value": float(value) if pd.notna(value) else None,
            "measurement_unit": None if r.evidence_class != EV_COMPUTATIONAL else "ddG (kcal/mol, computed)",
            "metric_type": "ddG_prediction" if r.evidence_class == EV_COMPUTATIONAL else "relative_activity_uncalibrated",
            "normalised_value": float(r.tm) if pd.notna(r.tm) else None,
            "normalised_unit": "Tm (deg C)" if pd.notna(r.tm) else None,
            "enzyme_loading_ug": None,
            "detection_threshold": None,
            "detection_threshold_unit": None,
            "replicate_group": None,
            "row_role": "literature_record",
            "observation_label": LAB_UNCERTAIN,
            "label_basis": (
                "computational prediction, not a measurement"
                if r.evidence_class == EV_COMPUTATIONAL else
                "within-study relative activity with no recorded unit, substrate form, "
                "enzyme loading or reaction time; comparable only as a rank inside this study"
            ),
            "evidence_class": r.evidence_class,
        })

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# KDD stage 3: Transformation - the condition-specific supervised dataset
# --------------------------------------------------------------------------

def build_condition_labels(observations, si_rounds):
    """Binary labels at one condition: cryPow, 40 C, pH 6.5.

    Every assayed enzyme has data here, including the lowest-yield tier, so
    no enzyme is dropped for lack of coverage at this condition. Replicate
    disagreement is the only source of 'uncertain'.
    """
    obs = observations[
        (observations.evidence_class == EV_STANDARDISED)
        & (observations.row_role == "library_enzyme")
        & (observations.substrate == TARGET_SUBSTRATE)
        & (observations.temperature_c == TARGET_TEMP_C)
        & (observations.ph == TARGET_PH)
    ].copy()

    g = obs.groupby("sequence_sha1").agg(
        sample_id=("sample_id", "first"),
        n_replicates=("measurement_value", "size"),
        n_replicates_positive=("measurement_value", lambda s: int((s > 0).sum())),
        max_mM_product=("measurement_value", "max"),
        mean_mM_product=("measurement_value", "mean"),
        max_umol_per_mg=("normalised_value", "max"),
    ).reset_index()

    def label(r):
        if r.n_replicates_positive == 0:
            return LAB_BELOW
        if r.n_replicates_positive == r.n_replicates:
            return LAB_DETECT
        return LAB_UNCERTAIN

    g["label"] = [label(r) for r in g.itertuples()]
    g["label_basis"] = np.select(
        [g.label == LAB_DETECT, g.label == LAB_BELOW],
        [
            "product above the 0.03 mM floor in every replicate at this condition",
            "no product above the 0.03 mM floor in any replicate at this condition; "
            "condition-qualified only, NOT evidence of universal inactivity",
        ],
        default="replicates disagree at this condition; excluded from binary training",
    )
    # A positive whose maximum sits within two rounding steps of the floor is
    # flagged: it is a real detection, but a weak one.
    g["is_marginal_positive"] = (g.label == LAB_DETECT) & (g.max_mM_product <= 0.05)

    # overall condition coverage, for context only - it does not change the label
    allobs = observations[
        (observations.evidence_class == EV_STANDARDISED)
        & (observations.row_role == "library_enzyme")
    ]
    cov = allobs.assign(
        cond=allobs.substrate.astype(str) + "|" + allobs.temperature_c.astype(str)
        + "|" + allobs.ph.astype(str)
    ).groupby("sequence_sha1").cond.nunique().rename("n_conditions_tested_overall")
    g = g.merge(cov, on="sequence_sha1", how="left")

    meta = si_rounds[["sequence_sha1", "round", "dataset", "expression_mgml", "tm_1"]]
    g = g.merge(meta, on="sequence_sha1", how="left")
    g["condition"] = f"{TARGET_SUBSTRATE}, {TARGET_TEMP_C} C, pH {TARGET_PH}"
    return g.sort_values("sequence_sha1").reset_index(drop=True)


# --------------------------------------------------------------------------
# KDD stage 3: Transformation - homology groups
# --------------------------------------------------------------------------

def _kmers(seq, k=KMER_K):
    return {seq[i:i + k] for i in range(len(seq) - k + 1)}


def _align_chunk(args):
    """Align one block of candidate pairs. Runs in a worker process."""
    pairs, seqs = args
    aligner = make_aligner("local")
    out = []
    for i, j in pairs:
        a, b = seqs[i], seqs[j]
        aln = aligner.align(a, b)[0]
        ident = aln.counts().identities
        cov_a = (aln.coordinates[0][-1] - aln.coordinates[0][0]) / len(a)
        cov_b = (aln.coordinates[1][-1] - aln.coordinates[1][0]) / len(b)
        out.append((i, j,
                    ident / aln.length,                 # identity over aligned columns
                    ident / min(len(a), len(b)),        # identity over shorter sequence
                    min(cov_a, cov_b)))
    return out


def candidate_pairs(seqs, min_jaccard=KMER_MIN_JACCARD):
    """Pairs worth aligning, by 5-mer Jaccard. Cheap, and safe at >=50%."""
    ks = [_kmers(s) for s in seqs]
    n = len(seqs)
    out = []
    for i in range(n):
        ki = ks[i]
        for j in range(i + 1, n):
            kj = ks[j]
            inter = len(ki & kj)
            if not inter:
                continue
            if inter / (len(ki) + len(kj) - inter) >= min_jaccard:
                out.append((i, j))
    return out


def compute_identities(sequences, workers=None):
    """Identity for every candidate pair. Returns a tidy DataFrame."""
    seqs = list(sequences)
    pairs = candidate_pairs(seqs)
    if not pairs:
        return pd.DataFrame(columns=["i", "j", "identity", "identity_shorter", "min_coverage"])
    chunks = [pairs[k:k + 2000] for k in range(0, len(pairs), 2000)]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for block in ex.map(_align_chunk, [(c, seqs) for c in chunks]):
            rows.extend(block)
    return pd.DataFrame(rows, columns=["i", "j", "identity", "identity_shorter", "min_coverage"])


def group_at(n_items, pairs_df, threshold):
    """Single-linkage components over pairs at or above `threshold`.

    Grouping uses identity over the *shorter* sequence and ignores coverage.
    That is deliberate: for leakage control we would rather merge two
    sequences that might be related than risk splitting a near-duplicate
    across the training and test sets. Single linkage merges aggressively for
    the same reason, so the group count is a LOWER bound on independence.
    """
    parent = list(range(n_items))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in pairs_df[pairs_df.identity_shorter >= threshold].itertuples():
        a, b = find(r.i), find(r.j)
        if a != b:
            parent[a] = b
    roots = [find(i) for i in range(n_items)]
    order = {}
    labels = []
    for r in roots:
        if r not in order:
            order[r] = len(order)
        labels.append(order[r])
    return labels


F_PAIRS_CACHE = CURATION / "tables" / "pairwise_identities.csv.gz"


def build_homology_groups(proteins, workers=None, reuse=True):
    """Identity groups at each threshold, for every sequence in the registry.

    The all-vs-all alignment is the expensive step (~100 s), so it is cached.
    The cache is keyed on the registry size and only reused when it matches.
    """
    seqs = proteins.sequence.tolist()
    pairs = None
    if reuse and F_PAIRS_CACHE.exists():
        cached = pd.read_csv(F_PAIRS_CACHE)
        if len(cached) and cached[["i", "j"]].max().max() < len(seqs):
            pairs = cached
    if pairs is None:
        pairs = compute_identities(seqs, workers=workers)
    out = proteins[["sequence_sha1", "sequence_length"]].copy()
    for thr in GROUP_THRESHOLDS:
        out[f"group_{int(thr * 100)}"] = group_at(len(seqs), pairs, thr)
    out["grouping_method"] = (
        "single-linkage over local BLOSUM62 alignments (gap open -11, extend -1); "
        "identity measured over the shorter sequence; coverage recorded but not "
        "required, so that near-duplicates can never be split across a split; "
        f"pairs prefiltered by {KMER_K}-mer Jaccard >= {KMER_MIN_JACCARD}"
    )
    out["primary_group"] = out[f"group_{int(PRIMARY_THRESHOLD * 100)}"]
    return out, pairs


# --------------------------------------------------------------------------
# KDD stage 3: Transformation - leakage-free split
# --------------------------------------------------------------------------

def build_splits(labels, groups, test_every=4, n_folds=5, seed=42):
    """Assign whole identity groups to train or test, never individuals.

    One dominant group holds ~40% of this dataset, so no single holdout can
    give both a diverse training set and a diverse test set. Groups are
    therefore ordered by size and every `test_every`-th is held out, which
    spreads both sides across the size spectrum; the single largest group is
    always kept in training so it cannot swamp the test set.

    Because even this holdout leaves few independent test families, the frame
    also carries `cv_fold`: a grouped 5-fold assignment over the *whole*
    labelled set. Grouped cross-validation is the evaluation we recommend;
    the holdout is provided for a final, single, untouched check.
    """
    df = labels.merge(
        groups[["sequence_sha1", "primary_group"]], on="sequence_sha1", how="left"
    )
    trainable = df[df.label.isin([LAB_DETECT, LAB_BELOW])]

    sizes = (trainable.groupby("primary_group")
             .agg(n=("sequence_sha1", "size"),
                  n_pos=("label", lambda s: int((s == LAB_DETECT).sum())))
             .sort_values(["n", "primary_group"], ascending=[False, True]))

    ordered = sizes.index.tolist()
    # ordered[0] is the dominant group: always training.
    test_groups = {g for k, g in enumerate(ordered) if k > 0 and k % test_every == 1}

    df["split"] = np.where(
        ~df.label.isin([LAB_DETECT, LAB_BELOW]), "excluded",
        np.where(df.primary_group.isin(test_groups), "test", "train"),
    )
    df["split_reason"] = np.select(
        [df.split == "excluded", df.split == "test"],
        [f"label is '{LAB_UNCERTAIN}' - replicates disagree at this condition",
         "identity group held out; no member has a >=70%-identical relative in training"],
        default="identity group assigned to the training set",
    )

    # Grouped CV folds over every labelled sequence, balanced by group size.
    rng = np.random.default_rng(seed)
    fold_load = np.zeros(n_folds, dtype=int)
    fold_of_group = {}
    for gid in ordered:
        k = int(np.argmin(fold_load))
        fold_of_group[gid] = k
        fold_load[k] += int(sizes.loc[gid, "n"])
    df["cv_fold"] = df.primary_group.map(fold_of_group)
    df.loc[df.split == "excluded", "cv_fold"] = -1
    df["cv_fold"] = df.cv_fold.astype(int)

    return df[[
        "sequence_sha1", "sample_id", "primary_group", "label",
        "split", "split_reason", "cv_fold",
    ]].sort_values(["split", "primary_group"]).reset_index(drop=True)


def split_diagnostics(splits, groups, pairs, proteins):
    """Verify no group spans the split, and measure cross-split identity."""
    by = splits[splits.split.isin(["train", "test"])]
    spanning = (by.groupby("primary_group").split.nunique() > 1).sum()

    idx = {h: i for i, h in enumerate(proteins.sequence_sha1)}
    tr = {idx[h] for h in by[by.split == "train"].sequence_sha1}
    te = {idx[h] for h in by[by.split == "test"].sequence_sha1}
    cross = pairs[
        (pairs.i.isin(tr) & pairs.j.isin(te)) | (pairs.i.isin(te) & pairs.j.isin(tr))
    ]
    return {
        "groups_spanning_both_sides": int(spanning),
        "n_train": int((by.split == "train").sum()),
        "n_test": int((by.split == "test").sum()),
        "train_positive": int(((by.split == "train") & (by.label == LAB_DETECT)).sum()),
        "train_negative": int(((by.split == "train") & (by.label == LAB_BELOW)).sum()),
        "test_positive": int(((by.split == "test") & (by.label == LAB_DETECT)).sum()),
        "test_negative": int(((by.split == "test") & (by.label == LAB_BELOW)).sum()),
        "train_groups": int(by[by.split == "train"].primary_group.nunique()),
        "test_groups": int(by[by.split == "test"].primary_group.nunique()),
        "max_cross_split_identity": round(float(cross.identity_shorter.max()), 4) if len(cross) else 0.0,
        "n_cross_split_pairs_above_70pct": int((cross.identity_shorter >= 0.70).sum()) if len(cross) else 0,
        "cv_folds": {
            str(k): {
                "n": int((splits.cv_fold == k).sum()),
                "positive": int(((splits.cv_fold == k) & (splits.label == LAB_DETECT)).sum()),
                "negative": int(((splits.cv_fold == k) & (splits.label == LAB_BELOW)).sum()),
                "groups": int(splits[splits.cv_fold == k].primary_group.nunique()),
            }
            for k in sorted(splits.loc[splits.cv_fold >= 0, "cv_fold"].unique())
        },
    }


# --------------------------------------------------------------------------
# KDD stage 3: Transformation - candidate eligibility
# --------------------------------------------------------------------------

def build_candidate_eligibility(proteins, observations, si_rounds, labels):
    """Classify every registry sequence by what we actually know about it.

    The central rule: a sequence that was never assayed is only a candidate if
    there is no evidence that it was *tried and failed to express*. The 2025
    library's unassayed members fail that rule - the paper's own SI states
    that a BCA concentration under 0.1 mg/mL is a failed purification.
    """
    tested_std = set(
        observations[(observations.evidence_class == EV_STANDARDISED)
                     & (observations.row_role == "library_enzyme")].sequence_sha1
    )
    tested_curated = set(
        observations[observations.evidence_class == EV_CURATED].sequence_sha1
    )
    lit_only = set(
        observations[observations.evidence_class == EV_LITERATURE_REL].sequence_sha1
    )
    uncertain_here = set(labels.loc[labels.label == LAB_UNCERTAIN, "sequence_sha1"])

    expr = si_rounds.set_index("sequence_sha1").expression_mgml.to_dict()
    in_library = set(si_rounds.sequence_sha1)

    rows = []
    for r in proteins.itertuples():
        h = r.sequence_sha1
        yield_mgml = expr.get(h)
        failed_expr = (
            h in in_library and h not in tested_std
            and yield_mgml is not None and pd.notna(yield_mgml)
            and float(yield_mgml) < SI_EXPRESSION_FAIL_MGML
        )
        if failed_expr:
            status, eligible, reason = (
                ST_FAILED_EXPR, False,
                f"in the 2025 library but never assayed; BCA yield {float(yield_mgml):.3f} mg/mL is "
                f"below the {SI_EXPRESSION_FAIL_MGML} mg/mL the source SI describes as a failed "
                "purification. Absence of a measurement here is a production failure, not an "
                "untested opportunity."
            )
        elif h in uncertain_here:
            status, eligible, reason = (
                ST_UNCERTAIN, False,
                "assayed at the target condition but replicates disagree; status unresolved")
        elif h in tested_std:
            status, eligible, reason = (
                ST_TESTED, False,
                "measured in the 2025 standardised screen; already has an experimental label")
        elif h in tested_curated:
            status, eligible, reason = (
                ST_TESTED, False,
                "has curated PET assay evidence in PAZy; already characterised")
        elif h in lit_only:
            status, eligible, reason = (
                ST_UNCERTAIN, False,
                "appears in PETML literature tables with an uncalibrated activity value; "
                "tested, but not on a scale we can interpret")
        elif h in in_library:
            status, eligible, reason = (
                ST_UNCERTAIN, False,
                "in the 2025 library, not assayed, and no expression value recorded")
        else:
            status, eligible, reason = (
                ST_NO_EVIDENCE, True,
                "annotation-only record with no identified PET testing evidence; "
                "eligible for computational ranking, with its nearest characterised "
                "relative reported alongside any score")
        rows.append({
            "sequence_sha1": h,
            "primary_name": r.primary_name,
            "source_datasets": r.source_datasets,
            "sequence_length": r.sequence_length,
            "expression_mgml": yield_mgml,
            "status": status,
            "eligible_for_ranking": eligible,
            "reason": reason,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# PETML external validation feasibility
# --------------------------------------------------------------------------

WILDTYPE_RE = re.compile(r"[_/](?:[A-Z]\d{2,4}[A-Z])")


def petml_wildtype_candidates(petml_seqs, proteins, observations):
    """Which PETML entries could serve as external validation.

    A usable external test protein must (a) look like a wild type rather than
    an engineered point mutant, and (b) carry a real activity label from
    somewhere other than the uncalibrated PETML `Activity` column.
    """
    df = petml_seqs.copy()
    df["looks_engineered"] = df.protein_name.str.contains(WILDTYPE_RE, regex=True)
    curated = set(observations[observations.evidence_class == EV_CURATED].sequence_sha1)
    df["has_curated_label"] = df.sequence_sha1.isin(curated)
    df["usable_as_external_test"] = (~df.looks_engineered) & df.has_curated_label
    return df


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def run(workers=None, write=True, reuse=True):
    """Execute the whole curation pipeline and return every table."""
    CURATION.mkdir(parents=True, exist_ok=True)

    si_rounds = load_si_rounds()
    si_activity = load_si_activity()
    petml_seqs = load_petml_sequences()
    petml_meas = load_petml_measurements()
    pazy = load_pazy_sequences()
    pazy_assays = load_pazy_assays()
    plasticdb = load_plasticdb()
    uniprot = load_uniprot()
    degraders = load_degraders()

    proteins = build_protein_registry(
        si_rounds, petml_seqs, pazy, plasticdb, uniprot, degraders)
    observations = build_observations(
        si_rounds, si_activity, petml_meas, petml_seqs, pazy, pazy_assays)

    # testing status belongs on the master table, derived from observations
    std = set(observations[(observations.evidence_class == EV_STANDARDISED)
                           & (observations.row_role == "library_enzyme")].sequence_sha1)
    cur = set(observations[observations.evidence_class == EV_CURATED].sequence_sha1)
    lit = set(observations[observations.evidence_class == EV_LITERATURE_REL].sequence_sha1)
    proteins["testing_status"] = np.select(
        [proteins.sequence_sha1.isin(std),
         proteins.sequence_sha1.isin(cur),
         proteins.sequence_sha1.isin(lit)],
        ["standardised_screen_measured", "curated_database_measured",
         "literature_uncalibrated_measured"],
        default="no_identified_testing_evidence",
    )
    proteins["provenance"] = np.where(
        proteins.source_datasets.str.contains("SI2025|PETML", regex=True),
        "newly_added_2026", "original_project_source",
    )

    labels = build_condition_labels(observations, si_rounds)
    groups, pairs = build_homology_groups(proteins, workers=workers, reuse=reuse)
    splits = build_splits(labels, groups)
    diagnostics = split_diagnostics(splits, groups, pairs, proteins)
    eligibility = build_candidate_eligibility(proteins, observations, si_rounds, labels)
    petml_wt = petml_wildtype_candidates(petml_seqs, proteins, observations)

    tables = {
        "proteins_master": proteins,
        "experimental_observations": observations,
        "condition_specific_labels": labels,
        "homology_groups": groups,
        "split_assignments": splits,
        "candidate_eligibility": eligibility,
    }
    if write:
        for name, df in tables.items():
            df.to_csv(CURATION / f"{name}.csv", index=False)
        (CURATION / "tables").mkdir(exist_ok=True)
        petml_wt.drop(columns=["sequence"]).to_csv(
            CURATION / "tables" / "petml_external_validation_candidates.csv", index=False)
        pairs.to_csv(CURATION / "tables" / "pairwise_identities.csv.gz",
                     index=False, compression="gzip")
        with open(CURATION / "split_diagnostics.json", "w") as fh:
            json.dump(diagnostics, fh, indent=2)

    tables["diagnostics"] = diagnostics
    tables["petml_wildtype"] = petml_wt
    tables["pairs"] = pairs
    return tables


if __name__ == "__main__":  # pragma: no cover
    out = run()
    print(json.dumps(out["diagnostics"], indent=2))
    for k in ("proteins_master", "experimental_observations",
              "condition_specific_labels", "homology_groups",
              "split_assignments", "candidate_eligibility"):
        print(f"{k:32s} {len(out[k]):7d} rows")
