# Dataset Exploration and Feasibility Audit

**PET Enzyme Explorer — read-only audit of `data/` prior to any modelling work**

Research question: *How can protein sequence analysis and machine learning help identify promising
enzyme candidates for PET plastic recycling?*

Audit date: 2026-10-29. Nothing in `data/`, `pet_explorer/`, `backend/`, `frontend/` or any existing
`outputs/` subfolder was modified, moved or renamed. All findings below are computed from the raw files;
supporting tables are in [tables/](tables/) and every quoted statistic is reproduced in
[audit_statistics.json](audit_statistics.json).

---

## 1. Executive summary

| Question | Answer |
|---|---|
| Can we build reliable positive labels? | **Yes.** 311 PAZy proteins with PET assay evidence, plus 128 experimentally positive enzymes in the 2025 screen. |
| Can we build reliable negative labels? | **Only condition-specific ones**, and essentially only from the 2025 screen (85 enzymes with no detected product). PAZy contains **zero** protein-level negatives. |
| Is there an independent test set? | **Yes, and it is unusually good.** The 2025 library shares **no exact sequence** with the PETML variant library and has a median best identity of **63%** to it. |
| Main threat to validity | **Sequence redundancy and leakage.** 501 PETML entries collapse to ~66 scaffolds; 244 are IsPETase point mutants. 329/501 PETML entries are ≥99% identical to a PAZy protein, and 128/214 assayed 2025 enzymes are ≥99% identical to a PAZy protein. |
| Recommended model | **Condition-specific binary classifier** (substrate × temperature × pH) trained on the 2025 screen, with scaffold-level grouped splits — *not* a global "PET-degrader vs not" classifier. |
| Can we predict untested candidates? | **Yes, with a narrowed claim.** We can rank untested sequences by predicted activity under a *named* condition. We cannot credibly predict "this protein degrades PET" in the abstract. |

---

## 2. Source inventory and provenance

41 files in `data/`, in four provenance groups. Full table: [tables/source_inventory.csv](tables/source_inventory.csv).

### 2.1 PETML study workbooks (33 files, 37 sheets)

Per-study tables of engineered PET hydrolase variants, digitised from the literature (Wei 2016 →
Sagong 2022). Per-sheet detail: [tables/petml_sheet_inventory.csv](tables/petml_sheet_inventory.csv).

- **Columns are near-uniform**: `Protein`, sometimes `Name in paper`, then `Activity`, `logActivity`,
  `Tm`, `dTm`. A few carry per-analyte columns (`MHET`, `TPA`) or prediction columns
  (`Pred Method`, `Score`).
- **26 sheets carry `Activity`**, 21 carry `Tm`. Four sheets inside `Cui et al, 2021 (NanoPET).xlsx`
  (`Abacus`, `FoldX`, `Rosetta_ddg`, `Consensus`) are **computational ΔΔG predictions, not measurements** —
  they must never be treated as experimental evidence.
- **711 protein mentions → 501 unique protein names.** Proteins recur across studies; these are repeated
  measurements, not independent proteins.
- **No missing sequences**: all 501 names resolve to a record in `sequences.fasta`, and every FASTA
  record is measured somewhere. This linkage is exact and complete (0 unmatched either way).

### 2.2 `sequences.fasta`

501 records, **498 unique sequences**. Three duplicate groups, all benign but worth fixing:

| Duplicate group | Cause |
|---|---|
| `IsPETase_S121E/D186H/R280A/R224Q/N233K` = `IsPETase_S121E/R224Q/N233K/D186H/R280A` | same mutant, mutations listed in different order |
| `IsPETase_S214H/I168R/W159H/S188Q/R280A/A180I/G165A/Q119Y/L117F/T140D` = `IsPETase_L117F/.../R280A` | same mutant (DuraPETase), different naming convention |
| `BbPETase` = `BurPL` | **same protein under two names from two papers** (Sagong 2022 / Chen 2021) |

### 2.3 `cs5c03460_si_002.xlsx` — ACS Catalysis 2025 supplementary

The single most valuable file for supervised learning. DOI `10.1021/acscatal.5c03460`. Seven sheets:

