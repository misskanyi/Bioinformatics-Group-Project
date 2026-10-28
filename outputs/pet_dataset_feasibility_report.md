# PET-Active vs PET-Inactive Dataset Feasibility Report

**Project:** Identification of PET plastic-degrading enzymes using bioinformatics and machine learning
**Analysis date:** 27 October 2026
**Code:** `analyze_pet_dataset.py` (run with `.venv/bin/python analyze_pet_dataset.py`)
**Status:** Data feasibility check only. **No machine-learning model was trained.**

---

## 1. Short answer

| Question | Answer |
|---|---|
| Is there enough real PET data? | **Yes, for PET-active enzymes.** 298 unique PET-active proteins have a valid sequence and reliable experimental evidence. |
| Can we reliably identify PET-active proteins? | **Yes.** 304 proteins show measured PET breakdown (products released, mass loss, conversion) in at least one assay. |
| Can we reliably identify PET-inactive proteins? | **No, not enough of them.** Only 4 proteins were tested and never showed PET breakdown, and **none of those 4 has a sequence in our files.** |
| Is PET-active vs PET-inactive ML feasible? | **No.** We have 298 usable active examples and **0** usable inactive examples. |
| Most realistic alternative | Unsupervised **sequence clustering and characterisation of the 298 experimentally verified PET-active enzymes**. Optional, harder extension: predicting whether PET breakdown is detected **under given assay conditions**. |
| Do we need more data? | Not for the clustering project. Binary classification would need experimentally confirmed inactive proteins **with sequences**. These files do not contain them. |

---

## 2. What is in the six files (Step 1)

| File | Format | Records | What it contains | Key field |
|---|---|---|---|---|
| `pazy_proteins_sequences.csv` | CSV | 301 | `protein_id` (int), `protein_name`, `amino_acid_sequence` | `protein_id` |
| `pazy_polymer_assays.json.gz` | gzipped JSON | 579 protein-x-paper records, **7,195 assays**, 462 proteins | Detailed experimental assays: substrate, material, conditions, detection method, measurements | `protein_id` |
| `pazy_proteins.fasta` | FASTA | 301 | Same 301 sequences as the CSV (all identical, checked) | header = `protein_id` |
| `PlasticDB.fasta` | FASTA | 329 | Enzyme sequences linked to plastics in the literature (186 mention PET) | header `id\|enzyme\|organism\|plastics\|GenBank` |
| `degraders_list.tsv` | TSV | 2,535 rows, 933 organisms | Organism–plastic reports; 527 rows include an enzyme sequence | none shared with PAZy (matched by exact sequence) |
| `uniprotkb_..._2026_10_27.fasta.gz` | gzipped FASTA | 3 | E9LVH8, E9LVH9 (*Thermobifida cellulosilytica* cutinase fragments), Q47RJ6 (*T. fusca* cutinase TfH) | UniProt accession |

### How the assay JSON is organised

Each JSON entry = **one protein in one publication**. Inside it, `assays[]` holds the experiments. Each assay has:

- `substrate`: the plastic. Values: PET, PA, PLA, PHA, PBS, PEF, PUR, PBAT, NR, PC.
- `material`: name, form (film, powder…), crystallinity, pretreatment.
- `conditions`: temperature, pH, duration, how pure the enzyme was, plus free-text `additional_conditions`.
- `detection_methods`: e.g. HPLC, UV absorbance.
- `measurements[]`: `metric_type`, `analyte`, `value`, `unit`, `qualifier` (`~` digitised from a figure, `<`, `>`), and sometimes `categorical_result` (`detected`, `positive`, `not_detected`, `negative`).
- `degradation_chemistry`: a description written at publication level.

**Important finding:** the JSON has **no "active / inactive" field**. Activity has to be worked out from the measurements. Also:

