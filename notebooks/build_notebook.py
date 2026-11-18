"""Generate notebooks/pet_enzyme_explorer.ipynb (then execute it with nbconvert).

    .venv/bin/python notebooks/build_notebook.py
    .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/pet_enzyme_explorer.ipynb

Sections follow the eight stages of the project brief, in order.
"""

from pathlib import Path

import nbformat as nbf

REPO = "https://github.com/misskanyi/Bioinformatics-Group-Project.git"

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(f"""
# PET Enzyme Explorer — Bioinformatics and Machine-Learning Analysis

**Project:** *PET Enzyme Explorer: A Bioinformatics and Machine Learning System for Identifying and Characterising
PET-Degrading Enzymes* (Computing for Bioinformatics, year 4).

**Why it matters.** PET (polyethylene terephthalate) is the plastic of drinks bottles and polyester fibre. A small number
of enzymes, mostly bacterial and fungal cutinases, can break it back into its building blocks, which makes enzymatic
recycling possible. Testing an enzyme in the laboratory is slow and expensive, so this notebook asks how far protein
sequence analysis and machine learning can narrow down which enzymes are worth testing.

**How to run.** *Runtime → Run all* in Google Colab, or locally from the repository root. In Colab the first code cell
clones the repository ({REPO}), which contains the raw data and cached results, and installs Biopython. Expensive
steps (44,253 pairwise alignments, clustering grids, cross-validation, the candidate search) are cached in
`outputs/explorer/`. Set `RECOMPUTE = True` (or the environment variable `PET_RECOMPUTE=1`) to regenerate every
analysis output from the raw files; this takes about 1 minute on 10 CPU cores and longer on Colab's 2 cores.
Preprocessing, quality control and the exploratory plots are always computed live.

**Convention:** *experimentally established* = taken from published assay records (PAZy, the 2025 screen).
*Computational* = derived here (similarity, clusters, evidence categories, model scores).
""")

md("""
## 1. Research question, objectives and hypotheses

> **Research question.** How can protein sequence analysis and machine learning help identify promising
> PET-degrading enzyme candidates for further laboratory testing?

A feasibility analysis (`outputs/pet_dataset_feasibility_report.md`) showed that the data contain
**298 PET-active proteins with sequences but 0 usable PET-inactive ones**, so a direct "PET-active vs PET-inactive"
classifier cannot be trained. The question is therefore answered through supporting investigations:

* **Sequence analysis** (alignment, motifs, similarity to characterised enzymes): what does a promising candidate
  look like, and how close is a new sequence to an enzyme with published PET activity? (Sections 5, 7.3, 7.4)
* **Clustering** (unsupervised learning): do the verified PET hydrolases form real sequence groups, and which group
  would a candidate belong to? (Sections 5.2–5.4, 6, 7.1)
* **Assay conditions** (temperature): do those groups differ in the conditions at which activity was observed?
  (Sections 5.5–5.6)
* **Supervised learning** under one standardised protocol: can sequence features predict activity at a named
  condition well enough to rank candidates? (Section 7.2)

**Objectives**
1. **O1 — Data:** build a clean, quality-controlled set of experimentally verified PET-active enzyme sequences from
   PAZy, linked to their assay conditions and (where documented) source organisms.
2. **O2 — Sequence groups:** group the enzymes by sequence (pairwise alignment, clustering, motifs, similarity
   network), test the groups against chance, and interpret them with domain annotation and the literature.
3. **O3 — Temperature:** test whether the groups differ in the temperatures at which PET degradation was detected,
   with statistical tests and false-discovery-rate (FDR) correction, separating real differences from study design.
4. **O4 — Machine learning:** evaluate the unsupervised grouping against null baselines, and build a supervised model
   that predicts PET activity at 60 °C from sequence, compared with proper baselines.

**Hypotheses**
* **H1** — Most verified PET-active enzymes belong to a small number of sequence-similarity groups that share the
  serine-hydrolase G-x-S-x-G catalytic motif.
* **H2** — Sequence groups differ in the temperatures at which PET degradation has been detected.
* **H3** — Sequence features predict whether PET conversion is still detected at 60 °C better than baselines.
""")

md("""
**Setup.** The next cell only acts in Google Colab: it clones the public repository (branch `REPO_BRANCH`) and
installs the one package Colab lacks. Locally it does nothing. The cell after it records the library versions used,
so a reader can tell whether a different environment could explain small numerical differences.
""")

code(f"""
# Google Colab only: fetch the repository (code + raw data + cached outputs) and the one missing package.
import os, subprocess, sys
from pathlib import Path
REPO_BRANCH = "main"
if "google.colab" in sys.modules and not Path("pet_explorer").exists():
    if not Path("Bioinformatics-Group-Project").exists():
        subprocess.run(["git", "clone", "-q", "--depth", "1", "-b", REPO_BRANCH, "{REPO}"], check=True)
    os.chdir("Bioinformatics-Group-Project")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "biopython==1.85"], check=True)
print("working directory:", Path.cwd())
""")

code("""
import json, platform, warnings
warnings.filterwarnings("ignore")
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))

import numpy as np, pandas as pd, matplotlib, matplotlib.pyplot as plt, sklearn, scipy, Bio
from IPython.display import Image, display, Markdown
from pet_explorer import config as C, pipeline, shortlist
pd.set_option("display.max_colwidth", 80, "display.width", 200)

print("python", platform.python_version(), "| numpy", np.__version__, "| pandas", pd.__version__,
      "| scikit-learn", sklearn.__version__, "| scipy", scipy.__version__, "| matplotlib", matplotlib.__version__,
      "| biopython", Bio.__version__)
print("versions used to produce the cached outputs: see requirements.txt")

RECOMPUTE = os.environ.get("PET_RECOMPUTE") == "1"   # True = rebuild every cached output from data/
if RECOMPUTE or not (C.PREDICTION / "model_comparison.csv").exists():
    C.ensure_dirs(); pipeline.stage1(); pipeline.stage2()
    from pet_explorer import temperature, organisms
    temperature.run(); organisms.run(); pipeline.export_network(); pipeline.stage5()
if RECOMPUTE or not shortlist.F_SHORTLIST.exists():
    shortlist.run()
fig = lambda name, w=700: display(Image(filename=str(C.FIGURES / name), width=w))   # show a pipeline figure


def show(f):
    # Render a figure drawn in this notebook as PNG (works whatever matplotlib backend is active).
    import io
    buf = io.BytesIO()
    f.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(f)
    display(Image(data=buf.getvalue()))


print("RECOMPUTE =", RECOMPUTE, "| outputs in", C.EXPLORER.relative_to(ROOT))
""")

