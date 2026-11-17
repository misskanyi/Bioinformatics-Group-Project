# Evaluation of the Newly Added Datasets

**PET Enzyme Explorer — were the new datasets worth adding?**

Research question: *How can protein sequence analysis and machine learning help identify promising
enzyme candidates for PET plastic recycling?*

Evaluation date: 2026-11-04. Read-only. Nothing in `data/`, `pet_explorer/`, `backend/`, `frontend/`
or any existing `outputs/` subfolder was moved, renamed, modified or overwritten. No model was trained.
This report is additive to the earlier audit at `outputs/dataset_audit/REPORT.md`, which it verifies
rather than replaces.

Supporting tables: [dataset_comparison.csv](dataset_comparison.csv),
[dataset_recommendations.csv](dataset_recommendations.csv),
[ml_feasibility_summary.csv](ml_feasibility_summary.csv),
[overlap_summary.csv](overlap_summary.csv), and [tables/](tables/).

---

## 1. Verdict

> **YES — but the value is concentrated in a single file.**

Of the 35 newly added files, **one** (`cs5c03460_si_002.xlsx`) changes what the project can do.
The other 34 (`sequences.fasta` and the 33 study workbooks) broaden the sequence and biological
analysis but cannot supply training labels.

The decisive finding is this:

> The group's meeting minutes of 28 October 2026 (MIN 03/2026) record that the project would **not**
> build an activity classifier, because *"there are no usable sequences for proteins confirmed not to
> degrade PET."* That was correct at the time. **It is no longer correct.** The 2025 supplementary
> workbook contains 56 enzymes with no detectable product across at least 8 standardised conditions,
> measured in one laboratory, against explicit blank and positive controls.

The single most telling statistic in this evaluation:

| Source of the 2025 screen | Positives captured | Negatives captured |
|---|---|---|
| PAZy (`pazy_polymer_assays.json.gz`) | **99** | **0** |
| `cs5c03460_si_002.xlsx` | 128 | **84** (56 broadly tested) |

PAZy had already ingested the 2025 paper — but, being a curated database of *published activity*, it
ingested only the enzymes that worked. **Every negative observation in this project exists in exactly
one file, and that file is new.** This is the positive-unlabelled problem made concrete, and it is the
entire argument for the new data.

---

## 2. What was verified, and what the previous audit got wrong

The earlier audit is **substantially reliable**. Every load-bearing number I recomputed from the raw
files reproduced, including all cross-source sequence identities — the hardest numbers to get right.

**Reproduced exactly:** 33 workbooks / 37 sheets / 711 protein mentions / 501 unique names; 501 FASTA
records → 498 unique sequences with the same 3 duplicate groups; complete and exact name↔FASTA linkage
(0 unmatched in either direction); 32 zero-activity rows; the SI structure (477 library rows, 3856
assay rows, 220 blanks, 20 conditions) and the **entire condition × label table**; exact overlaps
(PETML↔SI = 0, SI library↔PAZy = 102, PETML↔PAZy = 16, PAZy↔PlasticDB = 57); identity distributions
(SI→PETML median 0.632 with 2 of 212 above 95%; SI→PAZy 128 at ≥99%; PETML→PAZy 329 at ≥99%);
PAZy PET totals (5058 assays, 311 proteins, 83 publications); and the four computational prediction
sheets in `Cui et al, 2021 (NanoPET).xlsx`.

**Corrections — all minor, none changing a conclusion:**

| Audit says | Verified value | Why it differs |
|---|---|---|
| 213 library enzymes assayed | **212** | `RFP` is a non-enzyme control, not a library member (see §3.4) |
| 477 library members / 264 untested | **476 / 263** | same reason |
| 57 negatives, 28 uncertain | **56**, 28 | same reason |
| 26 sheets carry `Activity`, 21 carry `Tm` | **28** and **25** | counted sheets with ≥1 non-null value |
| 2158 replicate pairs, 40 disagreeing (1.9%) | **2122**, **39** (1.84%) | controls excluded from the enzyme set |
| ~66 PETML scaffolds | **56** at ≥99% identity, **27** at ≥70% | audit's figure was name-based; this is sequence-based |
| 5058 PAZy PET "assays" | 5058 assays → **8439 measurements** | an assay can carry several measurements |

---

## 3. What the previous audit missed

