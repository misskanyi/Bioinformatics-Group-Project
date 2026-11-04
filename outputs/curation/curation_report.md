# Unified Dataset Curation

**PET Enzyme Explorer — Phase 2. Preparing the data for supervised learning.**

Research question: *How can protein sequence analysis and machine learning help identify promising
enzyme candidates for PET plastic recycling?*

Curation date: 2026-11-04. No model was trained. No raw file in `data/` was modified, moved or renamed.
No previous report was overwritten. Produced by `pet_explorer/curation.py`, validated by
`tests/test_curation.py` (36 tests, all passing).

Reproduce with:

```bash
.venv/bin/python -m pet_explorer.curation     # ~100 s cold, ~4 s with the alignment cache
.venv/bin/python -m pytest tests/test_curation.py -q
```

Verified: deleting the alignment cache and re-running from scratch reproduces all six tables
**byte-identically**.

---

## 1. Method

The pipeline follows the KDD process. Phase 2 covers the first three stages only; the mining stage
stays deferred.

| KDD stage | What happens here |
|---|---|
| **Selection** | Load all 9 source families from `data/` — the 2025 SI workbook, the 33 PETML workbooks, PETML `sequences.fasta`, PAZy sequences and assays, PlasticDB, `degraders_list.tsv`, UniProt |
| **Preprocessing** | Normalise and hash every sequence; deduplicate on sequence, never on name; tag every observation with an evidence class |
| **Transformation** | Build the condition-specific target; compute identity groups; derive a leakage-free split and CV folds; classify candidate eligibility |
| **Data mining** | **Deferred** — awaiting approval |
| **Interpretation** | This report |

> **Note on sources.** The Data Mining & Machine Learning Recap slides referenced in the brief are not
> present in the workspace, so this pipeline follows the canonical KDD stages above. If the slides
> define different stage names or a different split protocol, say so and I will realign the structure.

### The identity key

Everything is keyed on `sequence_sha1` — the SHA-1 of the uppercased, whitespace-stripped,
stop-codon-stripped amino acid sequence. This is what resolves the naming problems the audit found:
`BbPETase` and `BurPL` are one protein published under two names, and two IsPETase mutants were listed
with their mutations in different orders. Name-based deduplication misses all three; sequence-based
deduplication catches them. A test asserts this.

### Evidence classes, kept strictly apart

| Class | Rows | Conditions recorded | Units | May it produce a training label? |
|---|---|---|---|---|
| `experimental_standardised_screen` | 3,824 | 3,824 (100%) | yes | **Yes** — this is the training signal |
| `experimental_curated_database` (PAZy) | 8,288 | 8,213 (99%) | 63 distinct units | No — positive-unlabelled by construction |
| `experimental_literature_relative_uncalibrated` (PETML) | 608 | 0 | **none recorded anywhere** | No — ordinal within study only |
| `computational_prediction` (Cui ddG sheets) | 103 | 0 | ddG, computed | **Never** — not a measurement |

---

## 2. What was built

| File | Rows | Contents |
|---|---|---|
| `proteins_master.csv` | **1,412** | One canonical record per unique sequence |
| `experimental_observations.csv` | **12,823** | One row per observation, conditions never collapsed |
| `condition_specific_labels.csv` | **212** | The supervised target at one named condition |
| `homology_groups.csv` | 1,412 | Identity groups at 50%, 70% and 90% |
| `split_assignments.csv` | 212 | Grouped train/test split **and** 5 CV folds |
| `candidate_eligibility.csv` | 1,412 | Who may be ranked later, and who may not |
| `split_diagnostics.json` | — | Leakage checks |
| `tables/pairwise_identities.csv.gz` | 155,208 | Cached alignment results |
| `tables/petml_external_validation_candidates.csv` | 501 | PETML external-validation screen |

### The protein registry

1,412 unique sequences, of which **975 were newly added in 2026** and 437 came from the original sources.

| Testing status | Newly added | Original | Total |
|---|---|---|---|
| `standardised_screen_measured` | 212 | 0 | **212** |
| `curated_database_measured` (PAZy) | 18 | 183 | 201 |
| `literature_uncalibrated_measured` (PETML) | 482 | 0 | 482 |
| `no_identified_testing_evidence` | 263 | 254 | 517 |

### The target condition

**Crystalline PET powder, 40 °C, pH 6.5.** Confirmed against the source protocol, as the brief required.
SI figure captions S4–S5 state the three yield-driven coverage tiers: 32 conditions in duplicate
(4 pH × 2 T × 2 substrates), 8 conditions (4 pH × 2 T × cryPow), and 4 conditions
(4 pH × 40 °C × cryPow). **The lowest tier is cryPow at 40 °C**, so every assayed enzyme — including
the lowest-yield ones — was tested at this condition. No enzyme is dropped for lack of coverage.