md("""
## 2. Data acquisition and provenance

All raw files were downloaded by the project team into `data/` and are **never modified**. Six core files feed the
reference set and the analyses in Sections 3–7.3:

| Source | File | Role here |
|---|---|---|
| PAZy (Plastics-Active enZymes database, pazy.eu) | `pazy_proteins_sequences.csv`, `pazy_proteins.fasta` | Protein sequences (301) |
| PAZy | `pazy_polymer_assays.json.gz` (schema 4.2) | Experimental assays (7,195; 5,058 on PET), including the two standardised screens |
| PlasticDB (plasticdb.org) | `PlasticDB.fasta`, `degraders_list.tsv` | Organism links, Tax IDs, isolation data; annotation-only candidate sequences (Section 7.4) |
| UniProt (downloaded 2026-10-27, from file name) | `uniprotkb_…fasta.gz` | Reference cutinases (3) |
| UniParc (rest.uniprot.org, queried by sequence checksum) | cached in `outputs/explorer/annotation/` | Pfam / InterPro domains (Section 6) |

Further sources were used by the dataset curation step (`python -m pet_explorer.curation`, report in
`outputs/curation/curation_report.md`), which built the candidate registry used in Section 7.4 and the labelled
dataset summarised in Section 7.2:

| Source | File(s) | Role |
|---|---|---|
| ACS Catalysis 2025 standardised screen, supplementary data (DOI 10.1021/acscatal.5c03460) | `cs5c03460_si_002.xlsx` | 477 library sequences, 3,856 assay rows; condition-specific labels |
| PETML study workbooks and variant library | 33 `*.xlsx` workbooks, `sequences.fasta` (501 sequences) | Literature activity tables without units: provenance only, never labels |
| Bulk-analysis demo files | `data/samples/*.csv` | Three small CSVs for the web app (two include unrelated or synthetic control sequences) |

Download dates of the non-UniProt files were not recorded. Licences and versions should be noted from the source websites.

**Data dictionary — variables used from each file**

| File | Variable | Meaning |
|---|---|---|
| `pazy_proteins_sequences.csv` | `protein_id` | PAZy integer ID; key shared by CSV, FASTA and JSON |
| | `protein_name` | Enzyme name used in the literature (e.g. ISPETase, LCC) |
| | `amino_acid_sequence` | Protein sequence, one-letter code |
| `pazy_proteins.fasta` | header / sequence | `protein_id` / the same sequence as the CSV (301/301 identical, checked) |
| `pazy_polymer_assays.json.gz` | `protein_id`, `literature_doi` | One entry = one protein in one publication |
| | `assays[].substrate` | Plastic tested: PET, PA, PLA, PHA, PBS, PEF, PUR, PBAT, NR, PC (only PET used) |
| | `assays[].material` | Reported name, form (film, powder…), crystallinity, pre-treatment |
| | `assays[].conditions` | `temperature_c`, `ph`, `duration_value/unit`, enzyme preparation, concentration, amount |
| | `assays[].detection_methods` | e.g. HPLC, UV absorbance |
| | `assays[].measurements[]` | `metric_type`, `analyte`, `value`, `unit`, `qualifier` (`~` read off a figure, `<`, `>`), `categorical_result` |
| `PlasticDB.fasta` | header | `id|enzyme|organism|plastics|GenBank` |
| `degraders_list.tsv` | `Microorganism`, `Tax ID`, `Plastic`, `Enzyme`, `Sequence`, `GenbankID` | Organism–plastic reports; 527 rows carry an enzyme sequence |
| | `Isolation environment`, `Isolation sample type`, `Thermophilic conditions`, `DOI` | Isolation metadata and source paper |
| `uniprotkb_…fasta.gz` | header / sequence | UniProt accession, organism / sequence (E9LVH8, E9LVH9, Q47RJ6) |

The JSON has **no "active / inactive" field**: activity must be worked out from the measurements (Section 3).
PAZy has **no organism field**; organisms come from exact sequence matches to PlasticDB / UniProt (Section 6.4).
""")
code("""
import gzip
from Bio import SeqIO

csv = pd.read_csv(C.F_CSV)
with gzip.open(C.F_ASSAYS, "rt") as fh:
    assay_json = json.load(fh)
degraders = pd.read_csv(C.F_DEGRADERS, sep="\\t")
pazy_fa = list(SeqIO.parse(C.DATA / "pazy_proteins.fasta", "fasta"))
plasticdb = list(SeqIO.parse(C.F_PLASTICDB, "fasta"))
with gzip.open(C.F_UNIPROT, "rt") as fh:
    uniprot = list(SeqIO.parse(fh, "fasta"))

n_assays = sum(len(r["assays"]) for r in assay_json)
n_pet = sum(a["substrate"] == "PET" for r in assay_json for a in r["assays"])
print(f"pazy_proteins_sequences.csv : {csv.shape[0]} rows x {csv.shape[1]} columns {list(csv.columns)}")
print(f"pazy_proteins.fasta         : {len(pazy_fa)} sequences")
print(f"pazy_polymer_assays.json.gz : {len(assay_json)} protein x paper records, {n_assays:,} assays ({n_pet:,} on PET)")
print(f"PlasticDB.fasta             : {len(plasticdb)} sequences, e.g. {plasticdb[0].id}")
print(f"degraders_list.tsv          : {degraders.shape[0]:,} rows, {degraders.Microorganism.nunique()} organisms")
print(f"uniprot fasta               : {[r.id for r in uniprot]}")
print("\\nExample PET assay (first record):")
a = next(a for r in assay_json for a in r["assays"] if a["substrate"] == "PET")
print(json.dumps({k: a[k] for k in ["substrate", "conditions"]}, indent=1)[:600])
""")
code("""
pd.read_csv(C.FEASIBILITY / "tables/dataset_inventory.csv")[["file", "format", "records", "unique_ids", "duplicate_sequences", "notes"]]
""")
code("""
# Everything in data/ (checked live, so nothing hidden is relied on)
files = sorted(p for p in C.DATA.rglob("*") if p.is_file() and not p.name.startswith("."))
inv = pd.DataFrame({"file": [str(p.relative_to(C.DATA)) for p in files],
                    "size_kb": [round(p.stat().st_size / 1024, 1) for p in files]})
inv["group"] = np.select([inv.file.str.startswith("samples/"), inv.file.str.contains(r" et al", regex=True)],
                         ["web-app demo", "PETML study workbook"], "core / screen / registry source")
print(len(inv), "files in data/")
inv.groupby("group").agg(files=("file", "size"), total_kb=("size_kb", "sum"))
""")
md("""
**Interpretation.** The core PAZy files are internally consistent (CSV and FASTA identical, one key for sequences
and assays). Two facts shape everything that follows: PAZy has **no "active / inactive" field**, so activity has to be
derived from measurements, and the PlasticDB files contain **positive reports only**, so they can supply candidates
and organisms but never negatives.
""")