| Sheet | Rows | Contents |
|---|---|---|
| `Rounds` | 477 | The screened library: `sample_id`, `accession`, full `seq_nuc` + `seq_aa`, expression yield, `tm_1`/`tm_2` |
| `Activity` | 3856 | The assay table — one row per well |
| `fig4a` | 92 | Per-variant observation counts and one condition's activity |
| `fig5a`, `fig5b,figS10`, `figS9`, `fid2d` | 45 / 1571 / 67 / 10 | The paper's own model benchmarks (AUROC by condition, HMM baselines) |

**Library (`Rounds`)**: 477 sequences, all unique, 474 unique accessions. Three discovery rounds and
three dataset families — `DP` (94, RND1), `TEP` (191, RND2), `ESM` (190, RND3). Accessions are mostly
NCBI `WP_` (241) and metagenomic `MGYP` (99). Lengths 159–570 aa (median 266). Melting temperature
measured for 234 of 477.

**Assay table (`Activity`)** — this is a genuine, standardised, condition-resolved screen:

- **Substrate**: `cryPow` (crystalline powder, 2432 rows) and `aFilm` (amorphous film, 1424 rows).
- **Temperature**: 40 °C (2052) and 60 °C (1804).
- **pH**: 4.5, 5.5, 6.5, 7.5, 8.5.
- **Controls present and explicit**: 220 `blank` wells (no enzyme) and 220 `LCC-ICCG` wells
  (the benchmark positive control), in every plate block.
- **Reaction parameters recorded per well**: reaction volume, PET loading, solids loading,
  enzyme loading (µg), mg enzyme per g PET, nM enzyme, dilution.
- **Nine measurement columns**, already normalised several ways: `mM_product`,
  `ug_per_mL_product_avgTPAMHET`, `mg_TPAeq`, `percent_depolymerization`,
  `umol_product_per_mg_enzyme`, `nmol_product_per_nM_enzyme` and others.
  **No missing values** in `umol_product_per_mg_enzyme`.
- **215 non-blank sample IDs**, of which 213 are library enzymes and 2 are the LCC-ICCG control forms.
  214 of 215 link cleanly to `Rounds`; the exception is `sumo_LCC-ICCG` (a control, not a library member).

### 2.4 PAZy, PlasticDB and UniProt

| Source | Size | Evidence status |
|---|---|---|
| `pazy_proteins.fasta` / `.csv` | 301 proteins, all unique | **Experimentally validated.** PAZy only admits proteins with published activity evidence. |
| `pazy_polymer_assays.json.gz` | 579 publication records → **7195 assays**, 462 proteins | Structured evidence: substrate, conditions (temperature, buffer, duration, enzyme prep), detection methods, measurements with units and qualifiers, and a literature DOI per record. Schema v4.2. |
| `PlasticDB.fasta` | 329 records, 311 unique, 187 headers mention PET | **Mixed.** Headers are `id\|enzyme_name\|organism\|plastic\|genbank`. Name-based annotation ("Cutinase", "PETase"); some entries have `NA` accessions. Treat as *annotated*, not validated. |
| `degraders_list.tsv` | 2535 rows × 22 cols, 253 PET rows | **Organism-level**, mostly. Evidence column is informative: `Clear zone` (661), `Spectrophotometry` (154), `Weight loss` (83), `HPLC` (63). **Sequence missing for 2008 of 2535 rows.** 399 rows are flagged `Degradation extrapolated from enzyme = Yes`. |
| UniProt gz | 3 records | Reference cutinases (E9LVH8, E9LVH9, Q47RJ6). Reviewed (`sp|`), `PE=1` (protein-level evidence). |

**PAZy PET subset** — the backbone of any positive set:
**5058 PET assay rows across 311 proteins and 83 publications.**
Temperature recorded for 4995 rows (range 4–90 °C, median 50 °C; modes at 30, 40, 50, 60 and 70 °C).

> **Provenance warning.** `degraders_list.tsv` contains **99 rows citing DOI `10.1021/acscatal.5c03460`** —
> the same 2025 paper as the SI workbook — all PET, all with sequences, all `Spectrophotometry`.
> PlasticDB and PAZy have already absorbed the 2025 study. This is the single biggest leakage trap in
> the repository and is quantified in §4.

---

## 3. Label counts: positive, negative, uncertain

### 3.1 The critical distinction

Throughout this audit, two things are kept strictly apart:

- **Zero measured activity under a specified condition** — a real, usable negative *for that condition*.
- **Universal inactivity** — a claim no dataset here supports, and one we never assert.
- **Untested** — absence of evidence. Never labelled negative.