These are new, and three of them materially change the recommendations.

### 3.1 PAZy ingested the 2025 paper's positives and none of its negatives

1084 PAZy PET assay rows (3672 measurements, 99 proteins) cite DOI `10.1021/acscatal.5c03460`.
**All 99 have a positive value; not one is an all-zero enzyme.** The current pipeline's model target is
built from exactly these 99 (`pet_explorer/prediction.py`). So the project has been training on a
filtered, positives-only view of the very screen whose negatives it needed. This is both the strongest
argument for the new file and an explanation of why the existing model does not work.

### 3.2 The 263 "untested" sequences are not untested candidates — they failed expression

This contradicts the earlier audit's "Set C", which framed them as *"exactly the previously untested
candidates the project aims to rank."*

| | Assayed (212) | Not assayed (263) |
|---|---|---|
| Median expression | **0.568 mg/mL** | **0.044 mg/mL** |
| Interquartile range | 0.233 – 1.090 | 0.030 – 0.061 |
| Full range | 0.100 – 2.423 | −0.020 – 0.118 |
| Median µg recovered | 139.1 | 10.9 |

The ranges barely touch: the lowest assayed value (0.100) is above the highest unassayed value (0.118)
in all but a handful of cases, and four unassayed sequences are at or below zero yield. They were not
assayed because **not enough protein could be produced**. Ranking them as promising candidates for the
laboratory would be recommending proteins that already failed the first laboratory step — and the
project would be presenting an expression failure as a discovery opportunity. The prompt's instruction
not to treat unlabelled proteins as untested without checking the evidence is exactly right here.

### 3.3 The real sample size is 69 families, not 212

The audit established that PETML collapses to a handful of scaffolds, but never asked the same question
of the 2025 screen — the dataset it recommends training on.

Single-linkage clustering of the 212 assayed enzymes (local BLOSUM62, identity over the shorter
sequence):

| Identity threshold | Clusters | Largest cluster |
|---|---|---|
| ≥99% | 212 | 1 |
| ≥90% | 171 | 27 |
| **≥70%** | **69** | **85 (40% of all data)** |
| ≥50% | 7 | 200 |

At 50% identity, 200 of 212 fall into one cluster — the library was built by homology search, so it is
one superfamily by construction. **For grouped cross-validation at 70% identity the effective sample
size is 69, and one group carries 40% of the data.** That is the number that bounds what the project
can claim, not 212.

Worse, the label is largely a property of the family: of the 69 families, **30 are purely positive, 21
purely negative, and only 3 contain both**. A baseline that predicts each enzyme from its own family's
rate (leave-one-out) scores **0.692 accuracy against a 0.538 majority-class baseline**. Any sequence
model must be benchmarked against *that*, not against 0.5, or it will take credit for rediscovering
homology.

### 3.4 There is a genuine non-enzyme negative control in the library

`RFP` (red fluorescent protein, 225 aa, no accession, no round or dataset assignment) sits in the
`Rounds` sheet and was assayed in 48 wells across 18 conditions, with **zero product in every one**.
This is a true biological negative — a protein with no hydrolase function at all. It adds no training
mass, but it is an excellent sanity anchor: any model scoring RFP as active is broken.

### 3.5 Measurements are thresholded and rounded, so "zero" has a defined meaning

The smallest non-zero `mM_product` is **0.03**, values step by exactly 0.01, there are no negative
values, and `A260`/`A280` are **exactly 0.0** wherever product is zero — as are all 220 blanks, with
zero variance. The published table has been background-subtracted, floored at zero and rounded.

This cuts both ways. It is *good* for labelling: the threshold is uniform, so a zero means the same
thing in every well. It is *bad* for the claim strength: a zero is "below ~0.03 mM under this assay",
and the blanks give no noise estimate because they were clipped too. It also means **18 of the 128
positives are marginal** — their maximum across all conditions is ≤0.05 mM, within two rounding steps
of the floor — and 14 enzymes are positive in only a single observation.

### 3.6 The screen is an adaptive experiment, not a random sample

| Round | Dataset family | n assayed | Positive rate |
|---|---|---|---|
| RND1 | DP | 53 | 56.6% |
| RND2 | TEP | 73 | 50.7% |
| RND3 | ESM | 86 | **70.9%** |