md("""
## 3. Pre-processing and quality control

Activity labels come from the feasibility analysis (`analyze_pet_dataset.py`). Each PET assay is classified from its
measurements:
* **degradation detected** — a direct breakdown metric > 0 (products released, conversion, mass loss…)
* **nothing detected** — a direct metric exactly 0, with no positive measurement in the same assay
* **unclear** — indirect evidence only, or values read as "≈ 0" off a figure
* **excluded** — PET-G / unspecified material, or time-zero samples

Assay results are aggregated per protein. We keep the proteins that are **PET-active (high/medium confidence) and have a
valid sequence**. Every sequence is re-checked against the raw CSV.

The next two cells **run** these steps on the raw JSON (about 2 s) rather than loading their results, and check that
the live result is identical to the cached clean set used by the rest of the notebook.
""")
code("""
import analyze_pet_dataset as feas            # assay classification and protein labelling (no files written here)
from pet_explorer import preprocess

assays = feas.build_assay_table(assay_json)   # one row per PET assay, classified from its measurements
labels = feas.label_proteins(assays)          # one evidence label per protein
print(f"{len(assays):,} PET assays classified:")
display(assays.assay_outcome.value_counts().rename("assays").to_frame())
display(labels.groupby(["pet_label", "label_confidence"]).size().rename("proteins").to_frame())
""")
code("""
clean, qc = preprocess.build_clean_set()      # selection + six QC checks against the raw CSV
display(qc)
proteins = pd.read_csv(C.F_PROTEINS)          # cached clean set used by later sections
assert qc.passed.all(), "QC failed"
assert clean.protein_id.tolist() == proteins.protein_id.tolist() and clean.sequence.tolist() == proteins.sequence.tolist()
live = labels.set_index("protein_id").loc[proteins.protein_id]
assert (live.pet_label.values == proteins.pet_label.values).all(), "live labels differ from the cached clean set"
print(f"Before: {len(csv)} sequences in PAZy  ->  after: {len(proteins)} PET-active proteins with valid sequences "
      "(live run identical to the cached set)")
proteins.pet_label.value_counts()
""")
md("""
**Interpretation and suspicious points.**
* **301 → 298 proteins.** Removed: TfCut1 (active in one study, inactive in another) and Tha_Cut1 and E4 (only
  indirect evidence: surface changes, turbidity). No sequence was altered.
* **Biology that must hold, checked:** all sequences use only the 20 standard amino acids; there are no duplicates;
  lengths (178–491 aa) fit single-domain α/β-hydrolases, with some longer multi-domain proteins (explained in Section 6).
* **Suspicious, and handled:** 3,198 PET measurements are exactly 0. Many are time-zero samples or conditions under which
  an otherwise active enzyme did nothing, so **a zero does not make a protein inactive**. 7 "PET" assays actually used
  PET-G or an unnamed polyester and were excluded.
* **No negatives.** Only 4 proteins were tested and never active, and none has a sequence. This rules out a PET-active
  vs PET-inactive classifier and shapes the whole project.
""")

md("""
## 4. Exploratory data analysis

Sequence features are computed live with Biopython's ProtParam (amino-acid composition, length, isoelectric point,
hydropathy (GRAVY), aromaticity, instability index, secondary-structure propensities) and the G-x-S-x-G motif search.
The three plots below are drawn here from those features.
""")
code("""
from pet_explorer import features
feats = features.feature_table(proteins)                       # computed now, ~1 s
cached = pd.read_csv(C.CLUSTERING / "sequence_features.csv")
num = feats.select_dtypes("number").columns
assert np.allclose(feats[num].to_numpy(), cached[num].to_numpy(), atol=1e-6), "features differ from the cached table"
display(feats[["length", "isoelectric_point", "gravy", "aromaticity", "instability_index"]].describe().round(2))
""")
code("""
# EDA plot 1: sequence length distribution
f, ax = plt.subplots(figsize=(7, 3.4))
ax.hist(feats.length, bins=np.arange(170, 500, 10), color="#2a78d6", edgecolor="white")
ax.axvline(feats.length.median(), color="#52514e", ls="--", lw=1)
ax.set_xlabel("sequence length (amino acids)"); ax.set_ylabel("proteins")
ax.set_title(f"Length of the {len(feats)} verified PET-active enzymes (median {feats.length.median():.0f} aa)", loc="left")
show(f)
print("range", feats.length.min(), "-", feats.length.max(), "aa; proteins > 400 aa:", int((feats.length > 400).sum()))
""")
code("""
# EDA plot 2: mean amino-acid composition (bars) and its spread between proteins (error bars = 1 sd)
aa = [c for c in feats.columns if c.startswith("aa_")]
comp = feats[aa].agg(["mean", "std"]).T.sort_values("mean", ascending=False)
f, ax = plt.subplots(figsize=(8, 3.4))
ax.bar([c[3:] for c in comp.index], comp["mean"], yerr=comp["std"], color="#1baf7a", capsize=2)
ax.set_ylabel("% of residues"); ax.set_title("Amino-acid composition across the 298 enzymes", loc="left")
show(f)
print("most frequent:", ", ".join(f"{c[3:]} {v:.1f}%" for c, v in comp["mean"].head(3).items()),
      "| median coefficient of variation across residues:", round(float((comp["std"] / comp["mean"]).median()), 2))
""")
md("""
**Interpretation.** Lengths range from 178 to 491 aa (median 297). This is consistent with single-domain α/β-hydrolases,
though several proteins are around 400–490 aa (explained by extra binding domains in Section 6.1). Alanine (11.0%) and
glycine (9.8%) are the most frequent residues on average. Composition varies little between proteins, which already
suggests composition alone will separate families poorly (confirmed in Section 5.2) and is a first warning for the
composition-based supervised model in Section 7.2.
""")

md("""
### 4.1 Conserved motif

Serine hydrolases (lipases, esterases, cutinases) usually carry their catalytic serine in a **G-x-S-x-G** pentapeptide.
We search for it in every sequence (a hypothesis-driven check, not an assumption).
""")
code("""
# EDA plot 3: which G-x-S-x-G variants occur, and in how many proteins
print("Proteins with >=1 G-x-S-x-G:", int((feats.gxsxg_count > 0).sum()), "/", len(feats))
variants = (feats.gxsxg_variants.fillna("").str.split("; ").explode().loc[lambda s: s != ""]
            .value_counts().head(12))
f, ax = plt.subplots(figsize=(7, 3.6))
ax.barh(variants.index[::-1], variants.values[::-1], color="#eb6834")
ax.set_xlabel("proteins carrying the variant"); ax.set_title("Most common G-x-S-x-G catalytic-motif variants", loc="left")
show(f)
""")
md("""
**Interpretation.** 296 of 298 proteins carry the motif, so almost every verified PET degrader is a serine hydrolase.
The most frequent variants are G-H-S-M-G and G-W-S-M-G; the residue before the serine is examined in Section 5.4.
""")

md("### 4.2 The experimental data: where PET assays were run")
code("""
fig("t01_tested_temperatures.png"); fig("t02_activity_by_temperature.png")
""")
md("""
**Interpretation.** Assay temperatures cluster at a few round values (30, 40, 50, 60, 70 °C), not on a continuous
scale. The share of assays with detected degradation is lowest at 40–49 °C (63%) and 60–69 °C (54%), the bins used
by the large screening studies that test many weak enzymes at once, and high at 70–79 °C (87%), probably because
only enzymes expected to be thermostable are tested that hot. This uneven design is important for H2: different
groups of enzymes were tested at different temperatures, for different reasons.
""")

md("""
## 5. Core analysis

### 5.1 Pairwise sequence similarity

All 44,253 protein pairs were aligned (Smith-Waterman, BLOSUM62, gap −11/−1). For each pair we store:
* identity over aligned columns
* coverage of each protein
* **identity relative to the shorter sequence**. This is coverage-aware: a short shared fragment cannot look like
  high identity. Clustering uses distance = 1 − this value.
""")
code("""
pairs = pd.read_csv(C.F_PAIRS)
display(pairs[["identity", "identity_shorter", "min_coverage", "normalised_score"]].describe().round(3))
fig("f07_identity_heatmap.png", 600)
""")
md("""
**Interpretation.** The heatmap shows one very large block of moderately similar proteins (≈40–60% identity), containing
smaller, near-identical blocks (variants of the same enzyme). It also shows a few proteins that resemble almost nothing
else. This shape is why the clustering method matters.
""")

