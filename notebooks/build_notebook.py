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
recycling possible. This notebook asks what the experimentally verified PET-degrading enzymes have in common at the
sequence level, and whether that relates to the temperatures at which they work.

**How to run.** *Runtime → Run all* in Google Colab, or locally from the repository root. In Colab the first cell clones
the repository ({REPO}), which contains the raw data and cached results. Expensive steps (44,253 pairwise alignments,
clustering grids, cross-validation) are cached in `outputs/explorer/`; set `RECOMPUTE = True` to regenerate everything
from the raw files (~5 min).

**Convention:** *experimentally established* = taken from PAZy assay records. *Computational* = derived here
(similarity, clusters, predictions).
""")

md("""
## 1. Research question, objectives and hypotheses

A feasibility analysis (`outputs/pet_dataset_feasibility_report.md`) showed that the data contain
**298 PET-active proteins with sequences but 0 usable PET-inactive ones**, so "PET-active vs PET-inactive"
classification is not possible. The question is therefore about structure *within* the known PET degraders:

> **Research question.** Do experimentally verified PET-hydrolysing enzymes form distinct groups based on their
> amino-acid sequence features, and do these groups relate to the temperatures at which PET degradation was observed?

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

code(f"""
# Google Colab only: fetch the repository (code + raw data + cached outputs) and the one missing package.
import os, subprocess, sys
from pathlib import Path
if "google.colab" in sys.modules and not Path("pet_explorer").exists():
    if not Path("Bioinformatics-Group-Project").exists():
        subprocess.run(["git", "clone", "-q", "{REPO}"], check=True)
    os.chdir("Bioinformatics-Group-Project")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "biopython==1.85"], check=True)
print("working directory:", Path.cwd())
""")

code("""
import json, warnings
warnings.filterwarnings("ignore")
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))

import numpy as np, pandas as pd
from IPython.display import Image, display, Markdown
from pet_explorer import config as C, pipeline
pd.set_option("display.max_colwidth", 80, "display.width", 200)

RECOMPUTE = False   # True = rebuild all cached outputs from data/ (~5 min on 10 cores)
if RECOMPUTE or not (C.PREDICTION / "model_comparison.csv").exists():
    C.ensure_dirs(); pipeline.stage1(); pipeline.stage2()
    from pet_explorer import temperature, organisms
    temperature.run(); organisms.run(); pipeline.export_network(); pipeline.stage5()
fig = lambda name, w=700: display(Image(filename=str(C.FIGURES / name), width=w))
print("outputs ready in", C.EXPLORER.relative_to(ROOT))
""")

md("""
## 2. Data acquisition and provenance

Six files were downloaded by the project team into `data/` and are **never modified**:

| Source | File | Role here |
|---|---|---|
| PAZy (Plastics-Active enZymes database, pazy.eu) | `pazy_proteins_sequences.csv`, `pazy_proteins.fasta` | Protein sequences (301) |
| PAZy | `pazy_polymer_assays.json.gz` (schema 4.2) | Experimental assays (7,195; 5,058 on PET) |
| PlasticDB (plasticdb.org) | `PlasticDB.fasta`, `degraders_list.tsv` | Organism links, Tax IDs, isolation data |
| UniProt (downloaded 2026-10-27, from file name) | `uniprotkb_…fasta.gz` | Reference cutinases (3) |
| UniParc (rest.uniprot.org, queried by sequence checksum) | cached in `outputs/explorer/annotation/` | Pfam / InterPro domains (Section 6) |

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
""")
code("""
display(pd.read_csv(C.CLEAN / "qc_checks.csv"))
proteins = pd.read_csv(C.F_PROTEINS)
print(f"Before: {len(csv)} sequences in PAZy  ->  after: {len(proteins)} PET-active proteins with valid sequences")
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

md("## 4. Exploratory data analysis")
code("""
feats = pd.read_csv(C.CLUSTERING / "sequence_features.csv")
display(feats[["length", "isoelectric_point", "gravy", "aromaticity", "instability_index"]].describe().round(2))
fig("f01_length_distribution.png"); fig("f02_aa_composition.png")
""")
md("""
**Interpretation.** Lengths range from 178 to 491 aa (median 297). This is consistent with single-domain α/β-hydrolases,
though several proteins are around 400–490 aa. Alanine (11.0%) and glycine (9.8%) are the most frequent residues on
average. Composition varies little between proteins, which already suggests composition alone will separate families
poorly (confirmed in Section 5.2).
""")

md("""
### 4.1 Conserved motif

Serine hydrolases (lipases, esterases, cutinases) usually carry their catalytic serine in a **G-x-S-x-G** pentapeptide.
We search for it in every sequence (a hypothesis-driven check, not an assumption).
""")
code("""
print("Proteins with >=1 G-x-S-x-G:", int((feats.gxsxg_count > 0).sum()), "/", len(feats))
fig("f09_gxsxg_motif_variants.png")
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
* **7.3** the nearest-neighbour **sequence matcher** behind the dashboard, validated by leave-one-out.

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
## 8. Conclusions, limitations and future work

**Answer to the research question.** Yes for the first half, no for the second: verified PET-hydrolysing enzymes form
clear, non-random sequence groups — dominated by one PET hydrolase/cutinase family — but with current data these groups
are **not** shown to differ in the temperatures at which they degrade PET.

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

**Future work**
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