| Label | n | Rule |
|---|---|---|
| `detectable_activity` | **110** | product above the 0.03 mM floor in *every* replicate |
| `below_detection` | **98** | no product above the floor in *any* replicate |
| `uncertain` | **4** | replicates disagree — excluded from binary training |

13 of the 110 positives are flagged `is_marginal_positive` (maximum ≤ 0.05 mM, within two rounding
steps of the floor). They are kept as positives but flagged, so a sensitivity check is possible later.

**What `below_detection` means, exactly:** no product above 0.03 mM at cryPow / 40 °C / pH 6.5, in a
plate carrying a blank and an LCC-ICCG positive control. It does **not** mean the protein cannot
degrade PET. Every such row carries that caveat in its `label_basis`, and a test enforces the wording.

---

## 3. Homology grouping and leakage control

**Rule.** Single-linkage components over local BLOSUM62 alignments (gap open −11, extend −1), with
identity measured over the **shorter** sequence. Coverage is recorded but deliberately *not* required,
and single linkage merges aggressively — both choices err toward merging. For leakage control that is
the safe direction: the resulting group count is a **lower bound** on independence, never an inflated one.
Pairs are prefiltered by 5-mer Jaccard ≥ 0.02, far below what any pair at ≥50% identity achieves.

Groups are nested across thresholds (a test asserts this): 90% groups never straddle a 70% group.

### The structure this reveals

The 212 labelled enzymes form **59 groups at 70% identity**, and the distribution is severely uneven:

| | |
|---|---|
| Groups among the 208 trainable enzymes | **57** |
| Largest group | **85 enzymes — 40.9% of the dataset** |
| Second largest | 31 |
| Singletons | 42 |
| Label-pure groups | 50 of 57 (16 all-positive, 34 all-negative) |
| Label-mixed groups | **7** |

This is the single most important result of Phase 2. The nominal sample size is 208; the **effective**
sample size is 57, and one family carries two fifths of it.

### Is a leakage-free split feasible?

**Yes — and it is verified.** But it is not comfortable.

| Diagnostic | Value |
|---|---|
| Groups spanning both sides | **0** |
| Cross-split pairs at ≥70% identity | **0** |
| Maximum cross-split identity | **0.695** |
| Train | 159 (93 positive / 66 negative) across **43 groups** |
| Test | 49 (17 positive / 32 negative) across **14 groups** |
| Excluded | 4 (`uncertain`) |

The split holds whole groups out, ordering them by size and reserving every fourth, with the dominant
85-member group forced into training so it cannot swamp the test set. The result is genuinely
leakage-free: no held-out enzyme has a ≥70%-identical relative anywhere in training.

**But a single holdout is a weak evaluation here**, and the pipeline says so. With 57 groups and one
holding 40%, any holdout is either tiny or dominated by one family. `split_assignments.csv` therefore
also carries `cv_fold`, a grouped 5-fold assignment:

| Fold | n | Positive | Negative | Groups |
|---|---|---|---|---|
| 0 | 85 | 52 | 33 | **1** |
| 1 | 31 | 10 | 21 | 2 |
| 2 | 31 | 15 | 16 | 18 |
| 3 | 31 | 16 | 15 | 18 |
| 4 | 30 | 17 | 13 | 18 |

Fold 0 *is* the dominant family. That is not a bug in the fold assignment — it is the data's shape made
visible. When fold 0 is held out, the model is tested on one family; when it is in training, it
dominates. **Grouped cross-validation is the recommended evaluation, and per-fold results must be
reported separately, never as a single averaged number.**

---

## 4. Supporting sources: what can and cannot be used

### PETML as external validation

The evaluation report identified PETML as the only clean train/test boundary (0 exact overlap with the
2025 library, median 63% identity). Phase 2 tested whether that promise survives contact with the
labels, and the answer is **mostly no**.

| PETML entries | 501 |
|---|---|
| Look like engineered point mutants | 435 |
| Carry a curated (PAZy) activity label | 17 |
| **Wild type *and* labelled → usable as external test** | **17** |

The problem is not sequence overlap, it is labels. The PETML `Activity` column carries **no units in any
of the 33 workbooks**, and the scales are irreconcilable, so it cannot supply a label. Only entries
with an independent PAZy record can — and after removing engineered mutants, 17 remain.

**17 proteins is a real but small external check.** It is worth reporting as a secondary result; it is
not a substitute for the grouped CV. The candidates are listed in
`tables/petml_external_validation_candidates.csv`.

### PAZy, PlasticDB, UniProt

Retained in the registry and the observation table as provenance and annotation. PAZy zeros are
preserved with an explicit caveat in every `label_basis`, because a zero there is a condition-level
failure of an enzyme that is in the database precisely *because* it worked somewhere else. Per the
brief's constraint, no PAZy annotation is used as an independent experimental test label.

---

## 5. Candidate eligibility

The brief's rule — do not call an unlabelled protein a promising candidate — is implemented as a hard
check, and it removes a quarter of the apparent opportunity.