md("""
### 5.2 Grouping the enzymes: clustering (unsupervised machine learning)

Three method families were compared on the same 298 proteins:
1. **Hierarchical clustering** (average linkage) on alignment distance, 2–80 clusters
2. **K-means** on standardised alignment-free features (20 amino-acid percentages, length, pI, GRAVY, aromaticity,
   instability, secondary-structure propensities), k = 2–30
3. **DBSCAN** on alignment distance, ε = 0.3–0.7

Each configuration was scored on the same criteria:
* silhouette on alignment distance (do groups reflect homology?)
* silhouette in feature space
* **stability**: mean adjusted Rand index (ARI) against 30 random 80% subsamples
* mean within-cluster identity
* largest-cluster share, singletons and noise

**Selection rule (fixed before inspecting cluster contents):**
* stability ≥ 0.9
* ≤ 5% unassigned
* mean within-cluster identity ≥ 40%
* then the highest alignment silhouette; ties within 0.01 go to the most stable configuration

Whether the selected clusters beat chance is tested in Section 7.1.
""")
code("""
comp = pd.read_csv(C.CLUSTERING / "method_comparison.csv")
sel = json.loads((C.CLUSTERING / "clustering_selection.json").read_text())
display(comp.sort_values("silhouette_alignment", ascending=False).groupby("method").head(3))
display(Markdown(f"**Selected:** `{sel['final_method']}` with {int(sel['final_parameter'])} clusters; "
                 f"ARI vs k-means (same k) = {sel['ari_final_vs_kmeans_same_k']}, vs DBSCAN ε=0.5 = {sel['ari_final_vs_dbscan_eps0.5']}, "
                 f"vs 70%-identity groups = {sel['ari_final_vs_identity_group_70']} ({sel['n_identity_groups_70']} groups)."))
fig("f04_clustering_method_comparison.png", 900)
""")
md("""
**Evaluation.**
* **Hierarchical clustering on alignment distance wins clearly.** Its best silhouette is about 0.34, it is highly
  stable, and the 7-cluster solution reproduces almost perfectly on subsamples.
* **K-means on composition/physicochemical features scores poorly** (silhouette ≈ 0.07–0.11 on alignment distance)
  and is unstable. It barely agrees with the homology clusters (ARI ≈ 0.08). Alignment-free composition features do
  not capture evolutionary relationships between these enzymes.
* **DBSCAN gets a high silhouette at ε = 0.7 only by labelling 25 proteins as noise**, which breaks the "assign
  every protein" requirement.
* **The 110 groups at 70% identity are not good ML clusters** (ARI ≈ 0.05 with the selected solution). They describe
  near-duplicates, which matters for data leakage (used in Section 7.2), not family structure.
* **A silhouette of about 0.34 means moderate, not strong, structure.**
""")
code("""
summ = pd.read_csv(C.CLUSTERING / "cluster_summary.csv")
display(summ)
fig("f06_mds_alignment.png"); fig("f05_pca_features.png"); fig("f08_cluster_sizes.png", 600)
""")
md("""
**Interpretation.** On the alignment map (MDS) the groups separate cleanly; on the composition PCA they overlap almost
completely. Sequence *homology*, not overall amino-acid make-up, is what distinguishes these enzymes.
""")

md("""
### 5.3 Second level: structure inside G1

G1 holds 263 of 298 proteins. Average linkage only ever peels single outliers off it, but the MDS map shows two
clouds. We therefore compared four algorithms inside G1:
* average-linkage hierarchical clustering
* complete-linkage hierarchical clustering
* spectral clustering on the similarity matrix
* k-means on MDS coordinates

A split was accepted only if it was stable (ARI ≥ 0.95) and no subgroup held more than 90% of the members.
""")
code("""
sub = pd.read_csv(C.CLUSTERING / "g1_subgroup_comparison.csv")
display(sub.sort_values(["stability_ari_mean", "silhouette_alignment"], ascending=False).head(8))
print("Selected:", sel["g1_subgroup_selected"])
""")
md("""
**Interpretation.**
* **G1 divides perfectly reproducibly** into **G1a (165)** and **G1b (98)**, with ARI 1.0.
* **The separation is weak** (silhouette ≈ 0.16, below the 0.25 usually taken as "substantial structure").
  G1 is best seen as one lineage with a continuum of variants.
* **G1b is distinctive but narrowly sampled.** Its proteins are longer (median 412 aa), more similar to each other
  (mean 60% identity) and share 12 group-specific 5-mers. But they come from only three publications, mostly two
  large screening studies, so G1b may partly reflect *what was sampled*.
""")

md("""
### 5.4 Motifs and cluster-specific sequence segments

We searched for 5-mers present in ≥ 80% of a group and ≤ 20% of all other proteins.
""")
code("""
assign = pd.read_csv(C.CLUSTERING / "cluster_assignments.csv")
d = proteins.merge(assign[["protein_id", "cluster", "subcluster"]], on="protein_id")
for k in ["SMGGG", "GHSMG", "GWSMG", "GYSQG"]:
    has = d.sequence.str.contains(k)
    print(f"{k}: G1 {100*has[d.cluster=='G1'].mean():.1f}%  outside G1 {100*has[d.cluster!='G1'].mean():.1f}%  by group {d[has].subcluster.value_counts().to_dict()}")
display(pd.read_csv(C.CLUSTERING / "cluster_specific_kmers.csv"))
""")
md("""
**Interpretation (H1).**
* **296 of 298 proteins carry G-x-S-x-G**, and 263 of them form G1.
* **G1 is defined by an extended form of the motif.** The 5-mer SMGGG (as in G-H-S-M-G-G-G) occurs in 93% of G1
  and about 3% of other proteins.
* **G1a and G1b differ at the residue before the catalytic serine.** GWSMG (Trp) occurs only in G1a (42 proteins),
  while every G1b protein has GHSMG (His).
* **G3 is a small, coherent group with its own motif:** GYSQG, in all 9 members, which are about 228 aa long.

**H1 is supported:** most verified PET hydrolases belong to one motif-sharing sequence lineage.
""")

md("""
### 5.5 Temperature analysis

We built a structured temperature dataset with one row per PET assay (temperature, pH, material, detection method,
outcome, DOI, cluster) and one row per measurement. Rules:
* The highest tested temperature is **not** the optimum.
* A *best tested temperature* is reported only inside a **comparable series**: same paper, metric, unit, pH,
  duration, material, enzyme loading and experiment context, with ≥ 3 temperatures.
""")
code("""
ts = pd.read_csv(C.TEMPERATURE / "protein_temperature_summary.csv")
display(ts.optimum_status_category.value_counts())
series = pd.read_csv(C.TEMPERATURE / "comparable_temperature_series.csv")
print(len(series), "comparable series; best value at an edge of the tested range in",
      int((series.best_at_edge != "interior").sum()))
display(pd.read_csv(C.TEMPERATURE / "active_temperature_by_cluster.csv"))
fig("t03_active_temperature_by_cluster.png")
""")
md("""
**Interpretation.**
* **Two-thirds of proteins cannot have an optimum determined.** 115 proteins were tested at one temperature
  and 89 at only two.
* **Many series peak at the edge of their tested range**, so the true optimum may lie outside it.
* **Groups appear to differ** (e.g. G1a median 50 °C vs G1b 40 °C per protein × temperature). But 89% of G1b assays
  were run at exactly 40 °C or 60 °C, mostly in one screening study (DOI 10.1021/acscatal.5c03460).

Valid cross-protein comparisons exist only inside the two standardised screens, where one protocol was used for many
proteins:
""")
code("""
fig("t04_standardised_screen_d3.png", 550); fig("t05_standardised_screen_40_vs_60.png", 600)
""")
md("""
In the 25-protein screen (DOI 10.1038/s41467-022-35237-x, Source Data Table D3), several enzymes give their highest
product release at 50–60 °C. Values of 500 mg/L hit the assay ceiling (">500"). In the 99-protein screen
(DOI 10.1021/acscatal.5c03460), most proteins converted more PET at 40 °C than at 60 °C under that protocol.
""")

