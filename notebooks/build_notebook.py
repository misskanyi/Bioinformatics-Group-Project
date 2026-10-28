"""Generate notebooks/pet_enzyme_explorer.ipynb (then execute it with nbconvert).

    .venv/bin/python notebooks/build_notebook.py
    .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/pet_enzyme_explorer.ipynb
"""

from pathlib import Path

import nbformat as nbf

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# PET Enzyme Explorer — Bioinformatics and Machine-Learning Analysis

**Project:** *PET Enzyme Explorer: A Bioinformatics and Machine Learning System for Identifying and Characterising
PET-Degrading Enzymes* (Computing for Bioinformatics, year 4).

This notebook documents the scientific analysis behind the dashboard (`app/streamlit_app.py`) in the order it was done.
Expensive steps (44,253 pairwise alignments, clustering grids) are cached in `outputs/explorer/`; set
`RECOMPUTE = True` below to regenerate everything from the raw files.

**Convention:** *experimentally established* = taken from PAZy assay records.
*Computational* = derived here (similarity, clusters, predictions).
""")

md("""
## 1. Research question and hypotheses

A previous feasibility analysis (`outputs/pet_dataset_feasibility_report.md`) showed that the data contain
**298 PET-active proteins with sequences but 0 usable PET-inactive ones**, so PET-active vs PET-inactive
classification is not possible. The question is therefore descriptive and unsupervised:

> **Research question.** Do experimentally verified PET-hydrolysing enzymes form distinct groups based on their
> amino-acid sequence features, and do these groups relate to the temperatures at which PET degradation was observed?

* **H1** — Most verified PET-active enzymes belong to a small number of sequence-similarity groups that share the
  serine-hydrolase G-x-S-x-G catalytic motif.
* **H2** — Sequence groups differ in the temperatures at which PET degradation has been detected.
""")

code("""
import sys, json, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))

import numpy as np, pandas as pd
from IPython.display import Image, display, Markdown
from pet_explorer import config as C, pipeline
pd.set_option("display.max_colwidth", 80, "display.width", 200)

RECOMPUTE = False   # True = rebuild all cached outputs (~1 min on 10 cores)
if RECOMPUTE or not (C.ORGANISMS / "protein_organisms.csv").exists():
    C.ensure_dirs(); pipeline.stage1(); pipeline.stage2();
    from pet_explorer import temperature, organisms
    temperature.run(); organisms.run(); pipeline.export_network()
fig = lambda name, w=700: display(Image(filename=str(C.FIGURES / name), width=w))
""")

md("""
## 2. Data acquisition and provenance

Six files were downloaded by the project team into `data/` and are **never modified**:

| Source | File | Role here |
|---|---|---|
| PAZy (Plastics-Active enZymes database) | `pazy_proteins_sequences.csv`, `pazy_proteins.fasta` | Protein sequences (301) |
| PAZy | `pazy_polymer_assays.json.gz` (schema 4.2) | Experimental assays (7,195; 5,058 on PET) |
| PlasticDB | `PlasticDB.fasta`, `degraders_list.tsv` | Organism links, Tax IDs, isolation data |
| UniProt (downloaded 2026-10-27, from file name) | `uniprotkb_…fasta.gz` | Reference cutinases (3) |

Download dates of the non-UniProt files were not recorded. Licences and versions should be noted from the source websites.
""")
code("""
pd.read_csv(C.FEASIBILITY / "tables/dataset_inventory.csv")[["file", "format", "records", "unique_ids", "duplicate_sequences", "notes"]]
""")

md("""
## 3. Pre-processing and quality control

Activity labels come from the feasibility analysis (`analyze_pet_dataset.py`). Each PET assay is classified from its
measurements: degradation detected / nothing detected / unclear / excluded. These assay results are then aggregated
per protein. We keep the 298 proteins that are **PET-active (high/medium confidence) and have a valid sequence**.
Every sequence is re-checked against the raw CSV.
""")
code("""
display(pd.read_csv(C.CLEAN / "qc_checks.csv"))
proteins = pd.read_csv(C.F_PROTEINS)
proteins.pet_label.value_counts()
""")

md("## 4. Exploratory analysis of the sequences")
code("""
feats = pd.read_csv(C.CLUSTERING / "sequence_features.csv")
display(feats[["length", "isoelectric_point", "gravy", "aromaticity", "instability_index"]].describe().round(2))
fig("f01_length_distribution.png"); fig("f02_aa_composition.png")
""")
md("""
**Interpretation.** Lengths range from 178 to 491 aa (median 297). This is consistent with single-domain α/β-hydrolases,
though several proteins are around 400–490 aa. Alanine (11.0%) and glycine (9.8%) are the most frequent residues on average. Composition
varies little between proteins, which already suggests composition alone will separate families poorly (Section 6).
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
## 5. Pairwise sequence similarity

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
## 6. Unsupervised machine learning: clustering

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
  near-duplicates, which matters for data leakage, not family structure.