- `degradation_chemistry` is text about the paper as a whole. It appears even on assays that measured zero, so it **cannot** be used as a per-assay result.
- 3,198 PET measurements are exactly 0 (or ≈0). Many come from time-zero samples or from conditions where an otherwise active enzyme did nothing. **A zero does not mean the protein is inactive** (see Step 3).
- PAZy files contain **no organism field**. Organism was found only by matching sequences exactly to PlasticDB, degraders_list or UniProt. This worked for 57 of 301 proteins.

### Data quality checks

- CSV: no missing values, no duplicate IDs, no duplicate sequences, all sequences use only the 20 standard amino-acid letters.
- CSV and PAZy FASTA match exactly (301/301).
- Protein names in JSON and CSV agree for every shared ID. The only difference is capitalisation (`ISPETase` vs `IsPETase`).
- Sequence length: 178–491 aa (median 297).

---

## 3. PET-related experiments (Step 2)

| Substrate | Assay records | Unique proteins |
|---|---|---|
| **PET** | **5,058** | **311** |
| PA (nylon) | 564 | 68 |
| PLA | 429 | 57 |
| PHA | 340 | 39 |
| PBS | 195 | 28 |
| PEF | 146 | 7 |
| PUR (polyurethane) | 128 | 34 |
| PBAT | 124 | 24 |
| NR (natural rubber) | 124 | 8 |
| PC | 87 | 10 |

- Only `substrate == "PET"` was used. PEF (polyethylene furanoate) is a different polyester and was **not** counted as PET.
- PAZy has **no PE or PP assays.** PAZy covers plastics with hydrolysable bonds. PE/PP appear only in `degraders_list.tsv`, as organism-level reports.
- 7 assays filed under "PET" actually used **PET-G** (a glycol-modified copolyester, 6 assays) or an unspecified "polyester fibre" (1 assay). These were excluded.
- 72 PET assays were **time-zero samples** (duration = 0). These were excluded because nothing can have happened yet.
- The CSV holds exactly the PET-tested proteins: all 301 CSV proteins have PET assays. 10 PET-tested proteins have **no sequence** in any provided file.

Full assay-level table: `outputs/tables/pet_assay_records.csv` (5,058 rows, one per assay, with conditions and the rule that decided its outcome).

---

## 4. How PET activity labels were decided (Step 3)

### 4a. Each assay gets one outcome

| Assay outcome | Rule |
|---|---|
| **Degradation detected (POS)** | Any measurement of a *direct* breakdown metric > 0 (product concentration/amount/release rate, specific activity, conversion %, mass loss %, depolymerisation %). Also counts: categorical `detected`/`positive`, or an author-reported product-release / hydrolysis-rate constant > 0. |
| **Nothing detected (NEG)** | A direct metric is **exactly 0** (not a value read off a figure), or categorical `not_detected`/`negative` for the PET material or total products. There must also be **no** positive measurement in the same assay. |
| **Unclear** | Only indirect evidence (contact angle, fluorescence, turbidity OD600, relative activity), values reported only as "< threshold", "≈0" read off a figure, a single product reported absent (e.g. "no BHET" while TPA was released), or missing values. |
| **Excluded** | PET-G / unspecified material, or time-zero sample. |

Result: 3,432 POS, 1,451 NEG, 96 unclear, 79 excluded.

**Why these rules?** Early versions of the rules made mistakes. One protein (Thf42_Cut1) was wrongly called inactive because the paper said "no BHET was released", even though TPA and MHET *were* released. Another (Tcur0390) had a measured hydrolysis-rate constant at 50 °C. The final rules fix both cases.

**Detection limits:** the JSON almost never gives a numeric detection limit. "0" therefore means "nothing measured by that method", not "proven to be zero".

### 4b. Each protein gets one label

| Protein label | Rule | Count |
|---|---|---|
| **PET-active** | ≥1 POS assay, no NEG assays | **165** |
| **PET-active (condition-dependent)** | POS and NEG assays, and every NEG comes from a paper that *also* shows activity (e.g. active at 50 °C, not at 70 °C) | **139** |
| **Conflicting (across studies)** | One paper reports only no-detection, another paper reports activity | **1** (TfCut1) |
| **PET-inactive (tested conditions)** | ≥1 NEG assay, **no** POS assay anywhere | **4** |
| **Unclear** | No POS and no NEG | **2** (Tha_Cut1: surface-only evidence; E4: turbidity only) |

