# PET Enzyme Explorer — Summary of Findings

All numbers come from `python -m pet_explorer.pipeline` run on the six files in `data/`.

## Data

- **298** experimentally verified PET-active proteins with valid sequences, all identical to the raw PAZy CSV.
- **0** usable PET-inactive sequences, so the work is unsupervised and descriptive.
- **5,058** PET assay records and **8,439** PET measurements.

## Sequence analysis and clustering (Feature 2)

- **Alignments:** 44,253 pairwise local alignments (BLOSUM62).
- **Method comparison:** hierarchical clustering on alignment distance, k-means on composition and physicochemical
  features, and DBSCAN on alignment distance.
- **Selected method:** hierarchical clustering (average linkage) with **7 clusters**. Silhouette 0.344 (moderate
  structure), stability ARI 0.987. The selection rule was fixed before inspecting cluster contents.
- **Dominant lineage:** G1 contains **263 / 298 (88%)** proteins.
  - 296 / 298 proteins carry the G-x-S-x-G catalytic-serine motif.
  - The 5-mer SMGGG is found in 93% of G1 and 3% of other proteins.
- **G1 sub-structure:** G1 splits reproducibly (ARI 1.0) but weakly (silhouette 0.16) into two subgroups.
  - **G1a (165 proteins):** all 42 GWSMG-motif proteins are here.
  - **G1b (98 proteins):** longer (median 412 aa), 60% mean identity. Drawn from only 3 publications, so this is a
    possible sampling effect.
- **Small groups:**
  - **G3 (9):** coherent, GYSQG motif, about 228 aa.
  - **G4 (5):** moderately coherent.
  - **G2 (15) and G5 (4):** heterogeneous remainders (mean identity < 25%).
  - **G6 and G7:** single proteins.
- **Composition features miss family structure:** k-means on them agrees with the alignment clusters at ARI 0.08.
- **Not ML clusters:** the 110 groups at 70% identity describe near-duplicates (ARI 0.05 with the selected solution).
- **Similarity network:** 298 nodes and 14,447 edges (≥ 40% identity, ≥ 70% coverage of both proteins).
  It has 41 components; the largest holds 239 proteins and 30 proteins are isolated.

- **Better than chance:** silhouette 0.344 vs at most −0.02 for random labels of the same sizes and 0.03 for
  average linkage on shuffled distances (200 draws each, empirical p = 0.005).

**H1 supported:** most verified PET hydrolases form one motif-sharing sequence lineage.

## Biological interpretation

- **Domains (Pfam via UniParc, 167 / 298 sequences found):**
  - G1a and G1b: PET hydrolase/cutinase-like (PF12740) in every annotated member.
  - G1b: 32 / 50 annotated proteins also carry a Ricin-B lectin domain (PF00652), others carbohydrate-binding
    modules, which explains their greater length.
  - G3: fungal cutinase (PF01083). G4: carboxylesterase type B (PF00135). G2/G5: mixed α/β-hydrolases.
- **Literature:** IsPETase, LCC, TfCut2, TfH, Cut190, Tcur_1278, BhrPETase, PE-H and PET2 are all in G1a; HiC is in G3.
  "Type II" enzymes (IsPETase, PE-H) carry GWSMG and "type I" cutinases (LCC, TfCut2) GHSMG, which matches the
  W159H observation of Austin et al. 2018.
- **Network roles:** hubs are G1 members with ~150–200 neighbours (TfH, LCC among them); the strongest bridges are
  G1b proteins (ESM121, ESM139) linking G1b to the G1a core.

## Sequence matching (Feature 1)

- **Speed:** about 0.13 s per query.
- **Ranking:** a length-normalised score.
- **Validation:**
  - all self-queries return 100%;
  - a 10%-mutated sequence finds its parent;
  - shuffled sequences fall below the homology bands.
- **Leave-one-out:** 8 of 298 proteins have no reliable relative in the reference set.

## Temperature (Feature 3)

- **Too few temperatures for most proteins:** 115 proteins were tested at one temperature and 89 at two.
  No optimum can be determined for any of them.
- **Comparable series:** 80 proteins have such series (same paper, metric, unit, pH, duration, material, enzyme
  loading; ≥ 3 temperatures). 163 of the 383 series peak at the edge of the tested range.
- **Group differences are confounded:**
  - Temperatures with detected activity differ between groups (G1a median 50 °C, G1b 40 °C).
  - But 89% of G1b assays were run at exactly 40 or 60 °C in screening studies.
- **Statistical tests (Benjamini–Hochberg FDR across 11 tests):**
  - Naive, all assays (one median per protein): Kruskal–Wallis q = 0.0005; G1a vs G1b q = 0.001.
  - Controlled, 99-protein screen: G1a vs G1b at 40 °C q = 0.97; at 60 °C p = 0.044 but q = 0.08; detected at
    60 °C 17/27 vs 22/51, q = 0.21. Conversion drops from 40 to 60 °C (median 0.67% → 0.04%, q < 10⁻⁹).
  - **H2 is not confirmed.**

## Supervised machine learning (H3)

- **Target:** PET conversion detected at 60 °C in the standardised screen (78 proteins, 39 / 39).
- **Protocol:** 20 × 5-fold cross-validation grouped by 70%-identity group (19 groups) to prevent leakage.
- **Result:** logistic regression and random forest ROC AUC 0.556; baselines 0.50 (majority), 0.47 (random),
  0.53 (cluster label only); 5-NN on alignment identity 0.52. Permutation test p = 0.32.
- **H3 not supported:** simple sequence features do not predict activity at 60 °C.
- **Valid cross-protein comparisons** exist only within two standardised screens:
  - DOI 10.1038/s41467-022-35237-x, Source Data Table D3 (25 proteins);
  - DOI 10.1021/acscatal.5c03460 (99 proteins).

## Organisms (Feature 4)

- **Coverage:** **159 / 298** proteins have a documented organism.
  - 56 from exact sequence matches.
  - 103 from precursor/mature-form containment matches (each covers ≥ 81% of the longer sequence).
- **Unknown:** 139 proteins show "Unknown — insufficient evidence".
- **Other flags:**
  - 4 proteins have conflicting database records (e.g. PET5: *Moraxella* sp. vs *Oleispira antarctica*);
  - 19 come from uncultured or metagenomic sources;
  - 12 have a documented isolation environment.

## Features that need additional datasets

| Feature | Missing data | Possible source |
|---|---|---|
| Predict PET degradation (active vs inactive) | Experimentally confirmed inactive enzymes with sequences | Literature negative results; screening studies' raw data |
| Organism for the remaining 139 proteins; full taxonomy | Accession-to-taxonomy mapping | UniProt / NCBI via `reference_accessions`, `accessions_in_pazy_notes` |
| Domain annotation for the 131 sequences not in UniParc | InterProScan runs | EBI InterProScan |
| True temperature optima / thermostability | Systematic temperature series, melting temperatures | Literature, protein stability databases |
| Isolation environment for most proteins | Sample metadata | NCBI BioSample, original publications |
| Structure-aware comparison | 3-D structures / predicted models | PDB, AlphaFold DB |