md("""
### 5.6 Statistical tests for H2 (with FDR correction)

All tests are non-parametric (temperatures and conversions are not normally distributed), and all p-values are
corrected together with the **Benjamini–Hochberg** procedure (q-value < 0.05 = significant).
* **A. Naive test, all PAZy assays:** one value per protein (its median temperature with detected activity; assays of
  one protein are not independent). Kruskal–Wallis across groups with ≥ 5 proteins, then pairwise Mann–Whitney U.
* **B. Controlled test, 99-protein standardised screen:** every protein measured with one protocol at 40 and 60 °C.
  Wilcoxon signed-rank (40 vs 60 °C, paired), Mann–Whitney U (G1a vs G1b at each temperature) and Fisher's exact
  test (conversion detected at 60 °C, G1a vs G1b). G1a and G1b are the only groups in this screen.
""")
code("""
tests = pd.read_csv(C.TEMPERATURE / "statistical_tests.csv")
tests
""")
md("""
**Interpretation (H2).**
* **The naive test says the groups differ** (Kruskal–Wallis q ≈ 0.0005). G2 (heterogeneous α/β-hydrolases) is active at
  higher temperatures (median 60 °C) than G1a and G1b, and G1a tends to be tested warmer than G1b (mean 42.9 vs 37.3 °C,
  q ≈ 0.001).
* **The controlled test does not confirm it for G1a vs G1b.** Under one protocol, the two subgroups convert the same
  amount of PET at 40 °C (q ≈ 0.97). At 60 °C G1a is slightly ahead (median 0.19% vs 0.00%, p = 0.044), but this does
  **not survive FDR correction** (q ≈ 0.08), and the share with detectable conversion at 60 °C does not differ
  (17/27 vs 22/51, q ≈ 0.21).
* **Temperature itself matters strongly:** in that screen conversion drops sharply from 40 to 60 °C (median 0.67% →
  0.04%, q < 10⁻⁹).
* **Conclusion: H2 is not confirmed.** The naive group difference is largely explained by *which studies tested which
  enzymes at which temperatures*. The G2 difference cannot be checked under controlled conditions with these data.
""")

md("""
## 6. Biological interpretation

### 6.1 Domain annotation (Pfam via UniParc / InterPro)

Every sequence was looked up in **UniParc**, UniProt's archive of all unique protein sequences, by the MD5 checksum of
its exact sequence. UniParc stores InterPro's pre-computed **Pfam** matches. Sequences absent from UniParc (e.g.
unpublished or engineered variants) are reported as such, not guessed. Results are cached in
`outputs/explorer/annotation/`.
""")
code("""
dom = pd.read_csv(C.ANNOTATION / "uniparc_domain_matches.csv")
print("Sequences found in UniParc:", dom.loc[dom.uniparc_id.notna(), "protein_id"].nunique(), "/", len(proteins))
pd.read_csv(C.ANNOTATION / "domains_by_group.csv")
""")
md("""
**Interpretation.** The domains give the groups biological names:
* **G1 (G1a + G1b) = the "PET hydrolase/cutinase-like" family (Pfam PF12740)**, in every annotated G1 protein. This is
  the family of the bacterial PETases and thermophilic actinomycete cutinases.
* **G1b proteins are multi-domain.** 32 of the 50 annotated G1b proteins also carry a **Ricin-B lectin domain
  (PF00652)**, and others a **carbohydrate-binding module (PF00553, PF03422)**. These extra binding domains explain why
  G1b proteins are longer (median 412 aa) and are a real biological difference, not only a sampling effect.
* **G3 = fungal cutinases (PF01083, Cutinase/acetylxylan esterase)**, consistent with its GYSQG motif.
* **G4 = carboxylesterases type B (PF00135)**, a different α/β-hydrolase family.
* **G2 and G5 are mixed α/β-hydrolases** (lipases, esterases, peptidase S9-like), confirming they are remainder groups,
  not families.
""")

md("""
### 6.2 Comparison with the literature

Well-studied PET hydrolases located in our groups, with their published properties:
""")
code("""
lit = pd.read_csv(C.ANNOTATION / "literature_comparison.csv")
with pd.option_context("display.max_colwidth", 200):
    display(lit)
""")
md("""
**Interpretation.**
* **The landmark bacterial PET hydrolases all fall in G1a**: IsPETase, LCC, TfCut2, TfH, Cut190, Tcur_1278, BhrPETase,
  PE-H and PET2. G1a is the core PETase/cutinase family described in the literature.
* **Our motif split matches a known structural difference.** IsPETase and PE-H, described as "type II" PETases
  (Joo et al. 2018), carry **GWSMG**; LCC and TfCut2, "type I" thermophilic cutinases, carry **GHSMG**. Austin et al.
  (2018) showed that changing this Trp to His (W159H) makes the IsPETase active site more cutinase-like. Our
  data-driven motif analysis therefore recovers a published structural distinction.
* **HiC, a fungal cutinase, sits in G3** with the fungal-cutinase Pfam domain: PET degradation evolved, or was found,
  in more than one hydrolase family.
""")

md("""
### 6.3 Sequence-similarity network (NetworkX, exported for Cytoscape)

Nodes are proteins. An **edge** joins two proteins whose local alignment has **≥ 40% identity and covers ≥ 70% of both
sequences**. The threshold is defensible for two reasons:
* 40% identity over most of two ~300-aa proteins is well above the 25–35% "twilight zone" (Rost 1999), so edges indicate
  probable homology.
* The coverage rule stops short shared segments, such as signal peptides, from linking unrelated proteins.

This is a **sequence-similarity network, not a protein–protein interaction network**: these enzymes are secreted and
act on plastic, so physical interaction partners (e.g. STRING) are not meaningful for most of them.
""")
code("""
display(pd.read_csv(C.NETWORK / "edge_threshold_sensitivity.csv").query("min_coverage == 0.7"))
nodes, edges = pd.read_csv(C.NETWORK / "ssn_nodes.csv"), pd.read_csv(C.NETWORK / "ssn_edges.csv")
print(len(nodes), "nodes,", len(edges), "edges. Files: outputs/explorer/network/ssn_nodes.csv, ssn_edges.csv")
fig("f11_similarity_network.png", 750)
""")
code("""
cent = pd.read_csv(C.NETWORK / "centrality.csv")
print("Most connected proteins (hubs):")
display(cent.head(8))
print("Strongest bridges (betweenness):")
display(cent.sort_values("betweenness", ascending=False).head(5))
cent.groupby("subcluster")[["degree", "betweenness"]].median()
""")
md("""
**Interpretation.**
* **One giant component** (239 proteins) holds almost all of G1; 30 proteins have no close relative at this threshold.
* **Hubs are G1 members similar to ~150–200 others**; well-known enzymes such as TfH and LCC are among them, so they
  are good representatives of the family.
* **The main bridges are G1b proteins (e.g. ESM121, ESM139)** that link the G1b cluster to the G1a core: G1a and G1b
  are connected sub-families of one lineage, matching the weak silhouette in 5.3.
* G3, G4 and the small groups form separate islands, consistent with their different Pfam families.

Import into Cytoscape:
1. **File → Import → Network from File** → `ssn_edges.csv` (source/target columns).
2. **File → Import → Table from File** → `ssn_nodes.csv` (key column `id`).
3. Colour nodes by `cluster`/`organism` and set edge width by `identity`.
""")