### 3.2 PAZy (protein-level)

| Category | Count |
|---|---|
| Proteins with ≥1 PET assay | **311** |
| Proteins with ≥1 positive PET measurement | **311** |
| Proteins whose PET measurements are *all* zero / non-detect | **0** |
| PET assay rows carrying a positive measurement | 3549 |
| PET assay rows that are zero / non-detect | 1509 |

**PAZy yields no protein-level negatives whatsoever.** Every protein in it is there *because* someone
published activity. The 1509 zero rows are condition-level failures of otherwise-active enzymes
(wrong temperature, wrong pH, wrong substrate form) — useful for a condition-specific model, useless
as "this protein cannot degrade PET".

This is textbook **positive-unlabelled (PU) data**, and it is why the existing cleaned set
(`outputs/explorer/clean/pet_active_proteins.csv`, 298 proteins) contains only `PET-active` (161) and
`PET-active (condition-dependent)` (137) — **no negative class at all**.

### 3.3 The 2025 screen (the only real source of negatives)

213 library enzymes assayed, each under 4–18 conditions (median 8 observations per enzyme):

| Proposed label | Count | Justification |
|---|---|---|
| **Positive** — product detected in ≥1 condition | **128** | direct experimental evidence |
| **Negative under tested conditions** — no product in any of ≥8 conditions | **57** | strong, condition-qualified negative |
| **Uncertain** — no product, but fewer than 8 conditions tested | **28** | too little coverage to call |
| **Untested** — in the 477-sequence library but never assayed | **264** | prediction targets, *not* negatives |

Per-enzyme table with nearest-neighbour annotations:
[tables/si2025_candidate_labels.csv](tables/si2025_candidate_labels.csv).

**Condition-level label counts** (the per-condition view, which is what we should actually model) —
full table at [tables/si2025_condition_labels.csv](tables/si2025_condition_labels.csv):

| Condition | n enzymes | positive | zero | positive rate |
|---|---|---|---|---|
| cryPow, 40 °C, pH 6.5 | 213 | 114 | 99 | 0.535 |
| cryPow, 40 °C, pH 7.5 | 213 | 106 | 107 | 0.498 |
| cryPow, 40 °C, pH 5.5 | 213 | 100 | 113 | 0.469 |
| cryPow, 60 °C, pH 6.5 | 161 | 47 | 114 | 0.292 |
| cryPow, 60 °C, pH 5.5 | 161 | 36 | 125 | 0.224 |
| aFilm, 40 °C, pH 6.5 | 78 | 12 | 66 | 0.154 |
| aFilm, 60 °C, pH 7.5 | 78 | 5 | 73 | 0.064 |
| aFilm, 60 °C, pH 4.5 | 63 | 2 | 61 | 0.032 |
| aFilm, 60 °C, pH 8.5 | 15 | 0 | 15 | **0.000** |

The three `cryPow, 40 °C` conditions are **near-balanced (47–54% positive) at n = 213** — ideal for
supervised learning. The `aFilm` and 8.5-pH conditions are severely imbalanced and some have no
positives at all; they are not independently modellable.

### 3.4 PETML zero-activity records

32 zero-`Activity` rows across 7 of the 33 workbooks
([tables/petml_zero_activity_records.csv](tables/petml_zero_activity_records.csv)):
13 IsPETase mutants (Cui 2021), 9 PETcan enzymes (Erickson 2022), 3 SbPETase mutants (Wang 2022),
3 in Chen 2021, 2 in Guo 2022, 1 each in Han 2017 and Sonnendecker 2021.

These are **mutant-level negatives under that study's single assay** — valuable for
mutation-effect modelling, but each is measured under its own unreported protocol (§5), so they
cannot be pooled into one negative class.

---

## 4. Sequence overlap and redundancy

Full matrix: [tables/sequence_overlap_summary.csv](tables/sequence_overlap_summary.csv).
Near-identity hits: `tables/besthits_*.csv`.

### 4.1 Exact duplicate sequences across sources

| Pair | Exact shared sequences |
|---|---|
| PETML ↔ **2025 SI library** | **0** |
| PETML ↔ PAZy | 16 |
| PETML ↔ PlasticDB | 16 |
| **2025 SI ↔ PAZy** | **102** |
| 2025 SI ↔ PlasticDB | 12 |
| PAZy ↔ PlasticDB | 57 |
| PlasticDB ↔ UniProt | 3 |