Round is **perfectly confounded** with dataset family, and 58 of the 69 identity families appear in
only one round. RND3 was selected *by the paper's own machine learning model* trained on earlier
rounds — its higher hit rate is the paper's result, not a natural base rate. Pooling all three rounds
inherits that selection. This does not invalidate training, but it means the positive rate is not a
population estimate and the model is learning partly from a model-selected sample.

### 3.7 The paper publishes the realistic performance ceiling

Sheet `fig5a` holds 44 model × condition AUROC results on this exact data:

- Best supervised: **0.91–0.93** (aFilm, 60 °C, pH 7.5)
- `cryPow` conditions — the ones with balanced labels: **~0.78**
- **A zero-shot "starting HMM", with no training at all: 0.83–0.87**
- A *"lit. supervised"* model trained on literature data of the PETML kind: **0.87–0.93**

Two lessons. First, a plain homology model is already strong, so the bar for "our ML worked" is high.
Second, the literature-trained model transferring to this screen is direct published evidence that
**PETML-style data can inform predictions on the 2025 library** — which raises PETML's value above
"exploratory only", provided within-study normalisation is done properly.

For comparison, the project's current model (`outputs/explorer/prediction/model_comparison.csv`) scores
**ROC AUC 0.556 with a permutation p-value of 0.32** — statistically indistinguishable from shuffled
labels.

---

## 4. Before and after

Full table: [dataset_comparison.csv](dataset_comparison.csv). Counts are deduplicated on exact sequence;
sources are **never summed**.

| Measure | Before (original data) | After (with new data) |
|---|---|---|
| Unique amino acid sequences | **557** | **1411** (+854 new, +153%) |
| Experimentally measured PET proteins | 311 (PAZy) | 311 + 212 SI-assayed (100 sequences overlap) |
| Protein-level positive observations | 303 | 303 + 128 |
| **Protein-level below-detection observations** | **0** | **56** |
| Uncertain (tested too narrowly) | not representable | 28 |
| Independent families in the assayable set | n/a — no negative class existed | **69** |
| Experimental conditions | heterogeneous, per publication | standardised 2 × 2 × 5 grid |
| Units | 69 distinct units, 14 metric types | 9 normalised columns, one protocol |
| Replicates | not recorded | 1244 duplicated pairs, 1.84% disagreement |
| Explicit controls | none | 220 blanks, 252 LCC-ICCG, 1 RFP |
| Defensible independent validation | none | PETML ↔ SI (0 exact, median 63% identity) |

The 153% growth in unique sequences is real but should not be oversold: PETML's 480 new sequences
collapse to **27 families** at 70% identity, with 243 records in one of them.

---

## 5. Does this make the machine learning objective achievable?

**Yes — a narrowly-framed version of it, with honest reporting. No — the version implied by a global
"PET-degrader vs not" classifier.**

**A. Training data.** Yes, for the first time. 128 positives and 56 broadly-tested negatives under one
protocol. At `cryPow, 40 °C` the split is near-even (114/98 at pH 6.5). The 28 uncertain enzymes must be
excluded, not relabelled.

**B. Generalisation.** This is the weak point. 69 effective families, one holding 40% of the data, and
51 of 69 label-pure. A random split would be meaningless; a grouped split at ≤70% identity is mandatory,
and even then the variance across folds will be large. The honest framing is that the model is
predicting *family-level* activity propensity, and it must be reported against the 0.692
family-membership baseline rather than 0.5.

**C. Comparability.** The SI screen is internally comparable by construction. The 33 PETML workbooks are
**not** poolable: no units are recorded anywhere, ranges run from 0.01–1.1 to 15.9–4055, and 5 workbooks
contain an exact `1.0` while 4 contain an exact `100` — each normalised to its own reference enzyme.
Rank-within-study only.

**D. Validation.** A genuinely independent split exists, and only one: **PETML versus the 2025 library**
(0 exact matches, 2 of 212 above 95%, median 63% identity). PAZy cannot serve, because 128 of 212
assayed enzymes are ≥99% identical to a PAZy entry and PAZy already contains 99 of this screen's
proteins. PlasticDB and `degraders_list.tsv` are contaminated too — 99 degrader rows cite the 2025 DOI.