md("""
### 6.4 Source organisms

Organisms come only from the provided files:
* **Exact sequence matches** (PlasticDB, degraders_list, UniProt)
* **Containment matches**: the PAZy sequence lies inside a database record or vice versa. Every such match covers
  ≥ 81% of the longer sequence, i.e. a precursor vs mature form.
* **PAZy curation text** ("cutinase from *Genus species*")

Expression hosts and organisms of *similar* sequences are never used. Unknown cases are reported as
"Unknown — insufficient evidence".
""")
code("""
org = pd.read_csv(C.ORGANISMS / "protein_organisms.csv")
display(pd.read_csv(C.ORGANISMS / "organism_evidence_summary.csv"))
print("Tax ID available:", int(org.taxonomy_id.notna().sum()), "| databases disagree:", int(org.sources_disagree.sum()),
      "| uncultured/metagenomic:", int(org.uncultured_or_metagenomic.sum()))
display(org[org.sources_disagree][["protein_name", "organism", "evidence_detail"]])
org.organism.str.split("; ").explode().value_counts().head(12)
""")
md("""
**Interpretation.**
* **Organism coverage:** 159 of 298 proteins (53%) have an organism with sequence-level evidence. 139 remain unknown
  from these files.
* **Database disagreements:** some records conflict, e.g. PET5 has identical sequences filed under *Moraxella* sp.
  and *Oleispira antarctica*. Both are shown and flagged; neither is picked.
* **No isolate:** 19 proteins come from uncultured / metagenomic sources.
""")

md("""
## 7. Machine learning

Two models, each judged against baselines rather than on its own:
* **7.1** the unsupervised clustering of Section 5.2 against two **null models**;
* **7.2** a **supervised classifier** that predicts PET activity at 60 °C (H3);
* **7.3** the nearest-neighbour **sequence matcher** behind the dashboard, validated by leave-one-out;
* **7.4** the candidate **shortlist** for laboratory testing, built from the matcher's evidence rules (not from 7.2).

Clustering (7.1) describes structure *among known PET degraders*; it does not predict activity. Only 7.2 attempts
activity prediction, and only 7.4 ranks untested sequences.

### 7.1 Are the clusters better than chance?

200 draws from each null model, scored with the same metrics as the real clustering:
* **random labels, same cluster sizes** — could *any* grouping of these sizes score as well?
* **average linkage on shuffled distances** — the same algorithm on a distance matrix whose values are shuffled between
  pairs (same distribution, homology destroyed).
""")
code("""
pd.read_csv(C.CLUSTERING / "null_baseline.csv")
""")
md("""
**Interpretation.** The real clustering (silhouette 0.34, within-cluster identity 44%) is far outside both null
distributions: random groupings reach a silhouette of at most −0.02, and clustering shuffled distances at most 0.03.
Empirical p = 0.005, the smallest possible with 200 draws. **The groups are real structure, not an artefact of the
method** — supporting H1.
""")

md("""
### 7.2 Supervised model: is PET conversion still detected at 60 °C?

**Target.** In the 99-protein standardised screen, 78 proteins were also measured at 60 °C; conversion was detected
for 39 and not for 39 — a balanced binary target under one protocol. 60 °C is just below PET's glass transition
(~65–70 °C), where the polymer becomes easier to attack, so activity there matters for recycling.

**Features.** The 28 composition + physicochemical features of Section 5.2, or alignment identity.

**Leakage control.** The screen holds near-identical variants, so cross-validation folds are **grouped by 70%-identity
group**: no test protein has a ≥ 70%-identical relative in its training fold.

**Protocol.** 20 repeats of 5-fold stratified group cross-validation; ROC AUC and balanced accuracy per fold.

| Baselines | Models |
|---|---|
| majority class; random scores; **cluster label only** (G1a/G1b detection rate) | logistic regression; random forest; similarity-weighted 5-nearest-neighbours on alignment identity |
""")
code("""
display(pd.read_csv(C.PREDICTION / "model_comparison.csv"))
fig("f10_prediction_models.png", 900)
display(pd.read_csv(C.PREDICTION / "permutation_test.csv"))
""")
code("""
print("Top features (fitted on all 78 proteins; descriptive only, since the model is near chance):")
pd.read_csv(C.PREDICTION / "feature_importance.csv").head(8)
""")
md("""
**Interpretation (H3).**
* **No model clearly beats the baselines.** The best models reach ROC AUC ≈ 0.56 (sd ≈ 0.09), against 0.50 for the
  majority class and 0.53 for "cluster label only".
* **The permutation test confirms this:** with shuffled labels the same model averages 0.49, and 0.556 lies well
  inside the null distribution (95th percentile 0.69, p ≈ 0.32).
* **Homology does not help either** (5-NN on alignment identity, AUC ≈ 0.52): close relatives do not share
  60 °C activity more than chance once near-duplicates are kept out of the training fold.
* **H3 is not supported.** With 78 proteins and simple sequence features, activity at 60 °C cannot be predicted.
  Thermostability depends on specific residues, disulfide bonds and calcium binding sites, which global composition
  features do not capture. This is an honest negative result, not a failed analysis.
""")

