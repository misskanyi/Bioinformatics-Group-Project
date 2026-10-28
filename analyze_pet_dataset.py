#!/usr/bin/env python3
"""
PET-active vs PET-inactive dataset feasibility analysis.

Reads the six raw files in data/ in their original formats, derives a
protein-level PET activity label from the PAZy assay records using explicit
(documented) rules, matches labels to sequences, measures sequence redundancy,
and writes tables, figures and summary numbers to outputs/.

No machine-learning model is trained here.

Usage:
    .venv/bin/python analyze_pet_dataset.py            # full run
    .venv/bin/python analyze_pet_dataset.py --reuse-identity   # reuse cached pairwise identities
"""

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from Bio import SeqIO
from Bio.Align import PairwiseAligner, substitution_matrices

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
TABLES = OUT / "tables"
FIGS = OUT / "figures"

F_CSV = DATA / "pazy_proteins_sequences.csv"
F_ASSAYS = DATA / "pazy_polymer_assays.json.gz"
F_PAZY_FA = DATA / "pazy_proteins.fasta"
F_PLASTICDB = DATA / "PlasticDB.fasta"
F_DEGRADERS = DATA / "degraders_list.tsv"
F_UNIPROT = DATA / "uniprotkb_accession_E9LVH8_OR_accession_2026_10_27.fasta.gz"

VALID_AA = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")

# Measurement metrics that directly quantify PET breakdown (products released,
# substrate converted, mass lost, hydrolytic activity on the polymer).
DIRECT_METRICS = {
    "product_concentration", "product_amount", "product_release_rate",
    "specific_activity", "conversion_percent", "mass_loss_percent",
    "depolymerization_percent",
}
# Metrics that are indirect / not interpretable as "degradation detected"
# without the paper (relative activity, surface contact angle, raw absorbance,
# fluorescence, kinetic constants, "other").
POSITIVE_CATEGORIES = {"detected", "positive"}
NEGATIVE_CATEGORIES = {"not_detected", "negative"}
# Indirect-metric analytes that still quantify PET breakdown (product release or
# hydrolysis rates reported by the authors) -> a value > 0 counts as positive.
RATE_ANALYTE = re.compile(
    r"release normali[sz]ed|hydrolysis rate|degradation rate|conversion rate|mass-loss rate"
    r"|hydrolytic activity \(sum|A260 reaction rate|hydrolysis rate constant", re.I)
# A single named product (e.g. "no BHET") being absent does not mean the PET
# was not degraded - other products may still be released.
SINGLE_PRODUCT = re.compile(r"^(BHET|MHET|TPA|TA|EG|TPA by UHPLC|bis\(2-hydroxyethyl\) terephthalate \(BHET\))$", re.I)
# Surface-only observations (SEM, contact angle) are not degradation measurements.
SURFACE_ONLY = re.compile(r"SEM|morpholog|contact angle|hydrophilicity", re.I)

# Materials recorded under substrate "PET" that are not plain PET homopolymer.
NON_PET_MATERIAL = [
    (re.compile(r"\bPET-G\b|\bPETG\b(?!Fa)", re.I), "PETG (glycol-modified copolyester)"),
    (re.compile(r"^polyester synthetic fiber substrate$", re.I), "unspecified polyester fibre"),
]

# Colours: reference categorical palette (light mode), fixed slot order.
C_BLUE, C_ORANGE, C_AQUA, C_YELLOW, C_MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
C_GREY, C_INK, C_INK2, C_GRID = "#a3a29c", "#0b0b0b", "#52514e", "#e6e5e0"

LABEL_ORDER = [
    "PET-active",
    "PET-active (condition-dependent)",
    "Conflicting (across studies)",
    "PET-inactive (tested conditions)",
    "Unclear",
]


# --------------------------------------------------------------------------- #
# Step 1: load and inspect
# --------------------------------------------------------------------------- #
def load_all():
    seqs = pd.read_csv(F_CSV)
    with gzip.open(F_ASSAYS, "rt") as fh:
        records = json.load(fh)
    pazy_fa = list(SeqIO.parse(F_PAZY_FA, "fasta"))
    plasticdb = list(SeqIO.parse(F_PLASTICDB, "fasta"))
    degraders = pd.read_csv(F_DEGRADERS, sep="\t")
    with gzip.open(F_UNIPROT, "rt") as fh:
        uniprot = list(SeqIO.parse(fh, "fasta"))
    return seqs, records, pazy_fa, plasticdb, degraders, uniprot