**E. Feature engineering.** Genuine improvement. 854 new sequences broaden composition, length and
physicochemical distributions; 234 melting temperatures support a stability analysis; 27 PETML families
plus 69 screen families give clustering, PCA and the similarity network far more structure than
PAZy alone. Motif analysis benefits most, because the engineered-variant series show which positions
tolerate change.

**F. Candidate discovery.** Weaker than it appears, per §3.2. The 263 unassayed sequences are expression
failures. Real candidate discovery must come from **scoring new sequences outside this library** —
UniProt/MGnify homologs — with every prediction reported alongside its nearest characterised relative
and that relative's identity.

### Recommended approach

| Option | Verdict |
|---|---|
| Global "PET-active vs not" classifier | **Reject.** No valid negative class outside one screen; PAZy is positive-unlabelled by construction. |
| **Condition-specific binary classifier** (`cryPow`, 40 °C) | **Recommended.** Matches how the data was generated; near-balanced; uses the 56 negatives honestly. |
| Logistic Regression | **Yes — the primary model.** 69 effective groups cannot support more. Interpretable coefficients also serve the biological discussion. |
| Random Forest | **Yes, as a comparator.** Already in the pipeline; expect high fold-to-fold variance. |
| PCA + Logistic Regression | **Yes, as a comparator.** Useful mainly because PCA is already a required visualisation. |
| Gradient Boosting | **Not justified.** With ~69 independent units it will overfit and add nothing a Random Forest does not. |
| Regression on activity magnitude | **Only within the SI screen**, on `umol_product_per_mg_enzyme`. Never on pooled PETML. |
| Mutation-effect / Tm model on PETML | **Viable as a clearly separate sub-study**, scored within study. |

Required reporting in every case: grouped CV at ≤70% identity, comparison against both the majority-class
and the **family-membership (0.692)** baselines, a label-permutation null, and confidence intervals.

---

## 6. Against the course requirements

The available course documents (`Computing_for_Bioinformatics_Course_Outline.pdf`, ICS 4301) give topics
and assessment weights — *Group presentations/Report, 10%* — but **no detailed marking rubric**. The
assessment below is therefore against the course's stated topics, not against a rubric I have seen.

| Course topic / project element | Effect of the new data |
|---|---|
| Biological databases, data retrieval, provenance | **Improved.** A DOI-identified primary source with full experimental metadata, alongside the curated databases. Also gives the project a real provenance lesson: PAZy filtered out the negatives. |
| Data cleaning and preprocessing | **Strongly improved**, and more demanding: deduplication on sequence, control rows, a detection floor, 3 duplicate groups, and the RFP control all have to be handled explicitly. |
| Exploratory analysis and visualisation | **Improved.** Condition-response curves, expression-vs-assay bias, Tm distributions, round-over-round enrichment. |
| Sequence alignment and conserved motifs | **Improved.** 854 new sequences; the engineered series make motif tolerance visible. |
| Clustering and biological interpretation | **Strongly improved.** 69 families with labels attached — clusters can now be interpreted against measured activity rather than described. |
| Supervised machine learning | **Unblocked.** This was impossible before and is now possible, in a condition-specific form. |
| Model evaluation and comparison | **Strongly improved.** A published external benchmark (0.78–0.93), a zero-shot HMM reference, and a family-membership baseline. |
| Conclusions and reproducibility | **Improved**, with a caveat: the group must update MIN 03/2026, which still records the decision not to build a classifier. |

**Still not adequately supported:** any claim of universal PET-degrading activity; any temperature
*optimum* prediction (the grid has only 40 and 60 °C); genetic algorithms and cloud/HPC (course topics
the project does not touch); and genuine candidate discovery, which needs an external sequence pool
rather than the 263 expression failures.

---

## 7. Recommendations

Full table with per-dataset reasoning: [dataset_recommendations.csv](dataset_recommendations.csv).

| Dataset | Recommendation |
|---|---|
| `cs5c03460_si_002.xlsx` | **KEEP — Primary ML training** |
| `sequences.fasta` (PETML) | **KEEP — Model validation, if scientifically justified; KEEP — Exploratory/biological analysis** |
| 33 PETML study workbooks | **KEEP — Exploratory/biological analysis; OPTIONAL for primary ML** |
| `Cui et al, 2021 (NanoPET)` prediction sheets | **EXCLUDE FROM MODELLING** — computational ΔΔG, not measurements |
| SI unassayed subset (263) | **OPTIONAL** — only with the expression-failure caveat stated |
| `pazy_polymer_assays.json.gz` | **KEEP — Exploratory/biological analysis; KEEP — Candidate discovery** (nearest-relative annotation) |
| `PlasticDB.fasta`, `degraders_list.tsv` | **KEEP — Exploratory/biological analysis** |
| `uniprotkb_*.fasta.gz` | **KEEP — Exploratory/biological analysis** |