Your definition of "conflicting" is "both positive and negative findings under different conditions". By that definition, **140** proteins are conflicting (139 + 1). Almost all of them (139) are not true contradictions. Enzymes simply work under some conditions and not others. For example, TfH is inactive at 65 °C *without* calcium and active *with* it. For "can this enzyme degrade PET at all?", these 139 count as active.

**Confidence levels** (column `label_confidence`):
- Active = *high* if at least one quantitative positive used purified/commercial enzyme, otherwise *medium*. 293 high, 11 medium.
- Inactive = *high* if ≥3 negative assays, ≥2 distinct conditions, all with purified enzyme. Only **Cbotu_EstB** meets this (pH 6, 7, 8 at 50 °C). The other 3 inactive proteins rest on **one** assay each.

### The four PET-inactive proteins

| Protein | Evidence | Conditions tested | Sequence in files? |
|---|---|---|---|
| Cbotu_EstB | "did not show any activity on PET foil" (3 assays) | 50 °C, pH 6–8 | **No** |
| PpEst | "No hydrolysis of PET could be observed after 7 days" | pH 7, 7 days | **No** |
| PFL1 | "no hydrolysis of PET was detected" | 50 °C, pH 7.5, 72 h | **No** |
| BaCut1 | "exhibited no activity toward PET" | 30 °C, pH 8, 48 h | **No** |

PlasticDB contains *Clostridium botulinum* esterases (AKZ20828.1, AKZ20829.1) and a *Pseudomonas pseudoalcaligenes* polyesterase (AMW89397.1). These **might** correspond to Cbotu_EstB and PpEst, but no PAZy sequence exists to confirm the match, so they were **not** used.

---

## 5. Matching experiments to sequences (Step 4)

- Matching key: `protein_id`, the same integer in the JSON, CSV and FASTA. Names were checked as a second check.
- **311** PET-tested proteins → **301** have a sequence. **10 are unmatched** (81 PET assays): ApLip-Ec, RmL, TmFae-PETase, Nepenthesin-1, Lipozyme TL, GlacPETase (all active) and **all 4 inactive proteins**.
- **151** proteins in the JSON were never tested on PET. They were **not** treated as inactive.
- Sequences were valid: 0 sequences contain non-standard letters.
- Exact duplicates: **0**.
- Multiple assays of one protein were collapsed to **one row per protein** (`pet_protein_activity_summary.csv`). The original assays are kept in `tables/pet_assay_records.csv` for traceability.
- UniProt: Q47RJ6 exactly matches PAZy **TfH**. E9LVH8 and E9LVH9 (fragments) do not exactly match or sit inside any PAZy sequence.

### Sequence similarity (data-leakage check)

Biopython was used to align all 45,150 pairs of the 301 sequences (BLOSUM62, free end gaps; identity = identical positions ÷ length of the shorter sequence). Similar proteins were then grouped at different identity cut-offs (single-linkage).

| Measure | Value |
|---|---|
| Pairs ≥95% identical | 40 |
| Pairs ≥90% identical | 231 |
| Pairs ≥70% identical | 1,206 |
| Proteins with a ≥90% identical neighbour | 95 of 301 |
| Independent groups of usable active proteins at 70% identity | **110** |
| … at 40% identity | **36** |

What this means: the 298 active sequences are **not** 298 independent examples. Many are close variants, such as the many *Thermobifida* cutinases and IsPETase-like enzymes. A fair model test must keep each similarity group entirely in train *or* in test. Otherwise accuracy will be inflated (data leakage).

---

## 6. Feasibility summary table (Step 5)

Full table with explanations: `outputs/pet_dataset_quality_summary.csv`.