Internal duplicates: PETML 3 groups (§2.2); PlasticDB 16 groups (329 records → 311 unique);
PAZy and the 2025 library are internally duplicate-free.

### 4.2 Near-identity — the real leakage picture

Exact matching badly understates the problem, because point mutants are ~99.6% identical to their
wild type. Local alignment (BLOSUM62, identity over the shorter sequence) gives:

| Comparison | n | ≥99% | ≥95% | ≥90% | ≥70% | median best identity |
|---|---|---|---|---|---|---|
| 2025 assayed → PETML | 214 | **0** | 2 | 4 | 56 | **0.632** |
| 2025 assayed → PAZy | 214 | **128** | 131 | 137 | 181 | **1.000** |
| PETML → PAZy | 501 | **329** | 490 | 494 | 500 | 0.996 |

Three consequences:

1. **PETML is not 501 independent proteins.** It is ~66 scaffolds
   ([tables/petml_scaffold_structure.csv](tables/petml_scaffold_structure.csv)), and six of them
   account for 419 of 501 entries: IsPETase (244), LCC (54), TfCut2 (53), PES-H1 (30), PET2 (25),
   SbPETase (13). A random train/test split on PETML would put IsPETase point mutants on both sides
   and report a meaningless accuracy.
2. **PAZy overlaps both other sources heavily.** Using PAZy as a positive set and the 2025 screen as a
   test set leaks 128 of 214 test proteins into training. Any such evaluation is invalid.
3. **PETML vs the 2025 library is genuinely independent** — 0 exact matches, only 2 of 214 above 95%,
   median 63% identity. This is the one clean train/test boundary in the whole repository.

---

## 5. Assay compatibility assessment

**The 33 PETML workbooks cannot be pooled into one activity variable.** Evidence:

- **No units are recorded anywhere in the workbooks.** The column is simply `Activity`.
- The numeric ranges are mutually irreconcilable: Cui 2021 NanoPET spans 0–1.25; Bell 2022 0.01–1.1;
  Tournier 2020 15.4–104.4; Zeng 2022 3.16–562.3; Sagong 2022 427–1452; Zhang 2021 15.9–4055.
- Several studies are explicitly **relative** (wild type set to 1, 10 or 100 — see Han 2017, Brott 2021),
  i.e. each is normalised to a *different* reference enzyme.
- Substrate form, enzyme loading, reaction time, buffer and temperature differ per study and are not
  recorded in these files.

`logActivity` is a within-study transform, not a cross-study scale. **Treat each PETML workbook as its
own ordinal series.** Cross-study comparison is only defensible as *rank within study* or
*fold-change versus that study's own wild type*.

By contrast:

- **The 2025 screen is internally compatible by construction** — one laboratory, one protocol,
  shared blanks and a shared LCC-ICCG control, with enzyme-normalised product units.
  This is the only dataset here where absolute values can be compared across proteins.
- **PAZy assays are heterogeneous but self-describing**: units are carried per measurement
  (`mg/L` 2130, `%` 2060, `µmol aromatic products/mg enzyme` 1836, `µM` 1040, …) alongside
  12 distinct `metric_type` values. Usable **after** filtering to one metric type and one unit,
  not in aggregate.

**Replicate structure in the 2025 screen** (2158 sample × condition pairs): 1262 pairs have 2
replicates, 872 a single measurement. 1541 pairs are consistently zero, 577 consistently positive,
and **only 40 pairs disagree** between replicates (one zero, one positive) — a ~1.9% replicate
disagreement rate. The screen is reproducible enough to label from, and those 40 borderline pairs
should be marked uncertain rather than forced either way.

---

## 6. Proposed training and independent validation sets

### Set A — primary supervised dataset (recommended)

- **Source**: 2025 screen, condition `cryPow, 40 °C` at pH 5.5 / 6.5 / 7.5.
- **Size**: 213 enzymes, 100–114 positive, 99–113 negative — near 50/50.
- **Labels**: positive = product detected; negative = no product *under that exact condition*.
- **Why**: one protocol, explicit controls, balanced, and condition-qualified.

### Set B — independent validation

- **Source**: PETML wild-type scaffolds only (66 scaffolds, excluding engineered point mutants).
- **Why it is independent of Set A**: 0 exact sequence overlap, median 63% identity, only 2 of 214
  above 95%.