No original source file should be deleted, and none was modified by this evaluation.

---

## 8. Answers to the ten questions

1. **Were the newly added datasets actually useful?** Yes, but unevenly. `cs5c03460_si_002.xlsx` is
   transformative. The other 34 files are useful for biological analysis and validation, not for labels.
2. **What new information did they contribute?** Above-detection *and* below-detection observations
   under one protocol with explicit controls; a standardised condition grid; replicates; expression
   yields; 234 melting temperatures; 854 new unique sequences; and a published performance benchmark.
3. **Did they improve our ability to build a supervised model?** Yes — they made it possible at all.
   Before, there were zero protein-level negatives.
4. **How many genuinely independent training examples do we have?** **212 enzymes, but only 69
   independent families at 70% identity**, one of which holds 85. Treat 69 as the real number.
5. **Which datasets should we train on?** `cs5c03460_si_002.xlsx`, condition `cryPow, 40 °C`
   (pH 5.5/6.5/7.5), 128 positives against 56 broadly-tested negatives, grouped at ≤70% identity.
6. **Which should we reserve for validation?** PETML wild-type scaffolds (`sequences.fasta`), the only
   set with no exact overlap and a median 63% identity to the training library. Labels for it must come
   from PAZy/literature, not the uncalibrated `Activity` column.
7. **Which are for biological analysis only?** The 33 workbooks, PlasticDB, `degraders_list.tsv`,
   UniProt, and the PAZy assay records. The four Cui prediction sheets are for methods discussion only.
8. **Do we have enough evidence for the research question?** For the narrow form — *can sequence
   analysis and ML rank enzymes by predicted activity under a named condition* — yes. For the broad
   form — *can we identify enzymes that degrade PET* — no, and no dataset here would support it.
9. **What gaps remain?** No negatives outside one laboratory; no detection-limit estimate; 69 effective
   families with one dominating; adaptive round design; no genuine untested candidate pool; only two
   temperatures; and PETML activity that cannot be pooled.
10. **What next?** See below.

### Next steps, in priority order

1. **Build a unified, provenance-tagged protein table** keyed on sequence SHA-1, with source, accession,
   label, label basis, condition and evidence DOI. This resolves the duplicate groups and makes the
   PAZy/SI overlap explicit and auditable.
2. **Materialise the label sets** as CSVs under a new `outputs/modelling/`, each carrying its exclusion
   list: training (SI `cryPow` 40 °C), validation (PETML wild-type scaffolds), excluded (uncertain,
   computational, controls), and prediction targets.
3. **Store 70%-identity family IDs** for every sequence, and use them for all splits.
4. **Then train** the condition-specific classifier, reporting against the majority-class, the
   family-membership (0.692) and the permutation baselines, with the paper's 0.78 as the external
   yardstick.
5. **Update the meeting minutes.** MIN 03/2026 records the decision not to build a classifier for lack
   of negatives. That decision should be formally revisited and the reason documented — it is also a
   good methodological narrative for the report.
6. **Reframe candidate discovery** away from the 263 expression failures and toward scoring external
   homologs, always reporting the nearest characterised relative and its identity.

---

## 9. Limitations of this evaluation

- Identity is computed by local BLOSUM62 alignment with a 4-mer prefilter (top 25–40 candidates per
  query). The prefilter is safe for *best*-hit identity but could in principle miss a remote homolog.
- Clustering is single-linkage, which is the conservative choice for leakage control — it merges
  aggressively, so 69 families is a *lower* bound on independence, not an upper one.
- PAZy positive/negative counts come from the nested `measurements` values; 231 PET measurement rows
  carry no numeric value and 8 proteins have none at all, so protein-level counts exclude them.
- I did not re-verify the earlier audit's per-sheet inventory or file-level metadata, by agreement —
  only the numbers that decisions depend on.
- No model was trained, so every performance figure quoted is either from the existing pipeline outputs
  or from the paper's own published benchmark sheets.