md("""
#### 7.2.1 A closer look at the same validation run

Everything below comes from the **held-out (out-of-fold) predictions of the same 20 × grouped 5-fold
cross-validation** that produced the table above: no model was retrained, no training-set predictions are used, and
no other validation run is mixed in. A test fold that happens to contain only one class is skipped, because ROC AUC
is undefined there; the number of skipped folds is reported.

* **Per-fold results:** one ROC AUC per held-out fold, to show how much a single split can mislead.
* **ROC curves:** out-of-fold scores of each repeat pooled into one curve (thin lines), and their mean (bold).
* **Confusion matrix, precision, recall, F1:** at the same 0.5 cut-off used for balanced accuracy.
* **Permutation histogram:** the 200 ROC AUCs obtained with shuffled labels, against the observed value.
""")
code("""
folds = pd.read_csv(C.PREDICTION / "cv_fold_metrics.csv")
ok = folds[~folds.skipped_single_class]
first = folds[folds.model == folds.model.iloc[0]]
print(f"{len(first)} folds per model; {int(first.skipped_single_class.sum())} skipped (one class only); "
      f"held-out fold size {first.n_test.min()}-{first.n_test.max()} proteins")
display(ok.groupby("model", sort=False).roc_auc.describe()[["count", "mean", "std", "min", "max"]].round(3))
fig("f15_cv_folds.png", 850)
""")
code("""
fig("f12_roc_curves.png", 900)
display(pd.read_csv(C.PREDICTION / "threshold_metrics.csv")[
    ["model", "kind", "precision_mean", "precision_sd", "recall_mean", "recall_sd", "f1_mean", "f1_sd",
     "tp_per_repeat", "fp_per_repeat", "tn_per_repeat", "fn_per_repeat"]])
fig("f13_confusion_matrices.png", 900)
""")
code("""
null = pd.read_csv(C.PREDICTION / "permutation_null.csv").null_roc_auc
perm = pd.read_csv(C.PREDICTION / "permutation_test.csv").iloc[0]
print(f"observed ROC AUC {perm.observed_roc_auc}; shuffled-label AUCs >= observed: {(null >= perm.observed_roc_auc).sum()} "
      f"of {len(null)} -> p = {perm.empirical_p}")
fig("f14_permutation_null.png", 650)
""")
md("""
**Interpretation.**
* **Single folds are unreliable.** The 78 proteins fall into only 19 identity groups, one of them with 33 proteins, so
  held-out folds range from a handful of proteins to more than half the data, 18 of 100 folds per model contain only
  one class, and single-fold ROC AUCs span from 0 to 1 for every model. Only the average over many repeats means
  anything, and that average is close to 0.5.
* **The ROC curves hug the diagonal.** When the out-of-fold scores of a whole repeat are pooled, the curves give an
  AUC of about 0.52–0.53 for the feature models and below 0.5 for 5-NN. Pooled AUCs are a little lower than the
  per-fold average because scores from different folds are not on a common scale; neither view shows useful signal.
* **Precision, recall and F1 tell the same story.** Logistic regression and random forest reach F1 ≈ 0.44–0.55,
  in the range of the "cluster label only" baseline (≈ 0.53). The 5-NN model's higher recall (≈ 0.82) is not skill:
  its confusion matrix shows it calls most proteins "detected", so it also has the most false positives.
* **The permutation histogram shows the observed AUC sitting inside the shuffled-label distribution** (p ≈ 0.32).
* **Biological reading.** Whether an enzyme still works at 60 °C depends on a few specific features (stabilising
  disulfide bonds, calcium-binding sites, surface salt bridges, individual active-site residues). Whole-protein
  averages such as amino-acid percentages or isoelectric point blur exactly these details, which is the most likely
  reason the models cannot separate the classes.
* **Conclusion for the research question:** the existing supervised model has **not demonstrated reliable
  predictive performance** and is **not used to rank candidates** anywhere in this project.

#### 7.2.2 Data prepared for a future condition-specific model (not trained)

The curation step (`pet_explorer/curation.py`) assembled a larger labelled dataset from the 2025 standardised screen
at one named condition. No model has been trained on it; it is summarised here because it defines what a future
model could learn, and how it would have to be validated.
""")
code("""
lab = pd.read_csv(ROOT / "outputs/curation/condition_specific_labels.csv")
diag = json.loads((ROOT / "outputs/curation/split_diagnostics.json").read_text())
print("condition:", lab.condition.iloc[0])
display(lab.label.value_counts().rename("enzymes").to_frame())
print(f"grouped split: {diag['n_train']} train / {diag['n_test']} test, {diag['groups_spanning_both_sides']} identity "
      f"groups on both sides, {diag['n_cross_split_pairs_above_70pct']} cross-split pairs >= 70% identity "
      f"(max {diag['max_cross_split_identity']})")
pd.DataFrame(diag["cv_folds"]).T
""")
md("""
**Interpretation.** 208 enzymes have a usable binary label at this condition (the uncertain ones are excluded), and a homology-aware split with no
near-duplicate leakage is possible. But one family makes up fold 0 on its own, and most identity groups contain only
one label, so a model could score well simply by recognising family membership. Any future model on these data must
beat a family-membership baseline, not just 50%.
""")

md("""
### 7.3 Nearest-neighbour sequence matcher (dashboard feature)

A query is aligned locally against all 298 proteins.
* **Ranking:** a **length-normalised score**, raw / √(self-score of query × self-score of match). Raw scores
  alone would favour long proteins.
* **Per hit:** identity, query and match coverage, and a z-score against 25 shuffled copies of the query (a
  per-query random baseline).

**Validation:**
* every protein retrieves itself (100%)
* a 10%-mutated IsPETase retrieves IsPETase
* shuffled sequences fall below the homology bands
* invalid input (DNA, ambiguity codes, multiple FASTA records) is rejected (tests in `tests/`)
""")
code("""
from pet_explorer.sequence_matching import SequenceMatcher, hits_to_frame
import random
m = SequenceMatcher(proteins)
rng = random.Random(1); seq = list(proteins.sequence[0])
for i in rng.sample(range(len(seq)), len(seq)//10): seq[i] = rng.choice([a for a in C.STANDARD_AA if a != seq[i]])
header, q, hits = m.search("".join(seq))
display(hits_to_frame(hits, proteins).drop(columns="pet_evidence"))
print(hits[0].alignment_text[:420])
""")
code("""
loo = pd.read_csv(C.MATCHING / "leave_one_out_nearest_neighbour.csv")
print("Leave-one-out: closest OTHER reference protein for each of the 298 proteins")
loo.band.value_counts()
""")
md("""
**Interpretation.**
* **Most reference proteins have a near-identical or clear homolog elsewhere in the set.** This is the redundancy
  noted in the feasibility study.
* **8 have no reliable relative.** A query resembling those would get no useful match.
* **A match is always reported as a *promising candidate*.** Sequence similarity does not prove PET degradation.
""")

md("""
### 7.4 From sequence evidence to a laboratory shortlist (not a machine-learning prediction)

The research question asks which enzymes are worth testing in the laboratory. Because the supervised model did not
beat its null (7.2), candidates are **not** ranked with it. They are ranked with the **validated sequence matcher and
the evidence rules** that the web app uses for every query (`pet_explorer/evidence.py`; thresholds calibrated against
shuffled sequences and a leave-one-out search of the 298 references).

**Candidates.** The curation step marked 254 registry sequences as *eligible*: annotation-only records (PlasticDB,
degraders list) with no PET testing evidence found in any of our sources. Each was searched against the 298
references (Smith–Waterman, BLOSUM62, 25 shuffles, seed 0) and assigned an evidence category, then a priority tier:

| Tier | Meaning |
|---|---|
| 1 | Strong homolog (40–90% identity over ≥ 70% of both sequences, shuffle z ≥ 15, catalytic motif present, well-supported reference) |
| 2 | Near-identical (≥ 90% identity) to a characterised enzyme: most likely to behave like it, least novel |
| 3 | Possible: motif missing, weaker reference, partial, remote or domain-level similarity |
| 4 | Not prioritised: signals disagree, fragment or short match |
| 5 | Not prioritised: no convincing similarity (not evidence of inactivity) |

Rebuild with `python -m pet_explorer.shortlist`; the table is `outputs/explorer/shortlist/candidate_shortlist.csv`.
""")
code("""
sl = pd.read_csv(shortlist.F_SHORTLIST)
summary = json.loads(shortlist.F_SUMMARY.read_text())
display(pd.Series(summary["by_tier"], name="candidates").to_frame())
print("invalid sequences:", summary["invalid_sequences"],
      "| tier-2 rows that are probably the same enzyme as a reference:", summary["probably_same_enzyme_as_a_reference"],
      "| candidates citing the 2025 screen paper:", summary["candidates_citing_2025_screen_doi"])
cols = ["rank", "name", "organism", "closest_reference", "identity", "candidate_coverage", "reference_coverage",
        "shuffled_z", "gxsxg_variants", "reference_positive_assays", "reference_publications", "evidence_category",
        "plasticdb_plastics_annotation"]
print("Tier 1: strongest sequence case for a new PET hydrolase")
display(sl[sl.priority_tier == 1][cols])
""")
code("""
print("Tier 3: possible candidates (weaker or partial evidence)")
display(sl[sl.priority_tier == 3][cols + ["rule"]])
with pd.option_context("display.max_colwidth", 300):
    display(sl[sl.priority_tier.isin([1, 3])][["rank", "name", "prioritisation_reason"]].head(4))
""")
md("""
**Interpretation.**
* **Eight candidates have the strongest sequence case** (tier 1). They are clear homologs (about 45–89% identity over
  almost their whole length, shuffle z far above the null range) of enzymes with published PET activity, and carry
  the catalytic motif: for example two *Aequorivita* esterases related to PET27, a *Halopseudomonas* lipase related to
  PpCutA, fungal cutinases related to HiC, and two bacterial hydrolases related to Lip4_120 and TA29. Several are
  annotated in PlasticDB for other polyesters (PCL, PLA, PBSA), which fits: these hydrolase families often act on
  several polyesters.
* **Most "near-identical" candidates are not really new** (tier 2). 104 of 121 are ≥ 99% identical over ≥ 98% of a
  characterised enzyme, and 86 cite the 2025 screening paper. They are almost certainly the same enzymes recorded under
  another name or as precursor or tagged forms; the curation step's exact-sequence deduplication could not catch
  them. They should be treated as already characterised, not as discoveries.
* **Twenty candidates are possible but weaker** (tier 3), mostly distant homologs in the twilight zone whose
  similarity is still far above shuffled controls. A profile-HMM or structure comparison should come before lab work.
* **86 candidates show no convincing similarity** (tier 5): a mix of PHB/PHA depolymerases (26), proteases,
  laccases and other oxidases, nylon- and rubber-degrading enzymes, mostly annotated for other plastics. This says the sequence evidence does not point to PET activity; it does not
  show they are inactive.
* **This shortlist is sequence evidence, not a validated activity prediction.** Activity depends on substrate form,
  temperature and pH, and a single active-site substitution can abolish it. The cited literature should be checked
  before any gene is ordered.
""")

