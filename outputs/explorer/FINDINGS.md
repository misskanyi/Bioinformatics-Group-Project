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

**H1 supported:** most verified PET hydrolases form one motif-sharing sequence lineage.

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
  - **H2 is not confirmed.**
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
| Named enzyme families | Domain annotations | Pfam, InterPro, ESTHER |
| True temperature optima / thermostability | Systematic temperature series, melting temperatures | Literature, protein stability databases |
| Isolation environment for most proteins | Sample metadata | NCBI BioSample, original publications |
| Structure-aware comparison | 3-D structures / predicted models | PDB, AlphaFold DB |