| Metric | Value | How it was calculated |
|---|---|---|
| Total protein sequences | 301 | Rows in PAZy CSV |
| Total PET-related assay records | 5,058 | `substrate == "PET"` |
| Unique proteins with PET assays | 311 | Unique `protein_id` in PET assays |
| Unique PET-active proteins | 304 | 165 always active + 139 condition-dependent |
| Unique PET-inactive proteins (tested conditions) | 4 | NEG assays only, never POS |
| Proteins with unclear evidence | 2 | No POS, no NEG |
| Proteins with conflicting evidence | 140 | 139 condition-dependent + 1 across studies |
| **Proteins with usable sequence + reliable label** | **298** | Valid sequence, high/medium confidence: **298 active, 0 inactive** |
| Exact duplicate sequences | 0 | Identical strings |
| Highly similar sequences (leakage risk) | 231 pairs ≥90%; 95 proteins with a ≥90% neighbour | Pairwise alignment |

---

## 7. Is PET-active vs PET-inactive classification feasible? (Step 6)

**No.** Reasons, in order of importance:

1. **No inactive class.** 0 usable inactive proteins with a sequence. Even if the 4 sequences were found, 298 vs 4 is a 75:1 imbalance. One or two test examples cannot give a meaningful accuracy, precision or recall.
2. **Inactive labels are weak anyway.** 3 of the 4 rest on one assay under one condition. "Not active at 30 °C for 48 h" does not mean "cannot degrade PET".
3. **Untested ≠ inactive.** Using the 151 non-PET-tested PAZy proteins, or non-PET PlasticDB entries, as negatives would invent labels. Many of them (cutinases, lipases) are the same kind of enzyme as known PET hydrolases.
4. **Negatives depend on conditions, not on the protein.** 1,451 "nothing detected" assays exist, but 140 of the 144 proteins with such assays are active under other conditions. The no-detection results reflect temperature, pH, substrate crystallinity and time.
5. **Negatives come from very few studies.** 97% of no-detection assays come from just two papers (DOI 10.1038/s41467-022-35237-x: 774; DOI 10.1021/acscatal.5c03460: 630). A model would learn those labs' protocols.
6. **Redundancy.** The 298 actives collapse to 110 groups at 70% identity and 36 at 40%.
7. **Condition differences.** PET assays span 4–90 °C, pH 4.5–11, films vs powders vs nanoparticles, and 15 minutes to 30 days. Outcomes from different papers are not directly comparable.

---

## 8. Alternative ML tasks (Step 7)

### Option A: Sequence clustering of verified PET-active enzymes (recommended)

- **Labels needed:** none for training (unsupervised). Experimental evidence is used only to choose which proteins go in (298 verified actives).
- **Data available:** 298 valid sequences, plus 165/139 "always vs condition-dependent" activity, temperature ranges and assay counts per protein for interpreting clusters.
- **Method idea:** turn sequences into numbers (amino-acid composition, dipeptide/k-mer frequencies, physicochemical properties, or protein language-model embeddings). Then use k-means / hierarchical clustering / UMAP. Compare the clusters with the alignment-based groups computed here (36 groups at 40%, 110 at 70%). Ask whether clusters relate to activity temperature or condition-dependence.
- **Limitations:** no negative class, so it cannot predict "will degrade PET". Organism known for only 57 of 301 (from these files). Results describe the diversity of *known* PET hydrolases.
- **Feasibility: high.** Everything needed is already in the files.

### Option B: Classification of PET-associated enzyme families

- **Labels needed:** *verified* family annotations (Pfam / InterPro / ESTHER), e.g. cutinase-like α/β-hydrolase vs lipase vs other.
- **Data available:** none verified in these files. PAZy has no family field. PlasticDB has free-text names only (PETase 133, depolymerase 50, hydrolase 35, esterase 31, cutinase 29, lipase 13…). These names are author-chosen and overlap. "PETase" is a function name, not a family.
- **Limitations:** would need an extra annotation download. Families would be very unbalanced, and family is largely predictable from sequence similarity alone, so the task is easy but not very novel.
- **Feasibility: medium**, and only after adding InterPro/Pfam annotations.