def inspect_datasets(seqs, records, pazy_fa, plasticdb, degraders, uniprot):
    """One row per file describing structure, size, missingness and duplicates."""
    rows = []
    rows.append({
        "file": F_CSV.name, "format": "CSV", "records": len(seqs),
        "fields": "; ".join(f"{c} ({t})" for c, t in seqs.dtypes.astype(str).items()),
        "missing_values": int(seqs.isna().sum().sum()),
        "unique_ids": seqs["protein_id"].nunique(),
        "duplicate_sequences": int(seqs["amino_acid_sequence"].duplicated().sum()),
        "notes": "Key = protein_id (integer). Only PET-tested PAZy proteins appear here.",
    })
    n_assays = sum(len(r["assays"]) for r in records)
    rows.append({
        "file": F_ASSAYS.name, "format": "gzipped JSON list",
        "records": len(records),
        "fields": "top: " + ", ".join(records[0].keys()) + " | assay: " + ", ".join(records[0]["assays"][0].keys()),
        "missing_values": None,
        "unique_ids": len({r["protein_id"] for r in records}),
        "duplicate_sequences": None,
        "notes": f"One record per protein x publication; {n_assays} assays in total. Key = protein_id. No sequences, no organism field.",
    })
    fa_seqs = [str(r.seq) for r in pazy_fa]
    rows.append({
        "file": F_PAZY_FA.name, "format": "FASTA", "records": len(pazy_fa),
        "fields": "header '>protein_id protein_name'",
        "missing_values": 0, "unique_ids": len({r.id for r in pazy_fa}),
        "duplicate_sequences": len(fa_seqs) - len(set(fa_seqs)),
        "notes": "Same IDs/sequences as the CSV (checked in Step 4).",
    })
    p_seqs = [str(r.seq) for r in plasticdb]
    rows.append({
        "file": F_PLASTICDB.name, "format": "FASTA", "records": len(plasticdb),
        "fields": "header 'id|enzyme|organism|plastics(_-separated)|GenBank'",
        "missing_values": sum(r.id.split("|")[4] == "NA" for r in plasticdb),
        "unique_ids": len({r.id.split('|')[0] for r in plasticdb}),
        "duplicate_sequences": len(p_seqs) - len(set(p_seqs)),
        "notes": "Positive associations only (no negative results). missing_values = entries with GenBank 'NA'.",
    })
    rows.append({
        "file": F_DEGRADERS.name, "format": "TSV", "records": len(degraders),
        "fields": "; ".join(degraders.columns),
        "missing_values": int(degraders.isna().sum().sum()),
        "unique_ids": degraders["Microorganism"].nunique(),
        "duplicate_sequences": int(degraders["Sequence"].dropna().duplicated().sum()),
        "notes": "Organism x plastic rows (unique_ids = unique organisms); only some rows carry an enzyme sequence. Positive reports only.",
    })
    rows.append({
        "file": F_UNIPROT.name, "format": "gzipped FASTA", "records": len(uniprot),
        "fields": "UniProt header (sp|ACC|ENTRY desc OS= OX= GN= PE= SV=)",
        "missing_values": 0, "unique_ids": len(uniprot),
        "duplicate_sequences": len(uniprot) - len({str(r.seq) for r in uniprot}),
        "notes": "; ".join(r.id.split("|")[1] + " " + r.description.split(" OS=")[0].split(" ", 1)[1] for r in uniprot),
    })
    return pd.DataFrame(rows)


def substrate_counts(records):
    c = Counter(a["substrate"] for r in records for a in r["assays"])
    p = defaultdict(set)
    for r in records:
        for a in r["assays"]:
            p[a["substrate"]].add(r["protein_id"])
    return pd.DataFrame(
        [{"substrate": s, "assay_records": n, "unique_proteins": len(p[s])} for s, n in c.most_common()]
    )


# --------------------------------------------------------------------------- #
# Steps 2-3: PET assays and outcome rules
# --------------------------------------------------------------------------- #
def material_flag(name):
    for pat, label in NON_PET_MATERIAL:
        if pat.search(name or ""):
            return label
    return ""


def classify_measurement(m):
    """Return POS / NEG / UNCLEAR plus a short reason for one measurement."""
    cat = m.get("categorical_result")
    analyte = (m.get("analyte") or "").strip()
    if cat in POSITIVE_CATEGORIES:
        return "POS", f"categorical '{cat}'"
    if cat in NEGATIVE_CATEGORIES:
        if SINGLE_PRODUCT.match(analyte):
            return "UNCLEAR", "only one product reported absent"
        if SURFACE_ONLY.search(analyte):
            return "UNCLEAR", "surface-only observation negative"
        return "NEG", f"categorical '{cat}'"
    metric = m.get("metric_type")
    v, q = m.get("value"), m.get("qualifier")
    if metric not in DIRECT_METRICS:
        if RATE_ANALYTE.search(analyte) and isinstance(v, (int, float)) and v > 0 and q != "<":
            return "POS", f"{metric} rate/release > 0"
        return "UNCLEAR", f"indirect metric '{metric}'"
    if v == 0 and SINGLE_PRODUCT.match(analyte):
        return "UNCLEAR", "only one product measured as 0"
    if v is None:
        return "UNCLEAR", "no value"
    if q == "<":
        return "UNCLEAR", "reported only as below a threshold ('<')"
    if v < 0:
        return "UNCLEAR", "negative value"
    if v > 0:
        return "POS", f"{metric} > 0" + (" (digitised ~)" if q == "~" else "")
    # v == 0
    if q == "~":
        return "UNCLEAR", "~0 digitised from a figure"
    return "NEG", f"{metric} = 0 (no product/activity measured)"