* **A silhouette of about 0.34 means moderate, not strong, structure.**
""")
code("""
summ = pd.read_csv(C.CLUSTERING / "cluster_summary.csv")
display(summ)
fig("f06_mds_alignment.png"); fig("f05_pca_features.png"); fig("f08_cluster_sizes.png", 600)
""")

md("""
### 6.1 Second level: structure inside G1

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
### 6.2 Motifs and cluster-specific sequence segments

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
## 7. Sequence-similarity network for Cytoscape

Nodes are proteins. An **edge** joins two proteins whose local alignment has **≥ 40% identity and covers ≥ 70% of both
sequences**. The threshold is defensible for two reasons:
* 40% identity over most of two ~300-aa proteins is well above the 25–35% "twilight zone" (Rost 1999), so edges indicate
  probable homology.
* The coverage rule stops short shared segments, such as signal peptides, from linking unrelated proteins.

This is a **sequence-similarity network, not a protein–protein interaction network.**
""")
code("""
display(pd.read_csv(C.NETWORK / "edge_threshold_sensitivity.csv").query("min_coverage == 0.7"))
nodes, edges = pd.read_csv(C.NETWORK / "ssn_nodes.csv"), pd.read_csv(C.NETWORK / "ssn_edges.csv")
print(len(nodes), "nodes,", len(edges), "edges. Files: outputs/explorer/network/ssn_nodes.csv, ssn_edges.csv")
nodes.head()
""")
md("""
Import into Cytoscape:
1. **File → Import → Network from File** → `ssn_edges.csv` (source/target columns).
2. **File → Import → Table from File** → `ssn_nodes.csv` (key column `id`).
3. Colour nodes by `cluster`/`organism` and set edge width by `identity`.
""")

md("""
## 8. Feature 1: sequence matching

A query is aligned locally against all 298 proteins.
* **Ranking:** a **length-normalised score**, raw / √(self-score of query × self-score of match). Raw scores
  alone would favour long proteins.
* **Per hit:** identity, query and match coverage, and a z-score against 25 shuffled copies of the query.

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
* **A few have no reliable relative.** A query resembling those would get no useful match.
* **A match is always reported as a *promising candidate*.** Sequence similarity does not prove PET degradation.
""")

md("""
## 9. Feature 3: experimental temperature analysis

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
fig("t01_tested_temperatures.png"); fig("t02_activity_by_temperature.png")
""")
code("""
display(pd.read_csv(C.TEMPERATURE / "active_temperature_by_cluster.csv"))
fig("t03_active_temperature_by_cluster.png")
""")
md("""
**Interpretation (H2).**
* **Two-thirds of proteins cannot have an optimum determined.** 115 proteins were tested at one temperature
  and 89 at only two.
* **Many series peak at the edge of their tested range**, so the true optimum may lie outside it.
* **Groups do differ in the temperatures where activity was detected** (e.g. G1a median 50 °C vs G1b 40 °C).
  But each group was tested in different studies with different temperature grids. 89% of G1b assays were run at
  exactly 40 °C or 60 °C, mostly in one screening study (DOI 10.1021/acscatal.5c03460).
* **H2 therefore cannot be confirmed:** the differences may reflect experimental design rather than enzyme
  thermostability.

**Valid cross-protein comparisons** exist only inside the two standardised screens, where one protocol was used for
many proteins.
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
## 10. Feature 4: organism identification

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
## 11. Conclusions, limitations and future work

**Conclusions**
1. **H1 supported.** 88% of verified PET-active enzymes form one sequence lineage (G1), sharing the catalytic-serine
   motif in an extended G-x-S-M-G-G-G form. A few small, distinct groups (e.g. G3, GYSQG) and outliers make up the rest.
2. **Choice of features matters.** Alignment-based clustering captures this structure. Composition-based k-means
   does not (ARI 0.08).
3. **G1 has a reproducible but weak internal split** (G1a/G1b), partly tied to how proteins were sampled.
4. **H2 not confirmed.** Temperature differences between groups are confounded by study design. Most proteins lack
   enough temperatures to define an optimum.

**Limitations**
* **No PET-inactive sequences**, so the system cannot predict PET degradation, only similarity to known degraders.
* **The data are redundant and literature-biased.** Large screening papers dominate some groups.
* **Assays are heterogeneous**: different units, methods, PET forms and conditions.
* **Organism known for only 53%** of proteins. There are no domain/family annotations (Pfam/InterPro).
* **Silhouette values are moderate (≤ 0.35).** Clusters are a useful summary, not sharp biological categories.

**Future work**
* Add experimentally confirmed inactive enzymes (with sequences) to enable supervised prediction.
* Enrich organisms and taxonomy via UniProt/NCBI accessions (`reference_accessions`, `accessions_in_pazy_notes`).
* Add Pfam/InterPro/ESTHER annotations to name the groups.
* Use protein language-model embeddings or structure-based features as alternatives to alignment.
* Extend the temperature analysis with thermostability data (e.g. melting temperatures).
""")

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3"}})
out = Path(__file__).with_name("pet_enzyme_explorer.ipynb")
nbf.write(nb, out)
print("wrote", out)