md("""
## 8. Conclusions, limitations and future work

**Answer to the research question** — *How can protein sequence analysis and machine learning help identify
promising PET-degrading enzyme candidates for further laboratory testing?*

**Sequence analysis helps directly; unsupervised learning explains the landscape; supervised learning, on the data
available, does not yet help.** In detail:

1. **Supported by sequence analysis.** Alignment against the 298 verified PET hydrolases, with a shuffled-sequence
   control and the catalytic-motif check, places a new sequence relative to enzymes with published PET activity.
   The matcher retrieves every reference and mutated variants of it, rejects shuffled sequences, and its evidence
   rules were calibrated so that shuffled sequences are never green or yellow (Sections 7.3–7.4). 296 of 298 verified
   enzymes carry the G-x-S-x-G motif, so a candidate without it needs a strong reason to be tested.
2. **Supported by clustering.** Verified PET hydrolases form real, stable sequence groups (silhouette 0.34 against
   at most 0.03 for null models, p = 0.005), dominated by one PET hydrolase/cutinase family (G1, 88%, Pfam PF12740)
   with an extended G-x-S-M-G-G-G motif, plus a separate fungal-cutinase family (G3). A candidate's group therefore
   says which known enzymes it most resembles. These groups are **not** shown to differ in the temperatures at which
   they degrade PET once study design is controlled (H2 not confirmed).
3. **Inconclusive supervised machine learning.** Under homology-aware cross-validation, sequence features did not
   predict whether PET conversion is still detected at 60 °C (ROC AUC ≈ 0.56, permutation p ≈ 0.32; per-fold,
   ROC-curve, confusion-matrix and F1 views agree). The model is therefore **not used to rank candidates**. The
   limiting factors are data, not method: no confirmed PET-inactive sequences, and 78 proteins in only 19 independent
   groups. A larger condition-specific dataset (208 labelled enzymes) is prepared but not yet modelled.
4. **Candidates that require laboratory testing.** Of 254 annotation-only candidates, **8** have the strongest
   sequence case (tier 1) and **20** are possible but weaker (tier 3). Most "near-identical" candidates (104 of 121)
   turn out to be the same enzymes as already characterised references. **None of these is a validated PET
   degrader**: the shortlist says where laboratory effort is best spent first, and only an assay can confirm activity.

**One point per objective**
1. **O1 — Data.** 298 experimentally verified PET-active proteins with valid sequences (from 301), 5,058 PET assays and
   8,439 measurements, with organism evidence for 159 proteins. No usable PET-inactive sequences exist in these sources.
2. **O2 — Sequence groups (H1 supported).** Alignment-based hierarchical clustering gives 7 groups that are stable
   (ARI 0.99) and far better than chance (p = 0.005). 88% of proteins form G1, the PET hydrolase/cutinase family
   (Pfam PF12740) sharing an extended G-x-S-M-G-G-G motif. G1 splits into G1a (all GWSMG / "type II"-like enzymes
   plus classic cutinases, including IsPETase and LCC) and G1b (multi-domain proteins with lectin and
   carbohydrate-binding modules). G3 is a separate fungal-cutinase family (GYSQG, PF01083).
3. **O3 — Temperature (H2 not confirmed).** A naive test finds group differences (q ≈ 0.0005), but under one standardised
   protocol G1a and G1b do not differ after FDR correction (q ≥ 0.08). The apparent differences reflect study design.
   Most proteins were tested at too few temperatures to define an optimum.
4. **O4 — Machine learning.** The clustering beats both null baselines. The supervised model for activity at 60 °C does
   **not** beat its baselines (AUC ≈ 0.56, permutation p ≈ 0.32), so H3 is not supported.

**Limitations**
* **No PET-inactive sequences**, so the system cannot predict PET degradation, only similarity to known degraders.
* **The data are redundant and literature-biased.** Large screening papers dominate some groups (e.g. G1b).
* **Assays are heterogeneous**: different units, methods, PET forms and conditions; only two standardised screens.
* **Small supervised dataset** (78 proteins, 19 identity groups), so model estimates are noisy.
* **Domain annotation covers 167 / 298 sequences** (those in UniParc); organism known for only 53%.
* **Silhouette values are moderate (≤ 0.35).** Clusters are a useful summary, not sharp biological categories.
* **The shortlist is sequence evidence only.** Evidence belongs to the matched reference enzyme; "eligible" means no
  PET testing evidence was found in our sources, not that none exists. Near-duplicate records were detected only
  after the search (same enzyme under another name), which shows the candidate registry needs similarity-based,
  not only exact-sequence, deduplication.

**Future work**
* Express and assay the tier-1 candidates under one named condition (e.g. crystalline PET powder, 40 °C, pH 6.5,
  HPLC quantification of TPA/MHET) with a known PET hydrolase as positive control.
* Add experimentally confirmed inactive enzymes (with sequences) to enable PET-active vs inactive prediction.
* Use structure-aware features (AlphaFold models, disulfide bonds, Ca²⁺ sites) or protein language-model embeddings
  for the 60 °C model; add melting temperatures (Tm) as a direct thermostability target.
* Run InterProScan on the 131 sequences missing from UniParc to complete the domain annotation.
* Enrich organisms and taxonomy via UniProt/NCBI accessions (`reference_accessions`, `accessions_in_pazy_notes`).
* Test the G1a/G1b temperature question with a new standardised screen covering more groups and temperatures.
""")

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3"},
                                                "colab": {"provenance": []}})
out = Path(__file__).with_name("pet_enzyme_explorer.ipynb")
nbf.write(nb, out)
print("wrote", out)