def build_assay_table(records):
    rows = []
    for ri, r in enumerate(records):
        for ai, a in enumerate(r["assays"]):
            if a["substrate"] != "PET":
                continue
            c, mat = a["conditions"], a["material"]
            add = c.get("additional_conditions") or {}
            mflag = material_flag(mat.get("reported_name"))
            calls = [classify_measurement(m) for m in a["measurements"]]
            kinds = {k for k, _ in calls}
            if mflag:
                outcome, reason = "EXCLUDED", f"material is {mflag}"
            elif c.get("duration_value") == 0:
                outcome, reason = "EXCLUDED", "time-zero sample (duration 0)"
            elif "POS" in kinds:
                outcome, reason = "POS", next(x for k, x in calls if k == "POS")
            elif "NEG" in kinds:
                outcome, reason = "NEG", next(x for k, x in calls if k == "NEG")
            else:
                outcome, reason = "UNCLEAR", calls[0][1] if calls else "no measurements"
            rows.append({
                "record_index": ri,
                "assay_index": ai,
                "protein_id": r["protein_id"],
                "protein_name": r["protein_name"],
                "literature_doi": r["literature_doi"],
                "reference_role": r["reference_role"],
                "is_representative": a["is_representative"],
                "material_name": mat.get("reported_name"),
                "material_form": mat.get("form"),
                "crystallinity_percent": mat.get("crystallinity_percent"),
                "material_flag": mflag,
                "temperature_c": c.get("temperature_c"),
                "ph": c.get("ph"),
                "duration_value": c.get("duration_value"),
                "duration_unit": c.get("duration_unit"),
                "enzyme_preparation": c.get("enzyme_preparation"),
                "enzyme_features": "; ".join(c.get("enzyme_features") or []),
                "experiment_context": add.get("experiment_context"),
                "background_correction": add.get("background_correction"),
                "detection_methods": "; ".join(d["method"] for d in a["detection_methods"]),
                "metric_types": "; ".join(sorted({m["metric_type"] for m in a["measurements"]})),
                "n_measurements": len(a["measurements"]),
                "max_value": max((m["value"] for m in a["measurements"] if isinstance(m.get("value"), (int, float))), default=None),
                "units": "; ".join(sorted({m.get("unit") or "" for m in a["measurements"]} - {""})),
                "categorical_results": "; ".join(sorted({m.get("categorical_result") for m in a["measurements"] if m.get("categorical_result")})),
                "qualifiers": "; ".join(sorted({m.get("qualifier") for m in a["measurements"] if m.get("qualifier")})),
                "assay_outcome": outcome,
                "outcome_reason": reason,
            })
    return pd.DataFrame(rows)