### Option C: Condition-level prediction ("is PET breakdown detected under these conditions?")

- **Labels needed:** assay-level POS / NEG, which **do** exist: 3,432 vs 1,451.
- **Data available:** 140 proteins with both outcomes. Features = sequence features + temperature, pH, substrate form, crystallinity, duration. A cleaner subset: 25 proteins from one standardised screen (same lab, same protocol, ~30 conditions each).
- **Limitations:** assays are not independent. Test splits must be grouped by protein and by similarity group. Negatives come mostly from 2 studies, so study effects are a risk. The model mainly learns condition effects such as temperature.
- **Feasibility: medium-low** for a semester. Defensible only with grouped cross-validation and careful wording. Good as an extension.

### Not recommended: PET vs "other plastics" using PlasticDB

PlasticDB lists only *positive* associations: 186 PET-linked vs 143 other entries. "Not listed for PET" means "not reported", not "cannot degrade PET". This is positive-unlabelled data and would repeat the untested-as-negative mistake.

---

## 9. Do we need more data?

- **For Option A:** no. The provided files are enough.
- **For true binary classification:** yes. Needed:
  1. Sequences of the 4 inactive and 6 unmatched active proteins (from UniProt / GenBank, via each protein's PAZy entry).
  2. Many more **experimentally tested, inactive** proteins with sequences, ideally ≥50 from several independent similarity groups and several labs. These files do not contain them.
- **Recommended extras even for Option A:**
  - organism / taxonomy for each protein (UniProt or NCBI). This lets you check the word "bacterial" in the title. Organism is currently known for only 57/301. The set also appears to include non-bacterial enzymes, e.g. the *Thermomyces lanuginosus* (fungal) lipase "Lipozyme TL" and Nepenthesin-1 (a pitcher-plant protease; this is from general knowledge, not from the files).
  - InterPro / Pfam domain annotations, to interpret clusters (and to enable Option B).

---

## 10. Suggested title and research question

**Title:**
> *Sequence-Based Clustering and Characterisation of Experimentally Verified PET-Hydrolysing Enzymes Using Bioinformatics and Machine Learning*

**Research question:**
> *Do experimentally verified PET-hydrolysing enzymes form distinct groups based on their amino-acid sequence features, and do these groups relate to their reported activity conditions (temperature and condition-dependence)?*

Notes:
- "Bacterial" was dropped because the provided files cannot confirm every enzyme is bacterial. Put it back only after adding taxonomy and filtering to bacteria.
- If Option C is added as an extension: *"Can sequence and assay-condition features predict whether PET hydrolysis is detected under specific experimental conditions?"*
- Explain to the lecturer why the original binary question was changed: it needs experimentally confirmed inactive proteins, and the data has 0 usable ones.

---

## 11. Output files

| File | Content |
|---|---|
| `analyze_pet_dataset.py` (project root) | Reproducible analysis |
| `outputs/pet_protein_activity_summary.csv` | One row per PET-tested protein: label, confidence, evidence counts, conditions, organism, cluster IDs, nearest neighbour, sequence |
| `outputs/pet_dataset_quality_summary.csv` | All counts with explanations |
| `outputs/tables/pet_assay_records.csv` | Every PET assay with its outcome and reason |
| `outputs/tables/dataset_inventory.csv` | File-by-file inspection |
| `outputs/tables/assays_by_substrate.csv` | Substrate counts |
| `outputs/tables/pairwise_identity.csv` | 45,150 pairwise identities |
| `outputs/tables/redundancy_clusters_by_threshold.csv` | Groups at 30–100% identity |
| `outputs/tables/standardised_screen_labels.csv` | 25-protein standardised screen subset |
| `outputs/tables/plasticdb_enzyme_name_keywords.csv` | PlasticDB name keywords |
| `outputs/figures/01–06_*.png` | Substrates, outcomes/labels, evidence per protein, redundancy, sequence availability, temperatures |
| `outputs/analysis_console_log.txt` | Console output of the last run |