- **Caveat**: labels must come from PAZy/literature assay records, not from the uncalibrated
  `Activity` column, and the overlap in §4.2 must be removed first.

### Set C — prediction targets (never labelled)

- **264 sequences** in the 2025 library that were never assayed, plus PlasticDB entries that are
  annotation-only. These are exactly the "previously untested candidates" the project aims to rank.

### Set D — mutation-effect data (separate task, do not mix)

- PETML's 435 engineered variants with within-study activity and 21 sheets of Tm data. Appropriate for
  a *stability* or *mutation-effect* model, scored within study. Note that the four `Cui et al, 2021
  (NanoPET)` prediction sheets are computational and belong in neither training nor test.

**Splitting rule for all of the above**: group by sequence cluster (≤70% identity), never at random.
The existing `outputs/explorer/network/` identity data and `identity_group_70` column in
`prediction_dataset.csv` already provide this grouping.

---

## 7. Scientific limitations

1. **No true protein-level negatives exist outside the 2025 screen.** PAZy, PlasticDB and the
   literature record successes. A global "PET-degrader vs non-degrader" classifier would be trained
   against an unlabelled background, and its apparent accuracy would be an artefact.
2. **Publication bias is severe and structural.** 244 of 501 PETML entries are IsPETase derivatives.
   The literature over-samples a handful of scaffolds that already worked. A model trained on this
   learns "looks like IsPETase or LCC", not "degrades PET".
3. **Leakage is easy to introduce accidentally**, because PAZy and PlasticDB have already ingested the
   2025 paper (§2.4, §4.2). Any split must be made on sequence identity, not on source file.
4. **Cross-study activity values are not comparable** (§5), so regression on pooled PETML activity is
   not defensible.
5. **Condition dependence is first-order, not a nuisance.** The same 213 enzymes go from a 53.5%
   positive rate (cryPow, 40 °C, pH 6.5) to 0% (aFilm, 60 °C, pH 8.5). Any claim of "active" without
   a stated condition is close to meaningless.
6. **Class imbalance varies by condition** from 0.535 down to 0.000 positive rate. Only the
   `cryPow, 40 °C` conditions support a balanced classifier; the rest need either pooling,
   class weighting, or to be dropped.
7. **Small absolute sample size.** 213 labelled enzymes, and far fewer independent sequence clusters.
   This bounds model complexity: regularised linear models or small ensembles over interpretable
   features, not deep networks trained from scratch.
8. **Missing sequences elsewhere**: 2008 of 2535 `degraders_list.tsv` rows have no sequence, and
   PlasticDB includes `NA` accessions — those rows cannot enter a sequence model at all.
9. **Assay sensitivity floors are unknown.** A zero means "below this assay's detection limit",
   not "no catalysis". Our negatives are detection-limited, and the report should say so.

---

## 8. Recommended modelling approach

**Recommendation: a condition-specific binary classifier, with grouped splits and a PU-aware framing.**

| Option | Verdict |
|---|---|
| Global protein-level "PET-active vs not" classifier | **Reject.** No valid negative class (§3.2). Would be a PU problem disguised as classification. |
| **Condition-specific classifier** (one condition, or condition as a feature) | **Recommended.** Matches how the data was actually generated; uses the 57 defensible negatives honestly; near-balanced at `cryPow, 40 °C`. |
| Regression on activity magnitude | **Reject for pooled PETML** (§5). *Possible later*, within the 2025 screen only, on `umol_product_per_mg_enzyme`, where units are consistent. |
| Mutation-effect / Tm model on PETML | **Viable as a separate, clearly-labelled sub-study** (Set D), never merged with Set A. |

Concretely: label `y = activity detected at (substrate, T, pH)`; features from sequence
(composition, k-mers, physicochemical descriptors, catalytic-motif presence — the `pet_explorer`
feature code already computes these); train with **grouped cross-validation at ≤70% identity**;
benchmark against the paper's own reported AUROCs (sheet `fig5a`, 44 model × condition results, spans
**0.41–0.93**: best-case 0.93 for their supervised model and 0.87 for the starting HMM, but *below
chance* in the worst conditions — a published yardstick, and a warning that per-condition performance
varies enormously); and always report against a shuffled-label null,
as the existing `null_baseline.csv` work already does.