def label_proteins(assays):
    """Aggregate assay outcomes into one evidence label per protein."""
    out = []
    for pid, g in assays.groupby("protein_id"):
        pos, neg = g[g.assay_outcome == "POS"], g[g.assay_outcome == "NEG"]
        pubs_pos, pubs_neg = set(pos.literature_doi), set(neg.literature_doi)
        if len(pos) and not len(neg):
            label = "PET-active"
        elif len(pos) and len(neg):
            # every negative comes from a paper that ALSO reports activity -> condition-dependent
            label = ("PET-active (condition-dependent)" if pubs_neg <= pubs_pos
                     else "Conflicting (across studies)")
        elif len(neg):
            label = "PET-inactive (tested conditions)"
        else:
            label = "Unclear"

        # confidence
        quant_pos = pos[~pos.outcome_reason.str.startswith("categorical")]
        purified = {"purified", "commercial_preparation"}
        if label.startswith("PET-active") or label.startswith("Conflicting"):
            if len(quant_pos) and quant_pos.enzyme_preparation.isin(purified).any():
                conf = "high" if label != "Conflicting (across studies)" else "low"
            else:
                conf = "medium" if label != "Conflicting (across studies)" else "low"
        elif label.startswith("PET-inactive"):
            neg_conditions = neg[["temperature_c", "ph", "material_form"]].astype(str).drop_duplicates()
            all_pure = neg.enzyme_preparation.isin(purified).all()
            if all_pure and len(neg) >= 3 and len(neg_conditions) >= 2:
                conf = "high"
            elif neg.enzyme_preparation.isin(purified).any():
                conf = "medium"
            else:
                conf = "low"
        else:
            conf = "none"

        def rng(col, frame):
            v = pd.to_numeric(frame[col], errors="coerce").dropna()
            return "" if v.empty else (f"{v.min():g}" if v.min() == v.max() else f"{v.min():g}-{v.max():g}")

        out.append({
            "protein_id": pid,
            "protein_name": g.protein_name.iloc[0],
            "pet_label": label,
            "label_confidence": conf,
            "n_pet_assays": len(g),
            "n_positive_assays": len(pos),
            "n_negative_assays": len(neg),
            "n_unclear_assays": int((g.assay_outcome == "UNCLEAR").sum()),
            "n_excluded_assays": int((g.assay_outcome == "EXCLUDED").sum()),
            "n_publications": g.literature_doi.nunique(),
            "n_publications_positive": len(pubs_pos),
            "n_publications_negative_only": len(pubs_neg - pubs_pos),
            "temperature_range_c": rng("temperature_c", g),
            "ph_range": rng("ph", g),
            "negative_temperature_range_c": rng("temperature_c", neg),
            "negative_ph_range": rng("ph", neg),
            "substrate_forms": "; ".join(sorted(set(g.material_form.dropna()))),
            "enzyme_preparations": "; ".join(sorted(set(g.enzyme_preparation.dropna()))),
            "detection_methods": "; ".join(sorted({x for s in g.detection_methods for x in s.split("; ") if x}))[:300],
            "positive_evidence_example": pos.outcome_reason.iloc[0] if len(pos) else "",
            "negative_evidence_example": neg.outcome_reason.iloc[0] if len(neg) else "",
            "in_standardised_screen": bool(g.experiment_context.fillna("").str.contains("Source Data Table D").any()),
            "dois": "; ".join(sorted(set(g.literature_doi))),
        })
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- #
# Step 4: sequences and external annotations
# --------------------------------------------------------------------------- #
def attach_sequences(labels, seqs, pazy_fa, plasticdb, degraders, uniprot):
    seq_by_id = dict(zip(seqs.protein_id, seqs.amino_acid_sequence))
    name_by_id = dict(zip(seqs.protein_id, seqs.protein_name))
    fa_by_id = {int(r.id): str(r.seq) for r in pazy_fa}

    pdb_by_seq = defaultdict(list)
    for r in plasticdb:
        pid, enz, org, plastics, gb = r.id.split("|")
        pdb_by_seq[str(r.seq).upper()].append((pid, enz.replace("_", " "), org.replace("_", " "), plastics, gb))
    deg = degraders.dropna(subset=["Sequence"])
    deg_by_seq = defaultdict(set)
    for s, org in zip(deg.Sequence.str.upper().str.strip(), deg.Microorganism):
        deg_by_seq[s].add(org)
    uni = [(r.id.split("|")[1], re.search(r"OS=(.+?) OX=", r.description).group(1), str(r.seq)) for r in uniprot]

    rows = []
    for _, row in labels.iterrows():
        pid = row.protein_id
        s = seq_by_id.get(pid)
        d = {"has_sequence": s is not None}
        d["sequence_length"] = len(s) if s else None
        d["sequence_valid_aa"] = bool(s and VALID_AA.match(s))
        d["fasta_matches_csv"] = (fa_by_id.get(pid) == s) if s else None
        d["csv_name"] = name_by_id.get(pid, "")
        d["name_consistent"] = (name_by_id.get(pid, "").lower() == row.protein_name.lower()) if s else None
        hits = pdb_by_seq.get(s.upper(), []) if s else []
        d["plasticdb_ids"] = "; ".join(h[0] for h in hits)
        d["plasticdb_enzyme_name"] = "; ".join(sorted({h[1] for h in hits}))
        d["plasticdb_plastics"] = "; ".join(sorted({p for h in hits for p in h[3].split("_")}))
        d["genbank"] = "; ".join(sorted({h[4] for h in hits if h[4] != "NA"}))
        orgs = {h[2] for h in hits} | (deg_by_seq.get(s.upper(), set()) if s else set())
        u_exact = [u for u in uni if s and u[2] == s]
        u_contained = [u for u in uni if s and u[2] != s and (u[2] in s or s in u[2])]
        orgs |= {u[1] for u in u_exact + u_contained}
        d["organism"] = "; ".join(sorted(orgs)) if orgs else "not available in provided files"
        d["uniprot_match"] = "; ".join([f"{u[0]} (exact)" for u in u_exact] + [f"{u[0]} (substring)" for u in u_contained])
        d["sequence"] = s or ""
        rows.append(d)
    return pd.concat([labels.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


# --------------------------------------------------------------------------- #
# Sequence similarity (pairwise global alignment, free end gaps)
# --------------------------------------------------------------------------- #
_ALIGNER = None


def _aligner():
    global _ALIGNER
    if _ALIGNER is None:
        a = PairwiseAligner()
        a.substitution_matrix = substitution_matrices.load("BLOSUM62")
        a.open_gap_score, a.extend_gap_score = -10, -0.5
        a.end_gap_score = 0  # semi-global: tolerate signal peptides / truncations
        _ALIGNER = a
    return _ALIGNER


def _identity_row(args):
    i, seqs = args
    al = _aligner()
    res = []
    for j in range(i + 1, len(seqs)):
        aln = al.align(seqs[i], seqs[j])[0]
        ident = aln.counts().identities
        res.append((i, j, ident / min(len(seqs[i]), len(seqs[j]))))
    return res


def pairwise_identity(ids, seqs, cache, reuse):
    if reuse and cache.exists():
        return pd.read_csv(cache)
    with ProcessPoolExecutor() as ex:
        chunks = ex.map(_identity_row, [(i, seqs) for i in range(len(seqs))], chunksize=4)
        rows = [x for ch in chunks for x in ch]
    df = pd.DataFrame(rows, columns=["i", "j", "identity"])
    df["protein_id_a"] = [ids[i] for i in df.i]
    df["protein_id_b"] = [ids[j] for j in df.j]
    df = df[["protein_id_a", "protein_id_b", "identity"]]
    df.to_csv(cache, index=False)
    return df


def single_linkage(ids, pairs, threshold):
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs.loc[pairs.identity >= threshold, ["protein_id_a", "protein_id_b"]].itertuples(index=False):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return {i: find(i) for i in ids}


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(C_GRID)
    ax.tick_params(colors=C_INK2, labelsize=9)
    ax.grid(axis="x", color=C_GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def hbar(ax, labels, values, color, title, xlabel):
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, color=color, height=0.6, edgecolor="white", linewidth=2)
    ax.set_yticks(y, labels)
    for yi, v in zip(y, values):
        ax.text(v, yi, f"  {v:,}", va="center", fontsize=9, color=C_INK)
    ax.set_title(title, loc="left", fontsize=11, color=C_INK, fontweight="bold")
    ax.set_xlabel(xlabel, color=C_INK2, fontsize=9)
    ax.set_xlim(0, max(values) * 1.18 if len(values) else 1)
    _style(ax)


def make_figures(subs, assays, summary, pairs, cluster_table, cross):
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.dpi": 150})

    # 1. assays per substrate
    fig, ax = plt.subplots(figsize=(7, 4))
    colors = [C_BLUE if s == "PET" else C_GREY for s in subs.substrate]
    y = np.arange(len(subs))[::-1]
    ax.barh(y, subs.assay_records, color=colors, height=0.6, edgecolor="white", linewidth=2)
    ax.set_yticks(y, subs.substrate)
    for yi, v, p in zip(y, subs.assay_records, subs.unique_proteins):
        ax.text(v, yi, f"  {v:,} assays / {p} proteins", va="center", fontsize=8.5, color=C_INK)
    ax.set_xlim(0, subs.assay_records.max() * 1.45)
    ax.set_title("PAZy assay records by substrate (PET highlighted)", loc="left", fontsize=11, fontweight="bold")
    ax.set_xlabel("Assay records", color=C_INK2, fontsize=9)
    _style(ax)
    fig.tight_layout(); fig.savefig(FIGS / "01_assays_by_substrate.png"); plt.close(fig)

    # 2. assay outcome counts + protein labels
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1, 1.5]})
    oc = assays.assay_outcome.value_counts().reindex(["POS", "NEG", "UNCLEAR", "EXCLUDED"]).fillna(0).astype(int)
    hbar(axes[0], ["Degradation detected", "Nothing detected (0)", "Unclear", "Excluded"], oc.values, C_BLUE,
         "PET assay outcomes", "Assay records")
    lc = summary.pet_label.value_counts().reindex(LABEL_ORDER).fillna(0).astype(int)
    hbar(axes[1], LABEL_ORDER, lc.values, C_BLUE, "Protein-level PET labels (all PET-tested proteins)", "Unique proteins")
    fig.tight_layout(); fig.savefig(FIGS / "02_assay_outcomes_and_protein_labels.png"); plt.close(fig)

    # 3. evidence per protein: positive vs negative assay counts
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for lab, col in [("PET-active", C_BLUE), ("PET-active (condition-dependent)", C_AQUA),
                     ("Conflicting (across studies)", C_YELLOW), ("PET-inactive (tested conditions)", C_ORANGE)]:
        g = summary[summary.pet_label == lab]
        ax.scatter(g.n_positive_assays + 1, g.n_negative_assays + 1, s=28, color=col, label=f"{lab} (n={len(g)})",
                   edgecolor="white", linewidth=1, alpha=0.9)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Positive PET assays per protein (+1, log)", color=C_INK2, fontsize=9)
    ax.set_ylabel("No-detection PET assays per protein (+1, log)", color=C_INK2, fontsize=9)
    ax.set_title("How much evidence supports each protein's label", loc="left", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2)
    _style(ax); ax.grid(axis="y", color=C_GRID, linewidth=0.8)
    fig.tight_layout(); fig.savefig(FIGS / "03_evidence_per_protein.png"); plt.close(fig)

    # 4. redundancy: independent clusters vs identity threshold
    fig, ax = plt.subplots(figsize=(7, 4))
    ct = cluster_table
    x = ct.identity_threshold * 100
    ax.plot(x, ct.clusters_with_active, color=C_BLUE, lw=2, marker="o", ms=6, label="clusters with a usable PET-active protein")
    ax.plot(x, ct.clusters_with_inactive, color=C_ORANGE, lw=2, marker="o", ms=6, label="clusters with a usable PET-inactive protein")
    for xi, a in zip(x, ct.clusters_with_active):
        ax.annotate(str(a), (xi, a), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8, color=C_INK)
    ax.set_xlabel("Sequence identity threshold for grouping (%)", color=C_INK2, fontsize=9)
    ax.set_ylabel("Independent sequence clusters", color=C_INK2, fontsize=9)
    ax.set_title("Independent examples after grouping similar sequences", loc="left", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    _style(ax); ax.grid(axis="y", color=C_GRID, linewidth=0.8)
    fig.tight_layout(); fig.savefig(FIGS / "04_clusters_vs_identity_threshold.png"); plt.close(fig)

    # 5. sequence availability per protein label
    fig, ax = plt.subplots(figsize=(8, 3.8))
    tab = pd.crosstab(summary.pet_label, summary.has_sequence).reindex(LABEL_ORDER).fillna(0).astype(int)
    with_seq = tab.get(True, pd.Series(0, index=tab.index)).values
    without = tab.get(False, pd.Series(0, index=tab.index)).values
    y = np.arange(len(tab))[::-1]
    ax.barh(y, with_seq, color=C_BLUE, height=0.6, edgecolor="white", linewidth=2, label="sequence available")
    ax.barh(y, without, left=with_seq, color=C_ORANGE, height=0.6, edgecolor="white", linewidth=2, label="no sequence in provided files")
    ax.set_yticks(y, tab.index)
    for yi, a_, b_ in zip(y, with_seq, without):
        ax.text(a_ + b_, yi, f"  {a_} with / {b_} without", va="center", fontsize=8.5, color=C_INK)
    ax.set_xscale("symlog", linthresh=10)
    ax.set_xlim(0, (with_seq + without).max() * 4)
    ax.set_xlabel("Unique proteins (symmetric log scale)", color=C_INK2, fontsize=9)
    ax.set_title("Every PET-inactive protein lacks a sequence in the provided files", loc="left", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, frameon=False, loc="lower right")
    _style(ax)
    fig.tight_layout(); fig.savefig(FIGS / "05_sequence_availability_by_label.png"); plt.close(fig)

    # 6. PET assay temperatures by outcome
    fig, ax = plt.subplots(figsize=(7, 3.8))
    t = assays[assays.assay_outcome.isin(["POS", "NEG"])]
    bins = np.arange(12.5, 95, 5)  # centred on 15, 20, ... °C
    ax.hist([t[t.assay_outcome == "POS"].temperature_c.dropna(), t[t.assay_outcome == "NEG"].temperature_c.dropna()],
            bins=bins, color=[C_BLUE, C_ORANGE], label=["degradation detected", "nothing detected"],
            edgecolor="white", linewidth=1.5)
    ax.set_xlabel("Assay temperature (°C)", color=C_INK2, fontsize=9)
    ax.set_ylabel("PET assay records", color=C_INK2, fontsize=9)
    ax.set_title("PET assay conditions differ widely (temperature shown)", loc="left", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, frameon=False)
    _style(ax); ax.grid(axis="y", color=C_GRID, linewidth=0.8); ax.grid(axis="x", visible=False)
    fig.tight_layout(); fig.savefig(FIGS / "06_assay_temperature_by_outcome.png"); plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse-identity", action="store_true", help="reuse cached pairwise identity table")
    args = ap.parse_args()
    for d in (OUT, TABLES, FIGS):
        d.mkdir(parents=True, exist_ok=True)

    seqs, records, pazy_fa, plasticdb, degraders, uniprot = load_all()

    # Step 1
    inventory = inspect_datasets(seqs, records, pazy_fa, plasticdb, degraders, uniprot)
    inventory.to_csv(TABLES / "dataset_inventory.csv", index=False)
    subs = substrate_counts(records)
    subs.to_csv(TABLES / "assays_by_substrate.csv", index=False)

    # Steps 2-3
    assays = build_assay_table(records)
    assays.to_csv(TABLES / "pet_assay_records.csv", index=False)
    labels = label_proteins(assays)

    # Step 4
    summary = attach_sequences(labels, seqs, pazy_fa, plasticdb, degraders, uniprot)
    pet_ids = set(assays.protein_id)
    all_json_ids = {r["protein_id"] for r in records}
    csv_ids = set(seqs.protein_id)
    unmatched_assays = assays[~assays.protein_id.isin(csv_ids)]

    # usable = valid sequence + (active/cond-dependent with high|medium) or (inactive with high|medium)
    summary["usable_for_binary_ml"] = (
        summary.has_sequence & summary.sequence_valid_aa
        & summary.label_confidence.isin(["high", "medium"])
        & summary.pet_label.isin(["PET-active", "PET-active (condition-dependent)", "PET-inactive (tested conditions)"])
    )
    summary["binary_class"] = np.where(
        ~summary.usable_for_binary_ml, "",
        np.where(summary.pet_label.str.startswith("PET-active"), "active", "inactive"))

    # Similarity / leakage
    seq_df = summary[summary.has_sequence].sort_values("protein_id")
    ids, sq = seq_df.protein_id.tolist(), seq_df.sequence.tolist()
    pairs = pairwise_identity(ids, sq, TABLES / "pairwise_identity.csv", args.reuse_identity)

    exact_dup_groups = seq_df.groupby("sequence").protein_id.apply(list)
    exact_dup_groups = exact_dup_groups[exact_dup_groups.str.len() > 1]

    cls = dict(zip(summary.protein_id, summary.binary_class))
    usable_ids = [i for i in ids if cls.get(i)]
    up = pairs[pairs.protein_id_a.isin(usable_ids) & pairs.protein_id_b.isin(usable_ids)]
    crows = []
    for thr in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]:
        root = single_linkage(usable_ids, up, thr)
        groups = defaultdict(set)
        for i, r in root.items():
            groups[r].add(cls[i])
        crows.append({
            "identity_threshold": thr,
            "clusters_total": len(groups),
            "clusters_with_active": sum("active" in g for g in groups.values()),
            "clusters_with_inactive": sum("inactive" in g for g in groups.values()),
            "mixed_clusters": sum(len(g) == 2 for g in groups.values()),
            "active_only_clusters": sum(g == {"active"} for g in groups.values()),
            "inactive_only_clusters": sum(g == {"inactive"} for g in groups.values()),
        })
    cluster_table = pd.DataFrame(crows)
    cluster_table.to_csv(TABLES / "redundancy_clusters_by_threshold.csv", index=False)
    for thr in (0.4, 0.7, 0.9):
        root = single_linkage(ids, pairs, thr)
        summary[f"cluster_id_{int(thr*100)}pct"] = summary.protein_id.map(root)

    # nearest neighbours
    sym = pd.concat([pairs, pairs.rename(columns={"protein_id_a": "protein_id_b", "protein_id_b": "protein_id_a"})])
    nn = sym.sort_values("identity", ascending=False).drop_duplicates("protein_id_a")
    summary["nearest_neighbour_id"] = summary.protein_id.map(dict(zip(nn.protein_id_a, nn.protein_id_b)))
    summary["nearest_neighbour_identity"] = summary.protein_id.map(dict(zip(nn.protein_id_a, nn.identity))).round(3)
    sym["cls_b"] = sym.protein_id_b.map(cls)
    sym["cls_a"] = sym.protein_id_a.map(cls)
    inact_vs_act = sym[(sym.cls_a == "inactive") & (sym.cls_b == "active")]
    cross = inact_vs_act.groupby("protein_id_a").identity.max().rename("max_identity_to_active").reset_index()
    summary["max_identity_to_opposite_class"] = summary.protein_id.map(
        sym[(sym.cls_a != "") & (sym.cls_b != "") & sym.cls_a.notna() & sym.cls_b.notna() & (sym.cls_a != sym.cls_b)]
        .groupby("protein_id_a").identity.max()).round(3)

    # standardised screen subset (same lab, same protocol)
    scr = assays[assays.experiment_context.fillna("").str.contains("Source Data Table D")]
    scr_lab = label_proteins(scr) if len(scr) else pd.DataFrame(columns=["pet_label"])
    scr_lab = scr_lab[scr_lab.protein_id.isin(csv_ids)]
    scr_lab[["protein_id", "protein_name", "pet_label", "n_positive_assays", "n_negative_assays", "dois"]].to_csv(
        TABLES / "standardised_screen_labels.csv", index=False)

    # alternative tasks: annotations available
    multi_sub = defaultdict(set)
    for r in records:
        for a in r["assays"]:
            multi_sub[r["protein_id"]].add(a["substrate"])
    pdb_names = Counter()
    for r in plasticdb:
        n = r.id.split("|")[1].lower()
        key = next((k for k in ["petase", "cutinase", "lipase", "esterase", "depolymerase", "hydrolase",
                                 "protease", "amidase", "urethanase", "laccase", "peroxidase", "oxidase"] if k in n), "other")
        pdb_names[key] += 1
    pd.DataFrame(pdb_names.most_common(), columns=["plasticdb_name_keyword", "sequences"]).to_csv(
        TABLES / "plasticdb_enzyme_name_keywords.csv", index=False)
    pdb_pet = sum("PET" in r.id.split("|")[3].split("_") for r in plasticdb)
    pdb_pet_only_new = len({str(r.seq) for r in plasticdb if "PET" in r.id.split("|")[3].split("_")} - set(seqs.amino_acid_sequence))

    # Save protein summary
    cols = [c for c in summary.columns if c != "sequence"] + ["sequence"]
    summary = summary[cols].sort_values(["pet_label", "protein_id"])
    summary.to_csv(OUT / "pet_protein_activity_summary.csv", index=False)

    # Step 5 quality summary
    lc = summary.pet_label.value_counts()
    usable = summary[summary.usable_for_binary_ml]
    hi = lambda thr: int(pairs[(pairs.identity >= thr)].shape[0])
    hi_usable = lambda thr: int(up[up.identity >= thr].shape[0])
    ct = cluster_table.set_index("identity_threshold")
    q = [
        ("Total protein sequences (PAZy CSV)", len(seqs), "Rows in pazy_proteins_sequences.csv (all have unique protein_id)."),
        ("PAZy FASTA sequences identical to CSV", int(summary.fasta_matches_csv.eq(True).sum()), "FASTA header ID -> same sequence string as CSV."),
        ("Proteins in assay JSON (all substrates)", len(all_json_ids), "Unique protein_id in pazy_polymer_assays.json.gz."),
        ("Protein x publication records in assay JSON", len(records), "Top-level JSON entries."),
        ("Total assay records (all substrates)", int(subs.assay_records.sum()), "Sum of assays[] across records."),
        ("Total PET-related assay records", len(assays), "Assays with substrate == 'PET'."),
        ("PET assays excluded (non-PET material or time-zero)", int((assays.assay_outcome == 'EXCLUDED').sum()), "PET-G / unspecified polyester material, or duration = 0."),
        ("PET assays: degradation detected", int((assays.assay_outcome == 'POS').sum()), "Any direct metric > 0 or categorical detected/positive."),
        ("PET assays: nothing detected", int((assays.assay_outcome == 'NEG').sum()), "Direct metric exactly 0 (not digitised) or categorical not_detected/negative, and no positive measurement."),
        ("PET assays: unclear", int((assays.assay_outcome == 'UNCLEAR').sum()), "Only indirect metrics, '<' values, '~0' digitised values or missing values."),
        ("Unique proteins with PET-related assays", len(pet_ids), "Unique protein_id among PET assays."),
        ("PET-tested proteins with a sequence", int(summary.has_sequence.sum()), "protein_id present in CSV."),
        ("PET-tested proteins WITHOUT a sequence (unmatched)", int((~summary.has_sequence).sum()), "; ".join(summary[~summary.has_sequence].protein_name)),
        ("PET assays belonging to unmatched proteins", len(unmatched_assays), "Assays whose protein_id is not in the CSV."),
        ("Assay proteins never tested on PET", len(all_json_ids - pet_ids), "In JSON, no PET assay; NOT treated as inactive."),
        ("Unique PET-active proteins (all evidence positive)", int(lc.get('PET-active', 0)), "POS assays only."),
        ("Unique PET-active proteins (condition-dependent)", int(lc.get('PET-active (condition-dependent)', 0)), "POS and NEG assays, but every NEG comes from a paper that also reports activity."),
        ("Unique PET-inactive proteins (tested conditions)", int(lc.get('PET-inactive (tested conditions)', 0)), "NEG assays only, no POS."),
        ("  of which high confidence", int(((summary.pet_label == 'PET-inactive (tested conditions)') & (summary.label_confidence == 'high')).sum()), ">=3 NEG assays, >=2 distinct conditions, all purified."),
        ("Proteins with unclear evidence", int(lc.get('Unclear', 0)), "No POS and no NEG assay."),
        ("Proteins with conflicting evidence (all)", int(lc.get('PET-active (condition-dependent)', 0) + lc.get('Conflicting (across studies)', 0)), "Both POS and NEG findings under different conditions (user definition)."),
        ("  of which conflicting across studies", int(lc.get('Conflicting (across studies)', 0)), "A paper reports only NEG while another paper reports POS."),
        ("Proteins with usable sequences and reliable labels", int(len(usable)), "Valid sequence + label active/cond.-dependent/inactive with high or medium confidence."),
        ("  usable active", int((usable.binary_class == 'active').sum()), ""),
        ("  usable inactive", int((usable.binary_class == 'inactive').sum()), ""),
        ("Sequences with non-standard amino acid characters", int((summary.has_sequence & ~summary.sequence_valid_aa).sum()), "Regex ^[ACDEFGHIKLMNPQRSTVWY]+$."),
        ("Exact duplicate sequences", int(sum(len(g) - 1 for g in exact_dup_groups)), "Identical sequence strings among PET-tested proteins."),
        ("Highly similar pairs >=95% identity (all PET-tested)", hi(0.95), "Semi-global BLOSUM62 alignment; identities / shorter length."),
        ("Highly similar pairs >=90% identity (all PET-tested)", hi(0.90), ""),
        ("Highly similar pairs >=70% identity (all PET-tested)", hi(0.70), ""),
        ("Proteins with a >=90% identical neighbour", int((summary.nearest_neighbour_identity >= 0.9).sum()), ""),
        ("Usable-set pairs >=90% identity", hi_usable(0.90), ""),
        ("Usable inactive proteins >=70% identical to a usable active", int((cross.max_identity_to_active >= 0.7).sum()), "Leakage / hard-negative indicator."),
        ("Independent clusters at 40% identity (active / inactive / mixed)",
         f"{ct.loc[0.4,'clusters_with_active']} / {ct.loc[0.4,'clusters_with_inactive']} / {ct.loc[0.4,'mixed_clusters']}",
         "Single-linkage clustering of usable proteins."),
        ("Independent clusters at 70% identity (active / inactive / mixed)",
         f"{ct.loc[0.7,'clusters_with_active']} / {ct.loc[0.7,'clusters_with_inactive']} / {ct.loc[0.7,'mixed_clusters']}", ""),
        ("Standardised-screen proteins (one study, same protocol)", int(len(scr_lab)), "experiment_context mentions 'Source Data Table D*'."),
        ("  screen: active / cond.-dependent / inactive",
         f"{(scr_lab.pet_label=='PET-active').sum()} / {(scr_lab.pet_label=='PET-active (condition-dependent)').sum()} / {(scr_lab.pet_label=='PET-inactive (tested conditions)').sum()}", ""),
        ("PlasticDB sequences annotated with PET", pdb_pet, "Positive associations only."),
        ("PlasticDB PET sequences not in PAZy CSV", pdb_pet_only_new, "Extra positives; no matching negatives."),
        ("PAZy proteins tested on >=2 substrates", sum(len(v) >= 2 for v in multi_sub.values()), "Basis for substrate-profile tasks."),
        ("PET-tested proteins with organism found in provided files", int((summary.organism != 'not available in provided files').sum()), "Exact sequence match to PlasticDB / degraders_list / UniProt."),
    ]
    quality = pd.DataFrame(q, columns=["metric", "value", "how_calculated"])
    quality.to_csv(OUT / "pet_dataset_quality_summary.csv", index=False)

    make_figures(subs, assays, summary, pairs, cluster_table, cross)

    # console summary
    pd.set_option("display.width", 200, "display.max_colwidth", 80)
    print(inventory[["file", "records", "unique_ids", "duplicate_sequences", "missing_values"]].to_string(index=False))
    print()
    print(subs.to_string(index=False))
    print()
    print(quality[["metric", "value"]].to_string(index=False))
    print()
    print(cluster_table.to_string(index=False))
    print()
    print(pd.crosstab(summary.pet_label, summary.label_confidence))
    print("\nOutcome reasons:\n", assays.outcome_reason.str.replace(r" \(.*", "", regex=True).value_counts().head(15).to_string())


if __name__ == "__main__":
    main()