| Status | n | Eligible for ranking |
|---|---|---|
| `experimentally_tested` | 407 | No — already characterised |
| `uncertain_experimental_status` | 497 | No — tested on a scale we cannot interpret, or unresolved |
| **`failed_expression`** | **254** | **No** |
| `no_identified_testing_evidence` | **254** | **Yes** |

The `failed_expression` class is the one that matters. These are 2025 library members that were never
assayed, and the paper's own SI (section S2) states the reason:

> *"Concentration was determined using the Pierce Rapid Gold BCA Protein Assay Kit and the
> concentration normalized via dilution to 0.1 mg/mL... If the concentration was under 0.1 mg/mL, then
> no dilution was performed"* — and elsewhere, enzymes that *"failed purification as evaluated by the
> BCA assay (measured concentration lower than 0.1 mg/mL)"*.

254 of the 263 unassayed library members fall below that 0.1 mg/mL threshold. They are production
failures, not untested opportunities. Two tests enforce this: they can never be eligible for ranking,
and they can never appear as a `below_detection` label.

The remaining 9 unassayed members have adequate yield but no recorded assay, so they are
`uncertain_experimental_status` rather than either category — an honest third answer.

**254 sequences remain genuinely eligible** for later computational ranking: annotation-only records,
mostly from PlasticDB and `degraders_list.tsv`, with no identified PET testing evidence. Each must be
reported with its nearest characterised relative and that relative's identity alongside any score.

---

## 6. Answers to the seven questions

1. **How many unique proteins do we have?** **1,412** unique amino acid sequences — 975 newly added,
   437 original.
2. **How many have reliable positive and below-detection labels?** **208** at the target condition:
   **110** detectable and **98** below detection. A further 4 are uncertain and excluded.
3. **How many independent protein families?** **59** at 70% identity among the 212 labelled enzymes
   (57 among the 208 trainable). One family holds 85 — 40.9% of the data.
4. **Is a leakage-free split feasible?** **Yes, and it is verified**: 0 groups span the split, 0
   cross-split pairs at ≥70%, maximum cross-split identity 0.695. But with 57 groups and one dominant
   family, a single holdout is weak; grouped 5-fold CV is the recommended evaluation.
5. **Which datasets for training and validation?** Train on the 2025 standardised screen at
   cryPow / 40 °C / pH 6.5. Validate by grouped CV within it, with a secondary external check on the
   **17** usable PETML wild types. Everything else is provenance, annotation or biological context.
6. **Any genuinely untested candidates left?** **254** — annotation-only records with no identified
   testing evidence. Not the 263 unassayed library members: 254 of those failed expression.
7. **Next modelling step?** Feature extraction on the curated training set, then a condition-specific
   logistic regression under grouped 5-fold CV, benchmarked against three baselines.

---

## 7. Issues that could still prevent reliable model training

These are real, and none is fixed by better code.

1. **One family is 40.9% of the dataset.** Fold 0 of the grouped CV is a single family. Per-fold results
   will vary widely and must be reported individually.
2. **The label is largely a family property.** 50 of 57 groups are label-pure. A model can score well by
   recognising family membership. The family-membership baseline measured in the evaluation report
   (0.692 leave-one-out accuracy, against 0.538 majority class) is the bar to beat — not 0.5.
3. **208 labelled enzymes, 57 independent units.** This bounds model complexity to regularised linear
   models or small ensembles. Gradient boosting is not justified at this scale.
4. **Negatives are detection-limited.** A zero means "below 0.03 mM in this assay". The blanks were
   clipped to exactly zero, so there is no noise estimate to calibrate against.
5. **13 positives are marginal**, sitting within two rounding steps of the floor. Flagged, but they
   soften the class boundary.
6. **The screen was adaptive.** Round 3 was selected by the paper's own model and has a 70.9% hit rate
   against 50.7% for round 2, and 58 of the families appear in only one round. The positive rate is not
   a natural base rate.
7. **External validation is thin** — 17 proteins, and their labels come from PAZy, which is itself
   positive-unlabelled.
8. **Only one condition is modelled.** Results will not transfer to amorphous film or to 60 °C, where
   positive rates fall as low as 0.

None of these blocks the work. All of them must appear in the limitations section of the final report.

---

## 8. Recommended next step

Extract sequence features for the 208 labelled enzymes — amino acid composition, length,
physicochemical descriptors, catalytic-motif presence — and train a **condition-specific logistic
regression** under **grouped 5-fold cross-validation**, reporting:

- per-fold scores, never a single average
- against three baselines: majority class, shuffled labels, and family-membership-only
- with the paper's own ~0.78 AUROC at cryPow conditions as the external yardstick
- and a secondary check on the 17 PETML wild types

Random Forest and PCA + Logistic Regression as comparators. No gradient boosting.

**Awaiting approval before training.**