**Can we predict previously untested PET-degrading candidates?** Yes — within a defensible claim:
we can rank the 264 untested library sequences, and any new sequence, by *predicted probability of
detectable activity under a named condition*, and report the nearest characterised relative and its
identity alongside every prediction. We cannot, and should not, output "this enzyme degrades PET".
That framing matches what the README already promises — a *promising candidate*, not proof.

---

## 9. Recommended next steps

1. **Build a unified, provenance-tagged protein table** (new module, e.g. `pet_explorer/audit.py` or a
   `curation` module) with one row per unique sequence and columns: `sequence_sha1`, sources it appears
   in, accessions, label, label basis, condition, and evidence DOI. Deduplicate on sequence, not on name
   — this resolves `BbPETase`/`BurPL` and the two mutation-order duplicates.
2. **Materialise the four sets A–D** as explicit CSVs under `outputs/dataset_audit/` or a new
   `outputs/modelling/`, each carrying its exclusion list, so leakage removal is auditable.
3. **Compute the identity-based grouping across the combined set** (not just the 298-protein clean set)
   and store cluster IDs for grouped splitting.
4. **Then, and only then, train** the condition-specific classifier on Set A, validate on Set B,
   and score Set C.
5. **Re-check the 40 disagreeing replicate pairs** and mark them uncertain before training.
6. Defer any folder reorganisation until after step 2, so that the backend and frontend — which read
   `outputs/explorer/` by fixed column names — keep working.

---

## 10. Proposed final folder structure

Nothing below has been created or moved; this is a proposal for discussion.

```
Bioinformatics-Group-Project/
├── data/                          # unchanged, read-only, never modified
│   ├── raw/
│   │   ├── pazy/                  # pazy_proteins.fasta, .csv, polymer_assays.json.gz
│   │   ├── plasticdb/             # PlasticDB.fasta, degraders_list.tsv
│   │   ├── uniprot/               # uniprotkb_*.fasta.gz
│   │   ├── petml/                 # the 33 study workbooks + sequences.fasta
│   │   └── acs2025/               # cs5c03460_si_002.xlsx
│   └── README.md                  # provenance, download date, DOI per source
│
├── pet_explorer/                  # existing analysis package (unchanged)
│   ├── curation.py                # NEW: unified protein table, dedup, provenance
│   └── labels.py                  # NEW: condition-specific label construction
│
├── outputs/
│   ├── dataset_audit/             # THIS AUDIT (new, self-contained)
│   ├── explorer/                  # existing pipeline outputs (untouched)
│   └── modelling/                 # NEW: sets A–D, splits, model results
│       ├── sets/                  # train/validation/targets CSVs + exclusion lists
│       └── models/
│
├── backend/  frontend/  app/  notebooks/  tests/     # unchanged
└── README.md
```

Two constraints on any future move: `backend/tests` assert against column names in
`outputs/explorer/`, and `pet_explorer/config.py` hard-codes input paths — both must be updated in the
same commit as any relocation, and the 33 workbooks plus the new data files are still untracked in git,
so they should be committed (or explicitly git-ignored with a documented download script) before
anything is reorganised.

---

## 11. Files produced by this audit

| Path | Contents |
|---|---|
| `outputs/dataset_audit/REPORT.md` | This report |
| `outputs/dataset_audit/audit_statistics.json` | Every statistic quoted above, machine-readable |
| `tables/source_inventory.csv` | 41 source files: format, size, contents, provenance |
| `tables/petml_sheet_inventory.csv` | 37 PETML sheets: columns, row counts, activity/Tm ranges, zeros, FASTA linkage |
| `tables/si2025_condition_labels.csv` | 20 conditions × positive/zero counts and positive rate |
| `tables/si2025_candidate_labels.csv` | 213 enzymes: observations, conditions, proposed label, nearest PETML and PAZy neighbour |
| `tables/sequence_overlap_summary.csv` | Exact-sequence overlap between all five sources |
| `tables/besthits_SIassayed_to_PETML.csv` | Per-enzyme nearest PETML relative and identity |
| `tables/besthits_SIassayed_to_PAZy.csv` | Per-enzyme nearest PAZy relative and identity |
| `tables/besthits_PETML_to_PAZy.csv` | Per-PETML-entry nearest PAZy relative and identity |
| `tables/petml_zero_activity_records.csv` | 32 zero-activity records with source workbook |
| `tables/petml_scaffold_structure.csv` | 66 scaffolds and variant counts |
